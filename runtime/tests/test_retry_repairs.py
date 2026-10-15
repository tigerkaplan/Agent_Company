"""Adversarial regression tests for the bounded CORE-06R1 F1-F8 repairs."""
from __future__ import annotations

import json
import threading
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from runtime.actions.runtime import ControlledWriteRuntime
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.core.validation import JobValidationError
from runtime.execution.models import ExecutionContractError, ExecutionRequest, ExecutionResult
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfiguration
from runtime.providers.context import ExecutionContextBuilder
from runtime.providers.executor import ProviderExecutor
from runtime.providers.routing import ProviderRouter
from runtime.retry.models import RetryContractError, RetryPolicy, history_entry_digest, policy_digest, state_digest
from runtime.retry.store import RetryStoreError
from runtime.review.runtime import ReviewerRuntime
from runtime.review.context import ReviewContextBuilder
from runtime.review.store import FileReviewStore
from runtime.review.verification import DeterministicVerifier
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests.test_actions import MutatingAdapter, UnavailableAdapter
from runtime.tests.test_retry_policy import IDs, REPOSITORY_ROOT, RetryHarness
from runtime.tests.test_review import FakeReviewer
from runtime.workers.worker import Worker


class ResultExecutor:
    supported_execution_modes = frozenset({"READ_ONLY"})

    def __init__(self, code=None, *, hold=False, variant=0):
        self.code, self.variant = code, variant
        self.calls = 0
        self.lock = threading.Lock()
        self.entered, self.release = threading.Event(), threading.Event()
        if not hold:
            self.release.set()

    def execute(self, request):
        with self.lock:
            self.calls += 1
        self.entered.set()
        if not self.release.wait(10):
            raise AssertionError("Executor release was not signalled")
        return ExecutionResult(
            execution_id=request.execution_id, job_id=request.job_id,
            status="failed" if self.code else "succeeded", summary=None if self.code else "Completed",
            error={"code": self.code, "message": f"Provider wording {self.variant}", "retryable": True} if self.code else None,
            provider=None, started_at="2026-09-28T12:00:00Z", completed_at="2026-09-28T12:00:00Z",
            usage={"duration_ms": self.variant, "unit": f"provider_unit_{self.variant}"},
            next_actions=({"action": f"action_{self.variant}", "description": f"Retry wording {self.variant}",
                           "requires_human": False, "automatic": False},),
        )


