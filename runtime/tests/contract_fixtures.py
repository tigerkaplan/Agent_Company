"""Explicit acceptance for existing deterministic runtime test fixtures.

These tests certify lifecycle/result integrity, not business task completion.
Production default_contract deliberately leaves acceptance unresolved.
"""
from copy import deepcopy
from runtime.core.task_contract import default_contract


def declare_fixture_contract(payload):
    value = deepcopy(payload)
    if not isinstance(value, dict) or not {"task", "capability", "risk_level", "review_required"} <= set(value):
        return value
    if "task_contract" not in value:
        job = {"execution_mode": "READ_ONLY", "execution_scope": None,
               "input_refs": [], "approval_status": "not_required", **value}
        try:
            value["task_contract"] = default_contract(job)
            value["task_contract"]["inputs"] = list(job["input_refs"])
            value["task_contract"]["acceptance_criteria"] = [{
                "criterion_id": "fixture_integrity", "description":
                "Validate the deterministic runtime fixture, canonical result integrity and absence of blockers",
                "check_ids": ["result_contract", "no_blockers"]}]
        except (KeyError, TypeError, AttributeError):
            pass  # Deliberately malformed fixtures remain malformed.
    return value


def persist_fixture_review(store, job, request, execution, run):
    from dataclasses import replace
    from runtime.review.models import DeterministicCheck, VerificationResult, ReviewPackage, ReviewRun
    check = DeterministicCheck("fixture_execution", "PASS", "Persisted deterministic fixture verified",
        ({"ref_type": "artifact", "ref": "runtime-execution:" + execution.execution_id},))
    result = replace(run.result, deterministic_checks=(check.to_dict(),), created_at=execution.completed_at)
    package = ReviewPackage(result.review_id, job, execution.to_dict(),
                            VerificationResult("PASS", (check,)), (), ())
    ref = store.create(package, result, "", execution_request=request.to_dict())
    return ReviewRun(result, ref)


def persist_execution_fixture(runtime, job, execution_id):
    from runtime.storage.execution_store import FileExecutionStore
    from runtime.workers.worker import Worker
    from runtime.executors.local import LocalExecutor
    store = runtime.execution_store or FileExecutionStore(runtime.store.root.parent / "executions")
    runtime.execution_store = store
    request = Worker._build_request(job, execution_id, ())
    result = LocalExecutor().execute(request)
    store.create(request, result)
    return {"ref_type": "artifact", "ref": "runtime-execution:" + execution_id,
            "description": "Persisted deterministic fixture"}


def execute_fixture(runtime, job):
    ref = persist_execution_fixture(runtime, job, "fixture-" + job["job_id"])
    return runtime.record_execution_success(job["job_id"], [ref])


from runtime.providers.adapters import CliProviderAdapter


class ToolFreeCliFixture(CliProviderAdapter):
    """All runners in adapter unit tests return canned data; no native tools."""
    native_tools = frozenset()
