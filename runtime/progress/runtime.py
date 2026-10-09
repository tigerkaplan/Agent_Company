"""Trusted observations only. Nothing in this module changes operational state."""

from contextlib import contextmanager
from contextvars import ContextVar

from runtime.progress.models import ProgressError, ProgressEvent, digest
from runtime.storage.file_store import FileJobStore, JobStoreError
from runtime.progress.store import ProgressStore


class ProgressRuntime:
    def __init__(self, root):
        self.store = ProgressStore(root)

    @staticmethod
    def logical_id(job):
        return (job.get("continuation") or job.get("retry_policy") or {}).get("logical_job_id", job["job_id"])

    def transition_lock(self, *, timeout_seconds=5.0):
        return FileJobStore(self.store.root / ".transitions").claim_transaction(timeout_seconds=timeout_seconds)

    @contextmanager
    def recovery_lock(self):
        try:
            with FileJobStore(self.store.root / ".recoveries").claim_transaction():
                yield
        except JobStoreError as error:
            raise ProgressError("Recovery coordination failed") from error

    def event(self, job, event_type, *, execution_id=None, step_id=None, detail="none", evidence_id=None):
        checkpoint = job.get("continuation") or {}
        return ProgressEvent(
            event_type, self.logical_id(job), job["job_id"], execution_id,
            step_id if step_id is not None else checkpoint.get("current_step_id"),
            detail, evidence_id,
        )

    def emit(self, job, event_type, **fields):
        return self.store.append(self.event(job, event_type, **fields))

    def observe_job(self, job):
        """Caller holds transition_lock and supplies freshly validated canonical state."""
        self.store.resolve(self.logical_id(job), job["job_id"], digest(job), self.transition_events(job))
        self.store.append_many(self.job_events(job))
        self.store.deliver_recovery(self.logical_id(job), job["job_id"])

    def begin_recovery(self, job, execution_id):
        self.store.begin_recovery(self.event(job, "recovery_completed", execution_id=execution_id, detail="worker_error"))

    def finish_recovery(self, job, outcome):
        event = self.event(job, "recovery_completed", execution_id=outcome.execution_id, detail=outcome.status)
        self.store.finish_recovery(event)
        self.emit(job, "recovery_completed", execution_id=outcome.execution_id, detail=outcome.status)

    def reconcile_recovery(self, job):
        """Caller holds recovery_lock: any unfinished prior attempt was interrupted."""
        record = self.store.recovery_record(self.logical_id(job), job["job_id"])
        if record is not None and not record[0]:
            # No returned outcome survived. Record the interrupted recovery as an
            # error, never infer success or an exit by the original worker.
            self.store.finish_recovery(record[1])
        self.store.deliver_recovery(self.logical_id(job), job["job_id"])

    def transition_events(self, job):
        return [self.event(job, "transition_requested", detail=job["status"]), *self.job_events(job)]

    def reserve_transition(self, previous, job):
        self.store.reserve(self.logical_id(job), job["job_id"], digest(previous), digest(job), self.transition_events(job))

    def job_events(self, job):
        events = []
        def emit(job, event_type, **fields):
            events.append(self.event(job, event_type, **fields))
        status = job["status"]
        checkpoint = job.get("continuation") or {}
        execution_id = None
        for reference in job.get("output_refs", []):
            if reference.get("ref", "").startswith("runtime-execution:"):
                execution_id = reference["ref"].split(":", 1)[1]
        # State observations deliberately do not include timestamps, heartbeat,
        # prose, or provider output. Replaying the same boundary is a no-op.
        emit(job, "job_state_observed", detail=status)
        if status == "running":
            emit(job, "job_started")
        if status in {"reviewing", "waiting_approval"}:
            emit(job, "gate_waiting", execution_id=execution_id,
                      detail="review" if status == "reviewing" else "human")
        if status == "failed":
            code = (job.get("error") or {}).get("code", "")
            failure_class = (job.get("error") or {}).get("failure_class")
            if code.startswith("execution_budget") or failure_class == "budget_failure":
                emit(job, "gate_failed", execution_id=execution_id, detail="budget")
            elif code == "approval_rejected":
                emit(job, "gate_failed", execution_id=execution_id, detail="human")
            elif code in {"review_failed", "review_retry_requested", "review_retry_exhausted"}:
                emit(job, "gate_failed", execution_id=execution_id, detail="review")
            elif failure_class in {"review_repair", "authority_failure", "policy_failure"}:
                emit(job, "gate_failed", execution_id=execution_id,
                          detail="review" if failure_class == "review_repair" else "authority")
            emit(job, "job_failed", execution_id=execution_id)
        if status == "cancelled":
            emit(job, "job_cancelled", execution_id=execution_id)
        if status == "completed":
            if checkpoint and checkpoint["current_step_id"] in checkpoint["completed_step_ids"]:
                emit(job, "step_completed", execution_id=execution_id)
            if not checkpoint or (checkpoint["state"] == "terminal" and not checkpoint["remaining_step_ids"]):
                emit(job, "job_completed", execution_id=execution_id)
        if job.get("continuation_parent_job_id"):
            emit(job, "continuation_reserved", evidence_id=job["continuation_parent_job_id"])
        return events

    def observe_retry(self, job, decision):
        kind = {"RETRY": "retry_requested", "REPLAN_REQUIRED": "replan_requested",
                "STOP": "stop_requested", "NEEDS_HUMAN": "gate_waiting", "ERROR": "gate_failed"}[decision.decision]
        self.emit(job, kind, evidence_id=decision.decision_id,
                  detail={"RETRY": "retry", "REPLAN_REQUIRED": "replan", "STOP": "stop",
                          "NEEDS_HUMAN": "human", "ERROR": "error"}[decision.decision])

    def execution_started(self, job, execution_id):
        self.emit(job, "execution_started", execution_id=execution_id)
        if job.get("continuation"):
            self.emit(job, "step_started", execution_id=execution_id)
        if job.get("retry_authorization"):
            self.emit(job, "repair_started", execution_id=execution_id,
                      evidence_id=job["retry_authorization"]["decision_id"])

    def observe_execution(self, job, result):
        # Result returned != successful logical completion or Reviewer completion.
        kind = ("execution_failed" if result.status == "failed" else
                "execution_completed" if result.status == "succeeded" else "execution_exited")
        self.emit(job, kind, execution_id=result.execution_id, detail=result.status)


_OBSERVER = ContextVar("runtime_progress_observer", default=None)


@contextmanager
def execution_observer(progress, job, execution_id):
    token = _OBSERVER.set((progress, job, execution_id))
    try:
        yield
    finally:
        _OBSERVER.reset(token)


@contextmanager
def tool_observation(tool_id):
    """Instrument an actual host call, never a provider-reported tool trace."""
    observer = _OBSERVER.get()
    if observer is None:
        yield
        return
    progress, job, execution_id = observer
    progress.emit(job, "tool_started", execution_id=execution_id, detail=tool_id)
    try:
        yield
    except BaseException:
        progress.emit(job, "tool_failed", execution_id=execution_id, detail=tool_id)
        raise
    else:
        progress.emit(job, "tool_completed", execution_id=execution_id, detail=tool_id)
