"""R4 Git consumption rollback and mutation-boundary regressions."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from runtime.core.capability_actions import ActionDecision
from runtime.core.task_contract import encoded
from runtime.progress.store import ProgressStore
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests import test_git as gt, test_remote_git as rg

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def fixture(kind):
    case = kind(); case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


def journal(audit):
    source = audit.value["authority_source"]
    return ProgressStore(Path(source["progress_store_root"])).path(source["logical_job_id"])


def lose_pair(audit, stage):
    for suffix in ("anchor", "witness"):
        audit.store._decision_path(audit.identity, stage, suffix).unlink()


CHILD = """import json,sys,subprocess
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.storage.execution_store import FileExecutionStore
from runtime.review.store import FileReviewStore
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.store import FileApprovalStore
from runtime.approvals.runtime import ApprovalRuntime
from runtime.git.store import FileGitArtifactStore
from runtime.git.runtime import GitRuntime
from runtime.git.remote_runtime import RemoteGitRuntime
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.git.forge import PullRequestState
from runtime.tests.test_remote_git import FakePullRequestAdapter
data=json.loads(Path(sys.argv[1]).read_text());state=Path(data['root'])/'state'
jobs=JobRuntime(state/'jobs');executions=FileExecutionStore(state/'executions')
reviews=FileReviewStore(state/'executions'/'reviews');mutations=FileMutationArtifactStore(state/'executions'/'mutations')
approvals=ApprovalRuntime(jobs,FileApprovalStore(state/'approvals'),execution_store=executions,review_store=reviews)
local=GitRuntime(Path.cwd(),jobs,executions,reviews,mutations,approvals,FileGitArtifactStore(state/'executions'/'git'))
adapter=FakePullRequestAdapter()
if data.get('pr_state'):adapter.state=PullRequestState(**data['pr_state'])
remote=RemoteGitRuntime(local,approvals,FileRemoteGitArtifactStore(state/'executions'/'git'),pull_request_adapter=adapter)
if data['action']=='create_pull_request':remote._remote_head=lambda *args:data['head_commit']
target=local if data['action']=='commit' else remote
try:
 getattr(target,data['action'])(data['identity']);denied=False;error=None
