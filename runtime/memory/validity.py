"""Bounded MEM-02 evidence and supplied-view overlays; no promotion or storage.

Only installed local checking code observes source bytes. Event outcomes,
relationships, actors, versions and review narratives remain caller-declared.
An explicit view cannot establish completeness or latest global state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json

from runtime.context.contracts import DiscoveryError, RepositoryReader, digest
from runtime.memory.contracts import (
    ActorTimeProvenance, ClaimStatus, EvidenceOrigin, MemoryContractError,
    MemoryInterface, MemoryRecord, SourceEvidence, _digest, _provenance, _sources,
    validate_memory_key, validate_memory_record,
)
from runtime.memory.lifecycle import (
    LifecycleCandidate, MemoryLink, MemoryReference, _actor, _canonical,
    _memory_interface, _object, _sources as _decode_sources, _text, _unique_object,
    decode_candidate, prepare_candidate, store_candidate,
)


class Usability(str, Enum):
    UNKNOWN = "unknown"
    VALID_FOR_REUSE = "valid-for-reuse"
    INVALIDATED = "invalidated"
    CONFLICTED = "conflicted"


class SourceObservationState(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class PinnedMemory:
    reference: MemoryReference
    record_digest: str

    def __post_init__(self):
        if type(self) is not PinnedMemory or type(self.reference) is not MemoryReference:
            raise MemoryContractError("Noncanonical pinned memory")
        self.reference.__post_init__()
        _digest(self.record_digest, "complete-record fingerprint")

    @classmethod
    def from_record(cls, stored: MemoryRecord):
        if type(stored) is not MemoryRecord:
            raise MemoryContractError("Canonical stored record required")
        validate_memory_record(stored.project_id, stored)
        decode_candidate(stored.project_id, stored, record_id=stored.record_id)
        return cls(reference=MemoryReference(project_id=stored.project_id,
                   record_id=stored.record_id), record_digest=digest(_canonical(asdict(stored))))


def _pin(pin, project_id):
    if type(pin) is not PinnedMemory:
        raise MemoryContractError("Canonical pinned memory required")
    pin.__post_init__()
    if pin.reference.project_id != project_id:
        raise MemoryContractError("Pinned evidence project mismatch")


def _event(event, cls):
    if type(event) is not cls or type(event.reference) is not MemoryReference:
        raise MemoryContractError("Noncanonical lifecycle event")
    event.reference.__post_init__()
    _sources(event.sources, event.reference.project_id)
    _provenance(event.capture, event.review)


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidityEvidence:
    """Historical declaration, including observations; never current authority."""
    reference: MemoryReference
    subject: PinnedMemory
    outcome: Usability
    basis: str
    check_id: str
    check_version: str
    sources: tuple[SourceEvidence, ...]
    previous: PinnedMemory | None = None
    capture: ActorTimeProvenance | None = None
    review: ActorTimeProvenance | None = None

    def __post_init__(self):
        _event(self, ValidityEvidence)
        _pin(self.subject, self.reference.project_id)
        if type(self.outcome) is not Usability:
            raise MemoryContractError("Invalid validity outcome")
        for value, label in ((self.basis, "validity basis"), (self.check_id, "check ID"),
                             (self.check_version, "check version")):
            _text(value, label)
        if self.previous is not None:
            _pin(self.previous, self.reference.project_id)
        if any(pin.reference == self.reference for pin in _event_pins(self)):
            raise MemoryContractError("Self-referencing validity event")


@dataclass(frozen=True, slots=True, kw_only=True)
class SupersessionEvidence:
    """Explicit pinned intent; byte identity does not prove replacement intent."""
    reference: MemoryReference
    predecessor: PinnedMemory
    successor: PinnedMemory
    applicability: str
    rationale: str
    sources: tuple[SourceEvidence, ...]
    capture: ActorTimeProvenance | None = None
    review: ActorTimeProvenance | None = None

    def __post_init__(self):
        _event(self, SupersessionEvidence)
        for pin in (self.predecessor, self.successor):
            _pin(pin, self.reference.project_id)
            if pin.reference == self.reference:
                raise MemoryContractError("Event cannot be a relationship endpoint")
        if self.predecessor.reference == self.successor.reference:
            raise MemoryContractError("Self supersession")
        _text(self.applicability, "relationship applicability")
        _text(self.rationale, "relationship rationale")


def _event_pins(event):
    if type(event) is ValidityEvidence:
        return (event.subject,) + (() if event.previous is None else (event.previous,))
    return (event.predecessor, event.successor)


def prepare_evidence(event: ValidityEvidence | SupersessionEvidence) -> LifecycleCandidate:
    if type(event) not in (ValidityEvidence, SupersessionEvidence):
        raise MemoryContractError("Unknown lifecycle event type")
    event.__post_init__()
    kind = "memory-validity-evidence" if type(event) is ValidityEvidence else "memory-supersession-evidence"
    original = MemoryRecord(project_id=event.reference.project_id,
        record_id=event.reference.record_id,
        claim=_canonical({"kind": kind, "version": 1, "evidence": asdict(event)}),
        status=ClaimStatus.REPORTED, sources=event.sources,
        capture=event.capture, review=event.review)
    links = tuple(MemoryLink(project_id=pin.reference.project_id, kind="memory",
                  target=pin.reference.identity, version=pin.record_digest)
                  for pin in _event_pins(event))
    return prepare_candidate(event.reference.project_id, original,
                             record_id=event.reference.record_id, links=links)


def _decode_pin(value):
    values = _object(PinnedMemory, value)
    values["reference"] = MemoryReference(**_object(MemoryReference, values["reference"]))
    return PinnedMemory(**values)


def decode_evidence(candidate: LifecycleCandidate):
    """Recognize event originals and require exact canonical event bindings."""
    if type(candidate) is not LifecycleCandidate:
        raise MemoryContractError("Canonical lifecycle candidate required")
    candidate.__post_init__()
    try:
        value = json.loads(candidate.original.claim, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError):
        # Ordinary claims need not be JSON. Reserved event claims must be JSON.
        if '"memory-validity-evidence"' in candidate.original.claim or '"memory-supersession-evidence"' in candidate.original.claim:
            raise MemoryContractError("Malformed event JSON")
        return None
    if type(value) is not dict:
        return None
    kind = value.get("kind")
    if kind not in ("memory-validity-evidence", "memory-supersession-evidence"):
        if type(kind) is str and kind.startswith(("memory-validity-", "memory-supersession-")):
            raise MemoryContractError("Unsupported lifecycle event kind")
        return None
    try:
        if (set(value) != {"kind", "version", "evidence"}
                or type(value["version"]) is not int or value["version"] != 1):
            raise MemoryContractError("Malformed event envelope")
        cls = ValidityEvidence if value["kind"] == "memory-validity-evidence" else SupersessionEvidence
        values = _object(cls, value["evidence"])
        values.update(reference=MemoryReference(**_object(MemoryReference, values["reference"])),
                      sources=_decode_sources(values["sources"]),
                      capture=_actor(values["capture"]), review=_actor(values["review"]))
        if cls is ValidityEvidence:
            values.update(subject=_decode_pin(values["subject"]), outcome=Usability(values["outcome"]),
                          previous=None if values["previous"] is None else _decode_pin(values["previous"]))
        else:
            values.update(predecessor=_decode_pin(values["predecessor"]),
                          successor=_decode_pin(values["successor"]))
        event = cls(**values)
        if prepare_evidence(event) != candidate:
            raise MemoryContractError("Stored event binding mismatch")
        return event
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as error:
        raise MemoryContractError("Malformed stored lifecycle event") from error


@dataclass(frozen=True, slots=True, kw_only=True)
class LifecycleView:
    """One selected subject and its explicitly supplied dependency closure.

    Coverage is caller-declared. All records are required, never silently pruned.
    Separate views permit metadata-only selection without reading other closures.
    """
    subject: PinnedMemory
    dependencies: tuple[PinnedMemory, ...] = ()
    coverage: str = "explicit supplied view; global completeness unknown"

    def __post_init__(self):
        if type(self) is not LifecycleView or type(self.subject) is not PinnedMemory:
            raise MemoryContractError("Noncanonical lifecycle view")
        self.subject.__post_init__()
        _text(self.coverage, "declared view coverage")
        if type(self.dependencies) is not tuple or len(self.dependencies) > 31:
            raise MemoryContractError("Dependency closure exceeds 32 records")
        seen = set()
        for pin in self.pins:
            _pin(pin, self.subject.reference.project_id)
            if pin.reference.identity in seen:
                raise MemoryContractError("Duplicate or conflicting dependency identity")
            seen.add(pin.reference.identity)

    @property
    def pins(self):
        return (self.subject,) + self.dependencies


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceObservation:
    source: SourceEvidence
    state: SourceObservationState
    basis: str
    observed_digest: str | None = None

    def __post_init__(self):
        if type(self) is not SourceObservation or type(self.source) is not SourceEvidence:
            raise MemoryContractError("Noncanonical source observation")
        self.source.__post_init__()
        if type(self.state) is not SourceObservationState:
            raise MemoryContractError("Invalid source observation")
        _text(self.basis, "source observation basis")
        if self.observed_digest is not None:
            _digest(self.observed_digest, "observed source bytes")
        if self.state in (SourceObservationState.MATCH, SourceObservationState.MISMATCH):
            if (self.observed_digest is None or
                    (self.observed_digest == self.source.source_digest) != (self.state is SourceObservationState.MATCH)):
                raise MemoryContractError("Source observation digest mismatch")
        elif self.observed_digest is not None:
            raise MemoryContractError("Incomplete source observation cannot assert a digest")


def _reserved_windows_component(part):
    """Device names remain reserved in every directory and with extensions."""
    name = part.partition(".")[0].rstrip(" ").upper()
    return (name in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            or (len(name) == 4 and name[:3] in {"COM", "LPT"}
                and name[3] in "123456789\u00b9\u00b2\u00b3"))


class LocalSourceChecker:
    """Installed checking code with an explicit project-to-reader-root binding.

    The shared RepositoryReader accounts reads across the request. Locations,
    origins and version labels cannot configure roots or authenticate sources.
    Supports complete UTF-8 local files only; spans and other origins are UNKNOWN.
    """
    def __init__(self, project_id: str, reader: RepositoryReader):
        validate_memory_key(project_id, "source-check")
        if type(reader) is not RepositoryReader:
            raise MemoryContractError("Canonical bounded RepositoryReader required")
        reader.limits.__post_init__()
        self.project_id = project_id
        self.reader = reader
        self._binding = (project_id, reader.root, reader.limits)

    def assert_project(self, project_id):
        if (type(self) is not LocalSourceChecker or type(self.reader) is not RepositoryReader
                or project_id != self.project_id
                or (self.project_id, self.reader.root, self.reader.limits) != self._binding):
            raise MemoryContractError("Local source checker binding changed or foreign")
        self.reader.limits.__post_init__()

    def observe(self, source: SourceEvidence) -> SourceObservation:
        if type(source) is not SourceEvidence:
            raise MemoryContractError("Canonical source evidence required")
        source.__post_init__()
        self.assert_project(source.project_id)
        state, basis, observed = SourceObservationState.UNKNOWN, "unsupported source identity/freshness check", None
        ref = source.location
        if (source.origin is EvidenceOrigin.REPOSITORY and len(ref.encode("utf-8")) <= 512
                and not any(part in {"", ".", ".."} for part in ref.split("/"))
                and not any(_reserved_windows_component(part) for part in ref.split("/"))
                and not any(char in ref for char in "\\:#?")):
            try:
                path = self.reader.path(ref)
                try:
                    path.stat()
                except FileNotFoundError:
                    state, basis = SourceObservationState.MISSING, "confirmed local source deletion in configured root"
                else:
                    # Do not treat directories, aliases or failed/partial reads as deletion.
                    if path.is_file() and self.reader.canonical_ref(ref) == ref:
                        observed = digest(self.reader.read(ref))
                        state = (SourceObservationState.MATCH if observed == source.source_digest
                                 else SourceObservationState.MISMATCH)
                        basis = "complete local source bytes compared; version/publisher/entailment unauthenticated"
            except DiscoveryError as error:
                if str(error) == "Discovery read budget exceeded":
                    raise MemoryContractError("Local source read budget exceeded") from error
                state, basis, observed = SourceObservationState.UNKNOWN, "local source read failed, partial or outside supported bounds", None
            except (OSError, ValueError, UnicodeError):
                state, basis, observed = SourceObservationState.UNKNOWN, "local source read failed, partial or outside supported bounds", None
        return SourceObservation(source=source, state=state, basis=basis, observed_digest=observed)


def _acyclic(graph):
    visiting, done = set(), set()
    def visit(node):
        if node in visiting:
            raise MemoryContractError("Cyclic lifecycle evidence in supplied view")
        if node in done:
            return
        visiting.add(node)
        for target in graph.get(node, ()):
            visit(target)
        visiting.remove(node)
        done.add(node)
    for node in graph:
        visit(node)


def _load_view(view, memory, max_bytes, prospective=None, charge=None):
    if type(view) is not LifecycleView:
        raise MemoryContractError("Canonical lifecycle view required")
    view.__post_init__()
    _memory_interface(memory)
    if type(max_bytes) is not int or not 1 <= max_bytes <= 1024 * 1024:
        raise MemoryContractError("Invalid view byte limit")
    project = view.subject.reference.project_id
    records, candidates, events, pins = {}, {}, {}, {}
    used = 0
    for pin in view.pins:
        identity = pin.reference.identity
        stored = (prospective if prospective is not None and prospective.record_id == pin.reference.record_id
                  else memory.get(project, pin.reference.record_id))
        candidate = decode_candidate(project, stored, record_id=pin.reference.record_id)
        if digest(_canonical(asdict(stored))) != pin.record_digest:
            raise MemoryContractError("Required dependency fingerprint changed")
        if charge is not None:
            charge(len(_canonical(asdict(stored)).encode("utf-8")))
        used += len(stored.claim.encode("utf-8"))
        if used > max_bytes:
            raise MemoryContractError("Dependency evidence exceeds shared byte limit")
        records[identity], candidates[identity], pins[identity] = stored, candidate, pin
        events[identity] = decode_evidence(candidate)
    relationships, history = {}, {}
    for identity, event in events.items():
        if event is None:
            continue
        for pin in _event_pins(event):
            if pins.get(pin.reference.identity) != pin:
                raise MemoryContractError("Dangling or mismatched event pin in supplied view")
        if type(event) is ValidityEvidence:
            if events[event.subject.reference.identity] is not None:
                raise MemoryContractError("Validity subject must be an original candidate")
            if event.previous is not None:
                previous_id = event.previous.reference.identity
                previous = events[previous_id]
                if type(previous) is not ValidityEvidence or previous.subject != event.subject:
                    raise MemoryContractError("Assessment history subject mismatch or invalid kind")
                history.setdefault(identity, set()).add(previous_id)
        else:
            old, new = event.predecessor.reference.identity, event.successor.reference.identity
            if events[old] is not None or events[new] is not None:
                raise MemoryContractError("Supersession endpoints must be original candidates")
            relationships.setdefault(old, set()).add(new)
    _acyclic(history)
    _acyclic(relationships)
    return records, candidates, events, relationships, history


def store_evidence(project_id: str, event: ValidityEvidence | SupersessionEvidence,
                   memory: MemoryInterface, *, dependencies: tuple[PinnedMemory, ...] = ()) -> MemoryRecord:
    """Append one event after checking its explicit closure; no global claims.

    Existing collision/read-back semantics and broken-provider limitations are
    those of store_candidate. Additional history/relationships must be supplied.
    """
    candidate = prepare_evidence(event)
    validate_memory_record(project_id, candidate.to_memory_record())
    if type(dependencies) is not tuple or len(dependencies) > 31:
        raise MemoryContractError("Invalid event dependency closure")
    unique = {}
    for pin in _event_pins(event) + dependencies:
        _pin(pin, project_id)
        identity = pin.reference.identity
        if identity in unique and unique[identity] != pin:
            raise MemoryContractError("Conflicting dependency fingerprints")
        unique[identity] = pin
    stored = candidate.to_memory_record()
    view = LifecycleView(subject=PinnedMemory.from_record(stored),
                         dependencies=tuple(unique[key] for key in sorted(unique)))
    _load_view(view, memory, 128 * 1024, prospective=stored)
    return store_candidate(project_id, candidate, memory)


@dataclass(frozen=True, slots=True, kw_only=True)
class DerivedAssessment:
    subject: PinnedMemory
    usability: Usability
    observations: tuple[SourceObservation, ...]
    relationship_state: str
    dependency_fingerprints: tuple[PinnedMemory, ...]
    declared_coverage: str
    scope: str = "within this supplied view only"
    truth: str = "unknown"
    limitations: tuple[str, ...] = (
        "No global completeness or latest-state claim.",
        "Historical outcomes and replacement intent remain caller-declared.",
        "Matching bytes do not authenticate versions, publishers or factual entailment.",
        "No suppression, redirect, predecessor reactivation or execution authority.",
    )

    def __post_init__(self):
        if type(self) is not DerivedAssessment or type(self.subject) is not PinnedMemory:
            raise MemoryContractError("Noncanonical derived assessment")
        self.subject.__post_init__()
        if type(self.usability) is not Usability:
            raise MemoryContractError("Invalid derived usability")
        project = self.subject.reference.project_id
        if type(self.observations) is not tuple or not 1 <= len(self.observations) <= 32:
            raise MemoryContractError("Invalid derived source observations")
        for observation in self.observations:
            if type(observation) is not SourceObservation:
                raise MemoryContractError("Noncanonical derived observation")
            observation.__post_init__()
            if observation.source.project_id != project:
                raise MemoryContractError("Foreign derived observation")
        states = {observation.state for observation in self.observations}
        if ((self.usability is Usability.VALID_FOR_REUSE and states != {SourceObservationState.MATCH})
                or (self.usability is Usability.INVALIDATED and not states & {
                    SourceObservationState.MISSING, SourceObservationState.MISMATCH})):
            raise MemoryContractError("Derived usability lacks matching observations")
        if (type(self.relationship_state) is not str or self.relationship_state not in {
                "none-declared-in-view", "declared-unverified", "conflicted"}
                or type(self.scope) is not str or self.scope != "within this supplied view only"
                or type(self.truth) is not str or self.truth != "unknown"):
            raise MemoryContractError("Derived assessment cannot claim global truth/state")
        LifecycleView(subject=self.subject,
            dependencies=tuple(pin for pin in self.dependency_fingerprints if pin != self.subject),
            coverage=self.declared_coverage)
        if (type(self.dependency_fingerprints) is not tuple
                or self.subject not in self.dependency_fingerprints
                or len({pin.reference.identity for pin in self.dependency_fingerprints}) != len(self.dependency_fingerprints)):
            raise MemoryContractError("Invalid derived dependency fingerprints")
        if type(self.limitations) is not tuple or self.limitations != type(self).__dataclass_fields__["limitations"].default:
            raise MemoryContractError("Derived limitations must be retained")


def _charge_memory_read(size, checker=None, charge=None):
    """Account complete records independently of optional request accounting."""
    if charge is not None:
        charge(size)
    if checker is not None:
        checker.reader.bytes_read += size
        if checker.reader.bytes_read > checker.reader.limits.scan_bytes:
            raise MemoryContractError("Shared dependency/source read budget exceeded")


def assess_view(view: LifecycleView, memory: MemoryInterface, *, max_bytes: int,
                checker: LocalSourceChecker | None = None, _charge_memory=None) -> str:
    """Read-only canonical material; all explicit dependencies remain visible."""
    if type(view) is not LifecycleView:
        raise MemoryContractError("Canonical lifecycle view required")
    view.__post_init__()
    if checker is not None:
        if type(checker) is not LocalSourceChecker:
            raise MemoryContractError("Canonical local source checker required")
        checker.assert_project(view.subject.reference.project_id)
    def charge(size):
        _charge_memory_read(size, checker, _charge_memory)
    records, candidates, events, relationships, history = _load_view(view, memory, max_bytes, charge=charge)
    subject_id = view.subject.reference.identity
    if events[subject_id] is not None:
        raise MemoryContractError("Selected view subject must be an original candidate")
    original = candidates[subject_id].original
    observations = tuple(checker.observe(source) if checker is not None else
        SourceObservation(source=source, state=SourceObservationState.UNKNOWN,
                          basis="no installed source checker for this request")
        for source in original.sources)
    states = {item.state for item in observations}
    usability = (Usability.INVALIDATED if states & {SourceObservationState.MISMATCH, SourceObservationState.MISSING}
                 else Usability.VALID_FOR_REUSE if states == {SourceObservationState.MATCH}
                 else Usability.UNKNOWN)
    incoming = {}
    for old, successors in relationships.items():
        for new in successors:
            incoming.setdefault(new, set()).add(old)
    conflicting_nodes = {old for old, successors in relationships.items() if len(successors) > 1}
    conflicting_nodes.update(new for new, predecessors in incoming.items() if len(predecessors) > 1)
    # Expose conflict across the supplied chain, without choosing a timestamp winner.
    connected = {subject_id}
    while True:
        expanded = connected | {new for old in connected for new in relationships.get(old, ())}
        expanded |= {old for new in connected for old in incoming.get(new, ())}
        if expanded == connected:
            break
        connected = expanded
    relationship_state = ("conflicted" if connected & conflicting_nodes else
                          "declared-unverified" if any(node in relationships or node in incoming for node in connected)
                          else "none-declared-in-view")
    referenced_history = {target for targets in history.values() for target in targets}
    tip_outcomes = {event.outcome for identity, event in events.items()
                    if type(event) is ValidityEvidence and event.subject == view.subject
                    and identity not in referenced_history}
    if relationship_state == "conflicted" or len(tip_outcomes) > 1:
        usability = Usability.CONFLICTED
    assessment = DerivedAssessment(subject=view.subject, usability=usability,
        observations=observations, relationship_state=relationship_state,
        dependency_fingerprints=tuple(sorted(view.pins, key=lambda pin: pin.reference.identity)),
        declared_coverage=view.coverage)
    content = _canonical({"kind": "memory-lifecycle-view", "version": 1,
        "original_candidate": asdict(records[subject_id]),
        "history_and_counterevidence": [asdict(records[key]) for key in sorted(records) if key != subject_id],
        "assessment": asdict(assessment), "trust": "untrusted", "authority": "none"})
    if len(content.encode("utf-8")) > max_bytes:
        raise MemoryContractError("Assessed material exceeds selected byte limit")
    return content
