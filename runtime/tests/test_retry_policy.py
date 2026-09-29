from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.budget.models import BudgetBinding
from runtime.budget.runtime import ExecutionBudgetRuntime
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionResult
from runtime.retry.models import MAX_HISTORY, RetryContractError, RetryPolicySpec
from runtime.retry.store import RetryStoreError
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class IDs:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"{self.prefix}-{self.value:03d}"


class NeverExecutor:
    supported_execution_modes = frozenset({"READ_ONLY", "CONTROLLED_WRITE"})

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        raise AssertionError("executor must not be called during this test")


class RetryHarness:
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock_value = "2026-09-28T12:00:00Z"
        self.ids = IDs("job-core06")
        self.jobs = JobRuntime(
            self.root / "state" / "jobs",
            clock=lambda: self.clock_value,
            id_factory=self.ids,
        )
        self.executions = FileExecutionStore(self.root / "state" / "executions")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def retry_config(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "no_progress_threshold": None,
            "stuck_threshold": None,
            "cycle_threshold": None,
        }
        value.update(overrides)
        return value

    @classmethod
    def payload(cls, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Repair failed unit A",
            "task_class": "software",
            "agent": "software",
            "workflow": "software",
            "capability": "debugging",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": False,
            "max_attempts": 4,
            "input_refs": [],
            "output_refs": [],
            "created_by": "core06-test",
            "retry_policy": cls.retry_config(),
        }
        value.update(overrides)
        return value

    def running(self, **overrides: object) -> dict[str, object]:
        job = self.jobs.create(self.payload(**overrides))
        self.jobs.enqueue(str(job["job_id"]))
        claimed = self.jobs.claim(claimed_by="core06-worker", lease_seconds=30)
        assert claimed is not None
        return claimed

    def fail(
        self,
        job: dict[str, object],
        *,
        code: str = "executor_error",
        failure_class: str | None = None,
        retryable: bool = False,
        output_refs: list[dict[str, str]] | None = None,
        message: str = "deterministic failure",
        progress_evidence_digest: str | None = None,
    ) -> dict[str, object]:
        if isinstance(job, str):
            unittest.TestCase.fail(self, job)
        return self.jobs.fail(
            str(job["job_id"]),
            code=code,
            message=message,
            retryable=retryable,
            failure_class=failure_class,
            output_refs=output_refs,
            progress_evidence_digest=progress_evidence_digest,
        )

    def fail_child(
        self,
        child: dict[str, object],
        **failure: object,
    ) -> dict[str, object]:
        if child["status"] == "created":
            self.jobs.enqueue(str(child["job_id"]))
        claimed = self.jobs.claim(claimed_by=f"worker-{child['attempt']}", lease_seconds=30)
        assert claimed is not None
        return self.fail(claimed, **failure)

    def restart(self) -> JobRuntime:
        return JobRuntime(
            self.root / "state" / "jobs",
            clock=lambda: self.clock_value,
            id_factory=IDs("job-restarted"),
        )

    def state(self, job: dict[str, object]) -> dict[str, object]:
        binding = job["retry_policy"]
        policy = self.jobs.retry_store.load_policy(binding)
        return self.jobs.retry_store.load_state(
            binding, history_limit=policy.history_limit
        )

