"""GOV-02-F1 reproduced and combined authority/trace/restart attacks."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

from runtime.core import capability_governance as gov
from runtime.execution.models import ExecutionResult
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests import test_task_contract, test_actions, test_capability_governance, test_git
from runtime.workers.worker import Worker
from runtime.core.task_contract import encoded


class GovernanceF1Tests(unittest.TestCase):
    def test_imported_execution_readable_but_cannot_complete(self):
        f = test_task_contract.TaskContractTests(); f.setUp()
        try:
            job = f.runtime.create(f.payload()); f.runtime.enqueue(job["job_id"])
            job = f.runtime.claim(claimed_by="attack")
            request = Worker._build_request(job, "imported", ())
            result = ExecutionResult(execution_id=request.execution_id, job_id=request.job_id,
                status="succeeded", output_refs=(), summary="Observation", error=None, provider=None,
                started_at=f.runtime.clock(), completed_at=f.runtime.clock())
            f.executions.create(request, result)
            self.assertEqual(f.executions.load(request.execution_id).result.status, "succeeded")
            with self.assertRaises(ValueError):
                f.runtime.record_execution_success(job["job_id"], [{"ref_type":"artifact", "ref":"runtime-execution:imported"}])
            self.assertNotEqual(f.runtime.show(job["job_id"])["status"], "completed")
        finally: f.tearDown()

    def test_final_apply_rechecks_deleted_replaced_tampered_noncanonical_pairs(self):
        for stage in ("effect-controlled_write", "dispatch-execute", "both"):
            for attack in ("delete", "replace", "tamper", "noncanonical"):
                with self.subTest(stage=stage, attack=attack):
                    f = test_actions.ControlledWriteTests(); f.setUp()
                    try:
                        request = f.request(); store, _, _ = gov._DISPATCH.get()
                        def mutate(workspace):
                            (workspace / "src" / "existing.txt").write_text("attack")
                            for target_stage in (("effect-controlled_write", "dispatch-execute") if stage == "both" else (stage,)):
                                for suffix in ("anchor", "witness"):
                                    path = store._decision_path(request.execution_id, target_stage, suffix)
                                    if attack == "delete": path.unlink()
                                    elif attack == "replace": path.write_bytes(encoded({"schema_version":1}))
                                    elif attack == "tamper":
                                        data = json.loads(path.read_bytes()); data["schema_version"] = 2
                                        path.write_bytes(encoded(data))
                                    else: path.write_text(json.dumps(json.loads(path.read_bytes()), indent=2))
                        with self.assertRaises(ValueError): f.execute_controlled(test_actions.MutatingAdapter(mutate), request)
                        self.assertEqual((f.target / "src" / "existing.txt").read_text(), "before\n")
                    finally: f.tearDown()

    def test_effect_deleted_after_outer_check_is_denied_inside_apply(self):
        from unittest.mock import patch
        f = test_actions.ControlledWriteTests(); f.setUp()
        try:
            request = f.request(); store, _, _ = gov._DISPATCH.get()
            original = f.runtime._apply
            def attack(*args, **kwargs):
                for suffix in ("anchor", "witness"):
                    store._decision_path(request.execution_id, "effect-controlled_write", suffix).unlink()
                return original(*args, **kwargs)
            with patch.object(f.runtime, "_apply", side_effect=attack):
                with self.assertRaises(ValueError):
                    f.execute_controlled(test_actions.MutatingAdapter(
                        lambda workspace: (workspace / "src" / "existing.txt").write_text("attack")), request)
            self.assertEqual((f.target / "src" / "existing.txt").read_text(), "before\n")
        finally: f.tearDown()

    def test_rollback_new_identity_store_and_restart_never_refund(self):
        for alternate in (False, True):
            for partial in ("intact", "one_missing", "both_missing", "identity_tampered", "foreign_identity_tampered"):
                with self.subTest(alternate=alternate, partial=partial):
                    f = test_capability_governance.CapabilityGovernanceTests(); f.setUp()
                    try:
                        job, request = f.prepared()
                        journal = f.runtime.progress.store.path(f.runtime.progress.logical_id(job)); prior = journal.read_bytes()
                        f.begin(job, request)
                        with gov.certified_dispatch(f.store, request): f.fixture.worker.executor.execute(request)
                        if partial in ("one_missing", "both_missing"):
                            f.store._decision_path(request.execution_id, "intent", "witness").unlink()
                            if partial == "both_missing": f.store._decision_path(request.execution_id, "intent", "anchor").unlink()
                        if partial in ("identity_tampered", "foreign_identity_tampered"):
                            prior_intent = f.store._decision_pair(request.execution_id, "intent")
                            prior_intent["request"]["attempt"] += 1
                            if partial == "foreign_identity_tampered":
                                prior_intent["request"]["job_id"] = "foreign-job"
                                prior_intent["authority_source"]["job_id"] = "foreign-job"
                            for suffix in ("anchor", "witness"):
                                f.store._decision_path(request.execution_id, "intent", suffix).write_bytes(encoded(prior_intent))
                        journal.write_bytes(prior)
                        data = request.to_dict(); data["execution_id"] = "replacement"
                        request_path = f.root / "replacement.json"; request_path.write_text(json.dumps(data))
                        owner = f.root / ("alternate-executions" if alternate else "executions")
                        code = """import json,sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.storage.execution_store import FileExecutionStore
