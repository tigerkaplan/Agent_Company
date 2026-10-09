"""Exact R2 contention properties plus bounded restart/continuation variants."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from runtime.budget.runtime import ExecutionBudgetRuntime
from runtime.core.jobs import RuntimeError as JobError
from runtime.graph.models import node_id
from runtime.tests.test_graph import GraphHarness


RECIPE = Path(__file__).resolve().parents[2] / "orchestrator/graph/reviews/ORCH-01-R2/probes.py"
spec = importlib.util.spec_from_file_location("orch01_r2_exact", RECIPE)
r2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2)


class GraphF2Tests(GraphHarness, unittest.TestCase):
    restart = r2.CombinedProbes.restart
    process_lock = r2.CombinedProbes.process_lock
    assert_no_live_claims = r2.CombinedProbes.assert_no_live_claims
    approve_pending = r2.CombinedProbes.approve_pending
    test_failed_source_replan_restart_claim_contention_defers_cleanly = (
        r2.CombinedProbes.test_failed_source_replan_restart_claim_contention_defers_cleanly)
    test_production_budget_lock_contention_does_not_permanently_fail_valid_batch = (
        r2.CombinedProbes.test_production_budget_lock_contention_does_not_permanently_fail_valid_batch)
    test_expired_preclaimed_batch_has_no_executor_entry = (
        r2.CombinedProbes.test_expired_preclaimed_batch_has_no_executor_entry)

    def observe(self, **data):
        # The immutable R2 functions are reused without their repository writers.
        self.observations = {**getattr(self, "observations", {}), **data}

    def capture_state(self, stage=None, *, held_lock=None):
        self.observations = {**getattr(self, "observations", {}), "stage": stage,
                             "jobs": self.jobs.store.list()}

    def assert_deferred(self, outcomes):
        self.assertTrue(outcomes)
        for outcome in outcomes:
            self.assertEqual(outcome.status, "execution_reserved", outcome.to_dict())
            self.assertEqual(outcome.error["code"], "budget_contention")
            self.assertEqual(outcome.budget["status"], "DEFER")
            self.assertFalse(outcome.budget["state"]["may_begin"])
            self.assertIsNone(outcome.execution_id)
            job = self.jobs.show(outcome.job_id)
            self.assertEqual(job["status"], "running")
            self.assertNotIn("error", job)
            self.assertIsNone(self.jobs.retry_runtime.persisted_decision(job))

    def test_failed_source_budget_contention_defers_decision_then_replans_once(self):
        root = self.create([self.node("source"), self.node("repair"),
                            self.node("join", depends=("source",), kind="merge")],
            edges=[dict(source="source", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "source", "failure").status, "failed")
        source = self.jobs.show(node_id(root["job_id"], "source"))
        self.restart()
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            for _ in range(2):
                self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
                self.assertIsNone(self.jobs.retry_runtime.persisted_decision(source))
                self.assertFalse(self.jobs.store.exists(node_id(root["job_id"], "repair")))
        self.restart()
        self.assertEqual([o.status for o in self.graph.run_ready(root["job_id"], self.factory)], ["completed"])
        self.restart()
        self.assertEqual([o.status for o in self.graph.run_ready(root["job_id"], self.factory)], ["completed"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2))), [[], []])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 3)
        self.assert_no_live_claims()

    def test_local_retry_budget_contention_preserves_unconsumed_attempt_and_identity(self):
        root = self.create([self.node("a"), self.node("join", depends=("a",), kind="merge")], max_attempts=2)
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "a", "failure").status, "failed")
        self.graph.advance(root["job_id"])
        retry_id = self.graph.show(root["job_id"])["nodes"]["a"]["job_id"]
        self.assertNotEqual(retry_id, node_id(root["job_id"], "a"))
        self.restart()
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            outcomes = self.graph.run_ready(root["job_id"], self.factory)
            self.assert_deferred(outcomes)
            self.assertIsNone(self.jobs.retry_runtime.execution_reservation(self.jobs.show(retry_id)))
        self.restart()
        self.graph.recover(root["job_id"], self.worker())
        self.assertEqual(self.jobs.show(retry_id)["status"], "queued")
        self.assertEqual(self.jobs.show(retry_id)["attempt"], 2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2)))
        self.assertEqual(sum(o.job_id == retry_id for b in batches for o in b), 1)
        self.restart()
        self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 3)
        state = self.worker().budget_runtime.state(root["execution_budget"])
        self.assertEqual(state.state["dimensions"]["execution_units"]["consumed"], 3)
        self.assert_no_live_claims()

    def test_budget_contention_recovery_stays_blocked_until_owner_returns(self):
        root = self.create([self.node("a"), self.node("b")])
        self.graph.advance(root["job_id"])
        self.restart()
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            self.assert_deferred(self.graph.run_ready(root["job_id"], self.factory))
            self.restart()
            view = self.graph.recover(root["job_id"], self.worker())
            self.assertEqual(view["status"], "running")
            self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
            self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
        self.restart()
        self.graph.recover(root["job_id"], self.worker())
        self.assertEqual([o.status for o in self.graph.run_ready(root["job_id"], self.factory)], ["completed", "completed"])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 2)
        self.assert_no_live_claims()

    def test_budget_contention_restart_preserves_review_completion_and_fan_in_gates(self):
        from runtime.tests.test_graph_integration import GraphIntegrationTests
        branch = self.node("a", review_required=True)
        branch["payload"]["task_contract"]["approval_requirements"]["completion"] = True
        root = self.create([branch, self.node("join", depends=("a",), kind="merge")])
        self.graph.advance(root["job_id"])
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            self.assert_deferred(self.graph.run_ready(root["job_id"], self.factory))
        self.restart()
        reviewer = GraphIntegrationTests.review_runtime(self, "PASS")
        self.graph.recover(root["job_id"], self.worker(reviewer=reviewer))
        outcome = self.graph.run_ready(root["job_id"], lambda n, j: self.worker(reviewer=reviewer))[0]
        self.assertEqual(outcome.status, "waiting_approval")
        self.assertIsNone(self.graph.show(root["job_id"])["nodes"]["join"]["job_id"])
        self.restart()
        recovering = self.worker(reviewer=GraphIntegrationTests.review_runtime(self, "PASS"))
        with patch.object(recovering.executor, "execute", wraps=recovering.executor.execute) as execute:
            self.graph.recover(root["job_id"], recovering)
            self.assertEqual(execute.call_count, 0)
        self.approve_pending(outcome.job_id)
        self.restart()
        self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 2)
        self.assert_no_live_claims()

    def test_finalization_contention_preserves_original_result_and_accounting(self):
        root = self.create([self.node("a"), self.node("join", depends=("a",), kind="merge")])
        worker = self.worker()
        finalize = worker.budget_runtime.finalize_execution
        def contended(*args, **kwargs):
            with self.process_lock(self.jobs.budget_store.root, owner="budget"):
                return finalize(*args, **kwargs)
        with patch.object(worker.budget_runtime, "finalize_execution", side_effect=contended):
            outcome = self.graph.run_ready(root["job_id"], lambda n, j: worker)[0]
        self.assertEqual(outcome.result["status"], "succeeded", outcome.to_dict())
        self.assertEqual(outcome.budget["status"], "DEFER")
        self.assertEqual(outcome.status, "execution_reserved")
        self.assertEqual(outcome.error["code"], "budget_contention")
        self.assertEqual(self.jobs.show(outcome.job_id)["status"], "running")
        self.assertNotIn("task_completion", self.jobs.show(outcome.job_id))
        # Delivery before accounting recovery must not turn an active source
        # reservation into a permanent STOP on the declared continuation.
        before_recovery = self.graph.run_ready(root["job_id"], self.factory)
        self.restart()
        recovering = self.worker()
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            pending = recovering.recover_persisted_results()
            self.assertEqual([o.status for o in pending], ["execution_reserved"])
            self.assertEqual(pending[0].execution_id, outcome.execution_id)
            self.assertEqual(pending[0].error["code"], "budget_contention")
            view = self.graph.recover(root["job_id"], recovering)
            self.assertEqual(view["status"], "running")
            self.assertNotIn("task_completion", self.jobs.show(outcome.job_id))
            self.assertIsNone(view["nodes"]["join"]["job_id"])
        with patch.object(recovering.executor, "execute", wraps=recovering.executor.execute) as execute:
            self.graph.recover(root["job_id"], recovering)
            self.assertEqual(execute.call_count, 0)
        state = recovering.budget_runtime.state(root["execution_budget"])
        self.assertEqual(state.state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertEqual(state.state["active_reservation_ids"], [])
        self.assertTrue(self.executions.exists(outcome.execution_id))
        resumed = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed",
                         "Transient finalization contention became a permanent downstream STOP")
        self.assertEqual(before_recovery, [])
        self.assertEqual([o.status for o in resumed], ["completed"])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 2)

    def test_budget_finalization_restart_blocks_authorized_continuation_until_accounted(self):
        root = self.jobs.create(self.payload(task="Step one",
            execution_budget={"max_execution_units": 100},
            continuation_plan={"plan_id": "plan-orch01-f2", "steps": [
                {"step_id": "STEP-001", "task": "Step one"},
                {"step_id": "STEP-002", "task": "Step two"}]}))
        self.jobs.enqueue(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=root["job_id"], claimed_by=worker.worker_id)
        finalize = worker.budget_runtime.finalize_execution
        def contended(*args, **kwargs):
            with self.process_lock(self.jobs.budget_store.root, owner="budget"):
                return finalize(*args, **kwargs)
        with patch.object(worker.budget_runtime, "finalize_execution", side_effect=contended):
            outcome = worker.run_claimed(claim["job_id"])
        self.assertEqual(outcome.status, "execution_reserved", outcome.to_dict())
        self.assertEqual(outcome.result["status"], "succeeded")
        self.assertEqual(outcome.error["code"], "budget_contention")
        self.restart()
        recovering = self.worker()
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            pending = recovering.recover_persisted_results()
            self.assertEqual([o.execution_id for o in pending], [outcome.execution_id])
            self.assertEqual(pending[0].error["code"], "budget_contention")
            self.assertEqual(recovering.continuation_runtime.recover(), [])
            self.assertEqual(len(self.jobs.list()), 1)
            self.assertEqual(self.jobs.show(root["job_id"])["status"], "running")
        self.restart()
        resumed = self.worker().run_once()
        self.assertEqual(resumed.status, "completed", resumed.to_dict())
        self.assertEqual(len(self.jobs.list()), 2)
        self.assertTrue(all(j["status"] == "completed" for j in self.jobs.list()))
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 2)
        self.assertTrue(self.executions.exists(outcome.execution_id))
        state = self.worker().budget_runtime.state(root["execution_budget"])
        self.assertEqual(state.state["dimensions"]["execution_units"]["consumed"], 2)
        self.assertEqual(state.state["active_reservation_ids"], [])

    def test_exhaustion_remains_stop_and_recovery_cannot_refund_it(self):
        root = self.create([self.node("a"), self.node("b", depends=("a",))], budget=1)
        self.graph.run_ready(root["job_id"], self.factory)
        outcomes = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual([o.status for o in outcomes], ["failed"])
        self.restart()
        self.graph.recover(root["job_id"], self.worker())
        failed = self.jobs.show(node_id(root["job_id"], "b"))
        decision = self.jobs.retry_runtime.persisted_decision(failed)
        self.assertEqual(decision["decision"], "STOP")
        self.assertEqual(decision["reason_code"], "denied_budget_failure")
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 1)
        self.assert_no_live_claims()

    def test_generic_transition_cannot_requeue_a_live_claim(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        job = self.jobs.claim(job_id=node_id(root["job_id"], "a"))
        with self.assertRaisesRegex(JobError, "explicit unstarted recovery"):
            self.jobs.enqueue(job["job_id"])
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "running")

    def test_late_budget_reservation_cannot_use_a_released_claim(self):
        for reclaim in (False, True):
            with self.subTest(same_worker_reclaims=reclaim):
                root = self.create([self.node("a")])
                self.graph.advance(root["job_id"])
                job = self.jobs.claim(job_id=node_id(root["job_id"], "a"))
                budget = ExecutionBudgetRuntime(self.jobs.budget_store)
                context = budget._graph_parallel_context
                def release(*args):
                    prior = context(*args)
                    self.jobs.recover_unstarted_graph_claims(root["job_id"])
                    if reclaim:
                        renewed = self.jobs.claim(job_id=job["job_id"], claimed_by=job["claimed_by"])
                        self.assertNotEqual(renewed["claimed_at"], job["claimed_at"])
                    return prior
                with patch.object(budget, "_graph_parallel_context", side_effect=release):
                    decision = budget.reserve_execution(job["execution_budget"], execution_id="late-budget",
                                                        job_id=job["job_id"], job_runtime=self.jobs)
                self.assertEqual(decision.status, "DEFER")
                self.assertEqual(self.jobs.show(job["job_id"])["status"], "running" if reclaim else "queued")
                self.assertEqual(budget.state(root["execution_budget"]).state["dimensions"]["execution_units"]["consumed"], 0)

    def test_worker_budget_admission_cannot_use_renewed_same_worker_claim(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        job = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        reserve = worker.budget_runtime.reserve_execution
        def renew(*args, **kwargs):
            self.jobs.recover_unstarted_graph_claims(root["job_id"])
            renewed = self.jobs.claim(job_id=job["job_id"], claimed_by=worker.worker_id)
            self.assertNotEqual(renewed["claimed_at"], job["claimed_at"])
            return reserve(*args, **kwargs)
        with patch.object(worker.budget_runtime, "reserve_execution", side_effect=renew):
            with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
                outcome = worker.run_claimed(job["job_id"])
                self.assertEqual(execute.call_count, 0)
        self.assert_deferred([outcome])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
        self.assertEqual(worker.budget_runtime.state(root["execution_budget"]).state[
            "dimensions"]["execution_units"]["consumed"], 0)
        self.restart()
        self.graph.recover(root["job_id"], self.worker())
        self.assertEqual([o.status for o in self.graph.run_ready(root["job_id"], self.factory)], ["completed"])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 1)

    def test_lease_expiring_after_authority_validation_cannot_reserve_budget(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        job = self.jobs.claim(job_id=node_id(root["job_id"], "a"))
        budget = ExecutionBudgetRuntime(self.jobs.budget_store)
        context = budget._graph_parallel_context
        def expire(*args):
            prior = context(*args)
            self.jobs.clock = lambda: (datetime.now(timezone.utc) + timedelta(seconds=400)).isoformat().replace("+00:00", "Z")
            return prior
        with patch.object(budget, "_graph_parallel_context", side_effect=expire):
            decision = budget.reserve_execution(job["execution_budget"], execution_id="expired-budget",
                                                job_id=job["job_id"], job_runtime=self.jobs)
        self.assertEqual(decision.status, "ERROR")
        self.assertIn("lease has expired", decision.reason)
        state = budget.state(root["execution_budget"])
        self.assertEqual(state.state["dimensions"]["execution_units"]["consumed"], 0)
        self.assertEqual(state.state["active_reservation_ids"], [])
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
        self.assertEqual(len(self.jobs.recover_expired_claims(backoff_seconds=(0,))), 1)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "failed")

    def test_lease_expiring_during_unstarted_proof_remains_with_expired_claim_owner(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        job = self.jobs.claim(job_id=node_id(root["job_id"], "a"))
        proof = self.executions.unstarted
        def expire(*args):
            self.assertTrue(proof(*args))
            self.jobs.clock = lambda: (datetime.now(timezone.utc) + timedelta(seconds=400)).isoformat().replace("+00:00", "Z")
            return True
        with patch.object(self.executions, "unstarted", side_effect=expire):
            self.assertEqual(self.jobs.recover_unstarted_graph_claims(root["job_id"]), [])
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "running")
        self.assertNotIn("claim_released_at", self.jobs.show(job["job_id"]))
        recovered = self.jobs.recover_expired_claims(backoff_seconds=(0,))
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["failed_job"]["error"]["code"], "claim_lease_expired")
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "failed")


if __name__ == "__main__":
    unittest.main()
