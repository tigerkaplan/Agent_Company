"""Fresh import-to-human/completion checks, using canonical runtime APIs."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.execution.models import ExecutionResult
from runtime.workers.worker import Worker
from runtime.tests.test_task_contract import TaskContractTests

OBSERVATIONS=[]

class ImportBoundaries(unittest.TestCase):
    def test_import_cannot_request_canonical_human_resumption(self):
        f=TaskContractTests();f.setUp()
        try:
            job=f.runtime.create(f.payload());f.runtime.enqueue(job['job_id']);job=f.runtime.claim(claimed_by='r4')
            request=Worker._build_request(job,'r4-human-import',())
            result=ExecutionResult(execution_id=request.execution_id,job_id=request.job_id,status='needs_human',
                output_refs=(),summary='Imported observation',error=None,provider=None,
                started_at=f.runtime.clock(),completed_at=f.runtime.clock())
            f.executions.create(request,result)
            self.assertEqual(f.executions.load(request.execution_id).result.status,'needs_human')
            approvals=ApprovalRuntime(f.runtime,FileApprovalStore(f.root/'approvals'),execution_store=f.executions)
            ref={'ref_type':'artifact','ref':'runtime-execution:'+request.execution_id}
            with self.assertRaises(ValueError):
                approvals.request_human_condition(job['job_id'],request.execution_id,
                    reason='Imported observation must not produce canonical resumption authority',execution_ref=ref,output_refs=[ref])
            self.assertEqual(f.runtime.show(job['job_id'])['status'],'running')
            OBSERVATIONS.append(dict(case='import-to-human-resumption',observation_readable=True,authority_denied=True))
        finally:f.tearDown()

    def test_import_cannot_complete_after_fresh_runtime_restart(self):
        f=TaskContractTests();f.setUp()
        try:
            job=f.runtime.create(f.payload());f.runtime.enqueue(job['job_id']);job=f.runtime.claim(claimed_by='r4')
            request=Worker._build_request(job,'r4-success-import',())
            result=ExecutionResult(execution_id=request.execution_id,job_id=request.job_id,status='succeeded',
                output_refs=(),summary='Imported observation',error=None,provider=None,
                started_at=f.runtime.clock(),completed_at=f.runtime.clock())
            f.executions.create(request,result)
            from runtime.core.jobs import JobRuntime
            from runtime.storage.execution_store import FileExecutionStore
            restarted=JobRuntime(f.root/'jobs',clock=f.runtime.clock)
            restarted.execution_store=FileExecutionStore(f.executions.root)
            ref={'ref_type':'artifact','ref':'runtime-execution:'+request.execution_id}
            with self.assertRaises(ValueError):restarted.record_execution_success(job['job_id'],[ref])
            self.assertNotEqual(restarted.show(job['job_id'])['status'],'completed')
            OBSERVATIONS.append(dict(case='import-to-completion-after-runtime-restart',authority_denied=True))
        finally:f.tearDown()

if __name__=='__main__':
    try:unittest.main()
    finally:(Path(__file__).resolve().parent/'import-observations.json').write_text(json.dumps(OBSERVATIONS,indent=2)+'\n')
