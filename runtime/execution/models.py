"""JSON-serializable provider-neutral execution contracts."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from runtime.actions.models import EXECUTION_MODES, ExecutionScope, ScopeContractError


class ExecutionContractError(ValueError):
    """Raised when an execution request or result violates its contract."""


EXECUTION_RESULT_STATUSES = frozenset(
    {"succeeded", "failed", "blocked", "needs_review", "needs_human"}
)
EVIDENCE_KINDS = frozenset(
    {
        "deterministic_check",
        "file_reference",
        "command_result",
        "observation",
        "provider_output",
        "other",
    }
)
EVIDENCE_STATUSES = frozenset({"passed", "failed", "observed", "not_run"})
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
_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "access_token",
        "auth_token",
        "bot_token",
        "client_secret",
        "credential",
        "credentials",
        "github_token",
        "password",
        "secret",
        "shared_secret",
        "private_key",
        "telegram_token",
        "token",
        "webhook_secret",
        "environment",
        "env",
        "chain_of_thought",
        "hidden_reasoning",
    }
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b\d{7,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(
        r"(?i)\b[A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|SECRET)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

_ERROR_DETAIL_MAX_ENTRIES = 32
_ERROR_DETAIL_KEY_LIMIT = 64
_ERROR_DETAIL_STRING_LIMIT = 1000
CANONICAL_INTEGER_MIN = -(2**63)
CANONICAL_INTEGER_MAX = 2**63 - 1


class FrozenMapping(Mapping[str, Any]):
    """Small recursively immutable mapping used by canonical result values."""

    __slots__ = ("__values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        frozen = dict(
            sorted(
                (str(key), _freeze_value(value)) for key, value in values.items()
            )
        )
        object.__setattr__(self, "_FrozenMapping__values", MappingProxyType(frozen))

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("canonical execution result mappings are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("canonical execution result mappings are immutable")

    def __getitem__(self, key: str) -> Any:
        return self.__values[key]

    def __iter__(self):
        return iter(self.__values)

    def __len__(self) -> int:
        return len(self.__values)

    def __repr__(self) -> str:
        return f"FrozenMapping({dict(self.__values)!r})"

    def __deepcopy__(self, memo: dict[int, Any]) -> FrozenMapping:
        return self


def _freeze_value(value: Any) -> Any:
    if isinstance(value, FrozenMapping):
        return value
    if isinstance(value, Mapping):
        return FrozenMapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


def _normalise_sensitive_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_")


def _is_sensitive_key(value: Any) -> bool:
    normalised = _normalise_sensitive_key(value)
    return normalised in _SENSITIVE_KEYS or normalised.endswith(
        (
            "_api_key",
            "_access_token",
            "_auth_token",
            "_password",
            "_secret",
            "_token",
            "_credential",
        )
    )


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


def _number_is_bounded(value: int | float) -> bool:
    return CANONICAL_INTEGER_MIN <= value <= CANONICAL_INTEGER_MAX


def _sanitize_historical_error(error: Any) -> Any:
    """Bound old error details without trusting or rewriting the stored record."""
    if not isinstance(error, dict):
        return error
    sanitized = dict(error)
    if isinstance(sanitized.get("message"), str) and _contains_secret(
        sanitized["message"]
    ):
        sanitized["message"] = "[REDACTED]"
    details = sanitized.get("details")
    if not isinstance(details, dict):
        if "details" in sanitized:
            sanitized["details"] = {"legacy_details": "[OMITTED_COMPLEX_VALUE]"}
        return sanitized
    bounded: dict[str, Any] = {}
    for key in sorted(details, key=lambda item: str(item)):
        if len(bounded) >= _ERROR_DETAIL_MAX_ENTRIES:
            break
        name = str(key)[:_ERROR_DETAIL_KEY_LIMIT]
        if not name or _is_sensitive_key(name):
            continue
        item = details[key]
        if isinstance(item, str):
            bounded[name] = (
                "[REDACTED]"
                if _contains_secret(item)
                else item[:_ERROR_DETAIL_STRING_LIMIT]
            )
        elif item is None or isinstance(item, bool):
            bounded[name] = item
        elif isinstance(item, int):
            bounded[name] = (
                item if _number_is_bounded(item) else "[OMITTED_OUT_OF_RANGE_VALUE]"
            )
        elif isinstance(item, float):
            bounded[name] = (
                item
                if math.isfinite(item) and _number_is_bounded(item)
                else "[OMITTED_OUT_OF_RANGE_VALUE]"
            )
        else:
            bounded[name] = "[OMITTED_COMPLEX_VALUE]"
    sanitized["details"] = bounded
    return sanitized


def _validate_error_details(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ExecutionContractError("ExecutionResult.error.details must be an object")
    if len(value) > _ERROR_DETAIL_MAX_ENTRIES:
        raise ExecutionContractError(
            f"ExecutionResult.error.details must contain at most {_ERROR_DETAIL_MAX_ENTRIES} entries"
        )
    for key, item in value.items():
        _bounded_string(key, "ExecutionResult.error.details key", _ERROR_DETAIL_KEY_LIMIT)
        if _is_sensitive_key(key):
            raise ExecutionContractError(
                "ExecutionResult.error.details contains a prohibited sensitive field"
            )
        if isinstance(item, str):
            if len(item) > _ERROR_DETAIL_STRING_LIMIT:
                raise ExecutionContractError(
                    "ExecutionResult.error.details string value is too long"
                )
        elif item is None or isinstance(item, bool):
            continue
        elif isinstance(item, int):
            if not _number_is_bounded(item):
                raise ExecutionContractError(
                    "ExecutionResult.error.details integer value is out of bounds"
                )
        elif isinstance(item, float):
            if not math.isfinite(item):
                raise ExecutionContractError(
                    "ExecutionResult.error.details values must be finite"
                )
            if not _number_is_bounded(item):
                raise ExecutionContractError(
                    "ExecutionResult.error.details numeric value is out of bounds"
                )
        else:
            raise ExecutionContractError(
                "ExecutionResult.error.details values must be bounded JSON scalars"
            )


def _bounded_string(value: Any, name: str, limit: int, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ExecutionContractError(
            f"{name} must be a non-empty string no longer than {limit} characters"
        )


def _validate_datetime(value: Any, name: str) -> None:
    _bounded_string(value, name, 100)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExecutionContractError(f"{name} must be an ISO 8601 date-time") from error
    if parsed.tzinfo is None:
        raise ExecutionContractError(f"{name} must include a timezone")


def _validate_reference(value: Any, name: str) -> None:
    if not isinstance(value, Mapping):
        raise ExecutionContractError(f"{name} must be an object")
    if set(value) - {"ref_type", "ref", "description"}:
        raise ExecutionContractError(f"{name} contains unexpected fields")
    if value.get("ref_type") not in REFERENCE_TYPES:
        raise ExecutionContractError(f"{name}.ref_type is not canonical")
    _bounded_string(value.get("ref"), f"{name}.ref", 2000)
    if "description" in value:
        _bounded_string(value.get("description"), f"{name}.description", 2000)


def _validate_evidence(value: Any, name: str) -> None:
    if not isinstance(value, Mapping):
        raise ExecutionContractError(f"{name} must be an object")
    if set(value) - {"kind", "status", "summary", "ref"}:
        raise ExecutionContractError(f"{name} contains unexpected fields")
    if value.get("kind") not in EVIDENCE_KINDS:
        raise ExecutionContractError(f"{name}.kind is not canonical")
    if value.get("status") not in EVIDENCE_STATUSES:
        raise ExecutionContractError(f"{name}.status is not canonical")
    _bounded_string(value.get("summary"), f"{name}.summary", 2000)
    if "ref" in value:
        _validate_reference(value["ref"], f"{name}.ref")


def _validate_blocker(value: Any, name: str) -> None:
    if not isinstance(value, Mapping):
        raise ExecutionContractError(f"{name} must be an object")
    required = {"code", "message", "retryable", "requires_human"}
    if set(value) - {*required, "ref"} or not required.issubset(value):
        raise ExecutionContractError(f"{name} has invalid fields")
    if not isinstance(value["code"], str) or _CODE.fullmatch(value["code"]) is None:
        raise ExecutionContractError(f"{name}.code is invalid")
    _bounded_string(value["message"], f"{name}.message", 2000)
    if not isinstance(value["retryable"], bool) or not isinstance(
        value["requires_human"], bool
    ):
        raise ExecutionContractError(f"{name} flags must be boolean")
    if "ref" in value:
        _validate_reference(value["ref"], f"{name}.ref")


def _validate_next_action(value: Any, name: str) -> None:
    if not isinstance(value, Mapping):
        raise ExecutionContractError(f"{name} must be an object")
    required = {"action", "description", "requires_human", "automatic"}
    if set(value) - {*required, "ref"} or not required.issubset(value):
        raise ExecutionContractError(f"{name} has invalid fields")
    if not isinstance(value["action"], str) or _CODE.fullmatch(value["action"]) is None:
        raise ExecutionContractError(f"{name}.action is invalid")
    _bounded_string(value["description"], f"{name}.description", 2000)
    if not isinstance(value["requires_human"], bool) or value["automatic"] is not False:
        raise ExecutionContractError(
            f"{name} must declare requires_human and automatic=false"
        )
    if "ref" in value:
        _validate_reference(value["ref"], f"{name}.ref")


def _validate_safe_content(value: Any, path: str = "ExecutionResult") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _is_sensitive_key(key):
                raise ExecutionContractError(
                    f"{path} contains a prohibited sensitive field"
                )
            _validate_safe_content(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_safe_content(item, f"{path}[{index}]")
    elif isinstance(value, str) and _contains_secret(value):
        raise ExecutionContractError(f"{path} contains credential-like content")
    elif isinstance(value, int) and not isinstance(value, bool):
        if not _number_is_bounded(value):
            raise ExecutionContractError(f"{path} integer value is out of bounds")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ExecutionContractError(f"{path} must contain only finite numbers")
        if not _number_is_bounded(value):
            raise ExecutionContractError(f"{path} numeric value is out of bounds")


@dataclass(frozen=True)
class ExecutionRequest:
    execution_id: str
    job_id: str
    task: str
    task_class: str
    project_id: str | None
    agent: str
    skill: str | None
    workflow: str
    capability: str
    provider: str | None
    risk_level: str
    input_refs: tuple[dict[str, Any], ...]
    context_refs: tuple[dict[str, Any], ...]
    review_required: bool
    attempt: int
    dry_run: bool = False
    approval_status: str = "not_required"
    execution_mode: str = "READ_ONLY"
    execution_scope: dict[str, Any] | None = None
    authorization_fingerprint: str | None = None

    def __post_init__(self) -> None:
        for name in ("execution_id", "job_id", "task", "task_class", "agent", "workflow", "capability", "risk_level"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ExecutionContractError(f"ExecutionRequest.{name} must be non-empty")
        if self.attempt < 1:
            raise ExecutionContractError("ExecutionRequest.attempt must be positive")
        if not isinstance(self.dry_run, bool):
            raise ExecutionContractError("ExecutionRequest.dry_run must be a boolean")
        if self.approval_status not in {"not_required", "required", "requested", "approved"}:
            raise ExecutionContractError(
                "ExecutionRequest.approval_status is not a canonical approval state"
            )
        if self.execution_mode not in EXECUTION_MODES:
            raise ExecutionContractError("ExecutionRequest.execution_mode is not canonical")
        if self.execution_mode == "READ_ONLY":
            if self.execution_scope is not None or self.authorization_fingerprint is not None:
                raise ExecutionContractError(
                    "READ_ONLY execution cannot contain write scope or authorization"
                )
        else:
            try:
                scope = ExecutionScope.from_dict(self.execution_scope or {})
            except ScopeContractError as error:
                raise ExecutionContractError(str(error)) from error
            if scope.dry_run != self.dry_run:
                raise ExecutionContractError(
                    "CONTROLLED_WRITE execution scope dry_run must match the request"
                )
            if self.approval_status != "approved" or not self.authorization_fingerprint:
                raise ExecutionContractError(
                    "CONTROLLED_WRITE execution requires exact approved authorization"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "task": self.task,
            "task_class": self.task_class,
            "project_id": self.project_id,
            "agent": self.agent,
            "skill": self.skill,
            "workflow": self.workflow,
            "capability": self.capability,
            "provider": self.provider,
            "risk_level": self.risk_level,
            "input_refs": deepcopy(list(self.input_refs)),
            "context_refs": deepcopy(list(self.context_refs)),
            "review_required": self.review_required,
            "attempt": self.attempt,
            "dry_run": self.dry_run,
            "approval_status": self.approval_status,
            "execution_mode": self.execution_mode,
            "execution_scope": deepcopy(self.execution_scope),
            "authorization_fingerprint": self.authorization_fingerprint,
        }


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    job_id: str
    status: str
    summary: str | None
    error: dict[str, Any] | None
    provider: str | None
    started_at: str
    completed_at: str
    output_refs: tuple[dict[str, Any], ...] | None = None
    requested_provider: str | None = None
    preferred_provider: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    execution_mode: str = "READ_ONLY"
    dry_run: bool = False
    evidence: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] | None = None
    blockers: tuple[dict[str, Any], ...] = ()
    next_actions: tuple[dict[str, Any], ...] = ()
    retryable: bool | None = None
    usage: dict[str, Any] | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        _bounded_string(self.execution_id, "ExecutionResult.execution_id", 200)
        _bounded_string(self.job_id, "ExecutionResult.job_id", 200)
        if self.schema_version != 1 or isinstance(self.schema_version, bool):
            raise ExecutionContractError("ExecutionResult.schema_version must be 1")
        if self.status not in EXECUTION_RESULT_STATUSES:
            raise ExecutionContractError("ExecutionResult.status is not canonical")
        if self.status == "failed" and not self.error:
            raise ExecutionContractError("Failed ExecutionResult requires an error")
        _validate_datetime(self.started_at, "ExecutionResult.started_at")
        _validate_datetime(self.completed_at, "ExecutionResult.completed_at")
        if self.execution_mode not in EXECUTION_MODES:
            raise ExecutionContractError("ExecutionResult.execution_mode is not canonical")
        if not isinstance(self.dry_run, bool):
            raise ExecutionContractError("ExecutionResult.dry_run must be a boolean")
        if not isinstance(self.fallback_used, bool):
            raise ExecutionContractError("ExecutionResult.fallback_used must be a boolean")
        _bounded_string(self.summary, "ExecutionResult.summary", 4000, optional=True)
        _bounded_string(self.provider, "ExecutionResult.provider", 100, optional=True)
        _bounded_string(
            self.requested_provider,
            "ExecutionResult.requested_provider",
            100,
            optional=True,
        )
        _bounded_string(
            self.preferred_provider,
            "ExecutionResult.preferred_provider",
            100,
            optional=True,
        )
        _bounded_string(
            self.fallback_reason,
            "ExecutionResult.fallback_reason",
            2000,
            optional=True,
        )

        for name in ("evidence", "blockers", "next_actions"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or len(value) > 100:
                raise ExecutionContractError(
                    f"ExecutionResult.{name} must be a tuple with at most 100 items"
                )

        for name in ("output_refs", "artifacts"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, tuple) or len(value) > 100
            ):
                raise ExecutionContractError(
                    f"ExecutionResult.{name} must be a tuple with at most 100 items"
                )

        output_refs = (
            None
            if self.output_refs is None
            else tuple(_freeze_value(item) for item in self.output_refs)
        )
        artifacts = (
            None
            if self.artifacts is None
            else tuple(_freeze_value(item) for item in self.artifacts)
        )
        if output_refs is not None and artifacts is not None and output_refs != artifacts:
            raise ExecutionContractError(
                "ExecutionResult.output_refs and artifacts must contain the same references"
            )
        canonical_artifacts = artifacts if artifacts is not None else output_refs
        if canonical_artifacts is None:
            canonical_artifacts = ()
        object.__setattr__(self, "artifacts", canonical_artifacts)
        object.__setattr__(self, "output_refs", canonical_artifacts)
        object.__setattr__(
            self, "evidence", tuple(_freeze_value(item) for item in self.evidence)
        )
        object.__setattr__(
            self, "blockers", tuple(_freeze_value(item) for item in self.blockers)
        )
        object.__setattr__(
            self, "next_actions", tuple(_freeze_value(item) for item in self.next_actions)
        )
        object.__setattr__(self, "error", _freeze_value(self.error))
        object.__setattr__(self, "usage", _freeze_value(self.usage))

        for index, reference in enumerate(self.artifacts):
            _validate_reference(reference, f"ExecutionResult.artifacts[{index}]")
        for index, item in enumerate(self.evidence):
            _validate_evidence(item, f"ExecutionResult.evidence[{index}]")
        for index, item in enumerate(self.blockers):
            _validate_blocker(item, f"ExecutionResult.blockers[{index}]")
        for index, item in enumerate(self.next_actions):
            _validate_next_action(item, f"ExecutionResult.next_actions[{index}]")

        if self.error is not None:
            if not isinstance(self.error, Mapping):
                raise ExecutionContractError("ExecutionResult.error must be an object or null")
            required = {"code", "message", "retryable"}
            if set(self.error) - {*required, "details"} or not required.issubset(self.error):
                raise ExecutionContractError("ExecutionResult.error has invalid fields")
            if not isinstance(self.error["code"], str) or _CODE.fullmatch(
                self.error["code"]
            ) is None:
                raise ExecutionContractError("ExecutionResult.error.code is invalid")
            _bounded_string(self.error["message"], "ExecutionResult.error.message", 2000)
            if not isinstance(self.error["retryable"], bool):
                raise ExecutionContractError("ExecutionResult.error.retryable must be boolean")
            if "details" in self.error:
                _validate_error_details(self.error["details"])

        retryable = self.retryable
        if retryable is None:
            if self.error is not None:
                retryable = self.error["retryable"]
            else:
                retryable = any(item["retryable"] for item in self.blockers)
            object.__setattr__(self, "retryable", retryable)
        if not isinstance(retryable, bool):
            raise ExecutionContractError("ExecutionResult.retryable must be a boolean")
        if self.error is not None and retryable != self.error["retryable"]:
            raise ExecutionContractError(
                "ExecutionResult.retryable must match error.retryable"
            )
        if self.blockers and retryable != any(
            item["retryable"] for item in self.blockers
        ):
            raise ExecutionContractError(
                "ExecutionResult.retryable must match its blockers"
            )

        if self.status == "succeeded":
            if (
                self.error is not None
                or self.blockers
                or retryable
                or any(item["requires_human"] for item in self.next_actions)
            ):
                raise ExecutionContractError(
                    "Succeeded ExecutionResult cannot contain errors, blockers, retryability, or human-required actions"
                )
        elif self.status == "failed":
            if self.blockers:
                raise ExecutionContractError(
                    "Failed ExecutionResult cannot contain blockers; use blocked or needs_human"
                )
        elif self.status == "blocked":
            if self.error is not None or not self.blockers or any(
                item["requires_human"] for item in self.blockers
            ) or any(item["requires_human"] for item in self.next_actions):
                raise ExecutionContractError(
                    "Blocked ExecutionResult requires only non-human blockers and no error"
                )
        elif self.status == "needs_review":
            if (
                self.error is not None
                or self.blockers
                or any(item["requires_human"] for item in self.next_actions)
                or not (self.summary or self.evidence or self.artifacts)
            ):
                raise ExecutionContractError(
                    "Needs-review ExecutionResult requires produced work without errors, blockers, or human-required actions"
                )
        elif self.status == "needs_human" and (
            self.error is not None
            or not any(item["requires_human"] for item in self.blockers)
        ):
            raise ExecutionContractError(
                "Needs-human ExecutionResult requires a human blocker and no error"
            )

        if self.usage is not None:
            if not isinstance(self.usage, Mapping):
                raise ExecutionContractError("ExecutionResult.usage must be an object or null")
            allowed_usage = {
                "duration_ms",
                "input_units",
                "output_units",
                "total_units",
                "unit",
            }
            if set(self.usage) - allowed_usage:
                raise ExecutionContractError("ExecutionResult.usage contains unexpected fields")
            for name in ("duration_ms", "input_units", "output_units", "total_units"):
                if name in self.usage and (
                    not isinstance(self.usage[name], int)
                    or isinstance(self.usage[name], bool)
                    or self.usage[name] < 0
                    or self.usage[name] > CANONICAL_INTEGER_MAX
                ):
                    raise ExecutionContractError(
                        f"ExecutionResult.usage.{name} must be a bounded non-negative integer"
                    )
            if "unit" in self.usage:
                _bounded_string(
                    self.usage["unit"], "ExecutionResult.usage.unit", 50
                )

        _validate_safe_content(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "status": self.status,
            "output_refs": _thaw_value(self.artifacts),
            "evidence": _thaw_value(self.evidence),
            "artifacts": _thaw_value(self.artifacts),
            "blockers": _thaw_value(self.blockers),
            "next_actions": _thaw_value(self.next_actions),
            "retryable": self.retryable,
            "summary": self.summary,
            "error": _thaw_value(self.error),
            "provider": self.provider,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "requested_provider": self.requested_provider,
            "preferred_provider": self.preferred_provider,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "execution_mode": self.execution_mode,
            "dry_run": self.dry_run,
            "usage": _thaw_value(self.usage),
        }

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        sanitize_historical: bool = False,
    ) -> ExecutionResult:
        """Load current or legacy persisted results through one narrow adapter."""
        if not isinstance(value, dict):
            raise ExecutionContractError("ExecutionResult payload must be an object")
        allowed = {
            "schema_version",
            "execution_id",
            "job_id",
            "status",
            "output_refs",
            "evidence",
            "artifacts",
            "blockers",
            "next_actions",
            "retryable",
            "summary",
            "error",
            "provider",
            "started_at",
            "completed_at",
            "requested_provider",
            "preferred_provider",
            "fallback_used",
            "fallback_reason",
            "execution_mode",
            "dry_run",
            "usage",
        }
        unexpected = set(value) - allowed
        if unexpected:
            raise ExecutionContractError(
                "ExecutionResult payload contains unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        if (
            "artifacts" in value
            and "output_refs" in value
            and value.get("artifacts") != value.get("output_refs")
        ):
            raise ExecutionContractError(
                "ExecutionResult.output_refs and artifacts must contain the same references"
            )
        artifacts = value.get("artifacts") if "artifacts" in value else None
        output_refs = value.get("output_refs") if "output_refs" in value else None
        error = (
            _sanitize_historical_error(value.get("error"))
            if sanitize_historical
            else value.get("error")
        )
        retryable = value.get("retryable")
        if retryable is None and isinstance(error, dict):
            retryable = error.get("retryable")
        status = value.get("status")
        if status is None and isinstance(error, dict):
            status = "failed"
        return cls(
            execution_id=value.get("execution_id"),
            job_id=value.get("job_id"),
            status=status,
            output_refs=None if output_refs is None else tuple(output_refs),
            summary=value.get("summary"),
            error=error,
            provider=value.get("provider"),
            started_at=value.get("started_at"),
            completed_at=value.get("completed_at"),
            requested_provider=value.get("requested_provider"),
            preferred_provider=value.get("preferred_provider"),
            fallback_used=value.get("fallback_used", False),
            fallback_reason=value.get("fallback_reason"),
            execution_mode=value.get("execution_mode", "READ_ONLY"),
            dry_run=value.get("dry_run", False),
            evidence=tuple(value.get("evidence", ())),
            artifacts=None if artifacts is None else tuple(artifacts),
            blockers=tuple(value.get("blockers", ())),
            next_actions=tuple(value.get("next_actions", ())),
            retryable=retryable,
            usage=value.get("usage"),
            schema_version=value.get("schema_version", 1),
        )
