"""Bounded CORE-06R4 reproductions and F4 adversarial regressions, in TEMP."""

from __future__ import annotations

import json
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch

from runtime.actions.store import FileMutationArtifactStore, MutationArtifactError
from runtime.approvals.store import ApprovalStoreError, FileApprovalStore
from runtime.budget.store import ExecutionBudgetStoreError
from runtime.continuation.store import AuthorizedPlanStoreError
from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.execution.models import ExecutionResult
from runtime.providers.artifacts import FileProviderArtifactStore, ProviderArtifactError
from runtime.retry.store import RetryStoreError
from runtime.review.store import FileReviewStore, ReviewStoreError
from runtime.storage.execution_store import ExecutionStoreError
from runtime.storage.file_store import FileJobStore, JobStoreError
from runtime.tests import test_retry_f3 as f3
from runtime.tests import test_retry_repairs as repairs
from runtime.tests.test_retry_policy import RetryHarness


def excessively_nested_json():
    depth = sys.getrecursionlimit() + 100
    return b'[' * depth + b'0' + b']' * depth


class RetryF4Tests(RetryHarness, unittest.TestCase):
    worker = repairs.RetryRepairTests.worker
    retry_claim = repairs.RetryRepairTests.retry_claim
    controlled_executor = repairs.RetryRepairTests.controlled_executor
    remove = f3.RetryF3Tests.remove
    erase = f3.RetryF3Tests.erase

    @contextmanager
    def isolated_case(self):
        case = RetryF4Tests()
        case.setUp()
        try:
            yield case
        finally:
            case.tearDown()

    def failed_execution(self, **overrides):
        _, child = self.retry_claim(**overrides)
        before = self.jobs.store.load(child["job_id"])
        executor = repairs.ResultExecutor("provider_failure")
        outcome = self.worker(executor).run_claimed(child["job_id"])
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(executor.calls, 1)
        self.assertIsNotNone(self.jobs.retry_store.load_anchor("failure", child["job_id"]))
        self.assertIsNotNone(self.jobs.retry_store.load_anchor("runtime-failure", outcome.execution_id))
        return child, before, executor, outcome.execution_id

    def erase_consumption(self, child, execution_id, *, result=True):
        for kind in ("execution", "attempt-admission", "consumed-attempt"):
            self.erase(kind, child["job_id"])
        self.erase("admission", execution_id)
        if result:
            self.remove(self.executions._path(execution_id))

    def assert_held(self, child, executor, *, concurrent=False):
        restarted = self.restart()
        if concurrent:
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(
                    lambda _: self.worker(executor, runtime=restarted).run_claimed(child["job_id"]), range(8)))
        else:
            outcomes = [self.worker(executor, runtime=restarted).run_claimed(child["job_id"])]
        self.assertTrue(all(item.status == "worker_error" for item in outcomes))
        self.assertEqual(executor.calls, 1)

    def test_01_exact_r4_loss_and_running_job_replay_no_budget(self):
        child, before, executor, execution_id = self.failed_execution()
        self.assertNotIn("execution_budget", child)
        self.erase_consumption(child, execution_id)
        self.jobs.store.save(before)
        executor.code = None
        self.assert_held(child, executor, concurrent=True)
        self.assert_held(child, executor)

    def test_02_same_attack_with_shared_budget_does_not_refund(self):
        child, before, executor, execution_id = self.failed_execution(execution_budget={"max_execution_units": 3})
        self.erase_consumption(child, execution_id)
        self.jobs.store.save(before)
        executor.code = None
        self.assert_held(child, executor)
        state = self.worker(executor).budget_runtime.state(child["execution_budget"])
        self.assertEqual(state.state["dimensions"]["execution_units"]["consumed"], 1)

    def test_03_failed_attempt_alone_prevents_reexecution(self):
        child, before, executor, execution_id = self.failed_execution()
        self.erase_consumption(child, execution_id)
        self.erase("runtime-failure", execution_id)
        self.jobs.store.save(before)
        executor.code = None
        self.assert_held(child, executor)

    def test_04_runtime_failure_alone_prevents_reexecution(self):
        child, before, executor, execution_id = self.failed_execution()
        self.erase_consumption(child, execution_id)
        self.erase("failure", child["job_id"])
        self.jobs.store.save(before)
        executor.code = None
        self.assert_held(child, executor, concurrent=True)

    def test_05_either_runtime_failure_half_prevents_reexecution(self):
        for half in (0, 1):
            with self.subTest(erased_half=half), self.isolated_case() as case:
                child, before, executor, execution_id = case.failed_execution()
                case.erase_consumption(child, execution_id)
                case.erase("failure", child["job_id"])
                case.remove(case.jobs.retry_store._anchor_paths("runtime-failure", execution_id)[half])
                case.jobs.store.save(before)
                executor.code = None
                case.assert_held(child, executor)

    def test_06_either_failed_attempt_half_prevents_reexecution(self):
        for half in (0, 1):
            with self.subTest(erased_half=half), self.isolated_case() as case:
                child, before, executor, execution_id = case.failed_execution()
                case.erase_consumption(child, execution_id)
                case.erase("runtime-failure", execution_id)
                case.remove(case.jobs.retry_store._anchor_paths("failure", child["job_id"])[half])
                case.jobs.store.save(before)
                executor.code = None
                case.assert_held(child, executor)

    def test_07_crash_after_provenance_before_result_or_failure_is_hold(self):
        _, child = self.retry_claim()
        executor = repairs.ResultExecutor("provider_failure")
        with patch.object(self.executions, "create", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(child["job_id"])
        execution_id = self.jobs.retry_runtime.execution_reservation(child)["execution_id"]
        self.assertIsNone(self.jobs.retry_store.load_anchor("failure", child["job_id"]))
        self.assertIsNotNone(self.jobs.retry_store.load_anchor("runtime-failure", execution_id))
        self.erase_consumption(child, execution_id, result=False)
        executor.code = None
        self.assert_held(child, executor)

    def terminal_fixture(self, decision):
        first, child = self.retry_claim(max_attempts=2)
        before = self.jobs.store.load(child["job_id"])
        failure_class = "authority_failure" if decision == "STOP" else "lease_expired"
        self.fail(child, code="claim_lease_expired", failure_class=failure_class)
        result = self.jobs.retry_or_stop(child["job_id"])
        self.assertEqual(result["decision"]["decision"], decision)
        self.assertEqual(self.state(first)["revision"], 2)
        return first, child, before

    def assert_terminal_replay_held(self, decision):
        first, child, before = self.terminal_fixture(decision)
        terminal_state = deepcopy(self.state(first))
        self.jobs.store.save(before)
        restarted = self.restart()
        executor = repairs.ResultExecutor()
        outcome = self.worker(executor, runtime=restarted).run_claimed(child["job_id"])
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(executor.calls, 0)
        self.assertEqual(self.state(first), terminal_state)
        # Historical authentication is not authority to execute or reserve anew.
        historical = restarted.show(child["job_id"])
        restarted.retry_runtime.validate_authorization(historical, for_execution=False)
        with self.assertRaises(RetryStoreError):
            restarted.retry_runtime.validate_authorization(historical)
        with self.assertRaises(JobRuntimeError):
            restarted.validate_execution_authority(child["job_id"], "core06-worker")
        with self.assertRaises(RetryStoreError):
            restarted.retry_runtime.reserve_execution(historical, "forbidden-new-execution")

    def test_08_exact_r4_intact_stop_revokes_running_job_replay(self):
        self.assert_terminal_replay_held("STOP")

    def test_09_exact_r4_intact_replan_revokes_running_job_replay(self):
        self.assert_terminal_replay_held("REPLAN_REQUIRED")

    def test_10_terminal_rechecked_after_reservation_before_admission(self):
        for decision in ("STOP", "REPLAN_REQUIRED"):
            with self.subTest(decision=decision), self.isolated_case() as case:
                first, child = case.retry_claim(max_attempts=2)
                executor = repairs.ResultExecutor()
                worker = case.worker(executor)
                resolve = worker.resolver.resolve
                def terminate(job):
                    case.fail(child, code="claim_lease_expired", failure_class=(
                        "authority_failure" if decision == "STOP" else "lease_expired"))
                    case.assertEqual(case.jobs.retry_or_stop(child["job_id"])["decision"]["decision"], decision)
                    return resolve(job)
                with patch.object(worker.resolver, "resolve", side_effect=terminate):
                    outcome = worker.run_claimed(child["job_id"])
                case.assertIn(outcome.status, {"worker_error", "execution_reserved"})
                case.assertEqual(executor.calls, 0)
                case.assertEqual(case.state(first)["history"][-1]["decision"], decision)

    def test_11_terminal_history_does_not_break_structured_stop_reporting(self):
        for decision in ("STOP", "REPLAN_REQUIRED"):
            with self.subTest(decision=decision), self.isolated_case() as case:
                first, child, _ = case.terminal_fixture(decision)
                before = case.state(first)
                restarted = case.restart()
                self.assertEqual(restarted.show(child["job_id"])["status"], "failed")
                result = restarted.retry_or_stop(child["job_id"])
                self.assertEqual(result["decision"]["decision"], decision)
                self.assertIsNone(result["retry_job"])
                self.assertEqual(case.state(first), before)

    def test_12_terminal_history_revokes_direct_repair_requests(self):
        _, child, before = self.terminal_fixture("STOP")
        self.jobs.store.save(before)
        with self.assertRaises(RetryStoreError):
            self.jobs.retry_runtime.validate_repair_request(
                child, unit_ids=[child["retry_authorization"]["failed_unit_id"]])

    def corrupt_execution(self, corruption):
        identity = "corrupt-execution"
        result = ExecutionResult(execution_id=identity, job_id="fixture", status="succeeded",
            summary="Fixture", error=None, provider=None, started_at=self.clock_value, completed_at=self.clock_value)
        self.executions.create(None, result)
        path = self.executions._path(identity)
        self.assertIn(self.root.resolve(), path.resolve().parents)
        if corruption == "utf8":
            path.write_bytes(b"\xff\xfe\xff")
        elif corruption == "json":
            path.write_bytes(b'{"result":')
        elif corruption == "schema":
            value = self.executions.load_raw(identity)
            value["result"]["schema_version"] = "invalid"
            self.executions._write(path, value)
        elif corruption == "identity":
            value = self.executions.load_raw(identity)
            value["result"]["execution_id"] = "different-execution"
            self.executions._write(path, value)
        elif corruption == "deep_json":
            path.write_bytes(excessively_nested_json())
        elif corruption == "oversized_integer":
            path.write_bytes(b'{"schema_version":' + b'1' * 5000 + b'}')
        else:
            raise AssertionError("Unknown corruption fixture")
        return identity

    def assert_integrity_stop(self, job, outcome):
        self.assertFalse(outcome.result["error"]["retryable"])
        self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "malformed_state")
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_13_corrupt_artifact_reads_raise_typed_execution_store_errors(self):
        for corruption in ("utf8", "json", "schema", "identity", "deep_json", "oversized_integer"):
            with self.subTest(corruption=corruption), self.isolated_case() as case:
                identity = case.corrupt_execution(corruption)
                with self.assertRaises(ExecutionStoreError):
                    case.executions.load(identity)

    def test_14_exact_r4_utf8_corruption_is_stop_at_worker_boundary(self):
        job = self.running()
        identity = self.corrupt_execution("utf8")
        executor = repairs.ResultExecutor()
        with patch.object(executor, "execute", side_effect=lambda _: self.executions.load(identity).result):
            outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assert_integrity_stop(job, outcome)

    def test_15_json_schema_and_identity_corruption_are_non_retryable(self):
        for corruption in ("json", "schema", "identity", "deep_json", "oversized_integer"):
            with self.subTest(corruption=corruption), self.isolated_case() as case:
                job = case.running()
                identity = case.corrupt_execution(corruption)
                executor = repairs.ResultExecutor()
                with patch.object(executor, "execute", side_effect=lambda _: case.executions.load(identity).result):
                    outcome = case.worker(executor).run_claimed(job["job_id"])
                case.assert_integrity_stop(job, outcome)

    def test_16_corrupt_canonical_context_never_invokes_provider_adapter(self):
        for corruption in ("utf8", "json", "schema", "identity", "deep_json", "oversized_integer"):
            with self.subTest(corruption=corruption), self.isolated_case() as case:
                job = case.running()
                identity = case.corrupt_execution(corruption)
                executor = case.controlled_executor(lambda _: None)
                with patch.object(executor.context_builder, "build", side_effect=lambda _: case.executions.load(identity)), \
                        patch.object(executor.router.adapters["codex"], "execute") as adapter:
                    outcome = case.worker(executor).run_claimed(job["job_id"])
                adapter.assert_not_called()
                case.assert_integrity_stop(job, outcome)

    def test_17_corrupt_retry_provenance_cannot_be_reused_as_fresh_authority(self):
        for corruption in (b'\xff', b'{"job_id":', excessively_nested_json()):
            with self.subTest(corruption=corruption[:10]), self.isolated_case() as case:
                child, before, executor, execution_id = case.failed_execution()
                case.erase_consumption(child, execution_id)
                case.erase("failure", child["job_id"])
                for path in case.jobs.retry_store._anchor_paths("runtime-failure", execution_id):
                    path.write_bytes(corruption)
                case.jobs.store.save(before)
                executor.code = None
                case.assert_held(child, executor)

    def test_18_corrupt_existing_retry_result_is_hold_not_second_delegation(self):
        _, child = self.retry_claim()
        executor = repairs.ResultExecutor()
        outcome = self.worker(executor).run_claimed(child["job_id"])
        self.executions._path(outcome.execution_id).write_bytes(b'\xff')
        self.assert_held(child, executor)

    def test_19_unrelated_valid_failure_provenance_does_not_block_fresh_retry(self):
        self.failed_execution()
        _, child = self.retry_claim()
        executor = repairs.ResultExecutor()
        outcome = self.worker(executor).run_claimed(child["job_id"])
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(executor.calls, 1)

    def test_20_execution_store_failure_propagates_without_provider_retry(self):
        job = self.running()
        executor = self.controlled_executor(lambda _: None)
        with patch.object(executor.context_builder, "build", side_effect=ExecutionStoreError("Trusted artifact integrity failure")), \
                patch.object(executor.router.adapters["codex"], "execute") as adapter:
            outcome = self.worker(executor).run_claimed(job["job_id"])
        adapter.assert_not_called()
        self.assert_integrity_stop(job, outcome)

    def corrupt_reader(self, name, corruption):
        stores = {
            "job": (FileJobStore, JobStoreError),
            "provider": (FileProviderArtifactStore, ProviderArtifactError),
            "mutation": (FileMutationArtifactStore, MutationArtifactError),
            "approval": (FileApprovalStore, ApprovalStoreError),
            "review": (FileReviewStore, ReviewStoreError),
        }
        directory = self.root / "corrupt-reader" / name
        directory.mkdir(parents=True)
        if name in stores:
            constructor, error = stores[name]
            store = constructor(directory)
            path = store._path("corrupt-record")
            read = lambda: store.load("corrupt-record")
        else:
            path = directory / "corrupt-record.json"
            readers = {
                "plan": (lambda: self.jobs.authorized_plan_store._read(path, "fixture", "plan"), AuthorizedPlanStoreError),
                "budget": (lambda: self.jobs.budget_store._read(path, "budget"), ExecutionBudgetStoreError),
                "retry": (lambda: self.jobs.retry_store._read(path, "retry"), RetryStoreError),
            }
            read, error = readers[name]
        self.assertIn(self.root.resolve(), path.resolve().parents)
        path.write_bytes(corruption)
        return read, error

    def test_21_shared_trusted_readers_normalize_canonical_decoding_corruption(self):
        for name in ("job", "provider", "mutation", "approval", "review", "plan", "budget", "retry"):
            for corruption in (b'\xff', b'{"schema_version":'):
                with self.subTest(store=name, corruption=corruption[:10]), self.isolated_case() as case:
                    read, error = case.corrupt_reader(name, corruption)
                    with self.assertRaises(error):
                        read()
                    if name == "job":
                        with self.assertRaises(JobStoreError):
                            FileJobStore(case.root / "corrupt-reader" / name).list()
            # Primitive plan/budget/retry readers deliberately return JSON of any
            # shape; schema validation belongs to their callers. Test an actual
            # decoder exception separately from a valid deeply nested array.
            with self.subTest(store=name, decoder="recursion"), self.isolated_case() as case:
                read, error = case.corrupt_reader(name, b'{}')
                with patch("json.loads", side_effect=RecursionError("Canonical decoder depth exhausted")):
                    with self.assertRaises(error):
                        read()

    def test_22_shared_canonical_corruption_never_reaches_provider_execution(self):
        for name in ("job", "provider", "mutation", "approval", "review", "plan", "budget", "retry"):
            for corruption in (b'\xff', b'{"schema_version":'):
                with self.subTest(store=name, corruption=corruption[:10]), self.isolated_case() as case:
                    job = case.running()
                    read, _ = case.corrupt_reader(name, corruption)
                    executor = case.controlled_executor(lambda _: None)
                    with patch.object(executor.context_builder, "build", side_effect=lambda _: read()), \
                            patch.object(executor.router.adapters["codex"], "execute") as adapter:
                        outcome = case.worker(executor).run_claimed(job["job_id"])
                    adapter.assert_not_called()
                    case.assert_integrity_stop(job, outcome)

    def test_23_boolean_execution_envelope_version_cannot_authorize_retry(self):
        child, _, executor, execution_id = self.failed_execution()
        path = self.executions._path(execution_id)
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["schema_version"] = True
        path.write_text(json.dumps(artifact), encoding="utf-8")

        with self.assertRaises(JobRuntimeError):
            self.jobs.retry_or_stop(child["job_id"])

        self.assertEqual(executor.calls, 1)
        self.assertFalse(
            any(job.get("parent_job_id") == child["job_id"] for job in self.jobs.list())
        )


if __name__ == "__main__":
    unittest.main()