except ValueError as exc:denied=True;error=str(exc)
print(json.dumps({'denied':denied,'error':error,'pr_create_calls':adapter.create_calls}))
sys.exit(0 if denied else 3)
"""


class GovernanceF3Tests(unittest.TestCase):
    def fresh_denies(self, f, identity, action="commit"):
        local = f if action == "commit" else f.phase_i
        data = {"root": str(local.root), "identity": identity, "action": action}
        if action == "create_pull_request":
            data.update(pr_state=asdict(f.adapter.state) if f.adapter.state else None,
                        head_commit=f.adapter.head_commit)
        path = local.root / "f3-restart.json"; path.write_text(json.dumps(data))
        child = subprocess.run([sys.executable, "-B", "-c", CHILD, str(path)],
                               cwd=ROOT, capture_output=True, text=True, timeout=90)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        outcome = json.loads(child.stdout)
        self.assertTrue(outcome["denied"])
        self.assertEqual(outcome["pr_create_calls"], 0)
        print(json.dumps({"fresh_process": action, **outcome}))

    def test_r4_m1_journal_rollback_during_staging_denies_commit_and_restart(self):
        with fixture(gt.GitRuntimeTests) as f:
            identity = f.approve(f.prepare()); saved = {}
            original_consume = ActionDecision.consume; original_git = f.runtime._git
            def remember(audit):
                saved.update(audit=audit, before=journal(audit).read_bytes())
                return original_consume(audit)
            def after_stage(repository, arguments, **kwargs):
                result = original_git(repository, arguments, **kwargs)
                if arguments[0] == "add": journal(saved["audit"]).write_bytes(saved["before"])
                return result
            with patch.object(ActionDecision, "consume", remember), patch.object(f.runtime, "_git", side_effect=after_stage):
                with self.assertRaises(ValueError): f.runtime.commit(identity)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
            audit = saved["audit"]
            self.assertTrue(audit.store._decision_path(audit.identity, "action-effect", "anchor").exists())
            self.assertTrue(audit.store._decision_pair(audit.identity, "action-failure")["result"]["effect_may_be_partial"])
            self.fresh_denies(f, identity)
            self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)

    def test_r4_m1_retained_failure_vetoes_consumption_refund_before_staging(self):
        for retain_observation in (False, True):
            with self.subTest(retain_observation=retain_observation), fixture(gt.GitRuntimeTests) as f:
                identity = f.approve(f.prepare()); saved = {}; commands = []
                original_consume = ActionDecision.consume; original_git = f.runtime._git
                def remember(audit):
                    saved.update(audit=audit, before=journal(audit).read_bytes())
                    return original_consume(audit)
                def fail_stage(repository, arguments, **kwargs):
                    commands.append(arguments[0])
                    if arguments[0] == "add":
                        return subprocess.CompletedProcess(arguments, 1, stdout="", stderr="R4 staging failure")
                    return original_git(repository, arguments, **kwargs)
                with patch.object(ActionDecision, "consume", remember), patch.object(f.runtime, "_git", side_effect=fail_stage):
                    with self.assertRaises(ValueError): f.runtime.commit(identity)
                audit = saved["audit"]; path = journal(audit)
                failures = {s: audit.store._decision_path(audit.identity, "action-failure", s).read_bytes()
                            for s in ("anchor", "witness")}
                later = path.read_bytes()[len(saved["before"]):]
                path.write_bytes(saved["before"] + (b"".join(line + b"\n" for line in later.splitlines()
                    if json.loads(line)["event_type"] == "decision_result_observed") if retain_observation else b""))
                lose_pair(audit, "action-effect")
                self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
                commands.clear()
                with patch.object(f.runtime, "_git", side_effect=fail_stage):
                    with self.assertRaises(ValueError): f.runtime.commit(identity)
                self.assertNotIn("add", commands); self.assertNotIn("commit", commands)
                self.fresh_denies(f, identity)
                self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
                for suffix, raw in failures.items():
                    self.assertEqual(audit.store._decision_path(audit.identity, "action-failure", suffix).read_bytes(), raw)

    def test_r4_m1_rollback_after_real_commit_push_or_fake_pr_denies_acceptance(self):
        for action in ("commit", "push", "create_pull_request"):
            with self.subTest(action=action), fixture(gt.GitRuntimeTests if action == "commit" else rg.RemoteGitRuntimeTests) as f:
                identity = (f.approve(f.prepare()) if action == "commit" else
                            f.approve(f.prepare_push()) if action == "push" else f.approve_pr(f.prepare_pr()))
                saved = {}; original_consume = ActionDecision.consume
                def remember(audit):
                    saved.update(audit=audit, before=journal(audit).read_bytes())
                    return original_consume(audit)
                if action == "create_pull_request":
                    original = f.adapter.create
                    def after_effect(*args, **kwargs):
                        result = original(*args, **kwargs)
                        journal(saved["audit"]).write_bytes(saved["before"])
                        return result
                    effect_patch = patch.object(f.adapter, "create", side_effect=after_effect)
                else:
                    original = f.runtime._git
                    def after_effect(repository, arguments, **kwargs):
                        result = original(repository, arguments, **kwargs)
                        if arguments[0] == action: journal(saved["audit"]).write_bytes(saved["before"])
                        return result
                    effect_patch = patch.object(f.runtime, "_git", side_effect=after_effect)
                with patch.object(ActionDecision, "consume", remember), effect_patch:
                    with self.assertRaises(ValueError): getattr(f.runtime, action)(identity)
                audit = saved["audit"]
                self.assertFalse(audit.store._decision_path(audit.identity, "action-result", "anchor").exists())
                if action == "commit": self.assertNotEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
                elif action == "push": self.assertTrue(f.phase_i.git("ls-remote", "--heads", "origin", "phase-6j-test").stdout.strip())
                else: self.assertEqual(f.adapter.create_calls, 1)
                local = f if action == "commit" else f.phase_i
                count = local.git("rev-list", "--count", "HEAD").stdout
                self.fresh_denies(f, identity, action)
                self.assertEqual(local.git("rev-list", "--count", "HEAD").stdout, count)

    def test_r4_m1_retained_result_prevents_refund_even_without_effect_and_observation(self):
        with fixture(gt.GitRuntimeTests) as f:
            identity = f.approve(f.prepare()); saved = {}; original_consume = ActionDecision.consume
            def remember(audit):
                saved.update(audit=audit, before=journal(audit).read_bytes())
                return original_consume(audit)
            with patch.object(ActionDecision, "consume", remember): f.runtime.commit(identity)
            audit = saved["audit"]; result = audit.store._decision_path(audit.identity, "action-result", "anchor").read_bytes()
            journal(audit).write_bytes(saved["before"]); lose_pair(audit, "action-effect")
            self.fresh_denies(f, identity)
            self.assertEqual(audit.store._decision_path(audit.identity, "action-result", "anchor").read_bytes(), result)
            with self.assertRaises(ValueError): audit.consume()

    def test_r4_m2_loss_change_or_noncanonical_evidence_during_staging_blocks_commit(self):
        attacks = ("policy-delete", "effect-delete", "policy-change", "effect-change", "policy-noncanonical",
                   "effect-noncanonical", "approval-delete", "approval-change", "approval-noncanonical",
                   "task-delete", "journal-rollback", "effect-and-journal-loss")
        for attack in attacks:
            with self.subTest(attack=attack), fixture(gt.GitRuntimeTests) as f:
                prepared = f.prepare(); identity = f.approve(prepared); saved = {}; commands = []
                original_consume = ActionDecision.consume; original_git = f.runtime._git
                def remember(audit):
                    saved.update(audit=audit, before=journal(audit).read_bytes())
                    return original_consume(audit)
                def after_stage(repository, arguments, **kwargs):
                    result = original_git(repository, arguments, **kwargs); commands.append(arguments[0])
                    if arguments[0] != "add": return result
                    audit = saved["audit"]
                    if attack in ("journal-rollback", "effect-and-journal-loss"):
                        journal(audit).write_bytes(saved["before"])
                        if attack == "effect-and-journal-loss": lose_pair(audit, "action-effect")
                    elif attack == "task-delete": f.jobs.task_contract_store._path(f.job_id, "witness").unlink()
                    elif attack.startswith("approval-"):
                        path = f.approval_store._path(audit.identity)
                        if attack == "approval-delete": path.unlink()
                        elif attack == "approval-noncanonical": path.write_bytes(path.read_bytes() + b" ")
                        else:
                            value = json.loads(path.read_bytes()); value["decided_by"] = "changed-owner"
                            path.write_bytes(encoded(value))
                    else:
                        stage = "action-policy" if attack.startswith("policy-") else "action-effect"
                        if attack.endswith("delete"): lose_pair(audit, stage)
                        else:
                            value = deepcopy(audit.store._decision_pair(audit.identity, stage))
                            if stage == "action-policy": value["executor"] = "changed-executor"
                            else: value["action_digest"] = "0" * 64
                            for suffix in ("anchor", "witness"):
                                path = audit.store._decision_path(audit.identity, stage, suffix)
                                path.write_bytes(path.read_bytes() + b" " if attack.endswith("noncanonical") else encoded(value))
                    return result
                with patch.object(ActionDecision, "consume", remember), patch.object(f.runtime, "_git", side_effect=after_stage):
                    with self.assertRaises(ValueError): f.runtime.commit(identity)
                self.assertNotIn("commit", commands); self.assertNotIn("reset", commands)
                self.assertEqual(f.git("rev-parse", "HEAD").stdout.strip(), f.base_head)
                self.assertTrue(f.git("diff", "--cached", "--name-only").stdout.strip())

    def test_r4_m2_loss_after_consumption_blocks_first_local_and_remote_effect(self):
        for action in ("commit", "push", "create_pull_request"):
            for stage in ("action-policy", "action-effect"):
                with self.subTest(action=action, stage=stage), fixture(gt.GitRuntimeTests if action == "commit" else rg.RemoteGitRuntimeTests) as f:
                    identity = (f.approve(f.prepare()) if action == "commit" else
                                f.approve(f.prepare_push()) if action == "push" else f.approve_pr(f.prepare_pr()))
                    original_consume = ActionDecision.consume; commands = []; original_git = f.runtime._git
                    def lose(audit):
                        result = original_consume(audit); lose_pair(audit, stage); return result
                    def record(repository, arguments, **kwargs):
                        commands.append(arguments[0]); return original_git(repository, arguments, **kwargs)
                    with patch.object(ActionDecision, "consume", lose), patch.object(f.runtime, "_git", side_effect=record):
                        with self.assertRaises(ValueError): getattr(f.runtime, action)(identity)
                    self.assertNotIn("add", commands); self.assertNotIn("commit", commands); self.assertNotIn("push", commands)
                    if action != "commit": self.assertEqual(f.adapter.create_calls, 0)

    def test_genuine_existing_external_effect_keeps_observation_only_recovery(self):
        with fixture(rg.RemoteGitRuntimeTests) as f:
            identity = f.approve(f.prepare_push()); plan = f.store.load_push_plan(identity)
            f.phase_i.git("push", "origin", f"{plan.commit_hash}:refs/heads/{plan.remote_branch}")
            result = f.runtime.push(identity)
            audit_store = FileExecutionStore(f.store.root)
            trace = audit_store._decision_pair(result["push_plan"]["approval_ref"]["ref"].split(":", 1)[1], "action-result")
            self.assertFalse(trace["effect_performed"])
            self.assertTrue(result["push_evidence"]["already_present"])
            self.assertEqual(f.runtime.push(identity), result)


if __name__ == "__main__":
    unittest.main()
