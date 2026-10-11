"""Bounded MEM-02 candidate lifecycle, using only injected MemoryInterface.

The stored MemoryRecord is a reported transformation envelope, not a verified
replacement for the original claim. Its canonical JSON retains the exact
original record, including verification, source versions and actor/time data.
Raw sources and operational State are never read or modified. This module
implements no storage provider, durability, entailment check or promotion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import Enum
import json

from runtime.context.contracts import digest
from runtime.memory.contracts import (
    ActorTimeProvenance, ClaimStatus, ConfidenceEvidence, EvidenceOrigin,
    EvidenceState, MemoryContractError, MemoryInterface, MemoryRecord,
    SourceEvidence, VerificationEvidence, validate_memory_key,
    validate_memory_record,
)


def _text(value, label, limit=4096):
    if type(value) is not str:
        raise MemoryContractError(f"Invalid {label}")
    try:
        valid = bool(value.strip()) and len(value.encode("utf-8")) <= limit
    except UnicodeError as error:
        raise MemoryContractError(f"Invalid {label} encoding") from error
    if not valid:
        raise MemoryContractError(f"Empty or oversized {label}")


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


def _memory_interface(memory):
    if not all(callable(getattr(memory, name, None)) for name in ("get", "put_candidate")):
        raise MemoryContractError("Injected MemoryInterface required")


def normalize_claim(claim: str) -> str:
    """Normalize CR/CRLF and trailing spaces/tabs only; retain interior text."""
    _text(claim, "claim", 128 * 1024)
    return "\n".join(line.rstrip(" \t") for line in
                     claim.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryReference:
    project_id: str
    record_id: str

    def __post_init__(self):
        if type(self) is not MemoryReference:
            raise MemoryContractError("Noncanonical memory reference")
        validate_memory_key(self.project_id, self.record_id)

    @property
    def identity(self):
        self.__post_init__()
        return f"memory:{self.project_id}:{self.record_id}"


class Disposition(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionEvidence:
    """Caller-reported rationale; accepted does not mean approved or promoted."""
    disposition: Disposition
    rationale: str

    def __post_init__(self):
        if type(self) is not DecisionEvidence or type(self.disposition) is not Disposition:
            raise MemoryContractError("Invalid decision evidence")
        _text(self.rationale, "decision rationale")


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryLink:
    """Explicit project-scoped inert anchor, never opened or executed."""
    project_id: str
    kind: str
    target: str
    version: str | None = None

    def __post_init__(self):
        if type(self) is not MemoryLink:
            raise MemoryContractError("Noncanonical memory link")
        validate_memory_key(self.project_id, "link")
        if type(self.kind) is not str or self.kind not in {
            "file", "symbol", "task", "workflow", "decision", "run", "test",
            "evidence", "agent", "capability", "memory",
        }:
            raise MemoryContractError("Invalid memory link kind")
        _text(self.target, "link target", 2048)
        if self.version is not None:
            _text(self.version, "link version", 512)
        if self.kind == "memory":
            # Memory links use scoped identities, not ambiguous bare IDs.
            prefix = f"memory:{self.project_id}:"
            if not self.target.startswith(prefix):
                raise MemoryContractError("Memory link project mismatch")
            validate_memory_key(self.project_id, self.target[len(prefix):])


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizationEvidence:
    algorithm: str
    input_digest: str
    output_digest: str

    def __post_init__(self):
        if type(self) is not NormalizationEvidence or type(self.algorithm) is not str:
            raise MemoryContractError("Noncanonical normalization evidence")
        if self.algorithm != "newline-trailing-space-v1":
            raise MemoryContractError("Unknown normalization algorithm")
        for value in (self.input_digest, self.output_digest):
            if (type(value) is not str or len(value) != 64
                    or any(c not in "0123456789abcdef" for c in value)):
                raise MemoryContractError("Invalid normalization digest")


@dataclass(frozen=True, slots=True, kw_only=True)
class LifecycleCandidate:
    original: MemoryRecord
    reference: MemoryReference
    normalized_claim: str
    transformation: NormalizationEvidence
    decision: DecisionEvidence | None = None
    links: tuple[MemoryLink, ...] = ()

    def __post_init__(self):
        if type(self) is not LifecycleCandidate or type(self.reference) is not MemoryReference:
            raise MemoryContractError("Noncanonical lifecycle candidate")
        self.reference.__post_init__()
        validate_memory_record(self.reference.project_id, self.original)
        expected = NormalizationEvidence(
            algorithm="newline-trailing-space-v1", input_digest=digest(self.original.claim),
            output_digest=digest(normalize_claim(self.original.claim)))
        if (type(self.normalized_claim) is not str
                or self.normalized_claim != normalize_claim(self.original.claim)
                or type(self.transformation) is not NormalizationEvidence
                or self.transformation != expected):
            raise MemoryContractError("Normalization provenance mismatch")
        self.transformation.__post_init__()
        if self.decision is not None:
            if type(self.decision) is not DecisionEvidence:
                raise MemoryContractError("Noncanonical decision evidence")
            self.decision.__post_init__()
        if type(self.links) is not tuple or len(self.links) > 32:
            raise MemoryContractError("Invalid lifecycle links")
        for link in self.links:
            if type(link) is not MemoryLink:
                raise MemoryContractError("Noncanonical memory link")
            link.__post_init__()
            if link.project_id != self.reference.project_id:
                raise MemoryContractError("Link project mismatch")
        if len(set(self.links)) != len(self.links):
            raise MemoryContractError("Duplicate lifecycle link")

    def to_memory_record(self) -> MemoryRecord:
        self.__post_init__()
        body = _canonical({"kind": "memory-lifecycle-candidate", "version": 1,
                           "candidate": asdict(self)})
        return MemoryRecord(project_id=self.reference.project_id,
                            record_id=self.reference.record_id, claim=body,
                            status=ClaimStatus.REPORTED, sources=self.original.sources)


def prepare_candidate(project_id: str, original: MemoryRecord, *, record_id: str,
                      decision: DecisionEvidence | None = None,
                      links: tuple[MemoryLink, ...] = ()) -> LifecycleCandidate:
    """Capture explicit inputs only, with a caller-chosen envelope identity.

    Duplicate identical links collapse deterministically. No claims, source
    histories or decisions are merged by semantic similarity.
    """
    reference = MemoryReference(project_id=project_id, record_id=record_id)
    validate_memory_record(project_id, original)
    if type(links) is not tuple or len(links) > 32:
        raise MemoryContractError("Invalid lifecycle links")
    for link in links:
        if type(link) is not MemoryLink:
            raise MemoryContractError("Noncanonical memory link")
        link.__post_init__()
    normalized = normalize_claim(original.claim)
    candidate = LifecycleCandidate(
        original=original, reference=reference, normalized_claim=normalized,
        transformation=NormalizationEvidence(algorithm="newline-trailing-space-v1",
            input_digest=digest(original.claim), output_digest=digest(normalized)),
        decision=decision,
        links=tuple(sorted(set(links), key=lambda link: _canonical(asdict(link)))))
    candidate.to_memory_record()  # Enforce MEM-01's serialized-claim byte bound.
    return candidate


def deduplicate_candidates(project_id: str, candidates: tuple[LifecycleCandidate, ...]
                           ) -> tuple[LifecycleCandidate, ...]:
    validate_memory_key(project_id, "deduplicate")
    if type(candidates) is not tuple or len(candidates) > 32:
        raise MemoryContractError("Invalid candidate collection")
    unique = {}
    for candidate in candidates:
        if type(candidate) is not LifecycleCandidate:
            raise MemoryContractError("Noncanonical lifecycle candidate")
        stored = candidate.to_memory_record()
        validate_memory_record(project_id, stored)
        key = candidate.reference.identity
        if key in unique and unique[key] != candidate:
            raise MemoryContractError("Candidate collision would replace evidence")
        unique[key] = candidate
    return tuple(unique[key] for key in sorted(unique))


def _object(cls, value):
    if type(value) is not dict or set(value) != {field.name for field in fields(cls)}:
        raise MemoryContractError(f"Malformed {cls.__name__} fields")
    return dict(value)


def _actor(value):
    return None if value is None else ActorTimeProvenance(**_object(ActorTimeProvenance, value))


def _source(value):
    values = _object(SourceEvidence, value)
    values.update(origin=EvidenceOrigin(values["origin"]), state=EvidenceState(values["state"]),
                  capture=_actor(values["capture"]), review=_actor(values["review"]))
    return SourceEvidence(**values)


def _sources(value):
    if type(value) is not list or not 1 <= len(value) <= 32:
        raise MemoryContractError("Malformed stored sources")
    return tuple(_source(source) for source in value)


def _record(value):
    values = _object(MemoryRecord, value)
    proof = values["verification"]
    if proof is not None:
        proof = _object(VerificationEvidence, proof)
        proof.update(evidence=_sources(proof["evidence"]), capture=_actor(proof["capture"]),
                     review=_actor(proof["review"]))
        proof = VerificationEvidence(**proof)
    confidence = values["confidence"]
    values.update(status=ClaimStatus(values["status"]), sources=_sources(values["sources"]),
        verification=proof, capture=_actor(values["capture"]), review=_actor(values["review"]),
        confidence=None if confidence is None else ConfidenceEvidence(
            **_object(ConfidenceEvidence, confidence)))
    return MemoryRecord(**values)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MemoryContractError("Duplicate stored JSON field")
        result[key] = value
    return result


def decode_candidate(project_id: str, stored: MemoryRecord, *, record_id: str
                     ) -> LifecycleCandidate:
    """Revalidate complete stored evidence, including all nested original data."""
    validate_memory_record(project_id, stored, record_id=record_id)
    try:
        value = json.loads(stored.claim, object_pairs_hook=_unique_object)
        if (type(value) is not dict or set(value) != {"kind", "version", "candidate"}
                or value["kind"] != "memory-lifecycle-candidate"
                or type(value["version"]) is not int or value["version"] != 1):
            raise MemoryContractError("Unknown lifecycle envelope")
        values = _object(LifecycleCandidate, value["candidate"])
        decision = values["decision"]
        if decision is not None:
            decision = _object(DecisionEvidence, decision)
            decision["disposition"] = Disposition(decision["disposition"])
            decision = DecisionEvidence(**decision)
        if type(values["links"]) is not list or len(values["links"]) > 32:
            raise MemoryContractError("Malformed stored links")
        candidate = LifecycleCandidate(
            original=_record(values["original"]),
            reference=MemoryReference(**_object(MemoryReference, values["reference"])),
            normalized_claim=values["normalized_claim"],
            transformation=NormalizationEvidence(
                **_object(NormalizationEvidence, values["transformation"])),
            decision=decision,
            links=tuple(MemoryLink(**_object(MemoryLink, link)) for link in values["links"]))
        if candidate.to_memory_record() != stored:
            raise MemoryContractError("Stored lifecycle envelope binding mismatch")
        return candidate
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError) as error:
        raise MemoryContractError("Malformed stored lifecycle evidence") from error


def store_candidate(project_id: str, candidate: LifecycleCandidate,
                    memory: MemoryInterface) -> MemoryRecord:
    """Store through the supplied port; no persistence or transaction guarantee.

    Precheck collisions and revalidate both return and read-back. A broken
    provider can still mutate before failing; this function cannot roll it back.
    """
    if type(candidate) is not LifecycleCandidate:
        raise MemoryContractError("Noncanonical lifecycle candidate")
    _memory_interface(memory)
    stored = candidate.to_memory_record()
    validate_memory_record(project_id, stored)
    previous = memory.get(project_id, stored.record_id)
    if previous is not None:
        validate_memory_record(project_id, previous, record_id=stored.record_id)
        if previous != stored:
            raise MemoryContractError("Candidate collision would replace evidence")
        decode_candidate(project_id, previous, record_id=stored.record_id)
        return previous
    returned = memory.put_candidate(project_id, stored)
    validate_memory_record(project_id, returned, record_id=stored.record_id)
    if returned != stored:
        raise MemoryContractError("Memory implementation changed candidate evidence")
    read_back = memory.get(project_id, stored.record_id)
    validate_memory_record(project_id, read_back, record_id=stored.record_id)
    if read_back != stored:
        raise MemoryContractError("Memory implementation failed candidate read-back")
    decode_candidate(project_id, read_back, record_id=stored.record_id)
    return read_back
