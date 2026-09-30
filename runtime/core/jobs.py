"""Deterministic canonical job operations for the local-first runtime."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from runtime.actions.authorization import authorization_fingerprint
from runtime.actions.models import ExecutionScope, ScopeContractError, scope_path_contains
from runtime.approvals.models import approval_boundary_id
from runtime.approvals.store import ApprovalStoreError, FileApprovalStore
from runtime.budget.models import (
    BudgetBinding,
    BudgetContractError,
    BudgetPolicy,
    ExecutionBudgetSpec,
    budget_id_for,
)
from runtime.budget.store import ExecutionBudgetStoreError, FileExecutionBudgetStore
from runtime.continuation.models import (
    ContinuationContractError,
    ContinuationPolicy,
    continuation_plan_digest,
)
from runtime.continuation.store import (
    AuthorizedPlanStoreError,
    FileAuthorizedPlanStore,
)
from runtime.core.lifecycle import Lifecycle, LifecycleError
from runtime.core.validation import JobValidationError, JobValidator
from runtime.execution.models import ExecutionContractError, ExecutionRequest
from runtime.retry.models import (
    RetryBinding,
    RetryContractError,
    RetryPolicy,
    RetryPolicySpec,
    policy_id_for,
    retry_work_digest,
)
from runtime.progress.models import ProgressError
from runtime.progress.runtime import ProgressRuntime
from runtime.retry.runtime import RetryRuntime
from runtime.retry.store import FileRetryStore, RetryStoreError
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore
from runtime.storage.file_store import FileJobStore, JobStoreError


class RuntimeError(ValueError):
    """Raised when a requested runtime operation is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_job_id() -> str:
    return f"job-{uuid4().hex}"


def _plain_json_value(value: Any) -> Any:
    """Copy Mapping-based canonical values into JSON-native containers."""
    if isinstance(value, Mapping):
        return {str(key): _plain_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json_value(item) for item in value]
    return deepcopy(value)


