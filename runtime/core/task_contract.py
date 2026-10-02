"""GOV-01 task policy, enforced by canonical jobs, not provider claims.

Contracts allocate authority ceilings. They never replace ApprovalRuntime,
ExecutionScope, CORE budgets, Reviewer, or separate Git action approvals.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import tempfile
from pathlib import Path
import re
from functools import lru_cache

from runtime.core.validation import JobValidator, JobValidationError


class TaskContractError(ValueError):
    """Missing or inconsistent task authority/evidence; always fail closed."""


LEVELS = {"L0": "Observe", "L1": "Produce", "L2": "Local Write",
          "L3": "External Draft", "L4": "External Action",
          "L5": "Financial/Irreversible"}
TOOLS = {"local_executor", "provider_call", "controlled_write", "tests", "git_read"}
SCHEMA = Path(__file__).resolve().parents[2] / "schemas/task-contract.schema.json"


@lru_cache(maxsize=1)
def contract_validator():
    return JobValidator(SCHEMA)


@lru_cache(maxsize=1)
def review_validator():
    return JobValidator(SCHEMA.parent / "review.schema.json")


def encoded(value, *, max_bytes=128 * 1024):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError) as error:
        raise TaskContractError("Task contract is not canonical JSON") from error
    if len(raw) > max_bytes:
        raise TaskContractError("Canonical task data exceeds its bounded identity limit")
    return raw


def digest(value):
    return hashlib.sha256(encoded(value, max_bytes=64 * 1024 * 1024)).hexdigest()


def _contract_bounds(value, depth=0, budget=None):
    if budget is None:
        budget = [16384, 128 * 1024]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise TaskContractError("Task contract exceeds structural bounds")
    if type(value) is str:
        try:
            budget[1] -= len(value.encode("utf-8"))
        except UnicodeError as error:
            raise TaskContractError("Task contract has malformed text") from error
        if budget[1] < 0:
            raise TaskContractError("Task contract exceeds text bounds")
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TaskContractError("Task contract keys must be strings")
            _contract_bounds(key, depth + 1, budget)
            _contract_bounds(item, depth + 1, budget)
    elif type(value) is list:
        for item in value:
            _contract_bounds(item, depth + 1, budget)
    elif value is not None and type(value) not in {bool, int, float}:
        raise TaskContractError("Task contract contains a noncanonical primitive")


def validate(contract):
    from runtime.evals.models import EvalCheckSpec, EVALUATOR_TYPES
    _contract_bounds(contract)
    encoded(contract)
    try:
        contract_validator().validate(contract)
        checks = [EvalCheckSpec.from_dict(c) for c in contract["required_checks"]]
    except (ValueError, TypeError, KeyError) as error:
        raise TaskContractError(f"Invalid task contract: {error}") from error
    ids = {c.check_id for c in checks}
    if len(ids) != len(checks) or any(c.evaluator_type not in EVALUATOR_TYPES for c in checks):
        raise TaskContractError("Task checks must be unique canonical evaluators")
    if any(not set(c["check_ids"]) <= ids for c in contract["acceptance_criteria"]):
        raise TaskContractError("Acceptance criterion has no canonical required check")
    if len({c["criterion_id"] for c in contract["acceptance_criteria"]}) != len(contract["acceptance_criteria"]):
        raise TaskContractError("Acceptance criteria must be unique")
    if any(c.check_id.startswith("gov_") for c in checks) or len(checks) + len(contract["required_evidence"]) + bool(contract["expected_outputs"]) > 100:
        raise TaskContractError("Task checks exceed the bounded completion allocation")
    if not set(contract["allowed_tools"]) <= TOOLS:
        raise TaskContractError("Unknown tool or attempted Git/deployment/financial grant")
    return deepcopy(contract)


def default_contract(job):
    """Conservative execution envelope with unresolved task acceptance.

    Legacy creation can observe/produce work but cannot reach DONE without
    declared acceptance criteria. No semantic acceptance is invented.
    """
    write = job["execution_mode"] == "CONTROLLED_WRITE"
    scope = job.get("execution_scope")
    checks = [{"check_id": "result_contract", "evaluator_type": "EXECUTION_RESULT_CONTRACT",
               "severity": "critical", "config": {}},
              {"check_id": "no_blockers", "evaluator_type": "FORBIDDEN_CONDITIONS",
               "severity": "critical", "config": {"forbid_blockers": True}}]
    tools = ["local_executor", "provider_call"]
    if write:
        tools.append("controlled_write")
        if scope.get("allow_tests"):
            tools.append("tests")
        if scope.get("allow_git_reads"):
            tools.append("git_read")
    return {"schema_version": 1, "objective": job["task"],
            "inputs": deepcopy(job["input_refs"]), "expected_outputs": [],
            "allowed_tools": tools, "allowed_capabilities": list(dict.fromkeys(
                [job["capability"], *(["independent_review"] if job["review_required"] else [])])),
            "write_scope": deepcopy(scope), "budget_references": deepcopy(job.get("execution_budget")),
            "acceptance_criteria": [],
            "required_checks": checks, "required_evidence": [],
            "stop_conditions": [{"kind": "on_blocker"}],
            "risk": job["risk_level"], "blast_radius": "local" if write else "none",
            "reversibility": "reversible" if write else "no_side_effect",
            "delegation_level": ("L5" if write and scope.get("write_mode") == "CREATE_MODIFY_DELETE" else "L2") if write else "L1",
            "approval_requirements": {"execution": write or job["approval_status"] != "not_required",
                                      "completion": False, "review": job["review_required"]}}


def validate_binding(job, *, now=None, executing=False):
    c = validate(job["task_contract"])
    if (c["objective"] != job["task"] or c["inputs"] != job["input_refs"]
            or job["capability"] not in c["allowed_capabilities"]
            or c["write_scope"] != job.get("execution_scope")
            or c["budget_references"] != job.get("execution_budget")
            or c["risk"] != job["risk_level"]):
        raise TaskContractError("Task contract does not match exact canonical work/scope/budget")
    level = int(c["delegation_level"][1])
    gates = c["approval_requirements"]
    if (gates["review"] and not job["review_required"]
            or gates["execution"] and job["approval_status"] == "not_required"):
        raise TaskContractError("Task contract approval/review gate was weakened")
    if gates["completion"] and not gates["review"]:
        raise TaskContractError("Human completion approval requires the canonical Reviewer boundary")
    if c["risk"] == "approval_required" and not gates["execution"]:
        raise TaskContractError("Risk approval requirement was weakened")
    if (level >= 4 or c["risk"] == "high"
            or c["blast_radius"] == "external" or c["reversibility"] == "irreversible"):
        if not gates["execution"] or not gates["review"]:
            raise TaskContractError("Risky authority requires explicit human approval and independent review")
    if job["execution_mode"] == "CONTROLLED_WRITE":
        if level < 2 or not gates["execution"] or not gates["review"] or "controlled_write" not in c["allowed_tools"]:
            raise TaskContractError("Local write exceeds delegation/tool/approval allocation")
        scope = c["write_scope"]
        if c["blast_radius"] == "none" or c["reversibility"] == "no_side_effect":
            raise TaskContractError("Write contract understates blast radius or side effects")
        if scope.get("allow_tests") and "tests" not in c["allowed_tools"]:
            raise TaskContractError("Test tool exceeds task allocation")
        if scope.get("allow_git_reads") and "git_read" not in c["allowed_tools"]:
            raise TaskContractError("Git read tool exceeds task allocation")
        if scope.get("write_mode") == "CREATE_MODIFY_DELETE" and level < 5:
            raise TaskContractError("Destructive writes require explicit L5 authority")
    elif "controlled_write" in c["allowed_tools"]:
        raise TaskContractError("Read-only contract cannot allocate write tools")
    if level == 0 and c["expected_outputs"]:
        raise TaskContractError("L0 observation cannot allocate produced deliverables")
    if executing:
        if gates["execution"] and job["approval_status"] != "approved":
            raise TaskContractError("Task execution requires canonical scoped human approval")
        for stop in c["stop_conditions"]:
            if stop["kind"] == "no_execution":
                raise TaskContractError("Task contract stop condition prohibits execution")
            if stop["kind"] == "deadline" and datetime.fromisoformat(now.replace("Z", "+00:00")) >= datetime.fromisoformat(stop["at"].replace("Z", "+00:00")):
                raise TaskContractError("Task contract deadline is stale")
    return c


class TaskContractStore:
    """Write-once exact-work anchor and creation witness; no approval store."""
    def __init__(self, root, *, progress):
        self.root = Path(root)
        self.progress = progress

    def _path(self, job_id, suffix):
        if not isinstance(job_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", job_id) is None:
            raise TaskContractError("Invalid task anchor identity")
        return self.root / f"{job_id}.{suffix}.json"

    @staticmethod
    def boundary(job):
        fields = ("job_id", "created_at", "task", "task_class", "project_id", "agent", "skill", "workflow",
                  "capability", "risk_level", "review_required", "execution_mode", "execution_scope",
                  "input_refs", "execution_budget", "max_attempts", "dry_run", "task_contract")
        return {k: deepcopy(job.get(k)) for k in fields}

    def create(self, job):
        value = {"schema_version": 2, "boundary": self.boundary(job)}
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            for suffix in ("witness", "anchor"):
                with self._path(job["job_id"], suffix).open("xb") as handle:
                    handle.write(encoded(value, max_bytes=512 * 1024))
                    handle.flush()
                    os.fsync(handle.fileno())
            gates = self._gate_value(job, job["review_required"])
            self._observe_gate(job, initial=True)
            for suffix in ("gate-witness", "gate-anchor"):
                self._write_new(self._path(job["job_id"], suffix), gates)
        except OSError as error:
            raise TaskContractError("Task contract creation interrupted or identity already anchored; recovery required") from error

    def _verify_creation(self, job):
        candidate = self.boundary(job)
        try:
            anchor = self._path(job["job_id"], "anchor")
            original = json.loads(self._read(anchor))
            if (type(original) is not dict or set(original) != {"schema_version", "boundary"}
                    or type(original["schema_version"]) is not int or original["schema_version"] != 2
                    or type(original["boundary"]) is not dict):
                raise TaskContractError("Pre-F1 task authority requires explicit recovery; no automatic migration")
            initial = original["boundary"]["review_required"]
            if type(initial) is not bool or initial and not candidate["review_required"]:
                raise TaskContractError("Task review gate was weakened")
            candidate["review_required"] = initial
            expected = encoded({"schema_version": 2, "boundary": candidate}, max_bytes=512 * 1024)
            for suffix in ("witness", "anchor"):
                path = self._path(job["job_id"], suffix)
                if self._read(path) != expected:
                    raise TaskContractError("Task contract anchor changed; recovery required")
            return initial
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise TaskContractError("Task contract authority missing; recovery required") from error

    def _gate_value(self, job, review_required):
        boundary = self.boundary(job)
        # The creation identity stays fixed when the effective gate strengthens.
        boundary["review_required"] = False
        return {"schema_version": 1, "job_id": job["job_id"],
                "boundary_digest": digest(boundary), "review_required": review_required}

    def _gates(self, job, initial):
        try:
            raw = self._read(self._path(job["job_id"], "gate-anchor"))
            if raw != self._read(self._path(job["job_id"], "gate-witness")):
                raise TaskContractError("Task gate acceptance is partial; recovery required")
            value = json.loads(raw)
            if (type(value) is not dict or type(value.get("review_required")) is not bool
                    or raw != encoded(self._gate_value(job, value["review_required"]))
                    or initial and not value["review_required"]):
                raise TaskContractError("Task gate acceptance is malformed or stale")
            paths = [self._path(job["job_id"], "review-required-" + s) for s in ("witness", "anchor")]
            if not initial and value["review_required"]:
                expected = encoded(self._gate_value(job, True))
                if any(self._read(p) != expected for p in paths):
                    raise TaskContractError("Task gate strengthening evidence is missing or tampered")
            elif any(p.exists() for p in paths):
                raise TaskContractError("Task gate acceptance rolled back or was interrupted")
            return value["review_required"]
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise TaskContractError("Task gate authority unavailable; recovery required") from error

    def verify(self, job):
        initial = self._verify_creation(job)
        effective = self._gates(job, initial)
        if (self._history_gate(job, initial) != effective
                or effective != job["review_required"]):
            raise TaskContractError("Persisted task review gate differs from durable authority")

    def _gate_event(self, job, review_required, *, initial):
        return self.progress.event(job, "task_gate_observed",
            detail="created" if initial else "review",
            evidence_id=digest(self._gate_value(job, review_required)))

    def _observe_gate(self, job, *, initial):
        from runtime.progress.models import ProgressError
        try:
            self.progress.store.append(self._gate_event(job, job["review_required"], initial=initial))
        except ProgressError as error:
            raise TaskContractError("Task gate observation could not be committed; recovery required") from error

    def _history_gate(self, job, initial):
        """CORE-07 observations veto rollback; they never grant task authority.

        Read the entire protected journal, including its head and pending state.
        Missing history is a recovery hold, never permission to recreate genesis.
        Only creation and strengthen() append these observations. Reconciliation
        and provider output cannot synthesize them from a mutable job snapshot.
        """
        from runtime.progress.models import ProgressError
        try:
            history = self.progress.store.read(self.progress.logical_id(job))
        except ProgressError as error:
            raise TaskContractError("Task gate history is unavailable or malformed; recovery required") from error
        observations = [event for event in history
                        if event.job_id == job["job_id"] and event.event_type == "task_gate_observed"]
        genesis = self._gate_event(job, initial, initial=True)
        strengthened = self._gate_event(job, True, initial=False)
        if observations == [genesis]:
            return initial
        if not initial and observations == [genesis, strengthened]:
            return True
        raise TaskContractError("Task gate history is missing, stale or conflicting; explicit recovery required")

    def strengthen(self, current, candidate):
        """Called under the canonical transition lock, before the job write.

        Creation, strengthening witnesses and accepted gate pairs remain in this
        store. Independent CORE-07 observations commit first and only veto stale
        authority. Interrupted writes hold rather than refund a committed gate.
        """
        initial = self._verify_creation(candidate)
        effective = self._gates(current, initial)
        if self._history_gate(current, initial) != effective:
            raise TaskContractError("Task gate records differ from independent durable observations")
        if effective and not candidate["review_required"]:
            raise TaskContractError("Canonical task review requirement cannot be weakened")
        if not effective and candidate["review_required"]:
            value = self._gate_value(candidate, True)
            # Commit the independent observation first. Every later interruption
            # holds the old job; deleting/replaying GOV-01 files cannot erase it.
            self._observe_gate(candidate, initial=False)
            try:
                for suffix in ("review-required-witness", "review-required-anchor"):
                    self._write_new(self._path(candidate["job_id"], suffix), value)
                for suffix in ("gate-witness", "gate-anchor"):
                    self._replace(self._path(candidate["job_id"], suffix), value)
            except OSError as error:
                raise TaskContractError("Task gate strengthening interrupted; recovery required") from error

    @staticmethod
    def _write_new(path, value):
        with path.open("xb") as handle:
            handle.write(encoded(value, max_bytes=512 * 1024))
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _replace(path, value):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(encoded(value, max_bytes=512 * 1024))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    @staticmethod
    def _read(path):
        with path.open("rb") as handle:
            raw = handle.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise TaskContractError("Task contract anchor is oversized")
        return raw

    def bind_completion(self, job_id, proof):
        """Pin observed completion facts before the canonical terminal write.

        An interrupted job write may retry the identical evidence receipt;
        it cannot rewrite those facts or bypass a current deadline/gate.
        """
        paths = [self._path(job_id, "completion-" + suffix) for suffix in ("witness", "anchor")]
        if any(path.exists() for path in paths):
            stored = self._completion(job_id)
            candidate = deepcopy(proof)
            candidate["accepted_at"] = stored["accepted_at"]
            if encoded(candidate, max_bytes=512 * 1024) != encoded(stored, max_bytes=512 * 1024):
                raise TaskContractError("Completion receipt cannot be rewritten; recovery required")
            return stored
        value = {"job_id": job_id, "proof": proof}
        try:
            for path in paths:
                with path.open("xb") as handle:
                    handle.write(encoded(value, max_bytes=512 * 1024))
                    handle.flush()
                    os.fsync(handle.fileno())
        except OSError as error:
            raise TaskContractError("Completion receipt creation interrupted; recovery required") from error
        return deepcopy(proof)

    def _completion(self, job_id):
        try:
            witness = self._read(self._path(job_id, "completion-witness"))
            anchor = self._read(self._path(job_id, "completion-anchor"))
            value = json.loads(anchor)
            if (anchor != witness or type(value) is not dict or set(value) != {"job_id", "proof"}
                    or value["job_id"] != job_id or type(value["proof"]) is not dict
                    or encoded(value, max_bytes=512 * 1024) != anchor):
                raise TaskContractError("Completion receipt is malformed or tampered")
            return value["proof"]
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise TaskContractError("Completion receipt is missing or malformed; recovery required") from error

    def verify_completion(self, job_id, proof):
        if encoded(self._completion(job_id), max_bytes=512 * 1024) != encoded(proof, max_bytes=512 * 1024):
            raise TaskContractError("Completion proof differs from its immutable receipt")


def require_tool(request, tool, *, now=None):
    if request.task_contract is None:
        raise TaskContractError("Execution requires a canonical task contract")
    c = validate(request.to_dict()["task_contract"])
    boundary = request.to_dict()
    boundary["task_contract"] = c
    boundary["execution_budget"] = c["budget_references"]
    validate_binding(boundary, now=now or datetime.now(timezone.utc).isoformat(), executing=True)
    if tool not in c["allowed_tools"]:
        raise TaskContractError(f"Tool {tool} is outside task contract")
    if c["delegation_level"] == "L0" and tool == "provider_call":
        raise TaskContractError("Provider production requires explicit L1 or higher delegation")
    if c["delegation_level"] in {"L4", "L5"} and request.execution_mode == "READ_ONLY":
        raise TaskContractError("External/financial operations require a separate supported action boundary")


def require_provider_tool_confinement(request, adapter):
    """Native tools are never authorized merely by permission to call a model.

    V1 supports adapters with disabled native tools. CLI adapters with opaque
    native tools fail closed; filesystem sandboxing does not prove tool scope.
    This is an execution restriction, not GOV-02 capability certification.
    """
    require_tool(request, "provider_call")
    if getattr(adapter, "native_tools", None) != frozenset() or type(getattr(adapter, "native_tools", None)) is not frozenset:
        raise TaskContractError("Provider native tool confinement is unavailable for this task contract")


def completion(runtime, job, *, verify_only=False):
    """Re-evaluate actual persisted evidence; completion itself grants nothing."""
    from runtime.actions.authorization import authorization_fingerprint
    from runtime.evals.models import EvalSpec, eval_input_digests
    from runtime.evals.runner import EvalRunner
    from runtime.evals.store import FileEvalStore
    c = validate_binding(job)
    if not c["acceptance_criteria"]:
        raise TaskContractError("DONE requires declared task acceptance criteria")
    validate_binding(job, now=runtime.clock(), executing=True)
    if runtime.execution_store is None:
        from runtime.storage.execution_store import FileExecutionStore
        runtime.execution_store = FileExecutionStore(runtime.store.root.parent / "executions")
    refs = [r["ref"] for r in job["output_refs"] if r["ref"].startswith("runtime-execution:")]
    if not refs:
        raise TaskContractError("DONE requires persisted execution evidence")
    record = runtime.execution_store.load(refs[-1].split(":", 1)[1])
    execution_boundary = deepcopy(job)
    if record.request is not None and record.result.status == "needs_review":
        execution_boundary["review_required"] = record.request["review_required"]
    if (record.request is None or record.result.status not in {"succeeded", "needs_review"}
            or authorization_fingerprint(record.request) != authorization_fingerprint(execution_boundary)
            or record.request.get("task_contract") != c):
        raise TaskContractError("Execution evidence is stale or does not bind exact task contract")
    if record.result.status == "needs_review" and not job["review_required"]:
        raise TaskContractError("Execution requires independent review")
    if any(s["kind"] == "on_blocker" for s in c["stop_conditions"]) and record.result.blockers:
        raise TaskContractError("Task stop condition: execution has blockers")
    if c["delegation_level"] == "L0" and record.result.artifacts:
        raise TaskContractError("Produced deliverables exceed L0 observation authority")
    checks = list(c["required_checks"])
    if c["expected_outputs"]:
        checks.append({"check_id": "gov_outputs", "evaluator_type": "REQUIRED_ARTIFACTS",
                       "severity": "critical", "config": {"required": c["expected_outputs"]}})
    for index, evidence in enumerate(c["required_evidence"]):
        checks.append({"check_id": f"gov_evidence_{index}", "evaluator_type": "FILE_DIGEST",
                       "severity": "critical", "config": evidence})
    spec = EvalSpec.from_dict({"schema_version": 1, "spec_id": "gov-01-" + digest(c)[:24],
        "job_id": job["job_id"], "execution_id": record.result.execution_id,
        "evaluator_id": "canonical-deterministic", "evaluator_version": "1",
        "checks": checks, "metadata": {"task_contract_digest": digest(c)}})
    eval_store = FileEvalStore(runtime.store.root.parent / "evals")
    if verify_only:
        proof = job["task_completion"]
        evaluated = eval_store.load(proof["eval_id"])
        spec_digest, execution_digest = eval_input_digests(spec, record.result.to_dict())
        if (evaluated.identity.spec_digest != spec_digest or evaluated.identity.execution_digest != execution_digest
                or evaluated.job_id != job["job_id"] or evaluated.execution_id != record.result.execution_id
                or {c.check_id for c in evaluated.checks} != {c["check_id"] for c in checks}):
            raise TaskContractError("Completion evaluation is stale or tampered")
        eval_ref = {"ref_type": "artifact", "ref": f"runtime-eval:{evaluated.eval_id}",
                    "description": "Canonical deterministic EvalResult"}
    else:
        run = EvalRunner(eval_store, clock=runtime.clock).run_persisted(spec, runtime.execution_store)
        evaluated, eval_ref = run.result, run.artifact_ref
    if evaluated.status != "pass":
        raise TaskContractError("Task acceptance criteria/required checks did not pass")
    artifact_digests = {}
    for output in c["expected_outputs"]:
        ref = output["ref"]
        if output["ref_type"] == "file":
            if not any(e["path"] == ref for e in c["required_evidence"]):
                raise TaskContractError("File deliverable requires pinned independently observed evidence")
        elif ref.startswith("runtime-provider-output:"):
            store = getattr(runtime, "provider_artifact_store", None)
            identity = ref.split(":", 1)[1]
            if store is None or identity != record.result.execution_id:
                raise TaskContractError("Provider deliverable is missing or belongs to another execution")
            artifact = store.load(identity)
            artifact_digests[ref] = digest(artifact)
            if (type(artifact) is not dict or artifact.get("execution_id") != identity
                    or type(artifact.get("process")) is not dict
                    or artifact["process"].get("status") != "succeeded"):
                raise TaskContractError("Provider deliverable has no successful process evidence")
        elif ref.startswith("runtime-mutation:"):
            store = getattr(runtime, "mutation_artifact_store", None)
            identity = ref.split(":", 1)[1]
            if store is None or identity != record.result.execution_id:
                raise TaskContractError("Mutation deliverable is missing or belongs to another execution")
            artifact = store.load(identity)
            artifact_digests[ref] = digest(artifact)
            if type(artifact) is not dict or artifact.get("execution_id") != identity or artifact.get("job_id") != job["job_id"]:
                raise TaskContractError("Mutation deliverable is not bound to this task")
        else:
            raise TaskContractError("Deliverable has no supported independently verifiable evidence source")
    review_ref = review_digest = None
    if job["review_required"]:
        if runtime.review_store is None:
            raise TaskContractError("DONE requires persisted independent review")
        review_refs = [r["ref"] for r in job["output_refs"] if r["ref"].startswith("runtime-review:")]
        if not review_refs:
            raise TaskContractError("DONE requires persisted independent review")
        review_record = runtime.review_store.load(review_refs[-1].split(":", 1)[1])
        review_ref = review_refs[-1]
        review_digest = digest(review_record)
        if type(review_record.get("schema_version")) is not int or review_record["schema_version"] != 1:
            raise TaskContractError("Review artifact version is malformed")
        review = review_record.get("result")
        try:
            review_validator().validate(review)
        except JobValidationError as error:
            raise TaskContractError("Required review artifact is malformed") from error
        approved_human = job.get("approval", {}).get("requested_action") == "COMPLETE_REVIEWED_JOB"
        if (review.get("job_id") != job["job_id"] or review.get("execution_id") != record.result.execution_id
                or review.get("reviewer") == job["agent"]
                or not review.get("deterministic_checks")
                or not review.get("evidence_refs")
                or review_record.get("task_contract_digest") != digest(c)
                or review_record.get("execution_request_digest") != digest(record.request)
                or review.get("decision") not in ({"PASS", "NEEDS_HUMAN"} if approved_human else {"PASS"})
                or any(check.get("status") != "PASS" for check in review.get("deterministic_checks", []))):
            raise TaskContractError("Required independent review gate is unsatisfied")
        if datetime.fromisoformat(review["created_at"].replace("Z", "+00:00")) < datetime.fromisoformat(record.result.completed_at.replace("Z", "+00:00")):
            raise TaskContractError("Required review predates execution evidence")
    approval_digests = {}
    approval_root = None
    approval_required = (c["approval_requirements"]["execution"]
                         or c["approval_requirements"]["completion"] or job.get("approval") is not None)
    if approval_required or (verify_only and job["task_completion"].get("approval_digests")):
        from runtime.approvals.store import ApprovalStoreError
        store = getattr(runtime, "approval_store", None)
        if store is None:
            raise TaskContractError("DONE requires the canonical approval evidence store")
        try:
            records = store.completion_evidence(job, record.result.execution_id,
                review_ref.split(":", 1)[1] if review_ref else None,
                pinned_refs=list(job["task_completion"]["approval_digests"]) if verify_only else None)
        except ApprovalStoreError as error:
            raise TaskContractError(f"Task approval evidence is invalid: {error}") from error
        approval_digests = {ref: digest(value) for ref, value in records.items()}
        approval_root = str(store.root.resolve())
    if c["approval_requirements"]["completion"]:
        approval = job.get("approval", {})
        if approval.get("requested_action") != "COMPLETE_REVIEWED_JOB" or approval.get("status") != "APPROVED":
            raise TaskContractError("DONE requires canonical human completion approval")
    proof = {"schema_version": 2, "contract_digest": digest(c), "execution_id": record.result.execution_id,
             "execution_digest": digest(record.to_dict()), "eval_id": evaluated.eval_id,
             "eval_digest": digest(evaluated.to_dict()),
             "review_ref": review_ref, "review_digest": review_digest,
             "artifact_digests": artifact_digests,
             "approval_digests": approval_digests, "approval_store_root": approval_root,
             "accepted_at": runtime.clock(), "execution_store_root": str(runtime.execution_store.root.resolve()),
             "review_store_root": str(runtime.review_store.root.resolve()) if job["review_required"] else None,
             "provider_store_root": str(getattr(runtime, "provider_artifact_store", None).root.resolve()) if getattr(runtime, "provider_artifact_store", None) else None,
             "mutation_store_root": str(getattr(runtime, "mutation_artifact_store", None).root.resolve()) if getattr(runtime, "mutation_artifact_store", None) else None}
    validate_binding(job, now=proof["accepted_at"], executing=True)
    if verify_only and proof != job["task_completion"]:
        raise TaskContractError("Persisted completion proof is stale or tampered")
    return eval_ref, proof


def verify_completion(runtime, job):
    """DONE is backed by immutable observations, not mutable source files.

    Recheck persisted execution/eval/review evidence after restart. A file may
    legitimately change later; its original observed digest stays in EvalResult.
    """
    from types import SimpleNamespace
    from runtime.storage.execution_store import FileExecutionStore
    from runtime.review.store import FileReviewStore
    from runtime.providers.artifacts import FileProviderArtifactStore
    from runtime.actions.store import FileMutationArtifactStore
    from runtime.approvals.store import FileApprovalStore
    proof = job.get("task_completion")
    if not isinstance(proof, dict):
        raise TaskContractError("DONE has no persisted completion proof")
    if type(proof.get("schema_version")) is not int or proof["schema_version"] != 2:
        raise TaskContractError("Pre-F1 completion requires explicit recovery; no automatic migration")
    runtime.task_contract_store.verify_completion(job["job_id"], proof)
    proxy = SimpleNamespace(store=runtime.store, clock=lambda: proof["accepted_at"],
        approval_store=FileApprovalStore(Path(proof["approval_store_root"])) if proof["approval_store_root"] else None,
        execution_store=FileExecutionStore(Path(proof["execution_store_root"])),
        review_store=FileReviewStore(Path(proof["review_store_root"])) if proof["review_store_root"] else None,
        provider_artifact_store=FileProviderArtifactStore(Path(proof["provider_store_root"])) if proof["provider_store_root"] else None,
        mutation_artifact_store=FileMutationArtifactStore(Path(proof["mutation_store_root"])) if proof["mutation_store_root"] else None)
    completion(proxy, job, verify_only=True)
