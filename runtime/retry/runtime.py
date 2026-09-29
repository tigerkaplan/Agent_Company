"""Deterministic CORE-06 retry decisions and exact-attempt reservations."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from runtime.actions.models import ExecutionScope, ScopeContractError, normalize_relative_path, scope_path_contains
from runtime.budget.runtime import ExecutionBudgetRuntime
from runtime.retry.models import (
    FAILURE_CLASSES,
    RetryBinding,
    RetryContractError,
    RetryDecision,
    RetryPolicy,
    authorization_digest,
    repair_scope,
    retry_unit_id,
    retry_work_digest,
)
from runtime.retry.store import FileRetryStore, RetryStoreError


_CLASS_BY_CODE = {
    "approval_rejected": "authority_failure",
    "authorization_error": "authority_failure",
    "continuation_authority_error": "authority_failure",
    "execution_budget_error": "budget_failure",
    "execution_budget_exhausted": "budget_failure",
    "forbidden_scope": "authority_failure",
    "invalid_authorization": "authority_failure",
    "malformed_state": "malformed_state",
    "policy_rejected": "policy_failure",
    "recovery_hold": "authority_failure",
    "review_failed": "permanent_failure",
    "review_retry_exhausted": "permanent_failure",
    "review_retry_requested": "review_repair",
    "claim_lease_expired": "lease_expired",
    "execution_storage_error": "transient_storage",
    "executor_error": "transient_runtime",
    "scheduler_worker_error": "transient_runtime",
    "execution_failed": "transient_execution",
    "provider_failed": "transient_execution",
    "provider_unavailable": "transient_runtime",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


class RetryRuntime:
    """Reserve at most one canonical local retry for one failed attempt."""

    def __init__(
        self,
        store: FileRetryStore,
        *,
        budget_store: Any | None = None,
        clock: Any,
    ) -> None:
        self.store = store
        self.budget_store = budget_store
        self.execution_store = None
        self.clock = clock

    def admit_execution(self, job: Mapping[str, Any], request: Any) -> None:
        """Anchor exact work and the complete request before external delegation."""
        if job.get("retry_policy") is None:
            return
        with self.store.transaction():
            admission = self._admission(job, request)
            if job.get("retry_authorization") is not None:
                self.validate_authorization(job, for_execution=True)
                reservation = self.execution_reservation(job)
                if reservation is None or reservation["execution_id"] != request.execution_id:
                    raise RetryStoreError("Retry admission has no matching execution reservation")
                # Independent, attempt-scoped evidence precedes delegation. Unlike
                # ordinary continuation admission, it can never accept a new ID.
                self.store.anchor("attempt-admission", str(job["job_id"]), admission)
            self.store.anchor("admission", request.execution_id, admission)

    @staticmethod
    def _admission(job: Mapping[str, Any], request: Any) -> dict[str, Any]:
        return {"schema_version": 1, "job_id": job["job_id"], "attempt": job["attempt"],
                "work_digest": retry_work_digest(job), "execution_id": request.execution_id,
                "request_digest": _digest(request.to_dict()),
                "approval_required": request.approval_status != "not_required"}

    def validate_admission(self, job: Mapping[str, Any], request: Any) -> None:
        admission = self.store.load_anchor("admission", request.execution_id)
        if admission is not None:
            if not self.store._same_json(admission, self._admission(job, request)):
                raise RetryStoreError("Execution request differs from immutable admission")
            self._approval_requirement(job, admission)

    def record_runtime_failure(self, request: Any, failure_class: str) -> None:
        """Persist Worker-observed provenance, outside provider result metadata."""
        if not isinstance(failure_class, str) or failure_class not in FAILURE_CLASSES:
            raise RetryStoreError("Runtime failure class is not canonical")
        with self.store.transaction():
            self.store.anchor("runtime-failure", request.execution_id, {
                "schema_version": 1, "job_id": request.job_id, "execution_id": request.execution_id,
                "request_digest": _digest(request.to_dict()), "failure_class": failure_class,
            })

    def runtime_failure_class(self, request: Any) -> str:
        evidence = self.store.load_anchor("runtime-failure", request.execution_id)
        if evidence is None:
            raise RetryStoreError("Runtime failure provenance is missing; recovery hold is required")
        failure_class = evidence.get("failure_class")
        expected = {"schema_version": 1, "job_id": request.job_id, "execution_id": request.execution_id,
                    "request_digest": _digest(request.to_dict()), "failure_class": failure_class}
        if not isinstance(failure_class, str) or failure_class not in FAILURE_CLASSES or not self.store._same_json(evidence, expected):
            raise RetryStoreError("Runtime failure provenance is malformed or bound to other work")
        return failure_class

    @staticmethod
    def _approval_requirement(job: Mapping[str, Any], evidence: Mapping[str, Any]) -> bool:
        required = evidence.get("approval_required")
        if type(required) is not bool:
            raise RetryStoreError("Original approval policy evidence is missing or malformed")
        if required and job.get("approval_status") == "not_required":
            raise RetryStoreError("Mutable approval status weakens immutable original approval policy")
        return required

    def approval_required(self, job: Mapping[str, Any]) -> bool:
        evidence = self.store.load_anchor("failure", str(job["job_id"]))
        if evidence is None:
            raise RetryStoreError("Original approval policy has no canonical failure evidence")
        required = self._approval_requirement(job, evidence)
        # A stricter current gate remains valid, but it cannot refund the original.
        return required or job.get("approval_status") != "not_required"

    def record_failure(self, job: Mapping[str, Any]) -> None:
        """Only canonical runtime failure transitions may mint failure evidence."""
        if job.get("retry_policy") is None:
            return
        with self.store.transaction():
            work = retry_work_digest(job)
            reference = self._original_execution_ref(job)
            admission = self.store.load_anchor("admission", reference.split(":", 1)[1]) if reference else None
            if admission is not None and (admission["work_digest"] != work or admission["attempt"] != job["attempt"]):
                raise RetryStoreError("Failed work differs from immutable execution admission")
            request_digest = self._check_execution(job, reference, admission)
            approval_required = (self._approval_requirement(job, admission) if admission is not None
                                 else job.get("approval_status") != "not_required")
            self.store.anchor("failure", str(job["job_id"]), {
                "job_id": job["job_id"], "attempt": job["attempt"], "work_digest": work,
                "failed_unit_id": retry_unit_id(job), "original_execution_ref": reference,
                "request_digest": request_digest, "failure_class": self._failure_class(job),
                "progress_evidence_digest": job.get("error", {}).get("progress_evidence_digest"),
                "approval_required": approval_required,
            })

    def _check_execution(self, job: Mapping[str, Any], reference: str | None, admission: Any) -> str | None:
        if reference is None:
            return None
        if self.execution_store is None:
            raise RetryStoreError("Failed execution store is unavailable; recovery hold is required")
        from runtime.execution.models import ExecutionRequest
        from runtime.storage.execution_store import ExecutionStoreError
        try:
            record = self.execution_store.load(reference.split(":", 1)[1])
            if record.request is None and admission is None and record.result.job_id == job["job_id"]:
                if self._failure_class(job) not in {"permanent_failure", "budget_failure", "malformed_state"}:
                    raise RetryStoreError("Retry-eligible failure has no exact execution request")
                return None
            request = ExecutionRequest.from_persisted_dict(record.request).to_dict()
        except (ValueError, ExecutionStoreError) as error:
            raise RetryStoreError(f"Failed execution evidence is untrusted: {error}") from error
        for name in ("job_id", "attempt", "task", "task_class", "project_id", "agent", "skill", "workflow",
                     "capability", "provider", "risk_level", "review_required", "input_refs", "execution_mode", "execution_scope", "dry_run"):
            if request.get(name) != job.get(name, False if name == "dry_run" else "READ_ONLY" if name == "execution_mode" else None):
                raise RetryStoreError(f"Failed execution request {name} does not match exact work")
        if request["approval_status"] != "not_required" and job.get("approval_status") == "not_required":
            raise RetryStoreError("Failed work weakened the original execution request approval policy")
        checkpoint = job.get("continuation")
        for request_name, job_name in (("continuation_plan_digest", "plan_digest"), ("continuation_step_id", "current_step_id"),
                                       ("continuation_sequence", "sequence"), ("continuation_logical_job_id", "logical_job_id")):
            if request.get(request_name) != (checkpoint.get(job_name) if isinstance(checkpoint, Mapping) else None):
                raise RetryStoreError("Failed execution request differs from canonical plan/unit")
        digest = _digest(request)
        if admission is not None and (admission["execution_id"] != request["execution_id"] or admission["request_digest"] != digest):
            raise RetryStoreError("Failed execution request changed after immutable admission")
        return digest

    def reserve_execution(self, job: Mapping[str, Any], execution_id: str) -> tuple[dict[str, Any] | None, bool]:
        if job.get("retry_authorization") is None:
            return None, True
        with self.store.transaction():
            self.validate_authorization(job, for_execution=True)
            existing = self.execution_reservation(job)
            if existing is not None:
                return existing, False
            reservation = {"job_id": job["job_id"], "attempt": job["attempt"], "execution_id": execution_id,
                           "authorization_digest": job["retry_authorization"]["authorization_digest"],
                           "work_digest": retry_work_digest(job)}
            # Independent write-once consumption precedes even reservation. A
            # torn admission/reservation cannot turn this attempt back to fresh.
            self.store.anchor("consumed-attempt", str(job["job_id"]), reservation)
            self.store.anchor("execution", str(job["job_id"]), reservation)
            return reservation, True

    def execution_reservation(self, job: Mapping[str, Any]) -> dict[str, Any] | None:
        self.validate_authorization(job, for_execution=False)
        reservation = self.store.load_anchor("execution", str(job["job_id"]))
        consumed = self.store.load_anchor("consumed-attempt", str(job["job_id"]))
        admission = self.store.load_anchor("attempt-admission", str(job["job_id"]))
        if (reservation is None) != (consumed is None):
            raise RetryStoreError("Retry consumption/reservation evidence is incomplete; recovery hold is required")
        if reservation is not None and not self.store._same_json(reservation, consumed):
            raise RetryStoreError("Retry reservation differs from immutable consumed-attempt evidence")
        if reservation is None:
            # Also recognize surviving older/per-execution canonical evidence.
            # Missing attempt indexes must never mean 'never executed'.
            self.store.reject_prior_execution_evidence(str(job["job_id"]))
            if self.execution_store is not None and self.execution_store.find_for_job(str(job["job_id"])) is not None:
                raise RetryStoreError("Retry has a persisted execution but no consumption evidence; recovery hold is required")
        if admission is not None:
            if type(admission.get("schema_version")) is not int or admission.get("schema_version") != 1:
                raise RetryStoreError("Consumed retry admission schema version is invalid")
            if reservation is None:
                raise RetryStoreError("Consumed retry reservation is missing after durable admission; recovery hold is required")
            if any(admission.get(name) != value for name, value in {
                "job_id": job["job_id"], "attempt": job["attempt"], "work_digest": retry_work_digest(job),
                "execution_id": reservation["execution_id"],
            }.items()):
                raise RetryStoreError("Consumed retry admission is stale or mismatched")
            self._approval_requirement(job, admission)
        if reservation is not None and any(reservation.get(name) != value for name, value in {
            "job_id": job["job_id"], "attempt": job["attempt"], "work_digest": retry_work_digest(job),
            "authorization_digest": job["retry_authorization"]["authorization_digest"],
        }.items()):
            raise RetryStoreError("Retry execution reservation is stale or mismatched")
        return reservation

    def reserve(self, failed: Mapping[str, Any]) -> RetryDecision:
        """Persist one deterministic decision before any retry child is created."""
        try:
            binding = RetryBinding.from_dict(failed.get("retry_policy"))
            policy = self.store.load_policy(binding.to_dict())
            work_digest = retry_work_digest(failed)
            unit_id = retry_unit_id(failed)
            with self.store.transaction():
                evidence = self.store.load_anchor("failure", str(failed["job_id"]))
                if evidence is None or any(evidence.get(name) != value for name, value in {
                    "attempt": failed.get("attempt"), "work_digest": work_digest, "failed_unit_id": unit_id,
                    "original_execution_ref": self._original_execution_ref(failed),
                    "failure_class": self._failure_class(failed),
                    "progress_evidence_digest": failed.get("error", {}).get("progress_evidence_digest"),
                }.items()):
                    raise RetryStoreError("Failed work changed or lacks immutable canonical failure evidence")
                request_digest = self._check_execution(failed, evidence["original_execution_ref"],
                    self.store.load_anchor("admission", evidence["original_execution_ref"].split(":", 1)[1])
                    if evidence["original_execution_ref"] else None)
                if request_digest != evidence["request_digest"]:
                    raise RetryStoreError("Failed execution request changed after canonical failure")
                self._approval_requirement(failed, evidence)
                state = self.store.load_state(
                    binding.to_dict(), history_limit=policy.history_limit
                )
                existing = next(
                    (
                        item
                        for item in state["history"]
                        if item["source_job_id"] == failed.get("job_id")
                    ),
                    None,
                )
                if existing is not None:
                    if existing["work_digest"] != work_digest:
                        raise RetryStoreError(
                            "Persisted retry decision is stale for changed work"
                        )
                    return self._from_entry(existing)
                return self._decide_and_append(
                    failed, binding, policy, state, work_digest, unit_id
                )
        except (RetryContractError, RetryStoreError, TypeError, ValueError) as error:
            raise RetryStoreError(str(error)) from error

    def validate_authorization(self, job: Mapping[str, Any], *, for_execution: bool = True) -> None:
        """Verify historical binding; current terminal state additionally revokes execution.

        Historical jobs/results remain readable for reconciliation and structured
        stop reporting. Reading an old RETRY decision is never execution authority.
        """
        authorization = job.get("retry_authorization")
        if authorization is None:
            if job.get("parent_job_id") is not None:
                raise RetryStoreError("Retry child has no canonical retry authorization")
            return
        if not isinstance(authorization, Mapping):
            raise RetryStoreError("Retry authorization must be an object")
        expected_fields = {
            "schema_version",
            "decision_id",
            "source_job_id",
            "retry_job_id",
            "logical_job_id",
            "failed_unit_id",
            "original_execution_ref",
            "retry_sequence",
            "attempt",
            "policy_id",
            "policy_digest",
            "work_digest",
            "repair_scope",
            "authorization_digest",
        }
        if set(authorization) != expected_fields:
            raise RetryStoreError("Retry authorization has invalid fields")
        if type(authorization.get("schema_version")) is not int or authorization.get("schema_version") != 1:
            raise RetryStoreError("Retry authorization version is unsupported")
        if authorization.get("authorization_digest") != authorization_digest(authorization):
            raise RetryStoreError("Retry authorization digest does not match content")
        binding = RetryBinding.from_dict(job.get("retry_policy"))
        policy = self.store.load_policy(binding.to_dict())
        state = self.store.load_state(binding.to_dict(), history_limit=policy.history_limit)
        decision = next(
            (
                item
                for item in state["history"]
                if item["decision_id"] == authorization.get("decision_id")
            ),
            None,
        )
        if decision is None or decision.get("decision") != "RETRY":
            raise RetryStoreError("Retry authorization has no canonical RETRY decision")
        if decision.get("authorization") != dict(authorization):
            raise RetryStoreError("Retry authorization differs from canonical decision")
        if for_execution:
            if any(item["decision"] in {"STOP", "REPLAN_REQUIRED"} for item in state["history"]):
                raise RetryStoreError("Current terminal retry history revokes earlier RETRY execution authority")
            if self.store.load_anchor("failure", str(job["job_id"])) is not None:
                raise RetryStoreError("Retry attempt already has canonical failure evidence; recovery hold is required")
        comparisons = {
            "source_job_id": job.get("parent_job_id"),
            "retry_job_id": job.get("job_id"),
            "logical_job_id": binding.logical_job_id,
            "attempt": job.get("attempt"),
            "policy_id": binding.policy_id,
            "policy_digest": binding.policy_digest,
            "work_digest": retry_work_digest(job),
            "failed_unit_id": retry_unit_id(job),
        }
        for name, actual in comparisons.items():
            if authorization.get(name) != actual:
                raise RetryStoreError(f"Retry authorization {name} is stale or mismatched")
        if authorization.get("repair_scope") != repair_scope(
            job, str(authorization.get("failed_unit_id"))
        ):
            raise RetryStoreError("Retry repair scope no longer matches exact work")
        original = self.store.load_anchor("failure", str(authorization["source_job_id"]))
        if original is None:
            raise RetryStoreError("Retry lost immutable original approval policy evidence")
        self._approval_requirement(job, original)

    def validate_repair_request(
        self,
        job: Mapping[str, Any],
        *,
        unit_ids: list[str],
        paths: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> None:
        """Fail closed if a repair targets a sibling, broader path, or capability."""
        self.validate_authorization(job, for_execution=True)
        authorization = job.get("retry_authorization")
        if not isinstance(authorization, Mapping):
            raise RetryStoreError("Ordinary work has no repair authority")
        scope = authorization["repair_scope"]
        if unit_ids != [scope["failed_unit_id"]]:
            raise RetryStoreError("Repair targets work outside the failed unit")
        requested_capabilities = capabilities or [str(job.get("capability"))]
        if any(item != scope["capability"] for item in requested_capabilities):
            raise RetryStoreError("Repair broadens the authorized capability")
        requested_paths = paths or []
        allowed_paths = scope["allowed_paths"]
        if requested_paths and not allowed_paths:
            raise RetryStoreError("Repair has no controlled-write path authority")
        for requested in requested_paths:
            try:
                normalized = normalize_relative_path(requested)
                allowed_paths = [normalize_relative_path(path) for path in allowed_paths]
                parent_scope = ExecutionScope.from_dict(job.get("execution_scope") or {})
                if not parent_scope.permits(normalized):
                    raise RetryStoreError("Repair path is outside parent authorized scope")
            except ScopeContractError as error:
                raise RetryStoreError(str(error)) from error
            if not any(
                scope_path_contains(allowed, normalized, project_root=parent_scope.project_root)
                for allowed in allowed_paths
            ):
                raise RetryStoreError("Repair path is outside authorized repair scope")

    def _decide_and_append(
        self,
        failed: Mapping[str, Any],
        binding: RetryBinding,
        policy: RetryPolicy,
        state: dict[str, Any],
        work_digest: str,
        unit_id: str,
    ) -> RetryDecision:
        if failed.get("status") != "failed":
            raise RetryStoreError("Only canonical failed work may be evaluated for retry")
        attempt = failed.get("attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or not 1 <= attempt <= policy.max_total_attempts:
            raise RetryStoreError("Failed attempt is outside canonical retry policy")
        failure_class = self._failure_class(failed)
        signatures = self._signatures(failed, failure_class, work_digest)
        decision = "RETRY"
        reason = "eligible_transient_failure"

        if failed.get("approval_status") == "denied":
            decision, reason = "STOP", "approval_denied"
        elif failure_class in policy.denied_failure_classes:
            decision, reason = "STOP", f"denied_{failure_class}"
        elif failure_class not in policy.allowed_failure_classes:
            decision, reason = "STOP", "failure_class_not_allowed"
        else:
            budget_decision = self._budget_decision(failed)
            if budget_decision == "ERROR":
                decision, reason = "ERROR", "budget_state_untrusted"
            elif budget_decision == "EXHAUSTED":
                decision, reason = "STOP", "budget_exhausted"
            elif attempt >= policy.max_total_attempts:
                decision, reason = policy.exhaustion_action, "local_attempt_limit_exhausted"
            else:
                prior = state["history"]
                no_progress = self._consecutive(
                    [item["state_signature"] for item in prior],
                    signatures["state_signature"],
                )
                stagnant = self._consecutive(
                    [item["progress_signature"] for item in prior],
                    signatures["progress_signature"],
                )
                prior_window = prior[-policy.cycle_window :]
                cycle_occurrences = 1 + sum(
                    item["state_signature"] == signatures["state_signature"]
                    for item in prior_window
                )
                if policy.no_progress_threshold is not None and no_progress >= policy.no_progress_threshold:
                    decision, reason = "REPLAN_REQUIRED", "no_progress_threshold_reached"
                elif policy.stuck_threshold is not None and stagnant >= policy.stuck_threshold:
                    decision, reason = "REPLAN_REQUIRED", "stuck_threshold_reached"
                elif (
                    policy.cycle_threshold is not None
                    and cycle_occurrences >= policy.cycle_threshold
                ):
                    decision, reason = "REPLAN_REQUIRED", "retry_cycle_detected"

        decision_id = self._decision_id(
            binding, str(failed["job_id"]), attempt, work_digest
        )
        retry_job_id = (
            f"job-retry-{hashlib.sha256(decision_id.encode('utf-8')).hexdigest()[:32]}"
            if decision == "RETRY"
            else None
        )
        original_execution_ref = self._original_execution_ref(failed)
        scope = repair_scope(failed, unit_id)
        authorization = None
        if decision == "RETRY":
            authorization = {
                "schema_version": 1,
                "decision_id": decision_id,
                "source_job_id": failed["job_id"],
                "retry_job_id": retry_job_id,
                "logical_job_id": binding.logical_job_id,
                "failed_unit_id": unit_id,
                "original_execution_ref": original_execution_ref,
                "retry_sequence": attempt,
                "attempt": attempt + 1,
                "policy_id": binding.policy_id,
                "policy_digest": binding.policy_digest,
                "work_digest": work_digest,
                "repair_scope": scope,
            }
            authorization["authorization_digest"] = authorization_digest(authorization)
        entry = {
            "sequence": state["revision"] + 1,
            "decision_id": decision_id,
            "decision": decision,
            "reason_code": reason,
            "source_job_id": failed["job_id"],
            "retry_job_id": retry_job_id,
            "attempt": attempt,
            "retry_sequence": attempt,
            "failed_unit_id": unit_id,
            "original_execution_ref": original_execution_ref,
            "work_digest": work_digest,
            "failure_class": failure_class,
            **signatures,
            "repair_scope": scope,
            "authorization": authorization,
            "recorded_at": self.clock(),
        }
        self.store.append(
            binding.to_dict(),
            entry,
            history_limit=policy.history_limit,
            updated_at=str(entry["recorded_at"]),
        )
        return self._from_entry(entry)

    def _budget_decision(self, failed: Mapping[str, Any]) -> str:
        binding = failed.get("execution_budget")
        if binding is None:
            return "AVAILABLE"
        if self.budget_store is None:
            return "ERROR"
        decision = ExecutionBudgetRuntime(
            self.budget_store, wall_clock=self.clock
        ).state(binding)
        if decision.status == "ERROR":
            return "ERROR"
        return "EXHAUSTED" if decision.state.get("exhausted_dimensions") else "AVAILABLE"

    @staticmethod
    def _failure_class(failed: Mapping[str, Any]) -> str:
        error = failed.get("error")
        if not isinstance(error, Mapping):
            return "malformed_state"
        explicit = error.get("failure_class")
        if isinstance(explicit, str) and explicit in set(_CLASS_BY_CODE.values()):
            return explicit
        code = error.get("code")
        if not isinstance(code, str):
            return "malformed_state"
        if code in _CLASS_BY_CODE:
            return _CLASS_BY_CODE[code]
        # Provider-controlled retryable/prose/next_actions are deliberately ignored.
        return "permanent_failure"

    @staticmethod
    def _signatures(
        failed: Mapping[str, Any], failure_class: str, work_digest: str
    ) -> dict[str, str]:
        error = failed.get("error", {})
        progress_evidence_digest = (
            error.get("progress_evidence_digest")
            if isinstance(error, Mapping)
            else None
        )
        checkpoint = failed.get("continuation")
        progress = {
            "accepted_progress_evidence_digest": progress_evidence_digest,
            "continuation": (
                {
                    name: deepcopy(checkpoint.get(name))
                    for name in (
                        "sequence",
                        "current_step_id",
                        "completed_step_ids",
                        "remaining_step_ids",
                        "state",
                    )
                }
                if isinstance(checkpoint, Mapping)
                else None
            ),
        }
        failure_signature = _digest(
            {
                "failure_class": failure_class,
                "accepted_progress_evidence_digest": progress_evidence_digest,
            }
        )
        progress_signature = _digest(progress)
        return {
            "failure_signature": failure_signature,
            "progress_signature": progress_signature,
            "state_signature": _digest(
                {
                    "work_digest": work_digest,
                    "failure_signature": failure_signature,
                    "progress_signature": progress_signature,
                }
            ),
        }

    @staticmethod
    def _consecutive(prior: list[str], current: str) -> int:
        count = 1
        for value in reversed(prior):
            if value != current:
                break
            count += 1
        return count

    @staticmethod
    def _original_execution_ref(failed: Mapping[str, Any]) -> str | None:
        refs = [
            str(reference.get("ref"))
            for reference in failed.get("output_refs", [])
            if isinstance(reference, Mapping)
            and str(reference.get("ref", "")).startswith("runtime-execution:")
        ]
        return refs[-1] if refs else None

    @staticmethod
    def _decision_id(
        binding: RetryBinding, source_job_id: str, attempt: int, work_digest: str
    ) -> str:
        material = (
            f"{binding.policy_id}\n{binding.policy_digest}\n{source_job_id}\n"
            f"{attempt}\n{work_digest}"
        ).encode("utf-8")
        return f"retry-decision-{hashlib.sha256(material).hexdigest()[:32]}"

    @staticmethod
    def _from_entry(entry: Mapping[str, Any]) -> RetryDecision:
        return RetryDecision(
            decision=str(entry["decision"]),
            reason_code=str(entry["reason_code"]),
            decision_id=str(entry["decision_id"]),
            source_job_id=str(entry["source_job_id"]),
            failed_unit_id=str(entry["failed_unit_id"]),
            retry_sequence=int(entry["retry_sequence"]),
            retry_job_id=(
                str(entry["retry_job_id"])
                if entry.get("retry_job_id") is not None
                else None
            ),
            authorization=(
                deepcopy(entry["authorization"])
                if isinstance(entry.get("authorization"), Mapping)
                else None
            ),
            evidence={
                name: deepcopy(entry.get(name))
                for name in (
                    "failure_class",
                    "failure_signature",
                    "progress_signature",
                    "state_signature",
                    "work_digest",
                    "original_execution_ref",
                    "repair_scope",
                )
            },
        )