class JobRuntime:
    """Create and transition jobs without routing or provider execution."""

    _MANAGED_CREATE_FIELDS = {
        "schema_version",
        "job_id",
        "created_at",
        "last_updated_at",
        "status",
        "attempt",
        "parent_job_id",
        "continuation",
        "continuation_parent_job_id",
        "retry_authorization",
        "error",
        "approval",
        "scheduled_at",
        "next_run_at",
        "schedule_reason",
        "claimed_by",
        "claimed_at",
        "lease_until",
        "heartbeat_at",
        "claim_released_at",
    }

    def __init__(
        self,
        state_root: Path,
        *,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] = new_job_id,
        lifecycle: Lifecycle | None = None,
        validator: JobValidator | None = None,
        notification_emitter: Any | None = None,
    ) -> None:
        self.store = FileJobStore(state_root)
        self.authorized_plan_store = FileAuthorizedPlanStore(
            self.store.root / ".continuation-authority"
        )
        self.budget_store = FileExecutionBudgetStore(
            self.store.root / ".execution-budgets"
        )
        self.retry_store = FileRetryStore(self.store.root / ".retry-policy")
        self.progress = ProgressRuntime(self.store.root / ".progress")
        self.clock = clock
        self.id_factory = id_factory
        self.lifecycle = lifecycle or Lifecycle()
        self.validator = validator or JobValidator()
        self.notification_emitter = notification_emitter
        self.approval_store: FileApprovalStore | None = None
        self.execution_store: FileExecutionStore | None = None
        self.retry_runtime = RetryRuntime(
            self.retry_store,
            budget_store=self.budget_store,
            clock=clock,
        )

    def reconcile_progress(self) -> None:
        """Recover observations after a job write committed but event delivery did not."""
        try:
            jobs = self.list()
            decisions = {}
            for snapshot in jobs:
                with self.progress.transition_lock():
                    job = self._load(snapshot["job_id"])
                    self.progress.observe_job(job)
                if job["status"] != "failed":
                    continue
                binding = job.get("retry_policy")
                if binding is None:
                    continue
                policy_id = binding["policy_id"]
                if policy_id not in decisions:
                    policy = self.retry_store.load_policy(binding)
                    decisions[policy_id] = self.retry_store.load_state(binding, history_limit=policy.history_limit)["history"]
                for entry in decisions[policy_id]:
                    if entry["source_job_id"] == job["job_id"]:
                        self.progress.observe_retry(job, self.retry_runtime._from_entry(entry))
        except (ProgressError, RetryStoreError, JobStoreError) as error:
            raise RuntimeError(str(error)) from error

    def configure_authority_stores(
        self,
        approval_store: FileApprovalStore,
        execution_store: FileExecutionStore | None,
    ) -> None:
        """Attach canonical stores used to authenticate resumed human authority."""
        self.approval_store = approval_store
        self.execution_store = execution_store
        self.retry_runtime.execution_store = execution_store

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError("Job creation input must be a JSON object")
        managed = sorted(set(payload) & self._MANAGED_CREATE_FIELDS)
        if managed:
            raise RuntimeError(
                f"Job creation input contains runtime-managed fields: {', '.join(managed)}"
            )
        return self._create_attempt(payload, attempt=1, parent_job_id=None)

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in self.lifecycle.statuses:
            raise RuntimeError(f"Unknown lifecycle status: {status}")
        try:
            jobs = self.store.list()
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        for job in jobs:
            self._validate(job)
        self._validate_continuation_lineage(jobs)
        for job in jobs:
            self._validate_retry_authorization(job)
        if status is not None:
            jobs = [job for job in jobs if job["status"] == status]
        return jobs

    def show(self, job_id: str) -> dict[str, Any]:
        job = self._load(job_id)
        return deepcopy(job)

    def enqueue(self, job_id: str) -> dict[str, Any]:
        job = self._load(job_id)
        if not self._approval_allows_execution(job):
            raise RuntimeError(
                "Job requires a resolved scoped approval before it can be queued"
            )
        return self._transition_job(job, "queued")

    def eligible(self, *, now: str | None = None) -> list[dict[str, Any]]:
        now_value = self._parse_timestamp(now or self.clock(), "scheduler clock")
        eligible = [
            job
            for job in self.list(status="queued")
            if self._approval_allows_execution(job)
            and (
                job.get("next_run_at") is None
                or self._parse_timestamp(job["next_run_at"], "next_run_at") <= now_value
            )
        ]
        return sorted(
            eligible,
            key=lambda job: (
                str(job.get("next_run_at") or job["created_at"]),
                job["created_at"],
                job["job_id"],
            ),
        )

    def claim(
        self,
        *,
        claimed_by: str = "manual-worker",
        lease_seconds: int = 300,
    ) -> dict[str, Any] | None:
        if not isinstance(claimed_by, str) or not claimed_by.strip() or len(claimed_by) > 200:
            raise RuntimeError("Claim owner must be bounded non-empty text")
        if not isinstance(lease_seconds, int) or not 5 <= lease_seconds <= 3600:
            raise RuntimeError("Lease duration must be between 5 and 3600 seconds")
        try:
            with self.store.claim_transaction():
                queued = self.eligible()
                if not queued:
                    return None
                job = queued[0]
                now_text = self.clock()
                lease_until = self._format_timestamp(
                    self._parse_timestamp(now_text, "scheduler clock")
                    + timedelta(seconds=lease_seconds)
                )
                updated = self._transition_job(job, "running", save=False)
                updated.update(
                    {
                        "claimed_by": claimed_by.strip(),
                        "claimed_at": now_text,
                        "heartbeat_at": now_text,
                        "lease_until": lease_until,
                    }
                )
                updated.pop("claim_released_at", None)
                return self._save(updated, expected_status=job["status"])
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error

    def validate_claim(self, job_id: str, claimed_by: str) -> dict[str, Any]:
        job = self._load(job_id)
        if job["status"] != "running" or job.get("claimed_by") != claimed_by:
            raise RuntimeError("Job is not held by the expected active claim")
        if self._parse_timestamp(job["lease_until"], "lease_until") <= self._parse_timestamp(
            self.clock(), "scheduler clock"
        ):
            raise RuntimeError("Job claim lease has expired")
        if not self._approval_allows_execution(job):
            raise RuntimeError("Job authorization became stale before execution")
        return job

    def validate_execution_authority(
        self, job_id: str, claimed_by: str
    ) -> dict[str, Any]:
        """Reload and revalidate exact work immediately before executor delegation."""
        job = self.validate_claim(job_id, claimed_by)
        try:
            self.retry_runtime.validate_authorization(job, for_execution=True)
        except RetryStoreError as error:
            raise RuntimeError(str(error)) from error
        return job

    def heartbeat(
        self,
        job_id: str,
        claimed_by: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        if not isinstance(lease_seconds, int) or not 5 <= lease_seconds <= 3600:
            raise RuntimeError("Lease duration must be between 5 and 3600 seconds")
        try:
            with self.store.claim_transaction():
                job = self.validate_claim(job_id, claimed_by)
                now_text = self.clock()
                updated = deepcopy(job)
                updated["heartbeat_at"] = now_text
                updated["lease_until"] = self._format_timestamp(
                    self._parse_timestamp(now_text, "scheduler clock")
                    + timedelta(seconds=lease_seconds)
                )
                updated["last_updated_at"] = now_text
                return self._save(updated, expected_status=job["status"])
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error

    def schedule(
        self,
        job_id: str,
        run_at: str,
        *,
        reason: str = "scheduled",
    ) -> dict[str, Any]:
        job = self._load(job_id)
        if job["status"] not in {"created", "queued"}:
            raise RuntimeError("Only created or queued jobs can be scheduled")
        run_at = self._format_timestamp(self._parse_timestamp(run_at, "run_at"))
        updated = deepcopy(job)
        updated["scheduled_at"] = self.clock()
        updated["next_run_at"] = run_at
        updated["schedule_reason"] = reason
        updated["last_updated_at"] = self.clock()
        if updated["status"] == "created":
            if self._approval_allows_execution(updated):
                updated = self._transition_job(updated, "queued", save=False)
        return self._save(updated, expected_status=job["status"])

    def reschedule(self, job_id: str, run_at: str) -> dict[str, Any]:
        return self.schedule(job_id, run_at, reason="rescheduled")

    def recover_expired_claims(
        self,
        *,
        backoff_seconds: tuple[int, ...],
        excluded_job_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        now = self._parse_timestamp(self.clock(), "scheduler clock")
        excluded = excluded_job_ids or set()
        try:
            with self.store.claim_transaction():
                expired = [
                    job
                    for job in self.list(status="running")
                    if job["job_id"] not in excluded
                    if self._parse_timestamp(job["lease_until"], "lease_until") <= now
                ]
                for job in expired:
                    failed = self._fail_job(
                        job,
                        code="claim_lease_expired",
                        message="Worker claim expired before a terminal result was persisted",
                        retryable=True,
                        failure_class="lease_expired",
                    )
                    delay = backoff_seconds[
                        min(failed["attempt"] - 1, len(backoff_seconds) - 1)
                    ]
                    retry_result = self._retry_locked(
                        failed["job_id"],
                        next_run_at=self._format_timestamp(now + timedelta(seconds=delay)),
                        enqueue=True,
                    )
                    recovered.append(
                        {
                            "failed_job": failed,
                            "retry_job": retry_result["retry_job"],
                            "retry_decision": retry_result["decision"],
                        }
                    )
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        return recovered

    def transition(self, job_id: str, target: str) -> dict[str, Any]:
        job = self._load(job_id)
        return self._transition_job(job, target)

    def approve(self, job_id: str, recorded_by: str) -> dict[str, Any]:
        raise RuntimeError(
            "Direct job approval is disabled; resolve a canonical ApprovalRequest"
        )

    def enter_approval_boundary(
        self,
        job_id: str,
        approval_ref: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_approval_ref(approval_ref)
        job = self._load(job_id)
        if job["status"] == "waiting_approval":
            refs = self._ordered_refs_with_prefix(job, "runtime-approval:")
            if refs and refs[-1] == str(approval_ref["ref"]):
                return job
            if refs:
                raise RuntimeError("Job is bound to a different approval request")
            updated = deepcopy(job)
            updated["output_refs"] = [
                *updated["output_refs"],
                deepcopy(approval_ref),
            ]
            updated["last_updated_at"] = self.clock()
            return self._save(updated, expected_status=job["status"])
        return self._transition_job(
            job, "waiting_approval", approval_ref=approval_ref
        )

    def complete(self, job_id: str) -> dict[str, Any]:
        return self.transition(job_id, "completed")

    def record_execution_success(
        self,
        job_id: str,
        output_refs: list[dict[str, Any]],
        *,
        continuation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job = self._load(job_id)
        updated = deepcopy(job)
        updated["output_refs"] = [
            *updated["output_refs"],
            *_plain_json_value(output_refs),
        ]
        if continuation is not None:
            updated["continuation"] = _plain_json_value(continuation)
        target = "reviewing" if updated["review_required"] else "completed"
        return self._transition_job(updated, target)

    def record_execution_for_review(
        self,
        job_id: str,
        output_refs: list[dict[str, Any]],
        *,
        continuation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Enter the existing Reviewer gate for a canonical needs_review result."""
        job = self._load(job_id)
        updated = deepcopy(job)
        updated["output_refs"] = [
            *updated["output_refs"],
            *_plain_json_value(output_refs),
        ]
        updated["review_required"] = True
        if continuation is not None:
            updated["continuation"] = _plain_json_value(continuation)
        return self._transition_job(updated, "reviewing")

    def record_execution_needs_human(
        self,
        job_id: str,
        output_refs: list[dict[str, Any]],
        *,
        approval_ref: dict[str, Any],
        continuation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a direct human condition without granting execution approval."""
        job = self._load(job_id)
        updated = deepcopy(job)
        updated["output_refs"] = [
            *updated["output_refs"],
            *_plain_json_value(output_refs),
        ]
        if continuation is not None:
            updated["continuation"] = _plain_json_value(continuation)
        return self._transition_job(
            updated, "waiting_approval", approval_ref=approval_ref
        )

    def fail(
        self,
        job_id: str,
        *,
        code: str = "execution_failed",
        message: str = "Job execution failed",
        retryable: bool = True,
        failure_class: str | None = None,
        progress_evidence_digest: str | None = None,
        error_ref: dict[str, Any] | None = None,
        output_refs: list[dict[str, Any]] | None = None,
        continuation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job = self._load(job_id)
        return self._fail_job(
            job,
            code=code,
            message=message,
            retryable=retryable,
            failure_class=failure_class,
            progress_evidence_digest=progress_evidence_digest,
            error_ref=error_ref,
            output_refs=output_refs,
            continuation=continuation,
        )

    def apply_review_decision(
        self,
        job_id: str,
        *,
        decision: str,
        reason: str,
        review_ref: dict[str, Any],
        approval_ref: dict[str, Any] | None = None,
        continuation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        review_rule = self.lifecycle.review_decision_rule
        decisions = review_rule["decisions"]
        if decision not in decisions:
            raise RuntimeError(f"Unsupported review decision: {decision}")
        if not reason.strip():
            raise RuntimeError("Review decision requires a non-empty reason")
        if review_ref.get("ref_type") != "review" or not review_ref.get("ref"):
            raise RuntimeError("Review decision requires a canonical review reference")
        job = self._load(job_id)
        if job["status"] != review_rule["from"]:
            raise RuntimeError("Review decisions may be applied only to reviewing jobs")
        updated = deepcopy(job)
        if continuation is not None:
            updated["continuation"] = _plain_json_value(continuation)
        if not any(
            reference.get("ref") == review_ref.get("ref")
            for reference in updated["output_refs"]
            if isinstance(reference, dict)
        ):
            updated["output_refs"] = [
                *updated["output_refs"],
                deepcopy(review_ref),
            ]

        if decision == "PASS":
            return {
                "job": self._transition_job(updated, decisions[decision]["target"]),
                "retry_job": None,
            }
        if decision == "NEEDS_HUMAN":
            if approval_ref is None:
                raise RuntimeError(
                    "NEEDS_HUMAN requires a persisted approval request reference"
                )
            return {
                "job": self._transition_job(
                    updated,
                    decisions[decision]["target"],
                    approval_ref=approval_ref,
                ),
                "retry_job": None,
            }
        if decision == "FAIL":
            failed = self._fail_job(
                updated,
                code="review_failed",
                message=reason,
                retryable=False,
                error_ref=review_ref,
            )
            return {"job": failed, "retry_job": None}

        failed = self._fail_job(
            updated,
            code="review_retry_requested",
            message=reason,
            retryable=True,
            error_ref=review_ref,
        )
        retry_result = self.retry_or_stop(failed["job_id"])
        retry_job = retry_result["retry_job"]
        if retry_job is not None and retry_job["approval_status"] == "not_required":
            retry_job = self.enqueue(retry_job["job_id"])
        return {"job": failed, "retry_job": retry_job, "retry_decision": retry_result["decision"]}

    def validate_approval_resolution(
        self,
        approval: dict[str, Any],
        approval_ref: dict[str, Any],
    ) -> None:
        self._validate_approval_ref(approval_ref)
        expected_approval_ref = f"runtime-approval:{approval.get('approval_id')}"
        if approval_ref.get("ref") != expected_approval_ref:
            raise RuntimeError("Approval request ID does not match its artifact reference")
        job = self._load(str(approval.get("job_id", "")))
        rule = self.lifecycle.approval_resolution_rule
        action = approval.get("requested_action")
        if job["status"] != rule["from"]:
            raise RuntimeError("Approval is stale: job is not waiting for approval")
        if job.get("approval_status") != "requested":
            raise RuntimeError("Approval is stale: job approval state has changed")
        if approval.get("status") not in {"PENDING", "APPROVED", "REJECTED"}:
            raise RuntimeError("Approval status is invalid")
        if action not in rule["actions"]:
            raise RuntimeError("Approval requested action is invalid")
        if approval.get("authorization_fingerprint") != authorization_fingerprint(job):
            raise RuntimeError("Approval is stale: authorized action scope has changed")
        approval_refs = self._ordered_refs_with_prefix(job, "runtime-approval:")
        if not approval_refs or approval_refs[-1] != str(approval_ref["ref"]):
            raise RuntimeError("Approval is stale: job approval reference has changed")

        execution_refs = self._refs_with_prefix(job, "runtime-execution:")
        review_refs = self._refs_with_prefix(job, "runtime-review:")
        if action == "EXECUTE_JOB":
            if approval.get("execution_id") is not None or approval.get("review_id") is not None:
                raise RuntimeError("Pre-execution approval boundary is malformed")
            if execution_refs or review_refs:
                raise RuntimeError("Approval is stale: execution state already exists")
            return

        if action == "RESOLVE_HUMAN_CONDITION":
            expected_execution = f"runtime-execution:{approval.get('execution_id')}"
            if approval.get("review_id") is not None:
                raise RuntimeError("Human-condition boundary cannot bind a review")
            if execution_refs != {expected_execution} or review_refs:
                raise RuntimeError(
                    "Human-condition approval is stale: execution state has changed"
                )
            checkpoint = job.get("continuation")
            if isinstance(checkpoint, dict) and checkpoint.get("state") != "waiting_human":
                raise RuntimeError("Human-condition checkpoint is no longer waiting")
            return

        expected_execution = f"runtime-execution:{approval.get('execution_id')}"
        expected_review = f"runtime-review:{approval.get('review_id')}"
        if execution_refs != {expected_execution} or review_refs != {expected_review}:
            raise RuntimeError("Approval is stale: execution or review state has changed")

    def apply_approval_resolution(
        self,
        approval: dict[str, Any],
        approval_ref: dict[str, Any],
    ) -> dict[str, Any]:
        self.validate_approval_resolution(approval, approval_ref)
        decision = str(approval["status"])
        action = str(approval["requested_action"])
        rule = self.lifecycle.approval_resolution_rule
        target = rule["actions"][action][decision]["target"]
        job = self._load(str(approval["job_id"]))
        try:
            self.lifecycle.require_transition(job["status"], target)
        except LifecycleError as error:
            raise RuntimeError(str(error)) from error

        updated = deepcopy(job)
        updated["approval_status"] = (
            "approved" if decision == "APPROVED" else "denied"
        )
        updated["approval"] = {
            "approval_id": approval["approval_id"],
            "requested_action": action,
            "execution_id": approval.get("execution_id"),
            "review_id": approval.get("review_id"),
            "status": decision,
            "recorded_at": approval["resolved_at"],
            "recorded_by": approval["decided_by"],
            "actor_type": approval["decision_actor_type"],
            "authorization_fingerprint": approval["authorization_fingerprint"],
        }
        updated["status"] = target
        if (
            decision == "APPROVED"
            and action == "COMPLETE_REVIEWED_JOB"
            and isinstance(updated.get("continuation"), dict)
        ):
            try:
                continuation_decision = ContinuationPolicy.decide_human_approval(updated)
            except ContinuationContractError as error:
                raise RuntimeError(str(error)) from error
            updated["continuation"] = _plain_json_value(
                continuation_decision.checkpoint
            )
        elif (
            decision == "APPROVED"
            and action == "RESOLVE_HUMAN_CONDITION"
            and isinstance(updated.get("continuation"), dict)
        ):
            try:
                continuation_decision = ContinuationPolicy.decide_human_resume(updated)
            except ContinuationContractError as error:
                raise RuntimeError(str(error)) from error
            updated["continuation"] = _plain_json_value(
                continuation_decision.checkpoint
            )
        if decision == "REJECTED":
            if isinstance(updated.get("continuation"), dict) and updated[
                "continuation"
            ].get("state") == "waiting_human":
                updated["continuation"]["state"] = "stopped"
            updated["error"] = {
                "code": "approval_rejected",
                "message": approval.get("decision_reason")
                or "Local operator rejected the requested action",
                "retryable": False,
                "ref": deepcopy(approval_ref),
            }
        updated["last_updated_at"] = self.clock()
        if decision == "REJECTED":
            try:
                self.retry_runtime.record_failure(updated)
            except RetryStoreError as error:
                raise RuntimeError(str(error)) from error
        return self._save(updated, expected_status=job["status"])

    def _fail_job(
        self,
        job: dict[str, Any],
        *,
        code: str,
        message: str,
        retryable: bool,
        failure_class: str | None = None,
        progress_evidence_digest: str | None = None,
        error_ref: dict[str, Any] | None = None,
        output_refs: list[dict[str, Any]] | None = None,
        continuation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not code.strip() or not message.strip():
            raise RuntimeError("Failure code and message must be non-empty")
        try:
            self.lifecycle.require_transition(job["status"], "failed")
        except LifecycleError as error:
            raise RuntimeError(str(error)) from error
        updated = deepcopy(job)
        updated["status"] = "failed"
        error_record: dict[str, Any] = {
            "code": code.strip(),
            "message": message.strip(),
            "retryable": retryable,
        }
        if failure_class is not None:
            if failure_class not in {
                "transient_execution",
                "transient_runtime",
                "transient_storage",
                "lease_expired",
                "review_repair",
                "permanent_failure",
                "authority_failure",
                "budget_failure",
                "policy_failure",
                "malformed_state",
            }:
                raise RuntimeError("Failure class is not canonical")
            error_record["failure_class"] = failure_class
        if progress_evidence_digest is not None:
            if (
                not isinstance(progress_evidence_digest, str)
                or len(progress_evidence_digest) != 64
                or any(character not in "0123456789abcdef" for character in progress_evidence_digest)
            ):
                raise RuntimeError("Progress evidence digest must be a SHA-256 digest")
            error_record["progress_evidence_digest"] = progress_evidence_digest
        if error_ref is not None:
            error_record["ref"] = deepcopy(error_ref)
        updated["error"] = error_record
        if job["status"] == "running":
            updated["claim_released_at"] = self.clock()
        if output_refs:
            updated["output_refs"] = [
                *updated["output_refs"],
                *_plain_json_value(output_refs),
            ]
        if continuation is not None:
            updated["continuation"] = _plain_json_value(continuation)
        updated["last_updated_at"] = self.clock()
        try:
            self.retry_runtime.record_failure(updated)
        except RetryStoreError as error:
            raise RuntimeError(str(error)) from error
        return self._save(updated, expected_status=job["status"])

    def retry(
        self,
        job_id: str,
        *,
        next_run_at: str | None = None,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        result = self.retry_or_stop(
            job_id, next_run_at=next_run_at, enqueue=enqueue
        )
        retry_job = result["retry_job"]
        if retry_job is None:
            decision = result["decision"]
            raise RuntimeError(
                f"Retry policy decision {decision['decision']}: "
                f"{decision['reason_code']}"
            )
        return retry_job

    def retry_or_stop(
        self,
        job_id: str,
        *,
        next_run_at: str | None = None,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        try:
            with self.store.claim_transaction():
                return self._retry_locked(
                    job_id, next_run_at=next_run_at, enqueue=enqueue
                )
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error

    def _retry_locked(
        self,
        job_id: str,
        *,
        next_run_at: str | None = None,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        failed = self._load(job_id)
        if failed["status"] != "failed":
            raise RuntimeError("Only a failed job can be retried")
        try:
            decision = self.retry_runtime.reserve(failed)
            self.progress.observe_retry(failed, decision)
        except (RetryStoreError, ProgressError) as error:
            raise RuntimeError(str(error)) from error
        if decision.decision != "RETRY":
            return {"decision": decision.to_dict(), "retry_job": None}
        if decision.retry_job_id is None or decision.authorization is None:
            raise RuntimeError("Canonical RETRY decision has no reserved attempt")
        existing = [
            job for job in self.list() if job.get("parent_job_id") == failed["job_id"]
        ]
        if len(existing) > 1:
            raise RuntimeError("Failed job has multiple retry children")
        if existing:
            retry_job = existing[0]
            if enqueue and retry_job["status"] == "created" and self._approval_allows_execution(retry_job):
                retry_job = self.enqueue(retry_job["job_id"])
            return {"decision": decision.to_dict(), "retry_job": retry_job}

        try:
            if any(self.retry_store.load_anchor(kind, decision.retry_job_id) is not None
                   for kind in ("materialized", "execution", "failure")):
                raise RetryStoreError("Reserved retry child was removed; consumed identity cannot be recreated")
        except RetryStoreError as error:
            raise RuntimeError(str(error)) from error

        copied_fields = (
            "task",
            "task_class",
            "project_id",
            "agent",
            "skill",
            "workflow",
            "capability",
            "provider",
            "risk_level",
            "review_required",
            "max_attempts",
            "input_refs",
            "execution_mode",
            "execution_scope",
            "dry_run",
            "continuation_plan",
            "continuation",
            "continuation_parent_job_id",
            "execution_budget",
            "retry_policy",
        )
        payload = {
            name: deepcopy(failed[name])
            for name in copied_fields
            if name in failed
        }
        if isinstance(payload.get("continuation"), dict):
            payload["continuation"]["state"] = "active"
            payload["continuation"].pop("next_step_id", None)
            payload["continuation"].pop("latest_execution_ref", None)
            payload["continuation"].pop("latest_review_ref", None)
        payload["output_refs"] = []
        payload["created_by"] = f"retry:{failed['job_id']}"
        payload["approval_status"] = self._retry_approval_status(failed)
        payload["retry_authorization"] = deepcopy(decision.authorization)
        retry_job = self._create_attempt(
            payload,
            attempt=failed["attempt"] + 1,
            parent_job_id=failed["job_id"],
            job_id_override=decision.retry_job_id,
        )
        try:
            with self.retry_store.transaction():
                self.retry_store.anchor("materialized", retry_job["job_id"], {
                    "job_id": retry_job["job_id"], "decision_id": decision.decision_id,
                    "attempt": retry_job["attempt"], "work_digest": retry_work_digest(retry_job),
                })
        except RetryStoreError as error:
            raise RuntimeError(str(error)) from error
        if next_run_at is not None:
            retry_job = self.schedule(
                retry_job["job_id"], next_run_at, reason="retry_backoff"
            )
        elif enqueue:
            retry_job = self.enqueue(retry_job["job_id"])
        return {"decision": decision.to_dict(), "retry_job": retry_job}

    def _create_attempt(
        self,
        payload: dict[str, Any],
        *,
        attempt: int,
        parent_job_id: str | None,
        job_id_override: str | None = None,
    ) -> dict[str, Any]:
        timestamp = self.clock()
        job = deepcopy(payload)
        job_id = job_id_override or self._unused_job_id()
        if job_id_override is not None and self.store.exists(job_id_override):
            raise RuntimeError("Reserved retry identity already exists")
        job.setdefault("input_refs", [])
        job.setdefault("output_refs", [])
        job.setdefault("max_attempts", 1)
        job.setdefault("execution_mode", "READ_ONLY")
        job.setdefault("execution_scope", None)
        job.setdefault("dry_run", False)
        job.update(
            {
                "schema_version": 1,
                "job_id": job_id,
                "created_at": timestamp,
                "last_updated_at": timestamp,
                "status": "created",
                "attempt": attempt,
            }
        )
        retry_value = job.get("retry_policy")
        is_internal_binding = (
            isinstance(retry_value, dict)
            and set(retry_value) == {"policy_id", "logical_job_id", "policy_digest"}
            and (
                parent_job_id is not None
                or job.get("continuation_parent_job_id") is not None
            )
        )
        try:
            if is_internal_binding:
                retry_binding = RetryBinding.from_dict(retry_value)
                self.retry_store.load_policy(retry_binding.to_dict())
            else:
                retry_spec = RetryPolicySpec.from_input(
                    retry_value, max_attempts=job["max_attempts"]
                )
                retry_policy = RetryPolicy.create(
                    job_id, retry_spec, created_at=timestamp
                )
                job["retry_policy"] = self.retry_store.create(retry_policy).to_dict()
        except (RetryContractError, RetryStoreError) as error:
            raise RuntimeError(str(error)) from error
        if "execution_budget" in job and parent_job_id is None:
            try:
                spec = ExecutionBudgetSpec.from_input(job["execution_budget"])
                policy = BudgetPolicy.create(job_id, spec, created_at=timestamp)
                job["execution_budget"] = self.budget_store.create(policy).to_dict()
            except (BudgetContractError, ExecutionBudgetStoreError) as error:
                raise RuntimeError(str(error)) from error
        authorized_plan: dict[str, Any] | None = None
        if "continuation_plan" in job and "continuation" not in job:
            try:
                job["continuation"] = ContinuationPolicy.initialize(job)
                authorized_plan = self.authorized_plan_store.canonical_record(
                    str(job["job_id"]),
                    job["continuation_plan"],
                    authorized_at=timestamp,
                )
            except (ContinuationContractError, AuthorizedPlanStoreError) as error:
                raise RuntimeError(str(error)) from error
        if parent_job_id is not None:
            job["parent_job_id"] = parent_job_id
        self._validate_against_persisted_lineage(
            job, authorized_plan=authorized_plan
        )
        try:
            if authorized_plan is not None:
                self.authorized_plan_store.create(
                    str(job["job_id"]),
                    job["continuation_plan"],
                    authorized_at=timestamp,
                )
            self.store.create(job)
        except (AuthorizedPlanStoreError, JobStoreError) as error:
            raise RuntimeError(str(error)) from error
        return deepcopy(job)

    def reserve_continuation(self, parent_job_id: str) -> dict[str, Any] | None:
        """Create one deterministic child for a ready persisted checkpoint."""
        try:
            with self.store.claim_transaction():
                parent = self._load(parent_job_id)
                checkpoint = parent.get("continuation")
                if (
                    parent["status"] != "completed"
                    or not isinstance(checkpoint, dict)
                    or checkpoint.get("state") != "ready"
                ):
                    return None
                next_step_id = str(checkpoint.get("next_step_id", ""))
                if not next_step_id:
                    raise RuntimeError("Ready continuation checkpoint has no next step")
                child_id = self._continuation_job_id(
                    str(checkpoint["logical_job_id"]),
                    str(checkpoint["plan_digest"]),
                    int(checkpoint["sequence"]) + 1,
                    next_step_id,
                )
                if self.store.exists(child_id):
                    child = self._load(child_id)
                    if (
                        child.get("continuation_parent_job_id") != parent_job_id
                        or child.get("continuation", {}).get("current_step_id")
                        != next_step_id
                        or child.get("continuation", {}).get("plan_digest")
                        != checkpoint.get("plan_digest")
                        or child.get("continuation_plan") != parent.get("continuation_plan")
                    ):
                        raise RuntimeError("Continuation identity is already bound elsewhere")
                    return child

                plan = parent.get("continuation_plan")
                if not isinstance(plan, dict):
                    raise RuntimeError("Continuation checkpoint has no authorized plan")
                try:
                    step = ContinuationPolicy.step(plan, next_step_id)
                    child_checkpoint = ContinuationPolicy.checkpoint_for_child(
                        parent, next_step_id
                    )
                except ContinuationContractError as error:
                    raise RuntimeError(str(error)) from error
                copied_fields = (
                    "task_class",
                    "project_id",
                    "agent",
                    "skill",
                    "workflow",
                    "capability",
                    "provider",
                    "risk_level",
                    "max_attempts",
                    "execution_mode",
                    "execution_scope",
                    "dry_run",
                    "execution_budget",
                    "retry_policy",
                )
                payload = {
                    name: deepcopy(parent[name])
                    for name in copied_fields
                    if name in parent
                }
                requires_approval = bool(step.get("requires_human_approval", False))
                requires_approval = requires_approval or (
                    payload.get("risk_level") == "approval_required"
                    or payload.get("execution_mode") == "CONTROLLED_WRITE"
                    or parent.get("approval_status") != "not_required"
                )
                payload.update(
                    {
                        "task": step["task"],
                        "review_required": bool(
                            step.get("review_required", parent["review_required"])
                        ),
                        "approval_status": "required" if requires_approval else "not_required",
                        "input_refs": deepcopy(step.get("input_refs", parent["input_refs"])),
                        "output_refs": [],
                        "created_by": f"continuation:{parent_job_id}",
                        "continuation_plan": deepcopy(plan),
                        "continuation": child_checkpoint,
                        "continuation_parent_job_id": parent_job_id,
                    }
                )
                if payload.get("execution_mode") == "CONTROLLED_WRITE":
                    payload["review_required"] = True
                timestamp = self.clock()
                child = deepcopy(payload)
                child.update(
                    {
                        "schema_version": 1,
                        "job_id": child_id,
                        "created_at": timestamp,
                        "last_updated_at": timestamp,
                        "status": "created",
                        "attempt": 1,
                    }
                )
                self._validate_against_persisted_lineage(child)
                self.store.create(child)
                return deepcopy(child)
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error

    def _transition_job(
        self,
        job: dict[str, Any],
        target: str,
        *,
        approval_ref: dict[str, Any] | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        try:
            self.lifecycle.require_transition(job["status"], target)
        except LifecycleError as error:
            raise RuntimeError(str(error)) from error

        if target == "running" and not self._approval_allows_execution(job):
            raise RuntimeError("Job cannot run without explicit approval")

        review_rule = self.lifecycle.review_completion_rule
        if (
            job.get(review_rule["condition_field"]) is True
            and target == review_rule["target"]
            and job["status"] not in review_rule["allowed_from"]
        ):
            allowed = ", ".join(review_rule["allowed_from"])
            raise RuntimeError(
                f"Review-required job can enter {target} only from: {allowed}"
            )

        approval_from = self.lifecycle.approval_resolution_rule["from"]
        if job["status"] == approval_from and target in {"queued", "completed", "failed"}:
            raise RuntimeError(
                "waiting_approval continuation requires a resolved ApprovalRequest"
            )

        if target == "waiting_approval":
            if approval_ref is None:
                raise RuntimeError(
                    "waiting_approval requires a persisted ApprovalRequest reference"
                )
            self._validate_approval_ref(approval_ref)

        updated = deepcopy(job)
        updated["status"] = target
        updated["last_updated_at"] = self.clock()
        if job["status"] == "running" and target != "running":
            updated["claim_released_at"] = updated["last_updated_at"]
        if target == "waiting_approval":
            updated["approval_status"] = "requested"
            updated.pop("approval", None)
            if not any(
                reference.get("ref") == approval_ref.get("ref")
                for reference in updated["output_refs"]
                if isinstance(reference, dict)
            ):
                updated["output_refs"] = [
                    *updated["output_refs"],
                    deepcopy(approval_ref),
                ]
        return self._save(updated, expected_status=job["status"]) if save else updated

    def _save(self, job: dict[str, Any], *, expected_status: str | None = None) -> dict[str, Any]:
        try:
            # Separate lock avoids nesting the existing claim/retry OS lock.
            # Every lifecycle writer and reconciliation use the same lock order.
            with self.progress.transition_lock():
                current = self._load(job["job_id"])
                self.progress.observe_job(current)
                if expected_status is not None and current["status"] != expected_status:
                    raise RuntimeError("Stale lifecycle transition; canonical status changed")
                if current["status"] in {"completed", "failed", "cancelled"}:
                    if job != current:
                        raise RuntimeError("Terminal canonical state cannot be rewritten")
                    return deepcopy(current)
                if current["status"] != job["status"]:
                    self.lifecycle.require_transition(current["status"], job["status"])
                self._validate_against_persisted_lineage(job)
                self.progress.reserve_transition(current, job)
                self.store.save(job)
                self.progress.observe_job(job)
        except (JobStoreError, ProgressError, LifecycleError) as error:
            raise RuntimeError(str(error)) from error
        if self.notification_emitter is not None and job["status"] in {
            "completed",
            "failed",
        }:
            try:
                self.notification_emitter.job_terminal(deepcopy(job))
            except Exception:
                # Notification delivery is never part of the job transaction.
                pass
        return deepcopy(job)

    def _validate_against_persisted_lineage(
        self,
        job: dict[str, Any],
        *,
        authorized_plan: dict[str, Any] | None = None,
    ) -> None:
        self._validate(job, authorized_plan=authorized_plan)
        try:
            persisted = self.store.list()
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        candidates = [
            existing
            for existing in persisted
            if existing.get("job_id") != job.get("job_id")
        ]
        self._validate_continuation_lineage([*candidates, job])
        self._validate_retry_authorization(job)

    def _load(self, job_id: str) -> dict[str, Any]:
        try:
            job = self.store.load(job_id)
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        self._validate(job)
        self._validate_loaded_continuation_lineage(job)
        self._validate_retry_authorization(job)
        return job

    def _validate_retry_authorization(self, job: dict[str, Any]) -> None:
        if job.get("parent_job_id") is None:
            return
        try:
            self.retry_runtime.validate_authorization(job, for_execution=False)
        except RetryStoreError as error:
            raise RuntimeError(str(error)) from error

    def _validate(
        self,
        job: dict[str, Any],
        *,
        authorized_plan: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.validator.validate(job)
        except JobValidationError as error:
            raise RuntimeError(f"Invalid canonical job: {error}") from error
        if job["status"] not in self.lifecycle.statuses:
            raise RuntimeError(
                f"Job status is not defined by the canonical lifecycle: {job['status']}"
            )
        if job["attempt"] > job["max_attempts"]:
            raise RuntimeError("Job attempt cannot exceed max_attempts")
        retry_value = job.get("retry_policy")
        if retry_value is not None:
            try:
                retry_binding = RetryBinding.from_dict(retry_value)
                retry_policy = self.retry_store.load_policy(retry_binding.to_dict())
            except (RetryContractError, RetryStoreError) as error:
                raise RuntimeError(f"Invalid retry policy: {error}") from error
            if retry_policy.max_total_attempts != job["max_attempts"]:
                raise RuntimeError("Retry policy attempt limit does not match job")
            checkpoint_for_retry = job.get("continuation")
            if isinstance(checkpoint_for_retry, dict):
                if retry_binding.logical_job_id != checkpoint_for_retry.get("logical_job_id"):
                    raise RuntimeError("Retry policy does not match continuation logical root")
            elif job.get("parent_job_id") is None and retry_binding.logical_job_id != job.get("job_id"):
                raise RuntimeError("Retry policy does not match logical job root")
        budget_value = job.get("execution_budget")
        if budget_value is not None:
            try:
                binding = BudgetBinding.from_dict(budget_value)
                self.budget_store.load_policy(binding)
            except (BudgetContractError, ExecutionBudgetStoreError) as error:
                raise RuntimeError(f"Invalid execution budget: {error}") from error
            checkpoint_for_budget = job.get("continuation")
            if isinstance(checkpoint_for_budget, dict):
                if binding.logical_job_id != checkpoint_for_budget.get("logical_job_id"):
                    raise RuntimeError(
                        "Execution budget does not match continuation logical identity"
                    )
            elif job.get("parent_job_id") is None and binding.logical_job_id != job.get(
                "job_id"
            ):
                raise RuntimeError(
                    "Initial execution budget does not match its logical job root"
                )
        plan = job.get("continuation_plan")
        checkpoint = job.get("continuation")
        if (plan is None) != (checkpoint is None):
            raise RuntimeError(
                "Continuation plan and checkpoint must be present together"
            )
        if isinstance(plan, dict) and isinstance(checkpoint, dict):
            steps = plan.get("steps", [])
            step_ids = [step.get("step_id") for step in steps]
            if len(step_ids) != len(set(step_ids)):
                raise RuntimeError("Continuation plan step IDs must be unique")
            if checkpoint.get("plan_id") != plan.get("plan_id"):
                raise RuntimeError("Continuation checkpoint plan ID does not match")
            try:
                expected_digest = continuation_plan_digest(plan)
            except ContinuationContractError as error:
                raise RuntimeError(str(error)) from error
            if checkpoint.get("plan_digest") != expected_digest:
                raise RuntimeError("Continuation plan digest does not match authorized plan")
            authority = authorized_plan
            if authority is None:
                try:
                    authority = self.authorized_plan_store.load(
                        str(checkpoint.get("logical_job_id", ""))
                    )
                except AuthorizedPlanStoreError as error:
                    raise RuntimeError(str(error)) from error
            if (
                authority.get("logical_job_id")
                != checkpoint.get("logical_job_id")
                or authority.get("plan_id") != plan.get("plan_id")
                or authority.get("plan_digest") != expected_digest
                or authority.get("plan") != plan
            ):
                raise RuntimeError(
                    "Continuation plan does not match immutable authorized plan"
                )
            completed = checkpoint.get("completed_step_ids", [])
            remaining = checkpoint.get("remaining_step_ids", [])
            if len(completed) != len(set(completed)):
                raise RuntimeError("Completed continuation step IDs must be unique")
            if len(remaining) != len(set(remaining)):
                raise RuntimeError("Remaining continuation step IDs must be unique")
            if set(completed) & set(remaining):
                raise RuntimeError("Continuation work cannot be complete and remaining")
            if set(completed) | set(remaining) != set(step_ids):
                raise RuntimeError("Continuation checkpoint must cover the authorized plan")
            current = checkpoint.get("current_step_id")
            state = checkpoint.get("state")
            sequence = checkpoint.get("sequence")
            if not isinstance(sequence, int) or not 0 <= sequence < len(step_ids):
                raise RuntimeError("Continuation sequence does not identify a plan step")
            if current != step_ids[sequence]:
                raise RuntimeError("Continuation current step does not match sequence")
            authorized_steps = authority["plan"]["steps"]
            authorized_step = authorized_steps[sequence]
            if current != authorized_step.get("step_id"):
                raise RuntimeError(
                    "Continuation current step does not match authorized plan"
                )
            if job.get("task") != authorized_step.get("task"):
                raise RuntimeError("Job task does not match the authorized current step")
            if "input_refs" in authorized_step and job.get(
                "input_refs"
            ) != authorized_step.get(
                "input_refs"
            ):
                raise RuntimeError(
                    "Job input references do not match the authorized current step"
                )
            self._validate_current_step_policy(job, authorized_step)
            if state in {"active", "waiting_review", "waiting_human", "blocked", "stopped"}:
                expected_completed = step_ids[:sequence]
                expected_remaining = step_ids[sequence:]
                if current not in remaining:
                    raise RuntimeError("Active continuation step must remain incomplete")
            else:
                expected_completed = step_ids[: sequence + 1]
                expected_remaining = step_ids[sequence + 1 :]
                if current not in completed:
                    raise RuntimeError("Ready or terminal continuation step must be complete")
            if completed != expected_completed or remaining != expected_remaining:
                raise RuntimeError(
                    "Continuation checkpoint must preserve authorized plan order"
                )
            if state == "ready":
                if not remaining or checkpoint.get("next_step_id") != remaining[0]:
                    raise RuntimeError("Ready continuation must identify the next planned step")
            elif "next_step_id" in checkpoint:
                raise RuntimeError("Only a ready continuation may identify a next step")
            if state == "terminal" and remaining:
                raise RuntimeError("Terminal continuation cannot retain remaining work")
            allowed_statuses = {
                "active": {
                    "created",
                    "queued",
                    "running",
                    "waiting_approval",
                    "failed",
                    "cancelled",
                },
                "waiting_review": {"reviewing", "cancelled"},
                "waiting_human": {"waiting_approval", "cancelled"},
                "blocked": {"failed"},
                "stopped": {"failed"},
                "ready": {"completed"},
                "terminal": {"completed"},
            }
            if job["status"] not in allowed_statuses.get(str(state), set()):
                raise RuntimeError(
                    "Continuation checkpoint state does not match job lifecycle state"
                )
        if job.get("continuation_parent_job_id") == job.get("job_id"):
            raise RuntimeError("Continuation child cannot parent itself")
        if (
            job.get("continuation_parent_job_id") is not None
            and job.get("continuation_parent_job_id") == job.get("parent_job_id")
        ):
            raise RuntimeError("Retry ancestry cannot masquerade as continuation ancestry")
        if job.get("approval_status") == "approved" and "approval" not in job:
            raise RuntimeError("Approved jobs require an explicit approval record")
        if job.get("approval_status") == "approved":
            approval = job.get("approval", {})
            if approval.get("authorization_fingerprint") != authorization_fingerprint(job):
                raise RuntimeError("Approval does not match the exact authorized work")
            if (
                job["status"] in {"created", "queued", "running"}
                and approval.get("requested_action") == "RESOLVE_HUMAN_CONDITION"
                and not self._approval_allows_execution(job)
            ):
                raise RuntimeError(
                    "Resolved human condition does not match its execution evidence"
                )
        if not isinstance(job.get("dry_run", False), bool):
            raise RuntimeError("Job dry_run must be a boolean")
        for field in (
            "scheduled_at",
            "next_run_at",
            "claimed_at",
            "lease_until",
            "heartbeat_at",
            "claim_released_at",
        ):
            if field in job:
                self._parse_timestamp(job[field], field)
        claim_fields = ("claimed_by", "claimed_at", "lease_until", "heartbeat_at")
        if job["status"] == "running" and any(field not in job for field in claim_fields):
            raise RuntimeError("Running jobs require complete claim lease metadata")
        execution_mode = job.get("execution_mode", "READ_ONLY")
        if execution_mode == "READ_ONLY":
            if job.get("execution_scope") is not None:
                raise RuntimeError("READ_ONLY jobs cannot define a write scope")
        elif execution_mode == "CONTROLLED_WRITE":
            try:
                scope = ExecutionScope.from_dict(job.get("execution_scope") or {})
            except ScopeContractError as error:
                raise RuntimeError(f"Invalid controlled-write scope: {error}") from error
            if scope.dry_run != job.get("dry_run", False):
                raise RuntimeError(
                    "CONTROLLED_WRITE execution scope dry_run must match the job"
                )
            if job.get("approval_status") == "not_required":
                raise RuntimeError("CONTROLLED_WRITE jobs require explicit approval")
            if job.get("review_required") is not True:
                raise RuntimeError("CONTROLLED_WRITE jobs require independent review")
            approval = job.get("approval")
            if job.get("approval_status") == "approved" and (
                not isinstance(approval, dict)
                or approval.get("authorization_fingerprint")
                != authorization_fingerprint(job)
            ):
                raise RuntimeError(
                    "CONTROLLED_WRITE approval does not match the current action scope"
                )

    @staticmethod
    def _parse_timestamp(value: str, label: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise RuntimeError(f"{label} must be an ISO 8601 date-time") from error
        if parsed.tzinfo is None:
            raise RuntimeError(f"{label} must include an explicit timezone")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _unused_job_id(self) -> str:
        for _ in range(10):
            candidate = self.id_factory()
            if not self.store.exists(candidate) and not self.authorized_plan_store.exists(
                candidate
            ) and not self.budget_store.exists(budget_id_for(candidate)):
                return candidate
        raise RuntimeError("Could not generate a unique job ID")

    @staticmethod
    def _continuation_job_id(
        logical_job_id: str, plan_digest: str, sequence: int, step_id: str
    ) -> str:
        boundary = f"{logical_job_id}\n{plan_digest}\n{sequence}\n{step_id}".encode("utf-8")
        return f"job-cont-{hashlib.sha256(boundary).hexdigest()[:32]}"

    def _approval_allows_execution(self, job: dict[str, Any]) -> bool:
        status = job.get("approval_status")
        if status == "not_required":
            return not self._current_step_requires_approval(job)
        approval = job.get("approval", {})
        action = approval.get("requested_action")
        allowed = (
            status == "approved"
            and approval.get("status") == "APPROVED"
            and approval.get("actor_type") == "local_operator"
            and bool(approval.get("approval_id"))
        )
        exact_work_allowed = bool(
            allowed
            and action in {"EXECUTE_JOB", "RESOLVE_HUMAN_CONDITION"}
            and approval.get("authorization_fingerprint")
            == authorization_fingerprint(job)
        )
        if not exact_work_allowed:
            return False
        if approval.get("approval_id") != approval_boundary_id(
            str(job.get("job_id", "")),
            approval.get("execution_id"),
            approval.get("review_id"),
            str(action),
            str(approval.get("authorization_fingerprint", "")),
        ):
            return False
        approval_refs = JobRuntime._ordered_refs_with_prefix(
            job, "runtime-approval:"
        )
        if not approval_refs or approval_refs[-1] != (
            f"runtime-approval:{approval.get('approval_id')}"
        ):
            return False
        if action != "RESOLVE_HUMAN_CONDITION":
            return True
        execution_id = approval.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id:
            return False
        expected_ref = f"runtime-execution:{execution_id}"
        if JobRuntime._refs_with_prefix(job, "runtime-execution:") != {
            expected_ref
        }:
            return False
        checkpoint = job.get("continuation")
        checkpoint_matches = not isinstance(checkpoint, dict) or checkpoint.get(
            "latest_execution_ref"
        ) == expected_ref
        return checkpoint_matches and self._human_resolution_artifacts_match(
            job, approval
        )

    @staticmethod
    def _current_step(job: dict[str, Any]) -> dict[str, Any] | None:
        plan = job.get("continuation_plan")
        checkpoint = job.get("continuation")
        if not isinstance(plan, dict) or not isinstance(checkpoint, dict):
            return None
        current = checkpoint.get("current_step_id")
        for step in plan.get("steps", []):
            if isinstance(step, dict) and step.get("step_id") == current:
                return step
        return None

    @classmethod
    def _current_step_requires_approval(cls, job: dict[str, Any]) -> bool:
        step = cls._current_step(job)
        if step is None:
            return False
        return bool(step.get("requires_human_approval", False)) or (
            step.get("risk_level") == "approval_required"
            or step.get("execution_mode") == "CONTROLLED_WRITE"
        )

    def _validate_current_step_policy(
        self, job: dict[str, Any], step: dict[str, Any]
    ) -> None:
        if self._current_step_requires_approval(job) and job.get(
            "approval_status"
        ) == "not_required":
            raise RuntimeError(
                "Job approval policy is weaker than the authorized current step"
            )
        step_requires_review = bool(step.get("review_required", False)) or (
            step.get("execution_mode") == "CONTROLLED_WRITE"
        )
        if step_requires_review and job.get("review_required") is not True:
            raise RuntimeError(
                "Job review policy is weaker than the authorized current step"
            )
        if "execution_mode" in step and job.get(
            "execution_mode", "READ_ONLY"
        ) != step.get("execution_mode"):
            raise RuntimeError(
                "Job execution mode does not match the authorized current step"
            )
        if step.get("dry_run") is True and job.get("dry_run", False) is not True:
            raise RuntimeError(
                "Job dry-run policy is weaker than the authorized current step"
            )
        if "risk_level" in step:
            ranks = {"low": 0, "medium": 1, "high": 2, "approval_required": 3}
            if ranks[str(job.get("risk_level"))] < ranks[str(step["risk_level"])]:
                raise RuntimeError(
                    "Job risk policy is weaker than the authorized current step"
                )
        if step.get("execution_scope") is not None:
            try:
                canonical_scope = ExecutionScope.from_dict(step["execution_scope"])
                actual_scope = ExecutionScope.from_dict(job.get("execution_scope") or {})
            except ScopeContractError as error:
                raise RuntimeError(f"Invalid current-step execution scope: {error}") from error
            if not self._scope_is_no_broader(actual_scope, canonical_scope):
                raise RuntimeError(
                    "Job execution scope is broader than the authorized current step"
                )

    @staticmethod
    def _scope_is_no_broader(
        actual: ExecutionScope, canonical: ExecutionScope
    ) -> bool:
        def covered(path: str, boundaries: tuple[str, ...]) -> bool:
            return any(
                scope_path_contains(boundary, path, project_root=canonical.project_root)
                for boundary in boundaries
            )

        if Path(actual.project_root).resolve() != Path(
            canonical.project_root
        ).resolve():
            return False
        if not all(
            covered(path, canonical.allowed_paths) for path in actual.allowed_paths
        ):
            return False
        if not all(
            covered(path, actual.forbidden_paths)
            for path in canonical.forbidden_paths
        ):
            return False
        if (
            canonical.write_mode == "CREATE_OR_MODIFY"
            and actual.write_mode != canonical.write_mode
        ):
            return False
        if actual.max_changed_files > canonical.max_changed_files:
            return False
        if actual.max_artifact_bytes > canonical.max_artifact_bytes:
            return False
        for field in ("allow_tests", "allow_git_reads", "allow_protected_paths"):
            if getattr(actual, field) and not getattr(canonical, field):
                return False
        if canonical.dry_run and not actual.dry_run:
            return False
        return True

    def _human_resolution_artifacts_match(
        self, job: dict[str, Any], compact: dict[str, Any]
    ) -> bool:
        if self.approval_store is None or self.execution_store is None:
            return False
        approval_id = compact.get("approval_id")
        execution_id = compact.get("execution_id")
        if not isinstance(approval_id, str) or not isinstance(execution_id, str):
            return False
        try:
            persisted_approval = self.approval_store.load(approval_id)
            execution_record = self.execution_store.load(execution_id)
            request = ExecutionRequest.from_persisted_dict(execution_record.request)
        except (
            ApprovalStoreError,
            ExecutionStoreError,
            ExecutionContractError,
        ):
            return False
        fingerprint = authorization_fingerprint(job)
        execution_ref = f"runtime-execution:{execution_id}"
        approval_ref = f"runtime-approval:{approval_id}"
        evidence_refs = {
            str(reference.get("ref"))
            for reference in persisted_approval.evidence_refs
            if isinstance(reference, dict)
        }
        return bool(
            persisted_approval.status == "APPROVED"
            and persisted_approval.requested_action == "RESOLVE_HUMAN_CONDITION"
            and persisted_approval.job_id == job.get("job_id")
            and persisted_approval.execution_id == execution_id
            and persisted_approval.review_id is None
            and persisted_approval.authorization_fingerprint == fingerprint
            and persisted_approval.approval_id == approval_id
            and persisted_approval.risk_level == job.get("risk_level")
            and persisted_approval.execution_mode
            == job.get("execution_mode", "READ_ONLY")
            and persisted_approval.execution_scope == job.get("execution_scope")
            and persisted_approval.dry_run == job.get("dry_run", False)
            and approval_ref
            in self._refs_with_prefix(job, "runtime-approval:")
            and execution_ref in evidence_refs
            and execution_record.result.status == "needs_human"
            and execution_record.result.job_id == job.get("job_id")
            and request.execution_id == execution_id
            and request.job_id == job.get("job_id")
            and authorization_fingerprint(request.to_dict()) == fingerprint
        )

    def logical_statuses(self) -> list[dict[str, Any]]:
        """Derive one authoritative head per logical continuation without rewriting history."""
        jobs = self.list()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for job in jobs:
            checkpoint = job.get("continuation")
            if isinstance(checkpoint, dict):
                grouped.setdefault(str(checkpoint["logical_job_id"]), []).append(job)
        statuses: list[dict[str, Any]] = []
        for logical_id, members in sorted(grouped.items()):
            head = max(
                members,
                key=lambda item: (
                    int(item["continuation"]["sequence"]),
                    int(item["attempt"]),
                    str(item["created_at"]),
                    str(item["job_id"]),
                ),
            )
            checkpoint = head["continuation"]
            statuses.append(
                {
                    "logical_job_id": logical_id,
                    "head_job_id": head["job_id"],
                    "head_status": head["status"],
                    "plan_digest": checkpoint["plan_digest"],
                    "sequence": checkpoint["sequence"],
                    "attempt": head["attempt"],
                    "current_step_id": checkpoint["current_step_id"],
                    "completed_step_ids": deepcopy(checkpoint["completed_step_ids"]),
                    "remaining_step_ids": deepcopy(checkpoint["remaining_step_ids"]),
                    "state": checkpoint["state"],
                    "terminal": head["status"] == "completed"
                    and checkpoint["state"] == "terminal"
                    and not checkpoint["remaining_step_ids"],
                    "final_result_ref": checkpoint.get("latest_execution_ref")
                    if checkpoint["state"] == "terminal"
                    else None,
                }
            )
        return statuses

    def logical_status(self, logical_job_id: str) -> dict[str, Any]:
        for status in self.logical_statuses():
            if status["logical_job_id"] == logical_job_id:
                return status
        raise RuntimeError(f"Logical continuation not found: {logical_job_id}")

    def _validate_continuation_lineage(self, jobs: list[dict[str, Any]]) -> None:
        by_id = {str(job["job_id"]): job for job in jobs}
        retry_positions: dict[tuple[str, int], str] = {}
        continuation_positions: dict[
            tuple[str, str, str, int, str, int], str
        ] = {}
        for job in jobs:
            checkpoint = job.get("continuation")
            retry_parent_id = job.get("parent_job_id")
            continuation_parent_id = job.get("continuation_parent_job_id")
            if retry_parent_id is not None:
                if retry_parent_id == job["job_id"]:
                    raise RuntimeError("Retry job cannot parent itself")
                retry_parent = by_id.get(str(retry_parent_id))
                if retry_parent is None:
                    raise RuntimeError("Retry parent is missing")
                if retry_parent.get("status") != "failed":
                    raise RuntimeError("Retry parent must be a failed job")
                if int(job["attempt"]) != int(retry_parent["attempt"]) + 1:
                    raise RuntimeError("Retry attempt must advance exactly once")
                if job.get("created_by") != f"retry:{retry_parent_id}":
                    raise RuntimeError("Retry provenance does not match its parent")
                preserved_retry_fields = (
                    "task",
                    "task_class",
                    "project_id",
                    "agent",
                    "skill",
                    "workflow",
                    "capability",
                    "provider",
                    "risk_level",
                    "review_required",
                    "max_attempts",
                    "input_refs",
                    "execution_mode",
                    "execution_scope",
                    "dry_run",
                    "continuation_plan",
                    "continuation_parent_job_id",
                    "execution_budget",
                    "retry_policy",
                )
                if any(
                    retry_parent.get(field) != job.get(field)
                    for field in preserved_retry_fields
                ):
                    raise RuntimeError("Retry ancestry changed canonical job identity")
                if job.get("retry_authorization", {}).get("source_job_id") != retry_parent_id:
                    raise RuntimeError("Retry authorization does not match its parent")
                position = (str(retry_parent_id), int(job["attempt"]))
                existing_retry = retry_positions.setdefault(
                    position, str(job["job_id"])
                )
                if existing_retry != str(job["job_id"]):
                    raise RuntimeError("Retry parent has competing child attempts")
                parent_checkpoint = retry_parent.get("continuation")
                if isinstance(checkpoint, dict):
                    if not isinstance(parent_checkpoint, dict) or any(
                        parent_checkpoint.get(field) != checkpoint.get(field)
                        for field in (
                            "logical_job_id",
                            "plan_id",
                            "plan_digest",
                            "sequence",
                            "current_step_id",
                        )
                    ):
                        raise RuntimeError(
                            "Retry ancestry changed continuation authority"
                        )
                    # _validate authenticates each checkpoint's ordered prefix
                    # against the persisted plan. A successful retry may finish
                    # its own unit without changing plan/sequence/unit identity.
                elif parent_checkpoint is not None:
                    raise RuntimeError(
                        "Ordinary retry cannot discard continuation authority"
                    )
            elif int(job["attempt"]) != 1:
                raise RuntimeError("A non-retry job must start at attempt one")

            if not isinstance(checkpoint, dict):
                if continuation_parent_id is not None:
                    raise RuntimeError(
                        "Continuation ancestry requires a continuation checkpoint"
                    )
                continue
            sequence = int(checkpoint["sequence"])
            if sequence == 0:
                if continuation_parent_id is not None:
                    raise RuntimeError("Initial continuation step cannot have a continuation parent")
                if retry_parent_id is None:
                    if checkpoint["logical_job_id"] != job["job_id"]:
                        raise RuntimeError("Initial continuation logical root is unrelated")
                    if int(job["attempt"]) != 1:
                        raise RuntimeError("Initial continuation root must start at attempt one")
                continue
            if continuation_parent_id is None:
                raise RuntimeError("Continuation child requires canonical parent ancestry")
            expected_child_id = self._continuation_job_id(
                str(checkpoint["logical_job_id"]),
                str(checkpoint["plan_digest"]),
                sequence,
                str(checkpoint["current_step_id"]),
            )
            if retry_parent_id is None and job["job_id"] != expected_child_id:
                raise RuntimeError(
                    "Continuation child ID does not match its canonical position"
                )
            parent = by_id.get(str(continuation_parent_id))
            parent_checkpoint = parent.get("continuation") if parent else None
            if not isinstance(parent_checkpoint, dict) or any(
                parent_checkpoint.get(field) != checkpoint.get(field)
                for field in ("logical_job_id", "plan_digest")
            ):
                raise RuntimeError("Continuation child is attached to an unrelated logical root")
            if int(parent_checkpoint["sequence"]) != sequence - 1:
                raise RuntimeError("Continuation sequence does not advance from its parent")
            if (
                parent.get("status") != "completed"
                or parent_checkpoint.get("state") != "ready"
                or parent_checkpoint.get("next_step_id")
                != checkpoint.get("current_step_id")
            ):
                raise RuntimeError(
                    "Continuation parent is not the completed ready prior step"
                )
            if retry_parent_id is None and int(job["attempt"]) != 1:
                raise RuntimeError("Continuation child must start at attempt one")
            preserved_continuation_fields = (
                "task_class",
                "project_id",
                "agent",
                "skill",
                "workflow",
                "capability",
                "provider",
                "risk_level",
                "max_attempts",
                "execution_mode",
                "execution_scope",
                "dry_run",
                "continuation_plan",
                "execution_budget",
                "retry_policy",
            )
            if any(
                parent.get(field) != job.get(field)
                for field in preserved_continuation_fields
            ):
                raise RuntimeError(
                    "Continuation ancestry changed canonical job identity"
                )

            continuation_position = (
                str(checkpoint["logical_job_id"]),
                str(continuation_parent_id),
                str(checkpoint["plan_digest"]),
                sequence,
                str(checkpoint["current_step_id"]),
                int(job["attempt"]),
            )
            existing_child = continuation_positions.setdefault(
                continuation_position, str(job["job_id"])
            )
            if existing_child != str(job["job_id"]):
                raise RuntimeError(
                    "Continuation lineage has competing canonical children"
                )

        for job in jobs:
            seen = {str(job["job_id"])}
            parent_id = job.get("parent_job_id")
            while parent_id is not None:
                current_id = str(parent_id)
                if current_id in seen:
                    raise RuntimeError("Retry ancestry contains a cycle")
                seen.add(current_id)
                parent = by_id.get(current_id)
                if parent is None:
                    break
                parent_id = parent.get("parent_job_id")

    def _validate_loaded_continuation_lineage(self, job: dict[str, Any]) -> None:
        try:
            jobs = self.store.list()
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        by_id = {str(candidate["job_id"]): candidate for candidate in jobs}
        pending = [job]
        seen = {str(job["job_id"])}
        while pending:
            current = pending.pop()
            for field in ("parent_job_id", "continuation_parent_job_id"):
                parent_id = current.get(field)
                if parent_id is None or str(parent_id) in seen:
                    continue
                parent = by_id.get(str(parent_id))
                if parent is None:
                    continue
                self._validate(parent)
                seen.add(str(parent_id))
                pending.append(parent)
        self._validate_continuation_lineage(jobs)

    @staticmethod
    def _validate_approval_ref(approval_ref: dict[str, Any]) -> None:
        if (
            approval_ref.get("ref_type") != "approval"
            or not str(approval_ref.get("ref", "")).startswith("runtime-approval:")
        ):
            raise RuntimeError("Approval boundary requires a canonical approval reference")

    @staticmethod
    def _refs_with_prefix(job: dict[str, Any], prefix: str) -> set[str]:
        return {
            str(reference.get("ref"))
            for reference in job.get("output_refs", [])
            if isinstance(reference, dict)
            and str(reference.get("ref", "")).startswith(prefix)
        }

    @staticmethod
    def _ordered_refs_with_prefix(job: dict[str, Any], prefix: str) -> list[str]:
        return [
            str(reference.get("ref"))
            for reference in job.get("output_refs", [])
            if isinstance(reference, dict)
            and str(reference.get("ref", "")).startswith(prefix)
        ]

    def _retry_approval_status(self, job: dict[str, Any]) -> str:
        try:
            return "required" if self.retry_runtime.approval_required(job) else "not_required"
        except RetryStoreError as error:
            raise RuntimeError(str(error)) from error
