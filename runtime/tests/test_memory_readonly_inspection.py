"""Bounded trace inspection through real journals and canonical evidence owners."""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from runtime.core.task_contract import (
    TaskContractError, completion, inspection_load, verify_completion,
)
from runtime.progress.models import ProgressError, ProgressEvent
from runtime.progress.store import (
    MAX_JOB_EVENTS, ProgressStore, inspection_active, inspection_read, readonly_inspection,
)
from runtime.review.store import FileReviewStore, ReviewStoreError
from runtime.storage.execution_store import ExecutionStoreError
from runtime.tests import test_graph as graph_fixtures
from runtime.tests import test_review as review_fixtures
from runtime.tests import test_task_contract as task_fixtures
from runtime.tests import test_task_contract_f1 as approval_fixtures


class LearningArtifactReadBoundaryTests(unittest.TestCase):
    def test_oversized_learning_artifact_is_denied_before_any_mutation(self):
        from runtime.approvals.store import FileApprovalStore
        from runtime.memory.learning import learning_inspection
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = FileApprovalStore(root / "approvals")
            path = store._learning_path("alpha", "genesis")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"x" * (128 * 1024 + 1))
            with no_persistent_mutations(self, root), learning_inspection(), self.assertRaises(ValueError):
                store._read_learning("alpha", "genesis")


def filesystem_snapshot(root):
    """Include names, bytes, identities and modification times, including dirs.

    Access times are filesystem-managed read metadata, not journal/evidence
    writes. They are intentionally excluded from the persistent-state claim.
    """
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.stat()
        result[str(path.relative_to(root))] = (
            info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        )
    return result


@contextmanager
def no_persistent_mutations(test, root):
    before = filesystem_snapshot(root)
    original_open, original_connect = Path.open, sqlite3.connect

    def read_open(path, mode="r", *args, **kwargs):
        test.assertFalse(any(flag in mode for flag in "wax+"), (path, mode))
        return original_open(path, mode, *args, **kwargs)

    def memory_connect(database, *args, **kwargs):
        test.assertEqual(database, ":memory:")
        return original_connect(database, *args, **kwargs)

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "open", read_open))
            stack.enter_context(patch("sqlite3.connect", memory_connect))
            for target in ("pathlib.Path.mkdir", "pathlib.Path.unlink", "pathlib.Path.rmdir",
                           "os.replace", "os.rename", "os.remove", "os.unlink",
                           "tempfile.mkstemp", "tempfile.NamedTemporaryFile",
                           "runtime.storage.file_store.FileJobStore.claim_transaction",
                           "runtime.progress.store.ProgressStore._transaction",
                           "runtime.evals.runner.EvalRunner.run_persisted",
                           "runtime.evals.store.FileEvalStore.create"):
                stack.enter_context(patch(target, side_effect=AssertionError("Unexpected mutation: " + target)))
            yield
    finally:
        test.assertEqual(filesystem_snapshot(root), before)


def legacy_schema(path, version):
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE recovery")
        if version == 0:
            connection.execute("DROP TABLE pending")
        connection.execute(f"PRAGMA user_version={version}")
    connection.close()


class JournalInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = ProgressStore(self.root / "progress")
        self.event = ProgressEvent("job_started", "logical-1", "job-1")

    def populated(self):
        self.store.append(self.event)
        return self.store.path("logical-1")

    def test_current_schema_repeated_inspection_has_no_locks_writes_or_cache(self):
        self.populated()
        with no_persistent_mutations(self, self.root):
            for _ in range(3):
                self.assertEqual(self.store.read("logical-1", inspection=True), [self.event])
        self.assertFalse(inspection_active())
        self.store.append(ProgressEvent("worker_exited", "logical-1", "job-1"))
        with no_persistent_mutations(self, self.root):
            self.assertEqual(len(self.store.read("logical-1", inspection=True)), 2)

    def test_missing_journal_fails_without_creating_root_and_default_remains_empty(self):
        with no_persistent_mutations(self, self.root):
            with self.assertRaises(ProgressError):
                self.store.read("missing", inspection=True)
            self.assertEqual(self.store.read("missing"), [])
        self.assertFalse(self.store.root.exists())

    def test_legacy_zero_and_one_fail_without_migration_default_still_migrates(self):
        for version in (0, 1):
            with self.subTest(version=version):
                store = ProgressStore(self.root / str(version))
                store.append(self.event)
                path = store.path("logical-1")
                legacy_schema(path, version)
                with no_persistent_mutations(self, self.root):
                    with self.assertRaises(ProgressError):
                        store.read("logical-1", inspection=True)
                self.assertFalse(inspection_active())
                self.assertEqual(store.read("logical-1"), [self.event])
                with sqlite3.connect(path) as connection:
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
                connection.close()

    def test_tampered_head_schema_pending_and_recovery_fail_without_repair(self):
        for sql in ("UPDATE head SET hash='tampered'", "DROP TRIGGER no_delete",
                    "INSERT INTO pending VALUES ('job-1','bad','bad','[]')",
                    "INSERT INTO recovery VALUES ('job-1',0,'{}')",
                    "INSERT INTO events VALUES (2,'bad','{}','bad','bad')"):
            with self.subTest(sql=sql):
                store = ProgressStore(self.root / hashlib.sha256(sql.encode()).hexdigest())
                store.append(self.event)
                with sqlite3.connect(store.path("logical-1")) as connection:
                    connection.execute(sql)
                connection.close()
                with no_persistent_mutations(self, self.root):
                    with self.assertRaises(ProgressError):
                        store.read("logical-1", inspection=True)

    def test_sidecars_rejected_before_sqlite_access(self):
        path = self.populated()
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            sidecar.write_bytes(b"")
            with self.subTest(suffix=suffix), no_persistent_mutations(self, self.root):
                with patch("sqlite3.connect", side_effect=AssertionError("SQLite accessed")):
                    with self.assertRaises(ProgressError):
                        self.store.read("logical-1", inspection=True)
            sidecar.unlink()

    def test_wal_header_rejected_without_recovery(self):
        path = self.populated()
        with sqlite3.connect(path) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        connection.close()
        with no_persistent_mutations(self, self.root):
            with patch("sqlite3.connect", side_effect=AssertionError("SQLite accessed")):
                with self.assertRaises(ProgressError):
                    self.store.read("logical-1", inspection=True)

    def test_journal_event_boundary_is_preserved(self):
        self.store.append_many([ProgressEvent("worker_exited", "logical-1", "job-1",
                                             evidence_id=f"boundary-{i}") for i in range(MAX_JOB_EVENTS)])
        with no_persistent_mutations(self, self.root):
            self.assertEqual(len(self.store.read("logical-1", inspection=True)), MAX_JOB_EVENTS)
        with self.assertRaises(ProgressError):
            self.store.append(self.event)
        with no_persistent_mutations(self, self.root):
            with patch("runtime.progress.store.MAX_JOB_EVENTS", MAX_JOB_EVENTS - 1):
                with self.assertRaises(ProgressError):
                    self.store.read("logical-1", inspection=True)

    def test_missing_deserialize_fails_closed_without_disk_fallback(self):
        self.populated()
        class NoDeserialize:
            def close(self):
                pass
        with no_persistent_mutations(self, self.root):
            with patch("sqlite3.connect", return_value=NoDeserialize()) as connect:
                with self.assertRaises(ProgressError):
                    self.store.read("logical-1", inspection=True)
                connect.assert_called_once_with(":memory:")

    def test_mutation_during_journal_validation_is_detected_and_not_repaired(self):
        path = self.populated()
        original = self.store._read
        injected = path.stat().st_mtime_ns + 2_000_000_000
        def mutate(*args):
            result = original(*args)
            os.utime(path, ns=(path.stat().st_atime_ns, injected))
            return result
        # The adversary deliberately changes the fixture; inspection must not
        # erase that change or return the previously validated snapshot.
        with patch.object(self.store, "_read", side_effect=mutate):
            with self.assertRaises(ProgressError):
                self.store.read("logical-1", inspection=True)
        self.assertEqual(path.stat().st_mtime_ns, injected)
        self.assertFalse(inspection_active())

    def test_shared_byte_budget_exact_boundary_and_boundary_plus_one(self):
        paths = [self.root / name for name in ("a", "b")]
        for path in paths:
            path.write_bytes(b"abc")
        # Two reads plus the final complete-byte rechecks cost exactly 12.
        with no_persistent_mutations(self, self.root):
            with patch("runtime.progress.store.MAX_DATABASE_BYTES", 12):
                with readonly_inspection():
                    for path in paths:
                        self.assertEqual(inspection_read(path), b"abc")
            with patch("runtime.progress.store.MAX_DATABASE_BYTES", 11):
                with self.assertRaises(ProgressError):
                    with readonly_inspection():
                        for path in paths:
                            inspection_read(path)
        self.assertFalse(inspection_active())

    def test_links_and_nonregular_evidence_are_rejected_before_open(self):
        path = self.root / "record"
        path.write_bytes(b"abc")
        with no_persistent_mutations(self, self.root), readonly_inspection():
            with patch.object(Path, "is_symlink", return_value=True), patch.object(Path, "open", side_effect=AssertionError("link opened")):
                with self.assertRaises(ProgressError):
                    inspection_read(path)
            with patch.object(Path, "open", side_effect=AssertionError("directory opened")):
                with self.assertRaises(ProgressError):
                    inspection_read(self.root)

    def test_inspection_context_rejects_journal_mutation(self):
        self.populated()
        with no_persistent_mutations(self, self.root), readonly_inspection():
            with self.assertRaises(ProgressError):
                self.store.append(ProgressEvent("worker_exited", "logical-1", "job-1"))

    def test_late_sidecar_is_detected_at_request_exit_and_not_recovered(self):
        path = self.populated()
        sidecar = Path(str(path) + "-journal")
        with self.assertRaises(ProgressError):
            with readonly_inspection():
                self.store.read("logical-1")
                sidecar.write_bytes(b"adversary-created sidecar")
        self.assertEqual(sidecar.read_bytes(), b"adversary-created sidecar")
        self.assertFalse(inspection_active())


