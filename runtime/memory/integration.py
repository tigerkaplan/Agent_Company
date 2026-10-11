"""Explicit foreground host composition; memory is evidence, never job authority.

The host installs project/root mappings, a metadata manifest callback and, for
storage only, a separate authority checker. That checker must consult actual
scoped human authority for the supplied sink object, project and exact pins.
This module creates no approval, tool, durable authority, provider or watcher.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from runtime.context.contracts import DiscoveryError, Limits, RepositoryReader
from runtime.execution.models import ExecutionRequest
from runtime.memory.action_trace import ActionTraceOwners, ActionTraceRequest, build_action_candidates
from runtime.memory.contracts import MemoryContractError, validate_memory_key
from runtime.memory.knowledge_adapter import ProjectKnowledgeDiscovery
from runtime.memory.lifecycle import LifecycleCandidate, MemoryReference, _canonical, _memory_interface, store_candidate
from runtime.memory.validity import (
    LocalSourceChecker, PinnedMemory, decode_evidence, prepare_evidence, store_evidence,
)


class MemoryIntegrationError(MemoryContractError):
    """Missing or mismatched explicit foreground inputs/authority."""


@dataclass(frozen=True, slots=True)
class StorageReport:
    """Only confirmed read-backs are stored; the failing write may have happened."""
    stored: tuple[PinnedMemory, ...]
    uncertain: MemoryReference | None = None
    unattempted: tuple[MemoryReference, ...] = ()
    failure: str | None = None


class _ForegroundDiscovery:
    def __init__(self, integration, adapter, root, limits):
        self.integration, self.adapter = integration, adapter
        self.root, self.limits = root, limits

    def assert_context(self, request, root, limits):
        self.integration.assert_root(root)
        if limits != self.limits:
            raise DiscoveryError("Memory context bounds changed")
        self.assert_request(request)

    def assert_request(self, request):
        self.integration._assert_request(request, self.root)
        self.adapter.assert_request(request)

    def candidates(self, query, limit):
        self.integration.assert_root(self.root)
        return self.adapter.candidates(query, limit)

    def load(self, identity, max_bytes):
        self.integration.assert_root(self.root)
        return self.adapter.load(identity, max_bytes)


class ForegroundMemoryIntegration:
    """A trusted host-installed port for one project and existing source root.

    manifest(request) returns exactly (entries, views), both explicit tuples.
    authorize_storage(project_id, sink, exact_pins) must independently check
    scoped storage authority; execution approval or an opt-in is insufficient.
    No public operation accepts an approval flag or execution approval record.
    """
    def __init__(self, project_id, project_root, memory, *, manifest,
                 owners: ActionTraceOwners | None = None, authorize_storage=None):
        validate_memory_key(project_id, "foreground")
        _memory_interface(memory)
        if not callable(manifest) or (authorize_storage is not None and not callable(authorize_storage)):
            raise MemoryIntegrationError("Trusted foreground callbacks required")
        if owners is not None:
            if type(owners) is not ActionTraceOwners:
                raise MemoryIntegrationError("Canonical trace owners required")
            owners.validate()
        self.project_id, self.memory = project_id, memory
        self.project_path = Path(project_root).absolute()
        self.project_root = self.project_path.resolve(strict=True)
        if not self.project_root.is_dir():
            raise MemoryIntegrationError("Existing project directory required")
        identity = self.project_root.stat()
        self._root_identity = (identity.st_dev, identity.st_ino)
        self.manifest, self.owners = manifest, owners
        self.authorize_storage = authorize_storage
        self._binding = (project_id, self.project_root, memory, manifest, owners, authorize_storage)

    def assert_root(self, root):
        try:
            identity = self.project_root.stat()
            if (type(self) is not ForegroundMemoryIntegration
                    or self._binding != (self.project_id, self.project_root, self.memory,
                                         self.manifest, self.owners, self.authorize_storage)
                    or self.project_path.resolve(strict=True) != self.project_root
                    or Path(root).resolve(strict=True) != self.project_root
                    or (identity.st_dev, identity.st_ino) != self._root_identity
                    or not self.project_root.is_dir()):
                raise MemoryIntegrationError("Foreground project/root binding changed or foreign")
        except (OSError, ValueError) as error:
            raise DiscoveryError("Foreground project/root unavailable or foreign") from error

    def _assert_request(self, request, root):
        self.assert_root(root)
        if type(request) is not ExecutionRequest or request.project_id != self.project_id:
            raise DiscoveryError("Foreign foreground execution request")
        try:
            validate_memory_key(request.project_id, "foreground")
            # Reconstruct without mutating the consumer. Canonical construction
            # validates scope/contract/reference shapes before any discovery I/O.
            if type(request.attempt) is not int or replace(request).to_dict() != request.to_dict():
                raise MemoryIntegrationError("Noncanonical foreground request")
        except (ValueError, TypeError, AttributeError) as error:
            raise DiscoveryError("Invalid foreground execution request") from error

    def request_adapter(self, request, root, limits):
        """Construct once per build; validate before metadata or any body reads."""
        self._assert_request(request, root)
        if type(limits) is not Limits:
            raise DiscoveryError("Canonical context limits required")
        limits.__post_init__()
        binding = _canonical(request.to_dict())
        manifest = self.manifest(request)
        if type(manifest) is not tuple or len(manifest) != 2:
            raise DiscoveryError("Explicit entries and views required")
        # The callback cannot redirect a root, sink or request mid-installation.
        self._assert_request(request, root)
        if _canonical(request.to_dict()) != binding:
            raise DiscoveryError("Execution request changed during manifest selection")
        adapter = ProjectKnowledgeDiscovery(request, self.memory, entries=manifest[0],
            views=manifest[1], checker=LocalSourceChecker(self.project_id,
                                                        RepositoryReader(self.project_root, limits)))
        return _ForegroundDiscovery(self, adapter, self.project_root, limits)

    def capture(self, request: ActionTraceRequest, *, max_candidate_bytes=128 * 1024):
        """Read only the explicit retained action; never store or complete it."""
        self.assert_root(self.project_root)
        if type(request) is not ActionTraceRequest or request.project_id != self.project_id:
            raise MemoryIntegrationError("Foreign foreground capture request")
        request.__post_init__()
        if self.owners is None:
            raise MemoryIntegrationError("Explicit canonical trace owners required")
        return build_action_candidates(request, self.owners,
                                       max_candidate_bytes=max_candidate_bytes)

    def _pins(self, candidates):
        self.assert_root(self.project_root)
        if type(candidates) is not tuple or not 1 <= len(candidates) <= 32:
            raise MemoryIntegrationError("Explicit bounded candidate writes required")
        pins = []
        for candidate in candidates:
            if type(candidate) is not LifecycleCandidate:
                raise MemoryIntegrationError("Canonical candidate required")
            candidate.__post_init__()
            if candidate.reference.project_id != self.project_id:
                raise MemoryIntegrationError("Foreign candidate write")
            pins.append(PinnedMemory.from_record(candidate.to_memory_record()))
        if len({p.reference.identity for p in pins}) != len(pins):
            raise MemoryIntegrationError("Duplicate candidate write identity")
        return tuple(pins)

    def _authorize(self, pins):
        self.assert_root(self.project_root)
        if self.authorize_storage is None:
            raise MemoryIntegrationError("Separate scoped storage authority required")
        if self.authorize_storage(self.project_id, self.memory, pins) is not True:
            raise MemoryIntegrationError("Separate scoped storage authority denied")
        self.assert_root(self.project_root)

    def _store(self, candidates, writer):
        pins = self._pins(candidates)
        # Authorize the entire exact plan before any storage/dependency I/O.
        self._authorize(pins)
        if self._pins(candidates) != pins:
            raise MemoryIntegrationError("Candidate writes changed during authority check")
        stored = []
        for index, candidate in enumerate(candidates):
            try:
                self._authorize(pins)
                if self._pins(candidates) != pins:
                    raise MemoryIntegrationError("Candidate write plan changed")
                returned = writer(candidate)
                confirmed = PinnedMemory.from_record(returned)
                if confirmed != pins[index]:
                    raise MemoryIntegrationError("Stored evidence differs from authorized pin")
                stored.append(confirmed)
            except Exception:
                # No rollback or automatic retry, even if a broken sink mutated
                # then raised. Nothing here modifies the source job's outcome.
                return StorageReport(tuple(stored), candidate.reference,
                    tuple(c.reference for c in candidates[index + 1:]), "storage_unconfirmed")
        return StorageReport(tuple(stored))

    def store_candidates(self, candidates):
        self._pins(candidates)
        # Event writes must use their existing dependency/cycle checks.
        if any(decode_evidence(c) is not None for c in candidates):
            raise MemoryIntegrationError("Lifecycle events require store_event and explicit dependencies")
        return self._store(candidates, lambda c: store_candidate(self.project_id, c, self.memory))

    def store_event(self, event, *, dependencies=()):
        candidate = prepare_evidence(event)
        self._pins((candidate,))
        if type(dependencies) is not tuple or len(dependencies) > 31:
            raise MemoryIntegrationError("Explicit bounded event dependencies required")
        for pin in dependencies:
            if type(pin) is not PinnedMemory or pin.reference.project_id != self.project_id:
                raise MemoryIntegrationError("Foreign event dependency")
            pin.__post_init__()
        dependency_binding = _canonical([asdict(pin) for pin in dependencies])

        def write(bound_candidate):
            if (prepare_evidence(event) != bound_candidate
                    or _canonical([asdict(pin) for pin in dependencies]) != dependency_binding):
                raise MemoryIntegrationError("Event or dependencies changed during authority check")
            return store_evidence(self.project_id, event, self.memory, dependencies=dependencies)

        return self._store((candidate,), write)
