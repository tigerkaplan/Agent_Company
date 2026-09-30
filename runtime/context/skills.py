"""Metadata-first skill discovery. Only explicitly selected instructions are read."""
from dataclasses import dataclass
import json
import re

from runtime.context.contracts import (
    Candidate, DiscoveryError, RepositoryReader, bounded_text, digest, file_material, select,
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DiscoveryError('Duplicate skill metadata field')
        result[key] = value
    return result


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    instructions: str
    sha256: str
    required_capabilities: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    prerequisites: tuple[str, ...]
    references: tuple[str, ...]
    templates: tuple[str, ...]
    version: int = 1

    def __post_init__(self):
        if self.version != 1 or type(self.version) is not int:
            raise DiscoveryError('Unsupported skill metadata version')
        if not isinstance(self.name, str) or not re.fullmatch('[a-z][a-z0-9-]{0,79}', self.name):
            raise DiscoveryError('Invalid skill name')
        bounded_text(self.description)
        bounded_text(self.instructions, 512)
        if not isinstance(self.sha256, str) or not re.fullmatch('[0-9a-f]{64}', self.sha256):
            raise DiscoveryError('Invalid skill digest')
        for values in (self.required_capabilities, self.inputs, self.outputs, self.prerequisites,
                       self.references, self.templates):
            if not isinstance(values, tuple) or len(values) > 32:
                raise DiscoveryError('Invalid skill metadata collection')
            for value in values:
                bounded_text(value, 1024)


class SkillCatalog:
    def __init__(self, reader: RepositoryReader, metadata: tuple[SkillMetadata, ...]):
        if len(metadata) > 256 or len({s.name for s in metadata}) != len(metadata):
            raise DiscoveryError('Invalid skill catalog size or duplicate names')
        instructions = {}
        for skill in metadata:
            skill.__post_init__()
            identity = reader.identity(skill.instructions)
            if identity in instructions:
                raise DiscoveryError('Ambiguous skill instruction identity')
            instructions[identity] = skill.name
            for ref in (*skill.references, *skill.templates):
                reader.path(ref)
        self.reader = reader
        self.metadata = tuple(sorted(metadata, key=lambda s: s.name))
        self._instructions = instructions

    def instruction_name(self, ref: str) -> str | None:
        return self._instructions.get(self.reader.identity(ref))

    @classmethod
    def from_file(cls, reader: RepositoryReader, ref: str = 'skills/catalog.json'):
        try:
            payload = json.loads(reader.read(ref), object_pairs_hook=_unique_object)
            if not isinstance(payload, list) or len(payload) > 256:
                raise DiscoveryError('Invalid skill catalog')
            records = []
            for entry in payload:
                if not isinstance(entry, dict):
                    raise DiscoveryError('Skill catalog entries must be JSON objects')
                entry = dict(entry)
                for field in ('required_capabilities', 'inputs', 'outputs', 'prerequisites', 'references', 'templates'):
                    if not isinstance(entry[field], list):
                        raise DiscoveryError('Invalid skill metadata list')
                    entry[field] = tuple(entry[field])
                records.append(SkillMetadata(**entry))
            return cls(reader, tuple(records))
        except (TypeError, KeyError, ValueError) as error:
            raise DiscoveryError('Malformed skill catalog') from error

    def discover(self, query: str, capabilities: tuple[str, ...], *, ranker=None,
                 limit: int = 4) -> tuple[str, ...]:
        eligible = tuple(Candidate(s.name, s.description, 'skill') for s in self.metadata
                         if set(s.required_capabilities) <= set(capabilities))
        return select(query, eligible, ranker, limit)

    def load(self, selected: tuple[str, ...]):
        if len(selected) > 8 or len(set(selected)) != len(selected):
            raise DiscoveryError('Invalid selected skill set')
        known = {s.name: s for s in self.metadata}
        result = []
        for name in selected:
            if name not in known:
                raise DiscoveryError('Unknown selected skill')
            metadata = known[name]
            material = file_material(self.reader, metadata.instructions, 'skills')
            if digest(material.content.replace('\r\n', '\n')) != metadata.sha256:
                raise DiscoveryError('Selected skill metadata is stale: ' + name)
            result.append(material)
        return tuple(result)
