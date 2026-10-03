"""Confirm combined rollback performs actual LocalExecutor redispatch."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
import adversarial as attacks
from runtime.core import capability_governance as gov
from runtime.core.task_contract import digest
from runtime.executors.local import LocalExecutor
from runtime.tests.test_capability_governance import CapabilityGovernanceTests

observations=[]
for alternate in (False,True):
    f=CapabilityGovernanceTests();f.setUp()
    try:
        job,request=f.prepared()
        journal=f.runtime.progress.store.path(f.runtime.progress.logical_id(job));prior=journal.read_bytes()
        authority_files=list(f.runtime.task_contract_store.root.glob('*.json'))+list(f.runtime.store.root.glob('*.json'))
        def fingerprints():return {str(p.relative_to(f.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in authority_files}
        before=fingerprints()
        f.begin(job,request)
        with gov.certified_dispatch(f.store,request):first=LocalExecutor().execute(request)
        value=f.store._decision_pair(request.execution_id,'intent')
        value['request']['job_id']='r3-foreign';value['authority_source']['job_id']='r3-foreign'
        attacks.pair(f.store,request.execution_id,'intent',value)
        attacks.pair(f.store,request.execution_id,'dispatch-execute',{'schema_version':1,'intent_digest':digest(value),'purpose':'execute'})
        journal.write_bytes(prior)
        data=request.to_dict();data['execution_id']='r3-actual-redispatch';path=f.root/'replacement.json';path.write_text(json.dumps(data))
        child=attacks.CHILD.replace('with certified_dispatch(store,request): require_dispatch(request)',
            'from runtime.executors.local import LocalExecutor\n with certified_dispatch(store,request): result=LocalExecutor().execute(request)')
        child=child.replace("'redispatched':True", "'redispatched':True,'result_status':result.status,'execution_id':result.execution_id")
        owner=f.root/('alternate-executions' if alternate else 'executions')
        result=subprocess.run([sys.executable,'-B','-c',child,str(f.root),str(path),str(owner)],cwd=ROOT,capture_output=True,text=True)
        observations.append(dict(alternate=alternate,first_status=first.status,returncode=result.returncode,
            stdout=result.stdout,stderr=result.stderr,authority_and_job_files_unchanged=before==fingerprints(),
            same_job=data['job_id']==request.job_id,same_attempt=data['attempt']==request.attempt,
            approval_received=value['approval_received'],authority_fingerprints=before))
    finally:f.tearDown()
out=Path(__file__).resolve().parent/'rollback-confirmation-observations.json'
out.write_text(json.dumps(observations,indent=2)+'\n')
print(json.dumps(observations,indent=2))
sys.exit(1 if any(o['returncode']==3 for o in observations) else 0)
