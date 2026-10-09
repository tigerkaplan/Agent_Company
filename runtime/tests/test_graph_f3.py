"""R3-M1 accounting integrity gates; persisted results never authorize replay."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from runtime.budget.models import BudgetBinding
from runtime.tests.test_graph import GraphHarness
from runtime.tests.test_graph_f2 import r2
from runtime.graph.models import node_id


class GraphF3Tests(GraphHarness, unittest.TestCase):
    restart = r2.CombinedProbes.restart

    def pending(self, *, ordinary=False, budget=100, mode="success"):
        if ordinary:
            root = self.jobs.create(self.payload(task="First", execution_budget={"max_execution_units": budget},
                continuation_plan={"plan_id": "f3-plan", "steps": [
                    {"step_id": "STEP-001", "task": "First"},
                    {"step_id": "STEP-002", "task": "Second"}]}))
            self.jobs.enqueue(root["job_id"])
            worker = self.worker(mode)
            claim = self.jobs.claim(job_id=root["job_id"], claimed_by=worker.worker_id)
        else:
            root = self.create([self.node("a"), self.node("join", depends=("a",), kind="merge")], budget=budget)
            self.graph.advance(root["job_id"])
            worker = self.worker(mode)
            claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        binding = BudgetBinding.from_dict(root["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        finalize = worker.budget_runtime.finalize_execution
        saved = []
        def corrupt(*args, **kwargs):
            saved.append(path.read_bytes())
            path.write_bytes(b"{}")
            return finalize(*args, **kwargs)
        with patch.object(worker.budget_runtime, "finalize_execution", side_effect=corrupt):
            outcome = worker.run_claimed(claim["job_id"])
        self.assertEqual(outcome.status, "execution_reserved", outcome.to_dict())
        self.assertEqual(outcome.error["code"], "execution_budget_error")
        self.assertEqual(outcome.budget["status"], "ERROR")
        self.assertFalse(outcome.budget["state"]["may_begin"])
        self.assertNotIn("task_completion", self.jobs.show(outcome.job_id))
        self.assertEqual(self.jobs.show(outcome.job_id)["status"], "running")
        result_path = self.executions.root / (outcome.execution_id + ".json")
        return root, outcome, path, saved[0], result_path.read_bytes()

    def assert_held(self, outcome, original):
        job = self.jobs.show(outcome.job_id)
        self.assertEqual(job["status"], "running")
        self.assertNotIn("task_completion", job)
        self.assertNotIn("claim_released_at", job)
        self.assertEqual((self.executions.root / (outcome.execution_id + ".json")).read_bytes(), original)
        self.assertIsNone(self.jobs.retry_runtime.persisted_decision(job))
        self.assertIsNone(self.jobs.progress.store.recovery_record(self.jobs.progress.logical_id(job), job["job_id"]))

    def test_live_error_and_repeated_restart_hold_result_then_canonical_recovery_admits_fan_in(self):
        root, outcome, path, valid, original = self.pending()
        for _ in range(2):
            self.restart()
            worker = self.worker()
            with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
                held = worker.recover_persisted_results()
                self.assertEqual([o.execution_id for o in held], [outcome.execution_id])
                self.assertEqual(held[0].budget["status"], "ERROR")
                self.graph.recover(root["job_id"], worker)
                self.assertEqual(execute.call_count, 0)
            self.assert_held(outcome, original)
            self.assertFalse(self.jobs.store.exists(node_id(root["job_id"], "join")))
        # Restore exact previously authoritative bytes in the isolated fixture;
        # the production budget owner still validates protected usage and recovers.
        path.write_bytes(valid)
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            self.graph.recover(root["job_id"], worker)
            self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual(self.jobs.show(outcome.job_id)["status"], "completed")
        self.assertIn("task_completion", self.jobs.show(outcome.job_id))
        self.assertEqual(self.jobs.show(node_id(root["job_id"], "join"))["status"], "queued")
        self.assertEqual(worker.budget_runtime.state(root["execution_budget"]).state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertEqual((self.executions.root / (outcome.execution_id + ".json")).read_bytes(), original)

    def test_ordinary_error_blocks_continuation_then_recovers_same_result(self):
        root, outcome, path, valid, original = self.pending(ordinary=True)
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            for _ in range(2):
                worker.run_once()
                self.assertEqual(len(self.jobs.list()), 1)
                self.assert_held(outcome, original)
            self.assertEqual(execute.call_count, 0)
        path.write_bytes(valid)
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            worker.recover_budget_state()
            recovered = worker.recover_persisted_results()
            worker.continuation_runtime.recover()
            self.assertEqual(execute.call_count, 0)
        self.assertEqual([o.execution_id for o in recovered], [outcome.execution_id])
        self.assertEqual(self.jobs.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(self.jobs.list()), 2)
        self.assertEqual((self.executions.root / (outcome.execution_id + ".json")).read_bytes(), original)

    def test_error_discovered_after_budget_recovery_blocks_all_downstream_recovery(self):
        root, outcome, path, valid, original = self.pending()
        path.write_bytes(valid)
        self.restart()
        worker = self.worker()
        finalize = worker.budget_runtime.finalize_execution
        def corrupt(*args, **kwargs):
            path.write_bytes(b"{}")
            return finalize(*args, **kwargs)
        with patch.object(worker.budget_runtime, "finalize_execution", side_effect=corrupt), \
                patch.object(self.jobs, "recover_unstarted_graph_claims", wraps=self.jobs.recover_unstarted_graph_claims) as claims, \
                patch.object(worker.continuation_runtime, "recover", wraps=worker.continuation_runtime.recover) as continuation, \
                patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            self.graph.recover(root["job_id"], worker)
            self.assertEqual((claims.call_count, continuation.call_count, execute.call_count), (0, 0, 0))
        self.assert_held(outcome, original)
        self.assertFalse(self.jobs.store.exists(node_id(root["job_id"], "join")))

    def test_missing_reservation_remains_error_without_reconstruction_or_executor_entry(self):
        root, outcome, path, valid, original = self.pending()
        # Create an intact canonical state for this binding with its reservation
        # removed. Protected usage detects the attack; no production repair writes.
        import json
        state = json.loads(valid)
        state["reservations"] = []
        path.write_text(json.dumps(state), encoding="utf-8")
        damaged = path.read_bytes()
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            worker.recover_persisted_results()
            self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assert_held(outcome, original)
        self.assertEqual(path.read_bytes(), damaged)

    def test_clock_rollback_error_stays_fail_closed_after_wall_clock_catches_up(self):
        root, outcome, path, valid, original = self.pending()
        path.write_bytes(valid)
        self.restart()
        worker = self.worker()
        worker.budget_runtime.wall_clock = lambda: (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assert_held(outcome, original)
        self.restart()
        worker = self.worker()
        self.assertEqual(worker.budget_runtime.state(root["execution_budget"]).status, "ERROR")
        self.graph.recover(root["job_id"], worker)
        self.assert_held(outcome, original)

    def test_trusted_exhaustion_after_accounting_retains_terminal_stop(self):
        root, outcome, path, valid, original = self.pending(budget=1)
        path.write_bytes(valid)
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual(self.jobs.show(outcome.job_id)["status"], "completed")
        join_node = next(n for n in root["graph_plan"]["nodes"] if n["node_id"] == "join")
        denied_worker = self.factory(join_node, self.jobs.show(node_id(root["job_id"], "join")))
        with patch.object(denied_worker.executor, "execute", wraps=denied_worker.executor.execute) as execute:
            denied = self.graph.run_ready(root["job_id"], lambda n, j: denied_worker)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual([o.error["code"] for o in denied], ["execution_budget_exhausted"])
        self.graph.advance(root["job_id"])
        join = self.jobs.show(node_id(root["job_id"], "join"))
        self.assertEqual(self.jobs.retry_runtime.persisted_decision(join)["decision"], "STOP")
        self.assertEqual(self.graph.show(root["job_id"])["status"], "failed")
        state = worker.budget_runtime.state(root["execution_budget"])
        self.assertEqual(state.state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertFalse(state.state["may_begin"])
        self.assertEqual((self.executions.root / (outcome.execution_id + ".json")).read_bytes(), original)

    def test_failed_result_with_unresolved_error_does_not_admit_retry(self):
        root, outcome, path, valid, original = self.pending(mode="failure")
        self.assertEqual(outcome.result["status"], "failed")
        self.restart()
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            worker.recover_persisted_results()
            self.graph.recover(root["job_id"], worker)
            self.assertEqual(execute.call_count, 0)
        self.assert_held(outcome, original)
        self.assertEqual(len(self.jobs.list()), 2)
