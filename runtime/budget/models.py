"""Typed canonical contracts for logical-job execution budgets."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class BudgetContractError(ValueError):
    """Raised when a budget contract is malformed or inconsistent."""


POLICY_VERSION = 1
MAX_ELAPSED_MS = 7 * 24 * 60 * 60 * 1000
MAX_EXECUTION_UNITS = 100_000
MAX_STATE_SEQUENCE = 2**63 - 1
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")


def parse_timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or len(value) > 100:
        raise BudgetContractError(f"{name} must be a bounded ISO 8601 date-time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise BudgetContractError(f"{name} must be an ISO 8601 date-time") from error
    if parsed.tzinfo is None:
        raise BudgetContractError(f"{name} must include a timezone")
    return parsed


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise BudgetContractError(f"{name} must be a bounded canonical identifier")
    return value


def _bounded_integer(value: Any, name: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BudgetContractError(f"{name} must be an integer")
    if not 0 <= value <= maximum:
        raise BudgetContractError(f"{name} must be between 0 and {maximum}")
    return value


def policy_digest(value: Mapping[str, Any]) -> str:
    semantic = {
        "schema_version": value.get("schema_version"),
        "budget_id": value.get("budget_id"),
        "logical_job_id": value.get("logical_job_id"),
        "policy_version": value.get("policy_version"),
        "max_elapsed_ms": value.get("max_elapsed_ms"),
        "max_execution_units": value.get("max_execution_units"),
        "created_at": value.get("created_at"),
    }
    encoded = json.dumps(
        semantic,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def budget_state_digest(value: Mapping[str, Any]) -> str:
    return _canonical_digest(value)


def reservation_history_digest(value: Any) -> str:
    return _canonical_digest(value)


def usage_anchor_digest(value: Mapping[str, Any]) -> str:
    semantic = {
        "schema_version": value.get("schema_version"),
        "budget_id": value.get("budget_id"),
        "logical_job_id": value.get("logical_job_id"),
        "policy_digest": value.get("policy_digest"),
        "state_sequence": value.get("state_sequence"),
        "consumed_execution_units": value.get("consumed_execution_units"),
        "consumed_elapsed_ms": value.get("consumed_elapsed_ms"),
        "reservation_count": value.get("reservation_count"),
        "reservation_history_digest": value.get("reservation_history_digest"),
        "state_digest": value.get("state_digest"),
        "previous_anchor_digest": value.get("previous_anchor_digest"),
    }
    return _canonical_digest(semantic)


def usage_claim_digest(value: Mapping[str, Any]) -> str:
    semantic = {
        "schema_version": value.get("schema_version"),
        "budget_id": value.get("budget_id"),
        "logical_job_id": value.get("logical_job_id"),
        "policy_digest": value.get("policy_digest"),
        "state_sequence": value.get("state_sequence"),
        "event_digest": value.get("event_digest"),
        "previous_claim_digest": value.get("previous_claim_digest"),
    }
    return _canonical_digest(semantic)


def budget_id_for(logical_job_id: str) -> str:
    _identifier(logical_job_id, "logical_job_id")
    digest = hashlib.sha256(logical_job_id.encode("utf-8")).hexdigest()
    return f"budget-{digest[:32]}"


@dataclass(frozen=True)
class ExecutionBudgetSpec:
    max_elapsed_ms: int | None = None
    max_execution_units: int | None = None

    @classmethod
    def from_input(cls, value: Any) -> "ExecutionBudgetSpec":
        if not isinstance(value, Mapping):
            raise BudgetContractError("execution_budget must be an object")
        allowed = {"max_elapsed_ms", "max_execution_units"}
        unexpected = sorted(set(value) - allowed)
        if unexpected:
            raise BudgetContractError(
                "execution_budget contains unknown dimensions: " + ", ".join(unexpected)
            )
        if not value:
            raise BudgetContractError("execution_budget must configure at least one dimension")
        elapsed = (
            _bounded_integer(value["max_elapsed_ms"], "max_elapsed_ms", MAX_ELAPSED_MS)
            if "max_elapsed_ms" in value
            else None
        )
        units = (
            _bounded_integer(
                value["max_execution_units"],
                "max_execution_units",
                MAX_EXECUTION_UNITS,
            )
            if "max_execution_units" in value
            else None
        )
        return cls(elapsed, units)


@dataclass(frozen=True)
class BudgetBinding:
    budget_id: str
    logical_job_id: str
    policy_digest: str

    @classmethod
    def from_dict(cls, value: Any) -> "BudgetBinding":
        if not isinstance(value, Mapping):
            raise BudgetContractError("execution_budget binding must be an object")
        expected = {"budget_id", "logical_job_id", "policy_digest"}
        if set(value) != expected:
            raise BudgetContractError(
                "execution_budget binding must contain only budget_id, logical_job_id, and policy_digest"
            )
        budget_id = _identifier(value.get("budget_id"), "budget_id")
        logical_job_id = _identifier(value.get("logical_job_id"), "logical_job_id")
        digest = value.get("policy_digest")
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            raise BudgetContractError("policy_digest must be a SHA-256 digest")
        if budget_id != budget_id_for(logical_job_id):
            raise BudgetContractError("budget_id does not match the logical job identity")
        return cls(budget_id, logical_job_id, digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "logical_job_id": self.logical_job_id,
            "policy_digest": self.policy_digest,
        }


@dataclass(frozen=True)
class BudgetPolicy:
    budget_id: str
    logical_job_id: str
    policy_version: int
    max_elapsed_ms: int | None
    max_execution_units: int | None
    created_at: str
    digest: str

    @classmethod
    def create(
        cls,
        logical_job_id: str,
        spec: ExecutionBudgetSpec,
        *,
        created_at: str,
    ) -> "BudgetPolicy":
        logical_job_id = _identifier(logical_job_id, "logical_job_id")
        parse_timestamp(created_at, "created_at")
        values: dict[str, Any] = {
            "schema_version": 1,
            "budget_id": budget_id_for(logical_job_id),
            "logical_job_id": logical_job_id,
            "policy_version": POLICY_VERSION,
            "max_elapsed_ms": spec.max_elapsed_ms,
            "max_execution_units": spec.max_execution_units,
            "created_at": created_at,
        }
        digest = policy_digest(values)
        return cls(
            values["budget_id"],
            logical_job_id,
            POLICY_VERSION,
            spec.max_elapsed_ms,
            spec.max_execution_units,
            created_at,
            digest,
        )

    @classmethod
    def from_dict(cls, value: Any) -> "BudgetPolicy":
        if not isinstance(value, Mapping):
            raise BudgetContractError("budget policy must be an object")
        expected = {
            "schema_version",
            "budget_id",
            "logical_job_id",
            "policy_version",
            "max_elapsed_ms",
            "max_execution_units",
            "created_at",
            "policy_digest",
        }
        if set(value) != expected:
            raise BudgetContractError("budget policy fields do not match the canonical contract")
        if value.get("schema_version") != 1 or value.get("policy_version") != POLICY_VERSION:
            raise BudgetContractError("unsupported budget policy version")
        binding = BudgetBinding.from_dict(
            {
                "budget_id": value.get("budget_id"),
                "logical_job_id": value.get("logical_job_id"),
                "policy_digest": value.get("policy_digest"),
            }
        )
        elapsed = value.get("max_elapsed_ms")
        units = value.get("max_execution_units")
        if elapsed is not None:
            elapsed = _bounded_integer(elapsed, "max_elapsed_ms", MAX_ELAPSED_MS)
        if units is not None:
            units = _bounded_integer(units, "max_execution_units", MAX_EXECUTION_UNITS)
        if elapsed is None and units is None:
            raise BudgetContractError("budget policy must enable at least one dimension")
        created_at = value.get("created_at")
        parse_timestamp(created_at, "created_at")
        expected_digest = policy_digest(value)
        if binding.policy_digest != expected_digest:
            raise BudgetContractError("budget policy digest does not match its immutable content")
        return cls(
            binding.budget_id,
            binding.logical_job_id,
            POLICY_VERSION,
            elapsed,
            units,
            created_at,
            expected_digest,
        )

    @property
    def binding(self) -> BudgetBinding:
        return BudgetBinding(self.budget_id, self.logical_job_id, self.digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "budget_id": self.budget_id,
            "logical_job_id": self.logical_job_id,
            "policy_version": self.policy_version,
            "max_elapsed_ms": self.max_elapsed_ms,
            "max_execution_units": self.max_execution_units,
            "created_at": self.created_at,
            "policy_digest": self.digest,
        }


@dataclass(frozen=True)
class BudgetUsageAnchor:
    budget_id: str
    logical_job_id: str
    policy_digest: str
    state_sequence: int
    consumed_execution_units: int
    consumed_elapsed_ms: int
    reservation_count: int
    reservation_history_digest: str
    state_digest: str
    previous_anchor_digest: str | None
    digest: str

    @classmethod
    def create(
        cls,
        policy: BudgetPolicy,
        state: Mapping[str, Any],
        *,
        previous_anchor_digest: str | None,
    ) -> "BudgetUsageAnchor":
        values = {
            "schema_version": 1,
            "budget_id": policy.budget_id,
            "logical_job_id": policy.logical_job_id,
            "policy_digest": policy.digest,
            "state_sequence": state.get("state_sequence"),
            "consumed_execution_units": state.get("consumed_execution_units"),
            "consumed_elapsed_ms": state.get("consumed_elapsed_ms"),
            "reservation_count": len(state.get("reservations", [])),
            "reservation_history_digest": reservation_history_digest(
                state.get("reservations", [])
            ),
            "state_digest": budget_state_digest(state),
            "previous_anchor_digest": previous_anchor_digest,
        }
        values["anchor_digest"] = usage_anchor_digest(values)
        return cls.from_dict(values)

    @classmethod
    def from_dict(cls, value: Any) -> "BudgetUsageAnchor":
        if not isinstance(value, Mapping):
            raise BudgetContractError("budget usage anchor must be an object")
        expected = {
            "schema_version",
            "budget_id",
            "logical_job_id",
            "policy_digest",
            "state_sequence",
            "consumed_execution_units",
            "consumed_elapsed_ms",
            "reservation_count",
            "reservation_history_digest",
            "state_digest",
            "previous_anchor_digest",
            "anchor_digest",
        }
        if set(value) != expected or value.get("schema_version") != 1:
            raise BudgetContractError(
                "budget usage anchor fields do not match the canonical contract"
            )
        budget_id = _identifier(value.get("budget_id"), "budget_id")
        logical_job_id = _identifier(value.get("logical_job_id"), "logical_job_id")
        policy_value = value.get("policy_digest")
        if not isinstance(policy_value, str) or _DIGEST.fullmatch(policy_value) is None:
            raise BudgetContractError("policy_digest must be a SHA-256 digest")
        sequence = _bounded_integer(
            value.get("state_sequence"), "state_sequence", MAX_STATE_SEQUENCE
        )
        units = _bounded_integer(
            value.get("consumed_execution_units"),
            "consumed_execution_units",
            MAX_EXECUTION_UNITS,
        )
        elapsed = _bounded_integer(
            value.get("consumed_elapsed_ms"),
            "consumed_elapsed_ms",
            MAX_STATE_SEQUENCE,
        )
        reservation_count = _bounded_integer(
            value.get("reservation_count"),
            "reservation_count",
            MAX_EXECUTION_UNITS,
        )
        history_digest = value.get("reservation_history_digest")
        state_value = value.get("state_digest")
        previous = value.get("previous_anchor_digest")
        digest = value.get("anchor_digest")
        for name, candidate in (
            ("reservation_history_digest", history_digest),
            ("state_digest", state_value),
            ("anchor_digest", digest),
        ):
            if not isinstance(candidate, str) or _DIGEST.fullmatch(candidate) is None:
                raise BudgetContractError(f"{name} must be a SHA-256 digest")
        if previous is not None and (
            not isinstance(previous, str) or _DIGEST.fullmatch(previous) is None
        ):
            raise BudgetContractError(
                "previous_anchor_digest must be null or a SHA-256 digest"
            )
        expected_digest = usage_anchor_digest(value)
        if digest != expected_digest:
            raise BudgetContractError(
                "budget usage anchor digest does not match its canonical content"
            )
        return cls(
            budget_id,
            logical_job_id,
            policy_value,
            sequence,
            units,
            elapsed,
            reservation_count,
            history_digest,
            state_value,
            previous,
            expected_digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "budget_id": self.budget_id,
            "logical_job_id": self.logical_job_id,
            "policy_digest": self.policy_digest,
            "state_sequence": self.state_sequence,
            "consumed_execution_units": self.consumed_execution_units,
            "consumed_elapsed_ms": self.consumed_elapsed_ms,
            "reservation_count": self.reservation_count,
            "reservation_history_digest": self.reservation_history_digest,
            "state_digest": self.state_digest,
            "previous_anchor_digest": self.previous_anchor_digest,
            "anchor_digest": self.digest,
        }


@dataclass(frozen=True)
class BudgetUsageClaim:
    """Write-once sequence claim binding one content-addressed usage event."""

    budget_id: str
    logical_job_id: str
    policy_digest: str
    state_sequence: int
    event_digest: str
    previous_claim_digest: str | None
    digest: str

    @classmethod
    def create(
        cls,
        policy: BudgetPolicy,
        anchor: BudgetUsageAnchor,
        *,
        previous_claim_digest: str | None,
    ) -> "BudgetUsageClaim":
        values = {
            "schema_version": 1,
            "budget_id": policy.budget_id,
            "logical_job_id": policy.logical_job_id,
            "policy_digest": policy.digest,
            "state_sequence": anchor.state_sequence,
            "event_digest": anchor.digest,
            "previous_claim_digest": previous_claim_digest,
        }
        values["claim_digest"] = usage_claim_digest(values)
        return cls.from_dict(values)

    @classmethod
    def from_dict(cls, value: Any) -> "BudgetUsageClaim":
        if not isinstance(value, Mapping):
            raise BudgetContractError("budget usage claim must be an object")
        expected = {
            "schema_version",
            "budget_id",
            "logical_job_id",
            "policy_digest",
            "state_sequence",
            "event_digest",
            "previous_claim_digest",
            "claim_digest",
        }
        if set(value) != expected or value.get("schema_version") != 1:
            raise BudgetContractError(
                "budget usage claim fields do not match the canonical contract"
            )
        budget_id = _identifier(value.get("budget_id"), "budget_id")
        logical_job_id = _identifier(value.get("logical_job_id"), "logical_job_id")
        policy_value = value.get("policy_digest")
        sequence = _bounded_integer(
            value.get("state_sequence"), "state_sequence", MAX_STATE_SEQUENCE
        )
        event_digest = value.get("event_digest")
        previous = value.get("previous_claim_digest")
        digest = value.get("claim_digest")
        for name, candidate in (
            ("policy_digest", policy_value),
            ("event_digest", event_digest),
            ("claim_digest", digest),
        ):
            if not isinstance(candidate, str) or _DIGEST.fullmatch(candidate) is None:
                raise BudgetContractError(f"{name} must be a SHA-256 digest")
        if previous is not None and (
            not isinstance(previous, str) or _DIGEST.fullmatch(previous) is None
        ):
            raise BudgetContractError(
                "previous_claim_digest must be null or a SHA-256 digest"
            )
        expected_digest = usage_claim_digest(value)
        if digest != expected_digest:
            raise BudgetContractError(
                "budget usage claim digest does not match its canonical content"
            )
        return cls(
            budget_id,
            logical_job_id,
            policy_value,
            sequence,
            event_digest,
            previous,
            expected_digest,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "budget_id": self.budget_id,
            "logical_job_id": self.logical_job_id,
            "policy_digest": self.policy_digest,
            "state_sequence": self.state_sequence,
            "event_digest": self.event_digest,
            "previous_claim_digest": self.previous_claim_digest,
            "claim_digest": self.digest,
        }


@dataclass(frozen=True)
class BudgetDecision:
    status: str
    reason: str
    state: dict[str, Any]
    reservation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "status": self.status,
            "reason": self.reason,
            "state": json.loads(json.dumps(self.state, allow_nan=False)),
        }
        if self.reservation is not None:
            value["reservation"] = json.loads(
                json.dumps(self.reservation, allow_nan=False)
            )
        return value
