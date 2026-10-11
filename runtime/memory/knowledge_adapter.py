"""Single-request, explicit-manifest MEM-02 bridge into CORE-08 discovery.

No enumeration API, default scan, global fallback, writes or runtime wiring.
Metadata and exact record fingerprints are supplied locally by the caller.
Construct a new adapter for each request; candidates may be called once only.
CORE-08's project-blind Protocol cannot detect a caller attaching an adapter to
the wrong request before first use. Callers must install the matching instance;
scope checks here protect the manifest and every actual memory load.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from runtime.context.contracts import Candidate, DiscoveryError, Limits, Material, digest, select
from runtime.execution.models import ExecutionRequest
from runtime.memory.contracts import MemoryContractError, MemoryInterface, validate_memory_key
from runtime.memory.lifecycle import (
    LifecycleCandidate, MemoryReference, _canonical, _memory_interface, _text, decode_candidate,
)
from runtime.memory.validity import LifecycleView, LocalSourceChecker, _charge_memory_read, assess_view


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryDiscoveryEntry:
    reference: MemoryReference
    description: str
    record_digest: str

    def __post_init__(self):
        if type(self) is not MemoryDiscoveryEntry or type(self.reference) is not MemoryReference:
            raise MemoryContractError("Noncanonical discovery entry")
        self.reference.__post_init__()
        _text(self.description, "candidate description")
        if (type(self.record_digest) is not str or len(self.record_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.record_digest)):
            raise MemoryContractError("Invalid candidate fingerprint")

    @classmethod
    def from_candidate(cls, candidate: LifecycleCandidate, *, description: str):
        if type(candidate) is not LifecycleCandidate:
            raise MemoryContractError("Noncanonical lifecycle candidate")
        record = candidate.to_memory_record()
        return cls(reference=candidate.reference, description=description,
                   record_digest=digest(_canonical(asdict(record))))


class ProjectKnowledgeDiscovery:
    """Duck-typed KnowledgeDiscovery bound to one canonical execution request.

    Only metadata is accessed in candidates. load reads only offered identities
    through the explicit project key, revalidates the complete lifecycle record,
    and fails on missing or changed evidence. Reported stale/unknown sources stay
    visible as evidence; they are never made CURRENT or silently discarded.
    """
    def __init__(self, request: ExecutionRequest, memory: MemoryInterface, *,
                 entries: tuple[MemoryDiscoveryEntry, ...],
                 views: tuple[LifecycleView, ...] = (),
                 checker: LocalSourceChecker | None = None):
        if type(request) is not ExecutionRequest:
            raise DiscoveryError("Canonical execution request required")
        try:
            validate_memory_key(request.project_id, "discovery")
            _text(request.task, "request task", 16000)
            _memory_interface(memory)
            self._request = request
            self._binding = _canonical(request.to_dict())
            self._project_id = request.project_id
            self._query = request.task
            self._memory = memory
            self._entries = self._validate_entries(entries)
            self._views = self._validate_views(views)
            if checker is not None:
                if type(checker) is not LocalSourceChecker:
                    raise MemoryContractError("Canonical local source checker required")
                checker.assert_project(self._project_id)
            self._checker = checker
            self._read_bytes = 0
            self._manifest_binding = _canonical({
                "entries": [asdict(entry) for entry in self._entries],
                "views": [asdict(view) for view in self._views],
            })
            self._offered = None
        except (MemoryContractError, TypeError, ValueError) as error:
            raise DiscoveryError("Invalid project-bound discovery inputs") from error

    @property
    def project_id(self):
        return self._project_id

    def _validate_entries(self, entries):
        if type(entries) is not tuple or len(entries) > 32:
            raise MemoryContractError("Discovery manifest exceeds bounds")
        unique = {}
        for entry in entries:
            if type(entry) is not MemoryDiscoveryEntry:
                raise MemoryContractError("Noncanonical discovery entry")
            entry.__post_init__()
            if entry.reference.project_id != self._project_id:
                raise MemoryContractError("Discovery candidate project mismatch")
            identity = entry.reference.identity
            if identity in unique and unique[identity] != entry:
                raise MemoryContractError("Conflicting discovery candidate metadata")
            unique[identity] = entry
        return tuple(unique[key] for key in sorted(unique))

    def _validate_views(self, views):
        if type(views) is not tuple or len(views) > 32:
            raise MemoryContractError("Invalid lifecycle view manifest")
        entries = {entry.reference.identity: entry for entry in self._entries}
        unique, pins = {}, {}
        for view in views:
            if type(view) is not LifecycleView:
                raise MemoryContractError("Noncanonical lifecycle view")
            view.__post_init__()
            identity = view.subject.reference.identity
            entry = entries.get(identity)
            if entry is None or entry.record_digest != view.subject.record_digest:
                raise MemoryContractError("View subject does not match discovery manifest")
            if identity in unique:
                raise MemoryContractError("Duplicate selected lifecycle view")
            unique[identity] = view
            for pin in view.pins:
                if pin.reference.project_id != self._project_id:
                    raise MemoryContractError("Foreign lifecycle view dependency")
                key = pin.reference.identity
                if key in pins and pins[key] != pin:
                    raise MemoryContractError("Conflicting view dependency fingerprints")
                if key in entries and entries[key].record_digest != pin.record_digest:
                    raise MemoryContractError("Dependency conflicts with discovery manifest")
                pins[key] = pin
        return tuple(unique[key] for key in sorted(unique))

    def _revalidate(self):
        try:
            if (_canonical(self._request.to_dict()) != self._binding
                    or self._request.project_id != self._project_id
                    or self._request.task != self._query):
                raise DiscoveryError("Discovery request binding changed")
            self._validate_entries(self._entries)
            self._validate_views(self._views)
            if self._manifest_binding != _canonical({
                    "entries": [asdict(entry) for entry in self._entries],
                    "views": [asdict(view) for view in self._views]}):
                raise DiscoveryError("Discovery manifest binding changed")
            if self._checker is not None:
                self._checker.assert_project(self._project_id)
        except (MemoryContractError, TypeError, ValueError, AttributeError) as error:
            raise DiscoveryError("Discovery request or manifest changed") from error

    def assert_request(self, request: ExecutionRequest) -> None:
        """Explicit caller check before installing this project-blind Protocol."""
        self._revalidate()
        if type(request) is not ExecutionRequest or _canonical(request.to_dict()) != self._binding:
            raise DiscoveryError("Adapter belongs to a different execution request")

    def candidates(self, query: str, limit: int) -> tuple[Candidate, ...]:
        self._revalidate()
        if self._offered is not None:
            raise DiscoveryError("Request discovery adapter cannot be reused")
        if type(query) is not str or query != self._query:
            raise DiscoveryError("Discovery query does not match bound request")
        if type(limit) is not int or not 1 <= limit <= 32:
            raise DiscoveryError("Invalid candidate limit")
        metadata = tuple(Candidate(e.reference.identity, e.description, "memory")
                         for e in self._entries)
        narrowed = select(query, metadata, limit=limit)
        by_id = {candidate.identity: candidate for candidate in metadata}
        self._offered = frozenset(narrowed)
        return tuple(by_id[identity] for identity in narrowed)

    def load(self, identity: str, max_bytes: int) -> Material:
        self._revalidate()
        if (type(identity) is not str or self._offered is None
                or identity not in self._offered):
            raise DiscoveryError("Memory source was not offered by this request")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 1024 * 1024:
            raise DiscoveryError("Invalid selected evidence byte limit")
        entry = next(e for e in self._entries if e.reference.identity == identity)
        try:
            # A failed request budget cannot be retried into more provider reads.
            _charge_memory_read(0, self._checker, self._charge_memory)
            view = next((view for view in self._views
                         if view.subject.reference.identity == identity), None)
            if view is not None:
                content = assess_view(view, self._memory, max_bytes=max_bytes,
                                      checker=self._checker, _charge_memory=self._charge_memory)
                return Material("memory", identity, content, digest(content),
                                origin="retrieved", trust="untrusted", authority="none")
            stored = self._memory.get(self._project_id, entry.reference.record_id)
            decode_candidate(self._project_id, stored, record_id=entry.reference.record_id)
            complete = _canonical(asdict(stored))
            if digest(complete) != entry.record_digest:
                raise MemoryContractError("Memory source changed since manifest capture")
            _charge_memory_read(len(complete.encode("utf-8")), self._checker, self._charge_memory)
            if len(stored.claim.encode("utf-8")) > max_bytes:
                raise MemoryContractError("Selected evidence exceeds byte limit")
            return Material("memory", identity, stored.claim, digest(stored.claim),
                            origin="retrieved", trust="untrusted", authority="none")
        except Exception as error:
            raise DiscoveryError("Selected memory evidence unavailable or invalid") from error

    def _charge_memory(self, size):
        """All complete records share CORE-08's default request scan ceiling."""
        self._read_bytes += size
        if self._read_bytes > Limits().scan_bytes:
            raise MemoryContractError("Request dependency read budget exceeded")
