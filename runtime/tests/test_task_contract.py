"""GOV-01 adversarial tests through real JobRuntime/Worker/store boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace

from runtime.actions.authorization import authorization_fingerprint
from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.core.task_contract import default_contract, validate, TaskContractError, require_tool
from runtime.execution.models import ExecutionRequest, ExecutionResult, ExecutionContractError
from runtime.executors.local import LocalExecutor
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker

ROOT = Path(__file__).resolve().parents[2]


def explicit_contract(payload):
    """An explicitly declared fixture acceptance, never production fallback."""
    job = {"execution_mode": "READ_ONLY", "execution_scope": None,
           "input_refs": [], "approval_status": "not_required", **deepcopy(payload)}
    c = default_contract(job)
    c["acceptance_criteria"] = [{"criterion_id": "fixture_integrity",
        "description": "Validate the deterministic execution fixture and absence of blockers",
        "check_ids": ["result_contract", "no_blockers"]}]
    return c


class TaskContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = JobRuntime(self.root / "jobs", clock=lambda: "2026-10-02T12:00:00Z")
        self.executions = FileExecutionStore(self.root / "executions")
        self.worker = Worker(self.runtime, CanonicalReferenceResolver(ROOT), LocalExecutor(),
                             self.executions, clock=self.runtime.clock)

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, **overrides):
        p = {"task": "Validate the deterministic execution fixture", "task_class": "operations",
             "agent": "operations", "workflow": "operations", "capability": "operations_coordination",
             "risk_level": "low", "approval_status": "not_required", "review_required": False,
             "created_by": "human", "input_refs": [], "max_attempts": 2, **overrides}
        p.setdefault("task_contract", explicit_contract(p))
        return p

    def run_job(self, payload=None):
        job = self.runtime.create(payload or self.payload())
        self.runtime.enqueue(job["job_id"])
        return job, self.worker.run_once()

    def test_exact_contract_worker_completion_and_eval_persistence(self):
        job, outcome = self.run_job()
        self.assertEqual(outcome.status, "completed")
        stored = self.runtime.show(job["job_id"])
        self.assertTrue(any(r["ref"].startswith("runtime-eval:") for r in stored["output_refs"]))
        self.assertEqual(stored["task_contract"], self.executions.load(outcome.execution_id).request["task_contract"])

    def test_undeclared_acceptance_never_becomes_done(self):
        p = self.payload(); p.pop("task_contract")
        job, outcome = self.run_job(p)
        self.assertNotEqual(outcome.status, "completed")
        self.assertEqual(self.executions.load(outcome.execution_id).result.status, "succeeded")
        self.assertNotEqual(self.runtime.show(job["job_id"])["status"], "completed")

    def test_manual_complete_without_execution_rejected(self):
        job = self.runtime.create(self.payload()); self.runtime.enqueue(job["job_id"]); self.runtime.claim()
        with self.assertRaisesRegex(RuntimeError, "execution evidence"):
            self.runtime.complete(job["job_id"])

    def test_missing_tool_blocks_actual_executor(self):
        p = self.payload(); p["task_contract"]["allowed_tools"] = ["provider_call"]
        _, outcome = self.run_job(p)
        self.assertNotEqual(outcome.status, "completed")

    def test_scope_and_capability_tampering_fails_closed(self):
        for field, value in (("objective", "another task"), ("allowed_capabilities", ["other"]),
                             ("write_scope", {}), ("budget_references", {}), ("risk", "medium")):
            with self.subTest(field=field):
                p = self.payload(); p["task_contract"][field] = value
                with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_contract_strict_types_unknown_fields_and_bounds(self):
        for field, value in (("schema_version", True), ("schema_version", "1"),
                             ("approval_requirements", {"execution": 1, "review": False, "completion": False}),
                             ("delegation_level", "L6"), ("allowed_tools", ["git_commit"]),
                             ("objective", "x" * 4097), ("stop_conditions", []), ("bogus", True)):
            with self.subTest(field=field):
                p = self.payload(); p["task_contract"][field] = value
                with self.assertRaises((TaskContractError, RuntimeError)): self.runtime.create(p)

    def test_acceptance_check_must_exist_and_be_unique(self):
        for change in ("missing", "duplicate"):
            p = self.payload()
            if change == "missing": p["task_contract"]["acceptance_criteria"][0]["check_ids"] = ["invented"]
            else: p["task_contract"]["required_checks"].append(deepcopy(p["task_contract"]["required_checks"][0]))
            with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_l0_cannot_allocate_deliverables(self):
        p = self.payload(); p["task_contract"]["delegation_level"] = "L0"
        p["task_contract"]["expected_outputs"] = [{"ref_type": "artifact", "ref": "fake"}]
        with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_higher_levels_do_not_inherit_approval(self):
        for level in ("L4", "L5"):
            p = self.payload(); p["task_contract"]["delegation_level"] = level
            with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_irreversibility_external_blast_radius_require_gates(self):
        for field, value in (("reversibility", "irreversible"), ("blast_radius", "external")):
            p = self.payload(); p["task_contract"][field] = value
            with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_approval_cannot_be_weakened(self):
        p = self.payload(); p["task_contract"]["approval_requirements"]["execution"] = True
        with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_no_execution_and_stale_deadline_stop_before_provider(self):
        for stop in ({"kind": "no_execution"}, {"kind": "deadline", "at": "2026-10-01T00:00:00Z"}):
            p = self.payload(); p["task_contract"]["stop_conditions"] = [stop]
            _, outcome = self.run_job(p)
            self.assertIsNone(outcome.execution_id)
            self.assertNotEqual(outcome.status, "completed")

    def test_deadline_expiring_during_execution_blocks_done(self):
        class AdvancingExecutor(LocalExecutor):
            def execute(inner, request):
                result = super().execute(request)
                self.runtime.clock = lambda: "2100-01-01T00:00:00Z"
                return result
        self.worker.executor = AdvancingExecutor()
        p = self.payload(); p["task_contract"]["stop_conditions"] = [{"kind": "deadline", "at": "2099-10-02T13:00:00Z"}]
        _, outcome = self.run_job(p)
        self.assertNotEqual(outcome.status, "completed")

    def test_pinned_real_evidence_verified_missing_or_tampered_denied(self):
        for state in ("valid", "missing", "tampered"):
            with self.subTest(state=state):
                file = self.root / (state + ".txt")
                if state != "missing": file.write_text("valid" if state == "valid" else "fake")
                p = self.payload(); p["task_contract"]["required_evidence"] = [{"path": str(file), "sha256": hashlib.sha256(b"valid").hexdigest()}]
                _, outcome = self.run_job(p)
                self.assertEqual(outcome.status == "completed", state == "valid")

    def test_provider_declared_fake_artifact_cannot_meet_output(self):
        class ClaimingExecutor(LocalExecutor):
            def execute(inner, request):
                result = super().execute(request)
                ref = {"ref_type": "artifact", "ref": "fake"}
                return replace(result, output_refs=(ref,), artifacts=(ref,))
        self.worker.executor = ClaimingExecutor()
        p = self.payload(); p["task_contract"]["expected_outputs"] = [{"ref_type": "artifact", "ref": "fake"}]
        _, outcome = self.run_job(p)
        self.assertNotEqual(outcome.status, "completed")

    def test_mutated_job_and_anchor_loss_survive_restart_fail_closed(self):
        for state in ("task", "weaken", "remove_contract", "anchor", "witness"):
            with self.subTest(state=state):
                job = self.runtime.create(self.payload())
                if state in {"anchor", "witness"}:
                    self.runtime.task_contract_store._path(job["job_id"], state).unlink()
                else:
                    altered = deepcopy(job)
                    if state == "task": altered["task"] = "new task"
                    elif state == "weaken": altered["task_contract"]["required_checks"] = []
                    else: altered.pop("task_contract")
                    self.runtime.store.save(altered)
                with self.assertRaises(RuntimeError): JobRuntime(self.root / "jobs").show(job["job_id"])
                # Restore only in the isolated test, to allow the next case.
                self.runtime.store._path(job["job_id"]).unlink()

    def test_original_review_cannot_be_weakened(self):
        job = self.runtime.create(self.payload(review_required=True)); job["review_required"] = False
        job["task_contract"]["approval_requirements"]["review"] = False
        self.runtime.store.save(job)
        with self.assertRaises(RuntimeError): self.runtime.show(job["job_id"])

    def test_contract_in_approval_fingerprint_and_immutable_request(self):
        job = self.runtime.create(self.payload()); altered = deepcopy(job)
        altered["task_contract"]["allowed_tools"] = []
        self.assertNotEqual(authorization_fingerprint(job), authorization_fingerprint(altered))
        self.runtime.enqueue(job["job_id"]); claim = self.runtime.claim()
        request = self.worker._build_request(claim, "exec-test", ())
        with self.assertRaises(TypeError): request.task_contract["delegation_level"] = "L5"
        with self.assertRaises(TaskContractError): require_tool(replace(request, task_contract=None), "local_executor")

    def test_review_reference_alone_never_completes(self):
        p = self.payload(review_required=True)
        job, outcome = self.run_job(p)
        self.assertEqual(outcome.status, "reviewing")
        with self.assertRaises(RuntimeError):
            self.runtime.apply_review_decision(job["job_id"], decision="PASS", reason="self-approved",
                review_ref={"ref_type": "review", "ref": "runtime-review:invented"})

    def test_retry_inherits_contract_and_logical_budget(self):
        p = self.payload(execution_budget={"max_execution_units": 2}); job = self.runtime.create(p)
        self.runtime.enqueue(job["job_id"]); self.runtime.claim()
        self.runtime.fail(job["job_id"], code="failure", message="fixture", retryable=True,
                          failure_class="transient_execution")
        child = self.runtime.retry(job["job_id"])
        self.assertEqual(child["task_contract"], job["task_contract"])
        self.assertEqual(child.get("execution_budget"), job.get("execution_budget"))
        self.assertIsNotNone(child["execution_budget"])

    def test_completed_task_evidence_loss_fails_closed_after_restart(self):
        for source in ("execution", "eval", "proof"):
            with self.subTest(source=source):
                job, outcome = self.run_job()
                stored = self.runtime.show(job["job_id"])
                if source == "execution": self.executions._path(outcome.execution_id).unlink()
                elif source == "eval":
                    (self.root / "evals" / (stored["task_completion"]["eval_id"] + ".eval.json")).unlink()
                else:
                    stored["task_completion"]["contract_digest"] = "0" * 64
                    self.runtime.store.save(stored)
                with self.assertRaises(RuntimeError): JobRuntime(self.root / "jobs").show(job["job_id"])
                self.runtime.store._path(job["job_id"]).unlink()

    def test_file_observation_is_persisted_not_reinvented_after_restart(self):
        file = self.root / "evidence.txt"; file.write_text("observed")
        p = self.payload(); p["task_contract"]["required_evidence"] = [{"path": str(file), "sha256": hashlib.sha256(b"observed").hexdigest()}]
        job, outcome = self.run_job(p)
        self.assertEqual(outcome.status, "completed")
        file.write_text("subsequent authorized project state")
        self.assertEqual(JobRuntime(self.root / "jobs").show(job["job_id"])["status"], "completed")

    def test_completion_timestamp_roots_and_eval_receipt_cannot_be_rewritten(self):
        for field in ("accepted_at", "execution_store_root", "eval_digest"):
            with self.subTest(field=field):
                job, _ = self.run_job()
                stored = self.runtime.show(job["job_id"])
                stored["task_completion"][field] = ("2026-10-01T00:00:00Z" if field == "accepted_at"
                    else str(self.root / "alternate") if field.endswith("root") else "0" * 64)
                self.runtime.store.save(stored)
                with self.assertRaises(RuntimeError): JobRuntime(self.root / "jobs").show(job["job_id"])
                self.runtime.store._path(job["job_id"]).unlink()

    def test_completion_receipt_loss_or_tampering_fails_closed(self):
        for suffix in ("completion-witness", "completion-anchor"):
            with self.subTest(suffix=suffix):
                job, _ = self.run_job()
                self.runtime.task_contract_store._path(job["job_id"], suffix).unlink()
                with self.assertRaises(RuntimeError): JobRuntime(self.root / "jobs").show(job["job_id"])
                self.runtime.store._path(job["job_id"]).unlink()

    def test_direct_executor_respects_stop_and_unapproved_contract(self):
        job = self.runtime.create(self.payload()); self.runtime.enqueue(job["job_id"]); claim = self.runtime.claim()
        request = self.worker._build_request(claim, "direct", ())
        for condition in ("stop", "deadline", "approval"):
            c = request.to_dict()["task_contract"]
            if condition == "stop": c["stop_conditions"] = [{"kind": "no_execution"}]
            elif condition == "deadline": c["stop_conditions"] = [{"kind": "deadline", "at": "2000-01-01T00:00:00Z"}]
            else: c["approval_requirements"]["execution"] = True
            with self.assertRaises(TaskContractError): LocalExecutor().execute(replace(request, task_contract=c))

    def test_opaque_cli_native_tools_are_blocked_before_runner(self):
        from runtime.providers.adapters import CliProviderAdapter
        from runtime.tests.test_providers import CliAdapterTests
        job = self.runtime.create(self.payload()); self.runtime.enqueue(job["job_id"]); claim = self.runtime.claim()
        request = self.worker._build_request(claim, "opaque-cli", ())
        calls = []
        adapter = CliProviderAdapter(CliAdapterTests.config(), ROOT, which=lambda _: "fake.exe",
            runner=lambda *a, **k: calls.append(1))
        with self.assertRaises(TaskContractError): adapter.execute(request, None)
        self.assertEqual(calls, [])

    def test_explicit_completion_approval_uses_existing_human_boundary(self):
        from runtime.tests.test_continuation import Reviewer
        p = self.payload(review_required=True)
        p["task_contract"]["approval_requirements"]["completion"] = True
        self.worker = Worker(self.runtime, CanonicalReferenceResolver(ROOT), LocalExecutor(clock=self.runtime.clock),
            self.executions, reviewer_runtime=Reviewer("PASS"), clock=self.runtime.clock)
        job, outcome = self.run_job(p)
        self.assertEqual(outcome.status, "waiting_approval")
        self.assertEqual(outcome.review["decision"], "PASS")
        self.assertEqual(self.runtime.review_store.load(outcome.review["review_id"])["result"]["decision"], "PASS")
        resolved = self.worker.approval_runtime.resolve(outcome.approval["approval_id"],
            decision="APPROVED", decided_by="human-owner")
        self.assertEqual(resolved["job"]["status"], "completed")

    def test_review_escalation_cannot_be_weakened_by_runtime_update(self):
        job = self.runtime.create(self.payload()); self.runtime.enqueue(job["job_id"]); claim = self.runtime.claim()
        strengthened = deepcopy(claim); strengthened["review_required"] = True
        self.runtime._save(strengthened)
        weakened = deepcopy(strengthened); weakened["review_required"] = False
        with self.assertRaisesRegex(RuntimeError, "cannot be weakened"):
            self.runtime._save(weakened)


if __name__ == "__main__": unittest.main()
