"""Adversarial regression coverage for the four CORE-07R1 findings."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier
import unittest
from unittest.mock import patch

from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError
from runtime.tests.contract_fixtures import persist_execution_fixture
from runtime.progress.models import ProgressError, ProgressEvent, canonical, digest
from runtime.progress.store import MAX_JOB_EVENTS, ProgressStore
from runtime.storage.file_store import JobStoreError
from runtime.tests import test_worker as fixture


class ProgressRepairTests(unittest.TestCase):
    setUp = fixture.WorkerTests.setUp
    tearDown = fixture.WorkerTests.tearDown
    payload = staticmethod(fixture.WorkerTests.payload)
    make_worker = fixture.WorkerTests.make_worker
    enqueue = fixture.WorkerTests.enqueue
    _create_canonical_fixture = fixture.WorkerTests._create_canonical_fixture

    def running(self):
        job = self.enqueue()
        self.runtime.claim(claimed_by="repair-worker", lease_seconds=300)
        running = self.runtime.show(job["job_id"])
        ref = persist_execution_fixture(self.runtime, running, "fixture-" + job["job_id"])
        running["output_refs"].append(ref)
        return self.runtime._save(running)

    def events(self, job):
        return self.runtime.progress.store.read(self.runtime.progress.logical_id(job))

    def fill(self, job, count):
        progress = self.runtime.progress
        for index in range(count - len(self.events(job))):
            progress.emit(job, "worker_exited", evidence_id=f"fill-{index}")
        self.assertEqual(len(self.events(job)), count)

    def pending_count(self, job):
        connection = sqlite3.connect(self.runtime.progress.store.path(job["job_id"]))
        try:
            return connection.execute("SELECT count(*) FROM pending").fetchone()[0]
        finally:
            connection.close()

    def concurrent_workers(self, second_status):
        job = self.enqueue()
        first, _ = self.make_worker()
        second, _ = self.make_worker()
        second.worker_id = first.worker_id
        second.id_factory = lambda: "execution-second"
        self.runtime.claim(claimed_by=first.worker_id)
        execution_barrier, save_barrier = Barrier(2), Barrier(2)
        original_save = self.runtime._save

        def synchronized_save(value, **kwargs):
            if value["status"] in {"completed", "failed"}:
                save_barrier.wait(timeout=10)
            return original_save(value, **kwargs)

        class Executor:
            supported_execution_modes = frozenset({"READ_ONLY"})
            def __init__(self, status):
                self.status = status
            def execute(self, request):
                execution_barrier.wait(timeout=10)
                return fixture.StaticResultExecutor(self.status).execute(request)

        first.executor, second.executor = Executor("succeeded"), Executor(second_status)
        with patch.object(self.runtime, "_save", side_effect=synchronized_save):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker.run_claimed, job["job_id"]) for worker in (first, second)]
                outcomes = [future.result(timeout=30) for future in futures]
        self.assertEqual(sum(outcome.status == "worker_error" for outcome in outcomes), 1)
        status = self.runtime.show(job["job_id"])["status"]
        terminal = [event for event in self.events(job) if event.event_type in {"job_completed", "job_failed"}]
        self.assertEqual(len(terminal), 1)
        self.assertEqual(terminal[0].event_type, {"completed": "job_completed", "failed": "job_failed"}[status])
        before = self.events(job)
        self.runtime.reconcile_progress()
        self.assertEqual(self.events(job), before)

    def test_completion_failure_worker_race_has_one_terminal(self):
        self.concurrent_workers("failed")

    def test_duplicate_completion_worker_race_has_one_terminal(self):
        self.concurrent_workers("succeeded")

    def test_cross_process_stale_terminal_transition_rejected(self):
        job = self.running()
        source = """
import sys,time
from pathlib import Path
from runtime.core.jobs import JobRuntime, RuntimeError
r=JobRuntime(Path(sys.argv[1])); original=r._save
def synchronized(value, **kwargs):
    Path(sys.argv[2],sys.argv[3]).touch()
    deadline=time.monotonic()+10
    while len(list(Path(sys.argv[2]).glob('ready-*'))) < 2:
        if time.monotonic()>deadline: raise Exception('barrier timeout')
        time.sleep(.01)
    return original(value, **kwargs)
