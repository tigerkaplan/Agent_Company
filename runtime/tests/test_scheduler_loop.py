from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.approvals.factory import build_approval_runtime
from runtime.continuation.models import ContinuationPolicy
from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.executors.local import LocalExecutor
from runtime.scheduler.dispatch import CanonicalDispatchAdapter
from runtime.scheduler.loop import SchedulerConfig, SchedulerLoop, SchedulerLoopError
from runtime.scheduler.schedules import ScheduleRuntime
from runtime.storage.execution_store import FileExecutionStore
from runtime.storage.scheduler_state_store import FileSchedulerStateStore
from runtime.workers.worker import Worker


RUNTIME_REPOSITORY = Path(__file__).resolve().parents[2]


class MutableClock:
    def __init__(self, value: str = "2026-03-01T12:00:00Z") -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value

    def advance(self, seconds: int) -> None:
        parsed = datetime.fromisoformat(self.value.replace("Z", "+00:00"))
        self.value = (parsed + timedelta(seconds=seconds)).astimezone(
            timezone.utc
        ).isoformat().replace("+00:00", "Z")


class SequenceIds:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"{self.prefix}-{self.value:04d}"


class RaisingWorker(Worker):
    def run_claimed(self, job_id: str):
        raise ValueError("untrusted internal detail")


class SchedulerLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = MutableClock()
        self.jobs = JobRuntime(
            self.root / "jobs",
            clock=self.clock,
            id_factory=SequenceIds("job"),
        )
        self.executions = FileExecutionStore(self.root / "executions")
        self.approvals = build_approval_runtime(
            self.jobs,
            self.root / "approvals",
            execution_store=self.executions,
        )
        self.schedules = ScheduleRuntime(
            self.root / "schedules",
            clock=self.clock,
            id_factory=SequenceIds("schedule"),
        )
        self.dispatcher = CanonicalDispatchAdapter(
            self.jobs,
            RUNTIME_REPOSITORY,
            self.approvals,
        )
        self.executor = LocalExecutor("success", clock=self.clock)
        self.worker = Worker(
            self.jobs,
            CanonicalReferenceResolver(RUNTIME_REPOSITORY),
            self.executor,
            self.executions,
            approval_runtime=self.approvals,
            clock=self.clock,
            id_factory=SequenceIds("execution"),
            worker_id="worker-phase-6m",
            lease_seconds=30,
        )
        self.state_store = FileSchedulerStateStore(self.root / "scheduler-runtime")
        self.loop = self.make_loop()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_loop(
        self,
        *,
        worker: Worker | None = None,
        counts_as_provider_run: bool = False,
        **config: object,
    ) -> SchedulerLoop:
        values = {
            "poll_interval_seconds": 0.01,
            "max_jobs_per_cycle": 1,
            "max_concurrent_jobs": 1,
            "max_provider_runs_per_cycle": 1,
            "max_provider_runs_per_day": 25,
            "lease_seconds": 30,
            "heartbeat_interval_seconds": 1.0,
            "retry_backoff_seconds": (10, 30, 60),
        }
        values.update(config)
        return SchedulerLoop(
            self.schedules,
            self.dispatcher,
            self.jobs,
            worker or self.worker,
            self.approvals,
            self.state_store,
            config=SchedulerConfig(**values),
            counts_as_provider_run=counts_as_provider_run,
            clock=self.clock,
            id_factory=SequenceIds("loop"),
        )

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Run bounded local scheduler fixture",
            "task_class": "operations",
            "agent": "operations",
            "workflow": "operations",
            "capability": "operations_coordination",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": False,
            "max_attempts": 3,
            "input_refs": [],
            "output_refs": [],
            "created_by": "phase-6m-test",
        }
        value.update(overrides)
        return value

    def enqueue(self, **overrides: object) -> dict[str, object]:
        job = self.jobs.create(self.payload(**overrides))
        return self.jobs.enqueue(job["job_id"])

    def schedule_payload(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "name": "Phase 6M recurring fixture",
            "enabled": True,
            "schedule_type": "recurring",
            "task": "Prepare a bounded operations report",
            "task_class": "operations",
            "recurrence": "hourly",
            "next_run_at": "2026-03-01T09:00:00Z",
            "created_by": "human-owner",
            "input_refs": [],
        }
        value.update(overrides)
        return value

    def test_a_queued_job_is_eligible_and_executes(self) -> None:
        queued = self.enqueue()
        self.assertEqual([item["job_id"] for item in self.jobs.eligible()], [queued["job_id"]])
        result = self.loop.run_once()
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(self.jobs.show(queued["job_id"])["status"], "completed")

    def test_b_future_job_is_not_eligible(self) -> None:
        job = self.jobs.create(self.payload())
        future = self.jobs.schedule(job["job_id"], "2026-03-01T13:00:00Z")
        self.assertEqual(future["status"], "queued")
        self.assertEqual(self.jobs.eligible(), [])
        self.assertEqual(self.loop.run_once()["processed_count"], 0)

    def test_c_due_scheduled_job_is_eligible(self) -> None:
        job = self.jobs.create(self.payload())
        self.jobs.schedule(job["job_id"], "2026-03-01T11:59:00Z")
        self.assertEqual(len(self.jobs.eligible()), 1)

    def test_d_waiting_approval_is_skipped_and_visible(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        waiting = self.approvals.request_execution(job["job_id"], reason="Test boundary").job
        self.assertEqual(waiting["status"], "waiting_approval")
        snapshot = self.loop.run_once(dry_run=True)
        self.assertIn(job["job_id"], snapshot["waiting_approvals"])
        self.assertEqual(self.executor.last_request, None)

    def test_e_terminal_jobs_are_skipped(self) -> None:
        completed = self.enqueue()
        self.worker.run_once()
        cancelled = self.jobs.create(self.payload(task="cancelled"))
        self.jobs.transition(cancelled["job_id"], "cancelled")
        self.assertEqual(self.jobs.eligible(), [])
        self.assertEqual(self.loop.run_once()["processed_count"], 0)
        self.assertEqual(self.jobs.show(completed["job_id"])["status"], "completed")

    def test_f_retry_backoff_blocks_then_becomes_due(self) -> None:
        queued = self.enqueue()
        running = self.jobs.claim(claimed_by="manual", lease_seconds=30)
        failed = self.jobs.fail(running["job_id"], retryable=True)
        retry = self.jobs.retry(
            failed["job_id"], next_run_at="2026-03-01T12:00:10Z", enqueue=True
        )
        self.assertEqual(self.jobs.eligible(), [])
        self.clock.advance(10)
        self.assertEqual(self.jobs.eligible()[0]["job_id"], retry["job_id"])
        self.assertEqual(queued["job_id"], failed["job_id"])

    def test_f2_canonical_failure_policy_not_retryable_metadata_schedules_retry(self) -> None:
        queued = self.enqueue(max_attempts=3)
        failure_worker = Worker(
            self.jobs,
            CanonicalReferenceResolver(RUNTIME_REPOSITORY),
            LocalExecutor("failure", clock=self.clock),
            self.executions,
            approval_runtime=self.approvals,
            clock=self.clock,
            id_factory=SequenceIds("execution-failure"),
            worker_id="worker-result-retry-metadata",
            lease_seconds=30,
        )
        snapshot = self.make_loop(worker=failure_worker).run_once()
        failed = self.jobs.show(str(queued["job_id"]))
        retry_children = [
            job
            for job in self.jobs.list()
            if job.get("parent_job_id") == queued["job_id"]
        ]

        self.assertEqual(snapshot["processed_count"], 1)
        self.assertEqual(failed["status"], "failed")
        self.assertFalse(failed["error"]["retryable"])
        self.assertEqual(len(retry_children), 1)
        self.assertFalse(failed["error"]["retryable"])
        self.assertEqual(
            retry_children[0]["retry_authorization"]["repair_scope"]["failed_unit_id"],
            queued["job_id"],
        )

    def test_g_max_attempts_and_non_retryable_failures_are_terminal(self) -> None:
        exhausted = self.enqueue(max_attempts=1)
        self.jobs.claim(claimed_by="manual", lease_seconds=30)
        self.jobs.fail(exhausted["job_id"], retryable=True)
        with self.assertRaisesRegex(RuntimeError, "exhausted"):
            self.jobs.retry(exhausted["job_id"])
        terminal = self.enqueue(task="terminal")
        self.jobs.claim(claimed_by="manual", lease_seconds=30)
        self.jobs.fail(
            terminal["job_id"],
            code="invalid_authorization",
            retryable=True,
        )
        with self.assertRaisesRegex(RuntimeError, "authority_failure"):
            self.jobs.retry(terminal["job_id"])

    def test_h_claim_is_bounded_and_duplicate_claim_is_blocked(self) -> None:
        self.enqueue()
        claimed = self.jobs.claim(claimed_by="worker-a", lease_seconds=30)
        self.assertEqual(claimed["claimed_by"], "worker-a")
        self.assertEqual(claimed["claimed_at"], self.clock.value)
        self.assertIsNone(self.jobs.claim(claimed_by="worker-b", lease_seconds=30))

    def test_i_active_lease_is_respected_and_heartbeat_extends_it(self) -> None:
        self.enqueue()
        claimed = self.jobs.claim(claimed_by="worker-a", lease_seconds=30)
        before = claimed["lease_until"]
        self.clock.advance(5)
        heartbeat = self.jobs.heartbeat(claimed["job_id"], "worker-a", lease_seconds=30)
        self.assertGreater(heartbeat["lease_until"], before)
        self.assertEqual(
            self.jobs.recover_expired_claims(backoff_seconds=(10, 30)), []
        )

    def test_j_expired_claim_recovers_to_one_backed_off_retry(self) -> None:
        self.enqueue()
        claimed = self.jobs.claim(claimed_by="worker-a", lease_seconds=5)
        self.clock.advance(6)
        recovered = self.jobs.recover_expired_claims(backoff_seconds=(10, 30))
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["failed_job"]["status"], "failed")
        retry = recovered[0]["retry_job"]
        self.assertEqual(retry["status"], "queued")
        self.assertEqual(retry["next_run_at"], "2026-03-01T12:00:16Z")
        again = self.jobs.retry(claimed["job_id"])
        self.assertEqual(again["job_id"], retry["job_id"])

    def test_k_run_once_and_multiple_cycles_are_bounded(self) -> None:
        first = self.enqueue(task="first")
        second = self.enqueue(task="second")
        outcome = self.loop.run(max_cycles=2)
        self.assertEqual(len(outcome["cycles"]), 2)
        self.assertEqual(self.jobs.show(first["job_id"])["status"], "completed")
        self.assertEqual(self.jobs.show(second["job_id"])["status"], "completed")

    def test_l_graceful_prestart_stop_executes_nothing(self) -> None:
        job = self.enqueue()
        self.loop.stop()
        outcome = self.loop.run(max_cycles=2)
        self.assertEqual(outcome["cycles"], [])
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "queued")
        self.assertEqual(self.state_store.load()["status"], "stopped")

    def test_m_restart_preserves_state_and_completed_job(self) -> None:
        job = self.enqueue()
        self.loop.run_once()
        restarted = self.make_loop()
        second = restarted.run_once()
        self.assertEqual(second["processed_count"], 0)
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "completed")
        self.assertEqual(self.state_store.load()["cycle_count"], 2)

    def test_m2_restart_recovers_ready_continuation_through_queue(self) -> None:
        plan = {
            "plan_id": "scheduler-continuation",
            "steps": [
                {
                    "step_id": "STEP-001",
                    "task": "Run bounded local scheduler fixture",
                },
                {"step_id": "STEP-002", "task": "Run recovered second step"},
            ],
        }
        created = self.jobs.create(self.payload(continuation_plan=plan))
        self.jobs.enqueue(created["job_id"])
        running = self.jobs.claim(claimed_by="crashed-worker", lease_seconds=30)
        assert running is not None
        decision = ContinuationPolicy.decide_execution(
            running,
            result_status="succeeded",
            execution_ref="runtime-execution:before-restart",
        )
        self.jobs.record_execution_success(
            running["job_id"], [], continuation=decision.checkpoint
        )

        snapshot = self.loop.run_once()

        self.assertEqual(len(snapshot["recovered_continuations"]), 1)
        child = self.jobs.show(snapshot["recovered_continuations"][0])
        self.assertEqual(child["continuation_parent_job_id"], created["job_id"])
        self.assertEqual(child["status"], "completed")
        self.assertEqual(child["continuation"]["state"], "terminal")
        logical = self.loop.inspect()["continuations"]
        self.assertEqual(len(logical), 1)
        self.assertEqual(logical[0]["head_job_id"], child["job_id"])
        self.assertTrue(logical[0]["terminal"])

    def test_n_recurring_missed_occurrences_coalesce_to_next_future_time(self) -> None:
        schedule = self.schedules.create(self.schedule_payload())
        self.loop.run_once()
        updated = self.schedules.show(schedule["schedule_id"])
        self.assertEqual(updated["next_run_at"], "2026-03-01T13:00:00Z")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_o_timestamps_require_timezone_and_are_stored_as_utc(self) -> None:
        job = self.jobs.create(self.payload())
        with self.assertRaisesRegex(RuntimeError, "timezone"):
            self.jobs.schedule(job["job_id"], "2026-03-01T13:00:00")
        scheduled = self.jobs.schedule(job["job_id"], "2026-03-01T13:00:00+01:00")
        self.assertEqual(scheduled["next_run_at"], "2026-03-01T12:00:00Z")

    def test_p_dry_run_has_zero_state_or_execution_mutation(self) -> None:
        job = self.enqueue()
        result = self.loop.run_once(dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "queued")
        self.assertIsNone(self.state_store.load())
        self.assertEqual(self.state_store.list_events(), [])
        self.assertIsNone(self.executor.last_request)

    def test_q_max_jobs_and_single_concurrency_are_enforced(self) -> None:
        first = self.enqueue(task="first")
        second = self.enqueue(task="second")
        result = self.loop.run_once()
        self.assertEqual(result["processed_count"], 1)
        states = {self.jobs.show(first["job_id"])["status"], self.jobs.show(second["job_id"])["status"]}
        self.assertEqual(states, {"completed", "queued"})
        with self.assertRaisesRegex(SchedulerLoopError, "exactly one"):
            SchedulerConfig(max_concurrent_jobs=2)

    def test_r_provider_cycle_and_daily_guards_stop_bursts(self) -> None:
        first = self.enqueue(task="first")
        second = self.enqueue(task="second")
        guarded = self.make_loop(
            counts_as_provider_run=True,
            max_jobs_per_cycle=2,
            max_provider_runs_per_cycle=1,
            max_provider_runs_per_day=1,
        )
        result = guarded.run_once()
        self.assertEqual(result["processed_count"], 1)
        second_cycle = self.make_loop(
            counts_as_provider_run=True,
            max_jobs_per_cycle=2,
            max_provider_runs_per_cycle=1,
            max_provider_runs_per_day=1,
        ).run_once()
        self.assertEqual(second_cycle["processed_count"], 0)
        self.assertEqual(self.state_store.load()["provider_runs_today"], 1)
        self.assertEqual(
            {self.jobs.show(first["job_id"])["status"], self.jobs.show(second["job_id"])["status"]},
            {"completed", "queued"},
        )

    def test_s_pending_approval_is_never_resolved_by_scheduler(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        request = self.approvals.request_execution(job["job_id"], reason="Owner required")
        self.loop.run(max_cycles=2)
        approval = self.approvals.store.load(request.request.approval_id)
        self.assertEqual(approval.status, "PENDING")
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "waiting_approval")

    def test_t_worker_exception_isolated_and_claim_recovers_later(self) -> None:
        job = self.enqueue()
        raising = RaisingWorker(
            self.jobs,
            CanonicalReferenceResolver(RUNTIME_REPOSITORY),
            self.executor,
            self.executions,
            approval_runtime=self.approvals,
            clock=self.clock,
            worker_id="worker-raising",
            lease_seconds=5,
        )
        result = self.make_loop(worker=raising, lease_seconds=5).run_once()
        self.assertEqual(result["outcomes"][0]["status"], "worker_error")
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "running")
        self.clock.advance(6)
        recovered = self.make_loop(lease_seconds=5).run_once()
        self.assertEqual(len(recovered["recovered_claims"]), 1)

    def test_t2_invalid_persisted_execution_blocks_expired_retry_recovery(self) -> None:
        job = self.enqueue()
        claimed = self.jobs.claim(
            claimed_by=self.worker.worker_id,
            lease_seconds=5,
        )
        self.assertIsNotNone(claimed)
        request = self.worker._build_request(
            claimed,
            "execution-invalid-recovery",
            self.worker.resolver.resolve(claimed),
        )
        result = self.executor.execute(request)
        path = self.executions.create(request, result)
        record = json.loads(path.read_text(encoding="utf-8"))
        record["request"]["workflow"] = "different-workflow"
        path.write_text(json.dumps(record), encoding="utf-8")
        self.clock.advance(6)

        recovered = self.make_loop(lease_seconds=5).run_once()
        self.assertEqual(recovered["status"], "partial_failure")
        self.assertEqual(recovered["recovered_claims"], [])
        self.assertEqual(
            recovered["reconciled_executions"][0]["status"], "worker_error"
        )
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "running")
        self.assertEqual(
            [item for item in self.jobs.list() if item.get("parent_job_id")], []
        )

    def test_u_audit_status_and_restart_recovery_are_persisted(self) -> None:
        job = self.enqueue()
        self.loop.run_once()
        events = self.state_store.list_events()
        event_types = {event["event_type"] for event in events}
        self.assertTrue(
            {"scheduler_started", "job_claimed", "job_started", "job_completed", "scheduler_stopped"}
            <= event_types
        )
        snapshot = self.make_loop().inspect()
        self.assertFalse(snapshot["running"])
        self.assertNotIn(job["job_id"], snapshot["eligible_jobs"])

    def test_u2_restart_recovers_failure_without_retry_child(self) -> None:
        failed = self.enqueue()
        claimed = self.jobs.claim(claimed_by="worker-crashed", lease_seconds=30)
        self.assertEqual(claimed["job_id"], failed["job_id"])
        self.jobs.fail(failed["job_id"], retryable=True)

        result = self.make_loop().run_once()
        self.assertEqual(len(result["recovered_retries"]), 1)
        retry = result["recovered_retries"][0]
        self.assertEqual(retry["parent_job_id"], failed["job_id"])
        self.assertEqual(retry["schedule_reason"], "retry_backoff")
        self.assertEqual(result["processed_count"], 0)

    def test_u3_continuous_dry_run_remains_read_only(self) -> None:
        job = self.enqueue()
        result = self.loop.run(max_cycles=2, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["cycles"]), 2)
        self.assertEqual(self.jobs.show(job["job_id"])["status"], "queued")
        self.assertIsNone(self.state_store.load())
        self.assertEqual(self.state_store.list_events(), [])

    def test_u4_authority_loss_keeps_scheduler_in_recovery_hold(self) -> None:
        job = self.enqueue(
            task="Planned step",
            continuation_plan={
                "plan_id": "plan-scheduler-hold",
                "steps": [{"step_id": "STEP-001", "task": "Planned step"}],
            },
        )
        logical_id = str(job["job_id"])
        self.jobs.authorized_plan_store._path(logical_id).unlink()

        result = self.loop.run_once()

        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["processed_count"], 0)
        self.assertEqual(result["outcomes"], [])
        self.assertTrue(
            any("recovery hold" in error["message"] for error in result["errors"])
        )
        self.assertEqual(self.jobs.store.load(logical_id)["status"], "queued")
        self.assertIsNone(self.executor.last_request)

    def test_v_second_scheduler_lock_is_rejected(self) -> None:
        self.state_store.acquire_run_lock()
        try:
            with self.assertRaisesRegex(SchedulerLoopError, "already holds"):
                self.make_loop().run_once()
        finally:
            self.state_store.release_run_lock()

    def test_w_no_real_provider_or_network_is_used(self) -> None:
        self.enqueue()
        self.loop.run_once()
        self.assertIsNotNone(self.executor.last_request)
        self.assertIsInstance(self.executor, LocalExecutor)


if __name__ == "__main__":
    unittest.main()
