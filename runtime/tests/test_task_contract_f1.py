"""GOV-01F1: R1 attacks at real authority, persistence and dispatch boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from runtime.tests import test_task_contract as fixtures
from runtime.tests import test_review as review_fixtures
from runtime.tests.test_continuation import Reviewer
from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.core.task_contract import encoded
from runtime.executors.local import LocalExecutor
from runtime.providers.models import ProviderExecutionResult
from runtime.workers.worker import Worker


class TaskContractF1Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TaskContractTests()
        self.fixture.setUp()
        self.root, self.runtime = self.fixture.root, self.fixture.runtime

    def tearDown(self):
        self.fixture.tearDown()

    def running(self):
        job = self.runtime.create(self.fixture.payload())
        self.runtime.enqueue(job["job_id"])
        return self.runtime.claim()

    def strengthen(self, job):
        value = deepcopy(job)
        value["review_required"] = True
        return self.runtime._save(value)

    def restarted(self):
        return JobRuntime(self.root / "jobs", clock=self.runtime.clock)

    def test_r1_review_gate_job_replay_fails_closed_before_execution_and_done(self):
        original = self.running()
        self.strengthen(original)
        self.runtime.store.save(original)
        restarted = self.restarted()
        for action in (lambda: restarted.show(original["job_id"]),
                       lambda: restarted.validate_execution_authority(original["job_id"], original["claimed_by"]),
                       lambda: restarted.complete(original["job_id"])):
            with self.assertRaises(RuntimeError):
                action()

    def test_strengthened_gate_survives_restart_without_new_authority(self):
        original = self.running()
        self.strengthen(original)
        loaded = self.restarted().show(original["job_id"])
        self.assertTrue(loaded["review_required"])
        self.assertEqual(loaded["task_contract"], original["task_contract"])
        self.assertEqual(loaded["approval_status"], original["approval_status"])

    def test_gate_acceptance_replay_and_missing_witnesses_fail_closed(self):
        for attack in ("gate-anchor", "gate-witness", "both-gates", "both-strengthening", "replay"):
            with self.subTest(attack=attack):
                job = self.runtime.create(self.fixture.payload())
                paths = [self.runtime.task_contract_store._path(job["job_id"], "gate-" + s)
                         for s in ("anchor", "witness")]
                baseline = [p.read_bytes() for p in paths]
                self.strengthen(job)
                if attack == "replay":
                    for p, raw in zip(paths, baseline):
                        p.write_bytes(raw)
                    self.runtime.store.save(job)
                elif attack == "both-gates":
                    for p in paths: p.unlink()
                elif attack == "both-strengthening":
                    for suffix in ("review-required-anchor", "review-required-witness"):
                        self.runtime.task_contract_store._path(job["job_id"], suffix).unlink()
                else:
                    self.runtime.task_contract_store._path(job["job_id"], attack).unlink()
                with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])
                self.runtime.store._path(job["job_id"]).unlink()

    def test_interrupted_strengthening_holds_original_job_after_restart(self):
        job = self.running()
        with patch.object(self.runtime.task_contract_store, "_replace", side_effect=OSError("crash")):
            with self.assertRaises(RuntimeError): self.strengthen(job)
        with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])

    def approved_completion(self, *, execution_approval=False):
        p = self.fixture.payload(review_required=True,
            approval_status="required" if execution_approval else "not_required")
        p["task_contract"]["approval_requirements"]["completion"] = True
        worker = Worker(self.runtime, self.fixture.worker.resolver,
            LocalExecutor(clock=self.runtime.clock), self.fixture.executions,
            reviewer_runtime=Reviewer("PASS"), clock=self.runtime.clock)
        job = self.runtime.create(p)
        execution_id = None
        if execution_approval:
            pending = worker.approval_runtime.request_execution(job["job_id"], reason="fixture execution authority")
            execution_id = pending.request.approval_id
            worker.approval_runtime.resolve(execution_id, decision="APPROVED", decided_by="owner")
        else:
            self.runtime.enqueue(job["job_id"])
        outcome = worker.run_once()
        self.assertEqual(outcome.status, "waiting_approval")
        resolved = worker.approval_runtime.resolve(outcome.approval["approval_id"],
            decision="APPROVED", decided_by="owner")
        self.assertEqual(resolved["job"]["status"], "completed")
        return resolved["job"], worker.approval_runtime.store, outcome.approval["approval_id"], execution_id

    def test_r1_missing_corrupt_rejected_and_replaced_completion_approval_invalidate_done(self):
        for attack in ("missing", "corrupt", "rejected", "replacement", "bool-version"):
            with self.subTest(attack=attack):
                job, store, approval_id, _ = self.approved_completion()
                path = store._path(approval_id)
                original = path.read_bytes()
                if attack == "missing": path.unlink()
                elif attack == "corrupt": path.write_text("{")
                else:
                    value = json.loads(path.read_text())
                    if attack == "rejected": value["status"] = "REJECTED"
                    elif attack == "bool-version": value["schema_version"] = True
                    else: value["decision_reason"] = "Replacement with the same exact approval identity"
                    path.write_text(json.dumps(value))
                with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])
                # Each attack is isolated; malformed old artifacts correctly
                # block the Worker's approval recovery on subsequent runs.
                path.write_bytes(original)
                self.runtime.store._path(job["job_id"]).unlink()

    def test_execution_and_completion_approvals_are_both_pinned(self):
        job, store, completion_id, execution_id = self.approved_completion(execution_approval=True)
        proof = job["task_completion"]
        self.assertEqual(set(proof["approval_digests"]),
            {"runtime-approval:" + completion_id, "runtime-approval:" + execution_id})
        self.assertEqual(self.restarted().show(job["job_id"])["status"], "completed")
        store._path(execution_id).unlink()
        with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])

    def test_compact_approval_cannot_replace_canonical_artifact(self):
        job, _, _, _ = self.approved_completion()
        job["approval"]["recorded_by"] = "self-appointed-agent"
        self.runtime.store.save(job)
        with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])

    def test_approval_receipt_and_store_root_cannot_be_rebound(self):
        for field in ("approval_digests", "approval_store_root"):
            job, _, _, _ = self.approved_completion()
            job["task_completion"][field] = {} if field == "approval_digests" else str(self.root / "replacement")
            self.runtime.store.save(job)
            with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])
            self.runtime.store._path(job["job_id"]).unlink()

    def test_pre_f1_creation_authority_requires_explicit_recovery(self):
        job = self.runtime.create(self.fixture.payload())
        for suffix in ("anchor", "witness"):
            path = self.runtime.task_contract_store._path(job["job_id"], suffix)
            value = json.loads(path.read_text())["boundary"]
            path.write_bytes(encoded(value))
        with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])

    def test_pre_f1_completion_receipt_is_not_silently_migrated(self):
        job, _ = self.fixture.run_job()
        job = self.runtime.show(job["job_id"])
        proof = job["task_completion"]
        proof["schema_version"] = 1
        proof.pop("approval_digests"); proof.pop("approval_store_root")
        self.runtime.store.save(job)
        with self.assertRaises(RuntimeError): self.restarted().show(job["job_id"])


class CapturingReviewAdapter(review_fixtures.FakeAdapter):
    def execute(self, request, context):
        self.calls += 1
        self.request = request
        return ProviderExecutionResult("succeeded", json.dumps({"decision": "PASS",
            "reason": "Canonical fixture evidence independently checked",
            "evidence_refs": list(context.available_evidence_refs[:1])}), "", 0)


class ReviewerAuthorityF1Tests(unittest.TestCase):
    def setUp(self):
        self.fixture = review_fixtures.ReviewerProviderTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def run_review(self, *, tools=None, capabilities=None, native=frozenset(), stop=None, eligible=None):
        original = self.fixture.payload
        def payload(**kwargs):
            p = original(**kwargs)
            if tools is not None: p["task_contract"]["allowed_tools"] = tools
            if capabilities is not None: p["task_contract"]["allowed_capabilities"] = capabilities
            if stop is not None: p["task_contract"]["stop_conditions"] = [stop]
            return p
        self.fixture.payload = payload
        self.codex = CapturingReviewAdapter("codex", available=True)
        self.claude = CapturingReviewAdapter("claude", available=True)
        self.codex.native_tools = native
        runtime, job, request, result = self.fixture.configured_runtime(executor_provider="claude",
            claude=self.claude, codex=self.codex)
        if eligible is not None:
            build = runtime.context_builder.build
            runtime.context_builder.build = lambda *args: replace(build(*args), eligible_providers=eligible)
        return runtime.run(job, request, result), job

    def test_r1_denied_provider_tool_cannot_dispatch_reviewer_or_complete(self):
        run, job = self.run_review(tools=["local_executor"])
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(run.result.error_category, "task_authority_blocked")
        self.assertFalse(run.result.model_review_performed)
        with self.assertRaises(RuntimeError):
            self.fixture.runtime.apply_review_decision(job["job_id"], decision="PASS",
                reason="Forge success", review_ref=run.artifact_ref)
        self.assertNotEqual(JobRuntime(self.fixture.job_root).show(job["job_id"])["status"], "completed")

    def test_missing_review_capability_blocks_provider(self):
        run, _ = self.run_review(capabilities=["software_implementation"])
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(run.result.error_category, "task_authority_blocked")

    def test_opaque_review_adapter_blocks_before_invocation(self):
        run, _ = self.run_review(native=None)
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(run.result.error_category, "task_authority_blocked")

    def test_valid_governed_review_preserves_gates_and_narrows_authority(self):
        run, job = self.run_review()
        self.assertEqual(run.result.decision, "PASS")
        self.assertEqual(self.codex.calls, 1)
        request = self.codex.request
        contract = request.to_dict()["task_contract"]
        parent = job["task_contract"]
        self.assertEqual(contract["allowed_capabilities"], ["independent_review"])
        self.assertEqual(contract["allowed_tools"], ["provider_call"])
        self.assertEqual(contract["approval_requirements"], parent["approval_requirements"])
        self.assertEqual(contract["budget_references"], parent["budget_references"])
        self.assertEqual(contract["stop_conditions"], parent["stop_conditions"])
        self.assertEqual(contract["objective"], request.task)
        self.assertIsNone(request.execution_scope)
        self.assertEqual(request.execution_mode, "READ_ONLY")
        self.assertEqual(self.fixture.runtime.show(job["job_id"])["status"], "reviewing")

    def test_provider_filter_is_preserved_by_review_dispatch(self):
        run, _ = self.run_review(eligible=("claude",))
        self.assertEqual(run.result.review_provider, "claude")
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(self.claude.calls, 1)

    def test_parent_stop_conditions_apply_to_reviewer_dispatch(self):
        run, _ = self.run_review(stop={"kind": "no_execution"})
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(run.result.error_category, "task_authority_blocked")


if __name__ == "__main__": unittest.main()
