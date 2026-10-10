"""Immutable MEM-01 Python contracts, without storage or a wire schema.

Knowledge describes durable facts; Memory records observations and learning;
State owns current tasks, runs and approvals. These records are candidate
evidence only. They do not update State, promote knowledge or planning rules,
or confer execution, review, write or approval authority.

Evidence metadata is supplied by the caller. Validation checks its shape and
exact bindings; it does not read sources, authenticate publishers, establish
freshness, or prove that evidence entails a claim. Installed implementations
must validate both operation inputs and returned records at their boundaries.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol


class MemoryContractError(ValueError):
    """Malformed, mismatched or authority-promoting Memory evidence."""


class ClaimStatus(str, Enum):
    """Evidence classifications, never ExecutionResult or job status values."""

    UNKNOWN = "unknown"
    REPORTED = "reported"
    INFERRED = "inferred"
    DISPUTED = "disputed"
    EVIDENCE_VERIFIED = "evidence-verified"


class EvidenceOrigin(str, Enum):
    """Where evidence originated; origin does not establish trust."""

    REPOSITORY = "repository"
    PASTED = "pasted"
    WEB = "web"
    EMAIL = "email"
    UPLOAD = "upload"
    RETRIEVED = "retrieved"
    SCRAPED = "scraped"
    CONNECTOR = "connector"
    TOOL = "tool"
    USER = "user"


class EvidenceState(str, Enum):
    """Caller-declared availability/freshness, not a source probe result."""

    UNKNOWN = "unknown"
    CURRENT = "current"
    MISSING = "missing"
    STALE = "stale"


def _exact(value, expected, label):
    if type(value) is not expected:
        raise MemoryContractError(f"Noncanonical {label} type")


def _text(value, label, limit=4096):
    _exact(value, str, label)
    try:
        valid = bool(value.strip()) and len(value.encode("utf-8")) <= limit
    except UnicodeError as error:
        raise MemoryContractError(f"Invalid {label} encoding") from error
    if not valid:
        raise MemoryContractError(f"Empty or oversized {label}")


def _identifier(value, label):
    _text(value, label, 128)
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value)
            or value.endswith(".") or ".." in value):
        raise MemoryContractError(f"Invalid {label}")


def _digest(value, label):
    _exact(value, str, label)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise MemoryContractError(f"Invalid {label}")


def validate_memory_key(project_id: str, record_id: str) -> tuple[str, str]:
    """Explicit opaque IDs: case-sensitive, never filesystem paths or defaults."""
    _identifier(project_id, "project_id")
    _identifier(record_id, "record_id")
    return project_id, record_id


@dataclass(frozen=True, slots=True, kw_only=True)
class ActorTimeProvenance:
    """Caller-supplied actor/time within the enclosing evidence's project.

    Each unknown value stays None, including partially known metadata. Actor is
    an inert identity reference; timestamp is a timezone-aware ISO 8601 string
    preserved verbatim. Neither authenticates an actor, proves review happened,
    establishes verification/freshness, or grants trust or execution authority.
    """

    actor: str | None = None
    timestamp: str | None = None

    def __post_init__(self):
        _exact(self, ActorTimeProvenance, "actor/time provenance")
        if self.actor is not None:
            _text(self.actor, "provenance actor", 512)
        if self.timestamp is not None:
            _text(self.timestamp, "provenance timestamp", 100)
            try:
                parsed = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            except ValueError as error:
                raise MemoryContractError("Provenance timestamp must be an ISO 8601 date-time") from error
            if parsed.tzinfo is None:
                raise MemoryContractError("Provenance timestamp must include a timezone")


def _provenance(capture, review):
    for value in (capture, review):
        if value is not None:
            _exact(value, ActorTimeProvenance, "actor/time provenance")
            try:
                ActorTimeProvenance.__post_init__(value)
            except AttributeError as error:
                raise MemoryContractError("Incomplete actor/time provenance") from error


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceEvidence:
    """An identified source version/location within one explicit project.

    The digest identifies original source bytes, not the Memory claim. Location
    is an inert reference (possibly a URL or source span); it is never opened.
    Missing/stale sources retain their known provenance instead of fabricating
    replacement content. UNKNOWN is the default availability/freshness state.
    Optional capture/review metadata describes this source evidence only.
    """

    project_id: str
    source_id: str
    source_version: str
    source_digest: str
    location: str
    origin: EvidenceOrigin
    state: EvidenceState = EvidenceState.UNKNOWN
    capture: ActorTimeProvenance | None = None
    review: ActorTimeProvenance | None = None

    def __post_init__(self):
        _exact(self, SourceEvidence, "source evidence")
        _identifier(self.project_id, "source project_id")
        _text(self.source_id, "source_id", 512)
        _text(self.source_version, "source_version", 512)
        _digest(self.source_digest, "source_digest")
        _text(self.location, "source location", 2048)
        _exact(self.origin, EvidenceOrigin, "evidence origin")
        _exact(self.state, EvidenceState, "evidence state")
        _provenance(self.capture, self.review)


def _sources(value, project_id):
    _exact(value, tuple, "evidence collection")
    if not 1 <= len(value) <= 32:
        raise MemoryContractError("Evidence count must be between 1 and 32")
    identities = set()
    for source in value:
        _exact(source, SourceEvidence, "source evidence")
        SourceEvidence.__post_init__(source)
        if source.project_id != project_id:
            raise MemoryContractError("Evidence project scope mismatch")
        identity = (source.source_id, source.source_version, source.location)
        if identity in identities:
            raise MemoryContractError("Duplicate or conflicting source identity")
        identities.add(identity)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfidenceEvidence:
    """An optional bounded estimate with a basis; never verification/authority."""

    value: float
    basis: str

    def __post_init__(self):
        _exact(self, ConfidenceEvidence, "confidence evidence")
        if (type(self.value) not in (int, float) or not 0 <= self.value <= 1
                or not math.isfinite(self.value)):
            raise MemoryContractError("Confidence must be finite and between 0 and 1")
        _text(self.basis, "confidence basis")


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationEvidence:
    """Supporting evidence pinned to a project, record and exact claim digest.

    This represents supplied verification evidence, not a verification engine.
    Every cited source must be explicitly CURRENT. A hash identifies bytes; it
    does not authenticate a source or create an approval receipt.
    Optional capture/review metadata does not replace these evidence bindings.
    """

    project_id: str
    record_id: str
    claim_digest: str
    evidence: tuple[SourceEvidence, ...]
    basis: str
    capture: ActorTimeProvenance | None = None
    review: ActorTimeProvenance | None = None

    def __post_init__(self):
        _exact(self, VerificationEvidence, "verification evidence")
        validate_memory_key(self.project_id, self.record_id)
        _digest(self.claim_digest, "verified claim digest")
        _text(self.basis, "verification basis")
        _provenance(self.capture, self.review)
        _sources(self.evidence, self.project_id)
        if any(source.state is not EvidenceState.CURRENT for source in self.evidence):
            raise MemoryContractError("Verification requires current identified evidence")


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryRecord:
    """Version 1 candidate evidence, including reported/inferred/disputed claims.

    Confidence and origin cannot select claim status. EVIDENCE_VERIFIED requires
    a verification object bound to this exact claim and sources. Other statuses
    carry source evidence without claiming successful verification. Constructing
    or storing a record never promotes it to trusted policy or durable learning.
    Optional capture/review metadata is independent of confidence and status.
    """

    project_id: str
    record_id: str
    claim: str
    status: ClaimStatus
    sources: tuple[SourceEvidence, ...]
    confidence: ConfidenceEvidence | None = None
    verification: VerificationEvidence | None = None
    version: int = 1
    trust: str = "untrusted"
    authority: str = "none"
    capture: ActorTimeProvenance | None = None
    review: ActorTimeProvenance | None = None

    def __post_init__(self):
        _exact(self, MemoryRecord, "memory record")
        if type(self.version) is not int or self.version != 1:
            raise MemoryContractError("Unsupported MemoryRecord version")
        validate_memory_key(self.project_id, self.record_id)
        _text(self.claim, "claim", 128 * 1024)
        _exact(self.status, ClaimStatus, "claim status")
        _exact(self.trust, str, "trust")
        _exact(self.authority, str, "authority")
        if self.trust != "untrusted" or self.authority != "none":
            raise MemoryContractError("Memory evidence cannot promote trust or authority")
        _provenance(self.capture, self.review)
        _sources(self.sources, self.project_id)
        if self.confidence is not None:
            _exact(self.confidence, ConfidenceEvidence, "confidence evidence")
            ConfidenceEvidence.__post_init__(self.confidence)
        if self.status is ClaimStatus.EVIDENCE_VERIFIED:
            _exact(self.verification, VerificationEvidence, "verification evidence")
            VerificationEvidence.__post_init__(self.verification)
            if (self.verification.project_id != self.project_id
                    or self.verification.record_id != self.record_id):
                raise MemoryContractError("Verification record scope mismatch")
            if self.verification.claim_digest != hashlib.sha256(self.claim.encode("utf-8")).hexdigest():
                raise MemoryContractError("Verification claim digest mismatch")
            if any(source not in self.sources for source in self.verification.evidence):
                raise MemoryContractError("Verification source provenance mismatch")
        elif self.verification is not None:
            raise MemoryContractError("Unverified claim cannot assert successful verification")


def validate_memory_record(project_id: str, record: MemoryRecord, *,
                           record_id: str | None = None) -> MemoryRecord:
    """Revalidate nested evidence on put/get, including illicit object mutation.

    get callers must supply the requested record_id as well as project_id. This
    function makes no storage change, source read or authority decision.
    """
    _identifier(project_id, "project_id")
    if record_id is not None:
        validate_memory_key(project_id, record_id)
    _exact(record, MemoryRecord, "memory record")
    try:
        MemoryRecord.__post_init__(record)
    except AttributeError as error:
        raise MemoryContractError("Incomplete Memory evidence") from error
    if record.project_id != project_id:
        raise MemoryContractError("Memory operation project scope mismatch")
    if record_id is not None and record.record_id != record_id:
        raise MemoryContractError("Memory operation record identity mismatch")
    return record


class MemoryInterface(Protocol):
    """Provider-neutral contract only: no default provider or storage.

    Implementations validate explicit keys even for misses. Returned records
    must be revalidated against both requested IDs. put_candidate accepts only
    validated immutable evidence in the supplied project and returns that
    candidate, not approval/promotion. A repeated identical candidate is
    idempotent; a changed candidate at the same key must fail instead of silently
    replacing provenance. Lifecycle updates/supersession belong to later MEM work.
    Both operations preserve all supplied capture/review metadata exactly,
    including absent values; they must not infer actors or generate timestamps.

    Implementations are trusted local code: a Protocol cannot sandbox an arbitrary
    implementation or itself prove that callers obey these boundary requirements.
    """

    def get(self, project_id: str, record_id: str) -> MemoryRecord | None: ...

    def put_candidate(self, project_id: str, record: MemoryRecord) -> MemoryRecord: ...
