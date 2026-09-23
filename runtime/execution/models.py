"""JSON-serializable provider-neutral execution contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from runtime.actions.models import EXECUTION_MODES, ExecutionScope, ScopeContractError


class ExecutionContractError(ValueError):
    """Raised when an execution request or result violates its contract."""


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
    output_refs: tuple[dict[str, Any], ...]
    summary: str | None
    error: dict[str, Any] | None
    provider: str | None
    started_at: str
    completed_at: str
    requested_provider: str | None = None
    preferred_provider: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    execution_mode: str = "READ_ONLY"
    dry_run: bool = False

    def __post_init__(self) -> None:
        if not self.execution_id or not self.job_id:
            raise ExecutionContractError("ExecutionResult IDs must be non-empty")
        if self.status not in {"succeeded", "failed"}:
            raise ExecutionContractError(
                "ExecutionResult.status must be 'succeeded' or 'failed'"
            )
        if self.status == "failed" and not self.error:
            raise ExecutionContractError("Failed ExecutionResult requires an error")
        if not self.started_at or not self.completed_at:
            raise ExecutionContractError("ExecutionResult timestamps must be non-empty")
        if self.execution_mode not in EXECUTION_MODES:
            raise ExecutionContractError("ExecutionResult.execution_mode is not canonical")
        if not isinstance(self.dry_run, bool):
            raise ExecutionContractError("ExecutionResult.dry_run must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "status": self.status,
            "output_refs": deepcopy(list(self.output_refs)),
            "summary": self.summary,
            "error": deepcopy(self.error),
            "provider": self.provider,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "requested_provider": self.requested_provider,
            "preferred_provider": self.preferred_provider,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "execution_mode": self.execution_mode,
            "dry_run": self.dry_run,
        }
