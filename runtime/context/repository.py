"""Bounded file index and conservative Python syntax relationships, no imports."""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass

from runtime.context.contracts import Candidate, DiscoveryError, RepositoryReader, digest, select


@dataclass(frozen=True)
class FileRecord:
    ref: str
    sha256: str
    symbols: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    syntax: str = 'text'


class RepositoryIndex:
    """Fresh in-memory index of explicit roots. No cache or general graph."""
    EXCLUDED = frozenset({'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.codex', '.agents'})
    EXTENSIONS = frozenset({'.py', '.md', '.json', '.yaml', '.yml', '.txt', '.ts', '.tsx', '.js', '.css'})

    def __init__(self, reader: RepositoryReader):
        self.reader = reader
        self.records: tuple[FileRecord, ...] = ()

    def build(self, roots: tuple[str, ...]) -> tuple[FileRecord, ...]:
        if not roots or len(roots) > 16:
            raise DiscoveryError('Explicit bounded index roots required')
        found = set()
        visited = set()
        count = 0

        def visit(ref, depth):
            nonlocal count
            identity = self.reader.identity(ref)
            path = self.reader.path(ref)
            ref = self.reader.canonical_ref(ref)
            if identity in visited:
                return
            visited.add(identity)
            count += 1
            if count > self.reader.limits.files or depth > self.reader.limits.depth:
                raise DiscoveryError('Repository traversal budget exceeded')
            if any(part in self.EXCLUDED or part.startswith('.') for part in identity.split('/')):
                return
            if path.is_dir():
                children = []
                with os.scandir(path) as entries:
                    for entry in entries:
                        if len(children) + count > self.reader.limits.files:
                            raise DiscoveryError('Directory entry budget exceeded')
                        children.append(entry.name)
                for name in sorted(children):
                    visit(ref + '/' + name, depth + 1)
            elif path.is_file() and path.suffix in self.EXTENSIONS:
                found.add(ref)
            elif not path.exists():
                raise DiscoveryError('Index root is missing')

        for root in sorted(set(roots)):
            visit(root, 0)
        records = []
        for ref in sorted(found):
            content = self.reader.read(ref)
            symbols, imports, calls = set(), set(), set()
            syntax = 'text'
            if ref.endswith('.py'):
                try:
                    tree = ast.parse(content)
                    syntax = 'python'
                    nodes = list(ast.walk(tree))
                    if len(nodes) > 20000:
                        raise DiscoveryError('Python syntax budget exceeded')
                    for node in nodes:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            symbols.add(node.name)
                        elif isinstance(node, ast.Import):
                            imports.update(a.name for a in node.names)
                        elif isinstance(node, ast.ImportFrom):
                            base = ref[:-3].split('/')[:-1]
                            if node.level:
                                base = base[:len(base) - node.level + 1]
                                prefix = '.'.join(base + ([node.module] if node.module else []))
                            else:
                                prefix = node.module or ''
                            imports.add(prefix)
                            imports.update(prefix + '.' + a.name for a in node.names)
                        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            calls.add(node.func.id)
                except (SyntaxError, RecursionError):
                    syntax = 'unparsed_python'
            records.append(FileRecord(ref, digest(content), tuple(sorted(symbols)),
                                      tuple(sorted(imports)), tuple(sorted(calls)), (), syntax))
        modules = {}
        for record in records:
            if record.ref.endswith('.py'):
                module = record.ref[:-3].replace('/', '.')
                modules[module.removesuffix('.__init__')] = record.ref
        linked = []
        for record in records:
            related = tuple(sorted({modules[i] for i in record.imports if i in modules and modules[i] != record.ref}))
            linked.append(FileRecord(record.ref, record.sha256, record.symbols, record.imports,
                                     record.calls, related, record.syntax))
        self.records = tuple(linked)
        return self.records

    def discover(self, query: str, *, ranker=None, limit: int = 8) -> tuple[str, ...]:
        candidates = tuple(Candidate(r.ref, (' '.join(r.symbols + r.imports) or r.ref)[:4096], 'file')
                           for r in self.records)
        return select(query, candidates, ranker, limit)

    def affected(self, refs: tuple[str, ...]) -> tuple[str, ...]:
        refs = tuple(self.reader.canonical_ref(ref) for ref in refs)
        known = {r.ref for r in self.records}
        if not set(refs) <= known:
            raise DiscoveryError('Affected-file query contains unknown paths')
        chosen = set(refs)
        for record in self.records:
            if record.ref in refs:
                chosen.update(record.related)
            if set(record.related) & set(refs):
                chosen.add(record.ref)
        return tuple(sorted(chosen))
