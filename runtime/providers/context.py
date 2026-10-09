"""Build one bounded provider-neutral package from canonical references."""

from __future__ import annotations

from pathlib import Path
from dataclasses import asdict, replace
import os
from uuid import uuid4

from runtime.cache import ContextCache

from runtime.core.sanitization import contains_secret
from runtime.execution.models import ExecutionRequest
from runtime.providers.models import ContextEntry, ExecutionPackage


class ContextBuildError(ValueError):
    """Raised when canonical execution context cannot be loaded safely."""


class ContextDiscoveryBlocked(ContextBuildError):
    """An explicit clarification or unresolved capability blocks discovery."""

    def __init__(self, message: str, *, questions: tuple[str, ...] = ()):
        super().__init__(message)
        if (not isinstance(questions, tuple) or len(questions) > 32
                or any(not isinstance(q, str) or not q.strip() or len(q.encode('utf-8')) > 1024
                       for q in questions)):
            raise ContextBuildError('Invalid context clarification')
        self.questions = tuple(
            'Resolve protected material context through canonical task inputs'
            if contains_secret(q) else q for q in questions
        )


class ExecutionContextBuilder:
    """Load only governance and Worker-resolved canonical context files."""

    def __init__(
        self,
        repository_root: Path,
        *,
        max_file_bytes: int = 128 * 1024,
        max_total_bytes: int = 512 * 1024,
        repository_roots: tuple[str, ...] = (),
        knowledge=None,
        ranker=None,
        capability_requests: tuple = (),
        missing: tuple = (),
        cache: ContextCache | None = None,
        cache_scope: str | None = None,
        external_content: tuple[dict, ...] = (),
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self.repository_roots = repository_roots
        from runtime.context.external import external_materials
        from runtime.context.contracts import DiscoveryError, Limits
        try:
            external_materials(external_content, Limits(file_bytes=max_file_bytes,
                                                       pack_bytes=max_total_bytes))
        except DiscoveryError as error:
            raise ContextBuildError(str(error)) from error
        # Validate bounds/primitive shapes before copying external input.
        self.external_content = tuple(dict(record) for record in external_content)
        self.knowledge = knowledge
        self.ranker = ranker
        self.capability_requests = capability_requests
        self.missing = missing
        if cache is not None and not cache_scope:
            raise ContextBuildError('Shared cache requires an explicit user/scope namespace')
        self.cache = cache if cache is not None else ContextCache()
        self.cache_scope = cache_scope if cache_scope is not None else uuid4().hex
        self.last_cache_result = None

    def build(self, request: ExecutionRequest) -> ExecutionPackage:
        from runtime.context.contracts import DiscoveryError, Limits, RepositoryReader
        from runtime.context.discovery import ContextDiscovery
        from runtime.context.skills import SkillCatalog

        self.last_cache_result = None
        try:
            limits = Limits(file_bytes=self.max_file_bytes, pack_bytes=self.max_total_bytes)
            required = [('project/state', 'CONSTITUTION.md'), ('project/state', 'AGENTS.md'),
                        ('project/state', 'PROJECT_STATE.md')]
            for reference in request.context_refs:
                if reference.get('ref_type') not in {'file', 'project_state'}:
                    continue
                ref = reference.get('ref')
                if not isinstance(ref, str):
                    raise DiscoveryError('Canonical context has no file path')
                source = 'skills' if ref.startswith('skills/') else 'project/state'
                required.append((source, ref))
            files = tuple(ref['ref'] for ref in request.input_refs if ref.get('ref_type') == 'file')
            canonical_refs = ['CONSTITUTION.md', 'AGENTS.md', 'INTENT.md']
            # Membership comes from the local canonical resolver, never source labels
            # or descriptions supplied with arbitrary context references.
            if (self.repository_root / 'orchestrator/routing/agents.yaml').is_file():
                from runtime.core.references import CanonicalReferenceResolver, ReferenceResolutionError
                try:
                    resolved = CanonicalReferenceResolver(self.repository_root, limits=limits).resolve(request.to_dict())
                except ReferenceResolutionError as error:
                    raise DiscoveryError('Canonical instruction selection failed') from error
                canonical_refs.extend(r['ref'] for r in resolved if r['ref_type'] == 'file')
            pack = ContextDiscovery(self.repository_root, limits).discover(
                request.task, required=tuple(required), files=files,
                selected_skills=(request.skill,) if request.skill else (),
                roots=self.repository_roots, knowledge=self.knowledge, ranker=self.ranker,
                capability_requests=self.capability_requests, missing=self.missing,
                external=self.external_content, canonical_refs=tuple(canonical_refs),
            )
            if pack.status != 'READY':
                raise ContextDiscoveryBlocked('Material context is missing',
                                              questions=tuple(m.question for m in pack.missing))
            binding = request.to_dict()
            # Provider choice does not affect this provider-neutral pack. All
            # exact-work and scope fields remain bound, including logical job.
            binding.pop('provider')
            skill_metadata = []
            if any(m.source == 'skills' for m in pack.materials):
                reader = RepositoryReader(self.repository_root, limits)
                catalog = SkillCatalog.from_file(reader)
                identities = {reader.identity(m.ref): m for m in pack.materials if m.source == 'skills'}
                for metadata in catalog.metadata:
                    if reader.identity(metadata.instructions) in identities:
                        # Recheck the catalog/instruction pair together; changed
                        # selected metadata is material even with identical text.
                        loaded = catalog.load((metadata.name,))[0]
                        if replace(loaded, trust=identities[reader.identity(metadata.instructions)].trust) != identities[reader.identity(metadata.instructions)]:
                            raise DiscoveryError('Skill changed during cache validation')
                        skill_metadata.append(asdict(metadata))
                if len(skill_metadata) != len(identities):
                    raise DiscoveryError('Selected skill metadata disappeared during cache validation')
            binding = {'request': binding, 'root': os.path.normcase(str(self.repository_root)),
                       'limits': asdict(limits), 'roots': self.repository_roots,
                       'skills': skill_metadata}
            self.last_cache_result = self.cache.reuse(
                namespace=self.cache_scope, binding=binding, fresh=pack)
            pack = self.last_cache_result.pack
        except (DiscoveryError, OSError, KeyError) as error:
            raise ContextBuildError(str(error)) from error
        entries = tuple(ContextEntry(ref=m.ref, description=f'{m.source}; {m.retention}; evidence only',
                                     content=m.content, origin=m.origin, trust=m.trust,
                                     source_digest=m.source_digest, material=m) for m in pack.materials if m.source != 'user')

        return ExecutionPackage(
            task=request.task,
            task_class=request.task_class,
            project_id=request.project_id,
            agent=request.agent,
            skill=request.skill,
            workflow=request.workflow,
            capability=request.capability,
            risk_level=request.risk_level,
            approval_status=request.approval_status,
            review_required=request.review_required,
            attempt=request.attempt,
            input_refs=request.input_refs,
            context=tuple(entries),
            execution_mode=request.execution_mode,
            execution_scope=request.execution_scope,
            dry_run=request.dry_run,
            context_pack=pack,
            task_contract=request.to_dict().get("task_contract"),
            execution_profile=request.execution_profile,
        )
