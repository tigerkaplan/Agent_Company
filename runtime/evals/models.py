"""Canonical provider-neutral evaluation contracts and deterministic identity."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from runtime.core.sanitization import contains_secret, is_sensitive_key


class EvalContractError(ValueError):
    """Raised when an evaluation contract is malformed or inconsistent."""


FRAMEWORK_VERSION = "1"
CANONICAL_EVALUATOR_ID = "canonical-deterministic"
MAX_AGGREGATE_EVIDENCE = 100
_RESULT_IDENTITY_MAX_BYTES = 64 * 1024 * 1024
EVAL_STATUSES = frozenset({"pass", "fail", "error"})
CHECK_STATUSES = EVAL_STATUSES
CHECK_SEVERITIES = frozenset({"critical", "major", "minor"})
EVALUATOR_TYPES = frozenset(
    {
        "EXECUTION_RESULT_CONTRACT",
        "EXPECTED_STATUS",
        "REQUIRED_EVIDENCE",
        "REQUIRED_ARTIFACTS",
        "FORBIDDEN_CONDITIONS",
        "FIELD_MATCH",
    }
)
REFERENCE_TYPES = frozenset(
    {
        "file",
        "project_state",
        "connector_contract",
        "message",
        "artifact",
        "log",
        "review",
        "approval",
        "provider_result",
        "knowledge_source",
        "other",
    }
)
FIELD_MATCH_PATHS = frozenset(
    {
        "execution_id",
        "job_id",
        "status",
        "provider",
        "requested_provider",
        "preferred_provider",
        "fallback_used",
        "fallback_reason",
        "execution_mode",
        "dry_run",
        "retryable",
        "summary",
        "usage.duration_ms",
        "usage.input_units",
        "usage.output_units",
        "usage.total_units",
        "usage.unit",
    }
)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_METADATA_KEY = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_EVAL_ID = re.compile(r"eval-[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_INTEGER_MIN = -(2**63)
_INTEGER_MAX = 2**63 - 1


class FrozenMapping(Mapping[str, Any]):
    """Recursively immutable JSON mapping for canonical eval values."""

    __slots__ = ("__values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        frozen = {
            str(key): _freeze(item)
            for key, item in sorted(values.items(), key=lambda pair: str(pair[0]))
        }
        object.__setattr__(self, "_FrozenMapping__values", MappingProxyType(frozen))

    def __getitem__(self, key: str) -> Any:
        return self.__values[key]

    def __iter__(self):
        return iter(self.__values)

    def __len__(self) -> int:
        return len(self.__values)

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("canonical evaluation mappings are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("canonical evaluation mappings are immutable")


def _freeze(value: Any) -> Any:
    if isinstance(value, FrozenMapping):
        return value
    if isinstance(value, Mapping):
        return FrozenMapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical_digest(
    value: Any,
    name: str,
    *,
    max_bytes: int = 2 * 1024 * 1024,
) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, TypeError, ValueError) as error:
        raise EvalContractError(f"{name} is not canonical JSON") from error
    if len(payload) > max_bytes:
        raise EvalContractError(f"{name} exceeds the bounded identity limit")
    return hashlib.sha256(payload).hexdigest()


def _bounded_string(value: Any, name: str, limit: int) -> None:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise EvalContractError(
            f"{name} must be a non-empty string no longer than {limit} characters"
        )
    if contains_secret(value):
        raise EvalContractError(f"{name} contains credential-like content")


def _identifier(value: Any, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise EvalContractError(f"{name} is not a bounded canonical identifier")


def _datetime(value: Any, name: str) -> None:
    _bounded_string(value, name, 100)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvalContractError(f"{name} must be an ISO 8601 date-time") from error
    if parsed.tzinfo is None:
        raise EvalContractError(f"{name} must include a timezone")


def _bounded_json(value: Any, name: str, *, depth: int = 0) -> None:
    if depth > 4:
        raise EvalContractError(f"{name} exceeds the maximum nesting depth")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if len(value) > 2000:
            raise EvalContractError(f"{name} contains an overlong string")
        if contains_secret(value):
            raise EvalContractError(f"{name} contains credential-like content")
        return
    if isinstance(value, int) and not isinstance(value, bool):
        if not _INTEGER_MIN <= value <= _INTEGER_MAX:
            raise EvalContractError(f"{name} contains an out-of-range integer")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or not _INTEGER_MIN <= value <= _INTEGER_MAX:
            raise EvalContractError(f"{name} contains an invalid number")
        return
    if isinstance(value, Mapping):
        if len(value) > 50:
            raise EvalContractError(f"{name} contains too many properties")
        for key, item in value.items():
            if not isinstance(key, str) or _CODE.fullmatch(key) is None:
                raise EvalContractError(f"{name} contains an invalid property name")
            if is_sensitive_key(key):
                raise EvalContractError(f"{name} contains a prohibited sensitive field")
            _bounded_json(item, f"{name}.{key}", depth=depth + 1)
        return
    if isinstance(value, (list, tuple)):
        if len(value) > 50:
            raise EvalContractError(f"{name} contains too many items")
        for index, item in enumerate(value):
            _bounded_json(item, f"{name}[{index}]", depth=depth + 1)
        return
    raise EvalContractError(f"{name} must contain only bounded JSON values")


def _scalar(value: Any, name: str) -> None:
    if isinstance(value, (Mapping, list, tuple)):
        raise EvalContractError(f"{name} must be a bounded JSON scalar")
    _bounded_json(value, name)


def _reference(value: Any, name: str) -> None:
    if not isinstance(value, Mapping):
        raise EvalContractError(f"{name} must be an object")
    if set(value) - {"ref_type", "ref", "description"}:
        raise EvalContractError(f"{name} contains unexpected fields")
    if value.get("ref_type") not in REFERENCE_TYPES:
        raise EvalContractError(f"{name}.ref_type is not canonical")
    _bounded_string(value.get("ref"), f"{name}.ref", 2000)
    if "description" in value:
        _bounded_string(value.get("description"), f"{name}.description", 2000)


def _metadata(value: Any, name: str) -> FrozenMapping:
    if not isinstance(value, Mapping) or len(value) > 32:
        raise EvalContractError(f"{name} must be an object with at most 32 properties")
    for key, item in value.items():
        if not isinstance(key, str) or _METADATA_KEY.fullmatch(key) is None:
            raise EvalContractError(f"{name} contains an invalid property name")
        if is_sensitive_key(key):
            raise EvalContractError(f"{name} contains a prohibited sensitive field")
        _scalar(item, f"{name}.{key}")
    return FrozenMapping(value)


@dataclass(frozen=True)
class EvalCheckSpec:
    check_id: str
    evaluator_type: str
    severity: str
    config: Mapping[str, Any]

    def __post_init__(self) -> None:
        _identifier(self.check_id, "EvalCheckSpec.check_id")
        if not isinstance(self.evaluator_type, str) or _CODE.fullmatch(self.evaluator_type) is None:
            raise EvalContractError("EvalCheckSpec.evaluator_type is invalid")
        if self.severity not in CHECK_SEVERITIES:
            raise EvalContractError("EvalCheckSpec.severity is not canonical")
        if not isinstance(self.config, Mapping):
            raise EvalContractError("EvalCheckSpec.config must be an object")
        _bounded_json(self.config, "EvalCheckSpec.config")
        object.__setattr__(self, "config", FrozenMapping(self.config))

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "evaluator_type": self.evaluator_type,
            "severity": self.severity,
            "config": _thaw(self.config),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "EvalCheckSpec":
        if not isinstance(value, dict):
            raise EvalContractError("Eval check specification must be an object")
        expected = {"check_id", "evaluator_type", "severity", "config"}
        if set(value) != expected:
            raise EvalContractError("Eval check specification fields are incomplete or unexpected")
        return cls(
            check_id=value["check_id"],
            evaluator_type=value["evaluator_type"],
            severity=value["severity"],
            config=value["config"],
        )


@dataclass(frozen=True)
class EvalSpec:
    spec_id: str
    execution_id: str
    job_id: str
    evaluator_id: str
    evaluator_version: str
    checks: tuple[EvalCheckSpec, ...]
    metadata: Mapping[str, Any]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise EvalContractError("EvalSpec.schema_version must be 1")
        for name in ("spec_id", "execution_id", "job_id", "evaluator_id"):
            _identifier(getattr(self, name), f"EvalSpec.{name}")
        _bounded_string(self.evaluator_version, "EvalSpec.evaluator_version", 50)
        if not isinstance(self.checks, tuple) or not 1 <= len(self.checks) <= 100:
            raise EvalContractError("EvalSpec.checks must contain 1-100 checks")
        if any(not isinstance(check, EvalCheckSpec) for check in self.checks):
            raise EvalContractError("EvalSpec.checks must contain EvalCheckSpec values")
        if len({check.check_id for check in self.checks}) != len(self.checks):
            raise EvalContractError("EvalSpec.check IDs must be unique")
        contract_checks = [
            check for check in self.checks
            if check.evaluator_type == "EXECUTION_RESULT_CONTRACT"
        ]
        if len(contract_checks) != 1 or self.checks[0].evaluator_type != "EXECUTION_RESULT_CONTRACT":
            raise EvalContractError(
                "EvalSpec must begin with exactly one EXECUTION_RESULT_CONTRACT check"
            )
        object.__setattr__(self, "metadata", _metadata(self.metadata, "EvalSpec.metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "checks": [check.to_dict() for check in self.checks],
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "EvalSpec":
        if not isinstance(value, dict):
            raise EvalContractError("EvalSpec payload must be an object")
        expected = {
            "schema_version", "spec_id", "execution_id", "job_id",
            "evaluator_id", "evaluator_version", "checks", "metadata",
        }
        if set(value) != expected:
            raise EvalContractError("EvalSpec fields are incomplete or unexpected")
        checks = value.get("checks")
        if not isinstance(checks, list):
            raise EvalContractError("EvalSpec.checks must be an array")
        return cls(
            schema_version=value["schema_version"],
            spec_id=value["spec_id"],
            execution_id=value["execution_id"],
            job_id=value["job_id"],
            evaluator_id=value["evaluator_id"],
            evaluator_version=value["evaluator_version"],
            checks=tuple(EvalCheckSpec.from_dict(check) for check in checks),
            metadata=value["metadata"],
        )


@dataclass(frozen=True)
class EvalCheckResult:
    check_id: str
    evaluator_type: str
    status: str
    severity: str
    expected: Any
    observed: Any
    message: str
    evidence: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.check_id, "EvalCheckResult.check_id")
        if not isinstance(self.evaluator_type, str) or _CODE.fullmatch(self.evaluator_type) is None:
            raise EvalContractError("EvalCheckResult.evaluator_type is invalid")
        if self.status not in CHECK_STATUSES:
            raise EvalContractError("EvalCheckResult.status is not canonical")
        if self.severity not in CHECK_SEVERITIES:
            raise EvalContractError("EvalCheckResult.severity is not canonical")
        _scalar(self.expected, "EvalCheckResult.expected")
        _scalar(self.observed, "EvalCheckResult.observed")
        _bounded_string(self.message, "EvalCheckResult.message", 2000)
        if not isinstance(self.evidence, tuple) or len(self.evidence) > 100:
            raise EvalContractError("EvalCheckResult.evidence must contain at most 100 references")
        frozen = tuple(_freeze(item) for item in self.evidence)
        for index, item in enumerate(frozen):
            _reference(item, f"EvalCheckResult.evidence[{index}]")
        object.__setattr__(self, "evidence", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "evaluator_type": self.evaluator_type,
            "status": self.status,
            "severity": self.severity,
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
            "evidence": _thaw(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "EvalCheckResult":
        if not isinstance(value, dict):
            raise EvalContractError("Eval check result must be an object")
        expected = {
            "check_id", "evaluator_type", "status", "severity",
            "expected", "observed", "message", "evidence",
        }
        if set(value) != expected or not isinstance(value.get("evidence"), list):
            raise EvalContractError("Eval check result fields are incomplete or unexpected")
        return cls(
            check_id=value["check_id"],
            evaluator_type=value["evaluator_type"],
            status=value["status"],
            severity=value["severity"],
            expected=value["expected"],
            observed=value["observed"],
            message=value["message"],
            evidence=tuple(value["evidence"]),
        )


@dataclass(frozen=True)
class EvalIdentity:
    """Compact content-addressed identity material retained with every result."""

    framework_version: str
    spec_digest: str
    execution_digest: str
    result_digest: str

    def __post_init__(self) -> None:
        if self.framework_version != FRAMEWORK_VERSION:
            raise EvalContractError("EvalIdentity.framework_version is unsupported")
        for name in ("spec_digest", "execution_digest", "result_digest"):
            if not isinstance(getattr(self, name), str) or _DIGEST.fullmatch(
                getattr(self, name)
            ) is None:
                raise EvalContractError(f"EvalIdentity.{name} is not a SHA-256 digest")

    @property
    def eval_id(self) -> str:
        digest = _canonical_digest(self.to_dict(), "EvalIdentity", max_bytes=4096)
        return f"eval-{digest[:32]}"

    def to_dict(self) -> dict[str, str]:
        return {
            "framework_version": self.framework_version,
            "spec_digest": self.spec_digest,
            "execution_digest": self.execution_digest,
            "result_digest": self.result_digest,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "EvalIdentity":
        expected = {
            "framework_version",
            "spec_digest",
            "execution_digest",
            "result_digest",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise EvalContractError("EvalIdentity fields are incomplete or unexpected")
        return cls(
            framework_version=value["framework_version"],
            spec_digest=value["spec_digest"],
            execution_digest=value["execution_digest"],
            result_digest=value["result_digest"],
        )


@dataclass(frozen=True)
class EvalResult:
    eval_id: str
    identity: EvalIdentity
    spec_id: str
    execution_id: str
    job_id: str
    evaluator_id: str
    evaluator_version: str
    status: str
    checks: tuple[EvalCheckResult, ...]
    score: None
    evidence: tuple[Mapping[str, Any], ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: Mapping[str, Any]
    created_at: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise EvalContractError("EvalResult.schema_version must be 1")
        if not isinstance(self.identity, EvalIdentity):
            raise EvalContractError("EvalResult.identity must be canonical identity material")
        for name in ("eval_id", "spec_id", "execution_id", "job_id", "evaluator_id"):
            _identifier(getattr(self, name), f"EvalResult.{name}")
        if _EVAL_ID.fullmatch(self.eval_id) is None:
            raise EvalContractError("EvalResult.eval_id is not a canonical content ID")
        _bounded_string(self.evaluator_version, "EvalResult.evaluator_version", 50)
        if self.status not in EVAL_STATUSES:
            raise EvalContractError("EvalResult.status is not canonical")
        if not isinstance(self.checks, tuple) or not 1 <= len(self.checks) <= 100:
            raise EvalContractError("EvalResult.checks must contain 1-100 checks")
        if any(not isinstance(check, EvalCheckResult) for check in self.checks):
            raise EvalContractError("EvalResult.checks must contain EvalCheckResult values")
        if len({check.check_id for check in self.checks}) != len(self.checks):
            raise EvalContractError("EvalResult.check IDs must be unique")
        contract_checks = [
            check for check in self.checks
            if check.evaluator_type == "EXECUTION_RESULT_CONTRACT"
        ]
        if len(contract_checks) != 1 or self.checks[0].evaluator_type != "EXECUTION_RESULT_CONTRACT":
            raise EvalContractError(
                "EvalResult must begin with exactly one EXECUTION_RESULT_CONTRACT check"
            )
        derived = (
            "error" if any(check.status == "error" for check in self.checks)
            else "fail" if any(check.status == "fail" for check in self.checks)
            else "pass"
        )
        if self.status != derived:
            raise EvalContractError("EvalResult.status does not match its checks")
        expected_failures = tuple(
            check.check_id for check in self.checks if check.status in {"fail", "error"}
        )
        if self.failures != expected_failures:
            raise EvalContractError("EvalResult.failures must identify every failed/error check")
        if self.score is not None:
            raise EvalContractError("CORE-03 deterministic EvalResult.score must be null")
        for name, values in (("failures", self.failures), ("warnings", self.warnings)):
            if not isinstance(values, tuple) or len(values) > 100:
                raise EvalContractError(f"EvalResult.{name} must contain at most 100 entries")
            for value in values:
                _bounded_string(value, f"EvalResult.{name} entry", 2000)
        if (
            not isinstance(self.evidence, tuple)
            or len(self.evidence) > MAX_AGGREGATE_EVIDENCE
        ):
            raise EvalContractError("EvalResult.evidence must contain at most 100 references")
        frozen_evidence = tuple(_freeze(item) for item in self.evidence)
        for index, item in enumerate(frozen_evidence):
            _reference(item, f"EvalResult.evidence[{index}]")
        object.__setattr__(self, "evidence", frozen_evidence)
        expected_evidence: list[Mapping[str, Any]] = []
        seen_evidence: set[tuple[str, str]] = set()
        for check in self.checks:
            for reference in check.evidence:
                key = (str(reference["ref_type"]), str(reference["ref"]))
                if key not in seen_evidence:
                    expected_evidence.append(reference)
                    seen_evidence.add(key)
        if tuple(expected_evidence[:MAX_AGGREGATE_EVIDENCE]) != frozen_evidence:
            raise EvalContractError(
                "EvalResult.evidence must be the bounded ordered deduplicated summary of check evidence"
            )
        object.__setattr__(self, "metadata", _metadata(self.metadata, "EvalResult.metadata"))
        _datetime(self.created_at, "EvalResult.created_at")
        self.verify_identity()

    @classmethod
    def create(
        cls,
        *,
        spec_digest: str,
        execution_digest: str,
        spec_id: str,
        execution_id: str,
        job_id: str,
        evaluator_id: str,
        evaluator_version: str,
        status: str,
        checks: tuple[EvalCheckResult, ...],
        score: None,
        evidence: tuple[Mapping[str, Any], ...],
        failures: tuple[str, ...],
        warnings: tuple[str, ...],
        metadata: Mapping[str, Any],
        created_at: str,
    ) -> "EvalResult":
        content = {
            "schema_version": 1,
            "spec_id": spec_id,
            "execution_id": execution_id,
            "job_id": job_id,
            "evaluator_id": evaluator_id,
            "evaluator_version": evaluator_version,
            "status": status,
            "checks": [check.to_dict() for check in checks],
            "score": score,
            "evidence": _thaw(evidence),
            "failures": list(failures),
            "warnings": list(warnings),
            "metadata": _thaw(metadata),
        }
        identity = EvalIdentity(
            framework_version=FRAMEWORK_VERSION,
            spec_digest=spec_digest,
            execution_digest=execution_digest,
            result_digest=_canonical_digest(
                content,
                "EvalResult semantic content",
                max_bytes=_RESULT_IDENTITY_MAX_BYTES,
            ),
        )
        return cls(
            eval_id=identity.eval_id,
            identity=identity,
            spec_id=spec_id,
            execution_id=execution_id,
            job_id=job_id,
            evaluator_id=evaluator_id,
            evaluator_version=evaluator_version,
            status=status,
            checks=checks,
            score=score,
            evidence=evidence,
            failures=failures,
            warnings=warnings,
            metadata=metadata,
            created_at=created_at,
        )

    def identity_payload(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("eval_id")
        value.pop("identity")
        value.pop("created_at")
        return value

    def verify_identity(self) -> None:
        expected_result_digest = _canonical_digest(
            self.identity_payload(),
            "EvalResult semantic content",
            max_bytes=_RESULT_IDENTITY_MAX_BYTES,
        )
        if self.identity.result_digest != expected_result_digest:
            raise EvalContractError("EvalResult semantic content digest mismatch")
        if self.eval_id != self.identity.eval_id:
            raise EvalContractError("EvalResult content identity mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "eval_id": self.eval_id,
            "identity": self.identity.to_dict(),
            "spec_id": self.spec_id,
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "score": self.score,
            "evidence": _thaw(self.evidence),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "metadata": _thaw(self.metadata),
            "created_at": self.created_at,
        }

    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("created_at")
        return value

    @classmethod
    def from_dict(cls, value: Any) -> "EvalResult":
        if not isinstance(value, dict):
            raise EvalContractError("EvalResult payload must be an object")
        expected = {
            "schema_version", "eval_id", "identity", "spec_id", "execution_id", "job_id",
            "evaluator_id", "evaluator_version", "status", "checks", "score",
            "evidence", "failures", "warnings", "metadata", "created_at",
        }
        arrays = ("checks", "evidence", "failures", "warnings")
        if set(value) != expected or any(not isinstance(value.get(name), list) for name in arrays):
            raise EvalContractError("EvalResult fields are incomplete or unexpected")
        return cls(
            schema_version=value["schema_version"],
            eval_id=value["eval_id"],
            identity=EvalIdentity.from_dict(value["identity"]),
            spec_id=value["spec_id"],
            execution_id=value["execution_id"],
            job_id=value["job_id"],
            evaluator_id=value["evaluator_id"],
            evaluator_version=value["evaluator_version"],
            status=value["status"],
            checks=tuple(EvalCheckResult.from_dict(check) for check in value["checks"]),
            score=value["score"],
            evidence=tuple(value["evidence"]),
            failures=tuple(value["failures"]),
            warnings=tuple(value["warnings"]),
            metadata=value["metadata"],
            created_at=value["created_at"],
        )


def eval_input_digests(
    spec: EvalSpec,
    execution: Mapping[str, Any],
) -> tuple[str, str]:
    """Return the canonical exact-input digests retained by EvalIdentity."""
    return (
        _canonical_digest(spec.to_dict(), "EvalSpec identity input"),
        _canonical_digest(execution, "ExecutionResult identity input"),
    )
