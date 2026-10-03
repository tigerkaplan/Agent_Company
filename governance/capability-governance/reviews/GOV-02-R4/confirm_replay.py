"""Consumed Git work rollback with retained independent failure evidence."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from runtime.core.capability_actions import ActionDecision
from runtime.progress.store import ProgressStore
from runtime.tests import test_git as gt

# Reuse only the deterministic subprocess body, without executing its probes.
import ast
tree=ast.parse((OUT/'confirm_actions.py').read_text())
CHILD=next(ast.literal_eval(n.value) for n in tree.body
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CHILD' for t in n.targets))

f=gt.GitRuntimeTests();f.setUp()
try:
    prepared=f.prepare();identity=f.approve(prepared)
    saved={};original_consume=ActionDecision.consume;original_git=f.runtime._git
    def remember(audit):
        source=audit.value['authority_source']
        journal=ProgressStore(Path(source['progress_store_root'])).path(source['logical_job_id'])
        saved.update(audit=audit,journal=journal,before=journal.read_bytes())
        return original_consume(audit)
    def fail_staging(repository,arguments,**kwargs):
        if arguments[0]=='add':return subprocess.CompletedProcess(arguments,1,stdout='',stderr='R4 simulated staging failure')
        return original_git(repository,arguments,**kwargs)
    first_error=None
    with patch.object(ActionDecision,'consume',remember),patch.object(f.runtime,'_git',side_effect=fail_staging):
        try:f.runtime.commit(identity)
        except ValueError as exc:first_error=str(exc)
    audit=saved['audit'];failure=audit.store._decision_pair(audit.identity,'action-failure')
    initial_head=f.git('rev-parse','HEAD').stdout.strip()
    # Restore consumption evidence stores only. Retain the failure pair recording
    # effect_may_be_partial=true, original policy pair, task/job/approval owners,
    # original plan and unchanged target repository.
    saved['journal'].write_bytes(saved['before'])
    for suffix in ('anchor','witness'):
        audit.store._decision_path(audit.identity,'action-effect',suffix).unlink()
    child=subprocess.run([sys.executable,'-B','-c',CHILD,str(f.root),str(f.repository),identity],cwd=ROOT,capture_output=True,text=True)
    after_head=f.git('rev-parse','HEAD').stdout.strip()
    value=dict(case='consumed-git-generation-refunded-despite-retained-failure',
        first_error=first_error,first_target_unchanged=initial_head==f.base_head,
        retained_failure=failure,retained_failure_pair_unchanged=audit.store._decision_pair(audit.identity,'action-failure')==failure,
        child_returncode=child.returncode,child_stdout=child.stdout,child_stderr=child.stderr,
        commit_created_after_restart=after_head!=initial_head,
        same_canonical_approval_id=audit.identity,new_human_approval=False)
    (OUT/'replay-confirmation-observations.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value,indent=2))
    sys.exit(1 if value['commit_created_after_restart'] else 0)
finally:f.tearDown()
