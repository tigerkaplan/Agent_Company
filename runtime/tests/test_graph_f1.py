"""ORCH-01-R1 exact reproductions and combined canonical-owner boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import threading
import time
import unittest
from unittest.mock import patch

from runtime.approvals.runtime import ApprovalRuntime
from runtime.core.jobs import ClaimContention, JobRuntime, RuntimeError as JobError
from runtime.core.task_contract import TaskContractError
from runtime.executors.local import LocalExecutor
from runtime.graph.models import GraphError, child_payload, node_id
from runtime.graph.planner import GraphPlanner
from runtime.graph.runtime import GraphRuntime
from runtime.storage.file_store import FileJobStore
from runtime.review.store import FileReviewStore
from runtime.tests.test_graph import GraphHarness
from runtime.tests import test_graph_integration as integration


class GraphF1Tests(GraphHarness, unittest.TestCase):
    def restart(self):
        self.jobs = JobRuntime(self.root / "jobs")
        self.jobs.execution_store = self.executions
        self.jobs.retry_runtime.execution_store = self.executions
        self.approvals = ApprovalRuntime(self.jobs, self.approvals.store,
                                         execution_store=self.executions,
                                         review_store=FileReviewStore(self.root / "reviews")
                                             if (self.root / "reviews").exists() else None)
        self.graph = GraphRuntime(self.jobs, self.approvals)

    def strengthen(self, job_id):
        job = self.jobs.show(job_id)
        job["review_required"] = True
        return self.jobs._save(job)

    def assert_review_pause(self, root, name):
        child = self.jobs.show(node_id(root["job_id"], name))
        self.assertTrue(child["review_required"])
        self.assertTrue(child["task_contract"]["approval_requirements"]["review"])
        outcome = self.execute(root, name)
        self.assertEqual(outcome.status, "reviewing", outcome.to_dict())
        self.assertNotIn("task_completion", self.jobs.show(child["job_id"]))
        self.assertNotEqual(self.graph.show(root["job_id"])["status"], "completed")

    def test_r1_public_effective_parent_review_survives_restart(self):
        payload = self.payload(execution_budget={"max_execution_units": 10})
        payload["review_required"] = True  # Stronger than immutable contract.
        root = self.graph.create(payload, GraphPlanner.build([self.node("a")], max_parallel=1))
        self.restart()
        self.graph.advance(root["job_id"])
        self.assert_review_pause(root, "a")

    def test_r1_strengthened_parent_review_survives_restart(self):
        root = self.create([self.node("a")])
        self.strengthen(root["job_id"])
        self.restart()
        self.graph.advance(root["job_id"])
        self.assert_review_pause(root, "a")

    def test_r1_pending_parent_execution_approval_blocks_and_resumes_exactly(self):
        payload = self.payload(execution_budget={"max_execution_units": 10})
        payload["approval_status"] = "required"
        root = self.graph.create(payload, GraphPlanner.build([self.node("a")], max_parallel=1))
        pending = self.approvals.request_execution(root["job_id"], reason="Explicit parent requirement")
        self.restart()
        for _ in range(2):
            view = self.graph.advance(root["job_id"])
            self.assertEqual(view["status"], "waiting_approval")
            self.assertIsNone(view["nodes"]["a"]["job_id"])
            self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
        self.assertEqual(self.approvals.store.load(pending.request.approval_id).status, "PENDING")
        self.approvals.resolve(pending.request.approval_id, decision="APPROVED", decided_by="test-owner")
        self.restart()
        self.graph.advance(root["job_id"])
        child = self.jobs.show(node_id(root["job_id"], "a"))
        self.assertEqual(child["approval_status"], "requested")
        self.assertTrue(child["task_contract"]["approval_requirements"]["execution"])
        child_request = self.approvals.store.list("PENDING")[0]
        self.assertNotEqual(child_request.approval_id, pending.request.approval_id)
        self.assertIsNone(self.jobs.claim(job_id=child["job_id"]))
        self.approvals.resolve(child_request.approval_id, decision="APPROVED", decided_by="test-owner")
        self.assertEqual(self.execute(root, "a").status, "completed")

    def test_effective_parent_approval_required_is_requested_without_contract_boolean(self):
        payload = self.payload(execution_budget={"max_execution_units": 10})
        payload["approval_status"] = "required"
        root = self.graph.create(payload, GraphPlanner.build([self.node("a")]))
        self.assertEqual(self.graph.advance(root["job_id"])["status"], "waiting_approval")
        self.assertEqual(len(self.approvals.store.list("PENDING")), 1)
        self.assertEqual(len(self.jobs.store.list()), 1)

    def test_later_parent_strengthening_denies_stale_child_after_restart(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        self.strengthen(root["job_id"])
        self.restart()
        with self.assertRaises((GraphError, JobError)):
            self.jobs.claim(job_id=node_id(root["job_id"], "a"))
        self.assertEqual(list(self.executions.root.glob("*.json")), [])

    def test_r1_strengthened_source_replan_preserves_gate_after_restart(self):
        root = self.create([self.node("a"), self.node("repair"),
                            self.node("join", depends=("a",), kind="merge")],
            edges=[dict(source="a", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        self.strengthen(node_id(root["job_id"], "a"))
        self.assertEqual(self.execute(root, "a", "failure").status, "failed")
        self.restart()
        self.graph.advance(root["job_id"])
        self.assert_review_pause(root, "repair")
        self.assertIsNone(self.graph.advance(root["job_id"])["nodes"]["join"]["job_id"])

    def test_r1_declared_gate_correction_waits_for_real_review(self):
        root = self.create([self.node("gate", kind="gate", profile="critic", review_required=True),
                            self.node("repair"), self.node("after", depends=("gate",))],
            edges=[dict(source="gate", target="repair", kind="correction")], handoffs=1)
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "gate", "failure").status, "failed")
        self.restart()
        self.graph.advance(root["job_id"])
        target = self.jobs.show(node_id(root["job_id"], "repair"))
        self.assertTrue(target["task_contract"]["approval_requirements"]["review"])
        reviewer = integration.GraphIntegrationTests.review_runtime(self, "PASS")
        self.assertEqual(self.execute(root, "repair", reviewer=reviewer).status, "completed")
        target = self.jobs.show(target["job_id"])
        self.assertIsNotNone(target["task_completion"]["review_digest"])
        self.assertEqual(self.graph.advance(root["job_id"])["nodes"]["after"]["status"], "queued")

    def test_recovery_requires_fresh_execution_and_completion_approval(self):
        source = self.node("a", review_required=True)
        source["payload"]["task_contract"]["approval_requirements"].update(execution=True, completion=True)
        root = self.create([source, self.node("repair")],
            edges=[dict(source="a", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        original = self.approvals.store.list("PENDING")[0]
        self.approvals.resolve(original.approval_id, decision="APPROVED", decided_by="test-owner")
        self.assertEqual(self.execute(root, "a", "failure").status, "failed")
        self.restart()
        self.graph.advance(root["job_id"])
        replacement = self.jobs.show(node_id(root["job_id"], "repair"))
        self.assertEqual(replacement["task_contract"]["approval_requirements"],
                         {"execution": True, "review": True, "completion": True})
        pending = self.approvals.store.list("PENDING")[0]
        self.assertNotEqual(pending.approval_id, original.approval_id)
        self.assertIsNone(self.jobs.claim(job_id=replacement["job_id"]))
        self.approvals.resolve(pending.approval_id, decision="APPROVED", decided_by="test-owner")
        reviewer = integration.GraphIntegrationTests.review_runtime(self, "PASS")
        self.assertEqual(self.execute(root, "repair", reviewer=reviewer).status, "waiting_approval")
        completion = self.approvals.store.list("PENDING")[0]
        self.assertEqual(completion.requested_action, "COMPLETE_REVIEWED_JOB")
        self.restart()
        self.assertEqual(self.graph.advance(root["job_id"])["status"], "waiting_approval")
        self.approvals.resolve(completion.approval_id, decision="APPROVED", decided_by="test-owner")
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")

    def test_recovery_cannot_widen_source_tools_capabilities_or_delegation(self):
        root = self.create([self.node("a"), self.node("repair")])
        source = child_payload(root, self.node("a"))
        for field, narrow in (("allowed_tools", []), ("allowed_capabilities", ["operations_coordination"]),
                              ("delegation_level", "L0")):
            with self.subTest(field=field):
                constrained = deepcopy(source)
                constrained["task_contract"][field] = narrow
                target = self.node("repair")
                if field == "allowed_capabilities":
                    target["payload"]["task_contract"][field].append("independent_review")
                with self.assertRaises(TaskContractError):
                    child_payload(root, target, recovery_source={**constrained, "job_id": "source"})

    def test_recovery_keeps_source_stop_conditions_and_input_ceiling(self):
        root = self.create([self.node("a"), self.node("repair")])
        source = {**child_payload(root, self.node("a")), "job_id": "source"}
        stop = {"kind": "no_execution"}
        source["task_contract"]["stop_conditions"].append(stop)
        self.assertIn(stop, child_payload(root, self.node("repair"), recovery_source=source)
                      ["task_contract"]["stop_conditions"])
        ref = {"ref_type": "file", "ref": "README.md"}
        root = self.create([self.node("a"), self.node("repair", input_refs=[ref])], input_refs=[ref])
        source = {**child_payload(root, self.node("a")), "job_id": "source"}
        with self.assertRaisesRegex(GraphError, "input scope"):
            child_payload(root, self.node("repair", input_refs=[ref]), recovery_source=source)

    def test_pending_parent_gate_after_admission_denies_actual_dispatch(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        self.approvals.request_execution(root["job_id"], reason="New unresolved parent requirement")
        self.restart()
        with self.assertRaises((GraphError, JobError)):
            self.jobs.claim(job_id=node_id(root["job_id"], "a"))
        self.assertEqual(list(self.executions.root.glob("*.json")), [])

    def test_r1_sixteen_workers_reach_executor_barrier(self):
        root = self.create([self.node("branch-%02d" % i) for i in range(16)], parallel=16)
        barrier = threading.Barrier(16)
        arrivals = []
        arrival_times = []
        lock = threading.Lock()
        class BarrierExecutor(LocalExecutor):
            def execute(executor, request):
                with lock:
                    arrivals.append(request.job_id)
                    arrival_times.append(time.monotonic())
                barrier.wait(timeout=45)
                return super(BarrierExecutor, executor).execute(request)
        outcomes = self.graph.run_ready(root["job_id"], lambda n, j: self.worker(executor=BarrierExecutor()))
        self.assertFalse(barrier.broken, {"executor_arrivals": len(arrivals),
            "arrival_span_seconds": max(arrival_times) - min(arrival_times) if arrival_times else None,
            "outcomes": [o.to_dict() for o in outcomes]})
        self.finish_persisted_batch(root, outcomes, 16)
        self.assertEqual(len(set(arrivals)), 16)
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])

    def test_r1_sixteen_workers_without_barrier_restart_and_duplicate_admission(self):
        root = self.create([self.node("branch-%02d" % i) for i in range(16)], parallel=16)
        self.graph.advance(root["job_id"])
        self.restart()
        outcomes = self.graph.run_ready(root["job_id"], self.factory)
        self.finish_persisted_batch(root, outcomes, 16)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2))), [[], []])
        self.assertEqual(len(self.jobs.list()), 17)
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 16)

    def finish_persisted_batch(self, root, outcomes, count):
        self.assertEqual(len(outcomes), count)
        for outcome in outcomes:
            self.assertIn(outcome.status, {"completed", "execution_reserved"}, outcome.to_dict())
            self.assertEqual(outcome.result["status"], "succeeded")
            if outcome.status == "execution_reserved":
                self.assertIn(outcome.error["code"], {"claim_contention", "budget_contention"})
                self.assertFalse(outcome.error["retryable"])
                self.assertNotEqual(self.jobs.show(outcome.job_id)["status"], "completed")
        identities = {o.execution_id for o in outcomes}
        self.assertEqual(len(identities), count)
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            view = self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual(view["status"], "completed")
        self.assertEqual({p.stem for p in self.executions.root.glob("*.json")}, identities)

    def test_created_node_lifecycle_contention_stays_created_until_next_tick(self):
        root = self.create([self.node("a")])
        with patch.object(self.jobs, "enqueue", side_effect=ClaimContention("Bounded claim wait")):
            view = self.graph.advance(root["job_id"])
            self.assertEqual(view["nodes"]["a"]["status"], "created")
        self.restart()
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory)[0].status, "completed")
        self.assertEqual(len(self.jobs.list()), 2)

    def test_persisted_result_lock_contention_recovers_same_execution_without_reentry(self):
        root = self.create([self.node("a")])
        with patch.object(self.jobs, "record_execution_success", side_effect=ClaimContention("Bounded claim wait")):
            outcomes = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(outcomes[0].status, "execution_reserved")
        self.assertNotIn("task_completion", self.jobs.show(outcomes[0].job_id))
        self.finish_persisted_batch(root, outcomes, 1)

    @contextmanager
    def contended_lock(self):
        held, release = threading.Event(), threading.Event()
        owner = FileJobStore(self.jobs.store.root)
        def hold():
            with owner.claim_transaction():
                held.set()
                release.wait(timeout=30)
        thread = threading.Thread(target=hold)
        thread.start()
        self.assertTrue(held.wait(5))
        original = self.jobs.store.claim_transaction
        try:
            with patch.object(self.jobs.store, "claim_transaction",
                              side_effect=lambda **kw: original(timeout_seconds=0.03)):
                yield
        finally:
            release.set()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

    def test_real_admission_lock_timeout_leaves_exact_work_for_restart(self):
        root = self.create([self.node("a")])
        with self.contended_lock():
            self.assertEqual(self.graph.advance(root["job_id"])["nodes"]["a"]["status"], "pending")
            self.assertEqual(len(self.jobs.store.list()), 1)
        self.restart()
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory)[0].status, "completed")
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])

    def test_real_dispatch_lock_timeout_never_runs_stale_or_duplicate_claim(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        with self.contended_lock():
            with self.assertRaises(ClaimContention):
                self.jobs.claim(job_id=node_id(root["job_id"], "a"), lock_timeout_seconds=0.03)
            self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
            self.assertEqual(self.jobs.show(node_id(root["job_id"], "a"))["status"], "queued")
            self.assertEqual(list(self.executions.root.glob("*.json")), [])
        self.restart()
        with ThreadPoolExecutor(max_workers=2) as pool:
            deliveries = list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2)))
        self.assertEqual(sum(len(batch) for batch in deliveries), 1)
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 1)

    def test_contention_handler_does_not_swallow_authority_or_storage_errors(self):
        root = self.create([self.node("a")])
        with patch.object(self.jobs, "claim", side_effect=JobError("Invalid canonical authority")):
            with self.assertRaisesRegex(JobError, "Invalid canonical authority"):
                self.graph.run_ready(root["job_id"], self.factory)

    def test_intent_lock_timeout_keeps_claim_and_accounts_reserved_budget(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        held, release = threading.Event(), threading.Event()
        owner = FileJobStore(self.jobs.progress.store.root / ".transitions")
        def hold():
            with owner.claim_transaction():
                held.set()
                release.wait(timeout=30)
        thread = threading.Thread(target=hold)
        thread.start()
        self.assertTrue(held.wait(5))
        original = self.jobs.progress.transition_lock
        try:
            with patch.object(self.jobs.progress, "transition_lock",
                              side_effect=lambda **kw: original(timeout_seconds=0.03)):
                outcome = worker.run_claimed(claim["job_id"])
        finally:
            release.set()
            thread.join(timeout=5)
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(outcome.error["code"], "claim_contention")
        self.assertIsNone(worker.executor.last_request)
        self.assertEqual(outcome.budget["reservation"]["state"], "finalized")
        self.assertEqual(outcome.budget["state"]["dimensions"]["execution_units"]["consumed"], 1)
        self.restart()
        self.assertEqual(self.jobs.show(claim["job_id"])["claimed_by"], worker.worker_id)
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
        self.assertEqual(list(self.executions.root.glob("*.json")), [])

    def test_r1_consumed_dispatch_cannot_be_reopened_after_restart(self):
        from runtime.core.capability_governance import certified_dispatch
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        original = worker.executor.execute
        seen = {}
        class SimulatedExit(BaseException):
            pass
        def crash(request):
            seen["request"] = request
            original(request)
            raise SimulatedExit()
        with patch.object(worker.executor, "execute", side_effect=crash), self.assertRaises(SimulatedExit):
            worker.run_claimed(claim["job_id"])
        self.restart()
        with self.assertRaisesRegex(ValueError, "consumed"):
            with certified_dispatch(self.executions, seen["request"]):
                original(seen["request"])

    def test_intent_wait_cannot_authorize_an_expired_canonical_claim(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        worker.lease_seconds = 5
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id,
                                lease_seconds=5)
        original = self.jobs.progress.transition_lock
        @contextmanager
        def expire(**kwargs):
            with original(**kwargs):
                self.jobs.clock = lambda: (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
                yield
        with patch.object(self.jobs.progress, "transition_lock", side_effect=expire):
            outcome = worker.run_claimed(claim["job_id"])
        self.assertEqual(outcome.status, "worker_error")
        self.assertIsNone(worker.executor.last_request)
        self.assertEqual(list(self.executions.root.glob("*.json")), [])
        self.assertEqual(list((self.executions.root / ".decisions").glob("*.intent.*.json")), [])

    def test_exact_claim_enforces_due_time_and_finite_lock_bound(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        job_id = node_id(root["job_id"], "a")
        for wait in (True, 0, -1, 31, 10**1000, float("nan"), float("inf")):
            with self.subTest(wait=wait), self.assertRaises(JobError):
                self.jobs.claim(job_id=job_id, lock_timeout_seconds=wait)
        job = self.jobs.show(job_id)
        job["next_run_at"] = "2099-01-01T00:00:00Z"
        self.jobs._save(job)
        self.assertIsNone(self.jobs.claim(job_id=job_id))


if __name__ == "__main__":
    unittest.main()
