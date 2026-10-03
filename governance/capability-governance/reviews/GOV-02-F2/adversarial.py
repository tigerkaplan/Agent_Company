"""Independent combined attacks using real runtime APIs in temporary state."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from runtime.core import capability_governance as gov
from runtime.core.task_contract import encoded, digest
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests import test_capability_governance as cg, test_actions as ac, test_git as gt, test_task_contract as tc
from runtime.workers.worker import Worker

OBSERVATIONS = []

def pair(store, execution, stage, value):
    for suffix in ('anchor', 'witness'):
        store._decision_path(execution, stage, suffix).write_bytes(encoded(value, max_bytes=512*1024))

CHILD = '''import json,sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.execution.models import ExecutionRequest
from runtime.storage.execution_store import FileExecutionStore
from runtime.core.capability_governance import certified_dispatch,require_dispatch
root=Path(sys.argv[1]); request=ExecutionRequest.from_persisted_dict(json.loads(Path(sys.argv[2]).read_text()))
runtime=JobRuntime(root/'jobs',clock=lambda:'2026-10-02T12:00:00Z');store=FileExecutionStore(Path(sys.argv[3]))
try:
 job=runtime.show(request.job_id)
 store.begin_decision(request,executor='independent-fresh-process',runtime=runtime,job=job)
 with certified_dispatch(store,request): require_dispatch(request)
except ValueError as e:
 print(json.dumps({'denied':True,'error':str(e)}));sys.exit(0)
print(json.dumps({'denied':False,'redispatched':True}));sys.exit(3)
'''

class IndependentAttacks(unittest.TestCase):
    def test_import_cannot_complete_or_dispatch(self):
        f=tc.TaskContractTests();f.setUp()
        try:
            job=f.runtime.create(f.payload());f.runtime.enqueue(job['job_id']);job=f.runtime.claim(claimed_by='r3')
            request=Worker._build_request(job,'r3-import',())
            result=ExecutionResult(execution_id=request.execution_id,job_id=request.job_id,status='succeeded',output_refs=(),summary='Imported observation',error=None,provider=None,started_at=f.runtime.clock(),completed_at=f.runtime.clock())
            f.executions.create(request,result)
            self.assertEqual(f.executions.load(request.execution_id).result.status,'succeeded')
            with self.assertRaises(ValueError): f.executions.load(request.execution_id,require_authority=True)
            with self.assertRaises(ValueError): f.runtime.record_execution_success(job['job_id'],[{'ref_type':'artifact','ref':'runtime-execution:'+request.execution_id}])
            with self.assertRaises(ValueError):
                with gov.certified_dispatch(f.executions,request): pass
            self.assertNotEqual(f.runtime.show(job['job_id'])['status'],'completed')
            OBSERVATIONS.append({'case':'observation-import','denied':True})
        finally:f.tearDown()

    def test_final_apply_combined_journal_and_effect_rollback(self):
        for stage in ('effect-controlled_write','dispatch-execute','intent','authority','approval'):
            with self.subTest(stage=stage):
                f=ac.ControlledWriteTests();f.setUp()
                try:
                    request=f.request();store,_,_=gov._DISPATCH.get()
                    intent=store._decision_pair(request.execution_id,'intent');source=intent['authority_source']
                    from runtime.progress.store import ProgressStore
                    journal=ProgressStore(Path(source['progress_store_root'])).path(source['logical_job_id'])
                    prior=journal.read_bytes()
                    def mutate(workspace):
                        (workspace/'src'/'existing.txt').write_text('r3-attack')
                        journal.write_bytes(prior)
                        if stage=='authority':
                            from runtime.core.task_contract import TaskContractStore
                            TaskContractStore(Path(source['task_store_root']),progress=None)._path(request.job_id,'witness').unlink()
                        elif stage=='approval':
                            from runtime.approvals.store import FileApprovalStore
                            approval_id=next(iter(intent['approval_received'])).split(':',1)[1]
                            FileApprovalStore(Path(source['approval_store_root']))._path(approval_id).unlink()
                        else:
                            for suffix in ('anchor','witness'):store._decision_path(request.execution_id,stage,suffix).unlink()
                    with self.assertRaises(ValueError):f.execute_controlled(ac.MutatingAdapter(mutate),request)
                    self.assertEqual((f.target/'src'/'existing.txt').read_text(),'before\n')
                    OBSERVATIONS.append({'case':'apply-journal-rollback-'+stage,'denied':True})
                finally:f.tearDown()

    def test_rollback_combined_identity_and_consumption_rebinding_fresh_process(self):
        for attack in ('journal-only','intent-delete','intent-foreign','intent-foreign-and-dispatch-rebind'):
            for alternate in (False,True):
                with self.subTest(attack=attack,alternate=alternate):
                    f=cg.CapabilityGovernanceTests();f.setUp()
                    try:
                        job,request=f.prepared();journal=f.runtime.progress.store.path(f.runtime.progress.logical_id(job));prior=journal.read_bytes()
                        f.begin(job,request)
                        with gov.certified_dispatch(f.store,request):gov.require_dispatch(request)
                        if attack=='intent-delete':
                            for suffix in ('anchor','witness'):f.store._decision_path(request.execution_id,'intent',suffix).unlink()
                        if attack.startswith('intent-foreign'):
                            value=f.store._decision_pair(request.execution_id,'intent')
                            value['request']['job_id']='r3-foreign';value['authority_source']['job_id']='r3-foreign'
                            pair(f.store,request.execution_id,'intent',value)
                            if attack.endswith('dispatch-rebind'):
                                pair(f.store,request.execution_id,'dispatch-execute',{'schema_version':1,'intent_digest':digest(value),'purpose':'execute'})
                        journal.write_bytes(prior)
                        data=request.to_dict();data['execution_id']='r3-replacement';path=f.root/'replacement.json';path.write_text(json.dumps(data))
                        owner=f.root/('alternate-executions' if alternate else 'executions')
                        result=subprocess.run([sys.executable,'-B','-c',CHILD,str(f.root),str(path),str(owner)],cwd=ROOT,capture_output=True,text=True)
                        observation={'case':'rollback-'+attack,'alternate':alternate,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
                        OBSERVATIONS.append(observation)
                        self.assertEqual(result.returncode,0,observation)
                    finally:f.tearDown()

    def test_git_import_and_review_dispatch_deletion_denied(self):
        for attack in ('execution-import','review-import','both-import','review-dispatch-delete','effect-delete'):
            with self.subTest(attack=attack):
                f=gt.GitRuntimeTests();f.setUp()
                try:
                    prepared=f.prepare();identity=f.approve(prepared);job=f.jobs.show(f.job_id)
                    if attack in ('execution-import','both-import'):
                        trace=f.executions._decision_pair(f.execution_id,'result');trace['intent_digest']=None;pair(f.executions,f.execution_id,'result',trace)
                    if attack in ('review-import','both-import'):
                        rid=next(r['ref'].split(':',1)[1] for r in job['output_refs'] if r['ref'].startswith('runtime-review:'))
                        store=f.reviews._decisions();trace=store._decision_pair(rid,'review-result');trace['intent_digest']=None;pair(store,rid,'review-result',trace)
                    if attack in ('review-dispatch-delete','effect-delete'):
                        stage='dispatch-review' if attack.startswith('review') else 'effect-controlled_write'
                        for suffix in ('anchor','witness'):f.executions._decision_path(f.execution_id,stage,suffix).unlink()
                    with self.assertRaises(ValueError):f.runtime.commit(identity)
                    self.assertEqual(f.git('rev-parse','HEAD').stdout.strip(),f.base_head)
                    OBSERVATIONS.append({'case':'git-'+attack,'denied':True})
                finally:f.tearDown()

    def test_child_ceiling_combined_substitution(self):
        for field,value in (('project_id','foreign'),('attempt',2),('execution_id','foreign'),('input_refs',[{'ref_type':'artifact','ref':'foreign'}])):
            with self.subTest(field=field):
                f=cg.CapabilityGovernanceTests();f.setUp()
                try:
                    job,request=f.prepared();f.begin(job,request)
                    data=request.to_dict();data[field]=value;changed=ExecutionRequest.from_persisted_dict(data)
                    with gov.certified_dispatch(f.store,request,purpose='review'):
                        with self.assertRaises(ValueError):gov.require_dispatch(changed)
                    OBSERVATIONS.append({'case':'review-parent-substitution-'+field,'denied':True})
                finally:f.tearDown()

    def test_git_policy_pair_loss_between_admission_and_effect(self):
        from runtime.core.capability_actions import ActionDecision
        f=gt.GitRuntimeTests();f.setUp()
        try:
            prepared=f.prepare();identity=f.approve(prepared)
            original=ActionDecision.consume
            def lost_policy(audit):
                for suffix in ('anchor','witness'):
                    audit.store._decision_path(audit.identity,'action-policy',suffix).unlink()
                return original(audit)
            denied=False;error=None
            with patch.object(ActionDecision,'consume',lost_policy):
                try:f.runtime.commit(identity)
                except ValueError as exc:denied=True;error=str(exc)
            changed=f.git('rev-parse','HEAD').stdout.strip()!=f.base_head
            OBSERVATIONS.append({'case':'git-action-policy-loss-at-consume','denied':denied,'error':error,'commit_created':changed})
            self.assertTrue(denied,'Git action completed with missing pre-effect policy pair')
            self.assertFalse(changed,'Git commit mutated after action-policy trace disappeared')
        finally:f.tearDown()

if __name__=='__main__':
    try:unittest.main()
    finally:(Path(__file__).resolve().parent/'adversarial-observations.json').write_text(json.dumps(OBSERVATIONS,indent=2)+'\n')
