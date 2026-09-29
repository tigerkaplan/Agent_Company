"""Bounded CORE-06R2 regression reproductions; all damaged state is in TEMP."""
from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from runtime.actions.models import ScopeContractError
from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.core.validation import JobValidationError
from runtime.execution.models import ExecutionContractError
from runtime.execution.validation import ExecutionResultValidationError
from runtime.providers.artifacts import ProviderArtifactError
from runtime.providers.config import ProviderConfigError
from runtime.providers.context import ContextBuildError
from runtime.retry.models import RetryContractError, history_entry_digest, repair_scope
from runtime.retry.store import RetryStoreError
from runtime.tests import test_retry_repairs as repairs
from runtime.tests.test_retry_policy import RetryHarness


class CrashExecutor(repairs.ResultExecutor):
    def execute(self, request):
        self.calls += 1
        raise KeyboardInterrupt("Simulated process death after Executor delegation")


class RetryF2ATests(RetryHarness, unittest.TestCase):
    # Reuse fixtures, not the old TestCase (which would duplicate its tests).
    worker = repairs.RetryRepairTests.worker
    retry_claim = repairs.RetryRepairTests.retry_claim
    controlled_executor = repairs.RetryRepairTests.controlled_executor
    rollback_fixture = repairs.RetryRepairTests.rollback_fixture
    approve = staticmethod(repairs.RetryRepairTests.approve)

    def remove(self, path):
        self.assertIn(self.root.resolve(), path.resolve().parents)
        path.unlink()

    def erase_reservation_pair(self, job):
        for path in self.jobs.retry_store._anchor_paths("execution", job["job_id"]):
            self.remove(path)

    def test_01_exact_r2_reservation_pair_loss_keeps_executor_count_one(self):
        _, child = self.retry_claim(execution_budget={"max_execution_units": 3})
        executor = CrashExecutor()
        with self.assertRaises(KeyboardInterrupt):
            self.worker(executor).run_claimed(child["job_id"])
        consumed = self.jobs.retry_store.load_anchor("attempt-admission", child["job_id"])
        self.assertEqual(consumed["job_id"], child["job_id"])
        self.erase_reservation_pair(child)
        restarted = self.restart()
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(
                lambda _: self.worker(executor, runtime=restarted).run_claimed(child["job_id"]), range(4)
            ))
        self.assertTrue(all(item.status == "worker_error" for item in outcomes))
        self.assertEqual(executor.calls, 1)
        self.assertEqual(self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status, "worker_error")
        self.assertEqual(executor.calls, 1)
        budget = self.worker(executor).budget_runtime.state(child["execution_budget"])
        self.assertEqual(budget.state["dimensions"]["execution_units"]["consumed"], 1)

    def test_02_success_before_reconciliation_and_reservation_loss_cannot_reexecute(self):
        _, child = self.retry_claim()
        executor = repairs.ResultExecutor()
        with patch.object(self.jobs, "record_execution_success", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(child["job_id"])
        self.erase_reservation_pair(child)
        outcome = self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"])
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(executor.calls, 1)

    def test_03_consumption_evidence_missing_half_is_a_hold(self):
        for half in (0, 1):
            with self.subTest(half=half):
                _, child = self.retry_claim()
                executor = CrashExecutor()
                with self.assertRaises(KeyboardInterrupt):
                    self.worker(executor).run_claimed(child["job_id"])
                self.remove(self.jobs.retry_store._anchor_paths("attempt-admission", child["job_id"])[half])
                self.assertEqual(self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status, "worker_error")
                self.assertEqual(executor.calls, 1)

    def test_04_crash_during_admission_cannot_reopen_missing_reservation(self):
        _, child = self.retry_claim()
        executor = repairs.ResultExecutor()
        anchor = self.jobs.retry_store.anchor
        def interrupted(kind, identity, value):
            if kind == "admission":
                raise KeyboardInterrupt("Attempt evidence committed; per-execution admission interrupted")
            return anchor(kind, identity, value)
        with patch.object(self.jobs.retry_store, "anchor", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(child["job_id"])
        self.erase_reservation_pair(child)
        self.assertEqual(self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status, "worker_error")
        self.assertEqual(executor.calls, 0)

    def replay_prefix(self, first, old):
        store = self.jobs.retry_store
        policy_id = first["retry_policy"]["policy_id"]
        newest = self.state(first)["history"][-1]
        self.remove(store._event_path(policy_id, 2, history_entry_digest(newest)))
        self.remove(store._claim_path(policy_id, 2))
        old_head = store._read(store._claim_path(policy_id, 1), "old decision claim")
        store._write_replace(store.root / ".history-head" / f"{policy_id}.json", old_head)
        store._write_replace(store._state_path(policy_id), old)

    def test_05_exact_r2_event_claim_and_cache_replay_cannot_erase_replan(self):
        first, _, final, _, old = self.rollback_fixture()
        self.replay_prefix(first, old)
        with self.assertRaises(RetryStoreError):
            self.state(first)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(final["job_id"])

    def test_06_stop_suffix_replay_is_also_rejected(self):
        first = self.fail(self.running(max_attempts=2))
        child = self.jobs.retry(first["job_id"])
        old = self.state(first)
        final = self.fail_child(child, failure_class="policy_failure")
        self.assertEqual(self.jobs.retry_or_stop(final["job_id"])["decision"]["decision"], "STOP")
        self.replay_prefix(first, old)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(first["job_id"])

    def test_07_genesis_replay_and_exhausted_child_removal_cannot_restore_authority(self):
        first, child, _, genesis, _ = self.rollback_fixture()
        store = self.jobs.retry_store
        policy_id = first["retry_policy"]["policy_id"]
        for directory in (store._event_root(policy_id), store.root / ".decision-claims" / policy_id):
            for path in directory.glob("*.json"):
                self.remove(path)
        for directory in (".history-head", ".history-started"):
            self.remove(store.root / directory / f"{policy_id}.json")
        self.remove(self.jobs.store._path(child["job_id"]))
        store._write_replace(store._state_path(policy_id), genesis)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(first["job_id"])

    def test_08_revision_witness_loss_or_boolean_version_fails_closed(self):
        for invalid in (None, True):
            with self.subTest(invalid=invalid):
                first = self.fail(self.running())
                self.jobs.retry(first["job_id"])
                path = self.jobs.retry_store._revision_path(first["retry_policy"]["policy_id"], 1)
                original = self.jobs.retry_store._read(path, "revision witness")
                try:
                    if invalid is None:
                        self.remove(path)
                    else:
                        value = {**original, "schema_version": invalid}
                        self.jobs.retry_store._write_replace(path, value)
                    with self.assertRaises(RetryStoreError):
                        self.state(first)
                finally:
                    # Isolate the next subtest from this deliberately damaged fixture.
                    self.jobs.retry_store._write_replace(path, original)

    def test_09_crash_after_revision_witness_before_event_is_a_hold(self):
        first = self.fail(self.running())
        store = self.jobs.retry_store
        write = store._write_new
        def interrupted(path, value):
            write(path, value)
            if ".history-revisions" in path.parts:
                raise KeyboardInterrupt("Revision consumed before event/cache reconciliation")
        with patch.object(store, "_write_new", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.jobs.retry_or_stop(first["job_id"])
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(first["job_id"])

    def test_10_unsupported_mode_is_a_trusted_stop_without_executor_call(self):
        job = self.running()
        executor = repairs.ResultExecutor()
        executor.supported_execution_modes = frozenset({"CONTROLLED_WRITE"})
        outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assertEqual(executor.calls, 0)
        self.assertFalse(outcome.result["error"]["retryable"])
        self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "policy_failure")
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_11_malformed_or_mismatched_executor_results_are_trusted_stops(self):
        changes = (None, {"execution_id": "unrelated"}, {"job_id": "unrelated"},
                   {"execution_mode": "CONTROLLED_WRITE"}, {"dry_run": True}, {"schema_version": True})
        for change in changes:
            with self.subTest(change=change):
                job = self.running()
                executor = repairs.ResultExecutor()
                canonical = executor.execute
                def malformed(request):
                    result = canonical(request)
                    if change is None:
                        return {"not": "ExecutionResult"}
                    if "schema_version" in change:
                        object.__setattr__(result, "schema_version", True)
                        return result
                    return replace(result, **change)
                with patch.object(executor, "execute", side_effect=malformed):
                    outcome = self.worker(executor).run_claimed(job["job_id"])
                self.assertFalse(outcome.result["error"]["retryable"])
                self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "malformed_state")
                self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_12_typed_trusted_contract_authority_and_policy_failures_never_retry(self):
        for error_type in (ExecutionContractError, ExecutionResultValidationError, JobValidationError,
                           RetryStoreError, ScopeContractError, JobRuntimeError, ApprovalRuntimeError,
                           ProviderConfigError, ContextBuildError, RetryContractError, ProviderArtifactError):
            with self.subTest(error=error_type.__name__):
                job = self.running()
                executor = repairs.ResultExecutor()
                with patch.object(executor, "execute", side_effect=error_type("Canonical denial")):
                    outcome = self.worker(executor).run_claimed(job["job_id"])
                self.assertFalse(outcome.result["error"]["retryable"])
                self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_13_real_provider_router_policy_denial_is_not_flattened_to_transient(self):
        job = self.running()
        executor = self.controlled_executor(lambda _: None)
        with patch.object(executor.router.configuration, "eligible", return_value=False):
            outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assertEqual(executor.router.adapters["codex"].workspaces, [])
        self.assertFalse(outcome.result["error"]["retryable"])
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_14_provider_wrapper_preserves_canonical_context_denial(self):
        job = self.running()
        executor = self.controlled_executor(lambda _: None)
        with patch.object(executor.context_builder, "build", side_effect=ContextBuildError("Context outside authority")):
            outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assertEqual(executor.router.adapters["codex"].workspaces, [])
        self.assertFalse(outcome.result["error"]["retryable"])
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_15_trusted_failure_provenance_survives_crash_reconciliation(self):
        job = self.running()
        executor = repairs.ResultExecutor()
        with patch.object(executor, "execute", return_value={"malformed": True}), \
                patch.object(self.jobs, "fail", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(job["job_id"])
        restarted = self.restart()
        outcomes = self.worker(executor, runtime=restarted).recover_persisted_results()
        self.assertEqual(outcomes[0].status, "failed")
        self.assertEqual(restarted.show(job["job_id"])["error"]["failure_class"], "malformed_state")
        self.assertEqual(restarted.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_16_missing_trusted_provenance_never_becomes_transient_on_restart(self):
        job = self.running()
        executor = repairs.ResultExecutor()
        with patch.object(executor, "execute", return_value={"malformed": True}), \
                patch.object(self.jobs, "fail", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.worker(executor).run_claimed(job["job_id"])
        record = self.executions.find_for_job(job["job_id"])
        for path in self.jobs.retry_store._anchor_paths("runtime-failure", record.result.execution_id):
            self.remove(path)
        restarted = self.restart()
        self.assertEqual(self.worker(executor, runtime=restarted).recover_persisted_results()[0].status, "failed")
        self.assertEqual(restarted.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")

    def test_17_provider_labels_cannot_impersonate_trusted_denial_provenance(self):
        for code in ("authorization_error", "malformed_state", "policy_rejected"):
            with self.subTest(code=code):
                job = self.running()
                outcome = self.worker(repairs.ResultExecutor(code)).run_claimed(job["job_id"])
                self.assertEqual(outcome.status, "failed")
                self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "transient_execution")
                self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "RETRY")

    def approval_failed_parent(self):
        created = self.jobs.create(self.payload(approval_status="required", execution_budget={"max_execution_units": 3}))
        approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "state" / "approvals"),
                                    execution_store=self.executions, clock=lambda: self.clock_value)
        self.approve(approvals, created)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        outcome = self.worker(repairs.ResultExecutor("provider_failed")).run_claimed(claimed["job_id"])
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(self.executions.load(outcome.execution_id).request["approval_status"], "approved")
        return claimed, approvals

    def test_18_original_approved_to_not_required_downgrade_before_decision_fails(self):
        parent, _ = self.approval_failed_parent()
        raw = self.jobs.store.load(parent["job_id"])
        raw["approval_status"] = "not_required"
        self.jobs.store.save(raw)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(parent["job_id"])
        self.assertEqual(self.state(parent)["history"], [])
        self.assertTrue(self.jobs.retry_store.load_anchor("failure", parent["job_id"])["approval_required"])

    def test_19_child_policy_downgrade_before_enqueue_cannot_bypass_fresh_approval(self):
        parent, _ = self.approval_failed_parent()
        child = self.jobs.retry(parent["job_id"])
        self.assertEqual(child["approval_status"], "required")
        raw = self.jobs.store.load(child["job_id"])
        raw["approval_status"] = "not_required"
        self.jobs.store.save(raw)
        with self.assertRaises(JobRuntimeError):
            self.jobs.enqueue(child["job_id"])
        executor = repairs.ResultExecutor()
        self.assertEqual(self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status, "worker_error")
        self.assertEqual(executor.calls, 0)

    def test_20_approved_retry_downgrade_at_execution_boundary_fails(self):
        parent, approvals = self.approval_failed_parent()
        child = self.jobs.retry(parent["job_id"])
        self.approve(approvals, child)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        raw = self.jobs.store.load(claimed["job_id"])
        raw["approval_status"] = "not_required"
        self.jobs.store.save(raw)
        executor = repairs.ResultExecutor()
        self.assertEqual(self.worker(executor, runtime=self.restart()).run_claimed(child["job_id"]).status, "worker_error")
        self.assertEqual(executor.calls, 0)

    def test_21_intact_fresh_approval_executes_with_same_logical_budget(self):
        parent, approvals = self.approval_failed_parent()
        child = self.jobs.retry(parent["job_id"])
        self.assertEqual(child["approval_status"], "required")
        with self.assertRaises(JobRuntimeError):
            self.jobs.enqueue(child["job_id"])
        self.approve(approvals, child)
        self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        executor = repairs.ResultExecutor()
        outcome = self.worker(executor).run_claimed(child["job_id"])
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(executor.calls, 1)
        self.assertEqual(child["execution_budget"], parent["execution_budget"])
        budget = self.worker(executor).budget_runtime.state(child["execution_budget"])
        self.assertEqual(budget.state["dimensions"]["execution_units"]["consumed"], 2)

    def wider_unit_retry(self):
        target = self.root / f"narrow-parent-{self.ids.value}"
        (target / "src/a").mkdir(parents=True)
        (target / "src/a/file.txt").write_text("A before", encoding="utf-8")
        (target / "src/b.txt").write_text("B before", encoding="utf-8")
        scope = {"project_root": str(target), "allowed_paths": ["src/a"], "forbidden_paths": ["src/a/secret.txt"],
                 "write_mode": "CREATE_OR_MODIFY", "max_changed_files": 4, "max_artifact_bytes": 65536,
                 "allow_tests": False, "allow_git_reads": False, "allow_protected_paths": False}
        unit_scope = {**deepcopy(scope), "allowed_paths": ["src"], "forbidden_paths": []}
        plan = {"plan_id": f"narrow-parent-plan-{self.ids.value}", "steps": [
            {"step_id": "A", "task": "Repair failed unit A", "execution_scope": unit_scope},
            {"step_id": "B", "task": "Sibling work"}]}
        created = self.jobs.create(self.payload(capability="software_implementation", risk_level="approval_required",
            approval_status="required", review_required=True, execution_mode="CONTROLLED_WRITE",
            execution_scope=scope, continuation_plan=plan))
        approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "state" / "approvals"),
                                    execution_store=self.executions, clock=lambda: self.clock_value)
        self.approve(approvals, created)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        failed = self.fail(claimed)
        child = self.jobs.retry(failed["job_id"])
        self.approve(approvals, child)
        return target, self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)

    def test_22_exact_r2_wider_unit_intersects_narrower_parent(self):
        _, child = self.wider_unit_retry()
        self.assertEqual(child["retry_authorization"]["repair_scope"]["allowed_paths"], ["src/a"])
        runtime = self.jobs.retry_runtime
        for valid in ("src/a/file.txt", "src\\a\\file.txt", "SRC/A/file.txt"):
            runtime.validate_repair_request(child, unit_ids=["A"], paths=[valid])
        cases = (["src/b.txt"], ["src/a/file.txt", "src/b.txt"], ["unrelated.txt"],
                 ["src/a/../b.txt"], ["src\\a\\..\\b.txt"], ["src/a//file.txt"],
                 ["src/a/secret.txt"], ["src/ab/file.txt"])
        for paths in cases:
            with self.subTest(paths=paths), self.assertRaises(RetryStoreError):
                runtime.validate_repair_request(child, unit_ids=["A"], paths=paths)
        with self.assertRaises(RetryStoreError):
            runtime.validate_repair_request(child, unit_ids=["A"], capabilities=["software_implementation", "deployment"])

    def test_23_scope_intersection_is_symmetric_and_disjoint_is_empty(self):
        _, child = self.wider_unit_retry()
        model_job = deepcopy(child)
        model_job["execution_scope"]["allowed_paths"] = ["src"]
        model_job["continuation_plan"]["steps"][0]["execution_scope"]["allowed_paths"] = ["src/a"]
        self.assertEqual(repair_scope(model_job, "A")["allowed_paths"], ["src/a"])
        model_job["execution_scope"]["allowed_paths"] = ["src/b"]
        self.assertEqual(repair_scope(model_job, "A")["allowed_paths"], [])

    def test_24_actual_mixed_or_sibling_repair_with_wider_unit_cannot_apply(self):
        for paths in (("src/b.txt",), ("src/a/file.txt", "src/b.txt"), ("src/a/../b.txt",)):
            with self.subTest(paths=paths):
                target, child = self.wider_unit_retry()
                def mutate(workspace):
                    for relative in paths:
                        (workspace / relative).write_text("unauthorized", encoding="utf-8")
                outcome = self.worker(self.controlled_executor(mutate)).run_claimed(child["job_id"])
                self.assertEqual(outcome.result["status"], "failed")
                self.assertEqual((target / "src/a/file.txt").read_text(), "A before")
                self.assertEqual((target / "src/b.txt").read_text(), "B before")
                self.assertEqual(self.jobs.retry_or_stop(child["job_id"])["decision"]["decision"], "STOP")

    def test_25_valid_narrow_parent_repair_applies_and_keeps_reviewer_gate(self):
        target, child = self.wider_unit_retry()
        outcome = self.worker(self.controlled_executor(
            lambda workspace: (workspace / "src/a/file.txt").write_text("fixed", encoding="utf-8")
        )).run_claimed(child["job_id"])
        self.assertEqual(outcome.result["status"], "succeeded")
        self.assertEqual(outcome.status, "reviewing")
        self.assertEqual((target / "src/a/file.txt").read_text(), "fixed")
        self.assertEqual((target / "src/b.txt").read_text(), "B before")

    def test_26_provider_wrapper_preserves_malformed_adapter_contract(self):
        job = self.running()
        executor = self.controlled_executor(lambda _: None)
        with patch.object(executor.router.adapters["codex"], "execute", return_value={"malformed": True}) as delegate:
            outcome = self.worker(executor).run_claimed(job["job_id"])
        self.assertEqual(delegate.call_count, 1)
        self.assertFalse(outcome.result["error"]["retryable"])
        self.assertEqual(self.jobs.show(job["job_id"])["error"]["failure_class"], "malformed_state")
        self.assertEqual(self.jobs.retry_or_stop(job["job_id"])["decision"]["decision"], "STOP")


if __name__ == "__main__":
    unittest.main()
