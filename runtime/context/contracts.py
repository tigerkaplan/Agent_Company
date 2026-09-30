"""Immutable evidence contracts and bounded filesystem access for CORE-08."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


class DiscoveryError(ValueError):
    """Discovery cannot safely supply the requested evidence."""


def bounded_text(value: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode('utf-8')) > limit:
        raise DiscoveryError('Invalid or oversized discovery text')
    return value


def digest(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Limits:
    files: int = 256
    entries: int = 48
    file_bytes: int = 128 * 1024
    scan_bytes: int = 2 * 1024 * 1024
    pack_bytes: int = 512 * 1024
    depth: int = 8

    def __post_init__(self):
        ceilings = (2048, 128, 1024 * 1024, 16 * 1024 * 1024, 2 * 1024 * 1024, 16)
        for value, ceiling in zip(asdict(self).values(), ceilings):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise DiscoveryError('Invalid discovery limit')


class RepositoryReader:
    def __init__(self, root: Path, limits: Limits = Limits()):
        self.root = Path(root).resolve(strict=True)
        self.limits = limits
        self.bytes_read = 0

    def path(self, ref: str) -> Path:
        bounded_text(ref, 512)
        # Reject aliases, drive paths, ADS, links and traversal on every platform.
        if ('\\' in ref or ':' in ref
                or any(not p or p.endswith(('.', ' ')) for p in ref.split('/'))):
            raise DiscoveryError('Non-canonical repository path')
        relative = PurePosixPath(ref)
        if relative.is_absolute():
            raise DiscoveryError('Absolute repository path')
        path = self.root
        for part in relative.parts:
            path = path / part
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise DiscoveryError('Repository links are not discovery sources')
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise DiscoveryError('Repository path escapes root')
        return resolved

    def canonical_ref(self, ref: str) -> str:
        """Actual filesystem spelling, retaining readable source provenance."""
        return self.path(ref).relative_to(self.root).as_posix()

    def identity(self, ref: str) -> str:
        """One validated identity for Windows aliases, exact paths elsewhere."""
        return os.path.normcase(self.canonical_ref(ref)).replace('\\', '/')

    def read(self, ref: str) -> str:
        path = self.path(ref)
        try:
            if not path.is_file():
                raise DiscoveryError('Required context file is missing: ' + ref)
            with path.open('rb') as stream:
                data = stream.read(self.limits.file_bytes + 1)
            self.bytes_read += len(data)
            if len(data) > self.limits.file_bytes or self.bytes_read > self.limits.scan_bytes:
                raise DiscoveryError('Discovery read budget exceeded')
            return data.decode('utf-8')
        except (OSError, UnicodeError) as error:
            raise DiscoveryError('Context file cannot be read: ' + ref) from error


@dataclass(frozen=True)
class Candidate:
    identity: str
    description: str
    kind: str

    def __post_init__(self):
        bounded_text(self.identity, 512)
        bounded_text(self.description)
        if self.kind not in {'skill', 'file', 'knowledge', 'memory'}:
            raise DiscoveryError('Invalid relevance candidate kind')


class RelevanceRanker(Protocol):
    """Return only candidate identities, in relevance order; never instructions."""
    def rank(self, query: str, candidates: tuple[Candidate, ...]) -> tuple[str, ...]: ...


class DeterministicRanker:
    def rank(self, query: str, candidates: tuple[Candidate, ...]) -> tuple[str, ...]:
        tokens = lambda text: set(re.findall(r'[a-z0-9]+', text.lower()))
        wanted = tokens(query)
        scored = [(len(wanted & tokens(c.identity + ' ' + c.description)), c.identity) for c in candidates]
        return tuple(identity for score, identity in sorted(scored, key=lambda x: (-x[0], x[1])) if score)


def select(query: str, candidates: tuple[Candidate, ...], ranker: RelevanceRanker | None = None,
           limit: int = 8) -> tuple[str, ...]:
    bounded_text(query, 16000)
    if type(limit) is not int or not 1 <= limit <= 48 or len(candidates) > 256:
        raise DiscoveryError('Selection bounds exceeded')
    known = {c.identity for c in candidates}
    if len(known) != len(candidates):
        raise DiscoveryError('Duplicate candidate identity')
    # An optional semantic implementation cannot inject sources or select authority.
    try:
        result = (ranker or DeterministicRanker()).rank(query, candidates)
        if (not isinstance(result, tuple) or len(result) > len(candidates)
                or any(not isinstance(i, str) or i not in known for i in result)
                or len(set(result)) != len(result)):
            raise DiscoveryError('Ranker returned invalid identities')
    except Exception as error:
        raise DiscoveryError('Relevance ranking failed closed') from error
    return result[:limit]


@dataclass(frozen=True)
class Material:
    source: str
    ref: str
    content: str
    source_digest: str
    start_line: int = 1
    retention: str = 'verbatim'

    def __post_init__(self):
        if self.source not in {'project/state', 'files/code', 'skills', 'knowledge', 'memory',
                               'user', 'capability/tool'}:
            raise DiscoveryError('Unknown context source')
        bounded_text(self.ref, 512)
        if not isinstance(self.content, str) or len(self.content.encode('utf-8')) > 1024 * 1024:
            raise DiscoveryError('Invalid or oversized context content')
        if not re.fullmatch('[0-9a-f]{64}', self.source_digest):
            raise DiscoveryError('Missing source digest')
        if type(self.start_line) is not int or self.start_line < 1:
            raise DiscoveryError('Invalid source line')
        if self.retention not in {'verbatim', 'excerpt'}:
            raise DiscoveryError('Unsupported retention mode')


class KnowledgeDiscovery(Protocol):
    """Read-only metadata-first interface. Implementations own bounded retrieval.

    No persistence or policy promotion; the caller explicitly installs an adapter.
    """
    def candidates(self, query: str, limit: int) -> tuple[Candidate, ...]: ...
    def load(self, identity: str, max_bytes: int) -> Material: ...


@dataclass(frozen=True)
class MissingInformation:
    field: str
    question: str
    material: bool = True

    def __post_init__(self):
        bounded_text(self.field, 128)
        bounded_text(self.question, 1024)
        if type(self.material) is not bool:
            raise DiscoveryError('Invalid clarification flag')


@dataclass(frozen=True)
class ContextPack:
    materials: tuple[Material, ...]
    missing: tuple[MissingInformation, ...] = ()

    @property
    def status(self) -> str:
        return 'BLOCKED' if self.missing else 'READY'

    def payload(self) -> dict:
        return {'version': 1, 'authority': 'none', 'status': self.status,
                'materials': [asdict(m) for m in self.materials],
                'missing': [asdict(m) for m in self.missing]}

    def render(self) -> str:
        return json.dumps(self.payload(), sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def assemble(materials: tuple[Material, ...], missing: tuple[MissingInformation, ...] = (),
             limits: Limits = Limits()) -> ContextPack:
    if len(materials) > limits.entries or len(missing) > 32:
        raise DiscoveryError('Context entry budget exceeded')
    unique: dict[tuple, Material] = {}
    for m in materials:
        m.__post_init__()
        key = (m.source, m.ref, m.start_line)
        if key in unique and unique[key] != m:
            raise DiscoveryError('Conflicting context provenance')
        unique[key] = m
    questions = {}
    for item in missing:
        item.__post_init__()
        if item.material:
            if item.field in questions and questions[item.field] != item:
                raise DiscoveryError('Conflicting clarification')
            questions[item.field] = item
    pack = ContextPack(tuple(unique.values()), tuple(questions.values()))
    if len(pack.render().encode('utf-8')) > limits.pack_bytes:
        raise DiscoveryError('Serialized context pack exceeds size limit')
    return pack


def file_material(reader: RepositoryReader, ref: str, source: str = 'files/code',
                  lines: tuple[int, int] | None = None) -> Material:
    ref = reader.canonical_ref(ref)
    content = reader.read(ref)
    original_digest = digest(content)
    start = 1
    if lines is not None:
        start, end = lines
        all_lines = content.splitlines(keepends=True)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(all_lines):
            raise DiscoveryError('Invalid verbatim line range')
        content = ''.join(all_lines[start - 1:end])
    return Material(source, ref, content, original_digest, start, 'excerpt' if lines else 'verbatim')
