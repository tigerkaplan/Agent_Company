"""Create, inspect, and resolve scoped local human approvals."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from runtime.actions.authorization import authorization_fingerprint
from runtime.approvals.models import (
    APPROVAL_STATUSES,
    ApprovalContractError,
    ApprovalRequest,
    ApprovalRun,
    approval_boundary_id,
)
from runtime.approvals.store import ApprovalStoreError, FileApprovalStore
from runtime.continuation.models import ContinuationPolicy
from runtime.core.jobs import JobRuntime, RuntimeError, utc_now
from runtime.git.models import GitContractError, commit_authorization_fingerprint
from runtime.git.remote_models import REMOTE_ACTIONS, remote_authorization_fingerprint
from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.review.models import ReviewResult
from runtime.review.store import FileReviewStore, ReviewStoreError
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore


class ApprovalRuntimeError(ValueError):
    """Raised when the human approval boundary cannot be satisfied safely."""


class ApprovalReconciliationRequired(ApprovalRuntimeError):
    """Raised when approval state persisted but its downstream transition did not."""


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
        learning=None,
    ) -> None:
        self.job_runtime = job_runtime
        self.store = store
        self.execution_store = execution_store
        self.review_store = review_store
        self.clock = clock
        self.notification_emitter = notification_emitter
        if learning is not None:
            from runtime.memory.learning import LearningInstallation
            if type(learning) is not LearningInstallation:
                raise ApprovalRuntimeError("Explicit canonical learning installation required")
            learning.validate()
        self.learning = learning
        self.job_runtime.configure_authority_stores(store, execution_store)
        if review_store is not None:
            self.job_runtime.review_store = review_store

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
            review.decision not in ({"NEEDS_HUMAN", "PASS"}
                if job["task_contract"]["approval_requirements"]["completion"] else {"NEEDS_HUMAN"})
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

    def request_human_condition(
        self,
        job_id: str,
        execution_id: str,
        *,
        reason: str,
        execution_ref: dict[str, Any],
        output_refs: list[dict[str, Any]],
        continuation: Any = None,
    ) -> ApprovalRun:
        """Request a decision for one direct execution human condition."""
        job = self.job_runtime.show(job_id)
        if job["status"] != "running":
            raise ApprovalRuntimeError(
                "Direct human-condition resolution requires a running job"
            )
        candidate = deepcopy(job)
        candidate["output_refs"] = [*candidate["output_refs"], *deepcopy(output_refs)]
        if continuation is not None:
            candidate["continuation"] = continuation
        request = self._request(
            job=candidate,
            execution_id=execution_id,
            review_id=None,
            requested_action="RESOLVE_HUMAN_CONDITION",
            reason=reason,
            evidence_refs=self._normalize_refs((execution_ref,)),
        )
        artifact_ref = self.artifact_ref(request.approval_id)
        try:
            updated = self.job_runtime.record_execution_needs_human(
                job_id,
                output_refs,
                approval_ref=artifact_ref,
                continuation=continuation,
            )
        except RuntimeError as error:
            raise ApprovalRuntimeError(str(error)) from error
        self._notify_approval_requested(request, updated)
        return ApprovalRun(request=request, artifact_ref=artifact_ref, job=updated)

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
                    "project_id",
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
        if request.requested_action == "SET_LEARNING_DISPOSITION":
            return self.resolve_learning(approval_id, decision=decision, decided_by=decided_by, reason=reason)
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
            try:
                self._ensure_boundary_linked(request)
                self.job_runtime.validate_approval_resolution(
                    request.to_dict(), self.artifact_ref(request.approval_id)
                )
                job = self.job_runtime.apply_approval_resolution(
                    request.to_dict(), self.artifact_ref(request.approval_id)
                )
            except (ApprovalRuntimeError, RuntimeError) as error:
                try:
                    current_job = self.job_runtime.show(request.job_id)
                except RuntimeError:
                    current_job = None
                if current_job is not None and self._resolution_is_applied(
                    request, current_job
                ):
                    raise ApprovalRuntimeError(
                        f"Approval is already resolved as {request.status}"
                    ) from error
                raise ApprovalReconciliationRequired(
                    f"Approval {request.approval_id} is {request.status} but its "
                    "downstream transition requires reconciliation"
                ) from error
            self._notify_approval_resolved(request, job)
            return {"approval": request.to_dict(), "job": job}
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
        except (ApprovalContractError, RuntimeError) as error:
            raise ApprovalRuntimeError(str(error)) from error
        try:
            self.store.resolve(resolved)
        except ApprovalStoreError as error:
            raise ApprovalRuntimeError(str(error)) from error
        try:
            job = self.job_runtime.apply_approval_resolution(
                resolved.to_dict(), self.artifact_ref(resolved.approval_id)
            )
        except RuntimeError as error:
            raise ApprovalReconciliationRequired(
                f"Approval {resolved.approval_id} is {resolved.status} but its "
                "downstream transition requires reconciliation"
            ) from error
        self._notify_approval_resolved(resolved, job)
        return {"approval": resolved.to_dict(), "job": job}

    def reconcile(
        self,
        approval_id: str,
        *,
        decision: str,
        decided_by: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Finish or confirm one interrupted canonical approval transition."""
        request = self._load(approval_id)
        if request.requested_action == "SET_LEARNING_DISPOSITION":
            raise ApprovalReconciliationRequired("Learning reconciliation is read-only; use check_learning")
        if request.status == "PENDING":
            return self.resolve(
                approval_id,
                decision=decision,
                decided_by=decided_by,
                reason=reason,
            )
        if request.status != decision:
            raise ApprovalRuntimeError(
                f"Approval is already resolved as {request.status}"
            )
        try:
            job = self.job_runtime.show(request.job_id)
        except RuntimeError as error:
            raise ApprovalReconciliationRequired(
                f"Approval {request.approval_id} is {request.status} but its "
                "downstream transition requires reconciliation"
            ) from error
        if self._resolution_is_applied(request, job):
            self._notify_approval_resolved(request, job)
            return {"approval": request.to_dict(), "job": job}
        return self.resolve(
            approval_id,
            decision=decision,
            decided_by=decided_by,
            reason=reason,
        )

    def _learning_genesis(self):
        from runtime.memory.learning import LearningError, LearningInstallation
        if type(self.learning) is not LearningInstallation or self.execution_store is None or self.review_store is None:
            raise LearningError("Explicit learning source and canonical authority owners required")
        self.learning.validate()
        jobs = self.job_runtime
        if not jobs.progress.store.path(self.learning.logical_job_id).is_file():
            from runtime.memory.learning import LearningError
            raise LearningError("Genesis must bind an existing canonical logical-job journal")
        return {"schema_version": 1, "project_id": self.learning.project_id,
            "project_root": str(self.learning.project_root), "logical_job_id": self.learning.logical_job_id,
            "owners": {"job_root": str(jobs.store.root.resolve()),
                "approval_root": str(self.store.root.resolve()),
                "execution_root": str(self.execution_store.root.resolve()),
                "review_root": str(self.review_store.root.resolve()),
                "task_root": str(jobs.task_contract_store.root.resolve()),
                "progress_root": str(jobs.progress.store.root.resolve()),
                "memory_source": self.learning.memory_source}}

    def _learning_events(self):
        return self.job_runtime.progress.store.read(self.learning.logical_job_id)

    def _learning_identity(self, identity):
        from runtime.core.task_contract import digest
        return "learning-" + digest(self.learning.project_id)[:24] + "-" + identity

    def _learning_observe(self, kind, identity, value, job_id):
        from runtime.progress.models import ProgressEvent
        from runtime.core.task_contract import digest
        self.job_runtime.progress.store.append(ProgressEvent(kind, self.learning.logical_job_id,
            job_id, execution_id=self._learning_identity(identity), evidence_id=digest(value)))

    def _learning_witness(self, kind, identity, value, job_id):
        from runtime.core.task_contract import digest
        from runtime.memory.learning import LearningError
        found = [e for e in self._learning_events() if e.event_type == kind
                 and e.execution_id == self._learning_identity(identity)]
        if len(found) != 1 or found[0].evidence_id != digest(value) or found[0].job_id != job_id:
            raise LearningError("Learning continuity observation missing or contradictory")

    def _learning_pair(self, approval_id, stage):
        from runtime.memory.learning import read_record
        # Same canonical execution artifacts and format, with narrower read bounds.
        anchor = read_record(self.execution_store._decision_path(approval_id, stage, "anchor"))
        witness = read_record(self.execution_store._decision_path(approval_id, stage, "witness"))
        if anchor != witness:
            from runtime.memory.learning import LearningError
            raise LearningError("Partial learning action evidence pair")
        return anchor

    def _learning_state(self, *, initialize=False, reservation_id=None):
        from runtime.memory.learning import LearningError, empty_index, fields, number, MAX_LINEAGES, MAX_TRANSITIONS
        from runtime.core.task_contract import digest
        g = self._learning_genesis()
        project = self.learning.project_id
        prefix = self._learning_identity("")
        events = [e for e in self._learning_events() if (e.execution_id or "").startswith(prefix)]
        directory = self.store._learning_path(project, "genesis").parent
        if not self.store._learning_path(project, "genesis").exists():
            # Only an explicit exact initialization request can use independently
            # observed absence. The existing fixed journal must already be readable.
            if not initialize:
                raise LearningError("Missing genesis never means new project")
            allowed = {"reservation.json"}
            if directory.exists() and set(p.name for p in directory.iterdir()) - allowed:
                raise LearningError("Partial learning genesis requires explicit recovery")
            for event in events:
                if event.event_type not in {"learning_reservation_observed", "learning_reservation_closed"}:
                    raise LearningError("Namespace has retained application continuity; cannot initialize")
                identity = event.execution_id[len(prefix):]
                old = self.store.load(identity, require_canonical=True)
                if old.requested_action != "SET_LEARNING_DISPOSITION" or old.learning_scope["intent"]["genesis"] != g:
                    raise LearningError("Foreign initialization continuity")
                if identity != reservation_id and old.status != "REJECTED":
                    raise LearningError("Unresolved namespace initialization request")
            index = empty_index(g)
        else:
            if initialize:
                raise LearningError("Existing learning namespace cannot be initialized again")
            actual = self.store._read_learning(project, "genesis")
            if actual != g:
                raise LearningError("Learning genesis owner/root binding changed")
            index = self.store._read_learning(project, "index")
            fields(index, "schema_version genesis_digest revision heads history")
            number(index["revision"], minimum=0, maximum=MAX_TRANSITIONS)
            if (index["schema_version"] != 1 or type(index["schema_version"]) is not int
                    or index["genesis_digest"] != digest(g) or type(index["heads"]) is not dict
                    or len(index["heads"]) > MAX_LINEAGES or type(index["history"]) is not list
                    or len(index["history"]) != index["revision"] or index["revision"] == 0):
                raise LearningError("Learning index missing, incomplete or over capacity")
            current = empty_index(g)
            expected_events = set()
            for revision, entry in enumerate(index["history"], 1):
                fields(entry, "approval_id transition_digest application_digest")
                approved = self.store.load(entry["approval_id"], require_canonical=True)
                if approved.status != "APPROVED" or approved.requested_action != "SET_LEARNING_DISPOSITION":
                    raise LearningError("Index lacks canonical approved disposition")
                s = approved.learning_scope
                if (s["intent"]["genesis"] != g or s["intent"]["expected_revision"] != revision - 1
                        or s["intent"]["expected_index_digest"] != digest(current)):
                    raise LearningError("Broken learning revision chain")
                record = self.store._read_learning(project, "transition-" + str(revision))
                policy = self._learning_pair(approved.approval_id, "action-policy")
                if (any(self.execution_store._decision_path(approved.approval_id, "action-failure", suffix).exists()
                        for suffix in ("anchor", "witness"))
                        or any(e.event_type == "decision_result_observed"
                            and e.execution_id == "action-failure-" + digest(approved.approval_id)
                            for e in self._learning_events())):
                    raise LearningError("Retained application failure; explicit recovery required")
                if policy["approval_received"] != approved.to_dict() or policy["request"]["scope"] != s:
                    raise LearningError("Disposition action differs from approval")
                self.execution_store._verify_observation(policy, "decision_intent_observed", approved.approval_id, digest(policy))
                claim = {"schema_version": 1, "action_digest": digest(policy)}
                if self._learning_pair(approved.approval_id, "action-effect") != claim:
                    raise LearningError("Missing single-use learning consumption")
                self.execution_store._verify_observation(policy, "decision_consumption_observed",
                    "consumed-" + digest({"execution_id": approved.approval_id, "stage": "action-effect"}), digest(claim))
                expected = self._learning_transition(approved, current, policy)
                if record != expected or entry != expected["after"]["history"][-1]:
                    raise LearningError("Disposition transition or index rolled back")
                application = expected["application"]
                result = {"schema_version": 1, "policy_digest": digest(policy),
                    "result_digest": digest(application), "effect_performed": True, "evidence": application}
                if self._learning_pair(approved.approval_id, "action-result") != result:
                    raise LearningError("Disposition application is unconfirmed")
                self.execution_store._verify_observation(policy, "decision_result_observed", approved.approval_id, digest(result))
                self._learning_witness("learning_transition_observed", str(revision), record, approved.job_id)
                self._learning_witness("learning_application_observed", str(revision), application, approved.job_id)
                if revision == 1:
                    self._learning_witness("learning_genesis_observed", "genesis", g, approved.job_id)
                current = expected["after"]
                expected_events.add(self._learning_identity(str(revision)))
            if current != index:
                raise LearningError("Index differs from confirmed current disposition chain")
            if any(e.event_type in {"learning_transition_observed", "learning_application_observed"}
                   and e.execution_id not in expected_events for e in events):
                raise LearningError("Index omits retained transition observation")
            allowed = {"genesis.json", "index.json", "reservation.json",
                       *["transition-" + str(i) + ".json" for i in range(1, index["revision"] + 1)]}
            if set(p.name for p in directory.iterdir()) - allowed:
                raise LearningError("Unconfirmed learning artifacts require recovery")
        reservation_path = self.store._learning_path(project, "reservation")
        requests = [e for e in events if e.event_type == "learning_reservation_observed"]
        if reservation_path.exists():
            reserved = self.store._read_learning(project, "reservation")
            fields(reserved, "approval_id scope_digest status")
            request = self.store.load(reserved["approval_id"], require_canonical=True)
            original = {**reserved, "status": "PENDING"}
            if digest(request.learning_scope) != reserved["scope_digest"]:
                raise LearningError("Reservation differs from immutable approval")
            self._learning_witness("learning_reservation_observed", request.approval_id, original, request.job_id)
            if reserved["status"] == "PENDING":
                if request.approval_id != reservation_id:
                    raise LearningError("Unresolved learning reservation; planning held")
            elif reserved["status"] in {"REJECTED", "APPLIED"}:
                if (reserved["status"] == "REJECTED" and request.status != "REJECTED"
                        or reserved["status"] == "APPLIED" and (not index["history"]
                        or index["history"][-1]["approval_id"] != request.approval_id)):
                    raise LearningError("Reservation closure lacks confirmed evidence")
                self._learning_witness("learning_reservation_closed", request.approval_id, reserved, request.job_id)
            else:
                raise LearningError("Unknown learning reservation state")
            # Retained requests cannot disappear while a later reservation wins.
            for event in requests:
                identity = event.execution_id[len(prefix):]
                if identity != reserved["approval_id"]:
                    old = self.store.load(identity, require_canonical=True)
                    if old.status == "PENDING" or (old.status == "APPROVED"
                        and identity not in {e["approval_id"] for e in index["history"]}):
                        raise LearningError("Unconfirmed competing learning request")
        elif requests:
            raise LearningError("Missing reservation; explicit recovery required")
        return index

    def _learning_transition(self, request, before, policy):
        from runtime.core.task_contract import digest
        from runtime.memory.learning import transition_heads
        s, i = request.learning_scope, request.learning_scope["intent"]
        p, revision = i["proposal"], before["revision"] + 1
        heads = transition_heads(i, before)
        if i["operation"] != "REVOKE":
            heads[p["constraint_id"]]["approval_id"] = request.approval_id
        transition = {"schema_version": 1, "revision": revision, "before_digest": digest(before),
            "genesis_digest": before["genesis_digest"], "operation": i["operation"],
            "scope_digest": digest(s), "approval_digest": digest(request.to_dict()),
            "consumption_digest": digest({"schema_version": 1, "action_digest": digest(policy)}),
            "heads": deepcopy(heads)}
        application = {"status": "CONFIRMED", "approval_id": request.approval_id,
            "revision": revision, "transition_digest": digest(transition)}
        # Only changed heads advance; retired predecessor heads retain the positive
        # approval identity, with withdrawal witnesses retained in project history.
        for key, head in heads.items():
            if head != before["heads"].get(key):
                heads[key] = {**head, "revision": revision, "transition_digest": digest(transition),
                              "application_digest": digest(application)}
        after = {**before, "revision": revision, "heads": heads,
            "history": [*before["history"], {"approval_id": request.approval_id,
                "transition_digest": digest(transition), "application_digest": digest(application)}]}
        return {"transition": transition, "before": before, "after": after, "application": application}

    def prepare_learning_scope(self, job_id, output_path):
        from runtime.memory.learning import learning_inspection, LearningScope, LearningIntent, charge
        from runtime.core.task_contract import digest
        from runtime.core.capability_governance import evaluate
        from runtime.context.contracts import RepositoryReader
        import json
        with learning_inspection():
            self._learning_genesis()
            job = self.job_runtime.show(job_id)
            proof = job.get("task_completion") or {}
            raw = self.learning.read_output(output_path)
            i = LearningIntent.from_dict(json.loads(raw)).to_dict()
            execution = self.execution_store.load(proof["execution_id"], require_authority=True)
            review_id = proof["review_ref"].split(":", 1)[1]
            review = self.review_store.load(review_id, require_authority=True)
            s = {"schema_version": 1, "action": "SET_LEARNING_DISPOSITION", "intent": i,
                "preparation": {"job_id": job_id, "attempt": job["attempt"],
                    "execution_id": proof["execution_id"], "contract_digest": digest(job["task_contract"]),
                    "execution_digest": digest(execution.to_dict()), "completion_digest": digest(proof),
                    "output_path": output_path, "output_digest": __import__('hashlib').sha256(raw).hexdigest()},
                "review": {"review_id": review_id, "digest": digest(review), "reviewer": review["result"]["reviewer"]},
                "governance": evaluate(job)}
            scope = LearningScope.from_dict(s).to_dict()
            self._validate_learning_scope(scope)
            return scope

    def _validate_learning_scope(self, scope, *, reservation_id=None, planning=False):
        from runtime.memory.learning import (LearningScope, LearningError, learning_inspection, coverage_name,
            package_coverage_name, review_content, packaged_review_evidence, overlap, encoded, charge)
        from runtime.core.task_contract import digest, verify_completion
        from runtime.core.capability_governance import evaluate, policy
        from runtime.context.contracts import RepositoryReader
        with learning_inspection():
            s = LearningScope.from_dict(scope).to_dict(); i = s["intent"]; p = s["preparation"]
            if i["genesis"] != self._learning_genesis():
                raise LearningError("Learning scope redirects canonical owners")
            job = self.job_runtime.show(p["job_id"])
            if (job["status"] != "completed" or not job["review_required"]
                    or job.get("project_id") != self.learning.project_id or job["attempt"] != p["attempt"]
                    or "graph_binding" in job or "graph_plan" in job):
                raise LearningError("Learning requires exact completed foreground preparation")
            self.job_runtime.task_contract_store.verify(job)
            verify_completion(self.job_runtime, job, inspection=True)
            proof = job["task_completion"]
            if (digest(proof) != p["completion_digest"] or digest(job["task_contract"]) != p["contract_digest"]
                    or proof["execution_id"] != p["execution_id"]):
                raise LearningError("Learning preparation receipt changed")
            execution = self.execution_store.load(p["execution_id"], require_authority=True)
            review = self.review_store.load(s["review"]["review_id"], require_authority=True)
            charge(encoded(execution.to_dict())); charge(encoded(review))
            result = review["result"]
            ref = {"ref_type": "file", "ref": p["output_path"]}
            checks = result.get("deterministic_checks", [])
            contract = job["task_contract"]
            executor = self.execution_store._decision_pair(p["execution_id"], "intent")["executor"]
            if (digest(execution.to_dict()) != p["execution_digest"] or digest(review) != s["review"]["digest"]
                    or result["reviewer"] != s["review"]["reviewer"] or result["reviewer"] in {executor, job["agent"]}
                    or result["job_id"] != job["job_id"] or result["execution_id"] != p["execution_id"]
                    or result["decision"] != "PASS" or proof["review_ref"] != "runtime-review:" + result["review_id"]
                    or not checks or any(c["status"] != "PASS" for c in checks)
                    or not any(c["name"] == coverage_name(i) and c["status"] == "PASS" for c in checks)
                    or not any(r.get("ref_type") == "file" and r.get("ref") == p["output_path"] for r in result["evidence_refs"])
                    or ref not in [{"ref_type": r["ref_type"], "ref": r["ref"]} for r in contract["expected_outputs"]]
                    or not any(e["path"] == p["output_path"] and e["sha256"] == p["output_digest"] for e in contract["required_evidence"])):
                raise LearningError("Incomplete independent learning review or output coverage")
            raw = self.learning.read_output(p["output_path"])
            if __import__('hashlib').sha256(raw).hexdigest() != p["output_digest"] or __import__('json').loads(raw) != i:
                raise LearningError("Substituted learning proposal output")
            if evaluate(job) != s["governance"]:
                raise LearningError("Learning policy/certificate binding changed")
            cert = policy()["certificates"].get(job["capability"])
            if cert is None or cert["status"] != "certified" or "LOCAL_WRITE" not in cert["profiles"]:
                raise LearningError("Learning action exceeds certified local-write ceiling")
            bodies = self.learning.check_evidence(i["proposal"], now=self.clock())
            content = review_content(i, bodies)
            if (not any(c["name"] == package_coverage_name(i, content) and c["status"] == "PASS" for c in checks)
                    or packaged_review_evidence(ref, content) not in review.get("package", "")):
                raise LearningError("Independent review does not cover the actual packaged learning evidence")
            if planning:
                return
            before = self._learning_state(initialize=i["initialize"], reservation_id=reservation_id)
            if before["revision"] != i["expected_revision"] or digest(before) != i["expected_index_digest"]:
                raise LearningError("Stale learning index/revision")
            if before["revision"] >= 32:
                raise LearningError("Learning transition capacity exhausted")
            from runtime.memory.learning import transition_heads
            transition_heads(i, before)
            # Check the entire confirmed eligible set, not a caller's memory view.
            for head in before["heads"].values():
                if head["state"] != "PROMOTED" or i["operation"] == "REVOKE":
                    continue
                if i["predecessor"] is not None and head["constraint_id"] == i["predecessor"]["constraint_id"]:
                    continue
                approved = self.store.load(head["approval_id"], require_canonical=True)
                old = approved.learning_scope["intent"]["proposal"]
                if overlap(old["applicability"], i["proposal"]["applicability"]):
                    raise LearningError("Overlapping eligible constraints require scoped resolution")
            return before

    def request_learning_disposition(self, scope, *, reason):
        from runtime.memory.learning import LearningScope, learning_fingerprint, LearningError
        from runtime.core.task_contract import digest
        s = LearningScope.from_dict(scope).to_dict(); p = s["preparation"]; r = s["review"]
        fingerprint = learning_fingerprint(s)
        identity = approval_boundary_id(p["job_id"], p["execution_id"], r["review_id"], "SET_LEARNING_DISPOSITION", fingerprint)
        with self.job_runtime.progress.transition_lock():
            self._validate_learning_scope(s)
            if self.store.exists(identity):
                raise LearningError("Disposition request already exists; no replay")
            request = ApprovalRequest(identity, p["job_id"], p["execution_id"], r["review_id"],
                "PENDING", self._bounded_required(reason, 2000, "Learning reason"), "approval_required",
                "SET_LEARNING_DISPOSITION", ({"ref_type": "file", "ref": p["output_path"]},),
                self.clock(), "READ_ONLY", None, fingerprint, learning_scope=s)
            reserved = {"approval_id": identity, "scope_digest": digest(s), "status": "PENDING"}
            self.store._encoded(request)  # Capacity check before any retained observation.
            # Observe first: interrupted creation cannot appear as a fresh namespace.
            self._learning_observe("learning_reservation_observed", identity, reserved, request.job_id)
            self.store.create(request)
            self.store._write_learning(self.learning.project_id, "reservation", reserved, replace=True)
            return ApprovalRun(request, self.artifact_ref(identity))

    def resolve_learning(self, approval_id, *, decision, decided_by, reason=None):
        from runtime.memory.learning import LearningError
        with self.job_runtime.progress.transition_lock():
            request = self.store.load(approval_id, require_canonical=True)
            if request.requested_action != "SET_LEARNING_DISPOSITION" or request.status != "PENDING":
                raise LearningError("Learning resolution requires exact pending canonical request")
            self._validate_learning_scope(request.learning_scope, reservation_id=approval_id)
            resolved = request.resolve(decision, decided_by=self._bounded_required(decided_by, 200, "Local operator"),
                resolved_at=self.clock(), reason=self._bounded_optional(reason, 2000))
            self.store.resolve(resolved)
            if decision == "REJECTED":
                reserved = {"approval_id": approval_id, "scope_digest": __import__('runtime.core.task_contract', fromlist=['digest']).digest(request.learning_scope), "status": "REJECTED"}
                self._learning_observe("learning_reservation_closed", approval_id, reserved, request.job_id)
                self.store._write_learning(self.learning.project_id, "reservation", reserved, replace=True)
            return {"approval": resolved.to_dict()}

    def apply_learning(self, approval_id):
        from runtime.core.capability_actions import ActionDecision
        return ActionDecision.apply_learning(self, approval_id)

    def _learning_eligible(self, index):
        from runtime.memory.learning import LearningError, overlap
        eligible = []
        for head in index["heads"].values():
            if head["state"] != "PROMOTED":
                continue
            request = self.store.load(head["approval_id"], require_canonical=True)
            self._validate_learning_scope(request.learning_scope, planning=True)
            p = request.learning_scope["intent"]["proposal"]
            if any(overlap(p["applicability"], other["proposal"]["applicability"]) for other in eligible):
                raise LearningError("Conflicting current learning constraints; planning held")
            eligible.append({"proposal": p, "disposition": deepcopy(head)})
        return eligible

    def inspect_learning(self):
        from runtime.memory.learning import learning_inspection
        with learning_inspection():
            index = self._learning_state()
            return {"index": index, "eligible": self._learning_eligible(index)}

    def check_learning(self, approval_id):
        """Historical confirmation and current eligibility are distinct read-only observations."""
        from runtime.memory.learning import learning_inspection, LearningError
        with learning_inspection():
            request = self.store.load(approval_id, require_canonical=True)
            if request.requested_action != "SET_LEARNING_DISPOSITION":
                raise LearningError("Not a learning disposition request")
            try:
                index = self._learning_state()
                confirmed = any(e["approval_id"] == approval_id for e in index["history"])
            except (ValueError, OSError, KeyError) as error:
                return {"approval_id": approval_id, "confirmed": False, "current_eligible": False,
                        "planning_hold": True, "reason": str(error)}
            try:
                eligible = self._learning_eligible(index)
            except (ValueError, OSError, KeyError) as error:
                return {"approval_id": approval_id, "confirmed": confirmed, "current_eligible": False,
                        "planning_hold": True, "reason": str(error)}
            return {"approval_id": approval_id, "confirmed": confirmed,
                    "current_eligible": any(e["disposition"]["approval_id"] == approval_id for e in eligible),
                    "planning_hold": not confirmed}

    @staticmethod
    def _resolution_is_applied(
        request: ApprovalRequest, job: dict[str, Any]
    ) -> bool:
        applied = job.get("approval", {})
        return (
            isinstance(applied, dict)
            and applied.get("approval_id") == request.approval_id
            and applied.get("status") == request.status
            and applied.get("authorization_fingerprint")
            == request.authorization_fingerprint
        )

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
                review_record = self.review_store.load(request.review_id, require_authority=True).get(
                    "result", {}
                )
                if (
                    review_record.get("decision") not in ({"NEEDS_HUMAN", "PASS"}
                        if job["task_contract"]["approval_requirements"]["completion"] else {"NEEDS_HUMAN"})
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
                return
            if (
                request.requested_action == "RESOLVE_HUMAN_CONDITION"
                and job["status"] == "running"
                and request.execution_id is not None
            ):
                if self.execution_store is None:
                    raise ApprovalRuntimeError(
                        "Execution store is required to restore a human boundary"
                    )
                record = self.execution_store.load(request.execution_id, require_authority=True)
                if (
                    record.result.job_id != request.job_id
                    or record.result.status != "needs_human"
                ):
                    raise ApprovalRuntimeError(
                        "Persisted execution does not match the human boundary"
                    )
                execution_ref = {
                    "ref_type": "artifact",
                    "ref": f"runtime-execution:{request.execution_id}",
                    "description": "Immutable normalized execution record",
                }
                decision = ContinuationPolicy.decide_execution(
                    job,
                    result_status="needs_human",
                    execution_ref=str(execution_ref["ref"]),
                )
                self.job_runtime.record_execution_needs_human(
                    request.job_id,
                    [*record.result.to_dict()["output_refs"], execution_ref],
                    approval_ref=approval_ref,
                    continuation=decision.checkpoint,
                )
        except (RuntimeError, ReviewStoreError, ExecutionStoreError) as error:
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

    def _notify_approval_resolved(
        self, request: ApprovalRequest, job: dict[str, Any]
    ) -> None:
        if self.notification_emitter is not None:
            try:
                self.notification_emitter.approval_resolved(
                    request.to_dict(), deepcopy(job)
                )
            except Exception:
                # Approval state remains authoritative if notification fails.
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
                result = {
                    "approval": request.to_dict(),
                    "job": self.job_runtime.show(request.job_id),
                }
                self._notify_approval_resolved(request, result["job"])
                return result
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
        result = {
            "approval": resolved.to_dict(),
            "job": self.job_runtime.show(request.job_id),
        }
        self._notify_approval_resolved(resolved, result["job"])
        return result

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
            result = self.execution_store.load(execution_id, require_authority=True).result.to_dict()
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
            result = self.review_store.load(review_id, require_authority=True).get("result", {})
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
        return approval_boundary_id(
            job_id,
            execution_id,
            review_id,
            requested_action,
            authorization_fingerprint,
        )

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
