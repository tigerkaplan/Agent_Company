"""Build one bounded provider-neutral package from canonical references."""

from __future__ import annotations

from pathlib import Path

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
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self.repository_roots = repository_roots
        self.knowledge = knowledge
        self.ranker = ranker
        self.capability_requests = capability_requests
        self.missing = missing

    def build(self, request: ExecutionRequest) -> ExecutionPackage:
        from runtime.context.contracts import DiscoveryError, Limits
        from runtime.context.discovery import ContextDiscovery

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
            pack = ContextDiscovery(self.repository_root, limits).discover(
                request.task, required=tuple(required), files=files,
                selected_skills=(request.skill,) if request.skill else (),
                roots=self.repository_roots, knowledge=self.knowledge, ranker=self.ranker,
                capability_requests=self.capability_requests, missing=self.missing,
            )
            if pack.status != 'READY':
                raise ContextDiscoveryBlocked('Material context is missing',
                                              questions=tuple(m.question for m in pack.missing))
        except (DiscoveryError, OSError, KeyError) as error:
            raise ContextBuildError(str(error)) from error
        entries = tuple(ContextEntry(ref=m.ref, description=f'{m.source}; {m.retention}; evidence only',
                                     content=m.content) for m in pack.materials if m.source != 'user')

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
        )
