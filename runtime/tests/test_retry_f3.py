"""CORE-06R3 exact attacks and bounded F3 adversarial regressions, in TEMP."""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch

from runtime.actions.models import ExecutionScope, scope_path_contains
from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.execution.failures import (
    AUTHORITY_FAILURES, INTEGRITY_FAILURES, POLICY_FAILURES, TRUSTED_EXECUTION_FAILURES,
)
from runtime.execution.models import ExecutionResult
from runtime.retry.models import MAX_HISTORY, history_entry_digest, repair_scope
from runtime.retry.store import RetryStoreError
from runtime.storage.execution_store import ExecutionStoreError
from runtime.tests import test_retry_f2a as f2a
from runtime.tests import test_retry_repairs as repairs
from runtime.tests.test_retry_policy import RetryHarness


class RetryF3Tests(RetryHarness, unittest.TestCase):
    worker = repairs.RetryRepairTests.worker
    retry_claim = repairs.RetryRepairTests.retry_claim
    controlled_executor = repairs.RetryRepairTests.controlled_executor
    rollback_fixture = repairs.RetryRepairTests.rollback_fixture
    approve = staticmethod(repairs.RetryRepairTests.approve)
    remove = f2a.RetryF2ATests.remove
    approval_failed_parent = f2a.RetryF2ATests.approval_failed_parent

    @contextmanager
    def isolated_case(self):
        case = RetryF3Tests()
        case.setUp()
        try:
            yield case
        finally:
            case.tearDown()

    def erase(self, kind, identity):
        for path in self.jobs.retry_store._anchor_paths(kind, identity):
            self.remove(path)

    def consumed_fixture(self, **changes):
        _, child = self.retry_claim(**changes)
        executor = f2a.CrashExecutor()
        with self.assertRaises(KeyboardInterrupt):
            self.worker(executor).run_claimed(child["job_id"])
        reservation = self.jobs.retry_runtime.execution_reservation(child)
        self.assertEqual(executor.calls, 1)
        return child, executor, reservation["execution_id"]

    def assert_redelivery_held(self, child, executor):
        restarted = self.restart()
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(
                lambda _: self.worker(executor, runtime=restarted).run_claimed(child["job_id"]),
                range(6),
            ))
        self.assertTrue(all(item.status == "worker_error" for item in outcomes))
        self.assertEqual(executor.calls, 1)
        self.assertEqual(
            self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status,
            "worker_error",
        )
        self.assertEqual(executor.calls, 1)

    def test_01_exact_r3_reservation_and_attempt_admission_loss_no_budget(self):
        child, executor, execution_id = self.consumed_fixture()
        self.assertNotIn("execution_budget", child)
        self.erase("execution", child["job_id"])
        self.erase("attempt-admission", child["job_id"])
        self.assertIsNotNone(self.jobs.retry_store.load_anchor("admission", execution_id))
        self.assertIsNotNone(self.jobs.retry_store.load_anchor("consumed-attempt", child["job_id"]))
        self.assert_redelivery_held(child, executor)

    def test_02_same_loss_with_shared_budget_cannot_refund_or_delegate(self):
        child, executor, _ = self.consumed_fixture(execution_budget={"max_execution_units": 3})
        self.erase("execution", child["job_id"])
        self.erase("attempt-admission", child["job_id"])
        self.assert_redelivery_held(child, executor)
        budget = self.worker(executor).budget_runtime.state(child["execution_budget"])
        self.assertEqual(budget.state["dimensions"]["execution_units"]["consumed"], 1)

    def test_03_all_attempt_indexes_lost_surviving_execution_admission_is_hold(self):
        child, executor, execution_id = self.consumed_fixture()
        for kind in ("execution", "attempt-admission", "consumed-attempt"):
            self.erase(kind, child["job_id"])
        self.assertIsNotNone(self.jobs.retry_store.load_anchor("admission", execution_id))
        self.assert_redelivery_held(child, executor)

    def test_04_either_surviving_admission_half_prevents_reexecution(self):
        for erased_half in (0, 1):
            with self.subTest(erased_half=erased_half):
                child, executor, execution_id = self.consumed_fixture()
                for kind in ("execution", "attempt-admission", "consumed-attempt"):
                    self.erase(kind, child["job_id"])
                self.remove(self.jobs.retry_store._anchor_paths("admission", execution_id)[erased_half])
                self.assert_redelivery_held(child, executor)

    def test_05_missing_consumed_half_or_pair_is_not_legacy_fresh_work(self):
        for half in (0, 1, None):
            with self.subTest(half=half):
                child, executor, _ = self.consumed_fixture()
                if half is None:
                    self.erase("consumed-attempt", child["job_id"])
                else:
                    self.remove(self.jobs.retry_store._anchor_paths("consumed-attempt", child["job_id"])[half])
                self.assert_redelivery_held(child, executor)

    def test_06_crash_after_consumption_before_reservation_never_delegates(self):
        for after_creation in (False, True):
            with self.subTest(after_creation=after_creation):
                _, child = self.retry_claim()
                executor = repairs.ResultExecutor()
                store = self.jobs.retry_store
                write = store._write_new
                def interrupted(path, value):
                    write(path, value)
                    if ("consumed-attempt" in path.parts if after_creation
                            else ".consumed-attempt" in path.parts):
                        raise KeyboardInterrupt("Consumed evidence precedes reservation")
                with patch.object(store, "_write_new", side_effect=interrupted):
                    with self.assertRaises(KeyboardInterrupt):
                        self.worker(executor).run_claimed(child["job_id"])
                self.assertEqual(
                    self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status,
                    "worker_error",
                )
                self.assertEqual(executor.calls, 0)

    def test_07_persisted_success_alone_cannot_reopen_lost_attempt_indexes(self):
        _, child = self.retry_claim()
        executor = repairs.ResultExecutor()
        with patch.object(self.jobs, "record_execution_success", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(child["job_id"])
        execution_id = self.jobs.retry_runtime.execution_reservation(child)["execution_id"]
        for kind in ("execution", "attempt-admission", "consumed-attempt"):
            self.erase(kind, child["job_id"])
        self.erase("admission", execution_id)
        self.assertEqual(self.executions.load(execution_id).result.status, "succeeded")
        self.assert_redelivery_held(child, executor)

    def replay_terminal_suffix(self, first, old, *, erase_acceptance=False):
        store = self.jobs.retry_store
        policy_id = first["retry_policy"]["policy_id"]
        newest = self.state(first)["history"][-1]
        for path in (
            store._event_path(policy_id, 2, history_entry_digest(newest)),
            store._claim_path(policy_id, 2),
            store._revision_path(policy_id, 2),
        ):
            self.remove(path)
        if erase_acceptance:
            for path in store._acceptance_paths(policy_id, 2):
                self.remove(path)
        store._write_replace(store.root / ".history-head" / f"{policy_id}.json",
                             store._read(store._claim_path(policy_id, 1), "old claim"))
        store._write_replace(store._state_path(policy_id), old)

    def assert_history_held(self, first, final):
        with self.assertRaises(RetryStoreError):
            self.state(first)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(first["job_id"])
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(final["job_id"])

    def test_08_exact_r3_event_claim_witness_and_prefix_replay_is_hold(self):
        first, _, final, _, old = self.rollback_fixture()
        self.assertEqual(self.state(first)["revision"], 2)
        self.replay_terminal_suffix(first, old)
        self.assert_history_held(first, final)

    def test_09_stop_cannot_disappear_through_the_same_suffix_attack(self):
        first = self.fail(self.running(max_attempts=2))
        child = self.jobs.retry(first["job_id"])
        old = self.state(first)
        final = self.fail_child(child, failure_class="policy_failure")
        self.assertEqual(self.jobs.retry_or_stop(final["job_id"])["decision"]["decision"], "STOP")
        self.replay_terminal_suffix(first, old)
        self.assert_history_held(first, final)

    def test_10_terminal_tombstone_survives_all_revision_suffix_loss(self):
        first, _, final, _, old = self.rollback_fixture()
        terminal = self.jobs.retry_store.load_anchor("terminal", first["retry_policy"]["policy_id"])
        self.assertEqual(terminal["sequence"], 2)
        self.assertEqual(terminal["decision"], "REPLAN_REQUIRED")
        self.replay_terminal_suffix(first, old, erase_acceptance=True)
        self.assert_history_held(first, final)

    def test_11_accepted_revision_missing_either_half_is_a_hold(self):
        for half in (0, 1):
            with self.subTest(half=half), self.isolated_case() as case:
                first, _, final, _, _ = case.rollback_fixture()
                case.remove(case.jobs.retry_store._acceptance_paths(first["retry_policy"]["policy_id"], 2)[half])
                case.assert_history_held(first, final)

    def test_12_terminal_missing_half_or_pair_is_not_reconstructed_from_cache(self):
        for half in (0, 1, None):
            with self.subTest(half=half), self.isolated_case() as case:
                first, _, final, _, _ = case.rollback_fixture()
                identity = first["retry_policy"]["policy_id"]
                if half is None:
                    case.erase("terminal", identity)
                else:
                    case.remove(case.jobs.retry_store._anchor_paths("terminal", identity)[half])
                case.assert_history_held(first, final)

    def test_13_genesis_replay_and_child_removal_still_fail_closed(self):
        first, child, final, genesis, _ = self.rollback_fixture()
        store = self.jobs.retry_store
        policy_id = first["retry_policy"]["policy_id"]
        for directory in (".events", ".decision-claims", ".history-revisions"):
            for path in (store.root / directory / policy_id).glob("*.json"):
                self.remove(path)
        for directory in (".history-started", ".history-head"):
            self.remove(store.root / directory / f"{policy_id}.json")
        store._write_replace(store._state_path(policy_id), genesis)
        self.remove(self.jobs.store._path(child["job_id"]))
        self.assert_history_held(first, final)

    def test_14_crash_after_accepted_revision_before_event_is_hold(self):
        for directory in (".acceptance-creation", ".accepted-revisions"):
            with self.subTest(directory=directory):
                first = self.fail(self.running())
                store = self.jobs.retry_store
                write = store._write_new
                def interrupted(path, value):
                    write(path, value)
                    if directory in path.parts:
                        raise KeyboardInterrupt("Accepted revision precedes event/cache")
                with patch.object(store, "_write_new", side_effect=interrupted):
                    with self.assertRaises(KeyboardInterrupt):
                        self.jobs.retry_or_stop(first["job_id"])
                with self.assertRaises(JobRuntimeError):
                    self.restart().retry_or_stop(first["job_id"])

    def test_15_crash_after_terminal_anchor_before_acceptance_is_hold(self):
        first = self.fail(self.running(max_attempts=1))
        store = self.jobs.retry_store
        write = store._write_new
        def interrupted(path, value):
            write(path, value)
            if ".terminal" in path.parts:
                raise KeyboardInterrupt("Terminal evidence precedes derived history")
        with patch.object(store, "_write_new", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.jobs.retry_or_stop(first["job_id"])
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(first["job_id"])

    def test_16_accepted_revision_cannot_use_boolean_schema_or_extra_sequence(self):
        first = self.fail(self.running())
        self.jobs.retry(first["job_id"])
        store = self.jobs.retry_store
        policy_id = first["retry_policy"]["policy_id"]
        paths = store._acceptance_paths(policy_id, 1)
        value = store._read(paths[0], "accepted revision")
        for path in paths:
            store._write_replace(path, {**value, "schema_version": True})
        with self.assertRaises(RetryStoreError):
            self.state(first)
        for path in paths:
            store._write_replace(path, value)
        for path in store._acceptance_paths(policy_id, MAX_HISTORY):
            store._write_new(path, value)
        with self.assertRaises(RetryStoreError):
            self.state(first)
        with self.assertRaises(RetryStoreError):
            store._acceptance_paths(policy_id, MAX_HISTORY + 1)

    def corrupted_execution(self):
        identity = f"corrupt-execution-{self.ids.value}"
        result = ExecutionResult(
            execution_id=identity, job_id="fixture", status="succeeded", summary="Fixture",
            error=None, provider=None, started_at=self.clock_value, completed_at=self.clock_value,
        )
        self.executions.create(None, result)
        value = self.executions.load_raw(identity)
        value["result"]["schema_version"] = "not-an-integer"
        self.executions._write(self.executions._path(identity), value)
        return identity

    def assert_integrity_stop(self, job, outcome):
        self.assertFalse(outcome.result["error"]["retryable"])
        self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "malformed_state")
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_17_exact_r3_real_execution_store_schema_failure_is_stop(self):
        job = self.running()
        identity = self.corrupted_execution()
        with self.assertRaises(ExecutionStoreError):
            self.executions.load(identity)
        executor = repairs.ResultExecutor()
        with patch.object(executor, "execute", side_effect=lambda _: self.executions.load(identity).result):
            outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assert_integrity_stop(job, outcome)

    def test_18_provider_wrapper_preserves_real_canonical_storage_failure(self):
        job = self.running()
        identity = self.corrupted_execution()
        executor = self.controlled_executor(lambda _: None)
        with patch.object(executor.router.adapters["codex"], "execute",
                          side_effect=lambda *args, **kw: self.executions.load(identity).result):
            outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assert_integrity_stop(job, outcome)

    def test_19_result_persistence_error_is_non_retryable(self):
        job = self.running()
        with patch.object(self.executions, "create", side_effect=ExecutionStoreError("Canonical persistence refused")):
            outcome = self.worker(repairs.ResultExecutor()).run_claimed(job["job_id"])
        self.assertFalse(outcome.error["retryable"])
        self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "malformed_state")
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_20_all_typed_trusted_failures_are_non_retryable_at_both_layers(self):
        for kind in TRUSTED_EXECUTION_FAILURES:
            for provider_wrapper in (False, True):
                with self.subTest(error=kind.__name__, provider_wrapper=provider_wrapper):
                    job = self.running()
                    executor = self.controlled_executor(lambda _: None) if provider_wrapper else repairs.ResultExecutor()
                    target = executor.router.adapters["codex"] if provider_wrapper else executor
                    with patch.object(target, "execute", side_effect=kind("Trusted failure with misleading RETRY prose")):
                        outcome = self.worker(executor).run_claimed(job["job_id"])
                    self.assertFalse(outcome.result["error"]["retryable"])
                    expected = ("malformed_state" if kind in INTEGRITY_FAILURES else
                                "authority_failure" if kind in AUTHORITY_FAILURES else "policy_failure")
                    self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], expected)
                    self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")
        self.assertEqual(set(TRUSTED_EXECUTION_FAILURES),
                         set(INTEGRITY_FAILURES + AUTHORITY_FAILURES + POLICY_FAILURES))

    def test_21_integrity_provenance_survives_result_reconciliation(self):
        job = self.running()
        identity = self.corrupted_execution()
        executor = repairs.ResultExecutor()
        with patch.object(executor, "execute", side_effect=lambda _: self.executions.load(identity).result), \
                patch.object(self.jobs, "fail", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(job["job_id"])
        # The independently corrupted fixture is unrelated to the job under test.
        self.remove(self.executions._path(identity))
        restarted = self.restart()
        recovered = self.worker(executor, runtime=restarted).recover_persisted_results()
        self.assertEqual(recovered[0].status, "failed")
        self.assertEqual(restarted.show(job["job_id"])["error"]["failure_class"], "malformed_state")
        self.assertEqual(restarted.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def unicode_retry(self, *, parent="src/stra\u00dfe", unit="src"):
        target = self.root / f"unicode-target-{self.ids.value}"
        for directory in ("src/stra\u00dfe", "src/strasse", "src/a", "src/b"):
            (target / directory).mkdir(parents=True)
            (target / directory / "before.txt").write_text(directory, encoding="utf-8")
        self.assertFalse((target / "src/stra\u00dfe").samefile(target / "src/strasse"))
        scope = {"project_root": str(target), "allowed_paths": [parent], "forbidden_paths": [],
                 "write_mode": "CREATE_OR_MODIFY", "max_changed_files": 4, "max_artifact_bytes": 65536,
                 "allow_tests": False, "allow_git_reads": False, "allow_protected_paths": False}
        plan = {"plan_id": f"unicode-plan-{self.ids.value}", "steps": [
            {"step_id": "A", "task": "Repair failed unit A",
             "execution_scope": {**deepcopy(scope), "allowed_paths": [unit]}},
            {"step_id": "B", "task": "Sibling"},
        ]}
        created = self.jobs.create(self.payload(
            capability="software_implementation", risk_level="approval_required",
            approval_status="required", review_required=True, execution_mode="CONTROLLED_WRITE",
            execution_scope=scope, continuation_plan=plan,
        ))
        approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "state" / "approvals"),
                                    execution_store=self.executions, clock=lambda: self.clock_value)
        self.approve(approvals, created)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        child = self.jobs.retry(self.fail(claimed)["job_id"])
        self.approve(approvals, child)
        return target, self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)

    @staticmethod
    def write_paths(workspace, paths):
        for relative in paths:
            path = workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("changed", encoding="utf-8")

    def test_22_unicode_namespace_intersection_is_disjoint_not_equivalent(self):
        target, child = self.unicode_retry()
        model = deepcopy(child)
        model["continuation_plan"]["steps"][0]["execution_scope"]["allowed_paths"] = ["src/strasse"]
        self.assertEqual(repair_scope(model, "A")["allowed_paths"], [])
        scope = ExecutionScope.from_dict(child["execution_scope"])
        self.assertTrue(scope.permits("src/stra\u00dfe/new.txt"))
        self.assertFalse(scope.permits("src/strasse/new.txt"))
        self.assertFalse(scope_path_contains("src/stra\u00dfe", "src/strasse/new.txt", project_root=str(target)))
        actual = ExecutionScope.from_dict({**child["execution_scope"], "allowed_paths": ["src/strasse"]})
        self.assertFalse(self.jobs._scope_is_no_broader(actual, scope))

    def test_23_exact_r3_disjoint_unicode_unit_is_rejected_before_execution(self):
        with self.assertRaises(JobRuntimeError):
            self.unicode_retry(unit="src/strasse")
        targets = list(self.root.glob("unicode-target-*"))
        self.assertTrue(targets)
        for target in targets:
            self.assertFalse((target / "src/strasse/new.txt").exists())

    def test_24_actual_unicode_sibling_write_is_rejected_before_target_mutation(self):
        target, child = self.unicode_retry()
        executor = self.controlled_executor(lambda workspace: self.write_paths(workspace, ["src/strasse/new.txt"]))
        controlled = executor.controlled_write_runtime
        with patch.object(controlled, "_apply", wraps=controlled._apply) as apply:
            outcome = self.worker(executor).run_claimed(child["job_id"])
        self.assertEqual(outcome.result["status"], "failed")
        apply.assert_not_called()
        self.assertFalse((target / "src/strasse/new.txt").exists())
        self.assertEqual((target / "src/stra\u00dfe/before.txt").read_text(encoding="utf-8"), "src/stra\u00dfe")
        self.assertEqual((target / "src/strasse/before.txt").read_text(), "src/strasse")

    def test_25_actual_mixed_sibling_unrelated_and_traversal_writes_are_atomic_denials(self):
        for paths in (
            ["src/stra\u00dfe/before.txt", "src/strasse/new.txt"],
            ["src/a/new.txt"], ["unrelated/new.txt"],
            ["src/stra\u00dfe/../strasse/new.txt"],
            ["src/stra\u00dfe/../../unrelated/new.txt"],
        ):
            with self.subTest(paths=paths):
                target, child = self.unicode_retry()
                executor = self.controlled_executor(lambda workspace: self.write_paths(workspace, paths))
                controlled = executor.controlled_write_runtime
                with patch.object(controlled, "_apply", wraps=controlled._apply) as apply:
                    outcome = self.worker(executor).run_claimed(child["job_id"])
                self.assertEqual(outcome.result["status"], "failed")
                apply.assert_not_called()
                self.assertFalse((target / "src/strasse/new.txt").exists())
                self.assertFalse((target / "src/a/new.txt").exists())
                self.assertFalse((target / "unrelated/new.txt").exists())
                self.assertEqual((target / "src/stra\u00dfe/before.txt").read_text(encoding="utf-8"), "src/stra\u00dfe")

    def test_26_repair_requests_reject_unicode_mixed_and_normalization_bypasses(self):
        _, child = self.unicode_retry()
        self.assertEqual(child["retry_authorization"]["repair_scope"]["allowed_paths"], ["src/stra\u00dfe"])
        self.jobs.retry_runtime.validate_repair_request(child, unit_ids=["A"], paths=["src\\stra\u00dfe\\new.txt"])
        for paths in (["src/strasse/new.txt"], ["src/stra\u00dfe/new.txt", "src/strasse/new.txt"],
                      ["src/stra\u00dfe/../strasse/new.txt"], ["src\\stra\u00dfe\\..\\strasse\\new.txt"],
                      ["src/stra\u00dfe//new.txt"], ["unrelated/new.txt"]):
            with self.subTest(paths=paths), self.assertRaises(RetryStoreError):
                self.jobs.retry_runtime.validate_repair_request(child, unit_ids=["A"], paths=paths)

    def test_27_valid_unicode_repair_applies_and_keeps_review_gate(self):
        target, child = self.unicode_retry()
        outcome = self.worker(self.controlled_executor(
            lambda workspace: self.write_paths(workspace, ["src/stra\u00dfe/new.txt"])
        )).run_claimed(child["job_id"])
        self.assertEqual(outcome.result["status"], "succeeded")
        self.assertEqual(outcome.status, "reviewing")
        self.assertEqual((target / "src/stra\u00dfe/new.txt").read_text(), "changed")
        self.assertFalse((target / "src/strasse/new.txt").exists())

    def test_28_ordinary_case_matches_actual_filesystem_not_unicode_linguistics(self):
        target, child = self.unicode_retry(parent="src/a")
        same_case_object = (target / "src/a").samefile(target / "SRC/A") if (target / "SRC/A").exists() else False
        scope = ExecutionScope.from_dict(child["execution_scope"])
        self.assertEqual(scope.permits("SRC/A/new.txt"), same_case_object and os.name == "nt")
        executor = self.controlled_executor(lambda workspace: self.write_paths(workspace, ["SRC/A/new.txt"]))
        outcome = self.worker(executor).run_claimed(child["job_id"])
        self.assertEqual(outcome.result["status"], "succeeded" if same_case_object and os.name == "nt" else "failed")
        self.assertEqual((target / "src/a/new.txt").exists(), same_case_object and os.name == "nt")
        self.assertFalse((target / "src/b/new.txt").exists())

    def test_29_future_forbidden_case_alias_cannot_bypass_negative_scope(self):
        _, child = self.unicode_retry(parent="src/a")
        scope = ExecutionScope.from_dict({**child["execution_scope"], "forbidden_paths": ["src/a/secret.txt"]})
        self.assertFalse(scope.permits("src/a/secret.txt"))
        if os.name == "nt":
            self.assertFalse(scope.permits("SRC/A/SECRET.TXT"))

    def test_30_original_approval_policy_and_exact_work_remain_immutable(self):
        parent, _ = self.approval_failed_parent()
        value = self.jobs.store.load(parent["job_id"])
        value["approval_status"] = "not_required"
        self.jobs.store.save(value)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(parent["job_id"])
        self.assertEqual(self.state(parent)["revision"], 0)

    def test_31_future_unicode_forbidden_case_alias_is_not_refunded(self):
        _, child = self.unicode_retry(parent="src/a")
        scope = ExecutionScope.from_dict({
            **child["execution_scope"], "forbidden_paths": ["src/a/\u00e9.txt"],
        })
        self.assertFalse(scope.permits("src/a/\u00e9.txt"))
        self.assertEqual(scope.permits("src/a/\u00c9.txt"), os.name != "nt")
        # Distinct sharp-s and ss siblings stay distinct even in negative scope.
        scope = ExecutionScope.from_dict({
            **child["execution_scope"], "allowed_paths": ["src"],
            "forbidden_paths": ["src/stra\u00dfe"],
        })
        self.assertTrue(scope.permits("src/strasse/new.txt"))

    def test_32_existing_unicode_case_alias_requires_real_filesystem_identity(self):
        target, child = self.unicode_retry()
        (target / "src/caf\u00e9").mkdir()
        alternate = target / "SRC/CAF\u00c9"
        identical = alternate.exists() and (target / "src/caf\u00e9").samefile(alternate)
        scope = ExecutionScope.from_dict({**child["execution_scope"], "allowed_paths": ["src/caf\u00e9"]})
        self.assertEqual(scope.permits("SRC/CAF\u00c9/new.txt"), identical and os.name == "nt")

    def test_33_case_sensitive_namespace_mismatch_cannot_use_ordinal_case_alone(self):
        target, _ = self.unicode_retry(parent="src/a")
        with patch("pathlib.Path.samefile", return_value=False):
            self.assertFalse(scope_path_contains("src/a", "SRC/A/new.txt", project_root=str(target)))

    def test_34_shared_scope_denies_unicode_sibling_even_without_retry_constraint(self):
        target = self.root / "ordinary-unicode-target"
        for relative in ("src/stra\u00dfe", "src/strasse"):
            (target / relative).mkdir(parents=True)
        scope = {
            "project_root": str(target), "allowed_paths": ["src/stra\u00dfe"], "forbidden_paths": [],
            "write_mode": "CREATE_OR_MODIFY", "max_changed_files": 4, "max_artifact_bytes": 65536,
            "allow_tests": False, "allow_git_reads": False, "allow_protected_paths": False,
        }
        created = self.jobs.create(self.payload(
            capability="software_implementation", risk_level="approval_required", approval_status="required",
            review_required=True, execution_mode="CONTROLLED_WRITE", execution_scope=scope,
        ))
        approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "state" / "approvals"),
                                    execution_store=self.executions, clock=lambda: self.clock_value)
        self.approve(approvals, created)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        self.assertNotIn("retry_authorization", claimed)
        executor = self.controlled_executor(lambda workspace: self.write_paths(workspace, ["src/strasse/new.txt"]))
        controlled = executor.controlled_write_runtime
        with patch.object(controlled, "_apply", wraps=controlled._apply) as apply:
            outcome = self.worker(executor).run_claimed(claimed["job_id"])
        self.assertEqual(outcome.result["status"], "failed")
        apply.assert_not_called()
        self.assertFalse((target / "src/strasse/new.txt").exists())


if __name__ == "__main__":
    unittest.main()
