"""RemoteCommandService for the transport-independent Phase 7 core."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError, utc_now
from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.remote.config import RemoteRuntimeConfig
from runtime.remote.models import (
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
        if existing is not None:
            return self._duplicate_or_conflict(
                normalized,
                existing,
                fingerprint,
                idempotency_fingerprint,
                actor_ref,
            )
        existing = self.store.find_by_idempotency_key(normalized.idempotency_key)
        if existing is not None:
            return self._duplicate_or_conflict(
                normalized,
                existing,
                fingerprint,
                idempotency_fingerprint,
                actor_ref,
            )

        if not identity.authenticated or not identity.authorized or not identity.mapped_human_identity:
            result = self._result(
                normalized.command_id,
                RemoteResultStatus.REJECTED,
                "authorization",
                "Remote identity is not authorized",
                error_code="unauthorized",
            )
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
            self._audit(
                normalized,
                identity,
                fingerprint,
                idempotency_fingerprint,
                result,
                authorization_result="rejected",
            )
            return result

        try:
            result = self._dispatch(normalized, identity)
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
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        handlers = {
            RemoteCommandType.STATUS: self._status,
            RemoteCommandType.JOBS_LIST: self._jobs_list,
            RemoteCommandType.JOB_SHOW: self._job_show,
            RemoteCommandType.APPROVALS_LIST: self._approvals_list,
            RemoteCommandType.APPROVE: self._approve,
            RemoteCommandType.REJECT: self._reject,
        }
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
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        approvals = [
            self._approval_summary(item)
            for item in self.approvals.list("PENDING")[:50]
        ]
        return self._result(
            command.command_id,
            RemoteResultStatus.ACCEPTED,
            "approvals_list",
            "Remote approvals list loaded",
            data_refs={"approvals": approvals, "count": len(approvals)},
        )

    def _approve(
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        return self._resolve_approval(command, identity, decision="APPROVED")

    def _reject(
        self, command: RemoteCommand, identity: RemoteIdentity
    ) -> RemoteCommandResult:
        return self._resolve_approval(command, identity, decision="REJECTED")

    def _resolve_approval(
        self, command: RemoteCommand, identity: RemoteIdentity, *, decision: str
    ) -> RemoteCommandResult:
        if not command.approval_id:
            raise RemoteCommandError(f"{command.command_type.value} requires approval_id")
        if not command.authorization_fingerprint:
            raise RemoteCommandError(
                f"{command.command_type.value} requires authorization_fingerprint"
            )
        if self._expired(command):
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                "Remote approval interaction is expired",
                error_code="remote_interaction_expired",
                data_refs={"approval_id": command.approval_id},
            )
        try:
            shown = self.approvals.show(command.approval_id)
        except ApprovalRuntimeError as error:
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                str(error),
                error_code="approval_not_available",
                data_refs={"approval_id": command.approval_id},
            )
        approval = shown["approval"]
        if approval.get("status") != "PENDING":
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                f"Approval is already resolved as {approval.get('status')}",
                error_code="approval_not_pending",
                data_refs={"approval_id": command.approval_id},
            )
        if approval.get("authorization_fingerprint") != command.authorization_fingerprint:
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                "Remote approval fingerprint does not match current approval",
                error_code="authorization_fingerprint_mismatch",
                data_refs={"approval_id": command.approval_id},
            )
        try:
            resolved = self.approvals.resolve(
                command.approval_id,
                decision=decision,
                decided_by=str(identity.mapped_human_identity),
                reason=f"Remote {decision.lower()} via {identity.channel}",
            )
        except ApprovalRuntimeError as error:
            return self._result(
                command.command_id,
                RemoteResultStatus.REJECTED,
                "approval",
                str(error),
                error_code="approval_stale",
                data_refs={"approval_id": command.approval_id},
            )
        return self._result(
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

    def _expired(self, command: RemoteCommand) -> bool:
        issued = self._parse_time(command.issued_at)
        received = self._parse_time(command.received_at)
        return (received - issued).total_seconds() > self.config.approval_ttl_seconds

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
    ) -> RemoteCommandResult:
        if (
            (
                existing.get("command_fingerprint") == fingerprint
                or existing.get("idempotency_fingerprint") == idempotency_fingerprint
            )
            and existing.get("actor") == actor_ref
        ):
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

    def _audit(
        self,
        command: RemoteCommand,
        identity: RemoteIdentity,
        fingerprint: str,
        idempotency_fingerprint: str,
        result: RemoteCommandResult,
        *,
        authorization_result: str,
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
            "result": result.to_dict(),
        }
        try:
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
