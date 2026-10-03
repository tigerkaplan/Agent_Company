"""Fresh-process confirmation and PR check; temporary effects only."""
import hashlib
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
from runtime.tests import test_git as gt, test_remote_git as rg

def journal(audit):
    source=audit.value['authority_source']
    return ProgressStore(Path(source['progress_store_root'])).path(source['logical_job_id'])

def fingerprints(f):
    paths=set(f.jobs.store.root.rglob('*.json')) | set(f.jobs.task_contract_store.root.rglob('*.json')) | set(f.approval_store.root.rglob('*.json'))
    return {str(p.relative_to(f.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

CHILD='''import json,sys,subprocess
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.storage.execution_store import FileExecutionStore
from runtime.review.store import FileReviewStore
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.store import FileApprovalStore
from runtime.approvals.runtime import ApprovalRuntime
from runtime.git.store import FileGitArtifactStore
from runtime.git.runtime import GitRuntime
root=Path(sys.argv[1]); repository=Path(sys.argv[2]); state=root/'state'
jobs=JobRuntime(state/'jobs'); executions=FileExecutionStore(state/'executions')
reviews=FileReviewStore(state/'executions'/'reviews'); mutations=FileMutationArtifactStore(state/'executions'/'mutations')
approvals=ApprovalRuntime(jobs,FileApprovalStore(state/'approvals'),execution_store=executions,review_store=reviews)
runtime=GitRuntime(Path.cwd(),jobs,executions,reviews,mutations,approvals,FileGitArtifactStore(state/'executions'/'git'))
count=lambda:subprocess.check_output(['git','-C',str(repository),'rev-list','--count','HEAD'],text=True).strip()
before=count()
try:
 result=runtime.commit(sys.argv[3]);accepted=True;error=None
except ValueError as exc:
 accepted=False;error=str(exc)
print(json.dumps(dict(accepted=accepted,error=error,commit_count_before=before,commit_count_after=count())))
sys.exit(3 if accepted else 0)
'''

observations=[]
f=gt.GitRuntimeTests();f.setUp()
try:
    prepared=f.prepare();identity=f.approve(prepared);before=fingerprints(f)
    saved={};original_consume=ActionDecision.consume;original_git=f.runtime._git
    def remember(audit):
        saved.update(audit=audit,journal=journal(audit),before=journal(audit).read_bytes())
        return original_consume(audit)
    def after_stage(repository,arguments,**kwargs):
        result=original_git(repository,arguments,**kwargs)
        if arguments[0]=='add': saved['journal'].write_bytes(saved['before'])
        return result
    with patch.object(ActionDecision,'consume',remember),patch.object(f.runtime,'_git',side_effect=after_stage):
        result=f.runtime.commit(identity)
    audit=saved['audit'];trace=audit.store._decision_pair(audit.identity,'action-result')
    child=subprocess.run([sys.executable,'-B','-c',CHILD,str(f.root),str(f.repository),identity],cwd=ROOT,capture_output=True,text=True)
    observations.append(dict(case='commit-journal-only-rollback-fresh-process',
        success=True,effect_performed=trace['effect_performed'],
        commit_created=f.git('rev-parse','HEAD').stdout.strip()!=f.base_head,
        effect_pair_survived=all(audit.store._decision_path(audit.identity,'action-effect',s).exists() for s in ('anchor','witness')),
        authority_job_approval_files_unchanged=before==fingerprints(f),authority_fingerprints=before,
        child_returncode=child.returncode,child_stdout=child.stdout,child_stderr=child.stderr))
finally:f.tearDown()

f=rg.RemoteGitRuntimeTests();f.setUp()
try:
    identity=f.approve_pr(f.prepare_pr());before=fingerprints(f.phase_i)
    saved={};original_consume=ActionDecision.consume;original_create=f.adapter.create
    def remember(audit):
        saved.update(audit=audit,journal=journal(audit),before=journal(audit).read_bytes())
        return original_consume(audit)
    def after_create(*args,**kwargs):
        state=original_create(*args,**kwargs)
        saved['journal'].write_bytes(saved['before'])
        return state
    with patch.object(ActionDecision,'consume',remember),patch.object(f.adapter,'create',side_effect=after_create):
        result=f.runtime.create_pull_request(identity)
    audit=saved['audit'];trace=audit.store._decision_pair(audit.identity,'action-result')
    observations.append(dict(case='fake-pr-journal-only-rollback-after-effect',success=True,
        effect_performed=trace['effect_performed'],adapter_create_calls=f.adapter.create_calls,
        effect_pair_survived=all(audit.store._decision_path(audit.identity,'action-effect',s).exists() for s in ('anchor','witness')),
        authority_job_approval_files_unchanged=before==fingerprints(f.phase_i)))
finally:f.tearDown()

(OUT/'action-confirmation-observations.json').write_text(json.dumps(observations,indent=2)+'\n')
print(json.dumps(observations,indent=2))
sys.exit(1 if any(o['success'] and not o['effect_performed'] for o in observations) else 0)
