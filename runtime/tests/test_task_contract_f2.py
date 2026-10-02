"""GOV-01F2 rollback resistance through canonical jobs and CORE-07 evidence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.progress.models import ProgressError
from runtime.tests import test_task_contract_f1 as fixtures


class GateRollbackF2Tests(unittest.TestCase):
    setUp = fixtures.TaskContractF1Tests.setUp
    tearDown = fixtures.TaskContractF1Tests.tearDown
    running = fixtures.TaskContractF1Tests.running
    strengthen = fixtures.TaskContractF1Tests.strengthen
    restarted = fixtures.TaskContractF1Tests.restarted

    def snapshots(self, job):
        store = self.runtime.task_contract_store
        return {suffix: store._path(job["job_id"], suffix).read_bytes()
                for suffix in ("gate-anchor", "gate-witness")}

    def replay(self, job, snapshots):
        store = self.runtime.task_contract_store
        for suffix, raw in snapshots.items():
            store._path(job["job_id"], suffix).write_bytes(raw)
        for suffix in ("review-required-anchor", "review-required-witness"):
            path = store._path(job["job_id"], suffix)
            if path.exists(): path.unlink()
        self.runtime.store.save(job)

    def assert_held(self, job):
        restarted = self.restarted()
        for operation in (lambda: restarted.show(job["job_id"]),
                          lambda: restarted.validate_execution_authority(job["job_id"], job.get("claimed_by")),
                          lambda: restarted.complete(job["job_id"]),
                          restarted.reconcile_progress):
            with self.assertRaises(RuntimeError): operation()

    def observations(self, job):
        return [event for event in self.runtime.progress.store.read(self.runtime.progress.logical_id(job))
                if event.job_id == job["job_id"] and event.event_type == "task_gate_observed"]

    def test_exact_r2_combined_replay_blocks_restart_execution_and_done(self):
        job = self.running()
        snapshots = self.snapshots(job)
        creation = {suffix: self.runtime.task_contract_store._path(job["job_id"], suffix).read_bytes()
                    for suffix in ("anchor", "witness")}
        self.strengthen(job)
        self.replay(job, snapshots)
        self.assert_held(job)
        self.assertEqual([event.detail for event in self.observations(job)], ["created", "review"])
        for suffix, raw in creation.items():
            self.assertEqual(self.runtime.task_contract_store._path(job["job_id"], suffix).read_bytes(), raw)

    def test_r2_created_job_replay_cannot_enqueue_or_run(self):
        job = self.runtime.create(self.fixture.payload())
        snapshots = self.snapshots(job)
        self.strengthen(job)
        self.replay(job, snapshots)
        with self.assertRaises(RuntimeError): self.restarted().enqueue(job["job_id"])
        self.assert_held(job)

    def test_strengthening_witness_deletion_does_not_erase_observation(self):
        job = self.running()
        strengthened = self.strengthen(job)
        for suffix in ("review-required-anchor", "review-required-witness"):
            self.runtime.task_contract_store._path(job["job_id"], suffix).unlink()
        self.assert_held(strengthened)
        self.assertEqual(len(self.observations(job)), 2)

    def test_missing_journal_cannot_be_refunded_or_recreated_by_reconciliation(self):
        job = self.running()
        strengthened = self.strengthen(job)
        path = self.runtime.progress.store.path(self.runtime.progress.logical_id(job))
        path.unlink()
        self.assert_held(strengthened)
        self.assertFalse(path.exists())
        # Even unrelated observations recreating a CORE journal cannot backfill
        # the missing gate creation/strengthening history.
        self.runtime.progress.emit(strengthened, "worker_exited", evidence_id="unrelated")
        self.assert_held(strengthened)
        self.assertEqual(self.observations(job), [])

    def test_independent_journal_snapshot_replay_alone_fails_closed(self):
        job = self.running()
        path = self.runtime.progress.store.path(self.runtime.progress.logical_id(job))
        baseline = path.read_bytes()
        strengthened = self.strengthen(job)
        path.write_bytes(baseline)
        self.assert_held(strengthened)

    def test_progress_schema_and_complete_chain_tampering_fail_closed(self):
        for attack in ("head", "protection"):
            with self.subTest(attack=attack):
                job = self.running()
                strengthened = self.strengthen(job)
                path = self.runtime.progress.store.path(self.runtime.progress.logical_id(job))
                connection = sqlite3.connect(path)
                try:
                    if attack == "head": connection.execute("UPDATE head SET hash=?", ("0" * 64,))
                    else: connection.execute("DROP TRIGGER no_delete")
                    connection.commit()
                finally: connection.close()
                self.assert_held(strengthened)
                # Remove this isolated corrupt fixture before creating another.
                self.runtime.store._path(job["job_id"]).unlink()

    def test_journal_event_deletion_is_protected(self):
        job = self.running()
        self.strengthen(job)
        path = self.runtime.progress.store.path(self.runtime.progress.logical_id(job))
        connection = sqlite3.connect(path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM events WHERE event_id=?", (self.observations(job)[-1].event_id,))
            connection.rollback()
        finally: connection.close()
        self.assertTrue(self.restarted().show(job["job_id"])["review_required"])

    def test_failure_before_observation_commit_preserves_old_authority(self):
        job = self.running()
        with patch.object(self.runtime.progress.store, "append", side_effect=ProgressError("uncommitted")):
            with self.assertRaises(RuntimeError): self.strengthen(job)
        self.assertFalse(self.restarted().show(job["job_id"])["review_required"])
        self.assertEqual(len(self.observations(job)), 1)

    def test_sqlite_rollback_does_not_accept_uncommitted_strengthening(self):
        job = self.running()
        original = self.runtime.progress.store._insert
        def interrupted(connection, history, previous, events):
            result = original(connection, history, previous, events)
            if any(event.event_type == "task_gate_observed" and event.detail == "review" for event in events):
                raise ProgressError("interrupted before SQLite commit")
            return result
        with patch.object(self.runtime.progress.store, "_insert", side_effect=interrupted):
            with self.assertRaises(RuntimeError): self.strengthen(job)
        self.assertFalse(self.restarted().show(job["job_id"])["review_required"])
        self.assertEqual(len(self.observations(job)), 1)

    def test_process_exit_after_independent_commit_survives_restart_and_replay(self):
        job = self.running()
        snapshots = self.snapshots(job)
        source = '''
import os, sys
from copy import deepcopy
from pathlib import Path
from runtime.core.jobs import JobRuntime
runtime = JobRuntime(Path(sys.argv[1]))
job = runtime.show(sys.argv[2]); candidate = deepcopy(job); candidate['review_required'] = True
runtime.task_contract_store._write_new = lambda *args: os._exit(0)
runtime._save(candidate)
raise AssertionError('crash boundary not reached')
'''
        subprocess.run([sys.executable, "-B", "-c", source, str(self.root / "jobs"), job["job_id"]],
                       check=True, timeout=30)
        self.replay(job, snapshots)
        self.assert_held(job)
        self.assertEqual(len(self.observations(job)), 2)

    def test_partial_persistence_after_observation_never_refunds_review(self):
        for method, failure_at in (("_write_new", 1), ("_write_new", 2), ("_replace", 1), ("_replace", 2)):
            with self.subTest(method=method, failure_at=failure_at):
                job = self.running()
                snapshots = self.snapshots(job)
                original = getattr(self.runtime.task_contract_store, method)
                calls = 0
                def interrupted(*args):
                    nonlocal calls
                    calls += 1
                    if calls == failure_at: raise OSError("process interrupted")
                    return original(*args)
                with patch.object(self.runtime.task_contract_store, method, side_effect=interrupted):
                    with self.assertRaises(RuntimeError): self.strengthen(job)
                self.assert_held(job)
                self.replay(job, snapshots)
                self.assert_held(job)
                self.assertEqual(len(self.observations(job)), 2)
                self.runtime.store._path(job["job_id"]).unlink()

    def test_crash_before_job_write_holds_even_when_gate_pair_is_intact(self):
        job = self.running()
        with patch.object(self.runtime.store, "save", side_effect=OSError("job write interrupted")):
            with self.assertRaises(OSError): self.strengthen(job)
        self.assert_held(job)
        self.assertEqual(len(self.observations(job)), 2)

    def test_concurrent_strengthening_is_idempotent_and_preserves_contract(self):
        job = self.running()
        candidate = deepcopy(job); candidate["review_required"] = True
        runtimes = [self.restarted(), self.restarted()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda runtime: runtime._save(deepcopy(candidate)), runtimes))
        self.assertTrue(all(result["review_required"] for result in results))
        history = self.observations(job)
        self.assertEqual(len(history), 2)
        current = self.restarted().show(job["job_id"])
        self.restarted()._save(current)
        self.assertEqual(self.observations(job), history)
        self.assertEqual(current["task_contract"], job["task_contract"])
        with self.assertRaises(RuntimeError): self.restarted()._save(job)

    def test_pre_f2_record_without_genesis_requires_explicit_recovery(self):
        job = self.runtime.create(self.fixture.payload())
        # F1 had creation/gate files but no gate journal observations.
        self.runtime.progress.store.path(self.runtime.progress.logical_id(job)).unlink()
        self.assert_held(job)

    def test_conflicting_gate_observation_cannot_grant_or_rebind_authority(self):
        job = self.running()
        self.runtime.progress.emit(job, "task_gate_observed", detail="review", evidence_id="0" * 64)
        self.assert_held(job)

    def test_interrupted_creation_cannot_recreate_history_for_same_identity(self):
        with patch.object(self.runtime.progress.store, "append", side_effect=ProgressError("creation interrupted")):
            with self.assertRaises(RuntimeError): self.runtime.create(self.fixture.payload())
        paths = list(self.runtime.task_contract_store.root.glob("*.anchor.json"))
        self.assertEqual(len(paths), 1)
        identity = paths[0].name.removesuffix(".anchor.json")
        original = paths[0].read_bytes()
        self.runtime.id_factory = lambda: identity
        with self.assertRaises(RuntimeError): self.runtime.create(self.fixture.payload())
        self.assertEqual(paths[0].read_bytes(), original)
        self.assertFalse(self.runtime.store.exists(identity))


if __name__ == "__main__": unittest.main()
