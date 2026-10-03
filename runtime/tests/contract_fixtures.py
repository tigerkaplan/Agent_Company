"""Explicit acceptance for existing deterministic runtime test fixtures.

These tests certify lifecycle/result integrity, not business task completion.
Production default_contract deliberately leaves acceptance unresolved.
"""
from copy import deepcopy
from contextlib import contextmanager
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
    store.begin_decision(result.review_id, job, request, execution, "reviewer")
    ref = store.create(package, result, "", execution_request=request.to_dict())
    return ReviewRun(result, ref)


def persist_execution_fixture(runtime, job, execution_id):
    from runtime.storage.execution_store import FileExecutionStore
    from runtime.workers.worker import Worker
    from runtime.executors.local import LocalExecutor
    store = runtime.execution_store or FileExecutionStore(runtime.store.root.parent / "executions")
    runtime.execution_store = store
    request = Worker._build_request(job, execution_id, ())
    with certified_fixture_dispatch(request, runtime=runtime, store=store):
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

    def execute(self, request, context, **kwargs):
        with certified_fixture_dispatch(request):
            return super().execute(request, context, **kwargs)


@contextmanager
def certified_fixture_dispatch(request, *, runtime=None, store=None, purpose="execute"):
    """Explicit test-only admission/human decisions; production never uses it."""
    from runtime.core import capability_governance as gov
    if gov._DISPATCH.get() is not None:
        yield
        return
    import tempfile
    from pathlib import Path
    from runtime.core.jobs import JobRuntime
    from runtime.approvals.runtime import ApprovalRuntime
    from runtime.approvals.store import FileApprovalStore
    from runtime.storage.execution_store import FileExecutionStore
    with tempfile.TemporaryDirectory() as temporary:
        if runtime is None:
            data = request.to_dict()
            if data["task_contract"] is None:
                yield  # Deliberately malformed requests still hit the real guard.
                return
            root = Path(temporary)
            runtime = JobRuntime(root / "jobs", id_factory=lambda: request.job_id)
            payload = {k: data[k] for k in ("task", "task_class", "project_id", "agent", "skill", "workflow",
                "capability", "provider", "risk_level", "review_required", "input_refs", "execution_mode",
                "execution_scope", "dry_run", "task_contract") if data[k] is not None}
            payload.update(created_by="explicit-human-test-fixture", max_attempts=max(3, request.attempt),
                approval_status="required" if data["task_contract"]["approval_requirements"]["execution"] else "not_required")
            if data["task_contract"]["budget_references"] is not None:
                payload["execution_budget"] = data["task_contract"]["budget_references"]
            try:
                job = runtime.create(payload)
                if request.approval_status == "approved":
                    approvals = ApprovalRuntime(runtime, FileApprovalStore(root / "approvals"))
                    pending = approvals.request_execution(job["job_id"], reason="Explicit deterministic test authority")
                    job = approvals.resolve(pending.request.approval_id, decision="APPROVED", decided_by="fixture-owner")["job"]
                if job["status"] == "created": runtime.enqueue(job["job_id"])
                job = runtime.claim(claimed_by="explicit-test-worker")
            except ValueError:
                yield  # Invalid declarations never receive a dispatch context.
                return
        else:
            job = runtime.show(request.job_id)
        store = store or FileExecutionStore(runtime.store.root.parent / "fixture-decisions")
        paths = [store._decision_path(request.execution_id, "intent", s) for s in ("anchor", "witness")]
        if job.get("execution_budget") is not None and not any(p.exists() for p in paths):
            from runtime.budget.runtime import ExecutionBudgetRuntime
            outcome = ExecutionBudgetRuntime(runtime.budget_store, wall_clock=runtime.clock).reserve_execution(
                job["execution_budget"], execution_id=request.execution_id, job_id=job["job_id"])
            if outcome.status != "ALLOW": raise AssertionError(outcome.reason)
        if any(p.exists() for p in paths):
            store._verify_intent(store._decision_pair(request.execution_id, "intent"))
        else:
            store.begin_decision(request, executor="explicit-deterministic-test-fixture", runtime=runtime, job=job)
        with gov.certified_dispatch(store, request, purpose=purpose):
            yield


from runtime.providers.executor import ProviderExecutor as _ProviderExecutor
from runtime.review.reviewers import ProviderBackedReviewer as _ProviderBackedReviewer


class CertifiedProviderFixture(_ProviderExecutor):
    def execute(self, request, **kwargs):
        with certified_fixture_dispatch(request):
            return super().execute(request, **kwargs)


class CertifiedReviewerFixture(_ProviderBackedReviewer):
    def review(self, package):
        from runtime.workers.worker import Worker
        if "task_contract" not in package.job:
            return super().review(package)  # Policy-only probes cannot call tools.
        request = Worker._build_request(package.job, package.execution["execution_id"], ())
        with certified_fixture_dispatch(request, purpose="review"):
            return super().review(package)


from runtime.review.runtime import ReviewerRuntime as _ReviewerRuntime


class CertifiedReviewRuntimeFixture(_ReviewerRuntime):
    def __init__(self, *args, fixture_runtime=None, **kwargs):
        self.fixture_runtime = fixture_runtime
        super().__init__(*args, **kwargs)

    def run(self, job, request, execution_result, **kwargs):
        with certified_fixture_dispatch(request, runtime=self.fixture_runtime,
                                        store=self.verifier.execution_store, purpose="review"):
            return super().run(job, request, execution_result, **kwargs)