class RetryRepairTests(RetryHarness, unittest.TestCase):
    def worker(self, executor, *, runtime=None, reviewer=None):
        return Worker(runtime or self.jobs, CanonicalReferenceResolver(REPOSITORY_ROOT), executor, self.executions,
                      reviewer_runtime=reviewer, clock=lambda: self.clock_value, worker_id="core06-worker")

    def retry_claim(self, **overrides):
        failed = self.fail(self.running(**overrides))
        child = self.jobs.retry(failed["job_id"], enqueue=True)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        self.assertEqual(claimed["job_id"], child["job_id"])
        return failed, claimed

    def test_f1_concurrent_direct_delivery_stress_calls_executor_once(self):
        for repetition in range(10):
            with self.subTest(repetition=repetition):
                _, claimed = self.retry_claim(execution_budget={"max_execution_units": 3})
                executor = ResultExecutor(hold=True)
                first = self.worker(executor)
                with ThreadPoolExecutor(max_workers=8) as pool:
                    try:
                        active = pool.submit(first.run_claimed, claimed["job_id"])
                        self.assertTrue(executor.entered.wait(10))
                        duplicates = list(pool.map(lambda _: self.worker(executor).run_claimed(claimed["job_id"]), range(7)))
                        self.assertTrue(all(outcome.status == "execution_reserved" for outcome in duplicates))
                    finally:
                        executor.release.set()
                    outcome = active.result(timeout=10)
                self.assertEqual(executor.calls, 1)
                self.assertEqual(outcome.status, "completed")
                self.assertEqual({item.execution_id for item in [outcome, *duplicates]}, {outcome.execution_id})
                duplicate = self.worker(executor, runtime=self.restart()).run_claimed(claimed["job_id"])
                self.assertEqual(duplicate.result, outcome.result)
                self.assertEqual(executor.calls, 1)
                from runtime.budget.runtime import ExecutionBudgetRuntime
                budget = ExecutionBudgetRuntime(self.jobs.budget_store, wall_clock=lambda: self.clock_value)
                self.assertEqual(budget.state(claimed["execution_budget"]).state["dimensions"]["execution_units"]["consumed"], 1)

    def test_f1_crash_after_attempt_reservation_before_budget_never_reopens(self):
        _, claimed = self.retry_claim(execution_budget={"max_execution_units": 3})
        executor = ResultExecutor()
        worker = self.worker(executor)
        with patch.object(worker.budget_runtime, "reserve_execution", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_claimed(claimed["job_id"])
        resumed = self.worker(executor, runtime=self.restart()).run_claimed(claimed["job_id"])
        self.assertEqual(resumed.status, "execution_reserved")
        self.assertEqual(executor.calls, 0)

    def test_f1_simultaneous_fresh_deliveries_share_execution_identity(self):
        for repetition in range(5):
            with self.subTest(repetition=repetition):
                _, claimed = self.retry_claim()
                executor = ResultExecutor()
                workers = [self.worker(executor) for _ in range(8)]
                gate = threading.Barrier(8)
                def deliver(worker):
                    gate.wait(timeout=10)
                    return worker.run_claimed(claimed["job_id"])
                with ThreadPoolExecutor(max_workers=8) as pool:
                    outcomes = list(pool.map(deliver, workers))
                self.assertEqual(executor.calls, 1)
                self.assertEqual(len({outcome.execution_id for outcome in outcomes}), 1)
                self.assertNotIn("worker_error", [outcome.status for outcome in outcomes])

    def test_f1_successful_planned_retry_keeps_identity_and_continues(self):
        plan = {"plan_id": "plan-successful-retry", "steps": [{"step_id": "A", "task": "Repair failed unit A"},
                                                             {"step_id": "B", "task": "Next unit"}]}
        _, claimed = self.retry_claim(continuation_plan=plan)
        executor = ResultExecutor()
        worker = self.worker(executor)
        outcome = worker.run_claimed(claimed["job_id"])
        self.assertEqual(outcome.status, "completed")
        self.assertIsNotNone(outcome.continuation_job_id)
        self.assertEqual(self.jobs.show(outcome.continuation_job_id)["continuation"]["current_step_id"], "B")
        self.assertEqual(worker.run_claimed(claimed["job_id"]).result, outcome.result)
        self.assertEqual(executor.calls, 1)

    def test_f1_two_processes_cannot_delegate_same_retry_twice(self):
        _, claimed = self.retry_claim()
        script = '''
import json, sys, time
from pathlib import Path
from runtime.core.jobs import JobRuntime
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionResult
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker
root, job_id = Path(sys.argv[1]), sys.argv[2]
now = "2026-09-28T12:00:00Z"
class Executor:
    def execute(self, request):
        with (root / "calls.txt").open("a", encoding="utf-8") as handle:
            handle.write(request.execution_id + "\\n")
        time.sleep(0.1)
        return ExecutionResult(execution_id=request.execution_id, job_id=request.job_id,
            status="succeeded", summary="Done", error=None, provider=None, started_at=now, completed_at=now)
runtime = JobRuntime(root / "state" / "jobs", clock=lambda: now)
worker = Worker(runtime, CanonicalReferenceResolver(Path.cwd()), Executor(),
    FileExecutionStore(root / "state" / "executions"), clock=lambda: now, worker_id="core06-worker")
print(json.dumps(worker.run_claimed(job_id).to_dict()))
'''
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.root), claimed["job_id"]],
                                      cwd=REPOSITORY_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(2)]
        outputs = []
        try:
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stderr)
                outputs.append(json.loads(stdout))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        self.assertEqual(len((self.root / "calls.txt").read_text().splitlines()), 1)
        self.assertEqual(len({outcome["execution_id"] for outcome in outputs}), 1)
        self.assertNotIn("worker_error", [outcome["status"] for outcome in outputs])

    def test_f1_crash_after_budget_reservation_never_reopens_or_refunds(self):
        _, claimed = self.retry_claim(execution_budget={"max_execution_units": 3})
        executor = ResultExecutor()
        worker = self.worker(executor)
        with patch.object(worker.resolver, "resolve", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_claimed(claimed["job_id"])
        restarted = self.worker(executor, runtime=self.restart())
        restarted.recover_budget_state()
        self.assertEqual(restarted.run_claimed(claimed["job_id"]).status, "execution_reserved")
        self.assertEqual(executor.calls, 0)
        self.assertEqual(restarted.budget_runtime.state(claimed["execution_budget"]).state["dimensions"]["execution_units"]["consumed"], 1)

    def test_f1_success_before_reconciliation_reuses_result(self):
        _, claimed = self.retry_claim()
        executor = ResultExecutor()
        worker = self.worker(executor)
        with patch.object(self.jobs, "record_execution_success", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_claimed(claimed["job_id"])
        restarted = self.worker(executor, runtime=self.restart())
        duplicate = restarted.run_claimed(claimed["job_id"])
        self.assertEqual(duplicate.result["status"], "succeeded")
        self.assertEqual(restarted.recover_persisted_results()[0].status, "completed")
        self.assertEqual(executor.calls, 1)

    def controlled_retry(self, *, allocation=True):
        target = self.root / f"target-{self.ids.value}"
        (target / "src" / "a").mkdir(parents=True)
        (target / "src" / "a" / "file.txt").write_text("A before", encoding="utf-8")
        (target / "src" / "b.txt").write_text("B before", encoding="utf-8")
        scope = {"project_root": str(target), "allowed_paths": ["src"], "forbidden_paths": [],
                 "write_mode": "CREATE_OR_MODIFY", "max_changed_files": 4, "max_artifact_bytes": 65536,
                 "allow_tests": False, "allow_git_reads": False, "allow_protected_paths": False}
        # Production already requires job scope <= explicit unit scope. An
        # unallocated broad parent must be held; explicit unit scope is usable.
        step_scope = deepcopy(scope)
        step_scope["allowed_paths"] = ["src/a"]
        plan = {"plan_id": f"plan-scope-{self.ids.value}", "steps": [
            {"step_id": "A", "task": "Repair failed unit A", **({"execution_scope": step_scope} if allocation else {})},
            {"step_id": "B", "task": "Sibling work"},
        ]}
        job_scope = step_scope if allocation else scope
        created = self.jobs.create(self.payload(capability="software_implementation", risk_level="approval_required",
            approval_status="required", review_required=True, execution_mode="CONTROLLED_WRITE", execution_scope=job_scope,
            continuation_plan=plan))
        approvals = ApprovalRuntime(self.jobs, FileApprovalStore(self.root / "state" / "approvals"),
                                    execution_store=self.executions, clock=lambda: self.clock_value)
        self.approve(approvals, created)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        failed = self.fail(claimed)
        child = self.jobs.retry(failed["job_id"])
        self.approve(approvals, child)
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        return target, claimed

    @staticmethod
    def approve(approvals, job):
        pending = approvals.request_execution(job["job_id"], reason="Isolated bounded retry repair fixture")
        approvals.resolve(pending.request.approval_id, decision="APPROVED", decided_by="fixture-owner", reason="Fixture approval")

    def controlled_executor(self, mutate):
        controlled = ControlledWriteRuntime(REPOSITORY_ROOT, FileMutationArtifactStore(self.root / "mutations"))
        executor = ProviderExecutor(ProviderRouter(ProviderConfiguration(REPOSITORY_ROOT),
            {"codex": MutatingAdapter(mutate), "claude": UnavailableAdapter()}),
            ExecutionContextBuilder(REPOSITORY_ROOT), FileProviderArtifactStore(self.root / "provider"),
            controlled_write_runtime=controlled, clock=lambda: self.clock_value)
        return executor

    def test_f2_broad_unallocated_unit_repair_denies_b_only_and_a_plus_b(self):
        for paths in (("src/b.txt",), ("src/a/file.txt", "src/b.txt"), ("outside.txt",)):
            with self.subTest(paths=paths):
                target, claimed = self.controlled_retry(allocation=False)
                def mutate(workspace):
                    for relative in paths:
                        (workspace / relative).write_text("unauthorized", encoding="utf-8")
                executor = self.controlled_executor(mutate)
                outcome = self.worker(executor).run_claimed(claimed["job_id"])
                self.assertEqual(outcome.result["status"], "failed")
                self.assertEqual(outcome.result["error"]["code"], "write_not_authorized")
                self.assertEqual(executor.router.adapters["codex"].workspaces, [])
                self.assertEqual((target / "src/b.txt").read_text(), "B before")
                self.assertEqual((target / "src/a/file.txt").read_text(), "A before")
                self.assertNotEqual(self.jobs.retry_or_stop(claimed["job_id"])["decision"]["decision"], "RETRY")

    def test_f2_allocated_unit_rejects_b_only_a_plus_b_and_traversal(self):
        for paths in (("src/b.txt",), ("src/a/file.txt", "src/b.txt"), ("src/a/../b.txt",), ("outside.txt",)):
            with self.subTest(paths=paths):
                target, claimed = self.controlled_retry()
                def mutate(workspace):
                    for relative in paths:
                        (workspace / relative).write_text("unauthorized", encoding="utf-8")
                outcome = self.worker(self.controlled_executor(mutate)).run_claimed(claimed["job_id"])
                self.assertEqual(outcome.result["error"]["code"], "mutation_scope_violation")
                self.assertEqual((target / "src/b.txt").read_text(), "B before")
                self.assertEqual((target / "src/a/file.txt").read_text(), "A before")
                self.assertFalse((target / "outside.txt").exists())

    def test_f2_path_authorization_rejects_aliases_absolute_and_traversal(self):
        _, child = self.controlled_retry()
        for path in ("src/a/../../b.txt", "src\\a\\..\\b.txt", "src/a/../b.txt", "src/a//b.txt", "C:/escape", "/escape", "src/a/CON.txt", "src/a/file.txt:stream"):
            with self.subTest(path=path), self.assertRaises(RetryStoreError):
                self.jobs.retry_runtime.validate_repair_request(child, unit_ids=["A"], paths=[path])

    def test_f2_valid_allocated_unit_repair_still_applies(self):
        target, claimed = self.controlled_retry()
        outcome = self.worker(self.controlled_executor(lambda workspace: (workspace / "src/a/file.txt").write_text("fixed"))).run_claimed(claimed["job_id"])
        self.assertEqual(outcome.result["status"], "succeeded")
        self.assertEqual(outcome.status, "reviewing")
        self.assertEqual((target / "src/a/file.txt").read_text(), "fixed")
        self.assertEqual((target / "src/b.txt").read_text(), "B before")

    def test_f2_provider_cannot_mutate_request_constraint_to_broaden_repair(self):
        _, claimed = self.controlled_retry()
        executor = self.controlled_executor(lambda _: None)
        adapter = executor.router.adapters["codex"]
        def tamper(request, context, *, working_directory=None):
            from runtime.providers.models import ProviderExecutionResult
            request.retry_repair_scope["allowed_paths"].append("src")
            (Path(working_directory) / "src/b.txt").write_text("unauthorized", encoding="utf-8")
            return ProviderExecutionResult("succeeded", "Provider claim", "", 0)
        with patch.object(adapter, "execute", side_effect=tamper):
            outcome = self.worker(executor).run_claimed(claimed["job_id"])
        self.assertEqual(outcome.result["error"]["code"], "mutation_scope_violation")
        self.assertNotEqual(outcome.status, "completed")

    def rollback_fixture(self):
        first = self.fail(self.running(max_attempts=2))
        genesis = self.state(first)
        child = self.jobs.retry(first["job_id"])
        old = self.state(first)
        final = self.fail_child(child)
        self.assertEqual(self.jobs.retry_or_stop(final["job_id"])["decision"]["decision"], "REPLAN_REQUIRED")
        return first, child, final, genesis, old

    def test_f3_delete_stop_and_rehash_mutable_state_fails_closed(self):
        first, _, final, _, old = self.rollback_fixture()
        policy_id = first["retry_policy"]["policy_id"]
        state = self.state(first)
        entry = state["history"][-1]
        self.jobs.retry_store._event_path(policy_id, 2, history_entry_digest(entry)).unlink()
        self.jobs.retry_store._write_replace(self.jobs.retry_store._state_path(policy_id), old)
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(final["job_id"])

    def test_f3_old_history_replay_even_with_claim_suffix_deletion_fails(self):
        first, _, final, _, old = self.rollback_fixture()
        policy_id = first["retry_policy"]["policy_id"]
        entry = self.state(first)["history"][-1]
        self.jobs.retry_store._event_path(policy_id, 2, history_entry_digest(entry)).unlink()
        self.jobs.retry_store._claim_path(policy_id, 2).unlink()
        self.jobs.retry_store._write_replace(self.jobs.retry_store._state_path(policy_id), old)
        with self.assertRaises(JobRuntimeError):
            self.jobs.retry_or_stop(final["job_id"])

    def test_f3_genesis_reset_and_exhausted_child_deletion_fails(self):
        first, child, _, genesis, _ = self.rollback_fixture()
        policy_id = first["retry_policy"]["policy_id"]
        for path in self.jobs.retry_store._event_root(policy_id).glob("*.json"):
            path.unlink()
        for path in (self.jobs.retry_store.root / ".decision-claims" / policy_id).glob("*.json"):
            path.unlink()
        (self.jobs.retry_store.root / ".history-head" / f"{policy_id}.json").unlink()
        self.jobs.retry_store._write_replace(self.jobs.retry_store._state_path(policy_id), genesis)
        self.jobs.store._path(child["job_id"]).unlink()
        with self.assertRaises(JobRuntimeError):
            self.restart().retry_or_stop(first["job_id"])

    def test_f3_consumed_child_cannot_be_recreated_with_intact_history(self):
        first, child, _, _, _ = self.rollback_fixture()
        self.jobs.store._path(child["job_id"]).unlink()
        with self.assertRaisesRegex(JobRuntimeError, "consumed identity"):
            self.jobs.retry_or_stop(first["job_id"])

    def test_f3_coherent_event_and_state_redigest_cannot_change_history(self):
        first, _, final, _, _ = self.rollback_fixture()
        policy_id = first["retry_policy"]["policy_id"]
        state = self.state(first)
        old = deepcopy(state["history"][0])
        self.jobs.retry_store._event_path(policy_id, 1, history_entry_digest(old)).unlink()
        state["history"][0]["failure_signature"] = "a" * 64
        self.jobs.retry_store._write_new(self.jobs.retry_store._event_path(policy_id, 1, history_entry_digest(state["history"][0])), state["history"][0])
        state["state_digest"] = state_digest(state)
        self.jobs.retry_store._write_replace(self.jobs.retry_store._state_path(policy_id), state)
        with self.assertRaises(JobRuntimeError):
            self.jobs.retry_or_stop(final["job_id"])

    def test_f3_decrement_source_attempt_before_first_decision_fails(self):
        first = self.fail(self.running())
        child = self.jobs.retry(first["job_id"])
        final = self.fail_child(child)
        raw = self.jobs.store.load(final["job_id"])
        raw["attempt"] = 1
        self.jobs.store.save(raw)
        with self.assertRaises(JobRuntimeError):
            self.jobs.retry_or_stop(final["job_id"])

    def test_f4_provider_label_message_metadata_actions_do_not_change_identity(self):
        for threshold in ("no_progress_threshold", "cycle_threshold", "stuck_threshold"):
            with self.subTest(threshold=threshold):
                job = self.running(retry_policy=self.retry_config(**{threshold: 2}))
                self.assertEqual(self.worker(ResultExecutor("provider_label_a", variant=1)).run_claimed(job["job_id"]).status, "failed")
                child = self.jobs.retry(job["job_id"], enqueue=True)
                self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
                self.assertEqual(self.worker(ResultExecutor("provider_label_b", variant=2)).run_claimed(child["job_id"]).status, "failed")
                decision = self.jobs.retry_or_stop(child["job_id"])["decision"]
                self.assertEqual(decision["decision"], "REPLAN_REQUIRED")
                history = self.state(job)["history"]
                self.assertEqual(history[0]["state_signature"], history[1]["state_signature"])

    def test_f5_real_controlled_scope_denial_never_retries(self):
        _, claimed = self.controlled_retry()
        executor = self.controlled_executor(lambda workspace: (workspace / "src/b.txt").write_text("unauthorized"))
        outcome = self.worker(executor).run_claimed(claimed["job_id"])
        self.assertEqual(outcome.result["error"]["code"], "mutation_scope_violation")
        failed = self.jobs.show(claimed["job_id"])
        self.assertEqual(failed["error"]["failure_class"], "authority_failure")
        self.assertEqual(self.jobs.retry_or_stop(claimed["job_id"])["decision"]["decision"], "STOP")

    def test_f5_adjacent_runtime_scope_denials_never_retries(self):
        for failure in ("write_not_authorized", "protected_path_violation", "path_escape_attempt", "write_scope_invalid", "provider_sandbox_unverified", "validation_failed"):
            with self.subTest(failure=failure):
                _, claimed = self.controlled_retry()
                executor = self.controlled_executor(lambda _: None)
                controlled = executor.controlled_write_runtime
                def reject(request, context, adapter):
                    from runtime.actions.models import ExecutionScope
                    return controlled._rejected(request, ExecutionScope.from_dict(request.execution_scope), failure,
                                               "Structured runtime denial", ())
                with patch.object(controlled, "execute", side_effect=reject):
                    outcome = self.worker(executor).run_claimed(claimed["job_id"])
                self.assertEqual(outcome.result["error"]["code"], failure)
                self.assertEqual(self.jobs.retry_or_stop(claimed["job_id"])["decision"]["decision"], "STOP")

    def test_f6_mutable_source_changed_before_first_retry_fails_closed(self):
        changes = {"task": "Unrelated work", "input_refs": [{"ref_type": "other", "ref": "changed"}],
                   "agent": "reviewer", "skill": "review", "capability": "independent_review", "risk_level": "medium",
                   "review_required": True, "provider": "codex", "dry_run": True}
        for field, value in changes.items():
            with self.subTest(field=field):
                claimed = self.running()
                self.assertEqual(self.worker(ResultExecutor("provider_failed")).run_claimed(claimed["job_id"]).status, "failed")
                raw = self.jobs.store.load(claimed["job_id"])
                original = deepcopy(raw)
                raw[field] = value
                self.jobs.store.save(raw)
                try:
                    with self.assertRaises(JobRuntimeError):
                        self.jobs.retry_or_stop(claimed["job_id"])
                finally:
                    self.jobs.store.save(original)

    def test_f6_changed_plan_current_step_scope_and_mode_fails_before_first_retry(self):
        for field in ("plan", "current_step", "scope", "mode"):
            with self.subTest(field=field):
                if field in {"scope", "mode"}:
                    _, claimed = self.controlled_retry()
                    executor = self.controlled_executor(lambda _: None)
                else:
                    plan = {"plan_id": f"plan-{field}", "steps": [{"step_id": "A", "task": "Repair failed unit A"},
                                                                         {"step_id": "B", "task": "Sibling"}]}
                    claimed = self.running(continuation_plan=plan)
                    executor = ResultExecutor("provider_failed")
                self.worker(executor).run_claimed(claimed["job_id"])
                raw = self.jobs.store.load(claimed["job_id"])
                original = deepcopy(raw)
                if field == "plan": raw["continuation_plan"]["steps"][1]["task"] = "Changed plan"
                elif field == "current_step": raw["continuation"]["current_step_id"] = "B"
                elif field == "scope": raw["execution_scope"]["max_changed_files"] = 5
                else: raw.update(execution_mode="READ_ONLY", execution_scope=None)
                self.jobs.store.save(raw)
                try:
                    with self.assertRaises(JobRuntimeError):
                        self.jobs.retry_or_stop(claimed["job_id"])
                finally:
                    self.jobs.store.save(original)

    def test_f6_redigested_failed_execution_request_cannot_replace_admission(self):
        claimed = self.running()
        outcome = self.worker(ResultExecutor("provider_failed")).run_claimed(claimed["job_id"])
        path = self.executions._path(outcome.execution_id)
        record = json.loads(path.read_text())
        record["request"]["context_refs"].append({"ref_type": "other", "ref": "unrelated"})
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(JobRuntimeError, "immutable admission|Decision result trace does not bind exact work/evidence"):
            self.jobs.retry_or_stop(claimed["job_id"])

    def test_f7_reviewer_no_progress_preserves_structured_replan_and_plan(self):
        plan = {"plan_id": "plan-review-retry", "steps": [{"step_id": "A", "task": "Repair failed unit A"}]}
        created = self.jobs.create(self.payload(review_required=True, continuation_plan=plan,
                                              retry_policy=self.retry_config(no_progress_threshold=2)))
        self.jobs.enqueue(created["job_id"])
        providers = FileProviderArtifactStore(self.root / "provider")
        reviewer = ReviewerRuntime(DeterministicVerifier(self.executions, providers),
                                   ReviewContextBuilder(REPOSITORY_ROOT, self.executions, providers),
                                   FakeReviewer("RETRY"), FileReviewStore(self.root / "reviews"),
                                   clock=lambda: self.clock_value,
                                   id_factory=IDs("review-retry"))
        executor = ResultExecutor()
        worker = self.worker(executor, reviewer=reviewer)
        first = worker.run_once()
        self.assertEqual(first.retry_decision["decision"], "RETRY")
        second = worker.run_once()
        self.assertEqual(second.status, "failed")
        self.assertEqual(second.retry_decision["decision"], "REPLAN_REQUIRED")
        self.assertEqual(second.retry_decision["reason_code"], "no_progress_threshold_reached")
        self.assertEqual(second.to_dict()["retry_decision"], second.retry_decision)
        self.assertIsNone(second.retry_job_id)
        self.assertNotEqual(second.error["code"], "lifecycle_update_error")
        self.assertEqual(self.jobs.show(created["job_id"])["continuation_plan"], plan)
        jobs = self.jobs.list()
        self.assertEqual(len(jobs), 2)
        self.assertTrue(all("graph_plan" not in job and "graph_binding" not in job for job in jobs))

    def test_f8_redigested_boolean_versions_rejected_by_model_schema_and_store(self):
        failed = self.fail(self.running())
        policy = self.jobs.retry_store.load_policy(failed["retry_policy"])
        for field in ("schema_version", "policy_version"):
            for invalid in (True, False, "1", 1.0, 2, None):
                with self.subTest(field=field, invalid=invalid):
                    value = policy.to_dict()
                    value[field] = invalid
                    value["policy_digest"] = policy_digest(value)
                    with self.assertRaises(RetryContractError):
                        RetryPolicy.from_dict(value)
                    with self.assertRaises(JobValidationError):
                        self.jobs.retry_store.policy_validator.validate(value)
                    with self.assertRaises(RetryStoreError):
                        self.jobs.retry_store._validate_policy(value, policy.binding)
        self.assertEqual(RetryPolicy.from_dict(policy.to_dict()), policy)

    def test_f8_repair_request_loader_requires_canonical_constraint(self):
        _, claimed = self.controlled_retry()
        worker = self.worker(ResultExecutor())
        request = worker._build_request(claimed, "execution-constraint", worker.resolver.resolve(claimed)).to_dict()
        for field, value in (("allowed_paths", ["src/a/../../b.txt"]), ("capability", "deployment"), ("failed_unit_id", "B")):
            with self.subTest(field=field), self.assertRaises(ExecutionContractError):
                changed = deepcopy(request)
                changed["retry_repair_scope"][field] = value
                ExecutionRequest.from_persisted_dict(changed)


class RetryCleanupTests(unittest.TestCase):
    """Inject failures into the real stress method without starting worker threads."""

    def check_failure_cleanup(self, phase, *, duplicate_assertion=False):
        case = RetryRepairTests("test_f1_concurrent_direct_delivery_stress_calls_executor_once")
        executor = ResultExecutor(hold=True)
        pool, active = MagicMock(), Mock()
        pool.__enter__.return_value = pool
        pool.submit.return_value = active
        pool.map.return_value = [Mock(status="execution_reserved") for _ in range(7)]
        release_at_shutdown = []

        def shutdown(*exc):
            release_at_shutdown.append(executor.release.is_set())
            return False

        pool.__exit__.side_effect = shutdown
        failure = TimeoutError("Injected result timeout") if phase == "timeout" else RuntimeError("Injected delivery failure")
        expected = AssertionError if phase == "entry" or duplicate_assertion else type(failure)
        if phase == "submission":
            pool.submit.side_effect = failure
        elif phase == "duplicates":
            if duplicate_assertion:
                pool.map.return_value = [Mock(status="worker_error") for _ in range(7)]
            else:
                pool.map.side_effect = failure
        elif phase == "timeout":
            active.result.side_effect = failure

        with patch.object(case, "retry_claim", return_value=(None, {"job_id": "cleanup-retry"})), \
                patch.object(case, "worker", return_value=Mock()), \
                patch(f"{__name__}.ResultExecutor", return_value=executor), \
                patch(f"{__name__}.ThreadPoolExecutor", return_value=pool) as factory, \
                patch.object(executor.entered, "wait", return_value=phase != "entry") as entered:
            with self.assertRaises(expected) as caught:
                case.test_f1_concurrent_direct_delivery_stress_calls_executor_once()

        factory.assert_called_once_with(max_workers=8)
        self.assertEqual(release_at_shutdown, [True])
        self.assertTrue(executor.release.is_set())
        if expected is not AssertionError:
            self.assertIs(caught.exception, failure)
        if phase == "submission":
            entered.assert_not_called()
        else:
            entered.assert_called_once_with(10)
        if phase in {"entry", "submission"}:
            pool.map.assert_not_called()
        else:
            pool.map.assert_called_once()
            self.assertEqual(list(pool.map.call_args.args[1]), list(range(7)))
        if phase == "timeout":
            active.result.assert_called_once_with(timeout=10)
        else:
            active.result.assert_not_called()

    def test_entry_failure_signals_release_before_shutdown(self):
        self.check_failure_cleanup("entry")

    def test_submission_failure_signals_release_before_shutdown(self):
        self.check_failure_cleanup("submission")

    def test_duplicate_failure_signals_release_before_shutdown(self):
        for assertion in (False, True):
            with self.subTest(assertion=assertion):
                self.check_failure_cleanup("duplicates", duplicate_assertion=assertion)

    def test_result_timeout_preserves_error_and_signals_release(self):
        self.check_failure_cleanup("timeout")


if __name__ == "__main__":
    unittest.main()
