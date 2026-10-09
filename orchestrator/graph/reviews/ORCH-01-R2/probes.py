"""Independent R2 reproductions and combined persisted-state attacks.

All runtime mutations are isolated test fixtures. Only observational evidence is
written to the checkout; original R1 recipes are imported without their writers.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from runtime.approvals.runtime import ApprovalRuntime
from runtime.core.jobs import JobRuntime, ClaimContention, RuntimeError as JobError
from runtime.core.task_contract import TaskContractError
from runtime.executors.local import LocalExecutor
from runtime.graph.models import GraphError, node_id
from runtime.graph.planner import GraphPlanner
from runtime.graph.runtime import GraphRuntime
from runtime.review.store import FileReviewStore
from runtime.tests.test_graph import GraphHarness
from runtime.tests.test_graph_integration import GraphIntegrationTests

spec = importlib.util.spec_from_file_location("r1_exact_recipes", OUT.parent / "ORCH-01-R1/probes.py")
r1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r1)
OBSERVATIONS = {}


def save_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class Evidence:
    def observe(self, **data):
        OBSERVATIONS.setdefault(self._testMethodName, {}).update(data)

    def capture_state(self, stage=None, *, held_lock=None):
        # Flat content-addressed copies avoid Windows MAX_PATH. Original path
        # identity remains in manifests; copied bytes grant no execution rights.
        blobs = OUT / "raw-state"
        blobs.mkdir(exist_ok=True)
        files, unreadable_locks = {}, {}
        if held_lock is not None:
            held_lock = Path(held_lock).resolve()
            self.assertIn(held_lock, {self.jobs.store.root.resolve() / ".claim.lock",
                                      self.jobs.budget_store.root.resolve() / ".budget.lock"})
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                relative = path.relative_to(self.root).as_posix()
                try:
                    raw = path.read_bytes()
                except PermissionError as error:
                    if held_lock is None or path.resolve() != held_lock:
                        raise
                    unreadable_locks[relative] = {"reason": "Held OS coordination byte-range lock",
                                                  "errno": error.errno}
                    continue
                sha = hashlib.sha256(raw).hexdigest()
                target = blobs / sha
                if not target.exists():
                    target.write_bytes(raw)
                files[relative] = {"sha256": sha, "bytes": len(raw)}
        name = self._testMethodName + ("-" + stage if stage else "") + "-state.json"
        save_json(name, {"original_root": str(self.root), "files": files,
                        "temporarily_unreadable_coordination_locks": unreadable_locks})

    def tearDown(self):
        self.capture_state()
        self.observe(raw_jobs=self.jobs.store.list(),
                     execution_ids=sorted(p.stem for p in self.executions.root.glob("*.json")))
        save_json("probe-observations.json", {**OBSERVATIONS, "r1_exact": r1.OBSERVATIONS})


class ExactR1(Evidence, r1.IndependentGraphProbes):
    pass


class CombinedProbes(Evidence, GraphHarness, unittest.TestCase):
    def assert_no_live_claims(self):
        # Canonical owners retain original Worker/lease provenance after release.
        # Check the active-claim boundary rather than deleting that history.
        for job in self.jobs.store.list():
            self.assertNotEqual(job["status"], "running")
            if job.get("claimed_by"):
                self.assertTrue(job.get("claim_released_at"), job["job_id"])
                with self.assertRaisesRegex(JobError, "not held by the expected active claim"):
                    self.jobs.validate_claim(job["job_id"], job["claimed_by"])

    def restart(self, review_store=None):
        self.jobs = JobRuntime(self.root / "jobs")
        self.jobs.execution_store = self.executions
        self.jobs.retry_runtime.execution_store = self.executions
        self.approvals = ApprovalRuntime(self.jobs, self.approvals.store, execution_store=self.executions,
            review_store=review_store or (FileReviewStore(self.root / "reviews") if (self.root / "reviews").exists() else None))
        self.graph = GraphRuntime(self.jobs, self.approvals)

    def approve_pending(self, job_id):
        pending = [a for a in self.approvals.store.list("PENDING") if a.job_id == job_id]
        self.assertEqual(len(pending), 1)
        self.approvals.resolve(pending[0].approval_id, decision="APPROVED", decided_by="r2-fixture-owner")
        return pending[0].approval_id

    def test_public_stronger_parent_review_and_pending_approval_restart_duplicate(self):
        payload = self.payload(execution_budget={"max_execution_units": 20})
        payload.update(review_required=True, approval_status="required")
        payload["task_contract"]["allowed_capabilities"].append("independent_review")
        root = self.graph.create(payload, GraphPlanner.build([self.node("a"), self.node("b")], max_parallel=2))
        self.graph.advance(root["job_id"])
        self.restart()
        with ThreadPoolExecutor(max_workers=3) as pool:
            views = list(pool.map(lambda _: self.graph.advance(root["job_id"]), range(3)))
        self.assertTrue(all(v["status"] == "waiting_approval" for v in views))
        self.assertEqual(len(self.jobs.store.list()), 1)
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
        parent_receipt = self.approve_pending(root["job_id"])
        self.restart()
        self.graph.advance(root["job_id"])
        for name in ("a", "b"):
            child = self.jobs.show(node_id(root["job_id"], name))
            self.assertEqual(child["task_contract"]["approval_requirements"],
                             {"execution": True, "review": True, "completion": False})
            self.assertIsNone(self.jobs.claim(job_id=child["job_id"]))
            self.assertNotEqual(self.approve_pending(child["job_id"]), parent_receipt)
        self.restart()
        reviewer = GraphIntegrationTests.review_runtime(self, "PASS")
        outcomes = self.graph.run_ready(root["job_id"], lambda n, j: self.worker(reviewer=reviewer))
        self.assertEqual([o.status for o in outcomes], ["completed", "completed"])
        self.assertTrue(all(self.jobs.show(o.job_id)["task_completion"]["review_digest"] for o in outcomes))
        self.restart()
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.observe(views=views, outcomes=[o.to_dict() for o in outcomes], parent_receipt=parent_receipt)

    def test_two_recovery_hops_preserve_source_gates_and_pending_completion(self):
        source = self.node("source", review_required=True)
        source["payload"]["task_contract"]["approval_requirements"].update(execution=True, completion=True)
        root = self.create([source, self.node("correction"), self.node("replan"),
                            self.node("join", depends=("source",), kind="merge")],
            edges=[dict(source="source", target="correction", kind="correction"),
                   dict(source="correction", target="replan", kind="replan")], handoffs=2)
        receipts = []
        for name in ("source", "correction"):
            self.graph.advance(root["job_id"])
            child_id = node_id(root["job_id"], name)
            receipts.append(self.approve_pending(child_id))
            self.assertEqual(self.execute(root, name, "failure").status, "failed")
            self.restart()
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: self.graph.advance(root["job_id"]), range(3)))
        target_id = node_id(root["job_id"], "replan")
        target = self.jobs.show(target_id)
        self.assertEqual(target["task_contract"]["approval_requirements"],
                         {"execution": True, "review": True, "completion": True})
        self.assertEqual(target["graph_binding"]["recovery_source_job_id"], node_id(root["job_id"], "correction"))
        self.assertIsNone(self.jobs.claim(job_id=target_id))
        receipts.append(self.approve_pending(target_id))
        outcome = self.execute(root, "replan", reviewer=GraphIntegrationTests.review_runtime(self, "PASS"))
        self.assertEqual(outcome.status, "waiting_approval")
        self.restart()
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "waiting_approval")
        self.assertIsNone(view["nodes"]["join"]["job_id"])
        self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
        receipts.append(self.approve_pending(target_id))
        self.restart()
        outcomes = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual([o.status for o in outcomes], ["completed"])
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(set(receipts)), 4)
        self.assertEqual(len(self.jobs.store.list()), 5)
        self.observe(receipts=receipts, pending_view=view, recovery_outcome=outcome.to_dict())

    def test_recovery_source_tool_ceiling_blocks_real_admission_after_restart(self):
        source = self.node("source")
        source["payload"]["task_contract"]["allowed_tools"] = ["local_executor"]
        target = self.node("repair")
        # Both templates are legal under the wider root, but the repair cannot
        # borrow tools removed from the exact failed source allocation.
        self.assertIn("provider_call", target["payload"]["task_contract"]["allowed_tools"])
        root = self.create([source, target], edges=[dict(source="source", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "source", "failure").status, "failed")
        self.restart()
        with self.assertRaises((GraphError, JobError, TaskContractError)) as caught:
            self.graph.advance(root["job_id"])
        self.assertFalse(self.jobs.store.exists(node_id(root["job_id"], "repair")))
        self.observe(denial=str(caught.exception))

    def test_missing_source_approval_receipt_cannot_authorize_replan_after_restart(self):
        source = self.node("source")
        source["payload"]["task_contract"]["approval_requirements"]["execution"] = True
        root = self.create([source, self.node("repair")],
            edges=[dict(source="source", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        source_id = node_id(root["job_id"], "source")
        receipt = self.approve_pending(source_id)
        self.assertEqual(self.execute(root, "source", "failure").status, "failed")
        receipt_path = self.approvals.store._path(receipt)
        raw = receipt_path.read_bytes()
        receipt_path.unlink()
        self.restart()
        error = None
        try:
            self.graph.advance(root["job_id"])
        except ValueError as caught:
            error = {"type": type(caught).__name__, "message": str(caught)}
        self.assertIsNotNone(error)
        self.assertFalse(self.jobs.store.exists(node_id(root["job_id"], "repair")))
        self.capture_state("missing-source-receipt")
        receipt_path.write_bytes(raw)
        self.restart()
        self.graph.advance(root["job_id"])
        replacement_id = node_id(root["job_id"], "repair")
        self.assertIsNone(self.jobs.claim(job_id=replacement_id))
        replacement_receipt = self.approve_pending(replacement_id)
        self.assertNotEqual(replacement_receipt, receipt)
        self.assertEqual(self.execute(root, "repair").status, "completed")
        self.observe(missing_receipt_denial=error, source_receipt=receipt,
                     replacement_receipt=replacement_receipt)

    def test_configured_custom_review_owner_survives_fan_in_dispatch_restart(self):
        gate = self.node("gate", kind="gate", profile="critic", review_required=True)
        root = self.create([gate, self.node("after", depends=("gate",))])
        self.graph.advance(root["job_id"])
        reviewer = GraphIntegrationTests.review_runtime(self, "PASS")
        custom = self.root / "custom-reviews"
        reviewer.store = FileReviewStore(custom)
        outcome = self.execute(root, "gate", reviewer=reviewer)
        self.assertEqual(outcome.status, "completed", outcome.to_dict())
        accepted = self.jobs.show(outcome.job_id)
        self.assertIsNotNone(accepted["task_completion"]["review_digest"])
        self.restart(review_store=FileReviewStore(custom))
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["nodes"]["after"]["status"], "queued")
        results = self.graph.run_ready(root["job_id"], self.factory)
        self.observe(gate=accepted, configured_review_root=str(custom), admitted=view,
                     outcomes=[o.to_dict() for o in results])
        self.assertEqual([o.status for o in results], ["completed"], [o.to_dict() for o in results])
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")

    @contextmanager
    def process_lock(self, store_root, *, owner="claim"):
        imports = {
            "claim": ("runtime.storage.file_store", "FileJobStore", "claim_transaction"),
            "budget": ("runtime.budget.store", "FileExecutionBudgetStore", "transaction"),
        }
        module, name, method = imports[owner]
        code = f"""import sys
