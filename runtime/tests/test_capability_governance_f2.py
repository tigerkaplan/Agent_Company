"""Exact GOV-02-R3 majors and bounded combined rollback/tamper regressions."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from runtime.core import capability_governance as gov
from runtime.core.capability_actions import ActionDecision
from runtime.core.task_contract import digest, encoded
from runtime.progress.store import ProgressStore
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests import test_actions as ac, test_capability_governance as cg
from runtime.tests import test_git as gt, test_remote_git as rg

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def fixture(kind):
    case = kind(); case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


def replace_pair(store, identity, stage, value):
    for suffix in ("anchor", "witness"):
        store._decision_path(identity, stage, suffix).write_bytes(encoded(value, max_bytes=512 * 1024))


def delete_pair(store, identity, stage):
    for suffix in ("anchor", "witness"):
        store._decision_path(identity, stage, suffix).unlink()


def journal_for(value):
    source = value["authority_source"]
    return ProgressStore(Path(source["progress_store_root"])).path(source["logical_job_id"])


CHILD = """import json,sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.execution.models import ExecutionRequest
from runtime.storage.execution_store import FileExecutionStore
from runtime.core.capability_governance import certified_dispatch
from runtime.executors.local import LocalExecutor
root=Path(sys.argv[1]);request=ExecutionRequest.from_persisted_dict(json.loads(Path(sys.argv[2]).read_text()))
jobs=JobRuntime(root/'jobs',clock=lambda:'2026-10-02T12:00:00Z');store=FileExecutionStore(Path(sys.argv[3]))
try:
 store.begin_decision(request,executor='f2-fresh-process',runtime=jobs,job=jobs.show(request.job_id))
 with certified_dispatch(store,request):
  result=LocalExecutor().execute(request)
except ValueError as error:
 print(json.dumps({'denied':True,'error':str(error)}));sys.exit(0)
