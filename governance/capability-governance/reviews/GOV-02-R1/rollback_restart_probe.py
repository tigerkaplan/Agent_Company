"""Fresh-process half of the single-journal rollback probe."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from runtime.core.jobs import JobRuntime
from runtime.execution.models import ExecutionRequest
from runtime.storage.execution_store import FileExecutionStore
from runtime.core.capability_governance import certified_dispatch
from runtime.executors.local import LocalExecutor
root=Path(sys.argv[1]);request=ExecutionRequest.from_persisted_dict(json.loads(Path(sys.argv[2]).read_text()))
runtime=JobRuntime(root/'jobs',clock=lambda:'2026-10-02T12:00:00Z');store=FileExecutionStore(root/'executions')
job=runtime.show(request.job_id)
store.begin_decision(request,executor='fresh-process-review-probe',runtime=runtime,job=job)
with certified_dispatch(store,request):LocalExecutor().execute(request)
print(json.dumps({'second_dispatch_accepted':True,'fresh_python_process':True}))
