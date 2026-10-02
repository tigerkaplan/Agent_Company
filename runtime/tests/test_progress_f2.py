"""CORE-07R2 recovery delivery and capacity regression probes."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError
from runtime.progress.models import ProgressError
from runtime.tests import test_progress_f1 as fixture


class RecoveryDurabilityTests(unittest.TestCase):
    setUp = fixture.ProgressRepairTests.setUp
    tearDown = fixture.ProgressRepairTests.tearDown
    payload = staticmethod(fixture.ProgressRepairTests.payload)
    make_worker = fixture.ProgressRepairTests.make_worker
    enqueue = fixture.ProgressRepairTests.enqueue
    _create_canonical_fixture = fixture.ProgressRepairTests._create_canonical_fixture
    events = fixture.ProgressRepairTests.events
    fill = fixture.ProgressRepairTests.fill
    alter_sql = fixture.ProgressRepairTests.alter_sql

    def interrupted_execution(self, **fields):
        job = self.enqueue(**fields)
        worker, _ = self.make_worker()
        with patch.object(self.runtime.progress, "observe_execution", side_effect=ProgressError("delivery gap")):
            self.assertEqual(worker.run_once().status, "worker_error")
        return self.runtime.show(job["job_id"]), worker

    def recovery_events(self, job):
        return [event for event in self.events(job) if event.event_type == "recovery_completed"]

    def interrupt_delivery(self, worker):
        original = self.runtime.progress.emit
        def interrupted(job, kind, **fields):
            if kind == "recovery_completed":
                raise ProgressError("interrupted recovery append")
            return original(job, kind, **fields)
        with patch.object(self.runtime.progress, "emit", side_effect=interrupted):
            with self.assertRaises(JobRuntimeError):
                worker.recover_persisted_results()

    def assert_replayed_once(self, job, detail="completed"):
        restarted = JobRuntime(self.job_root)
        restarted.reconcile_progress()
        before = self.events(job)
        restarted.reconcile_progress()
        self.assertEqual(self.events(job), before)
        records = self.recovery_events(job)
        self.assertEqual([event.detail for event in records], [detail])
        self.assertEqual([event for event in before if event.event_type == "worker_exited"
                          and not (event.evidence_id or "").startswith("fill-")], [])
        self.assertIsNone(restarted.progress.store.recovery_record(job["job_id"], job["job_id"]))

    def test_r2_interrupted_append_replays_after_terminal_transition(self):
        job, worker = self.interrupted_execution()
        self.interrupt_delivery(worker)
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")
        self.assertEqual(self.recovery_events(job), [])
        self.assert_replayed_once(job)
        self.assertEqual(worker.recover_persisted_results(), [])

    def test_r2_124_of_128_fails_before_terminal_transition(self):
        job, worker = self.interrupted_execution()
        self.fill(job, 124)
        outcomes = worker.recover_persisted_results()
        self.assertEqual([outcome.status for outcome in outcomes], ["worker_error"])
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "running")
        self.assertNotIn("job_completed", [event.event_type for event in self.events(job)])
        self.assert_replayed_once(job, "worker_error")

    def test_exact_fit_123_of_128_completes_state_and_evidence(self):
        job, worker = self.interrupted_execution()
        self.fill(job, 123)
        self.assertEqual(worker.recover_persisted_results()[0].status, "completed")
        self.assertEqual(len(self.events(job)), 128)
        self.assert_replayed_once(job)

    def test_exact_fit_interruption_preserves_reserved_slot(self):
        job, worker = self.interrupted_execution()
        self.fill(job, 123)
        self.interrupt_delivery(worker)
        self.assertEqual(len(self.events(job)), 127)
        with self.assertRaises(ProgressError):
            self.runtime.progress.emit(job, "worker_exited", evidence_id="steal-slot")
        self.assert_replayed_once(job)
        self.assertEqual(len(self.events(job)), 128)

    def test_delivery_transaction_rollback_retains_ready_record(self):
        job, worker = self.interrupted_execution()
        original = self.runtime.progress.store._insert
        def interrupted(connection, history, previous, events):
            count = original(connection, history, previous, events)
            if any(event.event_type == "recovery_completed" for event in events):
                raise ProgressError("after event insert before commit")
            return count
        with patch.object(self.runtime.progress.store, "_insert", side_effect=interrupted):
            with self.assertRaises(JobRuntimeError):
                worker.recover_persisted_results()
        self.assertEqual(self.recovery_events(job), [])
        self.assert_replayed_once(job)

    def test_process_exit_before_append_recovers_actual_outcome(self):
        job, _ = self.interrupted_execution()
        source = '''
import os, sys
from pathlib import Path
from runtime.tests import test_worker as fixture
case = fixture.WorkerTests()
case.root = Path(sys.argv[1])
case.repository = case.root / "repository"
case.execution_root = case.root / "state" / "executions"
case.runtime = fixture.JobRuntime(case.root / "state" / "jobs")
worker, _ = case.make_worker()
original = case.runtime.progress.emit
def crash(job, kind, **fields):
    if kind == "recovery_completed": os._exit(0)
    return original(job, kind, **fields)
case.runtime.progress.emit = crash
worker.recover_persisted_results()
raise Exception("crash boundary was not reached")
'''
        subprocess.run([sys.executable, "-B", "-c", source, str(self.root)], check=True, timeout=30)
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")
        self.assert_replayed_once(job)

    def test_unreturned_interrupted_recovery_records_error_not_invented_success(self):
        job, worker = self.interrupted_execution()
        with patch.object(self.runtime.progress.store, "finish_recovery", side_effect=ProgressError("before outcome commit")):
            with self.assertRaises(JobRuntimeError):
                worker.recover_persisted_results()
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")
        self.assertEqual(worker.recover_persisted_results(), [])
        self.assert_replayed_once(job, "worker_error")

    def test_review_wait_delivery_replays_without_granting_completion(self):
        job, worker = self.interrupted_execution(review_required=True)
        self.interrupt_delivery(worker)
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "reviewing")
        self.assert_replayed_once(job, "reviewing")
        self.assertNotIn("job_completed", [event.event_type for event in self.events(job)])

    def test_concurrent_recovery_delivers_once(self):
        job, first = self.interrupted_execution()
        second, _ = self.make_worker()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda worker: worker.recover_persisted_results(), (first, second)))
        self.assertEqual(sum(len(result) for result in results), 1)
        self.assert_replayed_once(job)

    def test_intact_f1_schema_migrates_without_losing_events(self):
        job, _ = self.interrupted_execution()
        before = self.events(job)
        self.alter_sql(job, "DROP TABLE recovery; PRAGMA user_version=1;")
        self.assertEqual(self.events(job), before)
        connection = sqlite3.connect(self.runtime.progress.store.path(job["job_id"]))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
        finally:
            connection.close()

    def test_missing_recovery_table_fails_closed(self):
        job, worker = self.interrupted_execution()
        self.alter_sql(job, "DROP TABLE recovery;")
        with self.assertRaises(JobRuntimeError):
            worker.recover_persisted_results()
        # GOV-01F2 canonical reads now require intact independent gate history.
        # Raw lifecycle state still proves recovery did not mutate the job.
        with self.assertRaises(JobRuntimeError): self.runtime.show(job["job_id"])
        self.assertEqual(self.runtime.store.load(job["job_id"])["status"], "running")

    def test_full_journal_rejects_before_recovery_mutates_state(self):
        job, worker = self.interrupted_execution()
        self.fill(job, 128)
        before = self.runtime.show(job["job_id"])
        with self.assertRaises(JobRuntimeError):
            worker.recover_persisted_results()
        self.assertEqual(self.runtime.show(job["job_id"]), before)
        self.assertEqual(self.recovery_events(job), [])

    def test_logical_capacity_also_includes_reserved_recovery_slot(self):
        job, worker = self.interrupted_execution()
        with patch("runtime.progress.store.MAX_EVENTS", len(self.events(job)) + 4):
            self.assertEqual(worker.recover_persisted_results()[0].status, "worker_error")
            self.assertEqual(self.runtime.show(job["job_id"])["status"], "running")
            self.assert_replayed_once(job, "worker_error")

    def test_altered_recovery_protection_definition_fails_closed(self):
        job, worker = self.interrupted_execution()
        self.alter_sql(job, "DROP TABLE recovery; CREATE TABLE recovery (job_id TEXT PRIMARY KEY NOT NULL, ready INTEGER NOT NULL, payload TEXT NOT NULL);")
        with self.assertRaises(JobRuntimeError):
            worker.recover_persisted_results()
        with self.assertRaises(JobRuntimeError): self.runtime.show(job["job_id"])
        self.assertEqual(self.runtime.store.load(job["job_id"])["status"], "running")


if __name__ == "__main__":
    unittest.main()
