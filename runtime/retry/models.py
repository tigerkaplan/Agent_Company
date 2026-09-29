"""Typed deterministic contracts for CORE-06 retry and stop decisions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class RetryContractError(ValueError):
    """Raised when retry policy, state, or authorization is malformed."""


POLICY_VERSION = 1
MAX_TOTAL_ATTEMPTS = 32
MAX_THRESHOLD = 16
MAX_HISTORY = 32
MAX_CYCLE_WINDOW = 16
DECISIONS = frozenset({"RETRY", "STOP", "REPLAN_REQUIRED", "NEEDS_HUMAN", "ERROR"})
FAILURE_CLASSES = frozenset(
    {
        "transient_execution",
        "transient_runtime",
        "transient_storage",
        "lease_expired",
        "review_repair",
        "permanent_failure",
        "authority_failure",
        "budget_failure",
        "policy_failure",
        "malformed_state",
    }
)
DEFAULT_ALLOWED_FAILURE_CLASSES = (
    "lease_expired",
    "review_repair",
    "transient_execution",
    "transient_runtime",
    "transient_storage",
)
DEFAULT_DENIED_FAILURE_CLASSES = (
    "authority_failure",
    "budget_failure",
    "malformed_state",
    "permanent_failure",
    "policy_failure",
)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise RetryContractError("Retry values must be canonical JSON") from error
    return hashlib.sha256(encoded).hexdigest()


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise RetryContractError(f"{name} must be a bounded canonical identifier")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise RetryContractError(f"{name} must be a SHA-256 digest")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RetryContractError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise RetryContractError(f"{name} must be between {minimum} and {maximum}")
    return value


def _timestamp(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 100:
        raise RetryContractError(f"{name} must be a bounded ISO 8601 date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RetryContractError(f"{name} must be an ISO 8601 date-time") from error
    if parsed.tzinfo is None:
        raise RetryContractError(f"{name} must include a timezone")
    return value


@dataclass(frozen=True)
class RetryPolicySpec:
    """Bounded policy input. max_total_attempts includes the initial attempt."""

    max_total_attempts: int
    allowed_failure_classes: tuple[str, ...] = DEFAULT_ALLOWED_FAILURE_CLASSES
    denied_failure_classes: tuple[str, ...] = DEFAULT_DENIED_FAILURE_CLASSES
    no_progress_threshold: int | None = 2
    stuck_threshold: int | None = 3
    cycle_threshold: int | None = 2
    cycle_window: int = 8
    history_limit: int = MAX_HISTORY
    exhaustion_action: str = "REPLAN_REQUIRED"

    @classmethod
    def from_input(cls, value: Any, *, max_attempts: Any) -> "RetryPolicySpec":
        total = _integer(max_attempts, "max_attempts", 1, MAX_TOTAL_ATTEMPTS)
        if value is None:
            return cls(max_total_attempts=total)
        if not isinstance(value, Mapping):
            raise RetryContractError("retry_policy must be an object")
        allowed_fields = {
            "max_total_attempts",
            "allowed_failure_classes",
            "denied_failure_classes",
            "no_progress_threshold",
            "stuck_threshold",
            "cycle_threshold",
            "cycle_window",
            "history_limit",
            "exhaustion_action",
        }
        unexpected = sorted(set(value) - allowed_fields)
        if unexpected:
            raise RetryContractError(
                "retry_policy contains unknown fields: " + ", ".join(unexpected)
            )
        configured_total = _integer(
            value.get("max_total_attempts", total),
            "max_total_attempts",
            1,
            MAX_TOTAL_ATTEMPTS,
        )
        if configured_total != total:
            raise RetryContractError(
                "retry_policy.max_total_attempts must equal canonical max_attempts"
            )
        allowed = cls._classes(
            value.get("allowed_failure_classes", DEFAULT_ALLOWED_FAILURE_CLASSES),
            "allowed_failure_classes",
        )
        denied = cls._classes(
            value.get("denied_failure_classes", DEFAULT_DENIED_FAILURE_CLASSES),
            "denied_failure_classes",
        )
        if set(allowed) & set(denied):
            raise RetryContractError("Allowed and denied failure classes must be disjoint")
        mandatory_denied = set(DEFAULT_DENIED_FAILURE_CLASSES)
        if not mandatory_denied.issubset(denied):
            raise RetryContractError(
                "Permanent, authority, budget, policy, and malformed failures must remain denied"
            )
        threshold_values: dict[str, int | None] = {}
        for name, default in (
            ("no_progress_threshold", 2),
            ("stuck_threshold", 3),
            ("cycle_threshold", 2),
        ):
            raw = value.get(name, default)
            threshold_values[name] = (
                None if raw is None else _integer(raw, name, 1, MAX_THRESHOLD)
            )
        cycle_window = _integer(
            value.get("cycle_window", 8), "cycle_window", 2, MAX_CYCLE_WINDOW
        )
        history_limit = _integer(
            value.get("history_limit", MAX_HISTORY),
            "history_limit",
            1,
            MAX_HISTORY,
        )
        if history_limit < cycle_window:
            raise RetryContractError("history_limit cannot be smaller than cycle_window")
        exhaustion = value.get("exhaustion_action", "REPLAN_REQUIRED")
        if exhaustion not in {"REPLAN_REQUIRED", "STOP"}:
            raise RetryContractError(
                "exhaustion_action must be REPLAN_REQUIRED or STOP"
            )
        return cls(
            max_total_attempts=configured_total,
            allowed_failure_classes=allowed,
            denied_failure_classes=denied,
            no_progress_threshold=threshold_values["no_progress_threshold"],
            stuck_threshold=threshold_values["stuck_threshold"],
            cycle_threshold=threshold_values["cycle_threshold"],
            cycle_window=cycle_window,
            history_limit=history_limit,
            exhaustion_action=str(exhaustion),
        )

    @staticmethod
    def _classes(value: Any, name: str) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)) or len(value) > len(FAILURE_CLASSES):
            raise RetryContractError(f"{name} must be a bounded array")
        if any(not isinstance(item, str) or item not in FAILURE_CLASSES for item in value):
            raise RetryContractError(f"{name} contains an unknown failure class")
        if len(value) != len(set(value)):
            raise RetryContractError(f"{name} must contain unique values")
        return tuple(sorted(value))


def policy_id_for(logical_job_id: str) -> str:
    logical = _identifier(logical_job_id, "logical_job_id")
    return f"retry-policy-{hashlib.sha256(logical.encode('utf-8')).hexdigest()[:32]}"


def policy_digest(value: Mapping[str, Any]) -> str:
    semantic = {
        name: value.get(name)
        for name in (
            "schema_version",
            "policy_id",
            "logical_job_id",
            "policy_version",
            "max_total_attempts",
            "allowed_failure_classes",
            "denied_failure_classes",
            "no_progress_threshold",
            "stuck_threshold",
            "cycle_threshold",
            "cycle_window",
            "history_limit",
            "exhaustion_action",
            "created_at",
        )
    }
    return _canonical_digest(semantic)


@dataclass(frozen=True)
class RetryBinding:
    policy_id: str
    logical_job_id: str
    policy_digest: str

    @classmethod
    def from_dict(cls, value: Any) -> "RetryBinding":
        if not isinstance(value, Mapping) or set(value) != {
            "policy_id",
            "logical_job_id",
            "policy_digest",
        }:
            raise RetryContractError(
                "retry_policy binding must contain only policy_id, logical_job_id, and policy_digest"
            )
        return cls(
            _identifier(value.get("policy_id"), "policy_id"),
            _identifier(value.get("logical_job_id"), "logical_job_id"),
            _digest(value.get("policy_digest"), "policy_digest"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "logical_job_id": self.logical_job_id,
            "policy_digest": self.policy_digest,
        }


@dataclass(frozen=True)
class RetryPolicy:
    policy_id: str
    logical_job_id: str
    policy_version: int
    max_total_attempts: int
    allowed_failure_classes: tuple[str, ...]
    denied_failure_classes: tuple[str, ...]
    no_progress_threshold: int | None
    stuck_threshold: int | None
    cycle_threshold: int | None
    cycle_window: int
    history_limit: int
    exhaustion_action: str
    created_at: str
    digest: str

    @classmethod
    def create(
        cls, logical_job_id: str, spec: RetryPolicySpec, *, created_at: str
    ) -> "RetryPolicy":
        value = {
            "schema_version": 1,
            "policy_id": policy_id_for(logical_job_id),
            "logical_job_id": _identifier(logical_job_id, "logical_job_id"),
            "policy_version": POLICY_VERSION,
            "max_total_attempts": spec.max_total_attempts,
            "allowed_failure_classes": list(spec.allowed_failure_classes),
            "denied_failure_classes": list(spec.denied_failure_classes),
            "no_progress_threshold": spec.no_progress_threshold,
            "stuck_threshold": spec.stuck_threshold,
            "cycle_threshold": spec.cycle_threshold,
            "cycle_window": spec.cycle_window,
            "history_limit": spec.history_limit,
            "exhaustion_action": spec.exhaustion_action,
            "created_at": _timestamp(created_at, "created_at"),
        }
        value["policy_digest"] = policy_digest(value)
        return cls.from_dict(value)

    @classmethod
    def from_dict(cls, value: Any) -> "RetryPolicy":
        if not isinstance(value, Mapping):
            raise RetryContractError("Retry policy must be an object")
        expected = {
            "schema_version",
            "policy_id",
            "logical_job_id",
            "policy_version",
            "max_total_attempts",
            "allowed_failure_classes",
            "denied_failure_classes",
            "no_progress_threshold",
            "stuck_threshold",
            "cycle_threshold",
            "cycle_window",
            "history_limit",
            "exhaustion_action",
            "created_at",
            "policy_digest",
        }
        if set(value) != expected:
            raise RetryContractError("Retry policy has invalid fields")
        if (
            _integer(value.get("schema_version"), "schema_version", 1, 1) != 1
            or _integer(value.get("policy_version"), "policy_version", POLICY_VERSION, POLICY_VERSION) != POLICY_VERSION
        ):
            raise RetryContractError("Retry policy version is unsupported")
        spec = RetryPolicySpec.from_input(
            {
                name: value.get(name)
                for name in (
                    "max_total_attempts",
                    "allowed_failure_classes",
                    "denied_failure_classes",
                    "no_progress_threshold",
                    "stuck_threshold",
                    "cycle_threshold",
                    "cycle_window",
                    "history_limit",
                    "exhaustion_action",
                )
            },
            max_attempts=value.get("max_total_attempts"),
        )
        logical = _identifier(value.get("logical_job_id"), "logical_job_id")
        policy_id = _identifier(value.get("policy_id"), "policy_id")
        if policy_id != policy_id_for(logical):
            raise RetryContractError("Retry policy identity does not match logical job")
        digest = _digest(value.get("policy_digest"), "policy_digest")
        if digest != policy_digest(value):
            raise RetryContractError("Retry policy digest does not match content")
        return cls(
            policy_id,
            logical,
            POLICY_VERSION,
            spec.max_total_attempts,
            spec.allowed_failure_classes,
            spec.denied_failure_classes,
            spec.no_progress_threshold,
            spec.stuck_threshold,
            spec.cycle_threshold,
            spec.cycle_window,
            spec.history_limit,
            spec.exhaustion_action,
            _timestamp(value.get("created_at"), "created_at"),
            digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "policy_id": self.policy_id,
            "logical_job_id": self.logical_job_id,
            "policy_version": self.policy_version,
            "max_total_attempts": self.max_total_attempts,
            "allowed_failure_classes": list(self.allowed_failure_classes),
            "denied_failure_classes": list(self.denied_failure_classes),
            "no_progress_threshold": self.no_progress_threshold,
            "stuck_threshold": self.stuck_threshold,
            "cycle_threshold": self.cycle_threshold,
            "cycle_window": self.cycle_window,
            "history_limit": self.history_limit,
            "exhaustion_action": self.exhaustion_action,
            "created_at": self.created_at,
            "policy_digest": self.digest,
        }

    @property
    def binding(self) -> RetryBinding:
        return RetryBinding(self.policy_id, self.logical_job_id, self.digest)


@dataclass(frozen=True)
class RetryDecision:
    decision: str
    reason_code: str
    decision_id: str
    source_job_id: str
    failed_unit_id: str
    retry_sequence: int
    retry_job_id: str | None
    authorization: dict[str, Any] | None
    evidence: dict[str, Any]

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise RetryContractError("Retry decision is not canonical")
        _identifier(self.decision_id, "decision_id")
        _identifier(self.source_job_id, "source_job_id")
        _identifier(self.failed_unit_id, "failed_unit_id")
        _integer(self.retry_sequence, "retry_sequence", 1, MAX_TOTAL_ATTEMPTS)
        if self.retry_job_id is not None:
            _identifier(self.retry_job_id, "retry_job_id")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "decision_id": self.decision_id,
            "source_job_id": self.source_job_id,
            "failed_unit_id": self.failed_unit_id,
            "retry_sequence": self.retry_sequence,
            "evidence": deepcopy(self.evidence),
        }
        if self.retry_job_id is not None:
            value["retry_job_id"] = self.retry_job_id
        if self.authorization is not None:
            value["authorization"] = deepcopy(self.authorization)
        return value


def retry_work_digest(job: Mapping[str, Any]) -> str:
    """Bind the exact execution-material work, excluding attempt-local lifecycle data."""
    fields = (
        "task",
        "task_class",
        "project_id",
        "agent",
        "skill",
        "workflow",
        "capability",
        "provider",
        "risk_level",
        "review_required",
        "input_refs",
        "execution_mode",
        "execution_scope",
        "dry_run",
        "continuation_plan",
        "execution_budget",
        "retry_policy",
    )
    material = {name: deepcopy(job.get(name)) for name in fields}
    checkpoint = job.get("continuation")
    if isinstance(checkpoint, Mapping):
        material["continuation"] = {
            name: deepcopy(checkpoint.get(name))
            for name in (
                "logical_job_id",
                "plan_id",
                "plan_digest",
                "sequence",
                "current_step_id",
                "completed_step_ids",
                "remaining_step_ids",
            )
        }
        # Completion of this unit is lifecycle progress, not a different work
        # request. CORE-02 independently authenticates the actual checkpoint.
        plan = job.get("continuation_plan")
        sequence = checkpoint.get("sequence")
        if isinstance(plan, Mapping) and type(sequence) is int:
            steps = [step.get("step_id") for step in plan.get("steps", [])]
            material["continuation"]["completed_step_ids"] = steps[:sequence]
            material["continuation"]["remaining_step_ids"] = steps[sequence:]
    return _canonical_digest(material)


def retry_unit_id(job: Mapping[str, Any]) -> str:
    checkpoint = job.get("continuation")
    if isinstance(checkpoint, Mapping):
        return _identifier(checkpoint.get("current_step_id"), "failed_unit_id")
    binding = RetryBinding.from_dict(job.get("retry_policy"))
    return binding.logical_job_id


def repair_scope(job: Mapping[str, Any], failed_unit_id: str) -> dict[str, Any]:
    from runtime.actions.models import normalize_relative_path, scope_path_contains, scope_path_key

    scope = job.get("execution_scope")
    allowed_paths = []
    if isinstance(scope, Mapping) and isinstance(scope.get("allowed_paths"), list):
        allowed_paths = deepcopy(scope["allowed_paths"])
    checkpoint = job.get("continuation")
    if isinstance(checkpoint, Mapping):
        # A parent scope is not an allocation of that scope to each plan unit.
        # Without an explicit canonical unit scope, write repair is held closed.
        step = next((step for step in job.get("continuation_plan", {}).get("steps", [])
                     if step.get("step_id") == failed_unit_id), {})
        unit_scope = step.get("execution_scope")
        parent_paths = [normalize_relative_path(path) for path in allowed_paths]
        unit_paths = ([normalize_relative_path(path) for path in unit_scope.get("allowed_paths", [])]
                      if isinstance(unit_scope, Mapping) else [])
        intersection = {}
        for parent in parent_paths:
            for unit in unit_paths:
                if scope_path_contains(parent, unit, project_root=scope["project_root"]):
                    intersection[scope_path_key(unit)] = unit
                elif scope_path_contains(unit, parent, project_root=scope["project_root"]):
                    intersection[scope_path_key(parent)] = parent
        allowed_paths = [intersection[key] for key in sorted(intersection)]
    allowed_paths = [normalize_relative_path(path) for path in allowed_paths]
    return {
        "failed_unit_id": _identifier(failed_unit_id, "failed_unit_id"),
        "capability": _identifier(job.get("capability"), "capability"),
        "execution_mode": job.get("execution_mode", "READ_ONLY"),
        "allowed_paths": allowed_paths,
        "execution_scope_digest": _canonical_digest(scope),
    }


def authorization_digest(value: Mapping[str, Any]) -> str:
    semantic = {name: deepcopy(value.get(name)) for name in value if name != "authorization_digest"}
    return _canonical_digest(semantic)


def validate_repair_scope(value: Any, *, capability: str, execution_mode: str,
                          execution_scope: Any, unit_id: str | None = None) -> None:
    from runtime.actions.models import normalize_relative_path

    if not isinstance(value, Mapping) or set(value) != {
        "failed_unit_id", "capability", "execution_mode", "allowed_paths", "execution_scope_digest"
    }:
        raise RetryContractError("Retry repair scope is malformed")
    _identifier(value["failed_unit_id"], "failed_unit_id")
    if (value["capability"] != capability or value["execution_mode"] != execution_mode
            or value["execution_scope_digest"] != _canonical_digest(execution_scope)
            or unit_id is not None and value["failed_unit_id"] != unit_id):
        raise RetryContractError("Retry repair scope is stale or broadens work authority")
    paths = value["allowed_paths"]
    if (not isinstance(paths, list) or len(paths) > 64 or any(not isinstance(path, str) for path in paths)
            or len(set(paths)) != len(paths)):
        raise RetryContractError("Retry repair paths must be a bounded unique array")
    for path in paths:
        if normalize_relative_path(path) != path:
            raise RetryContractError("Retry repair paths must be canonical")


def state_digest(value: Mapping[str, Any]) -> str:
    semantic = {name: deepcopy(value.get(name)) for name in value if name != "state_digest"}
    return _canonical_digest(semantic)


def history_entry_digest(value: Mapping[str, Any]) -> str:
    return _canonical_digest(value)
