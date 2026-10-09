"""ORCH-01 acceptance through real Job/Worker/Approval/Retry owners."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime, RuntimeError as JobError
from runtime.core.references import CanonicalReferenceResolver
from runtime.executors.local import LocalExecutor
from runtime.graph.executor import DeterministicGraphExecutor
from runtime.graph.models import GraphError, node_id
from runtime.graph.planner import GraphPlanner
from runtime.graph.runtime import GraphRuntime
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests.contract_fixtures import declare_fixture_contract
from runtime.workers.worker import Worker

REPOSITORY = Path(__file__).resolve().parents[2]


class GraphHarness:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.jobs = JobRuntime(self.root / "jobs")
        self.executions = FileExecutionStore(self.root / "executions")
        self.jobs.execution_store = self.executions
        self.jobs.retry_runtime.execution_store = self.executions
        self.approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "approvals"),
                                         execution_store=self.executions)
        self.graph = GraphRuntime(self.jobs, self.approvals)

    def payload(self, **overrides):
        value = dict(task="Accepted bounded test work", task_class="operations", agent="operations",
            workflow="operations", capability="operations_coordination", risk_level="low",
            approval_status="not_required", review_required=False, max_attempts=1,
            input_refs=[], output_refs=[], created_by="explicit-graph-test-owner")
        value.update(overrides)
        return declare_fixture_contract(value)

    def node(self, name, *, depends=(), kind="worker", profile="worker", **overrides):
        payload = self.payload(task="Accepted test unit " + name, **overrides)
        data = {k: payload[k] for k in ("task", "task_contract", "review_required", "input_refs")}
        result = dict(node_id=name, kind=kind, profile=profile, depends_on=list(depends), payload=data)
        if kind in {"deterministic", "merge", "fan_in", "fan_out"}:
            result["profile"] = "deterministic"
            result["operation"] = "collect"
        return result

    def create(self, nodes, *, edges=(), parallel=2, handoffs=0, budget=100, **overrides):
        payload = self.payload(execution_budget=budget if type(budget) is dict else {"max_execution_units": budget}, **overrides)
        # Allow narrower child reviewer gates without adding a new capability.
        if "independent_review" not in payload["task_contract"]["allowed_capabilities"]:
            payload["task_contract"]["allowed_capabilities"].append("independent_review")
        definition = GraphPlanner.build(nodes, edges=edges, max_parallel=parallel, max_handoffs=handoffs)
        return self.graph.create(payload, definition)

    def worker(self, mode="success", *, executor=None, reviewer=None):
        return Worker(self.jobs, CanonicalReferenceResolver(REPOSITORY),
            executor or LocalExecutor(mode), self.executions,
            reviewer_runtime=reviewer, approval_runtime=self.approvals)

    def factory(self, node, job):
        executor = DeterministicGraphExecutor(self.jobs) if "operation" in node else LocalExecutor()
        return self.worker(executor=executor)

    def execute(self, root, name, mode="success", **kwargs):
        view = self.graph.show(root["job_id"])
        worker = self.worker(mode, **kwargs)
        claim = self.jobs.claim(job_id=view["nodes"][name]["job_id"], claimed_by=worker.worker_id)
        self.assertIsNotNone(claim)
        return worker.run_claimed(claim["job_id"])


class GraphTests(GraphHarness, unittest.TestCase):
    def test_splitter_builds_canonical_parallel_topology(self):
        value = GraphPlanner.split([self.node("b"), self.node("a")],
            merge=self.node("join", kind="merge"), max_parallel=2)
        self.assertEqual([n["node_id"] for n in value["nodes"]], ["a", "b", "join"])
        self.assertEqual(value["nodes"][-1]["depends_on"], ["b", "a"])

    def test_graph_root_is_never_worker_work(self):
        root = self.create([self.node("a")])
        with self.assertRaises(JobError):
            self.jobs.enqueue(root["job_id"])
        self.assertEqual(self.worker().run_once().status, "no_work")

    def test_fan_out_restart_and_partial_fan_in(self):
        root = self.create([self.node("a"), self.node("b"), self.node("join", depends=("a", "b"), kind="merge")])
        first = self.graph.advance(root["job_id"])
        self.assertEqual(first["busy"], 2)
        self.assertEqual(self.execute(root, "a").status, "completed")
        restarted_jobs = JobRuntime(self.root / "jobs")
        restarted_jobs.execution_store = self.executions
        restarted_jobs.retry_runtime.execution_store = self.executions
        restarted_approvals = ApprovalRuntime(restarted_jobs, self.approvals.store, execution_store=self.executions)
        restarted = GraphRuntime(restarted_jobs, restarted_approvals)
        view = restarted.advance(root["job_id"])
        self.assertEqual(view["nodes"]["join"]["status"], "pending")
        self.assertEqual(view["nodes"]["b"]["job_id"], first["nodes"]["b"]["job_id"])
        self.assertEqual(self.execute(root, "b").status, "completed")
        self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        join = self.jobs.show(node_id(root["job_id"], "join"))
        self.assertEqual(len(join["graph_binding"]["dependency_jobs"]), 2)
        self.assertEqual(join["execution_budget"], root["execution_budget"])
        self.assertNotIn("task_completion", self.jobs.show(root["job_id"]))

    def test_capacity_is_preserved_across_restart(self):
        root = self.create([self.node(name) for name in "abcd"], parallel=2)
        self.graph.advance(root["job_id"])
        self.assertEqual(self.graph.advance(root["job_id"])["busy"], 2)
        self.execute(root, "a")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["busy"], 2)
        self.assertEqual(view["nodes"]["d"]["status"], "pending")

    def test_eight_concurrent_dispatches_admit_one_job_per_node(self):
        root = self.create([self.node("a"), self.node("b")])
        with ThreadPoolExecutor(max_workers=8) as pool:
            views = list(pool.map(lambda _: self.graph.advance(root["job_id"]), range(8)))
        self.assertEqual({v["busy"] for v in views}, {2})
        self.assertEqual(len(self.jobs.list()), 3)

    def test_duplicate_claimed_delivery_does_not_reexecute(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            self.assertEqual(worker.run_claimed(claim["job_id"]).status, "completed")
            worker.run_claimed(claim["job_id"])
            self.assertEqual(execute.call_count, 1)

    def test_parallel_workers_reach_barrier_together(self):
        root = self.create([self.node("a"), self.node("b")])
        barrier = threading.Barrier(2)
        class BarrierExecutor(LocalExecutor):
            def execute(self, request):
                barrier.wait(timeout=20)
                return super().execute(request)
        results = self.graph.run_ready(root["job_id"], lambda n, j: self.worker(executor=BarrierExecutor()))
        self.assertEqual([r.status for r in results], ["completed", "completed"], [r.to_dict() for r in results])

    def test_failed_branch_blocks_fan_in(self):
        root = self.create([self.node("a"), self.node("join", depends=("a",), kind="fan_in")])
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "a", "failure").status, "failed")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "failed")
        self.assertIsNone(view["nodes"]["join"]["job_id"])

    def test_cancelled_branch_blocks_fan_in(self):
        root = self.create([self.node("a"), self.node("join", depends=("a",))])
        view = self.graph.advance(root["job_id"])
        self.jobs.transition(view["nodes"]["a"]["job_id"], "cancelled")
        self.assertEqual(self.graph.advance(root["job_id"])["status"], "failed")

    def test_shared_budget_exhaustion_stops_remaining_work(self):
        root = self.create([self.node("a"), self.node("b")], parallel=1, budget=1)
        self.graph.run_ready(root["job_id"], self.factory)
        results = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[0].error["code"], "execution_budget_exhausted")
        self.assertEqual(self.graph.advance(root["job_id"])["status"], "failed")

    def test_human_gate_pauses_until_exact_child_approval(self):
        human = self.node("human", kind="human_gate")
        human["payload"]["task_contract"]["approval_requirements"]["execution"] = True
        root = self.create([human, self.node("after", depends=("human",))])
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "waiting_approval")
        self.assertEqual(self.worker().run_once().status, "no_work")
        pending = self.approvals.store.list()[0]
        self.approvals.resolve(pending.approval_id, decision="APPROVED", decided_by="test-owner")
        self.assertEqual(self.execute(root, "human").status, "completed")
        self.assertEqual(self.graph.advance(root["job_id"])["nodes"]["after"]["status"], "queued")

    def test_human_gate_rejection_propagates(self):
        human = self.node("human", kind="human_gate")
        human["payload"]["task_contract"]["approval_requirements"]["execution"] = True
        root = self.create([human, self.node("after", depends=("human",))])
        self.graph.advance(root["job_id"])
        pending = self.approvals.store.list()[0]
        self.approvals.resolve(pending.approval_id, decision="REJECTED", decided_by="test-owner")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "failed")
        self.assertIsNone(view["nodes"]["after"]["job_id"])

    def test_parent_approval_does_not_approve_child(self):
        node = self.node("a")
        node["payload"]["task_contract"]["approval_requirements"]["execution"] = True
        root = self.create([node], approval_status="required")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["busy"], 0)
        pending = self.approvals.store.list()[0]
        self.approvals.resolve(pending.approval_id, decision="APPROVED", decided_by="test-owner")
        self.assertEqual(self.worker().run_once().status, "no_work")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["nodes"]["a"]["status"], "waiting_approval")
        self.assertEqual(len(self.approvals.store.list()), 2)

    def test_narrower_child_contract_is_preserved(self):
        node = self.node("a")
        node["payload"]["task_contract"]["allowed_tools"] = ["local_executor"]
        node["payload"]["task_contract"]["delegation_level"] = "L0"
        root = self.create([node])
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "a").status, "completed")
        job = self.jobs.show(node_id(root["job_id"], "a"))
        self.assertEqual(job["task_contract"]["allowed_tools"], ["local_executor"])

    def test_correction_substitutes_accepted_result_in_fan_in(self):
        root = self.create([self.node("a"), self.node("repair"),
            self.node("join", depends=("a",), kind="merge")],
            edges=[dict(source="a", target="repair", kind="correction")], handoffs=1)
        first = self.graph.advance(root["job_id"])
        self.assertEqual(first["nodes"]["repair"]["status"], "dormant")
        self.execute(root, "a", "failure")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["nodes"]["repair"]["status"], "queued")
        self.execute(root, "repair")
        self.graph.run_ready(root["job_id"], self.factory)
        view = self.graph.show(root["job_id"])
        self.assertEqual(view["status"], "completed")
        join = self.jobs.show(view["nodes"]["join"]["job_id"])
        self.assertEqual(join["graph_binding"]["dependency_jobs"], [view["nodes"]["repair"]["job_id"]])

    def test_replan_handoff_bound_stops_chain(self):
        root = self.create([self.node("a"), self.node("b"), self.node("c")], edges=[
            dict(source="a", target="b", kind="replan"),
            dict(source="b", target="c", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        self.execute(root, "a", "failure")
        self.graph.advance(root["job_id"])
        self.execute(root, "b", "failure")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "failed")
        self.assertIsNone(view["nodes"]["c"]["job_id"])

    def test_replan_cycle_stops_without_admitting_work(self):
        root = self.create([self.node("a"), self.node("b")], edges=[
            dict(source="a", target="b", kind="replan"),
            dict(source="b", target="a", kind="replan")], handoffs=8)
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "failed")
        self.assertEqual(view["reason"], "replan_cycle")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_canonical_retry_reuses_graph_unit_and_budget(self):
        root = self.create([self.node("a")], max_attempts=2)
        self.graph.advance(root["job_id"])
        self.execute(root, "a", "failure")
        view = self.graph.advance(root["job_id"])
        job = self.jobs.show(view["nodes"]["a"]["job_id"])
        self.assertEqual(job["attempt"], 2)
        self.assertEqual(job["execution_budget"], root["execution_budget"])
        self.assertEqual(self.execute(root, "a").status, "completed")
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")

    def test_profiles_keep_existing_canonical_agents(self):
        nodes = [self.node("plan", kind="planner", profile="planner"),
                 self.node("split", depends=("plan",), kind="splitter", profile="splitter"),
                 self.node("research", depends=("split",), profile="researcher"),
                 self.node("explore", depends=("split",), profile="explorer")]
        root = self.create(nodes)
        for _ in range(3):
            self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual({j["agent"] for j in self.jobs.list()}, {"operations"})

    def test_deterministic_operations_use_certified_worker(self):
        for operation in ("collect", "deduplicate", "sort", "hash", "verify"):
            with self.subTest(operation=operation):
                node = self.node(operation, kind="deterministic")
                node["operation"] = operation
                root = self.create([node])
                outcome = self.graph.run_ready(root["job_id"], self.factory)[0]
                self.assertEqual(outcome.status, "completed")
                record = self.executions.load(outcome.execution_id, require_authority=True)
                self.assertIn(operation, record.result.summary)

    def test_missing_acceptance_never_completes_graph(self):
        node = self.node("a")
        node["payload"]["task_contract"]["acceptance_criteria"] = []
        root = self.create([node])
        outcome = self.graph.run_ready(root["job_id"], self.factory)[0]
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.error["code"], "task_completion_blocked")
        self.assertEqual(self.graph.advance(root["job_id"])["status"], "failed")

    def test_mixed_conditional_fan_in_activates_only_after_all_branches(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                root = self.create([self.node("a"), self.node("source"), self.node("repair"),
                    self.node("join", kind="merge", depends=("a", "repair"))],
                    edges=[dict(source="source", target="repair", kind="correction")], handoffs=1)
                self.graph.advance(root["job_id"])
                self.execute(root, "a")
                self.execute(root, "source", "failure" if failure else "success")
                view = self.graph.advance(root["job_id"])
                if failure:
                    self.assertEqual(view["nodes"]["repair"]["status"], "queued")
                    self.execute(root, "repair")
                    self.graph.run_ready(root["job_id"], self.factory)
                    self.assertEqual(self.graph.show(root["job_id"])["nodes"]["join"]["status"], "completed")
                else:
                    self.assertEqual(view["nodes"]["join"]["status"], "dormant")
                self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")


if __name__ == "__main__":
    unittest.main()
