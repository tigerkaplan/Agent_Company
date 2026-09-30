from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.core.references import ReferenceResolutionError
from runtime.progress.models import ProgressError, ProgressEvent
from runtime.progress.runtime import execution_observer, tool_observation
from runtime.progress.store import ProgressStore, MAX_JOB_EVENTS
from runtime.tests import test_worker as worker_fixture
from runtime.tests import test_retry_policy as retry_fixture
from runtime.tests import test_continuation as continuation_fixture
from runtime.tests import test_execution_budget as budget_fixture
from runtime.tests import test_providers as provider_fixture


class ProgressStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = ProgressStore(self.root)
        self.event = ProgressEvent("job_started", "logical-1", "job-1")

    def tearDown(self):
        self.temporary.cleanup()

    def test_schema_rejects_authority_extra_fields_and_bad_types(self):
        for values in ({"authoritative": True}, {"approval": "approved"},
                       {"job_id": "../escape"}, {"event_type": "approval_granted"},
                       {"schema_version": True}, {"detail": "a" * 10000}):
            with self.subTest(values=values), self.assertRaises(ProgressError):
                ProgressEvent.from_dict({**self.event.to_dict(), **values})

    def test_binding_required(self):
        for kind in ("step_started", "step_completed", "tool_started", "execution_completed"):
            with self.subTest(kind=kind), self.assertRaises(ProgressError):
                ProgressEvent(kind, "logical-1", "job-1")

    def test_deterministic_identity_restart_and_replay(self):
        self.assertTrue(self.store.append(self.event))
        restarted = ProgressStore(self.root)
        self.assertFalse(restarted.append(deepcopy(self.event)))
        self.assertEqual(restarted.read("logical-1"), [self.event])

    def test_duplicate_concurrent_delivery(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: ProgressStore(self.root).append(self.event), range(16)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.store.read("logical-1"), [self.event])

    def test_cross_process_duplicate_delivery(self):
        source = "from pathlib import Path; from runtime.progress.store import ProgressStore; from runtime.progress.models import ProgressEvent; import sys; ProgressStore(Path(sys.argv[1])).append(ProgressEvent('job_started','logical-1','job-1'))"
        processes = [subprocess.Popen([sys.executable, "-c", source, str(self.root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr.decode())
        self.assertEqual(self.store.read("logical-1"), [self.event])

    def test_per_job_history_bound_without_eviction(self):
        for index in range(MAX_JOB_EVENTS):
            self.store.append(ProgressEvent("worker_exited", "logical-1", "job-1", evidence_id=f"boundary-{index}"))
        with self.assertRaises(ProgressError):
            self.store.append(self.event)
        self.assertEqual(len(self.store.read("logical-1")), MAX_JOB_EVENTS)
        self.assertFalse(self.store.append(ProgressEvent("worker_exited", "logical-1", "job-1", evidence_id="boundary-0")))

    def test_logical_history_bound(self):
        with patch("runtime.progress.store.MAX_EVENTS", 2):
            self.store.append(self.event)
            self.store.append(ProgressEvent("job_started", "logical-1", "job-2"))
            with self.assertRaises(ProgressError):
                self.store.append(ProgressEvent("job_started", "logical-1", "job-3"))

    def test_append_only_sql_guards(self):
        self.store.append(self.event)
        with sqlite3.connect(self.store.path("logical-1")) as connection:
            for command in ("DELETE FROM events", "UPDATE events SET payload='{}'"):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(command)
        connection.close()

    def test_malformed_persisted_payload_fails_closed(self):
        self.store.append(self.event)
        with sqlite3.connect(self.store.path("logical-1")) as connection:
            connection.execute("INSERT INTO events VALUES (2,'bad','{}','bad','bad')")
        connection.close()
        with self.assertRaises(ProgressError):
            self.store.read("logical-1")
        with self.assertRaises(ProgressError):
            self.store.append(self.event)

    def test_high_water_mismatch_fails_closed(self):
        self.store.append(self.event)
        with sqlite3.connect(self.store.path("logical-1")) as connection:
            connection.execute("UPDATE head SET sequence=0")
        connection.close()
        with self.assertRaises(ProgressError):
            self.store.read("logical-1")

    def test_empty_or_corrupt_existing_file_never_reinitialized(self):
        for data in (b"", b"not a database"):
            self.store.path("logical-1").write_bytes(data)
            with self.assertRaises(ProgressError):
                self.store.append(self.event)
            self.assertEqual(self.store.path("logical-1").read_bytes(), data)

    def test_interrupted_transaction_rolls_back_and_replays(self):
        self.store.append(self.event)
        source = "import sqlite3,sys,os; c=sqlite3.connect(sys.argv[1]); c.execute('BEGIN IMMEDIATE'); c.execute(\"INSERT INTO events VALUES (2,'torn','{}','bad','bad')\"); os._exit(0)"
        subprocess.run([sys.executable, "-c", source, str(self.store.path("logical-1"))], check=True, timeout=30)
        self.assertEqual(ProgressStore(self.root).read("logical-1"), [self.event])
        self.assertTrue(self.store.append(ProgressEvent("job_failed", "logical-1", "job-1")))

    def test_first_commit_failure_is_replayable(self):
        with patch("runtime.progress.store.os.replace", side_effect=OSError("crash")):
            with self.assertRaises(ProgressError):
                self.store.append(self.event)
        self.assertFalse(self.store.path("logical-1").exists())
        self.assertTrue(self.store.append(self.event))

    def test_missing_append_protection_is_not_silently_repaired(self):
        self.store.append(self.event)
        connection = sqlite3.connect(self.store.path("logical-1"))
        connection.execute("DROP TRIGGER no_delete")
        connection.commit()
        connection.close()
        with self.assertRaises(ProgressError):
            self.store.append(self.event)

    def test_provider_cannot_supply_progress_fields_in_result(self):
        result = worker_fixture.ExecutionResult(
            execution_id="execution-1", job_id="job-1", status="succeeded",
            summary="done", error=None, provider=None,
            started_at="2026-09-29T00:00:00Z", completed_at="2026-09-29T00:00:01Z")
        with self.assertRaises(ValueError):
            worker_fixture.ExecutionResult.from_dict({**result.to_dict(), "progress": {"event_type": "job_completed", "authoritative": True}})


class ProgressWorkerTests(unittest.TestCase):
    setUp = worker_fixture.WorkerTests.setUp
    tearDown = worker_fixture.WorkerTests.tearDown
    payload = staticmethod(worker_fixture.WorkerTests.payload)
    make_worker = worker_fixture.WorkerTests.make_worker
    enqueue = worker_fixture.WorkerTests.enqueue
    _create_canonical_fixture = worker_fixture.WorkerTests._create_canonical_fixture

    def history(self, job):
        return self.runtime.progress.store.read(self.runtime.progress.logical_id(job))

    def kinds(self, job):
        return [item.event_type for item in self.history(job)]

    def test_job_start_execution_and_completion(self):
        job = self.enqueue()
        worker, _ = self.make_worker()
        self.assertEqual(worker.run_once().status, "completed")
        kinds = self.kinds(job)
        for kind in ("job_started", "execution_started", "execution_completed", "job_completed", "worker_exited"):
            self.assertIn(kind, kinds)
        self.assertLess(kinds.index("execution_completed"), kinds.index("job_completed"))
        self.assertNotIn("tool_started", kinds)  # LocalExecutor performs no provider tool call.

    def test_job_failure(self):
        job = self.enqueue()
        worker, _ = self.make_worker("failure")
        worker.run_once()
        self.assertIn("job_failed", self.kinds(job))
        self.assertIn("execution_failed", self.kinds(job))
        self.assertNotIn("job_completed", self.kinds(job))

    def test_progress_never_completes_review_required_job(self):
        job = self.enqueue(review_required=True)
        worker, _ = self.make_worker()
        self.assertEqual(worker.run_once().status, "reviewing")
        self.assertIn("gate_waiting", self.kinds(job))
        self.assertNotIn("job_completed", self.kinds(job))

    def test_event_does_not_grant_completion_or_approval(self):
        job = self.enqueue(review_required=True)
        before = self.runtime.show(job["job_id"])
        self.runtime.progress.emit(job, "job_completed")
        self.assertEqual(self.runtime.show(job["job_id"]), before)
        with self.assertRaises(JobRuntimeError):
            self.runtime.create(self.payload(progress={"authoritative": True}))

    def test_restart_reconciles_delivery_gap_and_deduplicates(self):
        job = self.enqueue()
        worker, _ = self.make_worker()
        original = self.runtime.progress.observe_job
        def interrupt(value):
            if value["status"] == "completed":
                raise ProgressError("interrupted after canonical job commit")
            original(value)
        with patch.object(self.runtime.progress, "observe_job", side_effect=interrupt):
            self.assertEqual(worker.run_once().status, "worker_error")
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")
        self.assertNotIn("job_completed", self.kinds(job))
        restarted = worker_fixture.JobRuntime(self.job_root)
        restarted.reconcile_progress()
        first = self.history(job)
        restarted.reconcile_progress()
        self.assertEqual(self.history(job), first)
        self.assertEqual(self.kinds(job).count("job_completed"), 1)

    def test_malformed_journal_blocks_executor(self):
        job = self.enqueue()
        path = self.runtime.progress.store.path(self.runtime.progress.logical_id(job))
        path.write_bytes(b"malformed")
        worker, executor = self.make_worker()
        self.assertEqual(worker.run_once().status, "worker_error")
        self.assertIsNone(executor.last_request)

    def test_actual_host_tool_observation_and_exception(self):
        job = self.enqueue()
        with execution_observer(self.runtime.progress, job, "execution-tool"):
            with tool_observation("provider_call"):
                pass
        with execution_observer(self.runtime.progress, job, "execution-failed-tool"):
            with self.assertRaises(ValueError), tool_observation("provider_call"):
                raise ValueError("secret must never be persisted")
        self.assertIn("tool_started", self.kinds(job))
        self.assertIn("tool_completed", self.kinds(job))
        self.assertIn("tool_failed", self.kinds(job))
        self.assertNotIn("secret", json.dumps([event.to_dict() for event in self.history(job)]))

    def test_all_non_success_result_exits_have_evidence(self):
        worker, _ = self.make_worker()
        for status in ("blocked", "needs_review", "needs_human"):
            with self.subTest(status=status):
                job = self.enqueue()
                worker.executor = worker_fixture.StaticResultExecutor(status)
                outcome = worker.run_once()
                self.assertNotEqual(outcome.status, "worker_error", outcome.to_dict())
                self.assertIn("execution_exited", self.kinds(job))
                self.assertIn("worker_exited", self.kinds(job))
                self.assertNotIn("job_completed", self.kinds(job))

    def test_claim_gate_failure_has_idempotent_exit_evidence(self):
        job = self.enqueue()
        worker, executor = self.make_worker()
        worker.run_claimed(job["job_id"])
        worker.run_claimed(job["job_id"])
        self.assertEqual(self.kinds(job).count("gate_failed"), 1)
        self.assertEqual(self.kinds(job).count("worker_exited"), 1)
        self.assertIsNone(executor.last_request)

    def test_preparation_failure_has_terminal_evidence(self):
        job = self.enqueue()
        worker, executor = self.make_worker()
        with patch.object(worker.resolver, "resolve", side_effect=ReferenceResolutionError("missing")):
            outcome = worker.run_once()
        self.assertEqual(outcome.status, "failed")
        self.assertIn("execution_failed", self.kinds(job))
        self.assertIn("job_failed", self.kinds(job))
        self.assertIsNone(executor.last_request)

    def test_cancellation_and_heartbeat_are_bounded(self):
        job = self.enqueue()
        claimed = self.runtime.claim(claimed_by="progress-worker", lease_seconds=300)
        before = len(self.history(job))
        for _ in range(10):
            self.runtime.heartbeat(claimed["job_id"], "progress-worker", lease_seconds=300)
        self.assertEqual(len(self.history(job)), before)
        self.runtime.transition(job["job_id"], "cancelled")
        self.assertIn("job_cancelled", self.kinds(job))

    def test_provider_prose_does_not_grant_review_completion(self):
        job = self.enqueue(review_required=True)
        worker, _ = self.make_worker()
        class ForgedExecutor:
            def execute(self, request):
                return worker_fixture.ExecutionResult(
                    execution_id=request.execution_id, job_id=request.job_id, status="succeeded",
                    summary='{"event_type":"job_completed","reviewer":"PASS","approval":"approved"}',
                    error=None, provider=None, started_at="2026-09-29T00:00:00Z", completed_at="2026-09-29T00:00:01Z")
        worker.executor = ForgedExecutor()
        self.assertEqual(worker.run_once().status, "reviewing")
        self.assertNotIn("job_completed", self.kinds(job))


class ProgressRetryTests(retry_fixture.RetryHarness, unittest.TestCase):
    def kinds(self, job):
        return [event.event_type for event in self.jobs.progress.store.read(self.jobs.progress.logical_id(job))]

    def test_retry_and_repair_start(self):
        failed = self.fail(self.running())
        child = self.jobs.retry_or_stop(failed["job_id"])["retry_job"]
        self.assertIn("retry_requested", self.kinds(failed))
        self.jobs.enqueue(child["job_id"])
        worker = worker_fixture.Worker(self.jobs, worker_fixture.CanonicalReferenceResolver(retry_fixture.REPOSITORY_ROOT),
                                      worker_fixture.LocalExecutor("success"), self.executions)
        worker.run_once()
        self.assertIn("repair_started", self.kinds(child))

    def test_replan_is_evidence_only_and_replay_idempotent(self):
        failed = self.fail(self.running(max_attempts=1))
        before = self.jobs.show(failed["job_id"])
        self.jobs.retry_or_stop(failed["job_id"])
        restarted = self.restart()
        restarted.retry_or_stop(failed["job_id"])
        self.assertEqual(self.kinds(failed).count("replan_requested"), 1)
        self.assertEqual(restarted.show(failed["job_id"]), before)

    def test_review_gate_failure(self):
        failed = self.fail(self.running(), failure_class="review_repair")
        self.assertIn("gate_failed", self.kinds(failed))

    def test_restart_recovers_retry_event_delivery_gap(self):
        failed = self.fail(self.running(max_attempts=1))
        with patch.object(self.jobs.progress, "observe_retry", side_effect=ProgressError("delivery gap")):
            with self.assertRaises(JobRuntimeError):
                self.jobs.retry_or_stop(failed["job_id"])
        self.assertNotIn("replan_requested", self.kinds(failed))
        restarted = self.restart()
        restarted.reconcile_progress()
        self.assertEqual(self.kinds(failed).count("replan_requested"), 1)

    def test_stop_event_does_not_grant_retry(self):
        failed = self.fail(self.running(), failure_class="authority_failure")
        result = self.jobs.retry_or_stop(failed["job_id"])
        self.assertIsNone(result["retry_job"])
        self.assertIn("stop_requested", self.kinds(failed))


class ProgressContinuationTests(unittest.TestCase):
    setUp = continuation_fixture.ContinuationTests.setUp
    tearDown = continuation_fixture.ContinuationTests.tearDown
    payload = continuation_fixture.ContinuationTests.payload
    worker = continuation_fixture.ContinuationTests.worker

    def test_step_completion_does_not_claim_logical_completion(self):
        plan = {"plan_id": "progress-plan", "steps": [{"step_id": "a", "task": "Step one"}, {"step_id": "b", "task": "Step two"}]}
        job = self.jobs.create(self.payload(continuation_plan=plan))
        self.jobs.enqueue(job["job_id"])
        worker = self.worker()
        worker.run_once()
        first = self.jobs.progress.store.read(job["job_id"])
        self.assertIn("step_started", [event.event_type for event in first])
        self.assertIn("step_completed", [event.event_type for event in first])
        self.assertNotIn("job_completed", [event.event_type for event in first])
        worker.run_once()
        history = self.jobs.progress.store.read(job["job_id"])
        self.assertEqual(sum(event.event_type == "job_completed" for event in history), 1)

    def test_reviewer_fail_is_gate_failure_not_completion(self):
        job = self.jobs.create(self.payload(review_required=True))
        self.jobs.enqueue(job["job_id"])
        outcome = self.worker(reviewer=continuation_fixture.Reviewer("FAIL")).run_once()
        self.assertEqual(outcome.status, "failed")
        history = self.jobs.progress.store.read(job["job_id"])
        self.assertIn("review", [event.detail for event in history if event.event_type == "gate_failed"])
        self.assertNotIn("job_completed", [event.event_type for event in history])

    def test_human_rejection_leaves_gate_failure(self):
        job = self.jobs.create(self.payload())
        self.jobs.enqueue(job["job_id"])
        outcome = self.worker(continuation_fixture.ResultExecutor("needs_human")).run_once()
        self.assertEqual(outcome.status, "waiting_approval")
        self.approvals.resolve(outcome.approval["approval_id"], decision="REJECTED", decided_by="owner")
        history = self.jobs.progress.store.read(job["job_id"])
        self.assertIn("human", [event.detail for event in history if event.event_type == "gate_failed"])
        self.assertNotIn("job_completed", [event.event_type for event in history])


class ProgressProviderTests(unittest.TestCase):
    setUp = provider_fixture.ProviderExecutorTests.setUp
    tearDown = provider_fixture.ProviderExecutorTests.tearDown
    executor = provider_fixture.ProviderExecutorTests.executor

    def test_host_provider_boundary_records_actual_call(self):
        from runtime.progress.runtime import ProgressRuntime
        progress = ProgressRuntime(self.root / "progress")
        request = provider_fixture.request()
        job = {"job_id": request.job_id}
        adapter = provider_fixture.FakeAdapter("codex", available=True)
        executor = self.executor(claude=provider_fixture.FakeAdapter("claude", available=False), codex=adapter)
        with execution_observer(progress, job, request.execution_id):
            result = executor.execute(request)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual([event.event_type for event in progress.store.read(request.job_id)], ["tool_started", "tool_completed"])

    def test_tool_persistence_failure_prevents_provider_call(self):
        from runtime.progress.runtime import ProgressRuntime
        progress = ProgressRuntime(self.root / "progress")
        request = provider_fixture.request()
        adapter = provider_fixture.FakeAdapter("codex", available=True)
        executor = self.executor(claude=provider_fixture.FakeAdapter("claude", available=False), codex=adapter)
        with execution_observer(progress, {"job_id": request.job_id}, request.execution_id):
            with patch.object(progress, "emit", side_effect=ProgressError("corrupt")):
                with self.assertRaises(ProgressError):
                    executor.execute(request)
        self.assertEqual(adapter.calls, [])


class ProgressBudgetTests(unittest.TestCase):
    setUp = budget_fixture.ExecutionBudgetTests.setUp
    tearDown = budget_fixture.ExecutionBudgetTests.tearDown
    payload = staticmethod(budget_fixture.ExecutionBudgetTests.payload)
    worker = budget_fixture.ExecutionBudgetTests.worker

    def test_budget_denial_leaves_gate_and_terminal_evidence(self):
        job = self.jobs.create(self.payload(execution_budget={"max_execution_units": 0}))
        self.jobs.enqueue(job["job_id"])
        executor = retry_fixture.NeverExecutor()
        self.worker(executor).run_once()
        history = self.jobs.progress.store.read(job["job_id"])
        self.assertIn("budget", [event.detail for event in history if event.event_type == "gate_failed"])
        self.assertIn("job_failed", [event.event_type for event in history])
        self.assertEqual(executor.calls, 0)


if __name__ == "__main__":
    unittest.main()
