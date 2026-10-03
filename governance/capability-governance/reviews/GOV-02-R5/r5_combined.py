"""Independent R5 combined staging-loss, journal-rollback and restart probes."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from runtime.core.capability_actions import ActionDecision
from runtime.progress.store import ProgressStore
from runtime.tests import test_git as gt, test_remote_git as rg

OBSERVATIONS = []
CHILD = '''import json,sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.storage.execution_store import FileExecutionStore
from runtime.review.store import FileReviewStore
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.store import FileApprovalStore
from runtime.approvals.runtime import ApprovalRuntime
from runtime.git.store import FileGitArtifactStore
from runtime.git.runtime import GitRuntime
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.git.remote_runtime import RemoteGitRuntime
root,identity,action=sys.argv[1:]; state=Path(root)/'state'
jobs=JobRuntime(state/'jobs'); executions=FileExecutionStore(state/'executions')
reviews=FileReviewStore(state/'executions'/'reviews')
approvals=ApprovalRuntime(jobs,FileApprovalStore(state/'approvals'),execution_store=executions,review_store=reviews)
local=GitRuntime(Path.cwd(),jobs,executions,reviews,FileMutationArtifactStore(state/'executions'/'mutations'),approvals,FileGitArtifactStore(state/'executions'/'git'))
target=local if action=='commit' else RemoteGitRuntime(local,approvals,FileRemoteGitArtifactStore(state/'executions'/'git'))
commands=[]; original=target._git
def record(repository,args,**kwargs):
 commands.append(args[0]); return original(repository,args,**kwargs)
target._git=record
try:
 getattr(target,action)(identity); denied=False; error=None
except ValueError as exc:denied=True; error=str(exc)
print(json.dumps(dict(denied=denied,error=error,commands=commands)))
'''

@contextmanager
def fixture(kind):
    case = kind(); case.setUp()
    try:
        yield case
    finally:
        case.tearDown()

def journal(audit):
    source = audit.value['authority_source']
    return ProgressStore(Path(source['progress_store_root'])).path(source['logical_job_id'])

def remove(audit, stage, suffixes=('anchor', 'witness')):
    for suffix in suffixes:
        audit.store._decision_path(audit.identity, stage, suffix).unlink(missing_ok=True)

def authorities(local):
    paths = list(local.jobs.task_contract_store.root.glob('*.json'))
    paths += list(local.jobs.store.root.glob('*.json'))
    paths += list(local.approval_store.root.glob('*.json'))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

class R5Combined(unittest.TestCase):
    def restart(self, local, identity, action):
        child = subprocess.run([sys.executable, '-B', '-c', CHILD, str(local.root), identity, action],
                               cwd=ROOT, capture_output=True, text=True, timeout=90)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        result = json.loads(child.stdout)
        self.assertTrue(result['denied'], result)
        self.assertFalse(set(result['commands']) & {'add', 'commit', 'push'}, result)
        return result

    def test_staging_rollback_plus_pair_or_authority_loss_stops_commit_and_restart(self):
        for loss in ('effect', 'effect-and-policy-witness', 'effect-and-approval'):
            with self.subTest(loss=loss), fixture(gt.GitRuntimeTests) as f:
                identity = f.approve(f.prepare()); saved = {}; commands = []
                authority_before = authorities(f)
                original_consume = ActionDecision.consume; original_git = f.runtime._git
                def remember(audit):
                    saved.update(audit=audit, before=journal(audit).read_bytes())
                    return original_consume(audit)
                def after_stage(repository, args, **kwargs):
                    result = original_git(repository, args, **kwargs); commands.append(args[0])
                    if args[0] == 'add':
                        audit = saved['audit']; journal(audit).write_bytes(saved['before'])
                        remove(audit, 'action-effect')
                        if loss == 'effect-and-policy-witness': remove(audit, 'action-policy', ('witness',))
                        if loss == 'effect-and-approval': f.approval_store._path(audit.identity).unlink()
                    return result
                with patch.object(ActionDecision, 'consume', remember), patch.object(f.runtime, '_git', side_effect=after_stage):
                    with self.assertRaises(ValueError) as error: f.runtime.commit(identity)
                self.assertNotIn('commit', commands); self.assertNotIn('reset', commands)
                self.assertEqual(f.git('rev-parse', 'HEAD').stdout.strip(), f.base_head)
                restart = self.restart(f, identity, 'commit')
                self.assertEqual(f.git('rev-parse', 'HEAD').stdout.strip(), f.base_head)
                intact = authorities(f) == authority_before
                if loss != 'effect-and-approval': self.assertTrue(intact)
                OBSERVATIONS.append(dict(case='staging-combined', loss=loss, error=str(error.exception),
                    commands=commands, restart=restart, target_head_unchanged=True,
                    canonical_authorities_unchanged=intact))

    def test_retained_partial_failure_never_refunds_local_or_remote_work(self):
        for action in ('commit', 'push'):
            for partial_failure in (False, True):
                with self.subTest(action=action, partial_failure=partial_failure), fixture(gt.GitRuntimeTests if action == 'commit' else rg.RemoteGitRuntimeTests) as f:
                    local = f if action == 'commit' else f.phase_i
                    identity = f.approve(f.prepare()) if action == 'commit' else f.approve(f.prepare_push())
                    saved = {}; original_consume = ActionDecision.consume; original_git = f.runtime._git
                    authority_before = authorities(local)
                    def remember(audit):
                        saved.update(audit=audit, before=journal(audit).read_bytes())
                        return original_consume(audit)
                    def fail_effect(repository, args, **kwargs):
                        if args[0] == ('add' if action == 'commit' else 'push'):
                            return subprocess.CompletedProcess(args, 1, stdout='', stderr='R5 injected effect failure')
                        return original_git(repository, args, **kwargs)
                    with patch.object(ActionDecision, 'consume', remember), patch.object(f.runtime, '_git', side_effect=fail_effect):
                        with self.assertRaises(ValueError): getattr(f.runtime, action)(identity)
                    audit = saved['audit']
                    failure = {s: audit.store._decision_path(audit.identity, 'action-failure', s).read_bytes() for s in ('anchor', 'witness')}
                    self.assertTrue(json.loads(failure['anchor'])['result']['effect_may_be_partial'])
                    journal(audit).write_bytes(saved['before']); remove(audit, 'action-effect')
                    if partial_failure: remove(audit, 'action-failure', ('witness',))
                    count = local.git('rev-list', '--count', 'HEAD').stdout
                    remote = local.git('ls-remote', '--heads', 'origin', 'phase-6j-test').stdout if action == 'push' else None
                    restart = self.restart(local, identity, action)
                    self.assertEqual(local.git('rev-list', '--count', 'HEAD').stdout, count)
                    if action == 'push': self.assertEqual(local.git('ls-remote', '--heads', 'origin', 'phase-6j-test').stdout, remote)
                    self.assertEqual(audit.store._decision_path(audit.identity, 'action-failure', 'anchor').read_bytes(), failure['anchor'])
                    self.assertEqual(authorities(local), authority_before)
                    OBSERVATIONS.append(dict(case='retained-failure-combined', action=action,
                        partial_failure=partial_failure, restart=restart, canonical_authorities_unchanged=True,
                        surviving_failure_unchanged=True, target_unchanged=True))

    def test_duplicate_approval_fields_fail_before_first_effect(self):
        for value in ('same', 'different'):
            with self.subTest(value=value), fixture(gt.GitRuntimeTests) as f:
                prepared = f.prepare(); identity = f.approve(prepared)
                path = f.approval_store._path(prepared['approval']['approval_id'])
                raw = path.read_bytes(); request = json.loads(raw)
                actor = request['decided_by'] if value == 'same' else 'forged-owner'
                altered = raw.rstrip()[:-1] + b',"decided_by":' + json.dumps(actor).encode() + b'}\n'
                path.write_bytes(altered)
                commands = []; original = f.runtime._git
                def record(repository, args, **kwargs):
                    commands.append(args[0]); return original(repository, args, **kwargs)
                with patch.object(f.runtime, '_git', side_effect=record):
                    with self.assertRaises(ValueError) as error: f.runtime.commit(identity)
                self.assertFalse(set(commands) & {'add', 'commit'})
                self.assertEqual(f.git('rev-parse', 'HEAD').stdout.strip(), f.base_head)
                OBSERVATIONS.append(dict(case='duplicate-approval', value=value, error=str(error.exception),
                    commands=commands, target_head_unchanged=True))

if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        (OUT / 'r5-combined-observations.json').write_text(json.dumps(OBSERVATIONS, indent=2) + '\n')
