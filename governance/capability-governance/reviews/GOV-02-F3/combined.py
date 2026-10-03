"""Reviewer-created near-boundary Git evidence-loss and rollback attacks."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from runtime.core.capability_actions import ActionDecision
from runtime.storage.execution_store import FileExecutionStore
from runtime.progress.store import ProgressStore
from runtime.tests import test_git as gt, test_remote_git as rg

OBSERVATIONS = []

@contextmanager
def fixture(kind):
    f = kind(); f.setUp()
    try: yield f
    finally: f.tearDown()

def journal(audit):
    source = audit.value["authority_source"]
    return ProgressStore(Path(source["progress_store_root"])).path(source["logical_job_id"])

def lose_pair(audit, stage):
    for suffix in ("anchor", "witness"):
        audit.store._decision_path(audit.identity, stage, suffix).unlink()

class CombinedAttacks(unittest.TestCase):
    def test_git_loss_after_staging_denies_subsequent_commit(self):
        for stage in ("action-policy", "action-effect"):
            with self.subTest(stage=stage), fixture(gt.GitRuntimeTests) as f:
                prepared = f.prepare(); identity = f.approve(prepared)
                audits = []; original_consume = ActionDecision.consume; original_git = f.runtime._git
                def remember(audit):
                    audits.append(audit); return original_consume(audit)
                commands = []
                def after_stage(repository, arguments, **kwargs):
                    result = original_git(repository, arguments, **kwargs)
                    commands.append(arguments)
                    if arguments[0] == "add": lose_pair(audits[0], stage)
                    return result
                error = None; outcome = None
                with patch.object(ActionDecision, "consume", remember), patch.object(f.runtime, "_git", side_effect=after_stage):
                    try: outcome = f.runtime.commit(identity)
                    except ValueError as exc: error = str(exc)
                changed = f.git("rev-parse", "HEAD").stdout.strip() != f.base_head
                OBSERVATIONS.append(dict(case="git-loss-after-staging",stage=stage,commit_created=changed,
                    success=outcome is not None,error=error,commands=commands))
                self.assertIsNone(outcome)
                self.assertFalse(changed, "Git commit ran after required evidence disappeared during staging")

    def test_git_journal_rollback_after_consumption_denies_acceptance(self):
        with fixture(gt.GitRuntimeTests) as f:
            prepared=f.prepare(); identity=f.approve(prepared)
            saved={}; original_consume=ActionDecision.consume; original_git=f.runtime._git
            def remember(audit):
                saved.update(audit=audit, journal=journal(audit), before=journal(audit).read_bytes())
                return original_consume(audit)
            def after_stage(repository, arguments, **kwargs):
                result=original_git(repository, arguments, **kwargs)
                if arguments[0]=="add": saved["journal"].write_bytes(saved["before"])
                return result
            outcome=None; error=None
            with patch.object(ActionDecision,"consume",remember), patch.object(f.runtime,"_git",side_effect=after_stage):
                try: outcome=f.runtime.commit(identity)
                except ValueError as exc: error=str(exc)
            audit=saved["audit"]
            changed=f.git("rev-parse","HEAD").stdout.strip()!=f.base_head
            trace=None
            if outcome is not None: trace=audit.store._decision_pair(audit.identity,"action-result")
            restarted=None; restart_error=None
            from runtime.git.runtime import GitRuntime
            fresh=GitRuntime(ROOT,f.jobs,f.executions,f.reviews,f.mutations,f.approvals,f.git_store)
            try: restarted=fresh.commit(identity)
            except ValueError as exc: restart_error=str(exc)
            OBSERVATIONS.append(dict(case="git-journal-rollback-after-consumption",commit_created=changed,
                success=outcome is not None,error=error,result_trace=trace,
                surviving_effect_pair=audit.store._decision_path(audit.identity,"action-effect","anchor").exists(),
                restart_accepted=restarted is not None,restart_error=restart_error))
            self.assertIsNone(outcome,"Git effect accepted after rollback erased consumption observation")
            self.assertIsNone(restarted,"Restart accepted surviving effect without consumption observation")

    def test_remote_push_journal_rollback_after_effect_denies_acceptance(self):
        with fixture(rg.RemoteGitRuntimeTests) as f:
            prepared=f.prepare_push(); identity=f.approve(prepared)
            saved={}; original_consume=ActionDecision.consume; original_git=f.runtime._git
            def remember(audit):
                saved.update(audit=audit,journal=journal(audit),before=journal(audit).read_bytes())
                return original_consume(audit)
            def after_push(repository, arguments, **kwargs):
                result=original_git(repository,arguments,**kwargs)
                if arguments[0]=="push": saved["journal"].write_bytes(saved["before"])
                return result
            outcome=None; error=None
            with patch.object(ActionDecision,"consume",remember),patch.object(f.runtime,"_git",side_effect=after_push):
                try: outcome=f.runtime.push(identity)
                except ValueError as exc: error=str(exc)
            audit=saved["audit"]; trace=None
            if outcome is not None: trace=audit.store._decision_pair(audit.identity,"action-result")
            remote=f.phase_i.git("ls-remote","--heads","origin","phase-6j-test").stdout.strip()
            from runtime.git.remote_runtime import RemoteGitRuntime
            fresh=RemoteGitRuntime(f.phase_i.runtime,f.phase_i.approvals,f.store,pull_request_adapter=f.adapter)
            restarted=None; restart_error=None
            try: restarted=fresh.push(identity)
            except ValueError as exc: restart_error=str(exc)
            OBSERVATIONS.append(dict(case="remote-push-rollback-after-effect",remote_head=remote,
                success=outcome is not None,error=error,result_trace=trace,
                restart_accepted=restarted is not None,restart_error=restart_error))
            self.assertIsNone(outcome,"Remote effect accepted after rollback erased consumption observation")
            self.assertIsNone(restarted)

if __name__=="__main__":
    try: unittest.main()
    finally: (Path(__file__).resolve().parent/"combined-observations.json").write_text(json.dumps(OBSERVATIONS,indent=2)+"\n")
