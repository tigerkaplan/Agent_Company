"""Provider-neutral human approval contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any

from runtime.actions.models import EXECUTION_MODES, ExecutionScope, ScopeContractError
from runtime.git.models import GitContractError, commit_authorization_fingerprint
from runtime.git.remote_models import REMOTE_ACTIONS, remote_authorization_fingerprint

APPROVAL_STATUSES = {"PENDING", "APPROVED", "REJECTED"}
REQUESTED_ACTIONS = {
    "SET_LEARNING_DISPOSITION",
    "EXECUTE_JOB",
    "COMPLETE_REVIEWED_JOB",
    "RESOLVE_HUMAN_CONDITION",
    "COMMIT_CHANGE_SET",
    *REMOTE_ACTIONS,
}
RISK_LEVELS = {"low", "medium", "high", "approval_required"}
REF_TYPES = {
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


def approval_boundary_id(
    job_id: str,
    execution_id: str | None,
    review_id: str | None,
    requested_action: str,
    authorization_fingerprint: str,
) -> str:
    """Return the deterministic identity of one exact approval boundary."""
    boundary = json.dumps(
        [
            job_id,
            execution_id,
            review_id,
            requested_action,
            authorization_fingerprint,
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(boundary.encode("utf-8")).hexdigest()[:32]
    return f"approval-{digest}"


class ApprovalContractError(ValueError):
    """Raised when approval state violates the canonical contract."""


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    job_id: str
    execution_id: str | None
    review_id: str | None
    status: str
    reason: str
    risk_level: str
    requested_action: str
    evidence_refs: tuple[dict[str, Any], ...]
    requested_at: str
    execution_mode: str
    execution_scope: dict[str, Any] | None
    authorization_fingerprint: str
    commit_scope: dict[str, Any] | None = None
    remote_scope: dict[str, Any] | None = None
    dry_run: bool = False
    resolved_at: str | None = None
    decision_reason: str | None = None
    decided_by: str | None = None
    decision_actor_type: str | None = None
    learning_scope: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.requested_action != "SET_LEARNING_DISPOSITION" and self.learning_scope is not None:
            raise ApprovalContractError("Existing approval actions cannot contain learning scope")
        if not self.approval_id or not self.job_id or not self.requested_at:
            raise ApprovalContractError("Approval request IDs and timestamp are required")
        if self.status not in APPROVAL_STATUSES:
            raise ApprovalContractError("Approval status is not canonical")
        if self.requested_action not in REQUESTED_ACTIONS:
            raise ApprovalContractError("Requested approval action is not canonical")
        if self.risk_level not in RISK_LEVELS:
            raise ApprovalContractError("Approval risk level is not canonical")
        if self.execution_mode not in EXECUTION_MODES:
            raise ApprovalContractError("Approval execution mode is not canonical")
        if not isinstance(self.dry_run, bool):
            raise ApprovalContractError("Approval dry_run must be a boolean")
        if (
            len(self.authorization_fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in self.authorization_fingerprint)
        ):
            raise ApprovalContractError("Approval authorization fingerprint is invalid")
        if self.execution_mode == "READ_ONLY" and self.execution_scope is not None:
            raise ApprovalContractError("READ_ONLY approval cannot contain write scope")
        if self.execution_mode == "CONTROLLED_WRITE":
            try:
                scope = ExecutionScope.from_dict(self.execution_scope or {})
            except ScopeContractError as error:
                raise ApprovalContractError(str(error)) from error
            if scope.dry_run != self.dry_run:
                raise ApprovalContractError(
                    "Approval execution scope dry_run must match the request"
                )
        if not self.reason.strip() or len(self.reason) > 2000:
            raise ApprovalContractError("Approval reason is invalid")
        if len(self.evidence_refs) > 64:
            raise ApprovalContractError("Approval evidence exceeds the bounded limit")
        for reference in self.evidence_refs:
            if (
                set(reference) - {"ref_type", "ref", "description"}
                or reference.get("ref_type") not in REF_TYPES
                or not isinstance(reference.get("ref"), str)
                or not reference["ref"]
                or (
                    "description" in reference
                    and not isinstance(reference["description"], str)
                )
            ):
                raise ApprovalContractError("Approval evidence reference is invalid")
        if self.requested_action == "EXECUTE_JOB":
            if self.execution_id is not None or self.review_id is not None:
                raise ApprovalContractError(
                    "Pre-execution approval cannot bind execution or review IDs"
                )
            if self.commit_scope is not None:
                raise ApprovalContractError("Execution approval cannot contain commit scope")
            if self.remote_scope is not None:
                raise ApprovalContractError("Execution approval cannot contain remote scope")
        elif self.requested_action == "COMPLETE_REVIEWED_JOB":
            if not self.execution_id or not self.review_id:
                raise ApprovalContractError(
                    "Reviewed completion approval requires execution and review IDs"
                )
            if self.commit_scope is not None:
                raise ApprovalContractError("Review approval cannot contain commit scope")
            if self.remote_scope is not None:
                raise ApprovalContractError("Review approval cannot contain remote scope")
        elif self.requested_action == "RESOLVE_HUMAN_CONDITION":
            if not self.execution_id or self.review_id is not None:
                raise ApprovalContractError(
                    "Human-condition resolution requires one execution and no review"
                )
            if self.commit_scope is not None or self.remote_scope is not None:
                raise ApprovalContractError(
                    "Human-condition resolution cannot contain Git authority"
                )
        elif self.requested_action == "SET_LEARNING_DISPOSITION":
            from runtime.memory.learning import LearningScope, learning_fingerprint
            try:
                scope = LearningScope.from_dict(self.learning_scope).to_dict()
                if (not self.execution_id or not self.review_id or self.execution_mode != "READ_ONLY"
                        or self.execution_scope is not None or self.dry_run
                        or self.commit_scope is not None or self.remote_scope is not None
                        or scope["preparation"]["job_id"] != self.job_id
                        or scope["preparation"]["execution_id"] != self.execution_id
                        or scope["review"]["review_id"] != self.review_id
                        or learning_fingerprint(scope) != self.authorization_fingerprint
                        or self.approval_id != approval_boundary_id(self.job_id, self.execution_id,
                            self.review_id, self.requested_action, self.authorization_fingerprint)):
                    raise ApprovalContractError("Learning approval bindings are invalid")
            except (ValueError, TypeError, KeyError) as error:
                raise ApprovalContractError("Invalid exact learning scope") from error
        elif not self.execution_id or not self.review_id:
            raise ApprovalContractError(
                "Post-completion approval requires execution and review IDs"
            )
        elif self.requested_action == "COMMIT_CHANGE_SET":
            if self.execution_mode != "CONTROLLED_WRITE" or self.dry_run:
                raise ApprovalContractError(
                    "Commit approval requires non-dry-run CONTROLLED_WRITE"
                )
            try:
                fingerprint = commit_authorization_fingerprint(self.commit_scope or {})
            except GitContractError as error:
                raise ApprovalContractError(str(error)) from error
            if fingerprint != self.authorization_fingerprint:
                raise ApprovalContractError("Commit approval fingerprint is invalid")
            if self.remote_scope is not None:
                raise ApprovalContractError("Commit approval cannot contain remote scope")
        else:
            if self.execution_mode != "CONTROLLED_WRITE" or self.dry_run:
                raise ApprovalContractError(
                    "Remote approval requires non-dry-run CONTROLLED_WRITE"
                )
            if self.commit_scope is not None:
                raise ApprovalContractError("Remote approval cannot contain commit scope")
            try:
                fingerprint = remote_authorization_fingerprint(
                    self.requested_action, self.remote_scope or {}
                )
            except GitContractError as error:
                raise ApprovalContractError(str(error)) from error
            if fingerprint != self.authorization_fingerprint:
                raise ApprovalContractError("Remote approval fingerprint is invalid")

        resolution = (
            self.resolved_at,
            self.decided_by,
            self.decision_actor_type,
        )
        if self.status == "PENDING" and any(
            value is not None for value in (*resolution, self.decision_reason)
        ):
            raise ApprovalContractError("Pending approval cannot contain resolution data")
        if self.status != "PENDING":
            if any(value is None for value in resolution):
                raise ApprovalContractError("Resolved approval requires complete audit data")
            if not str(self.resolved_at).strip() or not str(self.decided_by).strip():
                raise ApprovalContractError("Resolved approval audit data is empty")
            if self.decision_actor_type != "local_operator":
                raise ApprovalContractError(
                    "Approval decisions must identify the local operator boundary"
                )
            if len(str(self.decided_by)) > 200:
                raise ApprovalContractError("Approval actor exceeds the bounded limit")
        if self.decision_reason is not None and len(self.decision_reason) > 2000:
            raise ApprovalContractError("Decision reason exceeds the bounded limit")

    def resolve(
        self,
        decision: str,
        *,
        decided_by: str,
        resolved_at: str,
        reason: str | None,
    ) -> ApprovalRequest:
        if self.status != "PENDING":
            raise ApprovalContractError(
                f"Approval is already resolved as {self.status}"
            )
        if decision not in {"APPROVED", "REJECTED"}:
            raise ApprovalContractError("Approval decision must be APPROVED or REJECTED")
        return replace(
            self,
            status=decision,
            resolved_at=resolved_at,
            decision_reason=reason,
            decided_by=decided_by,
            decision_actor_type="local_operator",
        )

    def to_dict(self) -> dict[str, Any]:
        if self.requested_action == "SET_LEARNING_DISPOSITION":
            self.__post_init__()
        value = {
            "schema_version": 1,
            "approval_id": self.approval_id,
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "review_id": self.review_id,
            "status": self.status,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "requested_action": self.requested_action,
            "evidence_refs": deepcopy(list(self.evidence_refs)),
            "requested_at": self.requested_at,
            "execution_mode": self.execution_mode,
            "execution_scope": deepcopy(self.execution_scope),
            "authorization_fingerprint": self.authorization_fingerprint,
            "commit_scope": deepcopy(self.commit_scope),
            "remote_scope": deepcopy(self.remote_scope),
            "dry_run": self.dry_run,
            "resolved_at": self.resolved_at,
            "decision_reason": self.decision_reason,
            "decided_by": self.decided_by,
            "decision_actor_type": self.decision_actor_type,
        }
        if self.requested_action == "SET_LEARNING_DISPOSITION":
            value["learning_scope"] = deepcopy(self.learning_scope)
        return value

    def compact(self) -> dict[str, Any]:
        """Canonical projection embedded in a job; never standalone authority."""
        if self.requested_action == "SET_LEARNING_DISPOSITION":
            raise ApprovalContractError("Learning disposition cannot enter compact job approval")
        return {"approval_id": self.approval_id, "requested_action": self.requested_action,
                "execution_id": self.execution_id, "review_id": self.review_id,
                "status": self.status, "recorded_at": self.resolved_at,
                "recorded_by": self.decided_by, "actor_type": self.decision_actor_type,
                "authorization_fingerprint": self.authorization_fingerprint}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ApprovalRequest:
        expected = {
            "schema_version",
            "approval_id",
            "job_id",
            "execution_id",
            "review_id",
            "status",
            "reason",
            "risk_level",
            "requested_action",
            "evidence_refs",
            "requested_at",
            "execution_mode",
            "execution_scope",
            "authorization_fingerprint",
            "resolved_at",
            "decision_reason",
            "decided_by",
            "decision_actor_type",
        }
        optional = {"dry_run", "commit_scope", "remote_scope"}
        if value.get("requested_action") == "SET_LEARNING_DISPOSITION":
            expected.add("learning_scope")
        elif "learning_scope" in value:
            raise ApprovalContractError("Existing approval bytes cannot accept learning scope")
        if (
            not set(value).issubset(expected | optional)
            or not expected.issubset(value)
            or type(value.get("schema_version")) is not int or value.get("schema_version") != 1
        ):
            raise ApprovalContractError("Approval record has invalid fields or version")
        string_fields = (
            "approval_id",
            "job_id",
            "status",
            "reason",
            "risk_level",
            "requested_action",
            "requested_at",
            "execution_mode",
            "authorization_fingerprint",
        )
        if any(not isinstance(value.get(field), str) for field in string_fields):
            raise ApprovalContractError("Approval record has invalid string fields")
        nullable_strings = (
            "execution_id",
            "review_id",
            "resolved_at",
            "decision_reason",
            "decided_by",
            "decision_actor_type",
        )
        if any(
            item is not None and not isinstance(item, str)
            for item in (value.get(field) for field in nullable_strings)
        ):
            raise ApprovalContractError("Approval record has invalid nullable fields")
        evidence_refs = value.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not all(
            isinstance(reference, dict) for reference in evidence_refs
        ):
            raise ApprovalContractError("Approval evidence references are invalid")
        return cls(
            approval_id=value["approval_id"],
            job_id=value["job_id"],
            execution_id=value["execution_id"],
            review_id=value["review_id"],
            status=value["status"],
            reason=value["reason"],
            risk_level=value["risk_level"],
            requested_action=value["requested_action"],
            evidence_refs=tuple(deepcopy(evidence_refs)),
            requested_at=value["requested_at"],
            execution_mode=value["execution_mode"],
            execution_scope=deepcopy(value["execution_scope"]),
            authorization_fingerprint=value["authorization_fingerprint"],
            commit_scope=deepcopy(value.get("commit_scope")),
            remote_scope=deepcopy(value.get("remote_scope")),
            dry_run=value.get("dry_run", False),
            resolved_at=value["resolved_at"],
            decision_reason=value["decision_reason"],
            decided_by=value["decided_by"],
            decision_actor_type=value["decision_actor_type"],
            learning_scope=deepcopy(value.get("learning_scope")),
        )


@dataclass(frozen=True)
class ApprovalRun:
    request: ApprovalRequest
    artifact_ref: dict[str, Any]
    job: dict[str, Any] | None = None
