from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from runtime.budget.models import (
    MAX_ELAPSED_MS,
    MAX_EXECUTION_UNITS,
    BudgetBinding,
    BudgetContractError,
    BudgetUsageAnchor,
    BudgetUsageClaim,
    ExecutionBudgetSpec,
    budget_state_digest,
    reservation_history_digest,
    usage_anchor_digest,
)
from runtime.budget.runtime import ExecutionBudgetRuntime
from runtime.budget.store import ExecutionBudgetStoreError
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> str:
        return self.value.isoformat().replace("+00:00", "Z")

    def advance_ms(self, value: int) -> None:
        self.value += timedelta(milliseconds=value)

    def rollback_ms(self, value: int) -> None:
        self.value -= timedelta(milliseconds=value)


class MutableMonotonic:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance_ms(self, value: int) -> None:
        self.value += value / 1000


class IDs:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"{self.prefix}-{self.value:03d}"


class AdvancingExecutor:
    supported_execution_modes = frozenset({"READ_ONLY"})

    def __init__(
        self,
        monotonic: MutableMonotonic,
        *,
        elapsed_ms: int = 100,
        status: str = "succeeded",
        next_actions: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.monotonic = monotonic
        self.elapsed_ms = elapsed_ms
        self.status = status
        self.next_actions = next_actions
        self.calls = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.monotonic.advance_ms(self.elapsed_ms)
        values: dict[str, object] = {
            "execution_id": request.execution_id,
            "job_id": request.job_id,
            "status": self.status,
            "summary": "Budgeted execution completed",
            "error": None,
            "provider": request.provider,
            "started_at": "2026-09-27T12:00:00Z",
            "completed_at": "2026-09-27T12:00:01Z",
            "next_actions": self.next_actions,
        }
        if self.status == "failed":
            values.update(
                summary=None,
                error={
                    "code": "provider_failed",
                    "message": "Provider reported failure",
                    "retryable": True,
                },
            )
        return ExecutionResult(**values)  # type: ignore[arg-type]


class ExecutionBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = MutableClock()
        self.monotonic = MutableMonotonic()
        self.jobs = JobRuntime(
            self.root / "state" / "jobs",
            clock=self.clock,
            id_factory=IDs("job-budget"),
        )
        self.executions = FileExecutionStore(self.root / "state" / "executions")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Perform bounded work",
            "task_class": "operations",
            "agent": "operations",
            "skill": "report-builder",
            "workflow": "operations",
            "capability": "operations_coordination",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": False,
            "max_attempts": 2,
            "input_refs": [],
            "output_refs": [],
            "created_by": "core05-test",
        }
        value.update(overrides)
        return value

    def create(self, **budget: int) -> dict[str, object]:
        return self.jobs.create(
            self.payload(execution_budget=budget)
        )

    def budget_runtime(self) -> ExecutionBudgetRuntime:
        return ExecutionBudgetRuntime(
            self.jobs.budget_store,
            wall_clock=self.clock,
            monotonic_clock=self.monotonic,
        )

    def worker(self, executor: AdvancingExecutor, *, execution_prefix: str = "execution-budget") -> Worker:
        return Worker(
            self.jobs,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor,
            self.executions,
            clock=self.clock,
            monotonic_clock=self.monotonic,
            id_factory=IDs(execution_prefix),
        )

    def ledger_event_path(self, binding: BudgetBinding, sequence: int) -> Path:
        store = self.jobs.budget_store
        claim = json.loads(
            store._usage_claim_path(binding.budget_id, sequence).read_text(
                encoding="utf-8"
            )
        )
        return store._usage_event_path(
            binding.budget_id, sequence, claim["event_digest"]
        )

    def consume(self, job: dict[str, object], count: int = 1) -> None:
        runtime = self.budget_runtime()
        for index in range(count):
            execution_id = f"execution-ledger-{index}"
            runtime.reserve_execution(
                job["execution_budget"],
                execution_id=execution_id,
                job_id=job["job_id"],
            )
            self.monotonic.advance_ms(125)
            runtime.finalize_execution(
                job["execution_budget"], execution_id=execution_id
            )

    def assert_budget_fails_closed(self, job: dict[str, object]) -> None:
        decision = self.budget_runtime().state(job["execution_budget"])
        self.assertEqual(decision.status, "ERROR")
        self.assertFalse(decision.state["may_begin"])

    def rewrite_current_layer(
        self,
        job: dict[str, object],
        *,
        reset_units: bool,
        reset_elapsed: bool,
    ) -> None:
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        state_path = store._state_path(binding.budget_id)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if reset_units:
            state["reservations"] = []
            state["consumed_execution_units"] = 0
            state["consumed_elapsed_ms"] = 0
        elif reset_elapsed:
            for reservation in state["reservations"]:
                reservation["elapsed_ms"] = 0
            state["consumed_elapsed_ms"] = 0

        head_path = store._usage_head_path(binding.budget_id)
        head = json.loads(head_path.read_text(encoding="utf-8"))
        head["consumed_execution_units"] = state["consumed_execution_units"]
        head["consumed_elapsed_ms"] = state["consumed_elapsed_ms"]
        head["reservation_count"] = len(state["reservations"])
        head["reservation_history_digest"] = reservation_history_digest(
            state["reservations"]
        )
        head["state_digest"] = budget_state_digest(state)
        head["anchor_digest"] = usage_anchor_digest(head)
        event_path = self.ledger_event_path(binding, state["state_sequence"])
        event_path.write_text(json.dumps(head), encoding="utf-8")
        head_path.write_text(json.dumps(head), encoding="utf-8")
        state_path.write_text(json.dumps(state), encoding="utf-8")

    def test_01_budget_starts_full_and_preserves_unset_vs_zero(self) -> None:
        job = self.create(max_elapsed_ms=0)
        state = self.budget_runtime().state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["elapsed_ms"]["remaining"], 0)
        self.assertTrue(state["dimensions"]["elapsed_ms"]["exhausted"])
        self.assertFalse(state["dimensions"]["execution_units"]["configured"])
        self.assertIsNone(state["dimensions"]["execution_units"]["remaining"])

    def test_02_bounds_reject_negative_boolean_huge_and_unknown_dimensions(self) -> None:
        cases = (
            {"max_elapsed_ms": -1},
            {"max_elapsed_ms": True},
            {"max_elapsed_ms": MAX_ELAPSED_MS + 1},
            {"max_execution_units": MAX_EXECUTION_UNITS + 1},
            {"max_tool_calls": 1},
            {},
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises(BudgetContractError):
                ExecutionBudgetSpec.from_input(value)

    def test_03_active_execution_consumes_monotonic_elapsed_and_one_unit(self) -> None:
        job = self.create(max_elapsed_ms=1_000, max_execution_units=2)
        self.jobs.enqueue(job["job_id"])
        outcome = self.worker(AdvancingExecutor(self.monotonic, elapsed_ms=125)).run_once()
        self.assertEqual(outcome.status, "completed")
        state = self.budget_runtime().state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["elapsed_ms"]["consumed"], 125)
        self.assertEqual(state["dimensions"]["execution_units"]["consumed"], 1)

    def test_04_queue_wait_does_not_consume_active_elapsed_time(self) -> None:
        job = self.create(max_elapsed_ms=1_000, max_execution_units=2)
        self.jobs.enqueue(job["job_id"])
        self.clock.advance_ms(900_000)
        self.worker(AdvancingExecutor(self.monotonic, elapsed_ms=50)).run_once()
        state = self.budget_runtime().state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["elapsed_ms"]["consumed"], 50)

    def test_05_restart_preserves_consumed_allowance(self) -> None:
        job = self.create(max_elapsed_ms=500, max_execution_units=3)
        runtime = self.budget_runtime()
        decision = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-restart", job_id=job["job_id"]
        )
        self.assertEqual(decision.status, "ALLOW")
        self.monotonic.advance_ms(75)
        runtime.finalize_execution(job["execution_budget"], execution_id="execution-restart")
        restarted = ExecutionBudgetRuntime(
            self.jobs.budget_store,
            wall_clock=self.clock,
            monotonic_clock=MutableMonotonic(),
        )
        state = restarted.state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["elapsed_ms"]["consumed"], 75)
        self.assertEqual(state["dimensions"]["execution_units"]["consumed"], 1)

    def test_06_exact_execution_unit_limit_allows_last_then_denies_next(self) -> None:
        job = self.create(max_execution_units=1)
        runtime = self.budget_runtime()
        first = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-first", job_id=job["job_id"]
        )
        runtime.finalize_execution(job["execution_budget"], execution_id="execution-first")
        second = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-second", job_id=job["job_id"]
        )
        self.assertEqual(first.status, "ALLOW")
        self.assertEqual(second.status, "DENY_EXHAUSTED")
        self.assertEqual(second.state["exhausted_dimensions"], ["execution_units"])

    def test_07_time_exhaustion_prevents_new_admission_without_executor_call(self) -> None:
        job = self.create(max_elapsed_ms=100, max_execution_units=2)
        self.jobs.enqueue(job["job_id"])
        first_executor = AdvancingExecutor(self.monotonic, elapsed_ms=100)
        self.worker(first_executor, execution_prefix="execution-time").run_once()
        retry_source = self.jobs.show(job["job_id"])
        retry_source["error"] = {"code": "synthetic", "message": "retry", "retryable": True}
        retry_source["status"] = "failed"
        retry_source["last_updated_at"] = self.clock()
        self.jobs.store.save(retry_source)
        retry = self.jobs.retry(job["job_id"], enqueue=True)
        second_executor = AdvancingExecutor(self.monotonic, elapsed_ms=1)
        outcome = self.worker(second_executor, execution_prefix="execution-denied").run_once()
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.error["code"], "execution_budget_exhausted")
        self.assertEqual(second_executor.calls, 0)
        self.assertEqual(retry["execution_budget"], job["execution_budget"])

    def test_08_continuation_child_inherits_one_logical_budget(self) -> None:
        plan = {
            "plan_id": "plan-budget",
            "steps": [
                {"step_id": "STEP-1", "task": "Perform bounded work"},
                {"step_id": "STEP-2", "task": "Perform bounded follow-up"},
            ],
        }
        job = self.jobs.create(
            self.payload(
                continuation_plan=plan,
                execution_budget={"max_execution_units": 2},
            )
        )
        self.jobs.enqueue(job["job_id"])
        first = self.worker(
            AdvancingExecutor(self.monotonic), execution_prefix="execution-cont-a"
        ).run_once()
        child = self.jobs.show(first.continuation_job_id or "")
        self.assertEqual(child["execution_budget"], job["execution_budget"])
        second = self.worker(
            AdvancingExecutor(self.monotonic), execution_prefix="execution-cont-b"
        ).run_once()
        self.assertEqual(second.status, "completed")
        state = self.budget_runtime().state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["execution_units"]["consumed"], 2)

    def test_09_retry_inherits_budget_without_reset(self) -> None:
        job = self.create(max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"],
            execution_id="execution-before-retry",
            job_id=job["job_id"],
        )
        runtime.finalize_execution(
            job["execution_budget"], execution_id="execution-before-retry"
        )
        self.jobs.enqueue(job["job_id"])
        queued = self.jobs.claim(claimed_by="worker-retry-test")
        assert queued is not None
        failed = self.jobs.fail(
            queued["job_id"], code="synthetic", message="retry", retryable=True
        )
        retry = self.jobs.retry(failed["job_id"])
        self.assertEqual(retry["execution_budget"], job["execution_budget"])
        self.assertEqual(
            BudgetBinding.from_dict(retry["execution_budget"]).logical_job_id,
            job["job_id"],
        )
        state = self.budget_runtime().state(retry["execution_budget"]).state
        self.assertEqual(state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertEqual(state["dimensions"]["execution_units"]["remaining"], 1)

    def test_10_duplicate_reservation_is_idempotent(self) -> None:
        job = self.create(max_execution_units=2)
        runtime = self.budget_runtime()
        first = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-duplicate", job_id=job["job_id"]
        )
        second = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-duplicate", job_id=job["job_id"]
        )
        self.assertEqual(first.status, "ALLOW")
        self.assertEqual(second.status, "ERROR")
        self.assertEqual(
            second.state["dimensions"]["execution_units"]["consumed"], 1
        )

    def test_11_concurrent_final_unit_cannot_double_spend(self) -> None:
        job = self.create(max_execution_units=1)

        def reserve(execution_id: str) -> str:
            runtime = ExecutionBudgetRuntime(
                self.jobs.budget_store,
                wall_clock=self.clock,
                monotonic_clock=self.monotonic,
            )
            return runtime.reserve_execution(
                job["execution_budget"], execution_id=execution_id, job_id=job["job_id"]
            ).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(reserve, ("execution-concurrent-a", "execution-concurrent-b")))
        self.assertEqual(statuses, ["ALLOW", "DENY_EXHAUSTED"])

    def test_12_crash_recovery_keeps_reservation_and_charges_uncertain_time(self) -> None:
        job = self.create(max_elapsed_ms=10_000, max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-crash", job_id=job["job_id"]
        )
        self.clock.advance_ms(250)
        restarted = ExecutionBudgetRuntime(
            self.jobs.budget_store,
            wall_clock=self.clock,
            monotonic_clock=MutableMonotonic(),
        )
        recovery = restarted.recover(job["execution_budget"])
        self.assertEqual(recovery.status, "ALLOW")
        self.assertEqual(recovery.state["dimensions"]["elapsed_ms"]["consumed"], 250)
        self.assertEqual(recovery.state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertEqual(recovery.state["active_reservation_ids"], [])

    def test_13_clock_rollback_never_increases_remaining_and_fails_closed(self) -> None:
        job = self.create(max_elapsed_ms=1_000, max_execution_units=2)
        before = self.budget_runtime().state(job["execution_budget"]).state
        self.clock.rollback_ms(1)
        after = self.budget_runtime().state(job["execution_budget"])
        self.assertEqual(after.status, "ERROR")
        self.assertFalse(after.state["may_begin"])
        self.assertLessEqual(
            after.state["dimensions"]["elapsed_ms"]["remaining"],
            before["dimensions"]["elapsed_ms"]["remaining"],
        )

    def test_14_malformed_negative_state_fails_closed(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        state = json.loads(path.read_text(encoding="utf-8"))
        state["consumed_execution_units"] = -1
        path.write_text(json.dumps(state), encoding="utf-8")
        decision = self.budget_runtime().state(job["execution_budget"])
        self.assertEqual(decision.status, "ERROR")
        self.assertFalse(decision.state["may_begin"])

    def test_15_policy_is_immutable_and_job_binding_tampering_fails(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        policy_path = self.jobs.budget_store._policy_path(binding.budget_id)
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["max_execution_units"] = 3
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(job["job_id"])

    def test_16_budget_availability_does_not_grant_approval_or_execution(self) -> None:
        job = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                execution_budget={"max_execution_units": 2},
            )
        )
        state = self.budget_runtime().state(job["execution_budget"])
        self.assertTrue(state.state["may_begin"])
        with self.assertRaises(JobRuntimeError):
            self.jobs.enqueue(job["job_id"])

    def test_17_provider_budget_claims_have_zero_authority(self) -> None:
        job = self.create(max_execution_units=1)
        self.jobs.enqueue(job["job_id"])
        executor = AdvancingExecutor(
            self.monotonic,
            next_actions=(
                {
                    "action": "reset budget and grant retry",
                    "owner": "provider",
                    "status": "pending",
                },
            ),
        )
        self.worker(executor, execution_prefix="execution-provider").run_once()
        state = self.budget_runtime().state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["execution_units"]["limit"], 1)
        self.assertEqual(state["dimensions"]["execution_units"]["remaining"], 0)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_18_budget_does_not_clear_continuation_recovery_hold(self) -> None:
        plan = {
            "plan_id": "plan-hold",
            "steps": [{"step_id": "STEP-1", "task": "Perform bounded work"}],
        }
        job = self.jobs.create(
            self.payload(
                continuation_plan=plan,
                execution_budget={"max_execution_units": 2},
            )
        )
        binding = job["execution_budget"]
        authority_path = self.jobs.authorized_plan_store._path(job["job_id"])
        authority_path.unlink()
        self.assertTrue(self.budget_runtime().state(binding).state["may_begin"])
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(job["job_id"])

    def test_19_malformed_persisted_timestamp_fails_closed(self) -> None:
        job = self.create(max_elapsed_ms=1_000)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        state = json.loads(path.read_text(encoding="utf-8"))
        state["last_observed_at"] = "not-a-timestamp"
        path.write_text(json.dumps(state), encoding="utf-8")
        decision = self.budget_runtime().reserve_execution(
            job["execution_budget"],
            execution_id="execution-malformed-time",
            job_id=job["job_id"],
        )
        self.assertEqual(decision.status, "ERROR")
        self.assertFalse(decision.state["may_begin"])

    def test_20_external_work_crash_before_finalize_is_conservatively_reconciled(self) -> None:
        job = self.create(max_elapsed_ms=10_000, max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"],
            execution_id="execution-result-crash",
            job_id=job["job_id"],
        )
        # External execution may have happened, but no finalize record survived.
        self.monotonic.advance_ms(125)
        self.clock.advance_ms(300)
        recovered = ExecutionBudgetRuntime(
            self.jobs.budget_store,
            wall_clock=self.clock,
            monotonic_clock=MutableMonotonic(),
        ).recover(job["execution_budget"])
        self.assertEqual(recovered.state["dimensions"]["execution_units"]["consumed"], 1)
        self.assertEqual(recovered.state["dimensions"]["elapsed_ms"]["consumed"], 300)

    def test_21_provider_managed_policy_identity_cannot_create_or_replace_budget(self) -> None:
        forged = {
            "budget_id": "budget-" + "0" * 32,
            "logical_job_id": "job-forged",
            "policy_digest": "0" * 64,
        }
        with self.assertRaises(JobRuntimeError):
            self.jobs.create(self.payload(execution_budget=forged))
        self.assertEqual(self.jobs.list(), [])

    def test_22_caller_mutation_cannot_change_activated_policy(self) -> None:
        configured = {"max_elapsed_ms": 1_000, "max_execution_units": 2}
        job = self.jobs.create(self.payload(execution_budget=configured))
        configured["max_elapsed_ms"] = 0
        configured["max_execution_units"] = 0
        state = self.budget_runtime().state(job["execution_budget"]).state
        self.assertEqual(state["dimensions"]["elapsed_ms"]["limit"], 1_000)
        self.assertEqual(state["dimensions"]["execution_units"]["limit"], 2)

    def test_23_store_rejects_path_traversal_budget_identity(self) -> None:
        with self.assertRaises(BudgetContractError):
            BudgetBinding.from_dict(
                {
                    "budget_id": "../budget-escape",
                    "logical_job_id": "job-budget",
                    "policy_digest": "0" * 64,
                }
            )

    def test_24_worker_reloads_budget_binding_before_admission(self) -> None:
        job = self.create(max_execution_units=0)
        self.jobs.enqueue(job["job_id"])
        claimed = self.jobs.claim(claimed_by="worker-stale-budget")
        assert claimed is not None
        stale = deepcopy(claimed)
        stale.pop("execution_budget")
        executor = AdvancingExecutor(self.monotonic)
        worker = Worker(
            self.jobs,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor,
            self.executions,
            clock=self.clock,
            monotonic_clock=self.monotonic,
            id_factory=IDs("execution-stale-budget"),
            worker_id="worker-stale-budget",
        )
        outcome = worker._run_job(stale)
        self.assertEqual(outcome.error["code"], "execution_budget_exhausted")
        self.assertEqual(executor.calls, 0)

    def test_25_coherent_zero_usage_reset_fails_closed(self) -> None:
        job = self.create(max_elapsed_ms=1_000, max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-reset", job_id=job["job_id"]
        )
        self.monotonic.advance_ms(125)
        runtime.finalize_execution(job["execution_budget"], execution_id="execution-reset")
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        state = json.loads(path.read_text(encoding="utf-8"))
        state["consumed_elapsed_ms"] = 0
        state["consumed_execution_units"] = 0
        state["reservations"] = []
        path.write_text(json.dumps(state), encoding="utf-8")
        decision = runtime.state(job["execution_budget"])
        admission = runtime.reserve_execution(
            job["execution_budget"],
            execution_id="execution-after-reset",
            job_id=job["job_id"],
        )
        self.assertEqual(decision.status, "ERROR")
        self.assertFalse(decision.state["may_begin"])
        self.assertEqual(admission.status, "ERROR")

    def test_26_partial_elapsed_reset_and_finalized_rewrite_fail_closed(self) -> None:
        for rewrite_active in (False, True):
            with self.subTest(rewrite_active=rewrite_active):
                job = self.create(max_elapsed_ms=1_000, max_execution_units=2)
                runtime = self.budget_runtime()
                execution_id = f"execution-elapsed-{int(rewrite_active)}"
                runtime.reserve_execution(
                    job["execution_budget"],
                    execution_id=execution_id,
                    job_id=job["job_id"],
                )
                self.monotonic.advance_ms(125)
                runtime.finalize_execution(
                    job["execution_budget"], execution_id=execution_id
                )
                binding = BudgetBinding.from_dict(job["execution_budget"])
                path = self.jobs.budget_store._state_path(binding.budget_id)
                state = json.loads(path.read_text(encoding="utf-8"))
                state["consumed_elapsed_ms"] = 0
                state["reservations"][0]["elapsed_ms"] = 0
                if rewrite_active:
                    state["reservations"][0]["state"] = "active"
                    state["reservations"][0].pop("finalized_at")
                path.write_text(json.dumps(state), encoding="utf-8")
                self.assertEqual(runtime.state(job["execution_budget"]).status, "ERROR")

    def test_27_removed_reservation_and_partial_unit_reset_fail_closed(self) -> None:
        job = self.create(max_execution_units=3)
        runtime = self.budget_runtime()
        for suffix in ("a", "b"):
            execution_id = f"execution-remove-{suffix}"
            runtime.reserve_execution(
                job["execution_budget"], execution_id=execution_id, job_id=job["job_id"]
            )
            runtime.finalize_execution(job["execution_budget"], execution_id=execution_id)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        state = json.loads(path.read_text(encoding="utf-8"))
        state["reservations"].pop()
        state["consumed_execution_units"] = 1
        state["consumed_elapsed_ms"] = sum(
            item["elapsed_ms"] for item in state["reservations"]
        )
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(runtime.state(job["execution_budget"]).status, "ERROR")

    def test_28_old_valid_snapshot_and_sequence_rollback_fail_closed(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        initial = path.read_text(encoding="utf-8")
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-old", job_id=job["job_id"]
        )
        runtime.finalize_execution(job["execution_budget"], execution_id="execution-old")
        path.write_text(initial, encoding="utf-8")
        self.assertEqual(runtime.state(job["execution_budget"]).status, "ERROR")

    def test_29_high_water_tamper_and_forward_inconsistency_fail_closed(self) -> None:
        job = self.create(max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-anchor", job_id=job["job_id"]
        )
        binding = BudgetBinding.from_dict(job["execution_budget"])
        head_path = self.jobs.budget_store._usage_head_path(binding.budget_id)
        head = json.loads(head_path.read_text(encoding="utf-8"))
        head["consumed_execution_units"] = 0
        head["anchor_digest"] = usage_anchor_digest(head)
        head_path.write_text(json.dumps(head), encoding="utf-8")
        self.assertEqual(runtime.state(job["execution_budget"]).status, "ERROR")

        other = self.create(max_execution_units=2)
        other_binding = BudgetBinding.from_dict(other["execution_budget"])
        state_path = self.jobs.budget_store._state_path(other_binding.budget_id)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["state_sequence"] += 2
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(runtime.state(other["execution_budget"]).status, "ERROR")

        forward = self.create(max_elapsed_ms=1_000, max_execution_units=2)
        runtime.reserve_execution(
            forward["execution_budget"],
            execution_id="execution-forward",
            job_id=forward["job_id"],
        )
        forward_binding = BudgetBinding.from_dict(forward["execution_budget"])
        forward_path = self.jobs.budget_store._state_path(forward_binding.budget_id)
        forward_state = json.loads(forward_path.read_text(encoding="utf-8"))
        forward_state["consumed_elapsed_ms"] = 1
        forward_state["reservations"][0]["elapsed_ms"] = 1
        forward_path.write_text(json.dumps(forward_state), encoding="utf-8")
        self.assertEqual(runtime.state(forward["execution_budget"]).status, "ERROR")

    def test_30_restart_retains_anchor_and_duplicate_identity_charge(self) -> None:
        job = self.create(max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"],
            execution_id="execution-anchor-restart",
            job_id=job["job_id"],
        )
        runtime.finalize_execution(
            job["execution_budget"], execution_id="execution-anchor-restart"
        )
        restarted = ExecutionBudgetRuntime(
            self.jobs.budget_store,
            wall_clock=self.clock,
            monotonic_clock=MutableMonotonic(),
        )
        duplicate = restarted.reserve_execution(
            job["execution_budget"],
            execution_id="execution-anchor-restart",
            job_id=job["job_id"],
        )
        self.assertEqual(duplicate.status, "ERROR")
        self.assertEqual(
            duplicate.state["dimensions"]["execution_units"]["consumed"], 1
        )

    def test_31_orphan_usage_event_after_head_write_failure_fails_closed(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        head_path = store._usage_head_path(binding.budget_id)
        original_write = store._write

        def fail_head(path: Path, value: dict[str, object]) -> None:
            if path == head_path:
                raise ExecutionBudgetStoreError("synthetic head write failure")
            original_write(path, value)

        with patch.object(store, "_write", side_effect=fail_head):
            decision = self.budget_runtime().reserve_execution(
                job["execution_budget"],
                execution_id="execution-orphan-event",
                job_id=job["job_id"],
            )
        self.assertEqual(decision.status, "ERROR")
        self.assertEqual(self.budget_runtime().state(job["execution_budget"]).status, "ERROR")

    def test_32_head_advance_without_state_write_fails_closed(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        state_path = store._state_path(binding.budget_id)
        original_write = store._write

        def fail_state(path: Path, value: dict[str, object]) -> None:
            if path == state_path:
                raise ExecutionBudgetStoreError("synthetic state write failure")
            original_write(path, value)

        with patch.object(store, "_write", side_effect=fail_state):
            decision = self.budget_runtime().reserve_execution(
                job["execution_budget"],
                execution_id="execution-head-only",
                job_id=job["job_id"],
            )
        self.assertEqual(decision.status, "ERROR")
        self.assertEqual(self.budget_runtime().state(job["execution_budget"]).status, "ERROR")

    def test_33_lock_path_directory_returns_canonical_error_without_execution(self) -> None:
        job = self.create(max_execution_units=1)
        self.jobs.enqueue(job["job_id"])
        lock_path = self.jobs.budget_store.root / ".budget.lock"
        lock_path.unlink()
        lock_path.mkdir()
        executor = AdvancingExecutor(self.monotonic)
        outcome = self.worker(executor).run_once()
        self.assertEqual(outcome.error["code"], "execution_budget_error")
        self.assertEqual(executor.calls, 0)

    def test_34_lock_open_oserror_is_sanitized_and_does_not_mutate_state(self) -> None:
        job = self.create(max_execution_units=1)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        state_path = self.jobs.budget_store._state_path(binding.budget_id)
        before = state_path.read_bytes()
        original_open = Path.open

        def fail_lock(path: Path, *args: object, **kwargs: object):
            if path.name == ".budget.lock":
                raise PermissionError("private-path-details")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", new=fail_lock):
            decision = self.budget_runtime().reserve_execution(
                job["execution_budget"],
                execution_id="execution-lock-error",
                job_id=job["job_id"],
            )
        self.assertEqual(decision.status, "ERROR")
        self.assertNotIn("private-path-details", decision.reason)
        self.assertEqual(state_path.read_bytes(), before)

    def test_35_state_sequence_advances_only_with_canonical_evidence(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        state_path = store._state_path(binding.budget_id)
        runtime = self.budget_runtime()
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8"))["state_sequence"], 0
        )
        runtime.state(job["execution_budget"])
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8"))["state_sequence"], 0
        )
        runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-sequence", job_id=job["job_id"]
        )
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8"))["state_sequence"], 1
        )
        runtime.finalize_execution(
            job["execution_budget"], execution_id="execution-sequence"
        )
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8"))["state_sequence"], 2
        )
        runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-sequence", job_id=job["job_id"]
        )
        self.assertEqual(
            json.loads(state_path.read_text(encoding="utf-8"))["state_sequence"], 2
        )
        history = store._usage_events_dir(binding.budget_id)
        self.assertEqual(len(list(history.glob("*.json"))), 3)

    def test_36_usage_anchor_schema_model_and_detached_reload_agree(self) -> None:
        job = self.create(max_execution_units=1)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        head_path = store._usage_head_path(binding.budget_id)
        raw = json.loads(head_path.read_text(encoding="utf-8"))
        store.usage_anchor_validator.validate(raw)
        anchor = BudgetUsageAnchor.from_dict(raw)
        self.assertEqual(anchor.to_dict(), raw)
        claim_raw = json.loads(
            store._usage_claim_path(binding.budget_id, 0).read_text(encoding="utf-8")
        )
        store.usage_claim_validator.validate(claim_raw)
        claim = BudgetUsageClaim.from_dict(claim_raw)
        self.assertEqual(claim.to_dict(), claim_raw)
        self.assertEqual(claim.event_digest, anchor.digest)
        raw["consumed_execution_units"] = 1
        self.assertEqual(
            json.loads(head_path.read_text(encoding="utf-8"))["consumed_execution_units"],
            0,
        )

    def test_37_f2_genesis_corruption_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        self.ledger_event_path(binding, 0).write_text("{", encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_38_f2_middle_historical_corruption_is_rejected(self) -> None:
        job = self.create(max_execution_units=3)
        self.consume(job, 2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        self.ledger_event_path(binding, 2).write_text("[]", encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_39_f2_nonadjacent_historical_corruption_is_rejected(self) -> None:
        job = self.create(max_execution_units=3)
        self.consume(job, 2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        self.ledger_event_path(binding, 1).write_text("null", encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_40_f2_missing_historical_event_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        self.ledger_event_path(binding, 1).unlink()
        self.assert_budget_fails_closed(job)

    def test_41_f2_duplicate_sequence_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        original = self.ledger_event_path(binding, 1)
        duplicate = store._usage_events_dir(binding.budget_id) / (
            f"{1:020d}-{'0' * 64}.json"
        )
        duplicate.write_bytes(original.read_bytes())
        self.assert_budget_fails_closed(job)

    def test_42_f2_alternate_branch_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        original = self.ledger_event_path(binding, 2)
        branch = json.loads(original.read_text(encoding="utf-8"))
        branch["state_digest"] = "f" * 64
        branch["anchor_digest"] = usage_anchor_digest(branch)
        branch_path = store._usage_event_path(
            binding.budget_id, 2, branch["anchor_digest"]
        )
        branch_path.write_text(json.dumps(branch), encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_43_f2_wrong_previous_digest_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.ledger_event_path(binding, 2)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["previous_anchor_digest"] = "0" * 64
        value["anchor_digest"] = usage_anchor_digest(value)
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_44_f2_sequence_gap_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        event = self.ledger_event_path(binding, 1)
        event.rename(event.with_name(event.name.replace(f"{1:020d}-", f"{3:020d}-")))
        claim = store._usage_claim_path(binding.budget_id, 1)
        claim.rename(store._usage_claim_path(binding.budget_id, 3))
        self.assert_budget_fails_closed(job)

    def test_44a_f2_current_predecessor_corruption_is_rejected(self) -> None:
        job = self.create(max_execution_units=3)
        self.consume(job, 2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        self.ledger_event_path(binding, 3).write_text("{", encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_44b_f2_internal_event_sequence_rewrite_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.ledger_event_path(binding, 2)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["state_sequence"] = 3
        value["anchor_digest"] = usage_anchor_digest(value)
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_45_f2_coherent_zero_unit_current_layer_rewrite_is_rejected(self) -> None:
        job = self.create(max_execution_units=1)
        self.consume(job)
        self.rewrite_current_layer(job, reset_units=True, reset_elapsed=False)
        self.assert_budget_fails_closed(job)
        denied = self.budget_runtime().reserve_execution(
            job["execution_budget"],
            execution_id="execution-after-unit-reset",
            job_id=job["job_id"],
        )
        self.assertEqual(denied.status, "ERROR")

    def test_46_f2_coherent_zero_elapsed_current_layer_rewrite_is_rejected(self) -> None:
        job = self.create(max_elapsed_ms=1_000, max_execution_units=2)
        self.consume(job)
        self.rewrite_current_layer(job, reset_units=False, reset_elapsed=True)
        self.assert_budget_fails_closed(job)

    def test_47_f2_combined_current_layer_rewrite_is_rejected(self) -> None:
        job = self.create(max_elapsed_ms=1_000, max_execution_units=1)
        self.consume(job)
        self.rewrite_current_layer(job, reset_units=True, reset_elapsed=True)
        self.assert_budget_fails_closed(job)

    def test_48_f2_old_state_and_head_snapshot_replay_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        state_path = store._state_path(binding.budget_id)
        head_path = store._usage_head_path(binding.budget_id)
        old_state = state_path.read_bytes()
        old_head = head_path.read_bytes()
        self.consume(job)
        state_path.write_bytes(old_state)
        head_path.write_bytes(old_head)
        self.assert_budget_fails_closed(job)

    def test_49_f2_recomputed_current_event_digest_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.ledger_event_path(binding, 2)
        value = json.loads(path.read_text(encoding="utf-8"))
        value["consumed_execution_units"] = 0
        value["reservation_count"] = 0
        value["anchor_digest"] = usage_anchor_digest(value)
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_50_f2_fresh_genesis_rebind_after_use_is_rejected(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        initial_state = store._state_path(binding.budget_id).read_bytes()
        genesis = self.ledger_event_path(binding, 0).read_bytes()
        self.consume(job)
        for path in store._usage_events_dir(binding.budget_id).iterdir():
            if not path.name.startswith(f"{0:020d}-"):
                path.unlink()
        for path in store._usage_claims_dir(binding.budget_id).iterdir():
            if path.name != f"{0:020d}.json":
                path.unlink()
        store._state_path(binding.budget_id).write_bytes(initial_state)
        store._usage_head_path(binding.budget_id).write_bytes(genesis)
        self.assert_budget_fails_closed(job)

    def test_51_f2_event_only_crash_fails_closed_without_refund(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        claim_path = store._usage_claim_path(binding.budget_id, 1)
        original_write_once = store._write_once

        def fail_claim(path: Path, value: dict[str, object]) -> None:
            if path == claim_path:
                raise ExecutionBudgetStoreError("synthetic claim write failure")
            original_write_once(path, value)

        with patch.object(store, "_write_once", side_effect=fail_claim):
            result = self.budget_runtime().reserve_execution(
                job["execution_budget"],
                execution_id="execution-event-only",
                job_id=job["job_id"],
            )
        self.assertEqual(result.status, "ERROR")
        self.assert_budget_fails_closed(job)

    def test_52_f2_event_and_head_with_old_state_fail_closed(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        state_path = store._state_path(binding.budget_id)
        original_write = store._write

        def fail_state(path: Path, value: dict[str, object]) -> None:
            if path == state_path:
                raise ExecutionBudgetStoreError("synthetic state write failure")
            original_write(path, value)

        with patch.object(store, "_write", side_effect=fail_state):
            result = self.budget_runtime().reserve_execution(
                job["execution_budget"],
                execution_id="execution-head-state-crash",
                job_id=job["job_id"],
            )
        self.assertEqual(result.status, "ERROR")
        self.assert_budget_fails_closed(job)

    def test_53_f2_state_without_canonical_event_fails_closed(self) -> None:
        job = self.create(max_execution_units=2)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        path = self.jobs.budget_store._state_path(binding.budget_id)
        state = json.loads(path.read_text(encoding="utf-8"))
        state["state_sequence"] = 1
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assert_budget_fails_closed(job)

    def test_54_f2_restart_reconciliation_is_idempotent(self) -> None:
        job = self.create(max_elapsed_ms=10_000, max_execution_units=2)
        runtime = self.budget_runtime()
        runtime.reserve_execution(
            job["execution_budget"],
            execution_id="execution-reconcile-idempotent",
            job_id=job["job_id"],
        )
        self.clock.advance_ms(125)
        first = runtime.recover(job["execution_budget"])
        second = runtime.recover(job["execution_budget"])
        self.assertEqual(first.state, second.state)

    def test_55_f2_duplicate_execution_identity_adds_no_event_or_charge(self) -> None:
        job = self.create(max_execution_units=2)
        runtime = self.budget_runtime()
        first = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-same", job_id=job["job_id"]
        )
        binding = BudgetBinding.from_dict(job["execution_budget"])
        store = self.jobs.budget_store
        before = len(list(store._usage_claims_dir(binding.budget_id).iterdir()))
        duplicate = runtime.reserve_execution(
            job["execution_budget"], execution_id="execution-same", job_id=job["job_id"]
        )
        after = len(list(store._usage_claims_dir(binding.budget_id).iterdir()))
        self.assertEqual(first.status, "ALLOW")
        self.assertEqual(duplicate.status, "ERROR")
        self.assertEqual((before, after), (2, 2))

    def test_56_f2_concurrent_final_unit_remains_single_spend(self) -> None:
        job = self.create(max_execution_units=1)

        def reserve(index: int) -> str:
            return self.budget_runtime().reserve_execution(
                job["execution_budget"],
                execution_id=f"execution-final-{index}",
                job_id=job["job_id"],
            ).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(reserve, (1, 2)))
        self.assertEqual(sorted(statuses), ["ALLOW", "DENY_EXHAUSTED"])

    def test_57_f2_partial_claim_file_fails_closed(self) -> None:
        job = self.create(max_execution_units=2)
        self.consume(job)
        binding = BudgetBinding.from_dict(job["execution_budget"])
        self.jobs.budget_store._usage_claim_path(
            binding.budget_id, 1
        ).write_text("{", encoding="utf-8")
        self.assert_budget_fails_closed(job)


if __name__ == "__main__":
    unittest.main()
