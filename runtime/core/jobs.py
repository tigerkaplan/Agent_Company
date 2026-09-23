"""Deterministic canonical job operations for the local-first runtime."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from runtime.actions.authorization import authorization_fingerprint
from runtime.actions.models import ExecutionScope, ScopeContractError
from runtime.core.lifecycle import Lifecycle, LifecycleError
from runtime.core.validation import JobValidationError, JobValidator
from runtime.storage.file_store import FileJobStore, JobStoreError


class RuntimeError(ValueError):
    """Raised when a requested runtime operation is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_job_id() -> str:
    return f"job-{uuid4().hex}"


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
    ) -> None:
        self.store = FileJobStore(state_root)
        self.clock = clock
        self.id_factory = id_factory
        self.lifecycle = lifecycle or Lifecycle()
        self.validator = validator or JobValidator()

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
                return self._save(updated)
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
                return self._save(updated)
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
        return self._save(updated)

    def reschedule(self, job_id: str, run_at: str) -> dict[str, Any]:
        return self.schedule(job_id, run_at, reason="rescheduled")

    def recover_expired_claims(
        self,
        *,
        backoff_seconds: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        now = self._parse_timestamp(self.clock(), "scheduler clock")
        try:
            with self.store.claim_transaction():
                expired = [
                    job
                    for job in self.list(status="running")
                    if self._parse_timestamp(job["lease_until"], "lease_until") <= now
                ]
                for job in expired:
                    failed = self._fail_job(
                        job,
                        code="claim_lease_expired",
                        message="Worker claim expired before a terminal result was persisted",
                        retryable=True,
                    )
                    retry_job = None
                    if failed["attempt"] < failed["max_attempts"]:
                        delay = backoff_seconds[
                            min(failed["attempt"] - 1, len(backoff_seconds) - 1)
                        ]
                        retry_job = self.retry(
                            failed["job_id"],
                            next_run_at=self._format_timestamp(now + timedelta(seconds=delay)),
                            enqueue=True,
                        )
                    recovered.append({"failed_job": failed, "retry_job": retry_job})
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
            return self._save(updated)
        return self._transition_job(
            job, "waiting_approval", approval_ref=approval_ref
        )

    def complete(self, job_id: str) -> dict[str, Any]:
        return self.transition(job_id, "completed")

    def record_execution_success(
        self,
        job_id: str,
        output_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        job = self._load(job_id)
        updated = deepcopy(job)
        updated["output_refs"] = [*updated["output_refs"], *deepcopy(output_refs)]
        target = "reviewing" if updated["review_required"] else "completed"
        return self._transition_job(updated, target)

    def fail(
        self,
        job_id: str,
        *,
        code: str = "execution_failed",
        message: str = "Job execution failed",
        retryable: bool = True,
        error_ref: dict[str, Any] | None = None,
        output_refs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        job = self._load(job_id)
        return self._fail_job(
            job,
            code=code,
            message=message,
            retryable=retryable,
            error_ref=error_ref,
            output_refs=output_refs,
        )

    def apply_review_decision(
        self,
        job_id: str,
        *,
        decision: str,
        reason: str,
        review_ref: dict[str, Any],
        approval_ref: dict[str, Any] | None = None,
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

        if updated["attempt"] >= updated["max_attempts"]:
            failed = self._fail_job(
                updated,
                code="review_retry_exhausted",
                message="Reviewer requested retry but max_attempts is exhausted",
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
        retry_job = self.retry(failed["job_id"])
        if retry_job["approval_status"] == "not_required":
            retry_job = self.enqueue(retry_job["job_id"])
        return {"job": failed, "retry_job": retry_job}

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
            "status": decision,
            "recorded_at": approval["resolved_at"],
            "recorded_by": approval["decided_by"],
            "actor_type": approval["decision_actor_type"],
            "authorization_fingerprint": approval["authorization_fingerprint"],
        }
        updated["status"] = target
        if decision == "REJECTED":
            updated["error"] = {
                "code": "approval_rejected",
                "message": approval.get("decision_reason")
                or "Local operator rejected the requested action",
                "retryable": False,
                "ref": deepcopy(approval_ref),
            }
        updated["last_updated_at"] = self.clock()
        return self._save(updated)

    def _fail_job(
        self,
        job: dict[str, Any],
        *,
        code: str,
        message: str,
        retryable: bool,
        error_ref: dict[str, Any] | None = None,
        output_refs: list[dict[str, Any]] | None = None,
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
        if error_ref is not None:
            error_record["ref"] = deepcopy(error_ref)
        updated["error"] = error_record
        if job["status"] == "running":
            updated["claim_released_at"] = self.clock()
        if output_refs:
            updated["output_refs"] = [
                *updated["output_refs"],
                *deepcopy(output_refs),
            ]
        updated["last_updated_at"] = self.clock()
        return self._save(updated)

    def retry(
        self,
        job_id: str,
        *,
        next_run_at: str | None = None,
        enqueue: bool = False,
    ) -> dict[str, Any]:
        failed = self._load(job_id)
        if failed["status"] != "failed":
            raise RuntimeError("Only a failed job can be retried")
        if failed["attempt"] >= failed["max_attempts"]:
            raise RuntimeError(
                f"Job has exhausted max_attempts ({failed['max_attempts']})"
            )
        if failed.get("error", {}).get("retryable") is False:
            raise RuntimeError("Job failure is marked as non-retryable")
        existing = [
            job for job in self.list() if job.get("parent_job_id") == failed["job_id"]
        ]
        if len(existing) > 1:
            raise RuntimeError("Failed job has multiple retry children")
        if existing:
            retry_job = existing[0]
            if enqueue and retry_job["status"] == "created" and self._approval_allows_execution(retry_job):
                retry_job = self.enqueue(retry_job["job_id"])
            return retry_job

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
        )
        payload = {
            name: deepcopy(failed[name])
            for name in copied_fields
            if name in failed
        }
        payload["output_refs"] = []
        payload["created_by"] = f"retry:{failed['job_id']}"
        payload["approval_status"] = self._retry_approval_status(failed)
        retry_job = self._create_attempt(
            payload,
            attempt=failed["attempt"] + 1,
            parent_job_id=failed["job_id"],
        )
        if next_run_at is not None:
            retry_job = self.schedule(
                retry_job["job_id"], next_run_at, reason="retry_backoff"
            )
        elif enqueue:
            retry_job = self.enqueue(retry_job["job_id"])
        return retry_job

    def _create_attempt(
        self,
        payload: dict[str, Any],
        *,
        attempt: int,
        parent_job_id: str | None,
    ) -> dict[str, Any]:
        timestamp = self.clock()
        job = deepcopy(payload)
        job.setdefault("input_refs", [])
        job.setdefault("output_refs", [])
        job.setdefault("max_attempts", 1)
        job.setdefault("execution_mode", "READ_ONLY")
        job.setdefault("execution_scope", None)
        job.setdefault("dry_run", False)
        job.update(
            {
                "schema_version": 1,
                "job_id": self._unused_job_id(),
                "created_at": timestamp,
                "last_updated_at": timestamp,
                "status": "created",
                "attempt": attempt,
            }
        )
        if parent_job_id is not None:
            job["parent_job_id"] = parent_job_id
        self._validate(job)
        try:
            self.store.create(job)
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        return deepcopy(job)

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
        return self._save(updated) if save else updated

    def _save(self, job: dict[str, Any]) -> dict[str, Any]:
        self._validate(job)
        try:
            self.store.save(job)
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        return deepcopy(job)

    def _load(self, job_id: str) -> dict[str, Any]:
        try:
            job = self.store.load(job_id)
        except JobStoreError as error:
            raise RuntimeError(str(error)) from error
        self._validate(job)
        return job

    def _validate(self, job: dict[str, Any]) -> None:
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
        if job.get("approval_status") == "approved" and "approval" not in job:
            raise RuntimeError("Approved jobs require an explicit approval record")
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
            if not self.store.exists(candidate):
                return candidate
        raise RuntimeError("Could not generate a unique job ID")

    @staticmethod
    def _approval_allows_execution(job: dict[str, Any]) -> bool:
        status = job.get("approval_status")
        if status == "not_required":
            return True
        approval = job.get("approval", {})
        allowed = (
            status == "approved"
            and approval.get("status") == "APPROVED"
            and approval.get("actor_type") == "local_operator"
            and bool(approval.get("approval_id"))
        )
        if not allowed:
            return False
        if job.get("execution_mode", "READ_ONLY") == "CONTROLLED_WRITE":
            return approval.get("authorization_fingerprint") == authorization_fingerprint(
                job
            )
        return True

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

    @staticmethod
    def _retry_approval_status(job: dict[str, Any]) -> str:
        if job["approval_status"] == "not_required":
            return "not_required"
        return "required"
