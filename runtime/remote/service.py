"""RemoteCommandService for the transport-independent Phase 7 core."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from runtime.approvals.runtime import (
    ApprovalReconciliationRequired,
    ApprovalRuntime,
    ApprovalRuntimeError,
)
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError, utc_now
from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.remote.config import RemoteRuntimeConfig, RemoteUser
from runtime.remote.models import (
    COMMAND_PERMISSIONS,
    RemoteCommand,
    RemoteCommandError,
    RemoteCommandResult,
    RemoteCommandType,
    RemoteIdentity,
    RemoteResultStatus,
)
from runtime.remote.store import FileRemoteCommandStore, RemoteStoreError


class RemoteCommandServiceError(ValueError):
    """Raised when remote command handling cannot continue safely."""


class RemoteCommandService:
    def __init__(
        self,
        *,
        jobs: JobRuntime,
        approvals: ApprovalRuntime,
        store: FileRemoteCommandStore,
        config: RemoteRuntimeConfig | None = None,
        clock=utc_now,
    ) -> None:
        self.jobs = jobs
        self.approvals = approvals
        self.store = store
        self.config = config or RemoteRuntimeConfig.empty()
        self.clock = clock

    def handle(
        self,
        command: RemoteCommand | dict[str, Any],
        identity: RemoteIdentity,
    ) -> RemoteCommandResult:
        try:
            normalized = (
                command if isinstance(command, RemoteCommand) else RemoteCommand.from_dict(command)
            )
        except RemoteCommandError as error:
            command_id = str(command.get("command_id", "invalid-command")) if isinstance(command, dict) else "invalid-command"
            result = self._result(
                command_id,
                RemoteResultStatus.UNSUPPORTED,
                "unsupported_command",
                str(error),
                error_code="unsupported_command",
            )
            if isinstance(command, dict):
                self._audit_invalid(command, identity, result)
            return result

        fingerprint = self._command_fingerprint(normalized)
        idempotency_fingerprint = self._idempotency_fingerprint(normalized)
        actor_ref = identity.actor_ref
        existing = self.store.load(normalized.command_id)
        if existing is None:
            existing = self.store.find_by_idempotency_key(
                normalized.idempotency_key
            )

        remote_user = self.config.authorized_user(identity)
        if remote_user is None or not identity.mapped_human_identity:
            result = self._result(
                normalized.command_id,
                RemoteResultStatus.REJECTED,
                "authorization",
                "Remote identity is not authorized",
                error_code="unauthorized",
            )
            if existing is None:
                self._audit(
                    normalized,
                    identity,
                    fingerprint,
                    idempotency_fingerprint,
                    result,
                    authorization_result="rejected",
                )
            return result
        if normalized.channel != identity.channel or normalized.actor != identity.platform_user_id:
            result = self._result(
                normalized.command_id,
                RemoteResultStatus.REJECTED,
                "authorization",
                "Remote command actor does not match authenticated identity",
                error_code="actor_mismatch",
            )
            if existing is None:
                self._audit(
                    normalized,
                    identity,
                    fingerprint,
                    idempotency_fingerprint,
                    result,
                    authorization_result="rejected",
                )
            return result

        required_permission = COMMAND_PERMISSIONS[normalized.command_type]
        if required_permission not in remote_user.permissions:
            result = self._result(
                normalized.command_id,
                RemoteResultStatus.REJECTED,
                "authorization",
                "Remote identity lacks permission for this command",
                error_code="permission_denied",
            )
            if existing is None:
                self._audit(
                    normalized,
                    identity,
                    fingerprint,
                    idempotency_fingerprint,
                    result,
                    authorization_result="rejected",
                )
            return result

        if existing is not None:
            if not self._matching_replay(
                existing,
                fingerprint,
                idempotency_fingerprint,
                actor_ref,
            ):
                return self._duplicate_or_conflict(
                    normalized,
                    existing,
                    fingerprint,
                    idempotency_fingerprint,
                    actor_ref,
                    identity,
                )
            scope_error = self._replay_scope_error(
                normalized, remote_user, existing
            )
            if scope_error is not None:
                return scope_error
            return self._duplicate_or_conflict(
                normalized,
                existing,
                fingerprint,
                idempotency_fingerprint,
                actor_ref,
                identity,
            )

        if normalized.command_type in {
            RemoteCommandType.APPROVE,
            RemoteCommandType.REJECT,
        }:
            return self._handle_approval_mutation(
                normalized,
                identity,
                remote_user,
                fingerprint,
                idempotency_fingerprint,
            )

        try:
            result = self._dispatch(normalized, identity, remote_user)
        except (ApprovalRuntimeError, JobRuntimeError, RemoteCommandError) as error:
            result = self._result(
                normalized.command_id,
                RemoteResultStatus.REJECTED,
                "runtime",
                str(error),
                error_code="runtime_rejected",
            )
        except Exception as error:  # pragma: no cover - fail closed for unexpected errors.
            result = self._result(
                normalized.command_id,
                RemoteResultStatus.FAILED,
                "runtime",
                "Remote command failed",
                error_code=type(error).__name__,
            )
        self._audit(
            normalized,
            identity,
            fingerprint,
            idempotency_fingerprint,
            result,
            authorization_result="accepted",
        )
        return result

    def _dispatch(
        self,
        command: RemoteCommand,
        identity: RemoteIdentity,
        remote_user: RemoteUser,
    ) -> RemoteCommandResult:
        handlers = {
            RemoteCommandType.STATUS: self._status,
            RemoteCommandType.JOBS_LIST: self._jobs_list,
            RemoteCommandType.JOB_SHOW: self._job_show,
        }
        if command.command_type is RemoteCommandType.APPROVALS_LIST:
            return self._approvals_list(command, identity, remote_user)
        return handlers[command.command_type](command, identity)

    def _status(
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        jobs = self.jobs.list()
        approvals = self.approvals.list("PENDING")
        by_status: dict[str, int] = {}
        for job in jobs:
            status = str(job.get("status"))
            by_status[status] = by_status.get(status, 0) + 1
        return self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "status",
            "Remote runtime status loaded",
            data_refs={
                "checked_at": self.clock(),
                "jobs_total": len(jobs),
                "jobs_by_status": by_status,
                "pending_approvals": len(approvals),
                "actor": identity.mapped_human_identity,
            },
        )

    def _jobs_list(
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        jobs = [self._job_summary(job) for job in self.jobs.list()[:50]]
        return self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "jobs_list",
            "Remote jobs list loaded",
            data_refs={"jobs": jobs, "count": len(jobs)},
        )

    def _job_show(
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        if not command.target_id:
            raise RemoteCommandError("JOB_SHOW requires target_id")
        job = self.jobs.show(command.target_id)
        return self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "job_show",
            "Remote job loaded",
            data_refs={"job": self._job_summary(job, include_task=True)},
        )

    def _approvals_list(
        self,
        command: RemoteCommand,
        identity: RemoteIdentity,
        remote_user: RemoteUser,
    ) -> RemoteCommandResult:
        approvals = []
        for item in self.approvals.list("PENDING"):
            shown = self.approvals.show(str(item["approval_id"]))
            if remote_user.approval_scope.allows(item, shown["job"]):
                approvals.append(self._approval_summary(item))
            if len(approvals) == 50:
                break
        return self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "approvals_list",
            "Remote approvals list loaded",
            data_refs={"approvals": approvals, "count": len(approvals)},
        )

    def _handle_approval_mutation(
        self,
        command: RemoteCommand,
        identity: RemoteIdentity,
        remote_user: RemoteUser,
        fingerprint: str,
        idempotency_fingerprint: str,
    ) -> RemoteCommandResult:
        decision = (
            "APPROVED"
            if command.command_type is RemoteCommandType.APPROVE
            else "REJECTED"
        )
        validation, shown = self._validate_approval_command(
            command, remote_user
        )
        if validation is not None:
            self._audit(
                command,
                identity,
                fingerprint,
                idempotency_fingerprint,
                validation,
                authorization_result="accepted",
            )
            return validation

        intent = self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "approval_intent",
            "Remote approval command authorized before mutation",
            data_refs={"approval_id": command.approval_id},
        )
        self._audit(
            command,
            identity,
            fingerprint,
            idempotency_fingerprint,
            intent,
            authorization_result="accepted",
            audit_state="AUTHORIZED",
            mutation_state="not_started",
        )
        attempting = self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "approval_mutation",
            "Remote approval mutation is being attempted",
            data_refs={"approval_id": command.approval_id},
        )
        self._audit(
            command,
            identity,
            fingerprint,
            idempotency_fingerprint,
            attempting,
            authorization_result="accepted",
            audit_state="MUTATION_ATTEMPTED",
            mutation_state="attempted",
            update=True,
        )

        try:
            resolved = self.approvals.resolve(
                str(command.approval_id),
                decision=decision,
                decided_by=str(identity.mapped_human_identity),
                reason=f"Remote {decision.lower()} via {identity.channel}",
            )
        except ApprovalReconciliationRequired:
            result = self._result(
                command.command_id,
                RemoteResultStatus.FAILED,
                "approval_recovery",
                "Canonical approval resolution requires reconciliation",
                error_code="approval_reconciliation_required",
                data_refs={"approval_id": command.approval_id},
            )
            self._audit(
                command,
                identity,
                fingerprint,
                idempotency_fingerprint,
                result,
                authorization_result="accepted",
                audit_state="RECONCILIATION_REQUIRED",
                mutation_state="uncertain",
                update=True,
            )
            return result
        except ApprovalRuntimeError as error:
            result = self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                str(error),
                error_code="approval_stale",
                data_refs={"approval_id": command.approval_id},
            )
            self._audit(
                command,
                identity,
                fingerprint,
                idempotency_fingerprint,
                result,
                authorization_result="accepted",
                audit_state="FAILED",
                mutation_state="failed",
                update=True,
            )
            return result

        result = self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "approval",
            f"Remote approval {decision.lower()}",
            data_refs={
                "approval_id": command.approval_id,
                "approval_status": resolved["approval"]["status"],
                "job_id": resolved["approval"]["job_id"],
                "job_status": resolved["job"]["status"],
            },
        )
        self._audit(
            command,
            identity,
            fingerprint,
            idempotency_fingerprint,
            result,
            authorization_result="accepted",
            audit_state="COMPLETED",
            mutation_state="completed",
            update=True,
        )
        return result

    def _validate_approval_command(
        self, command: RemoteCommand, remote_user: RemoteUser
    ) -> tuple[RemoteCommandResult | None, dict[str, Any] | None]:
        if not command.approval_id:
            return (
                self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "approval",
                    f"{command.command_type.value} requires approval_id",
                    error_code="approval_id_required",
                ),
                None,
            )
        if not command.authorization_fingerprint:
            return (
                self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "approval",
                    f"{command.command_type.value} requires authorization_fingerprint",
                    error_code="authorization_fingerprint_required",
                ),
                None,
            )
        time_error = self._approval_time_error(command)
        if time_error is not None:
            return time_error, None
        try:
            shown = self.approvals.show(command.approval_id)
        except ApprovalRuntimeError as error:
            return (
                self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "approval",
                    str(error),
                    error_code="approval_not_available",
                    data_refs={"approval_id": command.approval_id},
                ),
                None,
            )
        approval = shown["approval"]
        if approval.get("status") != "PENDING":
            return (
                self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "approval",
                    f"Approval is already resolved as {approval.get('status')}",
                    error_code="approval_not_pending",
                    data_refs={"approval_id": command.approval_id},
                ),
                shown,
            )
        if approval.get("authorization_fingerprint") != command.authorization_fingerprint:
            return (
                self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "approval",
                    "Remote approval fingerprint does not match current approval",
                    error_code="authorization_fingerprint_mismatch",
                    data_refs={"approval_id": command.approval_id},
                ),
                shown,
            )
        if not remote_user.approval_scope.allows(approval, shown["job"]):
            return (
                self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "authorization",
                    "Remote identity is not authorized for this approval scope",
                    error_code="approval_scope_denied",
                    data_refs={"approval_id": command.approval_id},
                ),
                shown,
            )
        return None, shown

    def _approval_time_error(
        self, command: RemoteCommand
    ) -> RemoteCommandResult | None:
        issued = self._parse_time(command.issued_at)
        received = self._parse_time(command.received_at)
        age = (received - issued).total_seconds()
        if age < -self.config.allowed_clock_skew_seconds:
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                "Remote approval interaction was issued too far in the future",
                error_code="remote_interaction_future",
                data_refs={"approval_id": command.approval_id},
            )
        if age > self.config.approval_ttl_seconds:
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                "Remote approval interaction is expired",
                error_code="remote_interaction_expired",
                data_refs={"approval_id": command.approval_id},
            )
        return None

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise RemoteCommandError(f"Remote timestamp is invalid: {value}") from error
        if parsed.tzinfo is None:
            raise RemoteCommandError("Remote timestamp must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    def _duplicate_or_conflict(
        self,
        command: RemoteCommand,
        existing: dict[str, Any],
        fingerprint: str,
        idempotency_fingerprint: str,
        actor_ref: dict[str, Any],
        identity: RemoteIdentity,
    ) -> RemoteCommandResult:
        if self._matching_replay(
            existing,
            fingerprint,
            idempotency_fingerprint,
            actor_ref,
        ):
            if (
                existing.get("audit_state")
                in {"MUTATION_ATTEMPTED", "RECONCILIATION_REQUIRED"}
                and command.command_type
                in {RemoteCommandType.APPROVE, RemoteCommandType.REJECT}
            ):
                return self._reconcile_approval_mutation(
                    command, identity, existing
                )
            if existing.get("audit_state") == "AUTHORIZED":
                return self._result(
                    command.command_id,
                    RemoteResultStatus.FAILED,
                    "approval_recovery",
                    "Remote approval mutation has incomplete durable audit state",
                    data_refs={"approval_id": command.approval_id},
                    error_code="remote_mutation_incomplete",
                )
            prior = existing.get("result", {})
            return self._result(
                command.command_id,
                RemoteResultStatus.DUPLICATE,
                str(prior.get("result_type", "duplicate")),
                str(prior.get("message", "Duplicate remote command")),
                data_refs=deepcopy(prior.get("data_refs") or {}),
                error_code=prior.get("error_code"),
            )
        return self._result(
            command.command_id,
            RemoteResultStatus.REJECTED,
            "replay",
            "Remote command ID was already used for different content or actor",
            error_code="replay_conflict",
        )

    @staticmethod
    def _matching_replay(
        existing: dict[str, Any],
        fingerprint: str,
        idempotency_fingerprint: str,
        actor_ref: dict[str, Any],
    ) -> bool:
        return (
            existing.get("command_fingerprint") == fingerprint
            or existing.get("idempotency_fingerprint") == idempotency_fingerprint
        ) and existing.get("actor") == actor_ref

    def _replay_scope_error(
        self,
        command: RemoteCommand,
        remote_user: RemoteUser,
        existing: dict[str, Any],
    ) -> RemoteCommandResult | None:
        approval_ids: list[str] = []
        if command.command_type in {
            RemoteCommandType.APPROVE,
            RemoteCommandType.REJECT,
        }:
            if command.approval_id:
                approval_ids.append(command.approval_id)
        elif command.command_type is RemoteCommandType.APPROVALS_LIST:
            prior = existing.get("result", {})
            data_refs = prior.get("data_refs", {}) if isinstance(prior, dict) else {}
            summaries = data_refs.get("approvals", []) if isinstance(data_refs, dict) else []
            if not isinstance(summaries, list):
                summaries = []
            for summary in summaries:
                if isinstance(summary, dict) and isinstance(
                    summary.get("approval_id"), str
                ):
                    approval_ids.append(summary["approval_id"])
        else:
            return None

        for approval_id in approval_ids:
            try:
                shown = self.approvals.show(approval_id)
            except ApprovalRuntimeError:
                return self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "authorization",
                    "Current approval scope could not be verified",
                    error_code="approval_scope_denied",
                    data_refs={"approval_id": approval_id},
                )
            approval = shown["approval"]
            if (
                command.command_type
                in {RemoteCommandType.APPROVE, RemoteCommandType.REJECT}
                and approval.get("authorization_fingerprint")
                != command.authorization_fingerprint
            ) or not remote_user.approval_scope.allows(
                approval, shown["job"]
            ):
                return self._result(
                    command.command_id,
                    RemoteResultStatus.REJECTED,
                    "authorization",
                    "Remote identity is no longer authorized for this approval scope",
                    error_code="approval_scope_denied",
                    data_refs={"approval_id": approval_id},
                )
        return None

    def _reconcile_approval_mutation(
        self,
        command: RemoteCommand,
        identity: RemoteIdentity,
        existing: dict[str, Any],
    ) -> RemoteCommandResult:
        decision = (
            "APPROVED"
            if command.command_type is RemoteCommandType.APPROVE
            else "REJECTED"
        )
        try:
            shown = self.approvals.show(str(command.approval_id))
        except ApprovalRuntimeError:
            return self._result(
                command.command_id,
                RemoteResultStatus.FAILED,
                "approval_recovery",
                "Canonical approval state is unavailable for reconciliation",
                data_refs={"approval_id": command.approval_id},
                error_code="approval_reconciliation_required",
            )
        canonical_status = shown["approval"].get("status")
        if canonical_status == "PENDING":
            time_error = self._approval_time_error(command)
            if time_error is not None:
                self._finalize_recovery_failure(existing, time_error)
                return time_error
        try:
            resolved = self.approvals.reconcile(
                str(command.approval_id),
                decision=decision,
                decided_by=str(identity.mapped_human_identity),
                reason=f"Remote {decision.lower()} reconciliation via {identity.channel}",
            )
        except (ApprovalReconciliationRequired, ApprovalRuntimeError):
            return self._result(
                command.command_id,
                RemoteResultStatus.FAILED,
                "approval_recovery",
                "Canonical approval resolution requires reconciliation",
                data_refs={"approval_id": command.approval_id},
                error_code="approval_reconciliation_required",
            )

        stored_result = self._result(
            str(existing.get("command_id", command.command_id)),
            RemoteResultStatus.ACCEPTED,
            "approval",
            f"Remote approval {decision.lower()}",
            data_refs={
                "approval_id": command.approval_id,
                "approval_status": resolved["approval"]["status"],
                "job_id": resolved["approval"]["job_id"],
                "job_status": resolved["job"]["status"],
            },
        )
        completed = deepcopy(existing)
        completed["processed_at"] = stored_result.processed_at
        completed["audit_state"] = "COMPLETED"
        completed["mutation_state"] = "completed"
        completed["result"] = stored_result.to_dict()
        try:
            self.store.update(completed)
        except RemoteStoreError as error:
            raise RemoteCommandServiceError(str(error)) from error
        return self._result(
            command.command_id,
            RemoteResultStatus.DUPLICATE,
            "approval",
            f"Remote approval {decision.lower()} and reconciled",
            data_refs=deepcopy(stored_result.data_refs),
        )

    def _finalize_recovery_failure(
        self,
        existing: dict[str, Any],
        result: RemoteCommandResult,
    ) -> None:
        failed = deepcopy(existing)
        stored_result = result.to_dict()
        stored_result["command_id"] = str(
            existing.get("command_id", result.command_id)
        )
        failed["processed_at"] = result.processed_at
        failed["audit_state"] = "FAILED"
        failed["mutation_state"] = "failed"
        failed["result"] = stored_result
        try:
            self.store.update(failed)
        except RemoteStoreError as error:
            raise RemoteCommandServiceError(str(error)) from error

    def _audit(
        self,
        command: RemoteCommand,
        identity: RemoteIdentity,
        fingerprint: str,
        idempotency_fingerprint: str,
        result: RemoteCommandResult,
        *,
        authorization_result: str,
        audit_state: str = "COMPLETED",
        mutation_state: str = "not_applicable",
        update: bool = False,
    ) -> None:
        record = {
            "schema_version": 1,
            "command_id": command.command_id,
            "idempotency_key": command.idempotency_key,
            "command_fingerprint": fingerprint,
            "idempotency_fingerprint": idempotency_fingerprint,
            "channel": command.channel,
            "actor": identity.actor_ref,
            "command_type": command.command_type.value,
            "target": command.target_id,
            "approval_id": command.approval_id,
            "issued_at": command.issued_at,
            "received_at": command.received_at,
            "processed_at": result.processed_at,
            "authorization_result": authorization_result,
            "audit_state": audit_state,
            "mutation_state": mutation_state,
            "result": result.to_dict(),
        }
        try:
            if update:
                self.store.update(record)
            else:
                self.store.save(record)
        except RemoteStoreError as error:
            raise RemoteCommandServiceError(str(error)) from error

    def _audit_invalid(
        self,
        command: dict[str, Any],
        identity: RemoteIdentity,
        result: RemoteCommandResult,
    ) -> None:
        command_id = str(command.get("command_id", result.command_id))
        idempotency_key = str(command.get("idempotency_key", command_id))
        record = {
            "schema_version": 1,
            "command_id": command_id,
            "idempotency_key": idempotency_key,
            "command_fingerprint": self._digest(
                json.dumps(command, sort_keys=True, default=str, ensure_ascii=True)
            ),
            "idempotency_fingerprint": self._digest(
                json.dumps(
                    {
                        key: value
                        for key, value in command.items()
                        if key not in {"command_id", "received_at"}
                    },
                    sort_keys=True,
                    default=str,
                    ensure_ascii=True,
                )
            ),
            "channel": str(command.get("channel", "")),
            "actor": identity.actor_ref,
            "command_type": str(command.get("command_type", "")),
            "target": command.get("target_id"),
            "approval_id": command.get("approval_id"),
            "issued_at": command.get("issued_at"),
            "received_at": command.get("received_at"),
            "processed_at": result.processed_at,
            "authorization_result": "rejected",
            "audit_state": "COMPLETED",
            "mutation_state": "not_applicable",
            "result": result.to_dict(),
        }
        if self.store.load(command_id) is None:
            try:
                self.store.save(record)
            except RemoteStoreError as error:
                raise RemoteCommandServiceError(str(error)) from error

    def _result(
        self,
        command_id: str,
        status: RemoteResultStatus,
        result_type: str,
        message: str,
        *,
        data_refs: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> RemoteCommandResult:
        return RemoteCommandResult(
            command_id=command_id,
            status=status,
            result_type=result_type,
            message=message,
            data_refs=deepcopy(data_refs or {}),
            error_code=error_code,
            processed_at=self.clock(),
        )

    @staticmethod
    def _command_fingerprint(command: RemoteCommand) -> str:
        value = json.dumps(command.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return RemoteCommandService._digest(value)

    @staticmethod
    def _idempotency_fingerprint(command: RemoteCommand) -> str:
        value = command.to_dict()
        value.pop("command_id", None)
        value.pop("received_at", None)
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return RemoteCommandService._digest(encoded)

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _job_summary(job: dict[str, Any], *, include_task: bool = False) -> dict[str, Any]:
        keys = (
            "job_id",
            "status",
            "risk_level",
            "approval_status",
            "review_required",
            "attempt",
            "max_attempts",
            "created_at",
            "last_updated_at",
            "next_run_at",
        )
        summary = {key: job.get(key) for key in keys if key in job}
        if include_task:
            summary["task"] = bound_text(sanitize_provider_text(job.get("task")), 1000)
        return summary

    @staticmethod
    def _approval_summary(approval: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "approval_id",
            "job_id",
            "status",
            "risk_level",
            "requested_action",
            "requested_at",
            "authorization_fingerprint",
        )
        summary = {key: approval.get(key) for key in keys}
        summary["reason"] = bound_text(sanitize_provider_text(approval.get("reason")), 1000)
        return summary