r._save=synchronized
try:
    print(r.transition(sys.argv[4],sys.argv[5])['status'])
except RuntimeError:
    print('stale_rejected')
"""
        processes = [subprocess.Popen([sys.executable, "-B", "-c", source, str(self.job_root), str(self.root),
                                       f"ready-{index}", job["job_id"], target], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for index, target in enumerate(("completed", "cancelled"))]
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr.decode())
            outputs.append(stdout.decode().strip())
        self.assertEqual(outputs.count("stale_rejected"), 1)
        self.assertEqual(sum(event.event_type in {"job_completed", "job_cancelled"} for event in self.events(job)), 1)

    def test_existing_terminal_cannot_be_rewritten(self):
        job = self.running()
        stale = deepcopy(job)
        self.runtime.complete(job["job_id"])
        stale["status"] = "cancelled"
        with self.assertRaises(JobRuntimeError):
            self.runtime._save(stale)
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")

    def test_conflicting_terminal_append_is_rejected(self):
        job = self.running()
        self.runtime.complete(job["job_id"])
        before = self.events(job)
        with self.assertRaises(ProgressError):
            self.runtime.progress.emit(job, "job_failed")
        self.assertEqual(self.events(job), before)

    def test_legacy_conflicting_history_fails_closed_on_reconciliation(self):
        job = self.running()
        self.runtime.complete(job["job_id"])
        store = self.runtime.progress.store
        event = self.runtime.progress.event(job, "job_failed")
        connection = sqlite3.connect(store.path(job["job_id"]))
        try:
            sequence, prior = connection.execute("SELECT sequence,hash FROM head").fetchone()
            sequence += 1
            chain_hash = digest([sequence, prior, event.event_id])
            connection.execute("INSERT INTO events VALUES (?,?,?,?,?)", (sequence, event.event_id, canonical(event.to_dict()), prior, chain_hash))
            connection.execute("UPDATE head SET sequence=?,hash=?", (sequence, chain_hash))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(ProgressError):
            self.events(job)
        with self.assertRaises(JobRuntimeError):
            self.runtime.reconcile_progress()
        with self.assertRaises(JobRuntimeError): self.runtime.show(job["job_id"])
        self.assertEqual(self.runtime.store.load(job["job_id"])["status"], "completed")

    def test_near_capacity_completion_rejects_before_state_write(self):
        job = self.running()
        self.fill(job, MAX_JOB_EVENTS - 1)
        with self.assertRaises(JobRuntimeError):
            self.runtime.complete(job["job_id"])
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "running")
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS - 1)
        self.assertEqual(self.pending_count(job), 0)
        self.runtime.reconcile_progress()

    def test_near_capacity_failure_and_cancellation_reject_before_state_write(self):
        for target in ("failed", "cancelled"):
            with self.subTest(target=target):
                job = self.running()
                self.fill(job, MAX_JOB_EVENTS - 1)
                with self.assertRaises(JobRuntimeError):
                    self.runtime.transition(job["job_id"], target)
                self.assertEqual(self.runtime.show(job["job_id"])["status"], "running")
                self.assertEqual(self.pending_count(job), 0)

    def test_exact_capacity_bundle_is_atomic_and_idempotent(self):
        job = self.running()
        self.fill(job, MAX_JOB_EVENTS - 3)
        self.runtime.complete(job["job_id"])
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS)
        self.assertEqual(sum(event.event_type == "job_completed" for event in self.events(job)), 1)
        self.runtime.reconcile_progress()
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS)

    def test_interrupted_post_write_bundle_reserves_capacity_until_restart(self):
        job = self.running()
        self.fill(job, MAX_JOB_EVENTS - 3)
        original = self.runtime.progress.observe_job
        def interrupt(value):
            if value["status"] == "completed":
                raise ProgressError("interrupted after canonical write")
            original(value)
        with patch.object(self.runtime.progress, "observe_job", side_effect=interrupt):
            with self.assertRaises(JobRuntimeError):
                self.runtime.complete(job["job_id"])
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")
        self.assertEqual(self.pending_count(job), 1)
        with self.assertRaises(ProgressError):
            self.runtime.progress.emit(job, "worker_exited", evidence_id="cannot-steal-reserved-slot")
        JobRuntime(self.job_root).reconcile_progress()
        self.assertEqual(self.pending_count(job), 0)
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS)
        self.assertIn("job_completed", [event.event_type for event in self.events(job)])

    def test_pre_write_interruption_cancels_reservation_without_completing_job(self):
        job = self.running()
        self.fill(job, MAX_JOB_EVENTS - 3)
        with patch.object(self.runtime.store, "save", side_effect=JobStoreError("interrupted before write")):
            with self.assertRaises(JobRuntimeError):
                self.runtime.complete(job["job_id"])
        self.assertEqual(self.pending_count(job), 1)
        JobRuntime(self.job_root).reconcile_progress()
        self.assertEqual(self.pending_count(job), 0)
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "running")
        self.assertNotIn("job_completed", [event.event_type for event in self.events(job)])
        self.runtime.complete(job["job_id"])
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS)

    def test_process_exit_after_canonical_write_recovers_reserved_bundle(self):
        job = self.running()
        self.fill(job, MAX_JOB_EVENTS - 3)
        source = """