print(json.dumps({'denied':False,'result':result.status}));sys.exit(3)
"""


class GovernanceF2Tests(unittest.TestCase):
    def test_r3_m1_coherent_identity_dispatch_rebind_rollback_fresh_process(self):
        for alternate in (False, True):
            for coherent_request_digest in (False, True):
                with self.subTest(alternate=alternate, coherent_request_digest=coherent_request_digest):
                    with fixture(cg.CapabilityGovernanceTests) as f:
                        job, request = f.prepared()
                        journal = f.runtime.progress.store.path(f.runtime.progress.logical_id(job))
                        before = journal.read_bytes()
                        f.begin(job, request)
                        with gov.certified_dispatch(f.store, request):
                            self.assertEqual(f.fixture.worker.executor.execute(request).status, "succeeded")
                        original = f.store._decision_pair(request.execution_id, "intent")
                        changed = deepcopy(original)
                        changed["request"]["job_id"] = "r3-foreign"
                        changed["authority_source"]["job_id"] = "r3-foreign"
                        if coherent_request_digest:
                            changed["request_digest"] = digest(changed["request"])
                        replace_pair(f.store, request.execution_id, "intent", changed)
                        replace_pair(f.store, request.execution_id, "dispatch-execute", {
                            "schema_version": 1, "intent_digest": digest(changed), "purpose": "execute"})
                        journal.write_bytes(before)
                        data = request.to_dict(); data["execution_id"] = "f2-replacement"
                        path = f.root / "replacement.json"; path.write_text(json.dumps(data))
                        owner = f.root / ("alternate-executions" if alternate else "executions")
                        child = subprocess.run([sys.executable, "-B", "-c", CHILD, str(f.root), str(path), str(owner)],
                                               cwd=ROOT, capture_output=True, text=True)
                        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
                        self.assertTrue(json.loads(child.stdout)["denied"])
                        self.assertFalse(FileExecutionStore(owner)._decision_path("f2-replacement", "intent", "anchor").exists())
                        print(json.dumps({"case": "R3-M1", "alternate": alternate,
                            "request_digest_rebound": coherent_request_digest, "fresh_process": json.loads(child.stdout)}))

    def test_r3_m1_foreign_retained_intent_cannot_redirect_journal_owner(self):
        with fixture(cg.CapabilityGovernanceTests) as f:
            job, request = f.prepared(); f.begin(job, request)
            with gov.certified_dispatch(f.store, request):
                gov.require_dispatch(request)
            value = f.store._decision_pair(request.execution_id, "intent")
            value["authority_source"]["progress_store_root"] = str(f.root / "foreign-progress")
            replace_pair(f.store, request.execution_id, "intent", value)
            replace_pair(f.store, request.execution_id, "dispatch-execute", {
                "schema_version": 1, "intent_digest": digest(value), "purpose": "execute"})
            # Even coherent observations placed under an untrusted owner cannot
            # certify retained bytes in the canonical admission scan.
            f.store._observe(value, "decision_intent_observed", request.execution_id, digest(value))
            f.store._observe(value, "decision_consumption_observed", f.store._intent_work_id(value), digest(value))
            next_job = f.runtime.create(f.fixture.payload()); f.runtime.enqueue(next_job["job_id"])
            next_job = f.runtime.claim(claimed_by="f2-next")
            from runtime.workers.worker import Worker
            next_request = Worker._build_request(next_job, "f2-next", ())
            with self.assertRaises(ValueError):
                f.store.begin_decision(next_request, executor="f2", runtime=f.runtime, job=next_job)

    def test_r3_m2_local_git_policy_loss_replacement_and_journal_rollback_at_consume(self):
        for attack in ("delete", "replace", "journal-rollback", "replace-and-journal-rollback"):
            with self.subTest(attack=attack), fixture(gt.GitRuntimeTests) as f:
                prepared = f.prepare(); identity = f.approve(prepared)
                journal = f.jobs.progress.store.path(f.jobs.progress.logical_id(f.jobs.show(f.job_id)))
                before = journal.read_bytes(); original = ActionDecision.consume
                def lose_trace(audit):
                    if attack == "delete":
                        delete_pair(audit.store, audit.identity, "action-policy")
                    elif attack.startswith("replace"):
                        value = deepcopy(audit.value); value["executor"] = "foreign"
                        replace_pair(audit.store, audit.identity, "action-policy", value)
                        if attack.endswith("journal-rollback"): journal.write_bytes(before)
                    else:
                        journal.write_bytes(before)
                    return original(audit)
                with patch.object(ActionDecision, "consume", lose_trace):
                    with self.assertRaises(ValueError):
                        f.runtime.commit(identity)
                self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
                self.assertEqual(f.git("diff", "--cached", "--name-only").stdout.strip(), "")
                store = FileExecutionStore(f.git_store.root)
                self.assertFalse(store._decision_path(prepared["approval"]["approval_id"], "action-effect", "anchor").exists())
                print(json.dumps({"case": "R3-M2-consume", "attack": attack, "commit_created": False, "denied": True}))

    def test_r3_m2_git_policy_loss_at_finish_never_accepts_or_refunds_effect(self):
        with fixture(gt.GitRuntimeTests) as f:
            prepared = f.prepare(); identity = f.approve(prepared)
            original = ActionDecision.finish
            def lose_trace(audit, result):
                delete_pair(audit.store, audit.identity, "action-policy")
                return original(audit, result)
            with patch.object(ActionDecision, "finish", lose_trace):
                with self.assertRaises(ValueError):
                    f.runtime.commit(identity)
            head = f.git("rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(head, f.base_head)  # effect exists; acceptance does not
            store = FileExecutionStore(f.git_store.root)
            approval_id = prepared["approval"]["approval_id"]
            self.assertTrue(store._decision_path(approval_id, "action-effect", "anchor").exists())
            self.assertFalse(store._decision_path(approval_id, "action-result", "anchor").exists())
            # New runtime instance (restart) cannot reconstruct missing provenance
            # from a successful commit or grant another execution of this approval.
            from runtime.git.runtime import GitRuntime
            restarted = GitRuntime(ROOT, f.jobs, f.executions, f.reviews, f.mutations, f.approvals, f.git_store)
            with self.assertRaises(ValueError): restarted.commit(identity)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), head)

    def test_r3_m2_remote_push_and_pr_deny_policy_loss_before_effect(self):
        for action in ("push", "pull-request"):
            with self.subTest(action=action), fixture(rg.RemoteGitRuntimeTests) as f:
                if action == "push":
                    identity = f.approve(f.prepare_push())
                else:
                    identity = f.approve_pr(f.prepare_pr())
                original = ActionDecision.consume
                def lose_trace(audit):
                    delete_pair(audit.store, audit.identity, "action-policy")
                    return original(audit)
                with patch.object(ActionDecision, "consume", lose_trace):
                    with self.assertRaises(ValueError):
                        if action == "push": f.runtime.push(identity)
                        else: f.runtime.create_pull_request(identity)
                if action == "push":
                    self.assertEqual(f.phase_i.git("ls-remote", "--heads", "origin", "phase-6j-test").stdout.strip(), "")
                self.assertEqual(f.adapter.create_calls, 0)

    def test_r3_m3_multifile_stops_after_first_write_when_any_required_evidence_is_lost(self):
        for attack in ("effect-delete", "effect-replace", "effect-replace-and-journal-rollback", "journal-rollback", "dispatch-delete",
                       "intent-delete", "authority-delete", "approval-delete"):
            with self.subTest(attack=attack), fixture(ac.ControlledWriteTests) as f:
                (f.target / "src" / "delete.txt").write_text("keep")
                request = f.request(f.scope(write_mode="CREATE_MODIFY_DELETE"))
                store, _, _ = gov._DISPATCH.get()
                intent = store._decision_pair(request.execution_id, "intent")
                journal = journal_for(intent); before = journal.read_bytes()
                writes = []; original = f.runtime._atomic_write
                def observed_write(path, contents):
                    original(path, contents)
                    if f.target in path.parents:
                        writes.append(str(path.relative_to(f.target)).replace("\\", "/"))
                        if len(writes) == 1:
                            if attack == "journal-rollback": journal.write_bytes(before)
                            elif attack.startswith("effect-replace"):
                                value = store._decision_pair(request.execution_id, "effect-controlled_write")
                                value["request_digest"] = "0" * 64
                                replace_pair(store, request.execution_id, "effect-controlled_write", value)
                                if attack.endswith("journal-rollback"): journal.write_bytes(before)
                            elif attack == "authority-delete":
                                from runtime.core.task_contract import TaskContractStore
                                TaskContractStore(Path(intent["authority_source"]["task_store_root"]), progress=None)._path(request.job_id, "witness").unlink()
                            elif attack == "approval-delete":
                                from runtime.approvals.store import FileApprovalStore
                                approval_id = next(iter(intent["approval_received"])).split(":", 1)[1]
                                FileApprovalStore(Path(intent["authority_source"]["approval_store_root"]))._path(approval_id).unlink()
                            else:
                                stage = {"effect-delete": "effect-controlled_write", "dispatch-delete": "dispatch-execute", "intent-delete": "intent"}[attack]
                                delete_pair(store, request.execution_id, stage)
                def mutate(workspace):
                    (workspace / "src" / "new.txt").write_text("first-mutation")
                    (workspace / "src" / "existing.txt").write_text("second-mutation")
                    (workspace / "src" / "delete.txt").unlink()
                with patch.object(f.runtime, "_atomic_write", side_effect=observed_write):
                    with self.assertRaises(ValueError):
                        f.execute_controlled(ac.MutatingAdapter(mutate), request)
                self.assertEqual(writes, ["src/new.txt"])
                self.assertEqual((f.target / "src" / "new.txt").read_text(), "first-mutation")
                self.assertEqual((f.target / "src" / "existing.txt").read_text(), "before\n")
                self.assertEqual((f.target / "src" / "delete.txt").read_text(), "keep")
                with self.assertRaises(ValueError):
                    with gov.certified_dispatch(FileExecutionStore(store.root), request): pass
                print(json.dumps({"case": "R3-M3", "attack": attack, "writes": writes, "denied": True, "replay_denied": True}))

    def test_r3_m3_deletion_and_final_acceptance_have_their_own_boundaries(self):
        for delete_next in (False, True):
            with self.subTest(delete_next=delete_next), fixture(ac.ControlledWriteTests) as f:
                if delete_next: (f.target / "src" / "delete.txt").write_text("keep")
                request = f.request(f.scope(write_mode="CREATE_MODIFY_DELETE") if delete_next else None)
                store, _, _ = gov._DISPATCH.get(); original = f.runtime._atomic_write
                def observed_write(path, contents):
                    original(path, contents)
                    if f.target in path.parents:
                        delete_pair(store, request.execution_id, "effect-controlled_write")
                def mutate(workspace):
                    (workspace / "src" / "existing.txt").write_text("first-mutation")
                    if delete_next: (workspace / "src" / "delete.txt").unlink()
                with patch.object(f.runtime, "_atomic_write", side_effect=observed_write):
                    with self.assertRaises(ValueError):
                        f.execute_controlled(ac.MutatingAdapter(mutate), request)
                self.assertEqual((f.target / "src" / "existing.txt").read_text(), "first-mutation")
                if delete_next: self.assertEqual((f.target / "src" / "delete.txt").read_text(), "keep")

    def test_r3_m3_io_failure_rolls_back_only_while_evidence_is_valid(self):
        for evidence_loss in (False, True):
            with self.subTest(evidence_loss=evidence_loss), fixture(ac.ControlledWriteTests) as f:
                request = f.request(); store, _, _ = gov._DISPATCH.get()
                writes = []; original = f.runtime._atomic_write
                def failed_write(path, contents):
                    if f.target in path.parents:
                        writes.append(path.name)
                        if path.name == "existing.txt":
                            if evidence_loss: delete_pair(store, request.execution_id, "effect-controlled_write")
                            raise OSError("fixture second target failure")
                    original(path, contents)
                def mutate(workspace):
                    (workspace / "src" / "new.txt").write_text("first")
                    (workspace / "src" / "existing.txt").write_text("second")
                with patch.object(f.runtime, "_atomic_write", side_effect=failed_write):
                    if evidence_loss:
                        with self.assertRaises(ValueError): f.execute_controlled(ac.MutatingAdapter(mutate), request)
                    else:
                        outcome = f.execute_controlled(ac.MutatingAdapter(mutate), request)
                        self.assertNotEqual(outcome.provider_result.status, "succeeded")
                self.assertEqual((f.target / "src" / "existing.txt").read_text(), "before\n")
                self.assertEqual((f.target / "src" / "new.txt").exists(), evidence_loss)
