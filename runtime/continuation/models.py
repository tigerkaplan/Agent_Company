"""Deterministic CORE-02 continuation decisions and bounded checkpoints."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from runtime.execution.models import FrozenMapping


class ContinuationContractError(ValueError):
    """Raised when canonical continuation state is inconsistent."""


@dataclass(frozen=True)
class ContinuationDecision:
    """One inert policy decision; scheduling is performed by the runtime."""

    should_continue: bool
    reason: str
    remaining_work: tuple[str, ...]
    checkpoint: FrozenMapping | None
    next_step_id: str | None
    terminal: bool


class ContinuationPolicy:
    """Decide only from a persisted authorized plan and canonical gate state."""

    @classmethod
    def initialize(cls, job: dict[str, Any]) -> dict[str, Any] | None:
        plan = job.get("continuation_plan")
        if plan is None:
            return None
        steps = cls._steps(plan)
        if not steps:
            raise ContinuationContractError("Continuation plan must contain steps")
        first = steps[0]
        if first["task"] != job.get("task"):
            raise ContinuationContractError(
                "Initial job task must match the first authorized continuation step"
            )
        return {
            "logical_job_id": job["job_id"],
            "plan_id": plan["plan_id"],
            "plan_digest": continuation_plan_digest(plan),
            "sequence": 0,
            "current_step_id": first["step_id"],
            "completed_step_ids": [],
            "remaining_step_ids": [step["step_id"] for step in steps],
            "state": "active",
        }

    @classmethod
    def decide_execution(
        cls,
        job: dict[str, Any],
        *,
        result_status: str,
        execution_ref: str,
    ) -> ContinuationDecision:
        checkpoint = cls._checkpoint(job)
        if checkpoint is None:
            return ContinuationDecision(
                False,
                "no_authorized_continuation_plan",
                (),
                None,
                None,
                result_status in {"succeeded", "failed", "blocked"},
            )
        checkpoint["latest_execution_ref"] = execution_ref
        if result_status == "needs_review" or (
            result_status == "succeeded" and job.get("review_required") is True
        ):
            checkpoint["state"] = "waiting_review"
            return cls._waiting(checkpoint, "review_gate_required")
        if result_status == "needs_human":
            checkpoint["state"] = "waiting_human"
            return cls._waiting(checkpoint, "human_condition_required")
        if result_status == "blocked":
            checkpoint["state"] = "blocked"
            return cls._waiting(checkpoint, "execution_blocked")
        if result_status != "succeeded":
            checkpoint["state"] = "stopped"
            return cls._decision(
                False,
                "failed_execution_has_no_continuation_authority",
                checkpoint,
                None,
                True,
            )
        return cls._complete_current(checkpoint)

    @classmethod
    def decide_review(
        cls,
        job: dict[str, Any],
        *,
        decision: str,
        review_ref: str,
    ) -> ContinuationDecision:
        checkpoint = cls._checkpoint(job)
        if checkpoint is None:
            return ContinuationDecision(
                False,
                "no_authorized_continuation_plan",
                (),
                None,
                None,
                decision == "PASS",
            )
        checkpoint["latest_review_ref"] = review_ref
        if decision == "PASS":
            return cls._complete_current(checkpoint)
        if decision == "NEEDS_HUMAN":
            checkpoint["state"] = "waiting_human"
            return cls._waiting(checkpoint, "human_approval_required")
        checkpoint["state"] = "stopped"
        return cls._decision(
            False,
            "review_did_not_authorize_continuation",
            checkpoint,
            None,
            True,
        )

    @classmethod
    def decide_human_approval(cls, job: dict[str, Any]) -> ContinuationDecision:
        checkpoint = cls._checkpoint(job)
        if checkpoint is None:
            return ContinuationDecision(
                False, "no_authorized_continuation_plan", (), None, None, True
            )
        if checkpoint.get("state") != "waiting_human":
            raise ContinuationContractError(
                "Human approval does not match a waiting continuation checkpoint"
            )
        return cls._complete_current(checkpoint)

    @classmethod
    def decide_human_resume(cls, job: dict[str, Any]) -> ContinuationDecision:
        """Resume the exact incomplete step after a direct human condition is resolved."""
        checkpoint = cls._checkpoint(job)
        if checkpoint is None or checkpoint.get("state") != "waiting_human":
            raise ContinuationContractError(
                "Human resolution does not match a waiting continuation checkpoint"
            )
        checkpoint["state"] = "active"
        return cls._decision(
            False,
            "human_condition_resolved",
            checkpoint,
            None,
            False,
        )

    @classmethod
    def checkpoint_for_child(
        cls, parent: dict[str, Any], next_step_id: str
    ) -> dict[str, Any]:
        checkpoint = cls._checkpoint(parent)
        if checkpoint is None or checkpoint.get("state") != "ready":
            raise ContinuationContractError("Parent has no ready continuation checkpoint")
        if checkpoint.get("next_step_id") != next_step_id:
            raise ContinuationContractError("Continuation step does not match checkpoint")
        child = deepcopy(checkpoint)
        child["sequence"] = int(checkpoint["sequence"]) + 1
        child["current_step_id"] = next_step_id
        child["state"] = "active"
        child.pop("next_step_id", None)
        child.pop("latest_execution_ref", None)
        child.pop("latest_review_ref", None)
        return child

    @staticmethod
    def step(plan: dict[str, Any], step_id: str) -> dict[str, Any]:
        for step in ContinuationPolicy._steps(plan):
            if step["step_id"] == step_id:
                return deepcopy(step)
        raise ContinuationContractError("Continuation step is absent from authorized plan")

    @staticmethod
    def _steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
        steps = plan.get("steps") if isinstance(plan, dict) else None
        if not isinstance(steps, list):
            raise ContinuationContractError("Continuation plan steps must be a list")
        return steps

    @staticmethod
    def _checkpoint(job: dict[str, Any]) -> dict[str, Any] | None:
        value = job.get("continuation")
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ContinuationContractError("Continuation checkpoint must be an object")
        return deepcopy(value)

    @staticmethod
    def _waiting(checkpoint: dict[str, Any], reason: str) -> ContinuationDecision:
        return ContinuationPolicy._decision(False, reason, checkpoint, None, False)

    @staticmethod
    def _complete_current(checkpoint: dict[str, Any]) -> ContinuationDecision:
        current = checkpoint["current_step_id"]
        completed = list(checkpoint["completed_step_ids"])
        remaining = list(checkpoint["remaining_step_ids"])
        if current not in remaining:
            raise ContinuationContractError(
                "Current continuation step is not canonical remaining work"
            )
        if current not in completed:
            completed.append(current)
        remaining.remove(current)
        checkpoint["completed_step_ids"] = completed
        checkpoint["remaining_step_ids"] = remaining
        if not remaining:
            checkpoint["state"] = "terminal"
            checkpoint.pop("next_step_id", None)
            return ContinuationPolicy._decision(
                False, "all_authorized_work_complete", checkpoint, None, True
            )
        next_step = remaining[0]
        checkpoint["state"] = "ready"
        checkpoint["next_step_id"] = next_step
        return ContinuationPolicy._decision(
            True, "authorized_work_remains", checkpoint, next_step, False
        )

    @staticmethod
    def _decision(
        should_continue: bool,
        reason: str,
        checkpoint: dict[str, Any],
        next_step_id: str | None,
        terminal: bool,
    ) -> ContinuationDecision:
        return ContinuationDecision(
            should_continue,
            reason,
            tuple(checkpoint["remaining_step_ids"]),
            FrozenMapping(checkpoint),
            next_step_id,
            terminal,
        )


def continuation_plan_digest(plan: Any) -> str:
    """Hash the canonical JSON value of one authorized continuation plan."""
    if not isinstance(plan, dict):
        raise ContinuationContractError("Continuation plan must be an object")
    try:
        encoded = json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ContinuationContractError(
            "Continuation plan must contain canonical JSON values"
        ) from error
    return hashlib.sha256(encoded).hexdigest()
