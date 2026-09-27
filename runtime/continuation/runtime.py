"""Persist and queue continuation steps through existing runtime boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.core.jobs import JobRuntime, RuntimeError


@dataclass(frozen=True)
class ContinuationReservation:
    job: dict[str, Any]
    approval: dict[str, Any] | None = None
    disposition: str = "already_existing"


class ContinuationRuntime:
    """Recover idempotent child reservations without executing them recursively."""

    def __init__(self, jobs: JobRuntime, approvals: ApprovalRuntime) -> None:
        self.jobs = jobs
        self.approvals = approvals

    def reserve(self, parent_job_id: str) -> ContinuationReservation | None:
        before = {job["job_id"]: job["status"] for job in self.jobs.list()}
        child = self.jobs.reserve_continuation(parent_job_id)
        if child is None:
            return None
        approval: dict[str, Any] | None = None
        created_now = child["job_id"] not in before
        changed_now = created_now
        if child["approval_status"] == "required":
            run = self.approvals.request_execution(
                child["job_id"],
                reason="Authorized continuation step requires explicit execution approval",
            )
            child = run.job or child
            approval = run.request.to_dict()
            changed_now = True
        elif child["status"] == "waiting_approval":
            return ContinuationReservation(child, None, "already_existing")
        elif child["status"] == "created":
            child = self.jobs.enqueue(child["job_id"])
            changed_now = True
        disposition = (
            "created_now"
            if created_now
            else "recovered_now"
            if changed_now
            else "already_existing"
        )
        return ContinuationReservation(child, approval, disposition)

    def recover(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        for job in self.jobs.list(status="completed"):
            checkpoint = job.get("continuation")
            if not isinstance(checkpoint, dict) or checkpoint.get("state") != "ready":
                continue
            try:
                reservation = self.reserve(job["job_id"])
            except (RuntimeError, ApprovalRuntimeError):
                raise
            if reservation is not None and reservation.disposition != "already_existing":
                recovered.append(reservation.job)
        return recovered
