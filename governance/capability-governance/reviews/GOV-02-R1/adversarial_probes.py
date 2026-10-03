"""Review probes only: isolated temporary state, no implementation changes."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from runtime.tests.test_task_contract import TaskContractTests
from runtime.tests.test_actions import ControlledWriteTests,MutatingAdapter
from runtime.workers.worker import Worker
from runtime.execution.models import ExecutionResult
from runtime.core import capability_governance as gov

results=[]
f=TaskContractTests();f.setUp()
try:
 job=f.runtime.create(f.payload());f.runtime.enqueue(job['job_id']);job=f.runtime.claim(claimed_by='review-probe')
 request=Worker._build_request(job,'r1-imported-without-dispatch',())
 result=ExecutionResult(execution_id=request.execution_id,job_id=request.job_id,status='succeeded',output_refs=(),summary='Imported observation without actual execution',error=None,provider=None,started_at='2026-10-02T12:00:00Z',completed_at='2026-10-02T12:00:00Z')
 f.executions.create(request,result)
 trace=f.executions._decision_pair(request.execution_id,'result')
 ref={'ref_type':'artifact','ref':'runtime-execution:'+request.execution_id}
 f.runtime.execution_store=f.executions
 status=f.runtime.record_execution_success(job['job_id'],[ref])['status']
 if status!='completed':status=f.runtime.complete(job['job_id'])['status']
 results.append({'probe':'imported_execution_without_intent','intent_digest':trace['intent_digest'],'actual_job_status':status,'worker_executor_called':False})
except Exception as e:results.append({'probe':'imported_execution_without_intent','denied':type(e).__name__,'message':str(e)})
finally:f.tearDown()

f=ControlledWriteTests();f.setUp()
try:
 request=f.request();store,parent,purpose=gov._DISPATCH.get()
 def mutate(workspace):
  (workspace/'src'/'existing.txt').write_text('r1-staged-change')
  for suffix in ('anchor','witness'):store._decision_path(request.execution_id,'effect-controlled_write',suffix).unlink()
 outcome=f.execute_controlled(MutatingAdapter(mutate),request)
 results.append({'probe':'delete_effect_trace_before_apply','provider_status':outcome.provider_result.status,'target_contents':(f.target/'src'/'existing.txt').read_text(),'effect_pair_missing':not store._decision_path(request.execution_id,'effect-controlled_write','anchor').exists()})
except Exception as e:results.append({'probe':'delete_effect_trace_before_apply','denied':type(e).__name__,'message':str(e)})
finally:f.tearDown()

from runtime.tests.test_git import GitRuntimeTests
f=GitRuntimeTests();f.setUp()
try:
 job=f.jobs.show(f.job_id)
 record=f.executions.load(f.execution_id)
 execution_trace=f.executions._decision_pair(f.execution_id,'result')
 review_ref=next(r['ref'] for r in job['output_refs'] if r['ref'].startswith('runtime-review:'))
 review_id=review_ref.split(':',1)[1]
 review_trace=f.reviews._decisions()._decision_pair(review_id,'review-result')
 prepared=f.prepare();identity=f.approve(prepared);commit=f.runtime.commit(identity)
 results.append({'probe':'unobserved_review_to_completed_job_to_git_action','job_status':job['status'],'execution_has_intent':execution_trace['intent_digest'] is not None,'review_intent_digest':review_trace['intent_digest'],'actual_reviewer_dispatch':False,'commit_created':f.git('rev-parse','HEAD').stdout.strip()!=f.base_head})
except Exception as e:results.append({'probe':'unobserved_review_to_completed_job_to_git_action','denied':type(e).__name__,'message':str(e)})
finally:f.tearDown()
from runtime.tests.test_capability_governance import CapabilityGovernanceTests
from runtime.execution.models import ExecutionRequest
f=CapabilityGovernanceTests();f.setUp()
try:
 job,request=f.prepared()
 journal=f.runtime.progress.store.path(f.runtime.progress.logical_id(job))
 prior=journal.read_bytes()
 f.begin(job,request)
 with gov.certified_dispatch(f.store,request):f.fixture.worker.executor.execute(request)
 original_pair=f.store._decision_path(request.execution_id,'intent','anchor').read_bytes()
 journal.write_bytes(prior)
 data=request.to_dict();data['execution_id']='r1-new-id-after-single-journal-rollback'
 replacement=ExecutionRequest.from_persisted_dict(data)
 import subprocess
 request_file=f.root/'replacement-request.json';request_file.write_text(json.dumps(data))
 child=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('rollback_restart_probe.py')),str(f.root),str(request_file)],capture_output=True,text=True,check=True)
 child_result=json.loads(child.stdout)
 results.append({'probe':'single_journal_rollback_new_execution_id','second_dispatch_accepted':child_result['second_dispatch_accepted'],'fresh_python_process':child_result['fresh_python_process'],'same_job':replacement.job_id==request.job_id,'same_attempt':replacement.attempt==request.attempt,'original_intent_pair_unchanged':f.store._decision_path(request.execution_id,'intent','anchor').read_bytes()==original_pair,'authority_or_approval_replacement':False})
except Exception as e:results.append({'probe':'single_journal_rollback_new_execution_id','denied':type(e).__name__,'message':str(e)})
finally:f.tearDown()
print(json.dumps(results,indent=2))
Path(__file__).with_name('adversarial-results.json').write_text(json.dumps(results,indent=2)+'\n')
