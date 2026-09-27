"""Run-once execution coordination without provider or connector execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.continuation.models import ContinuationContractError, ContinuationPolicy
from runtime.continuation.runtime import ContinuationRuntime
from runtime.core.jobs import JobRuntime, RuntimeError, utc_now
from runtime.core.references import CanonicalReferenceResolver, ReferenceResolutionError
from runtime.execution.models import ExecutionContractError, ExecutionRequest, ExecutionResult
from runtime.executors.base import Executor
from runtime.review.runtime import ReviewerRuntime, ReviewRuntimeError
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore


def new_execution_id() -> str:
    return f"execution-{uuid4().hex}"


def new_worker_id() -> str:
    return f"worker-{uuid4().hex}"


@dataclass(frozen=True)
class WorkerRunOutcome:
    status: str
    job_id: str | None = None
    execution_id: str | None = None
    result: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    retry_job_id: str | None = None
    continuation_job_id: str | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"status": self.status}
        if self.job_id is not None:
            value["job_id"] = self.job_id
        if self.execution_id is not None:
            value["execution_id"] = self.execution_id
        if self.result is not None:
            value["result"] = self.result
        if self.review is not None:
            value["review"] = self.review
        if self.approval is not None:
            value["approval"] = self.approval
        if self.retry_job_id is not None:
            value["retry_job_id"] = self.retry_job_id
        if self.continuation_job_id is not None:
            value["continuation_job_id"] = self.continuation_job_id
        if self.error is not None:
            value["error"] = self.error
        return value


class Worker:
    """Claim one job, resolve references, delegate once, and record the result."""

    def __init__(
        self,
        runtime: JobRuntime,
        resolver: CanonicalReferenceResolver,
        executor: Executor,
        execution_store: FileExecutionStore,
        *,
        reviewer_runtime: ReviewerRuntime | None = None,
        approval_runtime: ApprovalRuntime | None = None,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] = new_execution_id,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> None:
        self.runtime = runtime
        self.resolver = resolver
        self.executor = executor
        self.execution_store = execution_store
        self.reviewer_runtime = reviewer_runtime
        self.clock = clock
        self.id_factory = id_factory
        self.worker_id = worker_id or new_worker_id()
        self.lease_seconds = lease_seconds
        self.approval_runtime = approval_runtime or ApprovalRuntime(
            runtime,
            FileApprovalStore(runtime.store.root.parent / "approvals"),
            execution_store=execution_store,
            review_store=(reviewer_runtime.store if reviewer_runtime is not None else None),
            clock=clock,
        )
        self.continuation_runtime = ContinuationRuntime(
            runtime, self.approval_runtime
        )

    def run_once(self) -> WorkerRunOutcome:
        try:
            self.recover_persisted_results()
            self.continuation_runtime.recover()
            job = self.runtime.claim(
                claimed_by=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
        except (RuntimeError, ApprovalRuntimeError) as error:
            return WorkerRunOutcome(
                status="worker_error",
                error={"code": "claim_error", "message": str(error)},
            )
        if job is None:
            return WorkerRunOutcome(status="no_work")

        return self._run_job(job)

    def run_claimed(self, job_id: str) -> WorkerRunOutcome:
        try:
            job = self.runtime.validate_claim(job_id, self.worker_id)
        except RuntimeError as error:
            return WorkerRunOutcome(
                status="worker_error",
                job_id=job_id,
                error={"code": "claim_error", "message": str(error)},
            )
        return self._run_job(job)

    def heartbeat(self, job_id: str) -> dict[str, Any]:
        return self.runtime.heartbeat(
            job_id,
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )

    def _run_job(self, job: dict[str, Any]) -> WorkerRunOutcome:
        execution_id = self.id_factory()
        try:
            job = self.runtime.validate_execution_authority(
                job["job_id"], self.worker_id
            )
            context_refs = self.resolver.resolve(job)
            request = self._build_request(job, execution_id, context_refs)
        except RuntimeError as error:
            return WorkerRunOutcome(
                status="worker_error",
                job_id=job["job_id"],
                error={"code": "authorization_error", "message": str(error)},
            )
        except (ReferenceResolutionError, ExecutionContractError) as error:
            return self._record_preparation_failure(job, execution_id, error)

        result = self._execute_safely(request)
        return self._record_result(job, request, result)

    @staticmethod
    def _build_request(
        job: dict[str, Any],
        execution_id: str,
        context_refs: tuple[dict[str, str], ...],
    ) -> ExecutionRequest:
        return ExecutionRequest(
            execution_id=execution_id,
            job_id=job["job_id"],
            task=job["task"],
            task_class=job["task_class"],
            project_id=job.get("project_id"),
            agent=job["agent"],
            skill=job.get("skill"),
            workflow=job["workflow"],
            capability=job["capability"],
            provider=job.get("provider"),
            risk_level=job["risk_level"],
            input_refs=tuple(job["input_refs"]),
            context_refs=context_refs,
            review_required=job["review_required"],
            attempt=job["attempt"],
            dry_run=job.get("dry_run", False),
            approval_status=job["approval_status"],
            execution_mode=job.get("execution_mode", "READ_ONLY"),
            execution_scope=job.get("execution_scope"),
            authorization_fingerprint=(
                job.get("approval", {}).get("authorization_fingerprint")
                if job.get("execution_mode") == "CONTROLLED_WRITE"
                and isinstance(job.get("approval"), dict)
                else None
            ),
            continuation_plan_digest=(
                job.get("continuation", {}).get("plan_digest")
                if isinstance(job.get("continuation"), dict)
                else None
            ),
            continuation_logical_job_id=(
                job.get("continuation", {}).get("logical_job_id")
                if isinstance(job.get("continuation"), dict)
                else None
            ),
            continuation_sequence=(
                job.get("continuation", {}).get("sequence")
                if isinstance(job.get("continuation"), dict)
                else None
            ),
            continuation_step_id=(
                job.get("continuation", {}).get("current_step_id")
                if isinstance(job.get("continuation"), dict)
                else None
            ),
            continuation_execution_ref=(
                job.get("continuation", {}).get("latest_execution_ref")
                if isinstance(job.get("continuation"), dict)
                else None
            ),
        )

    def recover_persisted_results(self) -> list[WorkerRunOutcome]:
        """Advance running jobs whose immutable result survived an interrupted update."""
        recovered: list[WorkerRunOutcome] = []
        for job in self.runtime.list(status="running"):
            linked = {
                str(reference.get("ref", "")).split(":", 1)[1]
                for reference in job.get("output_refs", [])
                if isinstance(reference, dict)
                and str(reference.get("ref", "")).startswith("runtime-execution:")
            }
            try:
                record = self.execution_store.find_for_job(
                    job["job_id"], linked_execution_ids=linked
                )
            except ExecutionStoreError as error:
                recovered.append(
                    WorkerRunOutcome(
                        status="worker_error",
                        job_id=job["job_id"],
                        error={"code": "execution_reconciliation_error", "message": str(error)},
                    )
                )
                continue
            if record is None:
                continue
            if record.request is None:
                recovered.append(
                    WorkerRunOutcome(
                        status="worker_error",
                        job_id=job["job_id"],
                        execution_id=record.result.execution_id,
                        error={
                            "code": "execution_reconciliation_error",
                            "message": "Persisted execution has no canonical request",
                        },
                    )
                )
                continue
            try:
                request = ExecutionRequest.from_persisted_dict(record.request)
                expected_request = self._build_request(
                    job,
                    record.result.execution_id,
                    self.resolver.resolve(job),
                )
            except (
                TypeError,
                ExecutionContractError,
                ReferenceResolutionError,
            ) as error:
                recovered.append(
                    WorkerRunOutcome(
                        status="worker_error",
                        job_id=job["job_id"],
                        execution_id=record.result.execution_id,
                        error={
                            "code": "execution_reconciliation_error",
                            "message": str(error),
                        },
                    )
                )
                continue
            if request.to_dict() != expected_request.to_dict():
                recovered.append(
                    WorkerRunOutcome(
                        status="worker_error",
                        job_id=job["job_id"],
                        execution_id=record.result.execution_id,
                        error={
                            "code": "execution_reconciliation_error",
                            "message": "Persisted execution does not match exact authorized work",
                        },
                    )
                )
                continue
            recovered.append(
                self._record_result(
                    job, request, record.result, persist_result=False
                )
            )
        return recovered

    def _execute_safely(self, request: ExecutionRequest) -> ExecutionResult:
        supported = getattr(self.executor, "supported_execution_modes", {"READ_ONLY"})
        if request.execution_mode not in supported:
            return self._failure_result(
                execution_id=request.execution_id,
                job_id=request.job_id,
                code="controlled_execution_failed",
                message="Selected executor does not support the requested execution mode",
                execution_mode=request.execution_mode,
                dry_run=request.dry_run,
            )
        try:
            result = self.executor.execute(request)
            if not isinstance(result, ExecutionResult):
                raise ExecutionContractError(
                    "Executor did not return the canonical ExecutionResult contract"
                )
            if result.execution_id != request.execution_id or result.job_id != request.job_id:
                raise ExecutionContractError(
                    "Executor result IDs do not match the execution request"
                )
            return result
        except Exception:
            return self._failure_result(
                execution_id=request.execution_id,
                job_id=request.job_id,
                code="executor_error",
                message="Executor raised an exception; details were not persisted",
                execution_mode=request.execution_mode,
                dry_run=request.dry_run,
            )

    def _record_preparation_failure(
        self,
        job: dict[str, Any],
        execution_id: str,
        error: Exception,
    ) -> WorkerRunOutcome:
        result = self._failure_result(
            execution_id=execution_id,
            job_id=job["job_id"],
            code="context_resolution_error",
            message=str(error),
            execution_mode=job.get("execution_mode", "READ_ONLY"),
            dry_run=job.get("dry_run", False),
        )
        return self._record_result(job, None, result)

    def _record_result(
        self,
        job: dict[str, Any],
        request: ExecutionRequest | None,
        result: ExecutionResult,
        *,
        persist_result: bool = True,
    ) -> WorkerRunOutcome:
        serialized_result = result.to_dict()
        try:
            if persist_result:
                self.execution_store.create(request, result)
        except ExecutionStoreError as error:
            failure = {
                "code": "execution_storage_error",
                "message": str(error),
                "retryable": True,
            }
            try:
                updated = self.runtime.fail(
                    job["job_id"],
                    code=failure["code"],
                    message=failure["message"],
                    retryable=True,
                )
                status = updated["status"]
            except RuntimeError:
                status = "worker_error"
            return WorkerRunOutcome(
                status=status,
                job_id=job["job_id"],
                execution_id=result.execution_id,
                result=serialized_result,
                error=failure,
            )

        artifact_ref = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{result.execution_id}",
            "description": "Local provider-neutral execution record",
        }
        review_result: dict[str, Any] | None = None
        approval_result: dict[str, Any] | None = None
        retry_job_id: str | None = None
        continuation_job_id: str | None = None
        try:
            continuation_decision = ContinuationPolicy.decide_execution(
                job,
                result_status=result.status,
                execution_ref=f"runtime-execution:{result.execution_id}",
            )
            if result.status in {"succeeded", "needs_review"}:
                output_refs = [*serialized_result["output_refs"], artifact_ref]
                if result.status == "needs_review":
                    updated = self.runtime.record_execution_for_review(
                        job["job_id"],
                        output_refs,
                        continuation=continuation_decision.checkpoint,
                    )
                else:
                    updated = self.runtime.record_execution_success(
                        job["job_id"],
                        output_refs,
                        continuation=continuation_decision.checkpoint,
                    )
                if updated["status"] == "reviewing" and self.reviewer_runtime is not None:
                    if request is None:
                        raise RuntimeError("Review-required execution has no request")
                    try:
                        review_run = self.reviewer_runtime.run(updated, request, result)
                    except ReviewRuntimeError as error:
                        return WorkerRunOutcome(
                            status="worker_error",
                            job_id=job["job_id"],
                            execution_id=result.execution_id,
                            result=serialized_result,
                            error={
                                "code": "review_runtime_error",
                                "message": str(error),
                            },
                        )
                    review_result = review_run.result.to_dict()
                    approval_ref = None
                    if review_run.result.decision == "NEEDS_HUMAN":
                        try:
                            approval_run = (
                                self.approval_runtime.request_review_completion(
                                    job["job_id"],
                                    result.execution_id,
                                    review_run.result,
                                    review_run.artifact_ref,
                                )
                            )
                        except ApprovalRuntimeError as error:
                            return WorkerRunOutcome(
                                status="worker_error",
                                job_id=job["job_id"],
                                execution_id=result.execution_id,
                                result=serialized_result,
                                review=review_result,
                                error={
                                    "code": "approval_runtime_error",
                                    "message": str(error),
                                },
                            )
                        approval_ref = approval_run.artifact_ref
                        approval_result = approval_run.request.to_dict()
                    review_transition = self.runtime.apply_review_decision(
                        job["job_id"],
                        decision=review_run.result.decision,
                        reason=review_run.result.reason,
                        review_ref=review_run.artifact_ref,
                        approval_ref=approval_ref,
                        continuation=ContinuationPolicy.decide_review(
                            updated,
                            decision=review_run.result.decision,
                            review_ref=str(review_run.artifact_ref["ref"]),
                        ).checkpoint,
                    )
                    updated = review_transition["job"]
                    retry_job = review_transition["retry_job"]
                    if retry_job is not None:
                        retry_job_id = retry_job["job_id"]
                        if retry_job["approval_status"] != "not_required":
                            try:
                                retry_approval = (
                                    self.approval_runtime.request_execution(
                                        retry_job_id,
                                        reason=(
                                            "Reviewer requested a new attempt; fresh "
                                            "execution approval is required"
                                        ),
                                    )
                                )
                            except ApprovalRuntimeError as error:
                                return WorkerRunOutcome(
                                    status="worker_error",
                                    job_id=job["job_id"],
                                    execution_id=result.execution_id,
                                    result=serialized_result,
                                    review=review_result,
                                    error={
                                        "code": "approval_runtime_error",
                                        "message": str(error),
                                    },
                                )
                            approval_result = retry_approval.request.to_dict()
                if updated["status"] == "completed":
                    reservation = self.continuation_runtime.reserve(job["job_id"])
                    if reservation is not None:
                        continuation_job_id = reservation.job["job_id"]
                        if reservation.approval is not None:
                            approval_result = reservation.approval
            elif result.status == "needs_human":
                output_refs = [*serialized_result["output_refs"], artifact_ref]
                blockers = serialized_result.get("blockers", [])
                reason = (
                    str(blockers[0].get("message"))
                    if blockers and isinstance(blockers[0], dict)
                    else "Explicit human input is required"
                )
                human_run = self.approval_runtime.request_human_condition(
                    job["job_id"],
                    result.execution_id,
                    reason=reason,
                    execution_ref=artifact_ref,
                    output_refs=output_refs,
                    continuation=continuation_decision.checkpoint,
                )
                updated = human_run.job or self.runtime.show(job["job_id"])
                approval_result = human_run.request.to_dict()
            else:
                error = self._normalise_result_error(result)
                updated = self.runtime.fail(
                    job["job_id"],
                    code=error["code"],
                    message=error["message"],
                    retryable=False,
                    error_ref=artifact_ref,
                    output_refs=[*serialized_result["output_refs"], artifact_ref],
                    continuation=continuation_decision.checkpoint,
                )
        except (RuntimeError, ApprovalRuntimeError, ContinuationContractError) as error:
            return WorkerRunOutcome(
                status="worker_error",
                job_id=job["job_id"],
                execution_id=result.execution_id,
                result=serialized_result,
                error={"code": "lifecycle_update_error", "message": str(error)},
            )

        outcome_status = updated["status"]
        if retry_job_id is not None:
            retry_job = self.runtime.show(retry_job_id)
            outcome_status = retry_job["status"]
        outcome_error = (
            serialized_result["error"]
            if result.status == "failed"
            else updated.get("error")
        )
        return WorkerRunOutcome(
            status=outcome_status,
            job_id=job["job_id"],
            execution_id=result.execution_id,
            result=serialized_result,
            review=review_result,
            approval=approval_result,
            retry_job_id=retry_job_id,
            continuation_job_id=continuation_job_id,
            error=outcome_error,
        )

    def _failure_result(
        self,
        *,
        execution_id: str,
        job_id: str,
        code: str,
        message: str,
        execution_mode: str = "READ_ONLY",
        dry_run: bool = False,
    ) -> ExecutionResult:
        started_at = self.clock()
        completed_at = self.clock()
        return ExecutionResult(
            execution_id=execution_id,
            job_id=job_id,
            status="failed",
            output_refs=(),
            summary=None,
            error={"code": code, "message": message, "retryable": True},
            next_actions=(
                {
                    "action": "retry_execution",
                    "description": "Retry after the execution blocker has been resolved",
                    "requires_human": False,
                    "automatic": False,
                },
            ),
            provider=None,
            started_at=started_at,
            completed_at=completed_at,
            execution_mode=execution_mode,
            dry_run=dry_run,
        )

    @staticmethod
    def _normalise_error(error: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(error, dict):
            return {
                "code": "executor_failure",
                "message": "Executor returned a failed result without a valid error",
                "retryable": True,
            }
        return {
            "code": str(error.get("code") or "executor_failure"),
            "message": str(error.get("message") or "Executor reported failure"),
            "retryable": bool(error.get("retryable", True)),
        }

    @classmethod
    def _normalise_result_error(cls, result: ExecutionResult) -> dict[str, Any]:
        if result.status == "failed" and result.error is not None:
            error = cls._normalise_error(dict(result.error))
            error["retryable"] = False
            return error
        if result.blockers:
            blocker = result.blockers[0]
            return {
                "code": f"execution_{result.status}",
                "message": str(blocker["message"]),
                "retryable": False,
            }
        return {
            "code": f"execution_{result.status}",
            "message": f"Execution ended with canonical status {result.status}",
            "retryable": False,
        }
