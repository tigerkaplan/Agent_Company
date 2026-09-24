"""Bounded human-readable Telegram formatting for remote results."""

from __future__ import annotations

from typing import Any

from runtime.remote.models import RemoteCommandResult, RemoteResultStatus
from runtime.notifications.models import NotificationEvent, NotificationType


TELEGRAM_MESSAGE_LIMIT = 4096
TRUNCATION_MARKER = "\n[response truncated]"


class TelegramResultFormatter:
    def __init__(self, *, max_chars: int = TELEGRAM_MESSAGE_LIMIT) -> None:
        if not 64 <= max_chars <= TELEGRAM_MESSAGE_LIMIT:
            raise ValueError("Telegram formatter bound is outside the allowed range")
        self.max_chars = max_chars

    def format(self, result: RemoteCommandResult) -> str:
        if result.status not in {
            RemoteResultStatus.ACCEPTED,
            RemoteResultStatus.DUPLICATE,
        }:
            text = self._error(result)
        elif result.result_type == "status":
            text = self._status(result.data_refs or {})
        elif result.result_type == "jobs_list":
            text = self._jobs(result.data_refs or {})
        elif result.result_type == "job_show":
            text = self._job((result.data_refs or {}).get("job", {}))
        elif result.result_type == "approvals_list":
            text = self._approvals(result.data_refs or {})
        elif result.result_type == "approval":
            text = self._approval_result(result.data_refs or {}, result.message)
        else:
            text = self._clean(result.message)
        if result.status is RemoteResultStatus.DUPLICATE:
            text = f"Duplicate delivery; prior result shown.\n\n{text}"
        return self.bound(text)

    def bound(self, text: str) -> str:
        cleaned = self._clean(text)
        if len(cleaned) <= self.max_chars:
            return cleaned
        keep = self.max_chars - len(TRUNCATION_MARKER)
        return cleaned[:keep].rstrip() + TRUNCATION_MARKER

    def _error(self, result: RemoteCommandResult) -> str:
        if result.status is RemoteResultStatus.FAILED:
            return "Request failed safely. Check the local runtime for details."
        lines = ["Request rejected.", self._clean(result.message)]
        if result.error_code:
            lines.append(f"Code: {self._clean(result.error_code)}")
        return "\n".join(lines)

    @staticmethod
    def _status(data: dict[str, Any]) -> str:
        statuses = data.get("jobs_by_status", {})
        status_text = ", ".join(
            f"{key}={value}" for key, value in sorted(statuses.items())
        ) or "none"
        return (
            "Runtime status\n"
            f"Jobs: {data.get('jobs_total', 0)} ({status_text})\n"
            f"Pending approvals: {data.get('pending_approvals', 0)}\n"
            f"Checked: {data.get('checked_at', 'unknown')}"
        )

    def _jobs(self, data: dict[str, Any]) -> str:
        jobs = data.get("jobs", [])
        if not jobs:
            return "Jobs\nNo jobs found."
        lines = [f"Jobs ({data.get('count', len(jobs))})"]
        for job in jobs:
            lines.append(
                f"{self._value(job.get('job_id'))} | "
                f"{self._value(job.get('status'))} | "
                f"risk={self._value(job.get('risk_level'))}"
            )
        return "\n".join(lines)

    def _job(self, job: Any) -> str:
        if not isinstance(job, dict):
            return "Job details are unavailable."
        lines = [f"Job {self._value(job.get('job_id'))}"]
        for label, key in (
            ("Status", "status"),
            ("Risk", "risk_level"),
            ("Approval", "approval_status"),
            ("Attempt", "attempt"),
            ("Updated", "last_updated_at"),
            ("Task", "task"),
        ):
            if key in job:
                lines.append(f"{label}: {self._value(job.get(key))}")
        return "\n".join(lines)

    def _approvals(self, data: dict[str, Any]) -> str:
        approvals = data.get("approvals", [])
        if not approvals:
            return "Pending approvals\nNone."
        lines = [f"Pending approvals ({data.get('count', len(approvals))})"]
        for approval in approvals:
            lines.extend(
                [
                    "",
                    f"ID: {self._value(approval.get('approval_id'))}",
                    f"Job: {self._value(approval.get('job_id'))}",
                    f"Action: {self._value(approval.get('requested_action'))}",
                    f"Reason: {self._value(approval.get('reason'))}",
                    "Fingerprint: "
                    f"{self._value(approval.get('authorization_fingerprint'))}",
                ]
            )
        return "\n".join(lines)

    def _approval_result(self, data: dict[str, Any], message: str) -> str:
        return (
            f"{self._clean(message)}\n"
            f"Approval: {self._value(data.get('approval_id'))}\n"
            f"Approval status: {self._value(data.get('approval_status'))}\n"
            f"Job: {self._value(data.get('job_id'))}\n"
            f"Job status: {self._value(data.get('job_status'))}"
        )

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value).replace("\x00", "").replace("\r", "").strip()

    def _value(self, value: Any) -> str:
        return self._clean("unknown" if value is None else value)


class TelegramNotificationFormatter:
    """Render bounded informational events without granting authority."""

    def __init__(self, *, max_chars: int = TELEGRAM_MESSAGE_LIMIT) -> None:
        self.result_formatter = TelegramResultFormatter(max_chars=max_chars)

    def format(self, event: NotificationEvent) -> str:
        metadata = event.metadata or {}
        if event.notification_type is NotificationType.APPROVAL_REQUESTED:
            approval_id = self._value(event.approval_id)
            fingerprint = self._value(event.authorization_fingerprint)
            text = (
                f"{event.title}\n"
                f"Approval ID: {approval_id}\n"
                f"Action: {self._value(metadata.get('requested_action'))}\n"
                f"Job: {self._value(metadata.get('job_id'))}\n"
                f"Fingerprint: {fingerprint}\n\n"
                f"Approve: /approve {approval_id} {fingerprint}\n"
                f"Reject: /reject {approval_id} {fingerprint}\n\n"
                "Delivery does not grant approval. An explicit command is required."
            )
        elif event.notification_type in {
            NotificationType.APPROVAL_APPROVED,
            NotificationType.APPROVAL_REJECTED,
        }:
            text = (
                f"{event.title}\n"
                f"Approval: {self._value(event.approval_id)}\n"
                f"Action: {self._value(metadata.get('requested_action'))}\n"
                f"Status: {self._value(metadata.get('approval_status'))}\n"
                f"Resolved by: {self._value(metadata.get('decided_by'))}"
            )
        elif event.notification_type is NotificationType.JOB_COMPLETED:
            text = (
                f"{event.title}\n"
                f"Job: {event.source_id}\n"
                f"Task class: {self._value(metadata.get('task_class'))}\n"
                f"Status: completed\n"
                f"{event.summary}"
            )
        elif event.notification_type is NotificationType.JOB_FAILED:
            text = (
                f"{event.title}\n"
                f"Job: {event.source_id}\n"
                f"Category: {self._value(metadata.get('failure_category'))}\n"
                f"Retryable: {self._value(metadata.get('retryable'))}\n"
                f"Attempt: {self._value(metadata.get('attempt'))}/"
                f"{self._value(metadata.get('max_attempts'))}\n"
                f"{event.summary}"
            )
        else:
            text = (
                f"{event.title}\n"
                f"Source: {event.source_type} {event.source_id}\n"
                f"Code: {self._value(metadata.get('error_code'))}\n"
                f"{event.summary}"
            )
        return self.result_formatter.bound(text)

    @staticmethod
    def _value(value: Any) -> str:
        return str("unknown" if value is None else value).replace("\x00", "").strip()
