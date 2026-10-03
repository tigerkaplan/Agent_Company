from __future__ import annotations

from runtime.tests.contract_fixtures import declare_fixture_contract, persist_fixture_review, persist_execution_fixture

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.actions.authorization import authorization_fingerprint
from runtime.approvals.models import approval_boundary_id
from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.continuation.models import ContinuationPolicy, continuation_plan_digest
from runtime.continuation.runtime import ContinuationRuntime
from runtime.continuation.store import AuthorizedPlanStoreError, FileAuthorizedPlanStore
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionContractError, ExecutionRequest, ExecutionResult
from runtime.executors.local import LocalExecutor
from runtime.review.models import ReviewResult, ReviewRun
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore
from runtime.workers.worker import Worker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 26, tzinfo=timezone.utc)

    def __call__(self) -> str:
        result = self.value.isoformat().replace("+00:00", "Z")
        self.value += timedelta(seconds=1)
        return result


class IDs:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"{self.prefix}-{self.value:03d}"


class ResultExecutor:
    supported_execution_modes = frozenset({"READ_ONLY"})

    def __init__(
        self,
        status: str = "succeeded",
        *,
        summary: str = "One planned step completed",
        next_actions: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.status = status
        self.summary = summary
        self.next_actions = next_actions

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        values: dict[str, object] = {
            "execution_id": request.execution_id,
            "job_id": request.job_id,
            "status": self.status,
            "summary": self.summary,
            "error": None,
            "provider": request.provider,
            "started_at": "2026-09-26T00:00:00Z",
            "completed_at": "2026-09-26T00:00:01Z",
            "next_actions": self.next_actions,
        }
        if self.status == "failed":
            values.update(
                summary=None,
                error={"code": "provider_failed", "message": "failed", "retryable": True},
            )
        elif self.status == "blocked":
            values["blockers"] = (
                {
                    "code": "missing_input",
                    "message": "Canonical prerequisite is missing",
                    "retryable": False,
                    "requires_human": False,
                },
            )
        elif self.status == "needs_review":
            values["evidence"] = (
                {"kind": "observation", "status": "observed", "summary": "Review it"},
            )
        elif self.status == "needs_human":
            values["blockers"] = (
                {
                    "code": "human_gate",
                    "message": "Explicit human action is required",
                    "retryable": False,
                    "requires_human": True,
                },
            )
        return ExecutionResult(**values)  # type: ignore[arg-type]


class CountingExecutor(ResultExecutor):
    def __init__(self, status: str = "succeeded") -> None:
        super().__init__(status)
        self.calls = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        return super().execute(request)


class Reviewer:
    def __init__(self, decision: str = "PASS") -> None:
        self.decision = decision
        from runtime.review.store import FileReviewStore
        self.review_temporary = tempfile.TemporaryDirectory()
        self.store = FileReviewStore(Path(self.review_temporary.name))
        self.store.temporary_owner = self.review_temporary

    def run(
        self,
        job: dict[str, object],
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> ReviewRun:
        review_id = f"review-{result.execution_id}"
        return persist_fixture_review(self.store, job, request, result, ReviewRun(
            ReviewResult(
                review_id=review_id,
                job_id=result.job_id,
                execution_id=result.execution_id,
                reviewer="deterministic-reviewer",
                review_provider=None,
                same_provider_review=False,
                model_review_performed=False,
                decision=self.decision,
                reason="Deterministic review decision",
                evidence_refs=(
                    {
                        "ref_type": "artifact",
                        "ref": f"runtime-execution:{result.execution_id}",
                    },
                ),
                deterministic_checks=(),
                created_at="2026-09-26T00:00:02Z",
            ),
            {
                "ref_type": "review",
                "ref": f"runtime-review:{review_id}",
                "description": "Deterministic review result",
            },
        ))


class ContinuationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = Clock()
        self.jobs = JobRuntime(
            self.root / "state" / "jobs",
            clock=self.clock,
            id_factory=IDs("job-core02"),
        )
        self.executions = FileExecutionStore(self.root / "state" / "executions")
        self.approvals = ApprovalRuntime(
            self.jobs,
            FileApprovalStore(self.root / "state" / "approvals"),
            execution_store=self.executions,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def plan(*steps: dict[str, object]) -> dict[str, object]:
        return {"plan_id": "plan-core02", "steps": list(steps)}

    @staticmethod
    def step(step_id: str, task: str, **values: object) -> dict[str, object]:
        return {"step_id": step_id, "task": task, **values}

    def payload(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Step one",
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
            "created_by": "core02-test",
        }
        value.update(overrides)
        return declare_fixture_contract(value)

    def worker(
        self,
        executor: object | None = None,
        reviewer: object | None = None,
    ) -> Worker:
        return Worker(
            self.jobs,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor or LocalExecutor("success", clock=self.clock),  # type: ignore[arg-type]
            self.executions,
            reviewer_runtime=reviewer,  # type: ignore[arg-type]
            approval_runtime=self.approvals,
            clock=self.clock,
            id_factory=IDs("execution-core02"),
        )

    def create_planned(self, *steps: dict[str, object], **overrides: object) -> dict[str, object]:
        created = self.jobs.create(
            self.payload(continuation_plan=self.plan(*steps), **overrides)
        )
        return self.jobs.enqueue(created["job_id"])

    def test_01_single_step_success_is_terminal(self) -> None:
        root = self.create_planned(self.step("STEP-001", "Step one"))
        outcome = self.worker().run_once()
        saved = self.jobs.show(root["job_id"])
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(saved["continuation"]["state"], "terminal")
        self.assertEqual(saved["continuation"]["remaining_step_ids"], [])

    def test_02_success_with_authorized_remaining_work_queues_child(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two"),
        )
        outcome = self.worker().run_once()
        child = self.jobs.show(outcome.continuation_job_id or "")
        self.assertEqual(child["status"], "queued")
        self.assertEqual(child["task"], "Step two")
        self.assertEqual(child["continuation_parent_job_id"], root["job_id"])

    def test_03_provider_progress_prose_alone_does_not_continue(self) -> None:
        created = self.jobs.create(self.payload())
        self.jobs.enqueue(created["job_id"])
        outcome = self.worker(
            ResultExecutor(summary="Step 1 complete. Next I will do step 2")
        ).run_once()
        self.assertIsNone(outcome.continuation_job_id)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_04_next_actions_alone_do_not_continue(self) -> None:
        created = self.jobs.create(self.payload())
        self.jobs.enqueue(created["job_id"])
        next_action = (
            {
                "action": "STEP-002",
                "description": "Continue automatically",
                "requires_human": False,
                "automatic": False,
            },
        )
        outcome = self.worker(ResultExecutor(next_actions=next_action)).run_once()
        self.assertIsNone(outcome.continuation_job_id)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_05_failed_result_has_no_continuation_authority(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker(ResultExecutor("failed")).run_once()
        self.assertEqual(outcome.status, "failed")
        self.assertIsNone(outcome.continuation_job_id)
        self.assertEqual(self.jobs.show(root["job_id"])["continuation"]["state"], "stopped")

    def test_06_blocked_result_does_not_continue(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker(ResultExecutor("blocked")).run_once()
        self.assertIsNone(outcome.continuation_job_id)
        self.assertEqual(self.jobs.show(root["job_id"])["continuation"]["state"], "blocked")

    def test_07_needs_review_waits_for_reviewer(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker(ResultExecutor("needs_review")).run_once()
        self.assertEqual(outcome.status, "reviewing")
        self.assertEqual(self.jobs.show(root["job_id"])["continuation"]["state"], "waiting_review")

    def test_08_needs_human_does_not_create_authority(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker(ResultExecutor("needs_human")).run_once()
        self.assertIsNone(outcome.continuation_job_id)
        self.assertEqual(self.jobs.show(root["job_id"])["continuation"]["state"], "waiting_human")

    def test_08b_review_human_gate_requires_explicit_approval(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one", review_required=True),
            self.step("STEP-002", "Step two"),
            review_required=True,
        )
        outcome = self.worker(ResultExecutor(), Reviewer("NEEDS_HUMAN")).run_once()
        self.assertEqual(outcome.status, "waiting_approval")
        self.assertIsNotNone(outcome.approval)
        self.assertEqual(len(self.jobs.list()), 1)
        approval_id = str((outcome.approval or {})["approval_id"])
        resolved = self.approvals.resolve(
            approval_id, decision="APPROVED", decided_by="human-owner"
        )
        self.assertEqual(resolved["job"]["continuation"]["state"], "ready")
        recovered = ContinuationRuntime(self.jobs, self.approvals).recover()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "waiting_approval")

    def test_09_reviewer_pass_allows_next_authorized_step(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one", review_required=True),
            self.step("STEP-002", "Step two"),
            review_required=True,
        )
        outcome = self.worker(ResultExecutor(), Reviewer("PASS")).run_once()
        self.assertIsNotNone(outcome.continuation_job_id)
        self.assertEqual(self.jobs.show(outcome.continuation_job_id or "")["status"], "queued")

    def test_10_missing_human_approval_keeps_next_step_unclaimable(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two", requires_human_approval=True),
        )
        outcome = self.worker().run_once()
        child = self.jobs.show(outcome.continuation_job_id or "")
        self.assertEqual(child["status"], "waiting_approval")
        self.assertNotIn(child["job_id"], [job["job_id"] for job in self.jobs.eligible()])

    def test_10b_continuation_never_reuses_parent_approval(self) -> None:
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                continuation_plan=self.plan(
                    self.step("STEP-001", "Step one"),
                    self.step("STEP-002", "Step two"),
                ),
            )
        )
        request = self.approvals.request_execution(
            created["job_id"], reason="Approve only the first execution step"
        )
        self.approvals.resolve(
            request.request.approval_id,
            decision="APPROVED",
            decided_by="human-owner",
        )
        outcome = self.worker().run_once()
        child = self.jobs.show(outcome.continuation_job_id or "")
        self.assertEqual(child["status"], "waiting_approval")
        self.assertNotEqual(
            child["output_refs"][-1]["ref"], request.artifact_ref["ref"]
        )

    def test_11_ready_checkpoint_survives_crash_before_child_reservation(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        running = self.jobs.claim()
        assert running is not None
        decision = ContinuationPolicy.decide_execution(
            running,
            result_status="succeeded",
            execution_ref="runtime-execution:crash-window",
        )
        self.jobs.record_execution_success(
            root["job_id"], [persist_execution_fixture(self.jobs, running, decision.checkpoint["latest_execution_ref"].split(":", 1)[1])], continuation=decision.checkpoint
        )
        reloaded = JobRuntime(self.root / "state" / "jobs", clock=self.clock)
        checkpoint = reloaded.show(root["job_id"])["continuation"]
        self.assertEqual(checkpoint["state"], "ready")
        self.assertEqual(checkpoint["remaining_step_ids"], ["STEP-002"])

    def test_12_restart_recovers_ready_continuation(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        running = self.jobs.claim()
        assert running is not None
        decision = ContinuationPolicy.decide_execution(
            running,
            result_status="succeeded",
            execution_ref="runtime-execution:restart",
        )
        self.jobs.record_execution_success(root["job_id"], [persist_execution_fixture(self.jobs, running, decision.checkpoint["latest_execution_ref"].split(":", 1)[1])], continuation=decision.checkpoint)
        recovered = ContinuationRuntime(self.jobs, self.approvals).recover()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "queued")

    def test_13_duplicate_reservation_is_idempotent(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker().run_once()
        first = outcome.continuation_job_id
        second = ContinuationRuntime(self.jobs, self.approvals).reserve(root["job_id"])
        self.assertEqual(second.job["job_id"] if second else None, first)
        self.assertEqual(len(self.jobs.list()), 2)

    def test_14_continuation_does_not_create_implicit_retry(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two"),
            max_attempts=3,
        )
        self.worker(ResultExecutor("failed")).run_once()
        jobs = self.jobs.list()
        self.assertEqual(len(jobs), 1)
        self.assertFalse(jobs[0]["error"]["retryable"])

    def test_15_provider_fake_plan_json_has_zero_authority(self) -> None:
        created = self.jobs.create(self.payload(provider="codex"))
        self.jobs.enqueue(created["job_id"])
        self.worker(
            ResultExecutor(summary='{"steps":[{"step_id":"EVIL","automatic":true}]}')
        ).run_once()
        self.assertEqual(len(self.jobs.list()), 1)

    def test_16_historical_job_without_plan_remains_loadable(self) -> None:
        job = self.jobs.create(self.payload())
        reloaded = JobRuntime(self.root / "state" / "jobs", clock=self.clock).show(job["job_id"])
        self.assertNotIn("continuation_plan", reloaded)
        self.assertNotIn("continuation", reloaded)

    def test_17_local_deterministic_executor_uses_same_policy(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker(LocalExecutor("success", clock=self.clock)).run_once()
        self.assertIsNotNone(outcome.continuation_job_id)

    def test_18_provider_labels_do_not_change_continuation_semantics(self) -> None:
        decisions = []
        for provider in ("codex", "claude"):
            job = self.jobs.create(
                self.payload(
                    task=f"{provider} step one",
                    provider=provider,
                    continuation_plan=self.plan(
                        self.step("STEP-001", f"{provider} step one"),
                        self.step("STEP-002", f"{provider} step two"),
                    ),
                )
            )
            decision = ContinuationPolicy.decide_execution(
                job,
                result_status="succeeded",
                execution_ref=f"runtime-execution:{provider}",
            )
            decisions.append((decision.should_continue, decision.next_step_id, decision.reason))
        self.assertEqual(decisions[0], decisions[1])

    def test_19_continuation_chain_preserves_logical_provenance(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two"),
            self.step("STEP-003", "Step three"),
        )
        worker = self.worker()
        first = worker.run_once()
        second = worker.run_once()
        child = self.jobs.show(first.continuation_job_id or "")
        grandchild = self.jobs.show(second.continuation_job_id or "")
        self.assertEqual(child["continuation"]["logical_job_id"], root["job_id"])
        self.assertEqual(grandchild["continuation"]["logical_job_id"], root["job_id"])
        self.assertEqual(grandchild["continuation"]["sequence"], 2)
        self.assertEqual(grandchild["continuation_parent_job_id"], child["job_id"])

    def test_20_terminal_completion_requires_empty_remaining_work(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        worker = self.worker()
        first = worker.run_once()
        parent = self.jobs.show(first.job_id or "")
        self.assertEqual(parent["continuation"]["state"], "ready")
        self.assertEqual(parent["continuation"]["remaining_step_ids"], ["STEP-002"])
        second = worker.run_once()
        final = self.jobs.show(second.job_id or "")
        self.assertEqual(final["continuation"]["state"], "terminal")
        self.assertEqual(final["continuation"]["remaining_step_ids"], [])

    def _pending_approved_plan(self) -> tuple[dict[str, object], dict[str, object]]:
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                continuation_plan=self.plan(
                    self.step("STEP-001", "Step one"),
                    self.step("STEP-002", "Step two"),
                ),
            )
        )
        run = self.approvals.request_execution(
            str(created["job_id"]), reason="Exact planned work"
        )
        return created, run.request.to_dict()

    def test_21_authorization_fingerprint_binds_exact_continuation_work(self) -> None:
        created = self.jobs.create(
            self.payload(
                continuation_plan=self.plan(
                    self.step("STEP-001", "Step one"),
                    self.step("STEP-002", "Step two"),
                )
            )
        )
        baseline = authorization_fingerprint(created)
        mutations = []
        for field, value in (
            ("task", "Deploy production"),
            ("task_class", "review"),
            ("agent", "reviewer"),
            ("skill", "different-skill"),
            ("workflow", "different-workflow"),
            ("review_required", True),
            ("input_refs", [{"ref_type": "other", "ref": "changed"}]),
        ):
            changed = deepcopy(created)
            changed[field] = value
            mutations.append(changed)
        changed = deepcopy(created)
        changed["continuation_plan"]["steps"][1]["task"] = "Changed step"
        mutations.append(changed)
        changed = deepcopy(created)
        changed["continuation_plan"]["steps"].reverse()
        mutations.append(changed)
        for field, value in (("current_step_id", "STEP-002"), ("sequence", 1)):
            changed = deepcopy(created)
            changed["continuation"][field] = value
            mutations.append(changed)
        self.assertTrue(
            all(authorization_fingerprint(value) != baseline for value in mutations)
        )

    def test_22_pending_approval_rejects_task_plan_and_input_mutation(self) -> None:
        mutators = (
            lambda job: job.update(task="Deploy production"),
            lambda job: job["input_refs"].append(
                {"ref_type": "other", "ref": "changed-input"}
            ),
            lambda job: job["continuation_plan"]["steps"][1].update(
                task="Changed step"
            ),
            lambda job: job["continuation_plan"]["steps"].reverse(),
        )
        for mutate in mutators:
            with self.subTest(mutate=mutate):
                created, approval = self._pending_approved_plan()
                stored = self.jobs.store.load(str(created["job_id"]))
                mutate(stored)
                if stored["task"] == stored["continuation_plan"]["steps"][0]["task"]:
                    stored["continuation"]["plan_digest"] = continuation_plan_digest(
                        stored["continuation_plan"]
                    )
                self.jobs.store.save(stored)
                with self.assertRaises((ApprovalRuntimeError, RuntimeError)):
                    self.approvals.resolve(
                        str(approval["approval_id"]),
                        decision="APPROVED",
                        decided_by="owner",
                    )

    def test_23_stale_approval_fails_at_enqueue_claim_and_execution(self) -> None:
        for boundary in ("enqueue", "claim", "execution"):
            with self.subTest(boundary=boundary):
                created = self.jobs.create(
                    self.payload(
                        task="Exact task",
                        risk_level="approval_required",
                        approval_status="required",
                    )
                )
                run = self.approvals.request_execution(
                    str(created["job_id"]), reason="Exact task"
                )
                resolved = self.approvals.resolve(
                    run.request.approval_id,
                    decision="APPROVED",
                    decided_by="owner",
                )["job"]
                if boundary == "execution":
                    claimed = self.jobs.claim(claimed_by="worker-stale", lease_seconds=30)
                    self.assertIsNotNone(claimed)
                stored = self.jobs.store.load(str(created["job_id"]))
                stored["task"] = "Changed after approval"
                if boundary == "enqueue":
                    stored["status"] = "created"
                self.jobs.store.save(stored)
                if boundary == "enqueue":
                    action = lambda: self.jobs.enqueue(str(created["job_id"]))
                elif boundary == "claim":
                    action = lambda: self.jobs.claim(
                        claimed_by="worker-stale", lease_seconds=30
                    )
                else:
                    action = lambda: self.worker().run_claimed(str(created["job_id"]))
                try:
                    if boundary == "execution":
                        self.assertEqual(action().error["code"], "claim_error")
                    else:
                        with self.assertRaises(JobRuntimeError):
                            action()
                finally:
                    self.jobs.store.save(resolved)

    def test_23b_review_requirement_mutation_invalidates_approval(self) -> None:
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                review_required=True,
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Review-required exact work"
        )
        self.approvals.resolve(
            approval.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
        )
        stored = self.jobs.store.load(str(created["job_id"]))
        stored["review_required"] = False
        self.jobs.store.save(stored)
        executor = CountingExecutor()
        outcome = self.worker(executor).run_once()
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(outcome.error["code"], "claim_error")
        self.assertEqual(executor.calls, 0)

    def test_24_child_identity_binds_plan_digest(self) -> None:
        first = self.jobs._continuation_job_id("logical", "a" * 64, 1, "STEP-002")
        second = self.jobs._continuation_job_id("logical", "b" * 64, 1, "STEP-002")
        self.assertNotEqual(first, second)

    def test_25_checkpoint_duplicates_order_skip_and_task_mismatch_fail(self) -> None:
        created = self.jobs.create(
            self.payload(
                continuation_plan=self.plan(
                    self.step("STEP-001", "Step one"),
                    self.step("STEP-002", "Step two"),
                    self.step("STEP-003", "Step three"),
                )
            )
        )
        invalid = []
        duplicate_completed = deepcopy(created)
        duplicate_completed["continuation"].update(
            sequence=1,
            current_step_id="STEP-002",
            completed_step_ids=["STEP-001", "STEP-001"],
            remaining_step_ids=["STEP-002", "STEP-003"],
        )
        duplicate_completed["task"] = "Step two"
        invalid.append(duplicate_completed)
        duplicate_remaining = deepcopy(created)
        duplicate_remaining["continuation"]["remaining_step_ids"] = [
            "STEP-001", "STEP-002", "STEP-002", "STEP-003"
        ]
        invalid.append(duplicate_remaining)
        reordered = deepcopy(created)
        reordered["continuation"]["remaining_step_ids"] = [
            "STEP-001", "STEP-003", "STEP-002"
        ]
        invalid.append(reordered)
        skipped = deepcopy(created)
        skipped["continuation"].update(
            sequence=2,
            current_step_id="STEP-003",
            completed_step_ids=["STEP-001"],
            remaining_step_ids=["STEP-003"],
        )
        skipped["task"] = "Step three"
        invalid.append(skipped)
        mismatch = deepcopy(created)
        mismatch["task"] = "Deploy production"
        invalid.append(mismatch)
        for job in invalid:
            with self.assertRaises(JobRuntimeError):
                self.jobs._validate(job)

    def test_26_logical_root_sequence_and_retry_ancestry_fail_closed(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker().run_once()
        child = self.jobs.store.load(outcome.continuation_job_id or "")
        unrelated = deepcopy(child)
        unrelated["continuation"]["logical_job_id"] = "unrelated-root"
        self.jobs.store.save(unrelated)
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(str(child["job_id"]))
        self.jobs.store.save(child)
        rollback = deepcopy(child)
        rollback["continuation"].update(
            sequence=0,
            current_step_id="STEP-001",
            completed_step_ids=[],
            remaining_step_ids=["STEP-001", "STEP-002"],
        )
        rollback["task"] = "Step one"
        self.jobs.store.save(rollback)
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(str(child["job_id"]))
        self.jobs.store.save(child)
        masquerade = deepcopy(child)
        masquerade["parent_job_id"] = root["job_id"]
        masquerade["continuation_parent_job_id"] = root["job_id"]
        self.jobs.store.save(masquerade)
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(str(child["job_id"]))

    def test_26b_self_retry_and_noncompleted_continuation_parent_fail_closed(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker().run_once()
        child_id = str(outcome.continuation_job_id)
        child = self.jobs.store.load(child_id)
        self_parented = deepcopy(child)
        self_parented["parent_job_id"] = child_id
        self.jobs.store.save(self_parented)
        with self.assertRaisesRegex(JobRuntimeError, "parent itself"):
            self.jobs.show(child_id)
        self.jobs.store.save(child)

        parent = self.jobs.store.load(str(root["job_id"]))
        parent["status"] = "running"
        self.jobs.store.save(parent)
        with self.assertRaisesRegex(JobRuntimeError, "lifecycle state"):
            self.jobs.show(child_id)

    def test_26c_retry_resets_checkpoint_and_requires_exact_attempt_ancestry(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), max_attempts=3
        )
        running = self.jobs.claim(claimed_by="retry-worker", lease_seconds=30)
        self.assertIsNotNone(running)
        decision = ContinuationPolicy.decide_execution(
            running,
            result_status="failed",
            execution_ref="runtime-execution:failed-attempt",
        )
        failed = self.jobs.fail(
            str(root["job_id"]),
            retryable=True,
            continuation=decision.checkpoint,
        )
        self.assertEqual(failed["continuation"]["state"], "stopped")
        retry = self.jobs.retry(str(root["job_id"]), enqueue=True)
        self.assertEqual(retry["continuation"]["state"], "active")
        self.assertNotIn("latest_execution_ref", retry["continuation"])

        malformed = self.jobs.store.load(str(retry["job_id"]))
        malformed["attempt"] = 3
        self.jobs.store.save(malformed)
        with self.assertRaisesRegex(JobRuntimeError, "advance exactly once"):
            self.jobs.show(str(retry["job_id"]))

    def test_27_persisted_result_reconciles_without_duplicate_execution(self) -> None:
        self.create_planned(self.step("STEP-001", "Step one"))
        executor = CountingExecutor()
        worker = self.worker(executor)
        original = self.jobs.record_execution_success
        calls = 0

        def fail_once(*args: object, **kwargs: object) -> dict[str, object]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise JobRuntimeError("injected job advance failure")
            return original(*args, **kwargs)  # type: ignore[arg-type]

        self.jobs.record_execution_success = fail_once  # type: ignore[method-assign]
        first = worker.run_once()
        self.assertEqual(first.status, "worker_error")
        self.assertEqual(executor.calls, 1)
        recovered = worker.recover_persisted_results()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].status, "completed")
        self.assertEqual(executor.calls, 1)

    def test_27b_requestless_success_cannot_reconcile_running_job(self) -> None:
        job = self.create_planned(self.step("STEP-001", "Step one"))
        executor = CountingExecutor()
        worker = self.worker(executor)
        claimed = self.jobs.claim(
            claimed_by=worker.worker_id,
            lease_seconds=30,
        )
        self.assertIsNotNone(claimed)
        result = ResultExecutor().execute(
            Worker._build_request(
                claimed,
                "execution-requestless",
                worker.resolver.resolve(claimed),
            )
        )
        self.executions.create(None, result)
        recovered = worker.recover_persisted_results()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].status, "worker_error")
        self.assertEqual(self.jobs.show(str(job["job_id"]))["status"], "running")
        self.assertEqual(executor.calls, 0)

    def test_27c_mismatched_persisted_request_cannot_reconcile(self) -> None:
        job = self.create_planned(self.step("STEP-001", "Step one"))
        executor = CountingExecutor()
        worker = self.worker(executor)
        original = self.jobs.record_execution_success

        def fail_update(*args: object, **kwargs: object) -> dict[str, object]:
            raise JobRuntimeError("injected job advance failure")

        self.jobs.record_execution_success = fail_update  # type: ignore[method-assign]
        first = worker.run_once()
        self.jobs.record_execution_success = original  # type: ignore[method-assign]
        path = self.executions._path(str(first.execution_id))
        record = json.loads(path.read_text(encoding="utf-8"))
        record["request"]["workflow"] = "different-workflow"
        path.write_text(json.dumps(record), encoding="utf-8")
        recovered = worker.recover_persisted_results()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].status, "worker_error")
        self.assertEqual(self.jobs.show(str(job["job_id"]))["status"], "running")
        self.assertEqual(executor.calls, 1)

    def test_27d_request_result_execution_identity_mismatch_fails_closed(self) -> None:
        job = self.create_planned(self.step("STEP-001", "Step one"))
        executor = CountingExecutor()
        worker = self.worker(executor)
        claimed = self.jobs.claim(
            claimed_by=worker.worker_id,
            lease_seconds=30,
        )
        self.assertIsNotNone(claimed)
        request = worker._build_request(
            claimed,
            "execution-bound",
            worker.resolver.resolve(claimed),
        )
        result = executor.execute(request)
        path = self.executions.create(request, result)
        record = json.loads(path.read_text(encoding="utf-8"))
        record["request"]["execution_id"] = "execution-unrelated"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(ExecutionStoreError, "canonical result"):
            self.executions.load("execution-bound")
        recovered = worker.recover_persisted_results()
        self.assertEqual(recovered[0].status, "worker_error")
        self.assertEqual(self.jobs.show(str(job["job_id"]))["status"], "running")

    def test_28_direct_needs_human_is_resolvable_and_exact(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        executor = ResultExecutor("needs_human")
        worker = self.worker(executor)
        outcome = worker.run_once()
        self.assertEqual(outcome.status, "waiting_approval")
        self.assertEqual(
            outcome.approval["requested_action"], "RESOLVE_HUMAN_CONDITION"
        )
        self.assertNotEqual(outcome.approval["requested_action"], "EXECUTE_JOB")
        self.assertIsNone(outcome.continuation_job_id)
        resolved = self.approvals.resolve(
            str(outcome.approval["approval_id"]),
            decision="APPROVED",
            decided_by="owner",
        )
        self.assertEqual(resolved["job"]["status"], "queued")
        self.assertEqual(resolved["job"]["continuation"]["state"], "active")
        self.assertEqual(
            resolved["job"]["approval"]["execution_id"], outcome.execution_id
        )
        executor.status = "succeeded"
        resumed = worker.run_once()
        self.assertEqual(resumed.status, "completed")
        self.assertIsNotNone(resumed.continuation_job_id)
        self.assertEqual(
            self.jobs.logical_status(str(root["job_id"]))["head_job_id"],
            resumed.continuation_job_id,
        )

    def test_29_stale_or_unrelated_human_resolution_is_rejected(self) -> None:
        self.create_planned(self.step("STEP-001", "Step one"))
        worker = self.worker(ResultExecutor("needs_human"))
        outcome = worker.run_once()
        other = self.jobs.create(self.payload(task="Other human condition"))
        self.jobs.enqueue(str(other["job_id"]))
        unrelated = worker.run_once()
        with self.assertRaises(JobRuntimeError):
            self.jobs.validate_approval_resolution(
                unrelated.approval,
                self.approvals.artifact_ref(str(outcome.approval["approval_id"])),
            )
        job = self.jobs.store.load(str(outcome.job_id))
        job["task"] = "Changed while waiting"
        self.jobs.store.save(job)
        with self.assertRaises(ApprovalRuntimeError):
            self.approvals.resolve(
                str(outcome.approval["approval_id"]),
                decision="APPROVED",
                decided_by="owner",
            )

    def test_29b_resolved_human_execution_binding_is_revalidated(self) -> None:
        self.create_planned(self.step("STEP-001", "Step one"))
        executor = CountingExecutor("needs_human")
        worker = self.worker(executor)
        outcome = worker.run_once()
        self.approvals.resolve(
            str(outcome.approval["approval_id"]),
            decision="APPROVED",
            decided_by="owner",
        )
        stored = self.jobs.store.load(str(outcome.job_id))
        stored["approval"]["execution_id"] = "unrelated"
        stored["approval"]["approval_id"] = approval_boundary_id(
            str(outcome.job_id),
            "unrelated",
            None,
            "RESOLVE_HUMAN_CONDITION",
            str(stored["approval"]["authorization_fingerprint"]),
        )
        stored["continuation"][
            "latest_execution_ref"
        ] = "runtime-execution:unrelated"
        stored["output_refs"] = [
            reference
            for reference in stored["output_refs"]
            if not str(reference.get("ref", "")).startswith("runtime-execution:")
        ]
        stored["output_refs"].append(
            {"ref_type": "artifact", "ref": "runtime-execution:unrelated"}
        )
        self.jobs.store.save(stored)
        executor.status = "succeeded"
        resumed = worker.run_once()
        self.assertEqual(resumed.status, "worker_error")
        self.assertEqual(resumed.error["code"], "claim_error")
        self.assertEqual(executor.calls, 1)

    def test_30_authoritative_logical_head_converges_without_rewriting_history(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two"),
            self.step("STEP-003", "Step three"),
        )
        worker = self.worker()
        first = worker.run_once()
        first_status = self.jobs.logical_status(str(root["job_id"]))
        self.assertEqual(first_status["head_job_id"], first.continuation_job_id)
        second = worker.run_once()
        second_status = self.jobs.logical_status(str(root["job_id"]))
        self.assertEqual(second_status["head_job_id"], second.continuation_job_id)
        worker.run_once()
        final = self.jobs.logical_status(str(root["job_id"]))
        self.assertTrue(final["terminal"])
        self.assertEqual(final["remaining_step_ids"], [])
        self.assertEqual(len(self.jobs.list()), 3)

    def test_30b_authoritative_logical_head_reports_latest_attempt(self) -> None:
        root = self.create_planned(self.step("STEP-001", "Step one"))
        running = self.jobs.claim(claimed_by="attempt-worker", lease_seconds=30)
        self.assertIsNotNone(running)
        self.jobs.fail(str(root["job_id"]), retryable=True)
        retry = self.jobs.retry(str(root["job_id"]), enqueue=True)
        status = self.jobs.logical_status(str(root["job_id"]))
        self.assertEqual(status["head_job_id"], retry["job_id"])
        self.assertEqual(status["attempt"], 2)

    def test_31_created_child_recovers_queue_once(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        running = self.jobs.claim(claimed_by="fault-worker", lease_seconds=30)
        self.assertIsNotNone(running)
        decision = ContinuationPolicy.decide_execution(
            running,
            result_status="succeeded",
            execution_ref="runtime-execution:fault-window",
        )
        self.jobs.record_execution_success(
            str(root["job_id"]), [persist_execution_fixture(self.jobs, running, decision.checkpoint["latest_execution_ref"].split(":", 1)[1])], continuation=decision.checkpoint
        )
        child = self.jobs.reserve_continuation(str(root["job_id"]))
        self.assertEqual(child["status"], "created")
        runtime = ContinuationRuntime(self.jobs, self.approvals)
        first = runtime.recover()
        second = runtime.recover()
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["status"], "queued")
        self.assertEqual(second, [])

    def test_32_review_resolution_recovers_reservation_after_crash(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one", review_required=True),
            self.step("STEP-002", "Step two"),
            review_required=True,
        )
        running = self.jobs.claim(claimed_by="review-worker", lease_seconds=30)
        self.assertIsNotNone(running)
        execution_ref = "runtime-execution:review-window"
        persist_execution_fixture(self.jobs, running, "review-window")
        execution_decision = ContinuationPolicy.decide_execution(
            running, result_status="succeeded", execution_ref=execution_ref
        )
        reviewing = self.jobs.record_execution_success(
            str(root["job_id"]),
            [{"ref_type": "artifact", "ref": execution_ref}],
            continuation=execution_decision.checkpoint,
        )
        review_ref = {"ref_type": "review", "ref": "runtime-review:review-window"}
        reviewer = Reviewer()
        self.jobs.review_store = reviewer.store
        record = self.executions.load("review-window")
        request = ExecutionRequest.from_persisted_dict(record.request)
        from runtime.core.capability_governance import certified_dispatch
        with certified_dispatch(self.executions, request, purpose="review"):
            review_ref = reviewer.run(reviewing, request, record.result).artifact_ref
        review_decision = ContinuationPolicy.decide_review(
            reviewing, decision="PASS", review_ref=str(review_ref["ref"])
        )
        transition = self.jobs.apply_review_decision(
            str(root["job_id"]),
            decision="PASS",
            reason="passed",
            review_ref=review_ref,
            continuation=review_decision.checkpoint,
        )
        self.assertEqual(transition["job"]["continuation"]["state"], "ready")
        recovered = ContinuationRuntime(self.jobs, self.approvals).recover()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "queued")

    def test_33_scheduler_view_reports_one_authoritative_head(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"), self.step("STEP-002", "Step two")
        )
        outcome = self.worker().run_once()
        statuses = self.jobs.logical_statuses()
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["logical_job_id"], root["job_id"])
        self.assertEqual(statuses[0]["head_job_id"], outcome.continuation_job_id)

    def test_34_continuation_decision_checkpoint_is_deeply_immutable(self) -> None:
        job = self.jobs.create(
            self.payload(continuation_plan=self.plan(self.step("STEP-001", "Step one")))
        )
        decision = ContinuationPolicy.decide_execution(
            job,
            result_status="succeeded",
            execution_ref="runtime-execution:immutable",
        )
        with self.assertRaises(TypeError):
            decision.checkpoint["state"] = "active"  # type: ignore[index]
        with self.assertRaises(TypeError):
            decision.checkpoint["completed_step_ids"][0] = "changed"  # type: ignore[index]

    def test_35_planned_gate_policy_cannot_be_downgraded_after_approval(self) -> None:
        created = self.jobs.create(
            self.payload(
                approval_status="required",
                review_required=True,
                continuation_plan=self.plan(
                    self.step(
                        "STEP-001",
                        "Step one",
                        requires_human_approval=True,
                        review_required=True,
                    )
                ),
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Exact gated step"
        )
        self.approvals.resolve(
            approval.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
        )
        stored = self.jobs.store.load(str(created["job_id"]))
        stored["approval_status"] = "not_required"
        stored["review_required"] = False
        stored.pop("approval", None)
        self.jobs.store.save(stored)
        with self.assertRaisesRegex(JobRuntimeError, "approval policy is weaker"):
            self.jobs.show(str(created["job_id"]))
        executor = CountingExecutor()
        outcome = self.worker(executor).run_once()
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(executor.calls, 0)

    def test_35b_current_step_execution_policy_is_monotonic(self) -> None:
        scope = {
            "project_root": str(self.root),
            "allowed_paths": ["state/jobs"],
            "forbidden_paths": ["state/jobs/protected"],
            "write_mode": "CREATE_OR_MODIFY",
            "max_changed_files": 2,
            "max_artifact_bytes": 4096,
            "allow_tests": False,
            "allow_git_reads": False,
            "allow_protected_paths": False,
            "dry_run": True,
        }
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                review_required=True,
                execution_mode="CONTROLLED_WRITE",
                execution_scope=scope,
                dry_run=True,
                continuation_plan=self.plan(
                    self.step(
                        "STEP-001",
                        "Step one",
                        requires_human_approval=True,
                        review_required=True,
                        execution_mode="CONTROLLED_WRITE",
                        dry_run=True,
                        risk_level="high",
                        execution_scope=scope,
                    )
                ),
            )
        )
        original = self.jobs.store.load(str(created["job_id"]))
        mutations = (
            lambda job: job.update(execution_mode="READ_ONLY", execution_scope=None),
            lambda job: job.update(dry_run=False),
            lambda job: job.update(risk_level="low"),
            lambda job: job["execution_scope"].update(allowed_paths=["state"]),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = deepcopy(original)
                mutate(changed)
                self.jobs.store.save(changed)
                with self.assertRaises(JobRuntimeError):
                    self.jobs.show(str(created["job_id"]))
        self.jobs.store.save(original)
        self.assertEqual(self.jobs.show(str(created["job_id"]))["status"], "created")

    def test_36_persisted_request_requires_every_canonical_field(self) -> None:
        job = self.create_planned(self.step("STEP-001", "Step one"))
        claimed = self.jobs.claim(claimed_by="field-worker", lease_seconds=30)
        self.assertIsNotNone(claimed)
        worker = self.worker()
        request = worker._build_request(
            claimed,
            "execution-complete-fields",
            worker.resolver.resolve(claimed),
        )
        for field in sorted(ExecutionRequest.PERSISTED_FIELDS):
            with self.subTest(field=field):
                incomplete = request.to_dict()
                incomplete.pop(field)
                with self.assertRaisesRegex(
                    ExecutionContractError, "incomplete or noncanonical"
                ):
                    ExecutionRequest.from_persisted_dict(incomplete)
        self.assertEqual(job["job_id"], request.job_id)

    def test_36b_defaultable_request_omissions_cannot_reconcile(self) -> None:
        for field in (
            "execution_mode",
            "dry_run",
            "approval_status",
            "execution_scope",
            "authorization_fingerprint",
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                clock = Clock()
                jobs = JobRuntime(root / "jobs", clock=clock, id_factory=IDs("job"))
                executions = FileExecutionStore(root / "executions")
                approvals = ApprovalRuntime(
                    jobs,
                    FileApprovalStore(root / "approvals"),
                    execution_store=executions,
                    clock=clock,
                )
                created = jobs.create(
                    self.payload(
                        continuation_plan=self.plan(
                            self.step("STEP-001", "Step one")
                        )
                    )
                )
                jobs.enqueue(str(created["job_id"]))
                executor = CountingExecutor()
                worker = Worker(
                    jobs,
                    CanonicalReferenceResolver(REPOSITORY_ROOT),
                    executor,
                    executions,
                    approval_runtime=approvals,
                    clock=clock,
                    id_factory=IDs("execution"),
                )
                original = jobs.record_execution_success

                def fail_update(*args: object, **kwargs: object) -> dict[str, object]:
                    raise JobRuntimeError("injected crash")

                jobs.record_execution_success = fail_update  # type: ignore[method-assign]
                first = worker.run_once()
                jobs.record_execution_success = original  # type: ignore[method-assign]
                path = executions._path(str(first.execution_id))
                record = json.loads(path.read_text(encoding="utf-8"))
                record["request"].pop(field)
                path.write_text(json.dumps(record), encoding="utf-8")
                recovered = worker.recover_persisted_results()
                self.assertEqual(recovered[0].status, "worker_error")
                self.assertEqual(jobs.show(str(created["job_id"]))["status"], "running")
                self.assertEqual(executor.calls, 1)

    def test_37_competing_continuation_child_fails_closed(self) -> None:
        self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two"),
        )
        outcome = self.worker().run_once()
        child = self.jobs.store.load(str(outcome.continuation_job_id))
        fork = deepcopy(child)
        fork["job_id"] = "job-competing-continuation"
        self.jobs.store.create(fork)
        with self.assertRaisesRegex(
            JobRuntimeError, "child ID|competing canonical children|task contract"
        ):
            self.jobs.logical_statuses()
        restarted = JobRuntime(self.jobs.store.root, clock=self.clock)
        with self.assertRaisesRegex(
            JobRuntimeError, "child ID|competing canonical children|task contract"
        ):
            restarted.show(str(child["job_id"]))

    def test_38_ordinary_retry_lineage_rejects_self_parent_and_cycles(self) -> None:
        created = self.jobs.create(self.payload(max_attempts=3))
        self.jobs.enqueue(str(created["job_id"]))
        self.jobs.claim(claimed_by="retry-lineage", lease_seconds=30)
        self.jobs.fail(str(created["job_id"]), retryable=True)
        retry = self.jobs.retry(str(created["job_id"]))
        self.assertEqual(self.jobs.show(str(retry["job_id"]))["attempt"], 2)

        original = self.jobs.store.load(str(retry["job_id"]))
        self_parent = deepcopy(original)
        self_parent["parent_job_id"] = self_parent["job_id"]
        self_parent["created_by"] = f"retry:{self_parent['job_id']}"
        self.jobs.store.save(self_parent)
        with self.assertRaisesRegex(JobRuntimeError, "parent itself|cycle"):
            self.jobs.show(str(retry["job_id"]))
        self.jobs.store.save(original)

        invalid_attempt = deepcopy(original)
        invalid_attempt["attempt"] = 3
        self.jobs.store.save(invalid_attempt)
        with self.assertRaisesRegex(JobRuntimeError, "advance exactly once"):
            self.jobs.show(str(retry["job_id"]))
        self.jobs.store.save(original)

        failed_parent = self.jobs.store.load(str(created["job_id"]))
        invalid_parent = deepcopy(failed_parent)
        invalid_parent["status"] = "created"
        self.jobs.store.save(invalid_parent)
        with self.assertRaisesRegex(JobRuntimeError, "failed job"):
            self.jobs.show(str(retry["job_id"]))
        self.jobs.store.save(failed_parent)

        other = self.jobs.store.load(str(created["job_id"]))
        other["status"] = "created"
        other["attempt"] = 3
        other["parent_job_id"] = retry["job_id"]
        other["created_by"] = f"retry:{retry['job_id']}"
        self.jobs.store.save(other)
        cycle_retry = self.jobs.store.load(str(retry["job_id"]))
        cycle_retry["status"] = "failed"
        cycle_retry["attempt"] = 2
        cycle_retry["parent_job_id"] = created["job_id"]
        cycle_retry["created_by"] = f"retry:{created['job_id']}"
        self.jobs.store.save(cycle_retry)
        with self.assertRaises(JobRuntimeError):
            self.jobs.show(str(retry["job_id"]))

    def test_39_forged_compact_human_authority_requires_real_artifacts(self) -> None:
        self.create_planned(self.step("STEP-001", "Step one"))
        executor = CountingExecutor("needs_human")
        worker = self.worker(executor)
        outcome = worker.run_once()
        self.approvals.resolve(
            str(outcome.approval["approval_id"]),
            decision="APPROVED",
            decided_by="owner",
        )
        stored = self.jobs.store.load(str(outcome.job_id))
        fake_execution = "execution-missing-authority"
        fake_approval = approval_boundary_id(
            str(outcome.job_id),
            fake_execution,
            None,
            "RESOLVE_HUMAN_CONDITION",
            str(stored["approval"]["authorization_fingerprint"]),
        )
        stored["approval"]["execution_id"] = fake_execution
        stored["approval"]["approval_id"] = fake_approval
        stored["continuation"]["latest_execution_ref"] = (
            f"runtime-execution:{fake_execution}"
        )
        for reference in stored["output_refs"]:
            if str(reference.get("ref", "")).startswith("runtime-execution:"):
                reference["ref"] = f"runtime-execution:{fake_execution}"
            if str(reference.get("ref", "")).startswith("runtime-approval:"):
                reference["ref"] = f"runtime-approval:{fake_approval}"
        self.jobs.store.save(stored)
        with self.assertRaisesRegex(
            JobRuntimeError, "does not match its execution evidence"
        ):
            self.jobs.show(str(outcome.job_id))
        executor.status = "succeeded"
        resumed = worker.run_once()
        self.assertEqual(resumed.status, "worker_error")
        self.assertEqual(executor.calls, 1)

    def test_39b_human_authority_survives_restart_with_real_artifacts(self) -> None:
        self.create_planned(self.step("STEP-001", "Step one"))
        first = self.worker(ResultExecutor("needs_human")).run_once()
        self.approvals.resolve(
            str(first.approval["approval_id"]),
            decision="APPROVED",
            decided_by="owner",
        )
        jobs = JobRuntime(
            self.jobs.store.root,
            clock=self.clock,
            id_factory=IDs("job-restarted"),
        )
        executions = FileExecutionStore(self.executions.root)
        approvals = ApprovalRuntime(
            jobs,
            FileApprovalStore(self.approvals.store.root),
            execution_store=executions,
            clock=self.clock,
        )
        executor = CountingExecutor("succeeded")
        worker = Worker(
            jobs,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor,
            executions,
            approval_runtime=approvals,
            clock=self.clock,
            id_factory=IDs("execution-restarted"),
        )
        resumed = worker.run_once()
        self.assertEqual(resumed.status, "completed")
        self.assertEqual(executor.calls, 1)

    def test_39c_human_authority_rejects_store_status_mismatch(self) -> None:
        self.create_planned(self.step("STEP-001", "Step one"))
        outcome = self.worker(ResultExecutor("needs_human")).run_once()
        approval_id = str(outcome.approval["approval_id"])
        execution_id = str(outcome.execution_id)
        self.approvals.resolve(
            approval_id,
            decision="APPROVED",
            decided_by="owner",
        )

        approval_path = self.approvals.store._path(approval_id)
        approval_record = json.loads(approval_path.read_text(encoding="utf-8"))
        rejected = deepcopy(approval_record)
        rejected["status"] = "REJECTED"
        approval_path.write_text(json.dumps(rejected), encoding="utf-8")
        with self.assertRaisesRegex(
            JobRuntimeError, "does not match its execution evidence"
        ):
            self.jobs.show(str(outcome.job_id))
        approval_path.write_text(json.dumps(approval_record), encoding="utf-8")

        execution_path = self.executions._path(execution_id)
        execution_record = json.loads(execution_path.read_text(encoding="utf-8"))
        not_human = deepcopy(execution_record)
        not_human["result"]["status"] = "succeeded"
        not_human["result"]["summary"] = "Changed persisted status"
        not_human["result"]["blockers"] = []
        execution_path.write_text(json.dumps(not_human), encoding="utf-8")
        with self.assertRaisesRegex(
            JobRuntimeError, "does not match its execution evidence"
        ):
            self.jobs.show(str(outcome.job_id))

    def test_40_coordinated_r4_plan_and_policy_rewrite_fails_closed(self) -> None:
        scope = {
            "project_root": str(self.root),
            "allowed_paths": ["state/jobs"],
            "forbidden_paths": ["state/jobs/protected"],
            "write_mode": "CREATE_OR_MODIFY",
            "max_changed_files": 2,
            "max_artifact_bytes": 4096,
            "allow_tests": False,
            "allow_git_reads": False,
            "allow_protected_paths": False,
            "dry_run": True,
        }
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                review_required=True,
                execution_mode="CONTROLLED_WRITE",
                execution_scope=scope,
                dry_run=True,
                continuation_plan=self.plan(
                    self.step(
                        "STEP-001",
                        "Step one",
                        requires_human_approval=True,
                        review_required=True,
                        execution_mode="CONTROLLED_WRITE",
                        dry_run=True,
                        risk_level="approval_required",
                        execution_scope=scope,
                    )
                ),
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Original controlled step"
        )
        self.approvals.resolve(
            approval.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
        )
        stored = self.jobs.store.load(str(created["job_id"]))
        step = stored["continuation_plan"]["steps"][0]
        step.update(
            {
                "requires_human_approval": False,
                "review_required": False,
                "execution_mode": "READ_ONLY",
                "dry_run": False,
                "risk_level": "low",
                "execution_scope": None,
            }
        )
        stored["continuation"]["plan_digest"] = continuation_plan_digest(
            stored["continuation_plan"]
        )
        stored.update(
            {
                "approval_status": "not_required",
                "review_required": False,
                "execution_mode": "READ_ONLY",
                "execution_scope": None,
                "dry_run": False,
                "risk_level": "low",
            }
        )
        stored.pop("approval", None)
        stored["output_refs"] = [
            reference
            for reference in stored["output_refs"]
            if not str(reference.get("ref", "")).startswith("runtime-approval:")
        ]
        self.jobs.store.save(stored)
        with self.assertRaisesRegex(JobRuntimeError, "immutable authorized plan"):
            self.jobs.show(str(created["job_id"]))
        executor = CountingExecutor()
        outcome = self.worker(executor).run_once()
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(executor.calls, 0)

    def test_41_each_coordinated_plan_mutation_invalidates_authority(self) -> None:
        scope = {
            "project_root": str(self.root),
            "allowed_paths": ["state/jobs"],
            "forbidden_paths": ["state/jobs/protected"],
            "write_mode": "CREATE_OR_MODIFY",
            "max_changed_files": 2,
            "max_artifact_bytes": 4096,
            "allow_tests": False,
            "allow_git_reads": False,
            "allow_protected_paths": False,
            "dry_run": True,
        }
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                review_required=True,
                execution_mode="CONTROLLED_WRITE",
                execution_scope=scope,
                dry_run=True,
                continuation_plan=self.plan(
                    self.step(
                        "STEP-001",
                        "Step one",
                        input_refs=[],
                        requires_human_approval=True,
                        review_required=True,
                        execution_mode="CONTROLLED_WRITE",
                        dry_run=True,
                        risk_level="approval_required",
                        execution_scope=scope,
                    )
                ),
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Mutation matrix"
        )
        self.approvals.resolve(
            approval.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
        )
        original = self.jobs.store.load(str(created["job_id"]))

        def approval_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["requires_human_approval"] = False  # type: ignore[index]
            job["continuation_plan"]["steps"][0]["risk_level"] = "low"  # type: ignore[index]
            job["approval_status"] = "not_required"
            job["risk_level"] = "low"
            job.pop("approval", None)

        def review_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["review_required"] = False  # type: ignore[index]
            job["review_required"] = False

        def mode_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["execution_mode"] = "READ_ONLY"  # type: ignore[index]
            job["continuation_plan"]["steps"][0]["execution_scope"] = None  # type: ignore[index]
            job["execution_mode"] = "READ_ONLY"
            job["execution_scope"] = None

        def dry_run_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["dry_run"] = False  # type: ignore[index]
            job["continuation_plan"]["steps"][0]["execution_scope"]["dry_run"] = False  # type: ignore[index]
            job["execution_scope"]["dry_run"] = False  # type: ignore[index]
            job["dry_run"] = False

        def risk_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["risk_level"] = "low"  # type: ignore[index]
            job["risk_level"] = "low"

        def scope_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["execution_scope"]["allowed_paths"] = ["state"]  # type: ignore[index]
            job["execution_scope"]["allowed_paths"] = ["state"]  # type: ignore[index]

        def task_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["task"] = "Changed task"  # type: ignore[index]
            job["task"] = "Changed task"

        def input_mutation(job: dict[str, object]) -> None:
            references = [{"ref_type": "other", "ref": "changed-input"}]
            job["continuation_plan"]["steps"][0]["input_refs"] = references  # type: ignore[index]
            job["input_refs"] = references

        def step_id_mutation(job: dict[str, object]) -> None:
            job["continuation_plan"]["steps"][0]["step_id"] = "STEP-CHANGED"  # type: ignore[index]
            job["continuation"]["current_step_id"] = "STEP-CHANGED"  # type: ignore[index]
            job["continuation"]["remaining_step_ids"] = ["STEP-CHANGED"]  # type: ignore[index]

        mutations = {
            "approval": approval_mutation,
            "review": review_mutation,
            "execution_mode": mode_mutation,
            "dry_run": dry_run_mutation,
            "risk": risk_mutation,
            "scope": scope_mutation,
            "task": task_mutation,
            "inputs": input_mutation,
            "step_id": step_id_mutation,
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                changed = deepcopy(original)
                mutate(changed)
                changed["continuation"]["plan_digest"] = continuation_plan_digest(  # type: ignore[index]
                    changed["continuation_plan"]
                )
                self.jobs.store.save(changed)
                with self.assertRaises(JobRuntimeError):
                    self.jobs.show(str(created["job_id"]))
                self.jobs.store.save(original)

        replaced_digest = deepcopy(original)
        replaced_digest["continuation"]["plan_digest"] = "f" * 64
        self.jobs.store.save(replaced_digest)
        with self.assertRaisesRegex(JobRuntimeError, "plan digest does not match"):
            self.jobs.show(str(created["job_id"]))
        self.jobs.store.save(original)

        two_step = self.jobs.create(
            self.payload(
                continuation_plan=self.plan(
                    self.step("ORDER-001", "First"),
                    self.step("ORDER-002", "Second"),
                ),
                task="First",
            )
        )
        reordered = self.jobs.store.load(str(two_step["job_id"]))
        reordered["continuation_plan"]["steps"].reverse()
        reordered["task"] = "Second"
        reordered["continuation"].update(
            {
                "plan_digest": continuation_plan_digest(
                    reordered["continuation_plan"]
                ),
                "current_step_id": "ORDER-002",
                "remaining_step_ids": ["ORDER-002", "ORDER-001"],
            }
        )
        self.jobs.store.save(reordered)
        with self.assertRaisesRegex(JobRuntimeError, "immutable authorized plan"):
            self.jobs.show(str(two_step["job_id"]))

    def test_42_authorized_plan_anchor_survives_restart_child_and_retry(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two"),
            max_attempts=2,
        )
        authority = self.jobs.authorized_plan_store.load(str(root["job_id"]))
        restarted = JobRuntime(self.jobs.store.root, clock=self.clock)
        self.assertEqual(
            restarted.show(str(root["job_id"]))["continuation"]["plan_digest"],
            authority["plan_digest"],
        )
        first = self.worker().run_once()
        child = self.jobs.show(str(first.continuation_job_id))
        self.assertEqual(child["continuation"]["logical_job_id"], root["job_id"])
        self.assertFalse(
            self.jobs.authorized_plan_store.exists(str(child["job_id"]))
        )
        self.jobs.claim(claimed_by="anchored-retry", lease_seconds=30)
        self.jobs.fail(str(child["job_id"]), retryable=True)
        retry = self.jobs.retry(str(child["job_id"]))
        self.assertEqual(
            self.jobs.show(str(retry["job_id"]))["continuation"]["plan_digest"],
            authority["plan_digest"],
        )

    def test_43_authorized_plan_anchor_is_required_and_write_once(self) -> None:
        root = self.jobs.create(
            self.payload(
                continuation_plan=self.plan(self.step("STEP-001", "Step one"))
            )
        )
        with self.assertRaises(AuthorizedPlanStoreError):
            self.jobs.authorized_plan_store.create(
                str(root["job_id"]),
                root["continuation_plan"],
                authorized_at=self.clock(),
            )
        self.jobs.authorized_plan_store._path(str(root["job_id"])).unlink()
        with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
            self.jobs.show(str(root["job_id"]))

    def test_44_deleted_authority_cannot_be_rebound_after_restart(self) -> None:
        scope = {
            "project_root": str(self.root),
            "allowed_paths": ["state/jobs"],
            "forbidden_paths": ["state/jobs/protected"],
            "write_mode": "CREATE_OR_MODIFY",
            "max_changed_files": 2,
            "max_artifact_bytes": 4096,
            "allow_tests": False,
            "allow_git_reads": False,
            "allow_protected_paths": False,
            "dry_run": True,
        }
        created = self.jobs.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
                review_required=True,
                execution_mode="CONTROLLED_WRITE",
                execution_scope=scope,
                dry_run=True,
                continuation_plan=self.plan(
                    self.step(
                        "STEP-001",
                        "Step one",
                        requires_human_approval=True,
                        review_required=True,
                        execution_mode="CONTROLLED_WRITE",
                        dry_run=True,
                        risk_level="approval_required",
                        execution_scope=scope,
                    )
                ),
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Original controlled step"
        )
        self.approvals.resolve(
            approval.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
        )
        logical_id = str(created["job_id"])
        store = self.jobs.authorized_plan_store
        self.assertTrue(store._manifest_path(logical_id).is_file())
        store._path(logical_id).unlink()

        restarted = JobRuntime(self.jobs.store.root, clock=self.clock)
        with self.assertRaisesRegex(AuthorizedPlanStoreError, "recovery hold"):
            restarted.authorized_plan_store.create(
                logical_id,
                created["continuation_plan"],
                authorized_at=self.clock(),
            )

        stored = self.jobs.store.load(logical_id)
        step = stored["continuation_plan"]["steps"][0]
        step.update(
            {
                "requires_human_approval": False,
                "review_required": False,
                "execution_mode": "READ_ONLY",
                "dry_run": False,
                "risk_level": "low",
                "execution_scope": None,
            }
        )
        stored["continuation"]["plan_digest"] = continuation_plan_digest(
            stored["continuation_plan"]
        )
        stored.update(
            {
                "approval_status": "not_required",
                "review_required": False,
                "execution_mode": "READ_ONLY",
                "execution_scope": None,
                "dry_run": False,
                "risk_level": "low",
            }
        )
        stored.pop("approval", None)
        stored["output_refs"] = [
            reference
            for reference in stored["output_refs"]
            if not str(reference.get("ref", "")).startswith("runtime-approval:")
        ]
        self.jobs.store.save(stored)
        with self.assertRaisesRegex(AuthorizedPlanStoreError, "recovery hold"):
            restarted.authorized_plan_store.create(
                logical_id,
                stored["continuation_plan"],
                authorized_at=self.clock(),
            )
        for operation in (
            lambda: restarted.show(logical_id),
            lambda: restarted.enqueue(logical_id),
            restarted.eligible,
            lambda: restarted.claim(claimed_by="r5", lease_seconds=30),
        ):
            with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
                operation()

        restarted_approvals = ApprovalRuntime(
            restarted,
            FileApprovalStore(self.root / "state" / "approvals"),
            execution_store=self.executions,
            clock=self.clock,
        )
        with self.assertRaisesRegex(
            (ApprovalRuntimeError, JobRuntimeError), "recovery hold"
        ):
            restarted_approvals.request_execution(
                logical_id, reason="Must remain held"
            )
        executor = CountingExecutor()
        worker = Worker(
            restarted,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor,
            self.executions,
            approval_runtime=restarted_approvals,
            clock=self.clock,
            id_factory=IDs("execution-held"),
        )
        outcome = worker.run_once()
        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(executor.calls, 0)
        second_restart = JobRuntime(self.jobs.store.root, clock=self.clock)
        with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
            second_restart.show(logical_id)

    def test_45_authority_loss_blocks_continuation_and_retry_recovery(self) -> None:
        root = self.create_planned(
            self.step("STEP-001", "Step one"),
            self.step("STEP-002", "Step two"),
            max_attempts=2,
        )
        first = self.worker().run_once()
        child_id = str(first.continuation_job_id)
        child = self.jobs.store.load(child_id)
        logical_id = str(root["job_id"])
        self.jobs.authorized_plan_store._path(logical_id).unlink()
        restarted = JobRuntime(self.jobs.store.root, clock=self.clock)
        with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
            restarted.reserve_continuation(str(root["job_id"]))
        with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
            restarted.show(child_id)
        child["status"] = "failed"
        child["error"] = {
            "code": "temporary",
            "message": "retry fixture",
            "retryable": True,
        }
        self.jobs.store.save(child)
        with self.assertRaisesRegex(JobRuntimeError, "recovery hold"):
            restarted.retry(child_id)
        self.assertFalse(restarted.authorized_plan_store.exists(child_id))

    def test_46_authorized_plan_create_enforces_canonical_schema(self) -> None:
        store = FileAuthorizedPlanStore(self.root / "authority-validation")
        valid_step = self.step("STEP-001", "Step one")
        invalid_plans = {
            "missing-steps": {"plan_id": "plan"},
            "empty-steps": {"plan_id": "plan", "steps": []},
            "unexpected-plan": {
                "plan_id": "plan",
                "steps": [valid_step],
                "unexpected": True,
            },
            "unexpected-step": self.plan(
                self.step("STEP-001", "Step one", unexpected=True)
            ),
            "duplicate-step-id": self.plan(
                self.step("STEP-001", "Step one"),
                self.step("STEP-001", "Different task"),
            ),
            "invalid-task": self.plan(self.step("STEP-001", "")),
            "invalid-policy": self.plan(
                self.step("STEP-001", "Step one", execution_mode="UNSAFE")
            ),
            "long-plan-id": {
                "plan_id": "p" * 201,
                "steps": [valid_step],
            },
            "malformed-input": self.plan(
                self.step("STEP-001", "Step one", input_refs=[{"ref": "x"}])
            ),
            "malformed-scope": self.plan(
                self.step("STEP-001", "Step one", execution_scope={})
            ),
        }
        for logical_id, plan in invalid_plans.items():
            with self.subTest(logical_id=logical_id):
                with self.assertRaises(AuthorizedPlanStoreError):
                    store.create(
                        logical_id,
                        plan,
                        authorized_at=self.clock(),
                    )
                self.assertFalse(store.exists(logical_id))
        with self.assertRaises(AuthorizedPlanStoreError):
            store.create(
                "l" * 201,
                self.plan(valid_step),
                authorized_at=self.clock(),
            )
        with self.assertRaises(AuthorizedPlanStoreError):
            store.create(
                "malformed-timestamp",
                self.plan(valid_step),
                authorized_at="not-a-timestamp",
            )

    def test_47_authorized_plan_load_enforces_schema_and_manifest(self) -> None:
        mutations = {
            "missing-field": lambda record: record.pop("authorized_at"),
            "unexpected-top-level": lambda record: record.update(unexpected=True),
            "invalid-digest": lambda record: record.update(plan_digest="invalid"),
            "unexpected-plan": lambda record: record["plan"].update(unexpected=True),
            "unexpected-step": lambda record: record["plan"]["steps"][0].update(
                unexpected=True
            ),
            "empty-steps": lambda record: record["plan"].update(steps=[]),
            "long-logical-id": lambda record: record.update(logical_job_id="l" * 201),
            "long-plan-id": lambda record: (
                record.update(plan_id="p" * 201),
                record["plan"].update(plan_id="p" * 201),
            ),
            "malformed-timestamp": lambda record: record.update(
                authorized_at="not-a-timestamp"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                store = FileAuthorizedPlanStore(
                    self.root / "authority-load" / label
                )
                logical_id = "root"
                store.create(
                    logical_id,
                    self.plan(self.step("STEP-001", "Step one")),
                    authorized_at=self.clock(),
                )
                record = json.loads(
                    store._path(logical_id).read_text(encoding="utf-8")
                )
                mutate(record)
                serialized = json.dumps(record)
                store._path(logical_id).write_text(serialized, encoding="utf-8")
                store._manifest_path(logical_id).write_text(
                    serialized, encoding="utf-8"
                )
                with self.assertRaises(AuthorizedPlanStoreError):
                    store.load(logical_id)

        valid = FileAuthorizedPlanStore(self.root / "authority-load" / "valid")
        record = valid.create(
            "root",
            self.plan(self.step("STEP-001", "Step one")),
            authorized_at=self.clock(),
        )
        restarted = FileAuthorizedPlanStore(valid.root)
        self.assertEqual(restarted.load("root"), record)
        changed = deepcopy(record)
        changed["plan"]["steps"][0]["task"] = "Changed step"
        changed["plan_digest"] = continuation_plan_digest(changed["plan"])
        valid._path("root").write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(
            AuthorizedPlanStoreError, "durable creation evidence"
        ):
            restarted.load("root")


if __name__ == "__main__":
    unittest.main()