from pathlib import Path
from {module} import {name}
with {name}(Path(sys.argv[1])).{method}():
    print('HELD', flush=True)
    sys.stdin.readline()
"""
        child = subprocess.Popen([sys.executable, "-B", "-c", code, str(store_root)], cwd=ROOT,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "HELD")
            yield
        finally:
            child.communicate("release\n", timeout=10)
            self.assertEqual(child.returncode, 0)

    def test_real_process_claim_contention_then_competing_restart_dispatch(self):
        root = self.create([self.node("a"), self.node("b"), self.node("join", depends=("a", "b"), kind="merge")])
        self.graph.advance(root["job_id"])
        original = self.jobs.store.claim_transaction
        with self.process_lock(self.jobs.store.root), patch.object(self.jobs.store, "claim_transaction",
                 side_effect=lambda **kw: original(timeout_seconds=0.04)):
            self.assertEqual(self.graph.run_ready(root["job_id"], self.factory), [])
            self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
            self.assertTrue(all(j["status"] == "queued" and j.get("claimed_by") is None
                                for j in self.jobs.store.list() if "graph_binding" in j))
        self.restart()
        with ThreadPoolExecutor(max_workers=2) as pool:
            batches = list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2)))
        self.assertEqual(sum(len(b) for b in batches), 2)
        self.restart()
        self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 3)
        self.assertEqual(len(self.jobs.store.list()), 4)
        self.assert_no_live_claims()
        self.observe(batches=[[o.to_dict() for o in b] for b in batches])

    def test_failed_source_replan_restart_claim_contention_defers_cleanly(self):
        root = self.create([self.node("source"), self.node("repair")],
            edges=[dict(source="source", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        self.assertEqual(self.execute(root, "source", "failure").status, "failed")
        self.restart()
        # This valid failed node still needs its canonical retry/replan decision.
        self.assertIsNone(self.jobs.retry_runtime.persisted_decision(
            self.jobs.show(node_id(root["job_id"], "source"))))
        self.capture_state("before-contention")
        error = None
        outcomes = None
        with self.process_lock(self.jobs.store.root):
            try:
                outcomes = self.graph.run_ready(root["job_id"], self.factory)
            except Exception as caught:
                error = {"type": type(caught).__name__, "message": str(caught),
                         "cause": type(caught.__cause__).__name__ if caught.__cause__ else None,
                         "traceback": traceback.format_exc()}
            self.assertFalse(self.jobs.store.exists(node_id(root["job_id"], "repair")))
            self.capture_state("during-contention", held_lock=self.jobs.store.root / ".claim.lock")
        self.observe(contended_exception=error, contended_outcomes=outcomes)
        self.restart()
        resumed = self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual([o.status for o in resumed], ["completed"])
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(self.jobs.store.list()), 3)
        self.observe(resumed=[o.to_dict() for o in resumed])
        self.assertIsNone(error, "Valid replan coordination leaked a canonical claim timeout")
        self.assertEqual(outcomes, [])

    def test_production_budget_lock_contention_does_not_permanently_fail_valid_batch(self):
        # This removes host-scheduling dependence from the stock sixteen-way
        # budget timeout observation. The live budget has ample capacity, and a
        # separate process holds its real canonical transaction until return.
        root = self.create([self.node("a"), self.node("b")], budget=100)
        self.graph.advance(root["job_id"])
        self.restart()
        workers = []
        def factory(node, job):
            worker = self.worker()
            workers.append(worker)
            return worker
        with self.process_lock(self.jobs.budget_store.root, owner="budget"):
            outcomes = self.graph.run_ready(root["job_id"], factory)
            self.assertTrue(all(w.executor.last_request is None for w in workers))
            self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
            self.observe(contended_outcomes=[o.to_dict() for o in outcomes])
            self.capture_state("during-budget-contention", held_lock=self.jobs.budget_store.root / ".budget.lock")
        self.restart()
        recovered = self.graph.recover(root["job_id"], self.worker())
        resumed = self.graph.run_ready(root["job_id"], self.factory)
        final = self.graph.show(root["job_id"])
        self.observe(recovered=recovered, resumed=[o.to_dict() for o in resumed], final=final)
        self.assertEqual(final["status"], "completed",
                         "Transient production budget lock contention became permanent graph failure")
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 2)

    def test_result_contention_pending_completion_restart_recovers_without_executor(self):
        source = self.node("a", review_required=True)
        source["payload"]["task_contract"]["approval_requirements"]["completion"] = True
        root = self.create([source, self.node("join", depends=("a",), kind="merge")])
        worker = self.worker(reviewer=GraphIntegrationTests.review_runtime(self, "PASS"))
        with patch.object(self.jobs, "record_execution_success", side_effect=ClaimContention("r2 bounded contention")):
            outcome = self.graph.run_ready(root["job_id"], lambda n, j: worker)[0]
        self.assertEqual(outcome.status, "execution_reserved")
        self.assertEqual(outcome.error["code"], "claim_contention")
        self.assertNotIn("task_completion", self.jobs.show(outcome.job_id))
        self.restart()
        recovering = self.worker(reviewer=GraphIntegrationTests.review_runtime(self, "PASS"))
        with patch.object(recovering.executor, "execute", wraps=recovering.executor.execute) as execute:
            view = self.graph.recover(root["job_id"], recovering)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual(view["status"], "waiting_approval")
        self.assertIsNone(view["nodes"]["join"]["job_id"])
        self.capture_state("pending-completion")
        self.approve_pending(outcome.job_id)
        self.restart()
        self.graph.run_ready(root["job_id"], self.factory)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 2)
        self.assertTrue(self.executions.exists(outcome.execution_id))
        self.observe(deferred=outcome.to_dict(), pending_view=view)

    def test_expired_preclaimed_batch_has_no_executor_entry(self):
        root = self.create([self.node("a"), self.node("b")])
        original = self.jobs.claim
        workers = []
        def factory(n, j):
            worker = self.worker()
            worker.lease_seconds = 5
            workers.append(worker)
            return worker
        count = 0
        def expire(**kwargs):
            nonlocal count
            claim = original(**kwargs)
            count += 1
            if count == 2:
                self.jobs.clock = lambda: (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
            return claim
        with patch.object(self.jobs, "claim", side_effect=expire):
            outcomes = self.graph.run_ready(root["job_id"], factory)
        self.assertEqual(len(outcomes), 2)
        self.assertTrue(all(w.executor.last_request is None for w in workers))
        self.assertEqual(len(list(self.executions.root.glob("*.json"))), 0)
        view = self.graph.recover(root["job_id"], self.worker())
        self.assertEqual(view["status"], "failed")
        self.observe(outcomes=[o.to_dict() for o in outcomes], recovered=view)
        self.assert_no_live_claims()

    def test_sixteen_barrier_after_restart_and_replay_unique_persisted_ids(self):
        root = self.create([self.node("branch-%02d" % i) for i in range(16)], parallel=16)
        self.graph.advance(root["job_id"])
        self.restart()
        barrier = threading.Barrier(16)
        lock = threading.Lock()
        arrivals = []
        class Executor(LocalExecutor):
            def execute(executor, request):
                with lock:
                    arrivals.append({"job_id": request.job_id, "execution_id": request.execution_id,
                                     "at": time.monotonic()})
                barrier.wait(timeout=45)
                return super(Executor, executor).execute(request)
        outcomes = self.graph.run_ready(root["job_id"], lambda n, j: self.worker(executor=Executor()))
        self.observe(arrivals=arrivals, outcomes=[o.to_dict() for o in outcomes], barrier_broken=barrier.broken)
        self.assertFalse(barrier.broken)
        self.assertEqual(len({a["job_id"] for a in arrivals}), 16)
        identities = {o.execution_id for o in outcomes}
        self.assertEqual(len(identities), 16)
        self.assertTrue(all(o.status in {"completed", "execution_reserved"} for o in outcomes))
        self.assertTrue(all(o.result and o.result["status"] == "succeeded" for o in outcomes))
        self.restart()
        recovery = self.worker()
        with patch.object(recovery.executor, "execute", wraps=recovery.executor.execute) as execute:
            view = self.graph.recover(root["job_id"], recovery)
            self.assertEqual(execute.call_count, 0)
        self.assertEqual(view["status"], "completed")
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2))), [[], []])
        self.assertEqual({p.stem for p in self.executions.root.glob("*.json")}, identities)
        self.assertEqual(len(self.jobs.store.list()), 17)
        self.assert_no_live_claims()


def main():
    diagnostic = len(sys.argv) > 1
    name = ("custom-review-owner-diagnostic" if diagnostic and "custom_review_owner" in sys.argv[1]
            else "budget-contention-diagnostic" if diagnostic and "production_budget_lock" in sys.argv[1]
            else "retry-contention-diagnostic" if diagnostic else "probes")
    suite = (unittest.TestSuite([CombinedProbes(sys.argv[1])]) if diagnostic else
             unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ExactR1),
                                 unittest.defaultTestLoader.loadTestsFromTestCase(CombinedProbes)]))
    with (OUT / (name + ".log")).open("w", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    save_json(name + "-result.json" if diagnostic else "probe-result.json", {"tests": result.testsRun, "passed": result.wasSuccessful(),
        "failures": [{"test": str(t), "traceback": trace} for t, trace in result.failures],
        "errors": [{"test": str(t), "traceback": trace} for t, trace in result.errors],
        "log_sha256": hashlib.sha256((OUT / (name + ".log")).read_bytes()).hexdigest()})
    print(json.dumps({"tests": result.testsRun, "passed": result.wasSuccessful(),
                      "failures": len(result.failures), "errors": len(result.errors)}), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
