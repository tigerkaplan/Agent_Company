"""Safe runtime-to-notification event bridge."""

from __future__ import annotations

from typing import Any

from runtime.core.jobs import utc_now
from runtime.notifications.models import (
    NotificationEvent,
    NotificationSeverity,
    NotificationType,
)
from runtime.notifications.service import NotificationService


class RuntimeNotificationEmitter:
    def __init__(
        self,
        service: NotificationService,
        target_human_identities: tuple[str, ...],
        *,
        clock=utc_now,
    ) -> None:
        self.service = service
        self.targets = tuple(dict.fromkeys(target_human_identities))
        self.clock = clock

    def approval_requested(
        self, approval: dict[str, Any], job: dict[str, Any]
    ) -> None:
        for target in self.targets:
            self._emit(
                NotificationEvent.create(
                    notification_type=NotificationType.APPROVAL_REQUESTED,
                    created_at=str(approval["requested_at"]),
                    target_human_identity=target,
                    source_type="approval",
                    source_id=str(approval["approval_id"]),
                    severity=NotificationSeverity.WARNING,
                    title="Approval required",
                    summary="A runtime operation is waiting for explicit human approval.",
                    approval_id=str(approval["approval_id"]),
                    authorization_fingerprint=str(
                        approval["authorization_fingerprint"]
                    ),
                    metadata={
                        "job_id": job.get("job_id"),
                        "requested_action": approval.get("requested_action"),
                        "risk_level": approval.get("risk_level"),
                    },
                )
            )

    def job_terminal(self, job: dict[str, Any]) -> None:
        status = str(job.get("status"))
        if status not in {"completed", "failed"}:
            return
        notification_type = (
            NotificationType.JOB_COMPLETED
            if status == "completed"
            else NotificationType.JOB_FAILED
        )
        severity = (
            NotificationSeverity.INFO
            if status == "completed"
            else NotificationSeverity.ERROR
        )
        error = job.get("error") if isinstance(job.get("error"), dict) else {}
        summary = (
            "Job completed successfully."
            if status == "completed"
            else "Job failed. Inspect the local runtime for bounded evidence."
        )
        for target in self.targets:
            self._emit(
                NotificationEvent.create(
                    notification_type=notification_type,
                    created_at=str(job["last_updated_at"]),
                    target_human_identity=target,
                    source_type="job",
                    source_id=str(job["job_id"]),
                    severity=severity,
                    title=("Job completed" if status == "completed" else "Job failed"),
                    summary=summary,
                    metadata={
                        "job_id": job.get("job_id"),
                        "task_class": job.get("task_class"),
                        "status": status,
                        "failure_category": error.get("code"),
                        "retryable": error.get("retryable"),
                        "attempt": job.get("attempt"),
                        "max_attempts": job.get("max_attempts"),
                    },
                )
            )

    def runtime_error(
        self,
        *,
        source_type: str,
        source_id: str,
        error_code: str,
    ) -> None:
        created_at = self.clock()
        cooldown_bucket = created_at[:13]
        for target in self.targets:
            self._emit(
                NotificationEvent.create(
                    notification_type=NotificationType.RUNTIME_ERROR,
                    created_at=created_at,
                    target_human_identity=target,
                    source_type=source_type,
                    source_id=source_id,
                    severity=NotificationSeverity.ERROR,
                    title="Runtime error",
                    summary=(
                        "The local runtime reported a meaningful operational error."
                    ),
                    metadata={
                        "error_code": error_code,
                        "cooldown_bucket": cooldown_bucket,
                    },
                    dedupe_key=f"{error_code}:{cooldown_bucket}",
                )
            )

    def _emit(self, event: NotificationEvent) -> None:
        try:
            self.service.emit(event)
        except Exception:
            # Notification persistence or transport must never control runtime state.
            return
