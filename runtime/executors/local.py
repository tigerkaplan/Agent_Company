"""Deterministic no-side-effect executor for local development and tests only."""

from __future__ import annotations

from typing import Callable

from runtime.core.jobs import utc_now
from runtime.execution.models import ExecutionRequest, ExecutionResult


class LocalExecutor:
    """Simulate execution success or failure without performing real work."""

    supported_execution_modes = frozenset({"READ_ONLY"})

    def __init__(
        self,
        mode: str = "success",
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        if mode not in {"success", "failure"}:
            raise ValueError("LocalExecutor mode must be 'success' or 'failure'")
        self.mode = mode
        self.clock = clock
        self.last_request: ExecutionRequest | None = None

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.last_request = request
        started_at = self.clock()
        completed_at = self.clock()
        if self.mode == "success":
            return ExecutionResult(
                execution_id=request.execution_id,
                job_id=request.job_id,
                status="succeeded",
                output_refs=(),
                summary="Deterministic local executor completed without performing external work.",
                error=None,
                provider=request.provider,
                started_at=started_at,
                completed_at=completed_at,
                execution_mode=request.execution_mode,
                dry_run=request.dry_run,
            )
        return ExecutionResult(
            execution_id=request.execution_id,
            job_id=request.job_id,
            status="failed",
            output_refs=(),
            summary="Deterministic local executor simulated a failure.",
            error={
                "code": "local_executor_failure",
                "message": "Deterministic local executor simulated a failure",
                "retryable": True,
            },
            provider=request.provider,
            started_at=started_at,
            completed_at=completed_at,
            execution_mode=request.execution_mode,
            dry_run=request.dry_run,
        )
