"""Assemble minimum selected evidence before provider execution."""
from pathlib import Path

from runtime.context.contracts import (
    DiscoveryError, KnowledgeDiscovery, Limits, Material, MissingInformation,
    RepositoryReader, assemble, bounded_text, digest, file_material, select,
)
from runtime.context.repository import RepositoryIndex
from runtime.context.skills import SkillCatalog
from runtime.context.fallback import resolve_fallback


class ContextDiscovery:
    def __init__(self, root: Path, limits: Limits = Limits()):
        self.root = Path(root)
        self.limits = limits

    def discover(self, query: str, *, required: tuple[tuple[str, str], ...] = (),
                 files: tuple[str, ...] = (), roots: tuple[str, ...] = (),
                 selected_skills: tuple[str, ...] = (), knowledge: KnowledgeDiscovery | None = None,
                 ranker=None, missing: tuple[MissingInformation, ...] = (),
                 availability: tuple[Material, ...] = (), capability_requests: tuple = ()):
        """Required refs are locally resolved; providers cannot configure discovery."""
        bounded_text(query, 16000)
        if len(missing) > 32:
            raise DiscoveryError('Clarification count exceeds limit')
        reader = RepositoryReader(self.root, self.limits)
        if len(required) + len(files) + len(availability) > self.limits.entries:
            raise DiscoveryError('Discovery input count exceeds limit')
        materials = []
        missing = list(missing)
        if len(capability_requests) > 16:
            raise DiscoveryError('Capability request budget exceeded')
        for requirement, implementations in capability_requests:
            resolution = resolve_fallback(requirement, implementations)
            materials.append(resolution.material())
            if resolution.status == 'BLOCKED':
                missing.append(MissingInformation(requirement.capability,
                    'Supply a safe implementation or structured evidence for ' + requirement.capability))
        seen = set()
        catalog = None
        if required or files or roots or selected_skills:
            # The bounded catalog is the inventory of instruction identities,
            # including ordinary-looking files. No instruction bodies are read.
            catalog_required = selected_skills or any(source == 'skills' for source, _ in required)
            try:
                reader.path('skills/catalog.json').stat()
                catalog_present = True
            except FileNotFoundError:
                catalog_present = False
            except OSError as error:
                raise DiscoveryError('Canonical skill catalog cannot be inspected') from error
            if catalog_present or catalog_required:
                catalog = SkillCatalog.from_file(reader)
        loaded_skills = set()

        def load_material(ref, source='files/code'):
            ref = reader.canonical_ref(ref)
            name = catalog.instruction_name(ref) if catalog else None
            if name is not None:
                loaded_skills.add(name)
                if len(loaded_skills) > 8:
                    raise DiscoveryError('Invalid selected skill set')
                return catalog.load((name,))[0]
            if source == 'skills':
                raise DiscoveryError('Skill instructions are absent from canonical catalog')
            return file_material(reader, ref, source)

        # Required/inherited skills are explicit evidence selections too. They
        # must use the same catalog validation, without changing the pinned role.
        for source, ref in required:
            identity = reader.identity(ref)
            if identity not in seen:
                material = load_material(ref, source)
                if material.source == 'project/state' and material.ref.endswith('PROJECT_STATE.md'):
                    # Retain the current checkpoint, not the accumulated dated history.
                    lines = material.content.splitlines(keepends=True)
                    headings = [i for i, line in enumerate(lines) if line.startswith('## ')]
                    if len(headings) > 1:
                        material = Material(source, material.ref, ''.join(lines[:headings[1]]),
                                            material.source_digest, 1, 'excerpt')
                materials.append(material)
                seen.add(identity)
        if len(selected_skills) > 8 or len(set(selected_skills)) != len(selected_skills):
            raise DiscoveryError('Invalid selected skill set')
        for name in selected_skills:
            metadata = next((s for s in catalog.metadata if s.name == name), None)
            if metadata is None:
                raise DiscoveryError('Unknown selected skill')
            identity = reader.identity(metadata.instructions)
            if identity not in seen:
                materials.append(load_material(metadata.instructions, 'skills'))
                seen.add(identity)
        chosen_files = list(files)
        index = RepositoryIndex(reader)
        if roots:
            index.build(roots)
            chosen_files.extend(index.discover(query, ranker=ranker))
        for ref in chosen_files:
            identity = reader.identity(ref)
            if identity not in seen:
                material = load_material(ref)
                indexed = next((r for r in index.records if reader.identity(r.ref) == identity), None)
                if indexed and indexed.sha256 != material.source_digest:
                    raise DiscoveryError('Repository source changed during discovery')
                materials.append(material)
                seen.add(identity)
        if knowledge is not None:
            candidates = knowledge.candidates(query, 32)
            if not isinstance(candidates, tuple) or len(candidates) > 32:
                raise DiscoveryError('Knowledge adapter exceeded candidate budget')
            if any(c.kind not in {'knowledge', 'memory'} for c in candidates):
                raise DiscoveryError('Knowledge adapter returned a non-knowledge source')
            kinds = {c.identity: c.kind for c in candidates}
            for identity in select(query, candidates, ranker, 4):
                material = knowledge.load(identity, self.limits.file_bytes)
                if (material.source != kinds[identity] or material.ref != identity
                        or len(material.content.encode('utf-8')) > self.limits.file_bytes):
                    raise DiscoveryError('Knowledge adapter returned mismatched evidence')
                materials.append(material)
        if any(m.source != 'capability/tool' for m in availability):
            raise DiscoveryError('Availability must be capability evidence')
        materials.extend(availability)
        materials.append(Material('user', 'task', query, digest(query)))
        return assemble(tuple(materials), tuple(missing), self.limits)