class EvidenceInspectionTests(unittest.TestCase):
    def fixture(self, cls=task_fixtures.TaskContractTests):
        fixture = cls()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        return fixture

    def completed(self):
        fixture = self.fixture()
        job, outcome = fixture.run_job()
        self.assertEqual(outcome.status, "completed")
        return fixture, fixture.runtime.store.load(job["job_id"]), outcome

    def test_execution_task_and_completion_inspect_exact_evidence_repeatedly_without_writes(self):
        fixture, job, outcome = self.completed()
        with no_persistent_mutations(self, fixture.root):
            for _ in range(2):
                record = fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
                self.assertEqual(record.request["task_contract"], job["task_contract"])
                self.assertEqual(record.result.execution_id, job["task_completion"]["execution_id"])
                fixture.runtime.task_contract_store.verify(job, inspection=True)
                verify_completion(fixture.runtime, job, inspection=True)
        self.assertFalse(inspection_active())

    def test_nested_legacy_journal_reads_fail_without_migration(self):
        fixture, job, outcome = self.completed()
        path = fixture.runtime.progress.store.path(fixture.runtime.progress.logical_id(job))
        legacy_schema(path, 1)
        with no_persistent_mutations(self, fixture.root):
            for reader in (lambda: fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True),
                           lambda: fixture.runtime.task_contract_store.verify(job, inspection=True),
                           lambda: verify_completion(fixture.runtime, job, inspection=True)):
                with self.assertRaises(ValueError):
                    reader()
        self.assertEqual(fixture.runtime.show(job["job_id"])["status"], "completed")

    def test_execution_missing_tampered_record_witness_and_job_fail_without_repair_or_cache(self):
        fixture, job, outcome = self.completed()
        paths = [fixture.executions._path(outcome.execution_id),
                 fixture.executions._decision_path(outcome.execution_id, "result", "witness"),
                 fixture.executions._decision_path(outcome.execution_id, "intent", "anchor"),
                 fixture.runtime.store._path(job["job_id"])]
        for path in paths:
            original = path.read_bytes()
            for attack in ("missing", "tampered"):
                with self.subTest(path=path.name, attack=attack):
                    fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
                    if attack == "missing":
                        path.unlink()
                    else:
                        path.write_bytes(b"{}")
                    with no_persistent_mutations(self, fixture.root):
                        with self.assertRaises(ExecutionStoreError):
                            fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
                    path.write_bytes(original)

    def test_exact_project_execution_attempt_contract_review_and_completion_bindings(self):
        fixture, job, _ = self.completed()
        for field, value in (("project_id", "another-project"), ("attempt", job["attempt"] + 1),
                             ("task", "substituted task"), ("review_required", True),
                             ("job_id", "another-job")):
            candidate = deepcopy(job)
            candidate[field] = value
            with self.subTest(field=field), no_persistent_mutations(self, fixture.root):
                with self.assertRaises(ValueError):
                    verify_completion(fixture.runtime, candidate, inspection=True)
        for field, value in (("execution_id", "another-execution"), ("contract_digest", "0" * 64),
                             ("review_ref", "runtime-review:substitute"), ("accepted_at", "2026-10-03T12:00:00Z"),
                             ("eval_digest", "0" * 64), ("execution_store_root", str(fixture.root / "other"))):
            candidate = deepcopy(job)
            candidate["task_completion"][field] = value
            with self.subTest(field=field), no_persistent_mutations(self, fixture.root):
                with self.assertRaises(ValueError):
                    verify_completion(fixture.runtime, candidate, inspection=True)
        candidate = deepcopy(job)
        candidate["task_contract"]["acceptance_criteria"][0]["description"] = "substituted acceptance"
        with no_persistent_mutations(self, fixture.root), self.assertRaises(ValueError):
            verify_completion(fixture.runtime, candidate, inspection=True)

    def test_missing_or_tampered_completion_receipt_and_eval_fail_without_repair(self):
        from runtime.evals.store import FileEvalStore
        fixture, job, _ = self.completed()
        paths = [fixture.runtime.task_contract_store._path(job["job_id"], "completion-witness"),
                 FileEvalStore(fixture.root / "evals")._path(job["task_completion"]["eval_id"])]
        for path in paths:
            original = path.read_bytes()
            for attack in ("missing", "tampered"):
                with self.subTest(path=path.name, attack=attack):
                    if attack == "missing":
                        path.unlink()
                    else:
                        path.write_bytes(b"{}")
                    with no_persistent_mutations(self, fixture.root), self.assertRaises(ValueError):
                        verify_completion(fixture.runtime, job, inspection=True)
                    path.write_bytes(original)

    def test_imported_execution_is_observation_and_cannot_gain_authority(self):
        fixture, _, outcome = self.completed()
        record = fixture.executions.load(outcome.execution_id, inspection=True)
        imported = replace(record.result, execution_id="imported-observation")
        fixture.executions.create(None, imported)
        with no_persistent_mutations(self, fixture.root):
            self.assertIsNone(fixture.executions.load(imported.execution_id, inspection=True).request)
            with self.assertRaises(ExecutionStoreError):
                fixture.executions.load(imported.execution_id, require_authority=True, inspection=True)

    def test_selected_inspection_does_not_discover_or_load_unrelated_records(self):
        fixture, job, outcome = self.completed()
        unrelated = fixture.executions._path("unselected")
        unrelated.write_bytes(b"invalid unrelated evidence")
        with no_persistent_mutations(self, fixture.root):
            with patch.object(Path, "glob", side_effect=AssertionError("record discovery")), patch.object(Path, "rglob", side_effect=AssertionError("recursive discovery")):
                fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
                verify_completion(fixture.runtime, job, inspection=True)

    def test_oversized_legacy_material_fails_before_open_and_default_content_is_unchanged(self):
        fixture, _, outcome = self.completed()
        original = fixture.executions.load(outcome.execution_id, inspection=True)
        imported = replace(original.result, execution_id="large-imported-observation")
        path = fixture.executions.create(None, imported)
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (512 * 1024 + 1 - len(raw)))
        self.assertEqual(fixture.executions.load(imported.execution_id).result, imported)
        with no_persistent_mutations(self, fixture.root):
            with patch.object(Path, "open", side_effect=AssertionError("oversized record opened")):
                with self.assertRaises(ExecutionStoreError):
                    fixture.executions.load(imported.execution_id, inspection=True)

    def test_output_snapshot_loads_preserve_material_and_canonical_owner_validation(self):
        from runtime.actions.store import FileMutationArtifactStore
        from runtime.providers.artifacts import FileProviderArtifactStore
        from runtime.providers.models import ProviderExecutionResult, ProviderSelection
        from runtime.evals.store import FileEvalStore
        fixture, job, _ = self.completed()
        provider = FileProviderArtifactStore(fixture.root / "provider-output")
        provider.create("output", ProviderSelection("codex", "codex", "codex", False, None),
                        ProviderExecutionResult(status="succeeded", stdout="exact material: \u00e9",
                                                stderr="", exit_code=0))
        mutation = FileMutationArtifactStore(fixture.root / "mutation-output")
        mutation.create("output", {"execution_id": "output", "job_id": job["job_id"]},
                        "exact observed diff", max_diff_bytes=1024)
        expected = [(owner, owner.load("output")) for owner in (provider, mutation)]
        evals = FileEvalStore(fixture.root / "evals")
        with no_persistent_mutations(self, fixture.root), readonly_inspection():
            for owner, value in expected:
                self.assertEqual(inspection_load(owner, "output"), value)
            with patch.object(evals.validator, "validate", wraps=evals.validator.validate) as validate:
                evaluated = inspection_load(evals, job["task_completion"]["eval_id"])
                self.assertEqual(evaluated.status, "pass")
                validate.assert_called_once()

    def test_review_authority_and_digest_checks_are_preserved_without_writes(self):
        fixture = self.fixture(review_fixtures.ReviewRuntimeTests)
        job, request, result = fixture.prepare_execution()
        reviewed = fixture.reviewer_runtime(review_fixtures.FakeReviewer("PASS")).run(job, request, result)
        review_id = reviewed.result.review_id
        with no_persistent_mutations(self, fixture.root):
            for _ in range(2):
                value = fixture.review_store.load(review_id, require_authority=True, inspection=True)
                self.assertEqual(value["result"]["execution_id"], request.execution_id)
                self.assertEqual(value["result"]["decision"], "PASS")
        path = fixture.review_store._path(review_id)
        original = path.read_bytes()
        value = json.loads(original)
        value["result"]["execution_id"] = "substituted"
        path.write_text(json.dumps(value))
        with no_persistent_mutations(self, fixture.root), self.assertRaises(ReviewStoreError):
            fixture.review_store.load(review_id, require_authority=True, inspection=True)
        path.write_bytes(original)
        witness = fixture.review_store._decisions()._decision_path(review_id, "review-intent", "witness")
        witness.unlink()
        with no_persistent_mutations(self, fixture.root), self.assertRaises(ReviewStoreError):
            fixture.review_store.load(review_id, require_authority=True, inspection=True)

    def test_review_nested_legacy_journal_fails_without_migration(self):
        fixture = self.fixture(review_fixtures.ReviewRuntimeTests)
        job, request, result = fixture.prepare_execution()
        reviewed = fixture.reviewer_runtime(review_fixtures.FakeReviewer("PASS")).run(job, request, result)
        legacy_schema(fixture.runtime.progress.store.path(fixture.runtime.progress.logical_id(job)), 1)
        with no_persistent_mutations(self, fixture.root), self.assertRaises(ReviewStoreError):
            fixture.review_store.load(reviewed.result.review_id, require_authority=True, inspection=True)

    def test_execution_and_completion_approvals_use_canonical_validation_and_exact_pins(self):
        fixture = self.fixture(approval_fixtures.TaskContractF1Tests)
        job, store, completion_id, execution_id = fixture.approved_completion(execution_approval=True)
        with no_persistent_mutations(self, fixture.root):
            verify_completion(fixture.runtime, job, inspection=True)
        for identity in (execution_id, completion_id):
            path = store._path(identity)
            original = path.read_bytes()
            value = json.loads(original)
            value["status"] = "REJECTED"
            path.write_text(json.dumps(value))
            with self.subTest(identity=identity), no_persistent_mutations(self, fixture.root):
                with self.assertRaises(ValueError):
                    verify_completion(fixture.runtime, job, inspection=True)
            path.write_bytes(original)

    def test_mutation_after_nested_read_is_detected_before_return(self):
        fixture, job, outcome = self.completed()
        path = fixture.executions._path(outcome.execution_id)
        original = fixture.executions.verify_decision
        injected = path.stat().st_mtime_ns + 2_000_000_000
        def mutate(*args, **kwargs):
            original(*args, **kwargs)
            os.utime(path, ns=(path.stat().st_atime_ns, injected))
        with patch.object(fixture.executions, "verify_decision", side_effect=mutate):
            with self.assertRaises(ProgressError):
                fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
        self.assertEqual(path.stat().st_mtime_ns, injected)
        self.assertFalse(inspection_active())

    def test_final_recheck_detects_changed_bytes_even_when_size_and_mtime_are_restored(self):
        fixture, _, outcome = self.completed()
        path = fixture.executions._path(outcome.execution_id)
        raw, info = path.read_bytes(), path.stat()
        self.assertEqual(raw[-1:], b"\n")
        original = fixture.executions.verify_decision
        def mutate(*args, **kwargs):
            original(*args, **kwargs)
            path.write_bytes(raw[:-1] + b" ")
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        with patch.object(fixture.executions, "verify_decision", side_effect=mutate):
            with self.assertRaises(ProgressError):
                fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
        self.assertEqual(path.read_bytes(), raw[:-1] + b" ")
        self.assertFalse(inspection_active())

    def test_graph_bound_inspection_fails_before_outside_owners(self):
        fixture = self.fixture(graph_fixtures.GraphTests)
        root = fixture.create([fixture.node("a")])
        fixture.graph.advance(root["job_id"])
        outcome = fixture.execute(root, "a")
        self.assertEqual(outcome.status, "completed")
        job = fixture.jobs.store.load(outcome.job_id)
        with no_persistent_mutations(self, fixture.root):
            with patch("runtime.graph.runtime.validate_graph_job", side_effect=AssertionError("graph owner called")), patch("runtime.core.jobs.JobRuntime", side_effect=AssertionError("outside runtime created")):
                with self.assertRaises(ExecutionStoreError):
                    fixture.executions.load(outcome.execution_id, require_authority=True, inspection=True)
                with self.assertRaises(TaskContractError):
                    verify_completion(fixture.jobs, job, inspection=True)

    def test_inspection_cannot_evaluate_or_create_completion_evidence(self):
        fixture, job, _ = self.completed()
        with no_persistent_mutations(self, fixture.root), readonly_inspection():
            with self.assertRaises(TaskContractError):
                completion(fixture.runtime, job)
            with self.assertRaises(TaskContractError):
                inspection_load(object(), "record")

    def test_strict_opt_in_flags_fail_before_io(self):
        fixture, job, outcome = self.completed()
        review_store = FileReviewStore(fixture.root / "missing-reviews")
        with no_persistent_mutations(self, fixture.root):
            for flag in (1, "yes", None):
                for reader in (lambda: fixture.executions.load(outcome.execution_id, inspection=flag),
                               lambda: fixture.runtime.task_contract_store.verify(job, inspection=flag),
                               lambda: verify_completion(fixture.runtime, job, inspection=flag),
                               lambda: review_store.load("missing", inspection=flag),
                               lambda: fixture.runtime.progress.store.read("missing", inspection=flag)):
                    with self.subTest(flag=flag), self.assertRaises(ValueError):
                        reader()


if __name__ == "__main__":
    unittest.main()
