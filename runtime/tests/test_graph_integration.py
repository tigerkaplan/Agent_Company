"""Graph restart, existing reviewer/human gates and CLI integration."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
from contextlib import contextmanager, redirect_stdout
from unittest.mock import patch
import unittest

from runtime.graph.models import node_id
from runtime.graph.runtime import GraphRuntime
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.review.context import ReviewContextBuilder
from runtime.review.runtime import ReviewerRuntime
from runtime.review.store import FileReviewStore
from runtime.review.verification import DeterministicVerifier
from runtime.tests.test_graph import GraphHarness, REPOSITORY
from runtime.tests.test_review import FakeReviewer


class GraphIntegrationTests(GraphHarness, unittest.TestCase):
    def test_reconstructed_parent_approval_uses_configured_canonical_owner(self):
        from runtime.approvals.runtime import ApprovalRuntime
        from runtime.approvals.store import FileApprovalStore
        self.approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "configured-approvals"),
                                         execution_store=self.executions)
        self.graph = GraphRuntime(self.jobs, self.approvals)
        node = self.node("a")
        node["payload"]["task_contract"]["approval_requirements"]["execution"] = True
        root = self.create([node], approval_status="required")
        self.graph.advance(root["job_id"])
        parent = self.approvals.store.list()[0]
        self.approvals.resolve(parent.approval_id, decision="APPROVED", decided_by="test-owner")
        self.graph.advance(root["job_id"])
        child = next(a for a in self.approvals.store.list() if a.job_id != root["job_id"])
        self.approvals.resolve(child.approval_id, decision="APPROVED", decided_by="test-owner")
        self.assertEqual(self.execute(root, "a").status, "completed")
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")

    def test_live_dispatch_waits_for_sibling_budget_publication(self):
        import threading
        from runtime.budget.store import FileExecutionBudgetStore
        from runtime.executors.local import LocalExecutor

        root = self.create([self.node("a"), self.node("b")])
        store = self.jobs.budget_store
        head_path = store._usage_head_path(root["execution_budget"]["budget_id"])
        barrier = threading.Barrier(2)
        both_started, head_written, reader_waiting = (threading.Event() for _ in range(3))
        reader = {}
        original_write = FileExecutionBudgetStore._write
        original_transaction = FileExecutionBudgetStore.transaction

        def pause_publication(owner, path, value):
            original_write(owner, path, value)
            if path == head_path and both_started.is_set() and not head_written.is_set():
                head_written.set()
                self.assertTrue(reader_waiting.wait(5), "Live reader bypassed the budget transaction")

        @contextmanager
        def observe_transaction(owner, **kwargs):
            if head_written.is_set() and threading.get_ident() == reader.get("thread"):
                reader_waiting.set()
            with original_transaction(owner, **kwargs):
                yield

        class PairedReadExecutor(LocalExecutor):
            def __init__(self, name):
                super().__init__()
                self.name = name

            def execute(executor, request):
                if executor.name == "b":
                    reader["thread"] = threading.get_ident()
                barrier.wait(timeout=20)
                both_started.set()
                if executor.name == "b":
                    self.assertTrue(head_written.wait(5))
                return super(PairedReadExecutor, executor).execute(request)

        with patch.object(FileExecutionBudgetStore, "_write", pause_publication), \
                patch.object(FileExecutionBudgetStore, "transaction", observe_transaction):
            outcomes = self.graph.run_ready(root["job_id"],
                lambda node, job: self.worker(executor=PairedReadExecutor(node["node_id"])))
        self.assertEqual([o.status for o in outcomes], ["completed", "completed"],
                         [o.to_dict() for o in outcomes])
        self.assertTrue(reader_waiting.is_set())

    def test_cli_uses_canonical_job_store_for_graph_batches(self):
        from runtime.cli.__main__ import run
        root = self.create([self.node("a", kind="deterministic")])
        prefix = ["--state-root", str(self.jobs.store.root), "--execution-root", str(self.executions.root),
                  "--approval-root", str(self.approvals.store.root), "graph"]
        output = io.StringIO()
        with redirect_stdout(output):
            code = run([*prefix, "run-once", root["job_id"]])
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["run"]["status"], "completed")
        self.assertEqual(result["outcomes"][0]["status"], "completed")
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")

    def test_profile_is_persisted_and_rendered_without_changing_agent(self):
        from runtime.providers.models import ExecutionPackage
        root = self.create([self.node("a", profile="explorer")])
        self.graph.advance(root["job_id"])
        outcome = self.execute(root, "a")
        record = self.executions.load(outcome.execution_id, require_authority=True)
        self.assertEqual(record.request["execution_profile"], "explorer")
        self.assertEqual(record.request["agent"], "operations")
        fields = ("task", "task_class", "project_id", "agent", "skill", "workflow", "capability",
                  "risk_level", "approval_status", "review_required", "attempt", "input_refs", "execution_profile")
        package = ExecutionPackage(**{k: record.request[k] for k in fields}, context=())
        self.assertIn('"execution_profile": "explorer"', package.render())
        self.assertIn("Execution role only", package.render())

    def test_controlled_write_scope_narrows_with_separate_child_approval(self):
        target = self.root / "target"
        target.mkdir()
        scope = dict(project_root=str(target), allowed_paths=["src"], forbidden_paths=[],
            write_mode="CREATE_OR_MODIFY", max_changed_files=4, max_artifact_bytes=65536,
            allow_tests=False, allow_git_reads=False, allow_protected_paths=False)
        narrowed = {**scope, "allowed_paths": ["src/component"], "max_changed_files": 1}
        overrides = dict(execution_mode="CONTROLLED_WRITE", execution_scope=narrowed,
            review_required=True, approval_status="required", risk_level="approval_required",
            capability="software_implementation", agent="software", task_class="software", workflow="software")
        node = self.node("write", **overrides)
        node["payload"].update(execution_mode="CONTROLLED_WRITE", execution_scope=narrowed)
        parent = {**overrides, "execution_scope": scope}
        root = self.create([node], **parent)
        self.graph.advance(root["job_id"])
        request = self.approvals.store.list("PENDING")[0]
        self.approvals.resolve(request.approval_id, decision="APPROVED", decided_by="test-owner")
        view = self.graph.advance(root["job_id"])
        child = self.jobs.show(view["nodes"]["write"]["job_id"])
        self.assertEqual(child["execution_scope"], narrowed)
        self.assertEqual(child["status"], "waiting_approval")
        self.assertEqual(child["task_contract"]["write_scope"], narrowed)

    def test_inflight_elapsed_budget_blocks_new_branch_without_refund(self):
        from runtime.budget.runtime import ExecutionBudgetRuntime
        class Clock:
            now = datetime(2026, 10, 3, tzinfo=timezone.utc)
            def __call__(self):
                return self.now.isoformat().replace("+00:00", "Z")
        clock = Clock()
        self.jobs.clock = clock
        root = self.create([self.node("a"), self.node("b")], budget={"max_elapsed_ms": 1000, "max_execution_units": 4})
        self.graph.advance(root["job_id"])
        a = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by="worker-a")
        budget = ExecutionBudgetRuntime(self.jobs.budget_store, wall_clock=clock)
        decision = budget.reserve_execution(root["execution_budget"], execution_id="execution-a", job_id=a["job_id"], job_runtime=self.jobs)
        self.assertEqual(decision.status, "ALLOW")
        clock.now += timedelta(seconds=2)
        b = self.jobs.claim(job_id=node_id(root["job_id"], "b"), claimed_by="worker-b")
        decision = budget.reserve_execution(root["execution_budget"], execution_id="execution-b", job_id=b["job_id"], job_runtime=self.jobs)
        self.assertEqual(decision.status, "DENY_EXHAUSTED")
        state = budget.recover(root["execution_budget"]).state
        self.assertEqual(state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertGreaterEqual(state["dimensions"]["elapsed_ms"]["consumed"], 2000)

    def review_runtime(self, decision):
        providers = FileProviderArtifactStore(self.root / "provider-output")
        reviews = FileReviewStore(self.root / "reviews")
        return ReviewerRuntime(DeterministicVerifier(self.executions, providers),
            ReviewContextBuilder(REPOSITORY, self.executions, providers),
            FakeReviewer(decision), reviews)

    def gate(self):
        return self.node("gate", kind="gate", profile="critic", review_required=True)

    def test_gate_waits_for_real_reviewer_store(self):
        root = self.create([self.gate(), self.node("after", depends=("gate",))])
        self.graph.advance(root["job_id"])
        outcome = self.execute(root, "gate")
        self.assertEqual(outcome.status, "reviewing")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "reviewing")
        self.assertIsNone(view["nodes"]["after"]["job_id"])
        self.assertNotIn("task_completion", self.jobs.show(view["nodes"]["gate"]["job_id"]))

    def test_reviewer_pass_unblocks_graph_gate(self):
        root = self.create([self.gate(), self.node("after", depends=("gate",))])
        self.graph.advance(root["job_id"])
        outcome = self.execute(root, "gate", reviewer=self.review_runtime("PASS"))
        self.assertEqual(outcome.status, "completed")
        gate = self.jobs.show(node_id(root["job_id"], "gate"))
        self.assertIsNotNone(gate["task_completion"]["review_digest"])
        self.assertEqual(self.graph.advance(root["job_id"])["nodes"]["after"]["status"], "queued")

    def test_reviewer_fail_rejects_gate_and_fan_in(self):
        root = self.create([self.gate(), self.node("after", depends=("gate",))])
        self.graph.advance(root["job_id"])
        outcome = self.execute(root, "gate", reviewer=self.review_runtime("FAIL"))
        self.assertEqual(outcome.status, "failed")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "failed")
        self.assertIsNone(view["nodes"]["after"]["job_id"])

    def test_reviewer_human_handoff_never_reexecutes_gate(self):
        root = self.create([self.gate(), self.node("after", depends=("gate",))])
        self.graph.advance(root["job_id"])
        worker = self.worker(reviewer=self.review_runtime("NEEDS_HUMAN"))
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "gate"), claimed_by=worker.worker_id)
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            outcome = worker.run_claimed(claim["job_id"])
            self.assertEqual(outcome.status, "waiting_approval")
            self.assertEqual(self.graph.advance(root["job_id"])["status"], "waiting_approval")
            pending = self.approvals.store.list("PENDING")[0]
            self.assertEqual(pending.requested_action, "COMPLETE_REVIEWED_JOB")
            self.approvals.resolve(pending.approval_id, decision="APPROVED", decided_by="test-owner")
            self.assertEqual(self.graph.advance(root["job_id"])["nodes"]["after"]["status"], "queued")
            self.assertEqual(execute.call_count, 1)

    def test_restart_after_first_admission_recovers_partial_fan_out(self):
        root = self.create([self.node("a"), self.node("b")])
        from runtime.graph import runtime as graph_module
        original = graph_module.child_payload
        def interrupt(root, node, *args):
            if node["node_id"] == "b":
                raise OSError("simulated process exit between admitted nodes")
            return original(root, node, *args)
        with patch.object(graph_module, "child_payload", side_effect=interrupt), self.assertRaises(OSError):
            self.graph.advance(root["job_id"])
        self.assertTrue(self.jobs.store.exists(node_id(root["job_id"], "a")))
        restarted = GraphRuntime(self.jobs, self.approvals)
        view = restarted.advance(root["job_id"])
        self.assertEqual(view["busy"], 2)
        self.assertEqual({v["status"] for v in view["nodes"].values()}, {"queued"})
        self.assertEqual(len(self.jobs.list()), 3)

    def test_restart_after_execution_persistence_reuses_result(self):
        root = self.create([self.node("a"), self.node("after", depends=("a",))])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        def interrupt(job, request, result, **kwargs):
            self.executions.create(request, result)
            raise OSError("simulated process exit after execution persistence")
        with patch.object(worker, "_record_result", side_effect=interrupt), self.assertRaises(OSError):
            worker.run_claimed(claim["job_id"])
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            view = self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual(view["nodes"]["a"]["status"], "completed")
        self.assertEqual(view["nodes"]["after"]["status"], "queued")

    def test_stale_dependency_proof_blocks_downstream_execution(self):
        root = self.create([self.node("a"), self.node("after", depends=("a",))])
        self.graph.advance(root["job_id"])
        outcome = self.execute(root, "a")
        self.graph.advance(root["job_id"])
        self.executions._path(outcome.execution_id).write_text("{}", encoding="utf-8")
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            self.assertEqual(worker.run_once().status, "worker_error")
            self.assertEqual(execute.call_count, 0)

    def test_parallel_shared_budget_cannot_overadmit_execution(self):
        root = self.create([self.node("a"), self.node("b")], budget=1)
        outcomes = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(sorted(outcome.status for outcome in outcomes), ["completed", "failed"])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