from runtime.execution.models import ExecutionRequest
root=Path(sys.argv[1]);runtime=JobRuntime(root/'jobs',clock=lambda:'2026-10-02T12:00:00Z')
request=ExecutionRequest.from_persisted_dict(json.loads(Path(sys.argv[2]).read_text()))
try:
 FileExecutionStore(Path(sys.argv[3])).begin_decision(request,executor='restart',runtime=runtime,job=runtime.show(request.job_id))
except ValueError:
 sys.exit(0)
sys.exit(3)
"""
                        child = subprocess.run([sys.executable, "-B", "-c", code, str(f.root), str(request_path), str(owner)], capture_output=True, text=True)
                        self.assertEqual(child.returncode, 0, child.stderr)
                        self.assertFalse(FileExecutionStore(owner)._decision_path("replacement", "intent", "anchor").exists())
                    finally: f.tearDown()

    def test_imported_review_and_execution_cannot_feed_separately_approved_git(self):
        for stage in ("execution", "review", "both"):
            with self.subTest(stage=stage):
                f = test_git.GitRuntimeTests(); f.setUp()
                try:
                    prepared = f.prepare(); identity = f.approve(prepared)
                    job = f.jobs.show(f.job_id)
                    if stage in ("execution", "both"):
                        trace = f.executions._decision_pair(f.execution_id, "result"); trace["intent_digest"] = None
                        for suffix in ("anchor", "witness"):
                            f.executions._decision_path(f.execution_id, "result", suffix).write_bytes(encoded(trace))
                        f.executions.load(f.execution_id)  # Observations remain readable.
                    if stage in ("review", "both"):
                        review_id = next(r["ref"].split(":",1)[1] for r in job["output_refs"] if r["ref"].startswith("runtime-review:"))
                        store = f.reviews._decisions(); trace = store._decision_pair(review_id, "review-result"); trace["intent_digest"] = None
                        for suffix in ("anchor", "witness"): store._decision_path(review_id, "review-result", suffix).write_bytes(encoded(trace))
                        f.reviews.load(review_id)
                    with self.assertRaises(ValueError): f.runtime.commit(identity)
                    self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
                finally: f.tearDown()

    def test_removed_unrelated_job_does_not_veto_new_authorized_work(self):
        f = test_task_contract.TaskContractTests(); f.setUp()
        try:
            job, outcome = f.run_job()
            self.assertEqual(outcome.status, "completed")
            f.runtime.store._path(job["job_id"]).unlink()
            next_job, next_outcome = f.run_job()
            self.assertNotEqual(next_job["job_id"], job["job_id"])
            self.assertEqual(next_outcome.status, "completed")
        finally: f.tearDown()

    def test_accepted_controlled_result_requires_effect_after_restart(self):
        f = test_git.GitRuntimeTests(); f.setUp()
        try:
            for suffix in ("anchor", "witness"):
                f.executions._decision_path(f.execution_id, "effect-controlled_write", suffix).unlink()
            with self.assertRaises(ValueError): FileExecutionStore(f.executions.root).load(f.execution_id, require_authority=True)
        finally: f.tearDown()
