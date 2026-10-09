"""Small deterministic reference operations behind canonical Worker admission."""
from copy import deepcopy

from runtime.core.task_contract import digest, require_tool
from runtime.execution.models import ExecutionResult
from runtime.graph.models import DETERMINISTIC_KINDS, GraphError
from runtime.graph.runtime import validate_graph_job


class DeterministicGraphExecutor:
    supported_execution_modes = frozenset({"READ_ONLY"})

    def __init__(self, jobs):
        self.jobs = jobs

    def execute(self, request):
        require_tool(request, "local_executor")
        job = self.jobs.show(request.job_id)
        validate_graph_job(self.jobs, job, executing=True)
        root = self.jobs.show(job["graph_binding"]["root_job_id"])
        node = next(n for n in root["graph_plan"]["nodes"] if n["node_id"] == job["graph_binding"]["node_id"])
        if node["kind"] not in DETERMINISTIC_KINDS:
            raise GraphError("Provider node cannot use deterministic graph operations")
        refs = deepcopy(job["input_refs"])
        operation = node["operation"]
        if operation in {"deduplicate", "sort"}:
            refs = list({digest(ref): ref for ref in refs}.values())
        if operation == "sort":
            refs.sort(key=lambda ref: (ref["ref_type"], ref["ref"]))
        if operation == "verify":
            for ref in refs:
                if ref["ref"].startswith("runtime-execution:"):
                    self.jobs.execution_store.load(ref["ref"].split(":", 1)[1], require_authority=True)
        summary = "Deterministic graph reference " + operation + ": " + digest(refs)
        return ExecutionResult(execution_id=request.execution_id, job_id=request.job_id,
            status="succeeded", summary=summary, error=None, output_refs=tuple(refs),
            evidence=({"kind": "deterministic_check", "status": "passed", "summary": summary},),
            provider=None, started_at=self.jobs.clock(), completed_at=self.jobs.clock(),
            execution_mode="READ_ONLY", dry_run=request.dry_run)
