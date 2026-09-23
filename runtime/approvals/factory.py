"""Construct the local Human Approval Runtime."""

from __future__ import annotations

from pathlib import Path

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime
from runtime.review.store import FileReviewStore
from runtime.storage.execution_store import FileExecutionStore


def build_approval_runtime(
    job_runtime: JobRuntime,
    approval_root: Path,
    *,
    execution_store: FileExecutionStore | None = None,
    review_store: FileReviewStore | None = None,
) -> ApprovalRuntime:
    return ApprovalRuntime(
        job_runtime,
        FileApprovalStore(approval_root),
        execution_store=execution_store,
        review_store=review_store,
    )

