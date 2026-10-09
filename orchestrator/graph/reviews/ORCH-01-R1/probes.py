"""Reviewer-created graph transition attacks. No implementation repairs."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from runtime.approvals.runtime import ApprovalRuntime
from runtime.core.jobs import JobRuntime, RuntimeError as JobError
from runtime.executors.local import LocalExecutor
from runtime.graph.models import node_id
from runtime.graph.runtime import GraphRuntime
from runtime.tests.test_graph import GraphHarness

OBSERVATIONS = {}

class IndependentGraphProbes(GraphHarness, unittest.TestCase):
    def restart(self):
        self.jobs = JobRuntime(self.root / "jobs")
        self.jobs.execution_store = self.executions
        self.jobs.retry_runtime.execution_store = self.executions
        self.approvals = ApprovalRuntime(self.jobs, self.approvals.store, execution_store=self.executions)
        self.graph = GraphRuntime(self.jobs, self.approvals)

    def strengthen(self, job_id):
        job = self.jobs.show(job_id)
        value = deepcopy(job)
        value["review_required"] = True
        return self.jobs._save(value)

    def test_strengthened_parent_gate_survives_restart_and_admission(self):
        root = self.create([self.node("a")])
        strengthened = self.strengthen(root["job_id"])
        self.restart()
        self.graph.advance(root["job_id"])
        child = self.jobs.show(node_id(root["job_id"], "a"))
        outcome = self.execute(root, "a")
        OBSERVATIONS["parent_gate"] = {"root_review_required": strengthened["review_required"],
            "root_contract_review": strengthened["task_contract"]["approval_requirements"]["review"],
            "child_review_required": child["review_required"], "outcome": outcome.to_dict(),
            "view": self.graph.show(root["job_id"])}
        self.assertTrue(child["review_required"], "Admission lost the verified effective parent review gate")
        self.assertNotEqual(outcome.status, "completed", "Child completed without independent review")

    def test_strengthened_failed_node_gate_survives_replan(self):
        root = self.create([self.node("a"), self.node("repair"), self.node("join", depends=("a",), kind="merge")],
            edges=[dict(source="a", target="repair", kind="replan")], handoffs=1)
        self.graph.advance(root["job_id"])
        source = self.strengthen(node_id(root["job_id"], "a"))
        failed = self.execute(root, "a", "failure")
        self.restart()
        self.graph.advance(root["job_id"])
        target = self.jobs.show(node_id(root["job_id"], "repair"))
        outcome = self.execute(root, "repair")
        self.graph.run_ready(root["job_id"], self.factory)
        OBSERVATIONS["replan_gate"] = {"source_review_required": source["review_required"],
            "source_failure": failed.to_dict(), "target_review_required": target["review_required"],
            "target_outcome": outcome.to_dict(), "view": self.graph.show(root["job_id"])}
        self.assertTrue(target["review_required"], "Replan replaced a strengthened gate with weaker authority")

    def test_repeated_merge_and_concurrent_delivery_execute_once(self):
        root = self.create([self.node("a"), self.node("join", depends=("a",), kind="merge")])
        self.graph.run_ready(root["job_id"], self.factory)
        with ThreadPoolExecutor(max_workers=2) as pool:
            deliveries = list(pool.map(lambda _: self.graph.run_ready(root["job_id"], self.factory), range(2)))
        self.restart()
        replay = self.graph.run_ready(root["job_id"], self.factory)
        join = self.jobs.show(node_id(root["job_id"], "join"))
        execution_refs = [r["ref"] for r in join["output_refs"] if r["ref"].startswith("runtime-execution:")]
        own = [self.executions.load(p.stem).result.execution_id for p in self.executions.root.glob("*.json")
               if self.executions.load(p.stem).result.job_id == join["job_id"]]
        OBSERVATIONS["repeated_merge"] = {"deliveries": [[r.to_dict() for r in d] for d in deliveries],
            "replay": [r.to_dict() for r in replay], "merge_execution_ids": own, "view": self.graph.show(root["job_id"])}
        self.assertEqual(len(own), 1)
        self.assertEqual(len(execution_refs), 2)  # one input collected by merge plus its own execution
        self.assertEqual(replay, [])

    def test_declared_review_gate_cannot_be_substituted_by_unreviewed_correction(self):
        gate = self.node("gate", kind="gate", profile="critic", review_required=True)
        root = self.create([gate, self.node("repair"), self.node("after", depends=("gate",))],
            edges=[dict(source="gate", target="repair", kind="correction")], handoffs=1)
        self.graph.advance(root["job_id"])
        failed = self.execute(root, "gate", "failure")
        self.graph.advance(root["job_id"])
        target = self.jobs.show(node_id(root["job_id"], "repair"))
        outcome = self.execute(root, "repair")
        self.graph.run_ready(root["job_id"], self.factory)
        OBSERVATIONS["declared_gate_correction"] = {"source_contract_review": True,
            "failure": failed.to_dict(), "target_contract_review": target["task_contract"]["approval_requirements"]["review"],
            "target_review_required": target["review_required"], "target_outcome": outcome.to_dict(),
            "view": self.graph.show(root["job_id"])}
        self.assertTrue(target["review_required"], "Correction bypassed an explicitly contracted graph review gate")

    def test_process_exit_mid_fan_out_resumes_exact_admissions(self):
        root = self.create([self.node("a"), self.node("b"), self.node("join", depends=("a", "b"), kind="fan_in")])
        source = '''
import os, sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.storage.execution_store import FileExecutionStore
from runtime.graph.runtime import GraphRuntime
j = JobRuntime(Path(sys.argv[1]) / "jobs")
e = FileExecutionStore(Path(sys.argv[1]) / "executions")
j.execution_store = e
j.retry_runtime.execution_store = e
a = ApprovalRuntime(j, FileApprovalStore(Path(sys.argv[1]) / "approvals"), execution_store=e)
original = j.store.create
def stop(job):
    result = original(job)
    if "graph_binding" in job: os._exit(73)
    return result
j.store.create = stop
GraphRuntime(j, a).advance(sys.argv[2])
'''
        crash = subprocess.run([sys.executable, "-B", "-c", source, str(self.root), root["job_id"]], cwd=ROOT,
                               capture_output=True, text=True)
        self.assertEqual(crash.returncode, 73, crash.stderr)
        raw_ids = [j["job_id"] for j in self.jobs.store.list()]
        self.restart()
        view = self.graph.advance(root["job_id"])
        self.graph.run_ready(root["job_id"], self.factory)
        self.graph.run_ready(root["job_id"], self.factory)
        OBSERVATIONS["process_exit_fan_out"] = {"exit_code": crash.returncode, "ids_at_crash": raw_ids,
            "resumed": view, "final": self.graph.show(root["job_id"])}
        self.assertEqual(view["busy"], 2)
        self.assertEqual(view["nodes"]["a"]["job_id"], node_id(root["job_id"], "a"))
        self.assertEqual(self.graph.show(root["job_id"])["status"], "completed")
        self.assertEqual(len(self.jobs.list()), 4)

    def test_consumed_dispatch_cannot_be_restored_by_restart(self):
        from runtime.core.capability_governance import certified_dispatch
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        original = worker.executor.execute
        observed = {}
        class SimulatedExit(BaseException):
            pass
        def crash(request):
            observed["request"] = request
            original(request)
            raise SimulatedExit("simulated exit after consumed effect before result persistence")
        with patch.object(worker.executor, "execute", side_effect=crash), self.assertRaises(SimulatedExit):
            worker.run_claimed(claim["job_id"])
        self.restart()
        request = observed["request"]
        error = None
        try:
            with certified_dispatch(self.executions, request):
                original(request)
        except ValueError as exc:
            error = str(exc)
        OBSERVATIONS["consumed_dispatch"] = {"job_id": claim["job_id"], "execution_id": request.execution_id,
            "replay_error": error}
        self.assertIsNotNone(error)
        self.assertIn("consumed", error)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IndependentGraphProbes)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (OUT / "probe-observations.json").write_text(json.dumps(OBSERVATIONS, indent=2) + "\n", encoding="utf-8")
    (OUT / "probe-result.json").write_text(json.dumps({"tests": result.testsRun,
        "failures": [{"test": str(t), "traceback": trace} for t, trace in result.failures],
        "errors": [{"test": str(t), "traceback": trace} for t, trace in result.errors],
        "passed": result.wasSuccessful()}, indent=2) + "\n", encoding="utf-8")
    sys.exit(not result.wasSuccessful())
