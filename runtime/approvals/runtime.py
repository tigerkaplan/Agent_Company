"""Create, inspect, and resolve scoped local human approvals."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable

from runtime.actions.authorization import authorization_fingerprint
from runtime.approvals.models import (
    APPROVAL_STATUSES,
    ApprovalContractError,
    ApprovalRequest,
    ApprovalRun,
)
from runtime.approvals.store import ApprovalStoreError, FileApprovalStore
from runtime.core.jobs import JobRuntime, RuntimeError, utc_now
from runtime.git.models import GitContractError, commit_authorization_fingerprint
from runtime.git.remote_models import REMOTE_ACTIONS, remote_authorization_fingerprint
from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.review.models import ReviewResult
from runtime.review.store import FileReviewStore, ReviewStoreError
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore


class ApprovalRuntimeError(ValueError):
    """Raised when the human approval boundary cannot be satisfied safely."""


class ApprovalRuntime:
    def __init__(
        self,
        job_runtime: JobRuntime,
        store: FileApprovalStore,
        *,
        execution_store: FileExecutionStore | None = None,
        review_store: FileReviewStore | None = None,
        clock: Callable[[], str] = utc_now,
        notification_emitter: Any | None = None,
    ) -> None:
        self.job_runtime = job_runtime
        self.store = store
        self.execution_store = execution_store
        self.review_store = review_store
        self.clock = clock
        self.notification_emitter = notification_emitter

    def request_execution(
        self,
        job_id: str,
        *,
        reason: str,
        evidence_refs: tuple[dict[str, Any], ...] = (),
    ) -> ApprovalRun:
        job = self.job_runtime.show(job_id)
        if job["status"] not in {"created", "queued", "waiting_approval"}:
            raise ApprovalRuntimeError(
                "Pre-execution approval requires a created, queued, or waiting job"
            )
        refs = self._normalize_refs((*job.get("input_refs", ()), *evidence_refs))
        request = self._request(
            job=job,
            execution_id=None,
            review_id=None,
            requested_action="EXECUTE_JOB",
            reason=reason,
            evidence_refs=refs,
        )
        artifact_ref = self.artifact_ref(request.approval_id)
        try:
            updated = self.job_runtime.enter_approval_boundary(job_id, artifact_ref)
        except RuntimeError as error:
            raise ApprovalRuntimeError(str(error)) from error
        self._notify_approval_requested(request, updated)
        return ApprovalRun(request=request, artifact_ref=artifact_ref, job=updated)

    def request_review_completion(
        self,
        job_id: str,
        execution_id: str,
        review: ReviewResult,
        review_ref: dict[str, Any],
    ) -> ApprovalRun:
        job = self.job_runtime.show(job_id)
        if job["status"] != "reviewing":
            raise ApprovalRuntimeError(
                "Reviewed completion approval requires a reviewing job"
            )
        if (
            review.decision != "NEEDS_HUMAN"
            or review.job_id != job_id
            or review.execution_id != execution_id
            or review_ref.get("ref") != f"runtime-review:{review.review_id}"
        ):
            raise ApprovalRuntimeError(
                "Approval boundary does not match the normalized review result"
            )
        execution_ref = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{execution_id}",
            "description": "Immutable normalized execution record",
        }
        refs = self._normalize_refs(
            (execution_ref, review_ref, *review.evidence_refs)
        )
        request = self._request(
            job=job,
            execution_id=execution_id,
            review_id=review.review_id,
            requested_action="COMPLETE_REVIEWED_JOB",
            reason=review.reason,
            evidence_refs=refs,
        )
        self._notify_approval_requested(request, job)
        return ApprovalRun(
            request=request,
            artifact_ref=self.artifact_ref(request.approval_id),
        )

    def request_commit_change_set(
        self,
        job_id: str,
        *,
        execution_id: str,
        review_id: str,
        commit_scope: dict[str, Any],
        reason: str,
        evidence_refs: tuple[dict[str, Any], ...] = (),
    ) -> ApprovalRun:
        """Request authority for one immutable, already-reviewed Git change set."""

        job = self.job_runtime.show(job_id)
        if (
            job.get("status") != "completed"
            or job.get("execution_mode") != "CONTROLLED_WRITE"
            or job.get("dry_run", False)
        ):
            raise ApprovalRuntimeError(
                "Commit approval requires a completed non-dry-run controlled-write job"
            )
        execution_ref = f"runtime-execution:{execution_id}"
        review_ref = f"runtime-review:{review_id}"
        job_refs = {
            str(reference.get("ref"))
            for reference in job.get("output_refs", [])
            if isinstance(reference, dict)
        }
        if execution_ref not in job_refs or review_ref not in job_refs:
            raise ApprovalRuntimeError(
                "Commit approval execution or review is not bound to the completed job"
            )
        try:
            fingerprint = commit_authorization_fingerprint(commit_scope)
        except GitContractError as error:
            raise ApprovalRuntimeError(str(error)) from error
        refs = self._normalize_refs(evidence_refs)
        request = self._request(
            job=job,
            execution_id=execution_id,
            review_id=review_id,
            requested_action="COMMIT_CHANGE_SET",
            reason=reason,
            evidence_refs=refs,
            authorization=fingerprint,
            commit_scope=commit_scope,
        )
        self._notify_approval_requested(request, job)
        return ApprovalRun(
            request=request,
            artifact_ref=self.artifact_ref(request.approval_id),
            job=job,
        )

    def request_remote_action(
        self,
        job_id: str,
        *,
        execution_id: str,
        requested_action: str,
        remote_scope: dict[str, Any],
        reason: str,
        evidence_refs: tuple[dict[str, Any], ...] = (),
    ) -> ApprovalRun:
        if requested_action not in REMOTE_ACTIONS:
            raise ApprovalRuntimeError("Remote approval action is not canonical")
        job = self.job_runtime.show(job_id)
        refs = {
            str(reference.get("ref"))
            for reference in job.get("output_refs", [])
            if isinstance(reference, dict)
        }
        review_refs = sorted(ref for ref in refs if ref.startswith("runtime-review:"))
        if (
            job.get("status") != "completed"
            or job.get("execution_mode") != "CONTROLLED_WRITE"
            or job.get("dry_run", False)
            or f"runtime-execution:{execution_id}" not in refs
            or len(review_refs) != 1
        ):
            raise ApprovalRuntimeError(
                "Remote approval requires one completed reviewed controlled-write job"
            )
        try:
            fingerprint = remote_authorization_fingerprint(
                requested_action, remote_scope
            )
        except GitContractError as error:
            raise ApprovalRuntimeError(str(error)) from error
        request = self._request(
            job=job,
            execution_id=execution_id,
            review_id=review_refs[0].split(":", 1)[1],
            requested_action=requested_action,
            reason=reason,
            evidence_refs=self._normalize_refs(evidence_refs),
            authorization=fingerprint,
            remote_scope=remote_scope,
        )
        self._notify_approval_requested(request, job)
        return ApprovalRun(
            request=request,
            artifact_ref=self.artifact_ref(request.approval_id),
            job=job,
        )

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in APPROVAL_STATUSES:
            raise ApprovalRuntimeError(f"Unknown approval status: {status}")
        try:
            return [request.to_dict() for request in self.store.list(status)]
        except ApprovalStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error

    def show(self, approval_id: str) -> dict[str, Any]:
        request = self._load(approval_id)
        try:
            job = self.job_runtime.show(request.job_id)
        except RuntimeError as error:
            raise ApprovalRuntimeError(str(error)) from error
        result: dict[str, Any] = {
            "approval": request.to_dict(),
            "job": {
                key: job.get(key)
                for key in (
                    "job_id",
                    "task",
                    "status",
                    "risk_level",
                    "approval_status",
                    "attempt",
                    "max_attempts",
                )
            },
        }
        result["job"]["task"] = bound_text(
            sanitize_provider_text(result["job"].get("task")), 4000
        )
        if request.execution_id is not None:
            result["execution"] = self._execution_summary(request.execution_id)
        if request.review_id is not None:
            result["review"] = self._review_summary(request.review_id)
        return result

    def resolve(
        self,
        approval_id: str,
        *,
        decision: str,
        decided_by: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        request = self._load(approval_id)
        if request.requested_action == "COMMIT_CHANGE_SET" or request.requested_action in REMOTE_ACTIONS:
            return self._resolve_commit(
                request,
                decision=decision,
                decided_by=decided_by,
                reason=reason,
            )
        if request.status != "PENDING":
            if decision != request.status:
                raise ApprovalRuntimeError(
                    f"Approval is already resolved as {request.status}"
                )
            self._ensure_boundary_linked(request)
            if decision == request.status:
                try:
                    self.job_runtime.validate_approval_resolution(
                        request.to_dict(), self.artifact_ref(request.approval_id)
                    )
                    job = self.job_runtime.apply_approval_resolution(
                        request.to_dict(), self.artifact_ref(request.approval_id)
                    )
                    return {"approval": request.to_dict(), "job": job}
                except RuntimeError:
                    pass
            raise ApprovalRuntimeError(
                f"Approval is already resolved as {request.status}"
            )
        self._ensure_boundary_linked(request)
        actor = self._bounded_required(decided_by, 200, "Approval actor")
        decision_reason = self._bounded_optional(reason, 2000)
        try:
            self.job_runtime.validate_approval_resolution(
                request.to_dict(), self.artifact_ref(request.approval_id)
            )
            resolved = request.resolve(
                decision,
                decided_by=actor,
                resolved_at=self.clock(),
                reason=decision_reason,
            )
            self.store.resolve(resolved)
            job = self.job_runtime.apply_approval_resolution(
                resolved.to_dict(), self.artifact_ref(resolved.approval_id)
            )
        except (ApprovalContractError, ApprovalStoreError, RuntimeError) as error:
            raise ApprovalRuntimeError(str(error)) from error
        return {"approval": resolved.to_dict(), "job": job}

    def _ensure_boundary_linked(self, request: ApprovalRequest) -> None:
        try:
            job = self.job_runtime.show(request.job_id)
            approval_ref = self.artifact_ref(request.approval_id)
            applied = job.get("approval", {})
            if request.requested_action == "COMMIT_CHANGE_SET" or request.requested_action in REMOTE_ACTIONS:
                self._validate_commit_boundary(request)
                return
            if (
                applied.get("approval_id") == request.approval_id
                and applied.get("status") == request.status
            ):
                return
            if job["status"] == "waiting_approval":
                return
            if (
                request.requested_action == "EXECUTE_JOB"
                and job["status"] in {"created", "queued"}
            ):
                self.job_runtime.enter_approval_boundary(
                    request.job_id, approval_ref
                )
                return
            if (
                request.requested_action == "COMPLETE_REVIEWED_JOB"
                and job["status"] == "reviewing"
                and request.review_id is not None
            ):
                if self.review_store is None:
                    raise ApprovalRuntimeError(
                        "Review store is required to restore an approval boundary"
                    )
                review_record = self.review_store.load(request.review_id).get(
                    "result", {}
                )
                if (
                    review_record.get("decision") != "NEEDS_HUMAN"
                    or review_record.get("job_id") != request.job_id
                    or review_record.get("execution_id") != request.execution_id
                ):
                    raise ApprovalRuntimeError(
                        "Persisted review does not match the approval boundary"
                    )
                review_ref = {
                    "ref_type": "review",
                    "ref": f"runtime-review:{request.review_id}",
                    "description": "Normalized review decision and bounded evidence package",
                }
                self.job_runtime.apply_review_decision(
                    request.job_id,
                    decision="NEEDS_HUMAN",
                    reason=request.reason,
                    review_ref=review_ref,
                    approval_ref=approval_ref,
                )
        except (RuntimeError, ReviewStoreError) as error:
            raise ApprovalRuntimeError(str(error)) from error

    def _request(
        self,
        *,
        job: dict[str, Any],
        execution_id: str | None,
        review_id: str | None,
        requested_action: str,
        reason: str,
        evidence_refs: tuple[dict[str, Any], ...],
        authorization: str | None = None,
        commit_scope: dict[str, Any] | None = None,
        remote_scope: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        fingerprint = authorization or authorization_fingerprint(job)
        approval_id = self._approval_id(
            str(job["job_id"]), execution_id, review_id, requested_action, fingerprint
        )
        if self.store.exists(approval_id):
            existing = self._load(approval_id)
            if existing.status != "PENDING":
                raise ApprovalRuntimeError(
                    f"Approval boundary is already resolved as {existing.status}"
                )
            return existing
        try:
            pending_for_job = [
                item
                for item in self.store.list("PENDING")
                if item.job_id == job["job_id"]
            ]
        except ApprovalStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error
        if pending_for_job:
            raise ApprovalRuntimeError(
                "Job already has a different unresolved approval request"
            )
        request = ApprovalRequest(
            approval_id=approval_id,
            job_id=str(job["job_id"]),
            execution_id=execution_id,
            review_id=review_id,
            status="PENDING",
            reason=self._bounded_required(reason, 2000, "Approval reason"),
            risk_level=str(job["risk_level"]),
            requested_action=requested_action,
            evidence_refs=evidence_refs,
            requested_at=self.clock(),
            execution_mode=str(job.get("execution_mode", "READ_ONLY")),
            execution_scope=deepcopy(job.get("execution_scope")),
            authorization_fingerprint=fingerprint,
            commit_scope=deepcopy(commit_scope),
            remote_scope=deepcopy(remote_scope),
            dry_run=bool(job.get("dry_run", False)),
        )
        try:
            self.store.create(request)
        except ApprovalStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error
        return request

    def _notify_approval_requested(
        self, request: ApprovalRequest, job: dict[str, Any]
    ) -> None:
        if self.notification_emitter is not None:
            try:
                self.notification_emitter.approval_requested(
                    request.to_dict(), deepcopy(job)
                )
            except Exception:
                # A pending approval remains authoritative if notification fails.
                pass

    def _resolve_commit(
        self,
        request: ApprovalRequest,
        *,
        decision: str,
        decided_by: str,
        reason: str | None,
    ) -> dict[str, Any]:
        self._validate_commit_boundary(request)
        if request.status != "PENDING":
            if decision == request.status:
                return {
                    "approval": request.to_dict(),
                    "job": self.job_runtime.show(request.job_id),
                }
            raise ApprovalRuntimeError(
                f"Approval is already resolved as {request.status}"
            )
        actor = self._bounded_required(decided_by, 200, "Approval actor")
        decision_reason = self._bounded_optional(reason, 2000)
        try:
            resolved = request.resolve(
                decision,
                decided_by=actor,
                resolved_at=self.clock(),
                reason=decision_reason,
            )
            self.store.resolve(resolved)
        except (ApprovalContractError, ApprovalStoreError) as error:
            raise ApprovalRuntimeError(str(error)) from error
        return {
            "approval": resolved.to_dict(),
            "job": self.job_runtime.show(request.job_id),
        }

    def _validate_commit_boundary(self, request: ApprovalRequest) -> None:
        try:
            job = self.job_runtime.show(request.job_id)
            if request.requested_action == "COMMIT_CHANGE_SET":
                expected = commit_authorization_fingerprint(request.commit_scope or {})
            else:
                expected = remote_authorization_fingerprint(
                    request.requested_action, request.remote_scope or {}
                )
        except (RuntimeError, GitContractError) as error:
            raise ApprovalRuntimeError(str(error)) from error
        refs = {
            str(reference.get("ref"))
            for reference in job.get("output_refs", [])
            if isinstance(reference, dict)
        }
        if (
            job.get("status") != "completed"
            or job.get("execution_mode") != "CONTROLLED_WRITE"
            or job.get("dry_run", False)
            or f"runtime-execution:{request.execution_id}" not in refs
            or f"runtime-review:{request.review_id}" not in refs
            or request.authorization_fingerprint != expected
        ):
            raise ApprovalRuntimeError(
                "Commit approval is stale or no longer matches completed job evidence"
            )

    def _load(self, approval_id: str) -> ApprovalRequest:
        try:
            return self.store.load(approval_id)
        except ApprovalStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error

    def _execution_summary(self, execution_id: str) -> dict[str, Any]:
        if self.execution_store is None:
            return {"execution_id": execution_id, "artifact_loaded": False}
        try:
            result = self.execution_store.load(execution_id).get("result", {})
        except ExecutionStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error
        summary = {
            key: result.get(key)
            for key in ("execution_id", "job_id", "status", "summary", "provider")
        }
        summary["summary"] = bound_text(
            sanitize_provider_text(summary.get("summary")), 4000
        )
        return summary

    def _review_summary(self, review_id: str) -> dict[str, Any]:
        if self.review_store is None:
            return {"review_id": review_id, "artifact_loaded": False}
        try:
            result = self.review_store.load(review_id).get("result", {})
        except ReviewStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error
        summary = {
            key: result.get(key)
            for key in (
                "review_id",
                "job_id",
                "execution_id",
                "reviewer",
                "review_provider",
                "same_provider_review",
                "decision",
                "reason",
                "evidence_refs",
            )
        }
        summary["reason"] = bound_text(
            sanitize_provider_text(summary.get("reason")), 2000
        )
        evidence = result.get("evidence_refs", [])
        summary["evidence_refs"] = list(
            self._normalize_refs(tuple(evidence))
        ) if isinstance(evidence, list) else []
        return summary

    @staticmethod
    def artifact_ref(approval_id: str) -> dict[str, Any]:
        return {
            "ref_type": "approval",
            "ref": f"runtime-approval:{approval_id}",
            "description": "Scoped human approval request and decision",
        }

    @staticmethod
    def _approval_id(
        job_id: str,
        execution_id: str | None,
        review_id: str | None,
        requested_action: str,
        authorization_fingerprint: str,
    ) -> str:
        boundary = json.dumps(
            [
                job_id,
                execution_id,
                review_id,
                requested_action,
                authorization_fingerprint,
            ],
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest = hashlib.sha256(boundary.encode("utf-8")).hexdigest()[:32]
        return f"approval-{digest}"

    @classmethod
    def _normalize_refs(
        cls, references: tuple[dict[str, Any], ...]
    ) -> tuple[dict[str, Any], ...]:
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for reference in references:
            if not isinstance(reference, dict):
                continue
            ref_type = cls._bounded_required(
                str(reference.get("ref_type", "")), 100, "Evidence ref_type"
            )
            ref = cls._bounded_required(
                str(reference.get("ref", "")), 2048, "Evidence ref"
            )
            key = (ref_type, ref)
            if key in seen:
                continue
            item = {"ref_type": ref_type, "ref": ref}
            description = cls._bounded_optional(reference.get("description"), 1000)
            if description:
                item["description"] = description
            normalized.append(item)
            seen.add(key)
            if len(normalized) == 64:
                break
        return tuple(deepcopy(normalized))

    @staticmethod
    def _bounded_required(value: Any, limit: int, label: str) -> str:
        normalized = bound_text(sanitize_provider_text(value), limit).strip()
        if not normalized:
            raise ApprovalRuntimeError(f"{label} must be non-empty")
        return normalized

    @staticmethod
    def _bounded_optional(value: Any, limit: int) -> str | None:
        if value is None:
            return None
        normalized = bound_text(sanitize_provider_text(value), limit).strip()
        return normalized or None