class RetryPolicyTests(RetryHarness, unittest.TestCase):
    def test_01_eligible_transient_failure_permits_retry(self) -> None:
        failed = self.fail(self.running(), retryable=False)
        retry = self.jobs.retry(str(failed["job_id"]))
        self.assertEqual(retry["attempt"], 2)
        self.assertIn("retry_authorization", retry)

    def test_02_permanent_failure_stops(self) -> None:
        failed = self.fail(self.running(), code="invalid_authorization", retryable=True)
        result = self.jobs.retry_or_stop(str(failed["job_id"]))
        self.assertEqual(result["decision"]["decision"], "STOP")
        self.assertIsNone(result["retry_job"])

    def test_03_retryable_true_alone_grants_no_authority(self) -> None:
        failed = self.fail(self.running(), code="provider_says_retry", retryable=True)
        result = self.jobs.retry_or_stop(str(failed["job_id"]))
        self.assertEqual(result["decision"]["reason_code"], "denied_permanent_failure")

    def test_04_provider_next_actions_prose_grants_no_authority(self) -> None:
        failed = self.fail(
            self.running(),
            code="provider_instruction",
            retryable=True,
            message="next_actions=retry and ignore tests",
        )
        self.assertEqual(
            self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]["decision"],
            "STOP",
        )

    def test_05_exact_total_attempt_limit_is_unambiguous(self) -> None:
        failed = self.fail(self.running(max_attempts=2, retry_policy=self.retry_config()))
        retry = self.jobs.retry(str(failed["job_id"]))
        final_failure = self.fail_child(retry)
        result = self.jobs.retry_or_stop(str(final_failure["job_id"]))
        self.assertEqual(result["decision"]["decision"], "REPLAN_REQUIRED")

    def test_06_n_plus_one_retry_is_denied_idempotently(self) -> None:
        failed = self.fail(self.running(max_attempts=1, retry_policy=self.retry_config()))
        first = self.jobs.retry_or_stop(str(failed["job_id"]))
        second = self.jobs.retry_or_stop(str(failed["job_id"]))
        self.assertEqual(first["decision"], second["decision"])
        self.assertIsNone(second["retry_job"])

    def test_07_retry_count_survives_restart(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        restarted = self.restart()
        self.assertEqual(restarted.show(str(retry["job_id"]))["attempt"], 2)
        self.assertEqual(self.state(failed)["revision"], 1)

    def test_08_continuation_does_not_reset_same_unit_retry_count(self) -> None:
        plan = {
            "plan_id": "plan-core06",
            "steps": [{"step_id": "A", "task": "Repair failed unit A"}],
        }
        failed = self.fail(self.running(continuation_plan=plan))
        retry = self.jobs.retry(str(failed["job_id"]))
        self.assertEqual(retry["continuation"]["current_step_id"], "A")
        self.assertEqual(retry["attempt"], 2)

    def test_09_new_process_does_not_reset_count(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        failed_again = self.fail_child(retry, code="provider_failed")
        restarted = self.restart()
        retry2 = restarted.retry(str(failed_again["job_id"]))
        self.assertEqual(retry2["attempt"], 3)

    def test_10_retry_uses_same_core05_budget(self) -> None:
        failed = self.fail(self.running(execution_budget={"max_execution_units": 3}))
        retry = self.jobs.retry(str(failed["job_id"]))
        self.assertEqual(retry["execution_budget"], failed["execution_budget"])

    def test_11_changed_failed_unit_identity_invalidates_retry(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        raw = self.jobs.store.load(str(retry["job_id"]))
        raw["retry_authorization"]["failed_unit_id"] = "B"
        self.jobs.store.save(raw)
        with self.assertRaisesRegex(JobRuntimeError, "digest|canonical decision"):
            self.jobs.show(str(retry["job_id"]))

    def test_12_changed_task_invalidates_stale_retry(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        raw = self.jobs.store.load(str(retry["job_id"]))
        raw["task"] = "Changed task"
        self.jobs.store.save(raw)
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(str(retry["job_id"]))

    def test_13_changed_plan_or_current_step_invalidates_retry(self) -> None:
        plan = {"plan_id": "plan-exact", "steps": [{"step_id": "A", "task": "Repair failed unit A"}]}
        failed = self.fail(self.running(continuation_plan=plan))
        self.jobs.retry(str(failed["job_id"]))
        raw = self.jobs.store.load(str(failed["job_id"]))
        raw["continuation"]["current_step_id"] = "B"
        self.jobs.store.save(raw)
        with self.assertRaises(JobRuntimeError):
            self.jobs.retry(str(failed["job_id"]))

    def test_14_changed_material_inputs_invalidate_retry(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        raw = self.jobs.store.load(str(retry["job_id"]))
        raw["input_refs"] = [{"ref_type": "other", "ref": "changed"}]
        self.jobs.store.save(raw)
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(str(retry["job_id"]))

    def test_15_repair_outside_allowed_scope_is_rejected(self) -> None:
        scope = {
            "project_root": str(self.root),
            "allowed_paths": ["src/a.py"],
            "forbidden_paths": [],
            "write_mode": "CREATE_OR_MODIFY",
            "max_changed_files": 1,
            "max_artifact_bytes": 1024,
            "allow_tests": False,
            "allow_git_reads": False,
            "allow_protected_paths": False,
        }
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                execution_mode="CONTROLLED_WRITE",
                execution_scope=scope,
                review_required=True,
            )
        )
        approvals = ApprovalRuntime(
            self.jobs,
            FileApprovalStore(self.root / "state" / "approvals"),
            execution_store=self.executions,
            clock=lambda: self.clock_value,
        )
        request = approvals.request_execution(
            str(created["job_id"]), reason="Approve bounded CORE-06 test repair"
        ).request
        approvals.resolve(
            request.approval_id,
            decision="APPROVED",
            decided_by="local-owner",
            reason="Proceed with the bounded repair test",
        )
        claimed = self.jobs.claim(claimed_by="controlled-worker", lease_seconds=30)
        assert claimed is not None
        failed = self.fail(claimed)
        retry = self.jobs.retry(str(failed["job_id"]))
        with self.assertRaisesRegex(RetryStoreError, "outside"):
            self.jobs.retry_runtime.validate_repair_request(
                retry, unit_ids=[failed["job_id"]], paths=["src/b.py"]
            )

    def test_16_sibling_unit_repair_is_rejected(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        with self.assertRaisesRegex(RetryStoreError, "failed unit"):
            self.jobs.retry_runtime.validate_repair_request(retry, unit_ids=["B"])

    def test_17_retry_does_not_broaden_tool_capability(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        with self.assertRaisesRegex(RetryStoreError, "capability"):
            self.jobs.retry_runtime.validate_repair_request(
                retry, unit_ids=[failed["job_id"]], capabilities=["deployment"]
            )

    def test_18_repeated_identical_failure_reaches_no_progress(self) -> None:
        policy = self.retry_config(no_progress_threshold=2)
        failed = self.fail(self.running(retry_policy=policy))
        retry = self.jobs.retry(str(failed["job_id"]))
        second = self.fail_child(retry)
        decision = self.jobs.retry_or_stop(str(second["job_id"]))["decision"]
        self.assertEqual(decision["reason_code"], "no_progress_threshold_reached")

    def test_19_trusted_evidence_improvement_allows_retry(self) -> None:
        policy = self.retry_config(no_progress_threshold=2)
        failed = self.fail(self.running(retry_policy=policy))
        retry = self.jobs.retry(str(failed["job_id"]))
        second = self.fail_child(
            retry,
            progress_evidence_digest="1" * 64,
        )
        self.assertIsNotNone(self.jobs.retry_or_stop(str(second["job_id"]))["retry_job"])

    def test_20_no_progress_history_survives_restart(self) -> None:
        policy = self.retry_config(no_progress_threshold=2)
        failed = self.fail(self.running(retry_policy=policy))
        retry = self.jobs.retry(str(failed["job_id"]))
        second = self.fail_child(retry)
        decision = self.restart().retry_or_stop(str(second["job_id"]))["decision"]
        self.assertEqual(decision["decision"], "REPLAN_REQUIRED")

    def test_21_stuck_threshold_stops_local_retry(self) -> None:
        policy = self.retry_config(stuck_threshold=2)
        failed = self.fail(self.running(retry_policy=policy), code="executor_error")
        retry = self.jobs.retry(str(failed["job_id"]))
        second = self.fail_child(retry, code="provider_failed")
        decision = self.jobs.retry_or_stop(str(second["job_id"]))["decision"]
        self.assertEqual(decision["reason_code"], "stuck_threshold_reached")

    def test_22_provider_progress_claim_cannot_reset_no_progress(self) -> None:
        policy = self.retry_config(no_progress_threshold=2)
        failed = self.fail(self.running(retry_policy=policy), message="no progress")
        retry = self.jobs.retry(str(failed["job_id"]))
        second = self.fail_child(retry, message="I made progress")
        decision = self.jobs.retry_or_stop(str(second["job_id"]))["decision"]
        self.assertEqual(decision["reason_code"], "no_progress_threshold_reached")

    def test_23_direct_self_cycle_is_detected(self) -> None:
        policy = self.retry_config(cycle_threshold=2)
        failed = self.fail(self.running(retry_policy=policy))
        retry = self.jobs.retry(str(failed["job_id"]))
        second = self.fail_child(retry)
        self.assertEqual(
            self.jobs.retry_or_stop(str(second["job_id"]))["decision"]["reason_code"],
            "retry_cycle_detected",
        )

    def test_24_two_state_cycle_is_detected(self) -> None:
        policy = self.retry_config(cycle_threshold=2)
        first = self.fail(self.running(retry_policy=policy), code="executor_error")
        second = self.fail_child(self.jobs.retry(str(first["job_id"])), code="provider_failed")
        third = self.fail_child(self.jobs.retry(str(second["job_id"])), code="executor_error")
        self.assertEqual(
            self.jobs.retry_or_stop(str(third["job_id"]))["decision"]["reason_code"],
            "retry_cycle_detected",
        )

    def test_25_longer_cycle_is_detected(self) -> None:
        policy = self.retry_config(cycle_threshold=2, cycle_window=8)
        codes = ("executor_error", "provider_failed", "execution_storage_error", "executor_error")
        failed = self.fail(self.running(max_attempts=5, retry_policy=policy), code=codes[0])
        for code in codes[1:]:
            failed = self.fail_child(self.jobs.retry(str(failed["job_id"])), code=code)
        self.assertEqual(
            self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]["reason_code"],
            "retry_cycle_detected",
        )

    def test_26_genuine_progress_avoids_cycle_false_positive(self) -> None:
        policy = self.retry_config(cycle_threshold=2)
        first = self.fail(self.running(retry_policy=policy), progress_evidence_digest="1" * 64)
        second = self.fail_child(self.jobs.retry(str(first["job_id"])), progress_evidence_digest="2" * 64)
        self.assertIsNotNone(self.jobs.retry_or_stop(str(second["job_id"]))["retry_job"])

    def test_27_cycle_history_is_bounded(self) -> None:
        with self.assertRaises(RetryContractError):
            RetryPolicySpec.from_input(
                {"history_limit": MAX_HISTORY + 1}, max_attempts=4
            )

    def test_28_local_exhaustion_returns_replan_required(self) -> None:
        failed = self.fail(self.running(max_attempts=1, retry_policy=self.retry_config()))
        self.assertEqual(
            self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]["decision"],
            "REPLAN_REQUIRED",
        )

    def test_29_replan_boundary_does_not_modify_plan(self) -> None:
        plan = {"plan_id": "plan-replan", "steps": [{"step_id": "A", "task": "Repair failed unit A"}]}
        failed = self.fail(self.running(max_attempts=1, retry_policy=self.retry_config(), continuation_plan=plan))
        before = deepcopy(failed["continuation_plan"])
        self.jobs.retry_or_stop(str(failed["job_id"]))
        self.assertEqual(self.jobs.show(str(failed["job_id"]))["continuation_plan"], before)

    def test_30_replan_boundary_grants_no_planner_authority(self) -> None:
        failed = self.fail(self.running(max_attempts=1, retry_policy=self.retry_config()))
        decision = self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]
        self.assertNotIn("planner_authority", decision)

    def test_31_replan_grants_no_retry_or_continuation_authority(self) -> None:
        failed = self.fail(self.running(max_attempts=1, retry_policy=self.retry_config()))
        result = self.jobs.retry_or_stop(str(failed["job_id"]))
        self.assertIsNone(result["retry_job"])
        self.assertNotIn("continuation", result["decision"])

    def test_32_no_orch01_graph_runtime_is_implemented(self) -> None:
        self.assertFalse((REPOSITORY_ROOT / "runtime" / "graph").exists())
        self.assertFalse((REPOSITORY_ROOT / "runtime" / "orchestration").exists())

    def test_33_crash_before_retry_execution_preserves_reservation(self) -> None:
        failed = self.fail(self.running())
        decision = self.jobs.retry_runtime.reserve(failed)
        self.assertIsNotNone(decision.retry_job_id)
        retry = self.restart().retry(str(failed["job_id"]))
        self.assertEqual(retry["job_id"], decision.retry_job_id)

    def test_34_post_budget_reservation_restart_does_not_refund(self) -> None:
        failed = self.fail(self.running(execution_budget={"max_execution_units": 2}))
        retry = self.jobs.retry(str(failed["job_id"]))
        budget = ExecutionBudgetRuntime(self.jobs.budget_store, wall_clock=lambda: self.clock_value)
        budget.reserve_execution(
            retry["execution_budget"], execution_id="execution-crash", job_id=retry["job_id"]
        )
        restarted = ExecutionBudgetRuntime(self.restart().budget_store, wall_clock=lambda: self.clock_value)
        state = restarted.state(retry["execution_budget"]).state
        self.assertEqual(state["dimensions"]["execution_units"]["consumed"], 1)

    def test_35_successful_retry_reconciliation_avoids_duplicate_external_work(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]), enqueue=True)
        claimed = self.jobs.claim(claimed_by="reconcile-worker", lease_seconds=30)
        assert claimed is not None
        worker = Worker(
            self.jobs,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            NeverExecutor(),
            self.executions,
            clock=lambda: self.clock_value,
            worker_id="reconcile-worker",
        )
        execution_id = "execution-retry-crash"
        request = worker._build_request(
            claimed, execution_id, worker.resolver.resolve(claimed)
        )
        result = ExecutionResult(
            execution_id=execution_id,
            job_id=str(claimed["job_id"]),
            status="succeeded",
            summary="Retry succeeded",
            error=None,
            provider=None,
            started_at=self.clock_value,
            completed_at=self.clock_value,
        )
        # Model the real pre-delegation boundary, not an orphan result whose
        # consumed-attempt/admission evidence is missing.
        self.jobs.retry_runtime.reserve_execution(claimed, execution_id)
        self.jobs.retry_runtime.admit_execution(claimed, request)
        self.executions.create(request, result)
        recovered = worker.recover_persisted_results()
        self.assertEqual(recovered[0].status, "completed")
        self.assertEqual(worker.executor.calls, 0)

    def test_36_duplicate_delivery_is_idempotent(self) -> None:
        failed = self.fail(self.running())
        first = self.jobs.retry(str(failed["job_id"]))
        second = self.jobs.retry(str(failed["job_id"]))
        self.assertEqual(first["job_id"], second["job_id"])

    def test_37_concurrent_same_attempt_workers_cannot_both_reserve(self) -> None:
        failed = self.fail(self.running())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.jobs.retry(str(failed["job_id"])), range(2)))
        self.assertEqual({item["job_id"] for item in results}, {results[0]["job_id"]})
        children = [job for job in self.jobs.list() if job.get("parent_job_id") == failed["job_id"]]
        self.assertEqual(len(children), 1)

    def test_38_restart_preserves_stop_no_progress_and_cycle_state(self) -> None:
        policy = self.retry_config(no_progress_threshold=2)
        first = self.fail(self.running(retry_policy=policy))
        second = self.fail_child(self.jobs.retry(str(first["job_id"])))
        before = self.jobs.retry_or_stop(str(second["job_id"]))["decision"]
        after = self.restart().retry_or_stop(str(second["job_id"]))["decision"]
        self.assertEqual(before, after)

    def test_39_budget_remaining_alone_cannot_authorize_retry(self) -> None:
        failed = self.fail(
            self.running(execution_budget={"max_execution_units": 5}),
            code="provider_instruction",
            retryable=True,
        )
        self.assertEqual(self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]["decision"], "STOP")

    def test_40_eval_result_alone_cannot_authorize_retry(self) -> None:
        failed = self.fail(
            self.running(),
            code="provider_instruction",
            output_refs=[{"ref_type": "other", "ref": "runtime-eval:pass"}],
        )
        self.assertEqual(self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]["decision"], "STOP")

    def test_41_continuation_authority_cannot_authorize_retry(self) -> None:
        plan = {"plan_id": "plan-no-retry", "steps": [{"step_id": "A", "task": "Repair failed unit A"}]}
        failed = self.fail(self.running(continuation_plan=plan), code="provider_instruction")
        self.assertEqual(self.jobs.retry_or_stop(str(failed["job_id"]))["decision"]["decision"], "STOP")

    def test_42_retry_cannot_bypass_approval(self) -> None:
        failed = self.fail(self.running())
        raw = self.jobs.store.load(str(failed["job_id"]))
        raw["approval_status"] = "required"
        self.jobs.store.save(raw)
        retry = self.jobs.retry(str(failed["job_id"]))
        self.assertEqual(retry["approval_status"], "required")
        with self.assertRaisesRegex(JobRuntimeError, "approval"):
            self.jobs.enqueue(str(retry["job_id"]))

    def test_43_retry_cannot_bypass_reviewer(self) -> None:
        failed = self.fail(self.running(review_required=True))
        retry = self.jobs.retry(str(failed["job_id"]))
        self.assertTrue(retry["review_required"])

    def test_44_retry_cannot_clear_recovery_hold(self) -> None:
        failed = self.fail(self.running())
        binding = failed["retry_policy"]
        self.jobs.retry_store._state_path(binding["policy_id"]).unlink()
        with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
            self.jobs.retry(str(failed["job_id"]))

    def test_45_retry_grants_no_new_controlled_write_authority(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        authorization = retry["retry_authorization"]
        self.assertEqual(authorization["repair_scope"]["execution_mode"], "READ_ONLY")
        self.assertEqual(authorization["repair_scope"]["allowed_paths"], [])

    def test_46_retry_grants_no_git_authority(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        serialized = json.dumps(retry["retry_authorization"], sort_keys=True)
        self.assertNotIn("git_authority", serialized)

    def test_47_retry_grants_no_deployment_authority(self) -> None:
        failed = self.fail(self.running())
        retry = self.jobs.retry(str(failed["job_id"]))
        serialized = json.dumps(retry["retry_authorization"], sort_keys=True)
        self.assertNotIn("deployment", serialized)

    def test_48_policy_rejects_negative_bool_huge_unknown_and_zero_thresholds(self) -> None:
        cases = (
            {"max_total_attempts": -1},
            {"max_total_attempts": True},
            {"max_total_attempts": 33},
            {"cycle_window": 10_000},
            {"no_progress_threshold": 0},
            {
                "allowed_failure_classes": ["permanent_failure"],
                "denied_failure_classes": [],
            },
            {"unknown": 1},
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(RetryContractError):
                RetryPolicySpec.from_input(value, max_attempts=4)

    def test_49_path_traversal_retry_identity_is_rejected(self) -> None:
        with self.assertRaises(RetryStoreError):
            self.jobs.retry_store._policy_path("../escape")

    def test_50_history_deletion_and_state_reset_fail_closed(self) -> None:
        failed = self.fail(self.running())
        self.jobs.retry(str(failed["job_id"]))
        state = self.state(failed)
        binding = failed["retry_policy"]
        policy_id = binding["policy_id"]
        event = next(self.jobs.retry_store._event_root(policy_id).glob("*.json"))
        event.unlink()
        with self.assertRaises(RetryStoreError):
            self.jobs.retry_store.load_state(binding, history_limit=MAX_HISTORY)

    def test_51_history_directory_scan_is_bounded_and_rejects_unexpected_entries(self) -> None:
        failed = self.fail(self.running())
        self.jobs.retry(str(failed["job_id"]))
        binding = failed["retry_policy"]
        root = self.jobs.retry_store._event_root(binding["policy_id"])
        (root / "unexpected.txt").write_text("not canonical", encoding="utf-8")
        with self.assertRaisesRegex(RetryStoreError, "unexpected"):
            self.jobs.retry_store.load_state(binding, history_limit=MAX_HISTORY)


if __name__ == "__main__":
    unittest.main()