import os,sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
r=JobRuntime(Path(sys.argv[1])); original=r.store.save
def crash(value):
    original(value)
    os._exit(0)
r.store.save=crash
r.complete(sys.argv[2])
"""
        subprocess.run([sys.executable, "-B", "-c", source, str(self.job_root), job["job_id"]], check=True, timeout=30)
        self.assertEqual(self.pending_count(job), 1)
        restarted = JobRuntime(self.job_root)
        restarted.reconcile_progress()
        restarted.reconcile_progress()
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS)
        self.assertEqual(sum(event.event_type == "job_completed" for event in self.events(job)), 1)

    def test_process_exit_during_bundle_insert_rolls_back_then_recovers(self):
        job = self.running()
        self.fill(job, MAX_JOB_EVENTS - 3)
        source = """
import os,sys
from pathlib import Path
from runtime.core.jobs import JobRuntime
r=JobRuntime(Path(sys.argv[1])); original=r.progress.store._insert
def crash(connection,history,previous,events):
    if any(event.event_type=='job_completed' for event in events):
        original(connection,history,previous,events[:1])
        os._exit(0)
    return original(connection,history,previous,events)
r.progress.store._insert=crash
r.complete(sys.argv[2])
"""
        subprocess.run([sys.executable, "-B", "-c", source, str(self.job_root), job["job_id"]], check=True, timeout=30)
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "completed")
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS - 3)
        self.assertEqual(self.pending_count(job), 1)
        JobRuntime(self.job_root).reconcile_progress()
        self.assertEqual(len(self.events(job)), MAX_JOB_EVENTS)
        self.assertEqual(self.pending_count(job), 0)

    def test_logical_capacity_reservations_are_serialized(self):
        store = ProgressStore(self.root / "quota-journal")
        barrier = Barrier(2)
        def reserve(job_id):
            events = [ProgressEvent("job_state_observed", "logical", job_id, detail="completed"),
                      ProgressEvent("job_completed", "logical", job_id)]
            barrier.wait(timeout=10)
            try:
                store.reserve("logical", job_id, "a" * 64, "b" * 64, events)
                return job_id, events
            except ProgressError:
                return None
        with patch("runtime.progress.store.MAX_EVENTS", 2):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(reserve, ("one", "two")))
            winners = [result for result in results if result is not None]
            self.assertEqual(len(winners), 1)
            job_id, events = winners[0]
            store.resolve("logical", job_id, "b" * 64, events)
            self.assertEqual(store.read("logical"), events)

    def test_pending_bundle_tamper_cannot_drive_job_state_or_delivery(self):
        job = self.running()
        with patch.object(self.runtime.store, "save", side_effect=JobStoreError("before write")):
            with self.assertRaises(JobRuntimeError):
                self.runtime.complete(job["job_id"])
        connection = sqlite3.connect(self.runtime.progress.store.path(job["job_id"]))
        try:
            connection.execute("UPDATE pending SET before_digest=?", ("0" * 64,))
            connection.commit()
        finally:
            connection.close()
        before = self.runtime.show(job["job_id"])
        with self.assertRaises(JobRuntimeError):
            self.runtime.reconcile_progress()
        self.assertEqual(self.runtime.show(job["job_id"]), before)
        self.assertNotIn("job_completed", [event.event_type for event in self.events(job)])

    def test_recovered_outcome_has_recovery_event_not_fabricated_worker_exit(self):
        job = self.enqueue()
        worker, _ = self.make_worker()
        with patch.object(self.runtime.progress, "observe_execution", side_effect=ProgressError("delivery gap")):
            self.assertEqual(worker.run_once().status, "worker_error")
        outcomes = worker.recover_persisted_results()
        self.assertEqual([outcome.status for outcome in outcomes], ["completed"])
        events = self.events(job)
        self.assertEqual(sum(event.event_type == "recovery_completed" for event in events), 1)
        self.assertNotIn("worker_exited", [event.event_type for event in events])
        self.assertEqual(worker.recover_persisted_results(), [])
        self.assertEqual(self.events(job), events)

    def test_recovery_error_outcome_has_evidence(self):
        job = self.running()
        worker, _ = self.make_worker()
        from runtime.storage.execution_store import ExecutionStoreError
        with patch.object(worker.execution_store, "find_for_job", side_effect=ExecutionStoreError("malformed")):
            self.assertEqual(worker.recover_persisted_results()[0].status, "worker_error")
            worker.recover_persisted_results()
        records = [event for event in self.events(job) if event.event_type == "recovery_completed"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].detail, "worker_error")

    def alter_sql(self, job, statement):
        connection = sqlite3.connect(self.runtime.progress.store.path(job["job_id"]))
        try:
            connection.executescript(statement)
            connection.commit()
        finally:
            connection.close()

    def test_same_named_noop_delete_trigger_fails_integrity(self):
        job = self.running()
        self.alter_sql(job, "DROP TRIGGER no_delete; CREATE TRIGGER no_delete BEFORE DELETE ON events BEGIN SELECT 1; END;")
        with self.assertRaises(ProgressError):
            self.events(job)
        with self.assertRaises(ProgressError):
            self.runtime.progress.emit(job, "worker_exited")

    def test_same_named_noop_update_trigger_fails_integrity(self):
        job = self.running()
        self.alter_sql(job, "DROP TRIGGER no_update; CREATE TRIGGER no_update BEFORE UPDATE ON events BEGIN SELECT 1; END;")
        with self.assertRaises(ProgressError):
            self.events(job)

    def test_altered_check_constraint_fails_integrity(self):
        job = self.running()
        self.alter_sql(job, "ALTER TABLE head RENAME TO previous_head; CREATE TABLE head (singleton INTEGER PRIMARY KEY, sequence INTEGER NOT NULL, hash TEXT NOT NULL); INSERT INTO head SELECT * FROM previous_head; DROP TABLE previous_head;")
        with self.assertRaises(ProgressError):
            self.events(job)

    def test_altered_unique_constraint_fails_integrity(self):
        job = self.running()
        self.alter_sql(job, "PRAGMA writable_schema=ON; UPDATE sqlite_master SET sql=replace(sql,'event_id TEXT UNIQUE','event_id TEXT') WHERE name='events'; PRAGMA writable_schema=OFF;")
        with self.assertRaises(ProgressError):
            self.events(job)

    def test_intact_r1_journal_migration_preserves_history(self):
        job = self.running()
        before = self.events(job)
        self.alter_sql(job, "DROP TABLE recovery; DROP TABLE pending; PRAGMA user_version=0;")
        self.assertEqual(self.events(job), before)
        self.assertEqual(self.pending_count(job), 0)

    def test_missing_new_pending_table_is_not_silently_reinitialized(self):
        job = self.running()
        self.alter_sql(job, "DROP TABLE pending;")
        with self.assertRaises(ProgressError):
            self.events(job)


if __name__ == "__main__":
    unittest.main()
