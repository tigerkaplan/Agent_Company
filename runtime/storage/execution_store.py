"""Atomic local persistence for execution request/result artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.core.validation import JobValidationError, JobValidator
from runtime.execution.models import ExecutionContractError, ExecutionRequest, ExecutionResult
from runtime.execution.validation import (
    ExecutionResultValidationError,
    ExecutionResultValidator,
)


class ExecutionStoreError(ValueError):
    """Raised when an execution artifact cannot be persisted."""


EXECUTION_ARTIFACT_SCHEMA_VERSION = 1


def default_execution_artifact_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "execution-artifact.schema.json"


@dataclass(frozen=True)
class ExecutionRecord:
    """Typed persisted record; the canonical result is always revalidated on load."""

    schema_version: int
    request: dict[str, Any] | None
    result: ExecutionResult

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != EXECUTION_ARTIFACT_SCHEMA_VERSION
        ):
            raise ExecutionStoreError("Execution artifact schema version is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request": deepcopy(self.request),
            "result": self.result.to_dict(),
        }


class FileExecutionStore:
    """Store one immutable request/result record per execution."""

    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.artifact_validator = JobValidator(
            default_execution_artifact_schema_path()
        )
        self.result_validator = ExecutionResultValidator()

    def exists(self, execution_id: str) -> bool:
        return self._path(execution_id).is_file()

    def _decision_path(self, execution_id, stage, suffix):
        self._path(execution_id)  # Validate before composing any path.
        if type(stage) is not str or self._SAFE_ID.fullmatch(stage) is None or len(stage) > 100 or suffix not in {"anchor", "witness"}:
            raise ExecutionStoreError("Decision stage/suffix contains unsupported path characters")
        return self.root / ".decisions" / f"{execution_id}.{stage}.{suffix}.json"

    def _decision_pair(self, execution_id, stage, value=None):
        from runtime.core.task_contract import TaskContractStore, encoded
        paths = [self._decision_path(execution_id, stage, s) for s in ("witness", "anchor")]
        try:
            if value is not None:
                paths[0].parent.mkdir(parents=True, exist_ok=True)
                for path in paths:
                    TaskContractStore._write_new(path, value)
            raw = TaskContractStore._read(paths[0])
            other = TaskContractStore._read(paths[1])
            parsed = json.loads(raw)
            if (type(parsed) is not dict or type(parsed.get("schema_version")) is not int
                    or parsed["schema_version"] != 1
                    or raw != other or raw != encoded(parsed, max_bytes=512 * 1024)):
                raise ExecutionStoreError("Decision trace is partial, stale or tampered")
            return parsed
        except (OSError, ValueError, TypeError) as error:
            raise ExecutionStoreError("Decision trace unavailable; explicit recovery required") from error

    def unstarted(self, job, runtime):
        """Read-only veto for claim recovery, under the transition transaction.

        Both retained intent halves and protected observations independently
        veto requeue; a missing or malformed half fails closed.
        """
        from runtime.core.task_contract import digest
        history = runtime.progress.store.read(runtime.progress.logical_id(job))
        if any(e.job_id == job["job_id"] and e.event_type in {
                "decision_intent_observed", "decision_consumption_observed",
                "decision_result_observed", "execution_started"} for e in history):
            return False
        for owner in {self.root, runtime.store.root.parent / "executions"}:
            decisions = FileExecutionStore(owner)
            if decisions.find_for_job(job["job_id"]) is not None:
                return False
            ids = set()
            for stage in ("intent", "dispatch-execute", "dispatch-review", "effect-controlled_write"):
                ids.update(p.name.rsplit("." + stage + ".", 1)[0]
                           for p in (owner / ".decisions").glob("*." + stage + ".*.json"))
            for execution_id in sorted(ids):
                prior = decisions._decision_pair(execution_id, "intent")
                try:
                    decisions._verify_observation(prior, "decision_intent_observed", execution_id, digest(prior))
                    decisions._verify_observation(prior, "decision_consumption_observed",
                                                  decisions._intent_work_id(prior), digest(prior))
                    if prior["request"]["job_id"] == job["job_id"] or prior["authority_source"]["job_id"] == job["job_id"]:
                        return False
                except (KeyError, TypeError, ValueError) as error:
                    raise ExecutionStoreError("Unstarted recovery has untrusted retained intent") from error
        return True

    def begin_decision(self, request, *, executor, runtime, job):
        """Consume exact-work intent before effects; restart never retries it."""
        from contextlib import nullcontext
        from runtime.graph.models import preflight_plan_scope
        binding = job.get("graph_binding")
        # Structural proofs only; all authority/lease/intent checks stay fresh.
        scope = (preflight_plan_scope(runtime.store.root, binding["root_job_id"])
                 if binding is not None else nullcontext())
        with scope:
            from runtime.core.capability_governance import decision
            from runtime.core.task_contract import digest, TaskContractError
            from runtime.approvals.store import FileApprovalStore
            try:
                canonical = runtime.validate_execution_authority(job["job_id"], job.get("claimed_by"))
                if (runtime.task_contract_store.boundary(canonical) != runtime.task_contract_store.boundary(job)
                        or any(canonical.get(k) != job.get(k) for k in ("claimed_by", "attempt", "approval_status"))):
                    raise ExecutionStoreError("Decision requires the current canonical active claim")
            except ValueError as error:
                raise ExecutionStoreError("Decision requires canonical execution authority") from error
            runtime.task_contract_store.verify(job)
            from runtime.workers.worker import Worker
            expected = Worker._build_request(job, request.execution_id, request.context_refs)
            if request.to_dict() != expected.to_dict():
                raise ExecutionStoreError("Decision request differs from authorized exact work")
            try:
                approval_store = runtime.approval_store or FileApprovalStore(runtime.store.root.parent / "approvals")
                approvals = approval_store.completion_evidence(job, request.execution_id, None, execution_only=True)
                value = decision(request, executor=executor,
                    authority_source={"job_id": job["job_id"],
                        "task_boundary_digest": digest(runtime.task_contract_store.boundary(job)),
                        "task_store_root": str(runtime.task_contract_store.root.resolve()),
                        "job_store_root": str(runtime.store.root.resolve()),
                        "claimed_by": job["claimed_by"],
                        "budget_store_root": str(runtime.budget_store.root.resolve()),
                        "execution_store_root": str(self.root.resolve()),
                        "review_evidence_refs": list(job.get("output_refs", [])),
                        "progress_store_root": str(runtime.progress.store.root.resolve()),
                        "logical_job_id": runtime.progress.logical_id(job),
                        "approval_store_root": str(approval_store.root.resolve())}, approvals=approvals)
            except (ValueError, TaskContractError) as error:
                raise ExecutionStoreError("Decision authority/approval evidence rejected") from error
            self._verify_live_dispatch(value)
            # Coordinate using the existing CORE-07 transition lock. The authorized
            # job attempt is one work claim even if a caller invents another ID/store.
            # Sixteen siblings also publish result/lifecycle evidence through this
            # owner. Allow their bounded contention without reopening any attempt;
            # the complete live authority/lease check below remains mandatory.
            lock = (runtime.progress.transition_lock(timeout_seconds=180.0)
                    if job.get("graph_binding") else runtime.progress.transition_lock())
            with lock:
                # Revalidate through the configured canonical owner after waiting.
                # One complete live check avoids rebuilding and validating the same
                # graph owner twice while holding the shared intent transaction.
                self._verify_live_dispatch(value, runtime=runtime)
                history = runtime.progress.store.read(runtime.progress.logical_id(job))
                identity = self._intent_work_id(value)
                # Retained intent pairs independently veto a rolled-back journal.
                # Scan the canonical execution owner under the existing transition lock.
                roots = {self.root, runtime.store.root.parent / "executions"}
                for owner in roots:
                    decisions = FileExecutionStore(owner)
                    directory = owner / ".decisions"
                    retained_ids = set()
                    for stage in ("intent", "dispatch-execute", "dispatch-review", "effect-controlled_write"):
                        for path in directory.glob("*." + stage + ".*.json"):
                            retained_ids.add(path.name.rsplit("." + stage + ".", 1)[0])
                    for prior_id in sorted(retained_ids):
                        prior = decisions._decision_pair(prior_id, "intent")
                        try:
                            source = prior["authority_source"]
                            if (prior["request"]["execution_id"] != prior_id
                                    or source["job_id"] != prior["request"]["job_id"]
                                    or prior["request_digest"] != digest(prior["request"])
                                    or Path(source["progress_store_root"]).resolve()
                                    != runtime.progress.store.root.resolve()):
                                raise ExecutionStoreError("Retained intent identity/provenance changed; recovery required")
                            prior_identity = self._intent_work_id(prior)
                            # Journal observations independently bind even apparently
                            # foreign retained entries. No live historical job is
                            # needed, but mutable paired records cannot certify each
                            # other or redirect verification to another journal owner.
                            decisions._verify_observation(prior, "decision_intent_observed", prior_id, digest(prior))
                            decisions._verify_observation(prior, "decision_consumption_observed", prior_identity, digest(prior))
                        except (KeyError, TypeError, ValueError) as error:
                            raise ExecutionStoreError("Retained intent malformed; explicit recovery required") from error
                        if prior_identity == identity:
                            raise ExecutionStoreError("Decision job attempt already consumed in retained intent; journal rollback requires recovery")
                        # Surviving consumption pairs bind the original intent even
                        # if its job/work identity is coherently edited. This check
                        # needs no live job record for unrelated completed work.
                        for stage, purpose in (("dispatch-execute", "execute"), ("dispatch-review", "review")):
                            if any(decisions._decision_path(prior_id, stage, suffix).exists()
                                   for suffix in ("anchor", "witness")):
                                claim = {"schema_version": 1, "intent_digest": digest(prior), "purpose": purpose}
                                decisions._verify_consumption(prior, stage, claim)
                        # A changed work identity is never trusted from retained
                        # bytes alone; canonical provenance and observations veto it.
                        if (prior["request"]["job_id"] == request.job_id
                                or prior["authority_source"]["job_id"] == request.job_id):
                            decisions._verify_intent(prior)

                if any((e.execution_id == identity and e.event_type == "decision_consumption_observed")
                       or (e.execution_id == request.execution_id and e.event_type == "decision_intent_observed")
                       for e in history):
                    raise ExecutionStoreError("Decision job attempt already consumed; no replay authority")
                runtime.progress.store.append(runtime.progress.event(job, "decision_consumption_observed",
                    execution_id=identity, evidence_id=digest(value)))
                runtime.progress.store.append(runtime.progress.event(job, "decision_intent_observed",
                    execution_id=request.execution_id, evidence_id=digest(value)))
                canonical_store = FileExecutionStore(runtime.store.root.parent / "executions")
                if canonical_store.root.resolve() != self.root.resolve():
                    canonical_store._decision_pair(request.execution_id, "intent", value)
                return self._decision_pair(request.execution_id, "intent", value)

    @staticmethod
    def _intent_work_id(intent):
        from runtime.core.task_contract import digest
        request = intent["request"]
        # Only receipts already verified by the canonical ApprovalStore can
        # distinguish an explicit human resumption. Advice, IDs and quota cannot.
        receipts = sorted(ref for ref, record in intent["approval_received"].items()
            if record["requested_action"] in {"EXECUTE_JOB", "RESOLVE_HUMAN_CONDITION"})
        return "intent-work-" + digest({"job_id": request["job_id"], "attempt": request["attempt"],
                                       "execution_authority_refs": receipts})

    def verify_decision(self, request, result, *, require_authority=False):
        from runtime.core.task_contract import digest
        value = self._decision_pair(result.execution_id, "result")
        if value != {"schema_version": 1, "request_digest": digest(request),
                     "result_digest": digest(result.to_dict()),
                     "intent_digest": value.get("intent_digest"),
                     "evidence": result.to_dict()["artifacts"]}:
            raise ExecutionStoreError("Decision result trace does not bind exact work/evidence")
        if require_authority and value["intent_digest"] is None:
            raise ExecutionStoreError("Imported observation has no execution authority")
        if value["intent_digest"] is not None:
            intent = self._decision_pair(result.execution_id, "intent")
            if digest(intent) != value["intent_digest"] or intent["request_digest"] != digest(request):
                raise ExecutionStoreError("Decision intent is stale or replayed")
            self._verify_intent(intent)
            self._verify_consumption(intent, "dispatch-execute", {
                "schema_version": 1, "intent_digest": digest(intent), "purpose": "execute"})
            if request["execution_mode"] == "CONTROLLED_WRITE" and result.status in {"succeeded", "needs_review"}:
                self.verify_effect(intent, "controlled_write")
            self._verify_observation(intent, "decision_result_observed", result.execution_id, digest(value))
        return value

    def verify_effect(self, intent, tool):
        from runtime.core.task_contract import digest
        self._verify_consumption(intent, "effect-" + tool, {
            "schema_version": 1, "request_digest": digest(intent["request"]), "tool": tool})

    def _verify_consumption(self, intent, stage, claim):
        from runtime.core.task_contract import digest
        identity = "consumed-" + digest({"execution_id": intent["request"]["execution_id"], "stage": stage})
        if self._decision_pair(intent["request"]["execution_id"], stage) != claim:
            raise ExecutionStoreError("Consumed decision trace is stale or tampered")
        self._verify_observation(intent, "decision_consumption_observed", identity, digest(claim))

    @staticmethod
    def _observe(intent, kind, identity, evidence):
        from runtime.progress.models import ProgressEvent
        from runtime.progress.store import ProgressStore
        source = intent["authority_source"]
        event = ProgressEvent(kind, source["logical_job_id"], source["job_id"],
                              execution_id=identity, evidence_id=evidence)
        ProgressStore(Path(source["progress_store_root"])).append(event)

    @staticmethod
    def _verify_observation(intent, kind, identity, evidence):
        from runtime.progress.store import ProgressStore
        source = intent["authority_source"]
        events = ProgressStore(Path(source["progress_store_root"])).read(source["logical_job_id"])
        found = [e for e in events if e.event_type == kind and e.execution_id == identity]
        if len(found) != 1 or found[0].evidence_id != evidence or found[0].job_id != source["job_id"]:
            raise ExecutionStoreError("Decision trace differs from independent durable observation")

    @staticmethod
    def _verify_intent(intent):
        from runtime.core.capability_governance import decision
        from runtime.execution.models import ExecutionRequest
        from runtime.core.task_contract import digest
        from runtime.progress.store import ProgressStore
        from runtime.progress.store import inspection_active, inspection_read
        from runtime.approvals.store import FileApprovalStore
        try:
            request = ExecutionRequest.from_persisted_dict(intent["request"])
            expected = decision(request, executor=intent["executor"],
                authority_source=intent["authority_source"], approvals=intent["approval_received"])
            if intent != expected:
                raise ExecutionStoreError("Decision certification/policy provenance changed")
            source = intent["authority_source"]
            from runtime.core.task_contract import TaskContractStore, inspection_load
            from runtime.progress.runtime import ProgressRuntime
            from runtime.storage.file_store import FileJobStore
            job_store = FileJobStore(Path(source["job_store_root"]))
            if inspection_active():
                current_job = json.loads(inspection_read(job_store._path(request.job_id)))
                if type(current_job) is not dict:
                    raise ExecutionStoreError("Inspection job record is not an object")
            else:
                current_job = job_store.load(request.job_id)
            JobValidator().validate(current_job)
            tasks = TaskContractStore(Path(source["task_store_root"]),
                progress=ProgressRuntime(Path(source["progress_store_root"])))
            tasks.verify(current_job)
            if current_job.get("graph_binding") is not None:
                if inspection_active():
                    raise ExecutionStoreError("Graph-bound authority inspection requires outside owners")
                from runtime.core.jobs import JobRuntime
                from runtime.graph.runtime import validate_graph_job
                jobs = JobRuntime(Path(source["job_store_root"]))
                jobs.execution_store = FileExecutionStore(Path(source["execution_store_root"]))
                jobs.configure_authority_stores(FileApprovalStore(Path(source["approval_store_root"])), jobs.execution_store)
                validate_graph_job(jobs, current_job)
            boundary = tasks.boundary(current_job)
            # GOV-01 permits a verified monotonic strengthening of this gate.
            # TaskContractStore has already checked its original anchor, paired
            # strengthening record and independent journal; no scope is added.
            boundary["review_required"] = request.review_required
            if digest(boundary) != source["task_boundary_digest"]:
                raise ExecutionStoreError("Decision parent authority changed")
            history = ProgressStore(Path(source["progress_store_root"])).read(source["logical_job_id"])
            observed = [e for e in history if e.execution_id == request.execution_id
                        and e.event_type == "decision_intent_observed"]
            if (len(observed) != 1 or observed[0].job_id != request.job_id
                    or observed[0].evidence_id != digest(intent)):
                raise ExecutionStoreError("Decision intent differs from independent durable evidence")
            work = [e for e in history if e.event_type == "decision_consumption_observed"
                    and e.execution_id == FileExecutionStore._intent_work_id(intent)]
            if len(work) != 1 or work[0].job_id != request.job_id or work[0].evidence_id != digest(intent):
                raise ExecutionStoreError("Decision job-attempt consumption is missing or tampered")
            approvals = FileApprovalStore(Path(source["approval_store_root"]))
            for ref, record in intent["approval_received"].items():
                if inspection_load(approvals, ref.split(":", 1)[1]).to_dict() != record:
                    raise ExecutionStoreError("Decision approval evidence changed")
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise ExecutionStoreError("Decision intent provenance unavailable or tampered") from error

    @staticmethod
    def _verify_live_dispatch(intent, *, runtime=None):
        """Reuse operational claim/budget records; provenance cannot grant them."""
        from runtime.storage.file_store import FileJobStore
        from runtime.budget.models import BudgetBinding
        from runtime.budget.store import FileExecutionBudgetStore
        try:
            source, request = intent["authority_source"], intent["request"]
            if runtime is None:
                job = FileJobStore(Path(source["job_store_root"])).load(request["job_id"])
            else:
                from runtime.core.task_contract import digest
                if runtime.store.root.resolve() != Path(source["job_store_root"]).resolve():
                    raise ExecutionStoreError("Dispatch canonical job owner changed")
                job = runtime.validate_execution_authority(request["job_id"], source["claimed_by"])
                if digest(runtime.task_contract_store.boundary(job)) != source["task_boundary_digest"]:
                    raise ExecutionStoreError("Dispatch exact task boundary changed during the intent wait")
            if (job["status"] != "running" or not job.get("claimed_by")
                    or job["claimed_by"] != source["claimed_by"]
                    or job["attempt"] != request["attempt"]
                    or job["approval_status"] != request["approval_status"]):
                raise ExecutionStoreError("Certified dispatch has no exact active canonical claim")
            if job.get("graph_binding") is not None and runtime is None:
                from runtime.core.jobs import JobRuntime
                from runtime.graph.runtime import validate_graph_job
                from runtime.approvals.store import FileApprovalStore
                jobs = JobRuntime(Path(source["job_store_root"]))
                jobs.execution_store = FileExecutionStore(Path(source["execution_store_root"]))
                jobs.configure_authority_stores(FileApprovalStore(Path(source["approval_store_root"])), jobs.execution_store)
                validate_graph_job(jobs, job, executing=True)
            if request["task_contract"]["budget_references"] is not None:
                binding = BudgetBinding.from_dict(request["task_contract"]["budget_references"])
                store = FileExecutionBudgetStore(Path(source["budget_store_root"]))
                # The canonical writer publishes usage evidence before its
                # mutable state. Parallel siblings must observe a committed
                # pair, never mistake an in-flight transaction for corruption.
                with store.transaction(timeout_seconds=30.0 if job.get("graph_binding") else 5.0):
                    store.load_policy(binding)
                    state = store.load_state(binding)
                    reservations = [r for r in state["reservations"]
                        if r["execution_id"] == request["execution_id"]]
                    if (state["clock_rollback_detected"] or len(reservations) != 1
                            or reservations[0]["job_id"] != request["job_id"]
                            or reservations[0]["state"] != "active"):
                        raise ExecutionStoreError("Certified dispatch has no active canonical budget reservation")
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise ExecutionStoreError("Dispatch claim/budget evidence unavailable") from error

    def create(
        self,
        request: ExecutionRequest | None,
        result: ExecutionResult,
    ) -> Path:
        path = self._path(result.execution_id)
        if path.exists():
            raise ExecutionStoreError(
                f"Execution artifact already exists: {result.execution_id}"
            )
        self.result_validator.validate_model(result)
        self._validate_request_result_binding(
            request.to_dict() if request is not None else None,
            result,
        )
        record: dict[str, Any] = {
            "schema_version": EXECUTION_ARTIFACT_SCHEMA_VERSION,
            "request": request.to_dict() if request is not None else None,
            "result": result.to_dict(),
        }
        if request is not None and request.task_contract is not None:
            from runtime.core.task_contract import digest
            intent_path = self._decision_path(result.execution_id, "intent", "anchor")
            witness_path = self._decision_path(result.execution_id, "intent", "witness")
            intent = self._decision_pair(result.execution_id, "intent") if intent_path.exists() or witness_path.exists() else None
            if intent is not None and intent["request_digest"] != digest(request.to_dict()):
                raise ExecutionStoreError("Decision intent request substitution rejected")
            # Direct artifact imports record observations, never pre-effect
            # authorization. Canonical Worker records an intent before dispatch.
            trace = {
                "schema_version": 1, "request_digest": digest(request.to_dict()),
                "result_digest": digest(result.to_dict()),
                "intent_digest": digest(intent) if intent is not None else None,
                "evidence": result.to_dict()["artifacts"]}
            if intent is not None:
                self._verify_intent(intent)
                from runtime.progress.store import ProgressStore
                source = intent["authority_source"]
                history = ProgressStore(Path(source["progress_store_root"])).read(source["logical_job_id"])
                if any(e.event_type == "decision_result_observed" and e.execution_id == result.execution_id for e in history):
                    raise ExecutionStoreError("Result trace already observed; explicit recovery required")
                self._observe(intent, "decision_result_observed", result.execution_id, digest(trace))
            self._decision_pair(result.execution_id, "result", trace)
        self._write(path, record)
        return path

    def load(self, execution_id: str, *, require_authority=False, inspection=False) -> ExecutionRecord:
        if type(inspection) is not bool:
            raise ExecutionStoreError("Inspection flag must be a boolean")
        if inspection:
            from runtime.progress.store import readonly_inspection
            with readonly_inspection():
                return self.load(execution_id, require_authority=require_authority)
        value = self.load_raw(execution_id)
        if set(value) - {"schema_version", "request", "result"}:
            raise ExecutionStoreError(
                f"Execution artifact contains unexpected fields: {execution_id}"
            )
        try:
            self.artifact_validator.validate(value)
        except JobValidationError as error:
            raise ExecutionStoreError(
                f"Invalid execution artifact envelope {execution_id}: {error}"
            ) from error
        if (
            type(value.get("schema_version")) is not int
            or value["schema_version"] != EXECUTION_ARTIFACT_SCHEMA_VERSION
        ):
            raise ExecutionStoreError(
                f"Execution artifact has unsupported schema version: {execution_id}"
            )
        request = value.get("request")
        if request is not None and not isinstance(request, dict):
            raise ExecutionStoreError(
                f"Execution artifact request is not an object: {execution_id}"
            )
        payload = value.get("result")
        if not isinstance(payload, dict):
            raise ExecutionStoreError(
                f"Execution artifact result is not an object: {execution_id}"
            )
        try:
            result = ExecutionResult.from_dict(payload, sanitize_historical=True)
            self.result_validator.validate_model(result)
        except (ExecutionContractError, ExecutionResultValidationError) as error:
            raise ExecutionStoreError(
                f"Invalid execution artifact result {execution_id}: {error}"
            ) from error
        if result.execution_id != execution_id:
            raise ExecutionStoreError(
                f"Execution artifact identity mismatch: {execution_id}"
            )
        self._validate_request_result_binding(request, result)
        if require_authority and (request is None or request.get("task_contract") is None):
            raise ExecutionStoreError("Observation lacks canonical task and execution authority")
        if request is not None and request.get("task_contract") is not None:
            self.verify_decision(request, result, require_authority=require_authority)
        return ExecutionRecord(
            EXECUTION_ARTIFACT_SCHEMA_VERSION, deepcopy(request), result
        )

    def load_raw(self, execution_id: str) -> dict[str, Any]:
        """Compatibility-only raw read; canonical runtime consumers use load()."""
        path = self._path(execution_id)
        if not path.is_file():
            raise ExecutionStoreError(f"Execution artifact not found: {execution_id}")
        try:
            from runtime.progress.store import inspection_active, inspection_read
            if inspection_active():
                value = json.loads(inspection_read(path))
            else:
                with path.open("r", encoding="utf-8") as handle:
                    value = json.load(handle)
        except (OSError, ValueError, RecursionError) as error:
            raise ExecutionStoreError(
                f"Could not read execution artifact {execution_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ExecutionStoreError(
                f"Execution artifact is not an object: {execution_id}"
            )
        return value

    def find_for_job(
        self, job_id: str, *, linked_execution_ids: set[str] | None = None
    ) -> ExecutionRecord | None:
        """Find the one immutable execution result already committed for a job."""
        if not self.root.exists():
            return None
        matches: list[ExecutionRecord] = []
        for path in sorted(self.root.glob("*.json")):
            record = self.load(path.stem)
            if (
                record.result.job_id == job_id
                and record.result.execution_id not in (linked_execution_ids or set())
            ):
                matches.append(record)
        if len(matches) > 1:
            raise ExecutionStoreError(
                f"Multiple execution artifacts are bound to job: {job_id}"
            )
        return matches[0] if matches else None

    def _path(self, execution_id: str) -> Path:
        if self._SAFE_ID.fullmatch(execution_id) is None:
            raise ExecutionStoreError("Execution ID contains unsupported path characters")
        return self.root / f"{execution_id}.json"

    @staticmethod
    def _validate_request_result_binding(
        request: dict[str, Any] | None,
        result: ExecutionResult,
    ) -> None:
        if request is None:
            return
        expected = {
            "execution_id": result.execution_id,
            "job_id": result.job_id,
            "execution_mode": result.execution_mode,
            "dry_run": result.dry_run,
        }
        actual = {
            "execution_id": request.get("execution_id"),
            "job_id": request.get("job_id"),
            "execution_mode": request.get("execution_mode", "READ_ONLY"),
            "dry_run": request.get("dry_run", False),
        }
        if actual != expected:
            raise ExecutionStoreError(
                "Execution artifact request does not match its canonical result"
            )

    def _write(self, path: Path, record: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(
                    record,
                    handle,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise ExecutionStoreError(
                f"Could not persist execution artifact {path.stem}: invalid or unserializable canonical data"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
