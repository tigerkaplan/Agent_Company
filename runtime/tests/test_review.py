from __future__ import annotations

from runtime.tests.contract_fixtures import declare_fixture_contract

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.executors.local import LocalExecutor
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfiguration
from runtime.providers.models import (
    ProviderAvailability,
    ProviderExecutionResult,
    ProviderSelection,
)
from runtime.providers.routing import ProviderRouter
from runtime.review.context import ReviewContextBuilder
from runtime.review.models import ReviewPackage, ReviewerResponse
from runtime.review.reviewers import ProviderBackedReviewer
from runtime.review.runtime import ReviewerRuntime
from runtime.review.store import FileReviewStore
from runtime.review.verification import DeterministicVerifier
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeReviewer:
    def __init__(
        self,
        decision: str,
        *,
        raw_output: str = "",
        reason: str = "Evidence supports the normalized decision",
    ) -> None:
        self.decision = decision
        self.raw_output = raw_output
        self.reason = reason
        self.calls: list[ReviewPackage] = []

    def review(self, package: ReviewPackage) -> ReviewerResponse:
        self.calls.append(package)
        evidence = package.available_evidence_refs[:1]
        return ReviewerResponse(
            decision=self.decision,
            reason=self.reason,
            evidence_refs=evidence,
            reviewer="reviewer",
            review_provider="codex",
            same_provider_review=False,
            model_review_performed=True,
            raw_output=self.raw_output,
        )


class FakeAdapter:
    native_tools = frozenset()
    def __init__(
        self,
        provider_id: str,
        *,
        available: bool,
        result: ProviderExecutionResult | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.available = available
        self.result = result or ProviderExecutionResult(
            status="succeeded",
            stdout="",
            stderr="",
            exit_code=0,
        )
        self.calls = 0

    def is_available(self) -> ProviderAvailability:
        return ProviderAvailability(
            available=self.available,
            reason="fake_available" if self.available else "fake_unavailable",
            executable_path=f"C:/fake/{self.provider_id}.exe" if self.available else None,
        )

    def execute(
        self, request: ExecutionRequest, context: object
    ) -> ProviderExecutionResult:
        self.calls += 1
        return self.result


class ReviewTestHarness:
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.job_root = self.root / "jobs"
        self.execution_root = self.root / "executions"
        self.execution_store = FileExecutionStore(self.execution_root)
        self.provider_store = FileProviderArtifactStore(
            self.execution_root / "provider-output"
        )
        self.review_store = FileReviewStore(self.execution_root / "reviews")
        self.runtime = JobRuntime(self.job_root)
        self.runtime.execution_store = self.execution_store
        self.runtime.review_store = self.review_store

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Verify a bounded execution result",
            "task_class": "software",
            "agent": "software",
            "workflow": "software",
            "capability": "software_implementation",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": True,
            "max_attempts": 2,
            "input_refs": [],
            "output_refs": [],
            "created_by": "review-test",
        }
        value.update(overrides)
        return declare_fixture_contract(value)

    def prepare_execution(
        self,
        *,
        provider: str | None = None,
        max_attempts: int = 2,
        persist_execution: bool = True,
    ) -> tuple[dict[str, object], ExecutionRequest, ExecutionResult]:
        created = self.runtime.create(
            self.payload(provider=provider, max_attempts=max_attempts)
        )
        self.runtime.enqueue(str(created["job_id"]))
        running = self.runtime.claim()
        assert running is not None
        execution_id = f"execution-{created['job_id']}"
        refs = CanonicalReferenceResolver(REPOSITORY_ROOT).resolve(running)
        request = ExecutionRequest(
                      task_contract=running["task_contract"],
            execution_id=execution_id,
            job_id=str(created["job_id"]),
            task=str(running["task"]),
            task_class=str(running["task_class"]),
            project_id=None,
            agent=str(running["agent"]),
            skill=None,
            workflow=str(running["workflow"]),
            capability=str(running["capability"]),
            provider=provider,
            risk_level=str(running["risk_level"]),
            input_refs=(),
            context_refs=refs,
            review_required=True,
            attempt=int(running["attempt"]),
            approval_status=str(running["approval_status"]),
        )
        output_refs: tuple[dict[str, object], ...] = ()
        if provider is not None:
            provider_ref = self.provider_store.create(
                execution_id,
                ProviderSelection(provider, provider, provider, False, None),
                ProviderExecutionResult(
                    status="succeeded",
                    stdout="bounded provider evidence",
                    stderr="",
                    exit_code=0,
                ),
            )
            output_refs = (provider_ref,)
        result = ExecutionResult(
            execution_id=execution_id,
            job_id=str(created["job_id"]),
            status="succeeded",
            output_refs=output_refs,
            summary="Executor reported success",
            error=None,
            provider=provider,
            started_at="2026-09-22T12:00:00Z",
            completed_at="2026-09-22T12:00:01Z",
            requested_provider=provider,
            preferred_provider=provider,
        )
        if persist_execution:
            self.execution_store.create(request, result)
        execution_ref = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{execution_id}",
            "description": "Local provider-neutral execution record",
        }
        reviewing = self.runtime.record_execution_success(
            str(created["job_id"]), [*result.output_refs, execution_ref]
        )
        return reviewing, request, result

    def reviewer_runtime(self, reviewer: object) -> ReviewerRuntime:
        return ReviewerRuntime(
            DeterministicVerifier(self.execution_store, self.provider_store),
            ReviewContextBuilder(
                REPOSITORY_ROOT, self.execution_store, self.provider_store
            ),
            reviewer,  # type: ignore[arg-type]
            self.review_store,
            id_factory=lambda: "review-fixed-001",
            clock=lambda: "2026-09-22T12:00:02Z",
        )


class ReviewRuntimeTests(ReviewTestHarness, unittest.TestCase):

    def test_a_deterministic_pass_precedes_reviewer(self) -> None:
        job, request, result = self.prepare_execution()
        verification = DeterministicVerifier(
            self.execution_store, self.provider_store
        ).verify(job, request, result)
        self.assertEqual(verification.status, "PASS")
        self.assertTrue(all(check.status == "PASS" for check in verification.checks))

    def test_a2_needs_review_is_consumed_without_becoming_the_verdict(self) -> None:
        job, request, original = self.prepare_execution(persist_execution=False)
        needs_review = ExecutionResult(
            execution_id=original.execution_id,
            job_id=original.job_id,
            status="needs_review",
            summary="Execution produced work requiring independent review",
            error=None,
            provider=None,
            started_at=original.started_at,
            completed_at=original.completed_at,
            evidence=(
                {
                    "kind": "observation",
                    "status": "observed",
                    "summary": "Reviewable work was produced",
                },
            ),
        )
        self.execution_store.create(request, needs_review)
        review_run = self.reviewer_runtime(FakeReviewer("PASS")).run(
            job, request, needs_review
        )

        self.assertEqual(review_run.result.decision, "PASS")
        self.assertNotEqual(needs_review.status, review_run.result.decision)
        self.assertTrue(review_run.result.model_review_performed)

    def test_b_deterministic_failure_skips_model_reviewer(self) -> None:
        job, request, result = self.prepare_execution(persist_execution=False)
        reviewer = FakeReviewer("PASS")
        review_run = self.reviewer_runtime(reviewer).run(job, request, result)
        self.assertEqual(review_run.result.decision, "FAIL")
        self.assertEqual(
            review_run.result.error_category, "deterministic_verification_failure"
        )
        self.assertFalse(review_run.result.model_review_performed)
        self.assertEqual(reviewer.calls, [])

    def test_c_to_f_normalized_review_decisions(self) -> None:
        for decision in ("PASS", "FAIL", "RETRY", "NEEDS_HUMAN"):
            with self.subTest(decision=decision):
                self.tearDown()
                self.setUp()
                job, request, result = self.prepare_execution()
                review_run = self.reviewer_runtime(FakeReviewer(decision)).run(
                    job, request, result
                )
                self.assertEqual(review_run.result.decision, decision)
                self.assertTrue(review_run.result.evidence_refs)

    def test_g_review_artifact_persists_and_sanitizes(self) -> None:
        job, request, result = self.prepare_execution()
        review_run = self.reviewer_runtime(
            FakeReviewer(
                "PASS", raw_output="OPENAI_API_KEY=TEST_REVIEW_SENTINEL"
            )
        ).run(job, request, result)
        stored = self.review_store.load(review_run.result.review_id)
        self.assertNotIn("TEST_REVIEW_SENTINEL", stored["raw_output"])
        self.assertIn("[REDACTED]", stored["raw_output"])
        self.assertEqual(stored["result"]["decision"], "PASS")

    def test_h_evidence_refs_are_persisted(self) -> None:
        job, request, result = self.prepare_execution()
        review_run = self.reviewer_runtime(FakeReviewer("PASS")).run(
            job, request, result
        )
        stored = self.review_store.load(review_run.result.review_id)["result"]
        self.assertEqual(stored["evidence_refs"], list(review_run.result.evidence_refs))
        self.assertTrue(stored["deterministic_checks"])

    def test_i_state_survives_reload(self) -> None:
        job, request, result = self.prepare_execution()
        review_run = self.reviewer_runtime(FakeReviewer("PASS")).run(
            job, request, result
        )
        transition = self.runtime.apply_review_decision(
            str(job["job_id"]),
            decision="PASS",
            reason=review_run.result.reason,
            review_ref=review_run.artifact_ref,
        )
        reloaded_runtime = JobRuntime(self.job_root)
        reloaded_store = FileReviewStore(self.execution_root / "reviews")
        self.assertEqual(
            reloaded_runtime.show(str(job["job_id"]))["status"], "completed"
        )
        self.assertEqual(
            reloaded_store.load(review_run.result.review_id)["result"]["decision"],
            "PASS",
        )
        self.assertEqual(transition["job"]["status"], "completed")


class ReviewerProviderTests(ReviewTestHarness, unittest.TestCase):
    def configured_runtime(
        self,
        *,
        executor_provider: str,
        claude: FakeAdapter,
        codex: FakeAdapter,
        risk_level: str = "low",
    ) -> tuple[ReviewerRuntime, dict[str, object], ExecutionRequest, ExecutionResult]:
        configuration = ProviderConfiguration(REPOSITORY_ROOT)
        router = ProviderRouter(
            configuration, {"claude": claude, "codex": codex}
        )
        job, request, result = self.prepare_execution(provider=executor_provider)
        if risk_level != "low":
            job = dict(job)
            job["risk_level"] = risk_level
        reviewer = ProviderBackedReviewer(router)
        return self.reviewer_runtime(reviewer), job, request, result

    @staticmethod
    def decision_result(decision: str) -> ProviderExecutionResult:
        return ProviderExecutionResult(
            status="succeeded",
            stdout=json.dumps(
                {
                    "decision": decision,
                    "reason": "Evidence independently supports this decision",
                    "evidence_refs": [
                        {
                            "ref_type": "artifact",
                            "ref": "PLACEHOLDER",
                        }
                    ],
                }
            ),
            stderr="",
            exit_code=0,
        )

    def test_j_malformed_reviewer_output_needs_human(self) -> None:
        runtime, job, request, result = self.configured_runtime(
            executor_provider="codex",
            claude=FakeAdapter(
                "claude",
                available=True,
                result=ProviderExecutionResult("succeeded", "PASS", "", 0),
            ),
            codex=FakeAdapter("codex", available=True),
        )
        review_run = runtime.run(job, request, result)
        self.assertEqual(review_run.result.decision, "NEEDS_HUMAN")
        self.assertEqual(review_run.result.error_category, "invalid_review_output")

    def test_k_unavailable_reviewer_is_explicit(self) -> None:
        runtime, job, request, result = self.configured_runtime(
            executor_provider="codex",
            claude=FakeAdapter("claude", available=False),
            codex=FakeAdapter("codex", available=False),
        )
        review_run = runtime.run(job, request, result)
        self.assertEqual(review_run.result.decision, "NEEDS_HUMAN")
        self.assertEqual(review_run.result.error_category, "reviewer_unavailable")
        self.assertFalse(review_run.result.model_review_performed)

    def test_l_reviewer_timeout_is_distinct(self) -> None:
        runtime, job, request, result = self.configured_runtime(
            executor_provider="codex",
            claude=FakeAdapter(
                "claude",
                available=True,
                result=ProviderExecutionResult(
                    "failed", "", "", None, "provider_timeout", "Timed out"
                ),
            ),
            codex=FakeAdapter("codex", available=True),
        )
        review_run = runtime.run(job, request, result)
        self.assertEqual(review_run.result.error_category, "review_timeout")
        self.assertEqual(review_run.result.decision, "NEEDS_HUMAN")

    def test_m_same_provider_review_is_disclosed(self) -> None:
        claude = FakeAdapter("claude", available=False)
        codex = FakeAdapter("codex", available=True)
        runtime, job, request, result = self.configured_runtime(
            executor_provider="codex", claude=claude, codex=codex
        )
        package = runtime.context_builder.build(
            "review-probe",
            job,
            request,
            result,
            runtime.verifier.verify(job, request, result),
        )
        evidence = package.available_evidence_refs[0]
        codex.result = ProviderExecutionResult(
            "succeeded",
            json.dumps(
                {
                    "decision": "PASS",
                    "reason": "Evidence supports completion",
                    "evidence_refs": [evidence],
                }
            ),
            "",
            0,
        )
        review_run = runtime.run(job, request, result)
        self.assertTrue(review_run.result.same_provider_review)
        self.assertEqual(review_run.result.review_provider, "codex")
        self.assertEqual(
            review_run.result.fallback_reason,
            "different_reviewer_provider_unavailable",
        )

    def test_n_cross_provider_review_is_preferred(self) -> None:
        claude = FakeAdapter("claude", available=True)
        codex = FakeAdapter("codex", available=True)
        runtime, job, request, result = self.configured_runtime(
            executor_provider="claude", claude=claude, codex=codex
        )
        package = runtime.context_builder.build(
            "review-probe",
            job,
            request,
            result,
            runtime.verifier.verify(job, request, result),
        )
        codex.result = ProviderExecutionResult(
            "succeeded",
            json.dumps(
                {
                    "decision": "PASS",
                    "reason": "Different provider verified the evidence",
                    "evidence_refs": [package.available_evidence_refs[0]],
                }
            ),
            "",
            0,
        )
        review_run = runtime.run(job, request, result)
        self.assertEqual(review_run.result.review_provider, "codex")
        self.assertFalse(review_run.result.same_provider_review)
        self.assertEqual(codex.calls, 1)
        self.assertEqual(claude.calls, 0)

    def test_o_high_risk_same_provider_escalates(self) -> None:
        runtime, job, request, result = self.configured_runtime(
            executor_provider="codex",
            claude=FakeAdapter("claude", available=False),
            codex=FakeAdapter("codex", available=True),
            risk_level="high",
        )
        review_run = runtime.run(job, request, result)
        self.assertEqual(review_run.result.decision, "NEEDS_HUMAN")
        self.assertEqual(
            review_run.result.error_category, "independent_reviewer_unavailable"
        )


class WorkerReviewTests(ReviewTestHarness, unittest.TestCase):
    def run_worker_decision(
        self,
        decision: str,
        *,
        max_attempts: int = 2,
        review_required: bool = True,
        approval_required: bool = False,
    ) -> tuple[dict[str, object], object, FakeReviewer]:
        created = self.runtime.create(
            self.payload(
                max_attempts=max_attempts,
                review_required=review_required,
                risk_level=("approval_required" if approval_required else "low"),
                approval_status=("required" if approval_required else "not_required"),
            )
        )
        if approval_required:
            approvals = ApprovalRuntime(
                self.runtime,
                FileApprovalStore(self.root / "approvals"),
            )
            requested = approvals.request_execution(
                str(created["job_id"]), reason="Initial execution requires approval"
            )
            approvals.resolve(
                requested.request.approval_id,
                decision="APPROVED",
                decided_by="test-owner",
            )
        else:
            self.runtime.enqueue(str(created["job_id"]))
        reviewer = FakeReviewer(decision)
        worker = Worker(
            self.runtime,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            LocalExecutor("success", clock=lambda: "2026-09-22T12:00:01Z"),
            self.execution_store,
            reviewer_runtime=self.reviewer_runtime(reviewer),
            id_factory=lambda: "execution-worker-review-001",
        )
        return created, worker.run_once(), reviewer

    def test_p_worker_pass_completes(self) -> None:
        created, outcome, _ = self.run_worker_decision("PASS")
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(outcome.review["decision"], "PASS")
        self.assertEqual(self.runtime.show(str(created["job_id"]))["status"], "completed")

    def test_q_worker_fail_terminates_attempt(self) -> None:
        created, outcome, _ = self.run_worker_decision("FAIL")
        failed = self.runtime.show(str(created["job_id"]))
        self.assertEqual(outcome.status, "failed")
        self.assertEqual(failed["error"]["code"], "review_failed")
        self.assertFalse(failed["error"]["retryable"])

    def test_r_retry_within_budget_creates_queued_child(self) -> None:
        created, outcome, _ = self.run_worker_decision("RETRY", max_attempts=2)
        self.assertEqual(outcome.status, "queued")
        self.assertIsNotNone(outcome.retry_job_id)
        retry = self.runtime.show(str(outcome.retry_job_id))
        self.assertEqual(retry["attempt"], 2)
        self.assertEqual(retry["parent_job_id"], created["job_id"])
        self.assertEqual(retry["status"], "queued")

    def test_s_retry_exhaustion_fails_without_child(self) -> None:
        created, outcome, _ = self.run_worker_decision("RETRY", max_attempts=1)
        failed = self.runtime.show(str(created["job_id"]))
        self.assertEqual(outcome.status, "failed")
        self.assertIsNone(outcome.retry_job_id)
        self.assertEqual(failed["error"]["code"], "review_retry_requested")
        self.assertEqual(outcome.retry_decision["decision"], "REPLAN_REQUIRED")
        self.assertEqual(outcome.retry_decision["reason_code"], "local_attempt_limit_exhausted")

    def test_t_needs_human_enters_existing_waiting_boundary(self) -> None:
        created, outcome, _ = self.run_worker_decision("NEEDS_HUMAN")
        waiting = self.runtime.show(str(created["job_id"]))
        self.assertEqual(outcome.status, "waiting_approval")
        self.assertEqual(waiting["approval_status"], "requested")
        self.assertEqual(outcome.approval["status"], "PENDING")
        self.assertTrue(
            any(
                reference["ref"]
                == f"runtime-approval:{outcome.approval['approval_id']}"
                for reference in waiting["output_refs"]
            )
        )

    def test_u_non_review_job_does_not_call_reviewer(self) -> None:
        created, outcome, reviewer = self.run_worker_decision(
            "FAIL", review_required=False
        )
        self.assertEqual(outcome.status, "completed")
        self.assertEqual(reviewer.calls, [])
        self.assertIsNone(outcome.review)
        self.assertEqual(self.runtime.show(str(created["job_id"]))["status"], "completed")

    def test_v_executor_success_words_cannot_self_authorize(self) -> None:
        created, outcome, _ = self.run_worker_decision("FAIL")
        self.assertEqual(outcome.result["status"], "succeeded")
        self.assertEqual(outcome.review["decision"], "FAIL")
        self.assertEqual(self.runtime.show(str(created["job_id"]))["status"], "failed")

    def test_w_retry_after_approval_requires_fresh_scoped_approval(self) -> None:
        _, outcome, _ = self.run_worker_decision(
            "RETRY", max_attempts=2, approval_required=True
        )
        retry = self.runtime.show(str(outcome.retry_job_id))
        self.assertEqual(outcome.status, "waiting_approval")
        self.assertEqual(retry["approval_status"], "requested")
        self.assertEqual(outcome.approval["status"], "PENDING")
        self.assertEqual(outcome.approval["requested_action"], "EXECUTE_JOB")


class ReviewCliAndIgnoreTests(ReviewTestHarness, unittest.TestCase):
    def test_w_review_cli_list_and_show_are_compact(self) -> None:
        job, request, result = self.prepare_execution()
        review_run = self.reviewer_runtime(FakeReviewer("PASS")).run(
            job, request, result
        )
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = run(
                [
                    "--execution-root",
                    str(self.execution_root),
                    "review",
                    "show",
                    review_run.result.review_id,
                ]
            )
        self.assertEqual(exit_code, 0)
        shown = json.loads(output.getvalue())
        self.assertEqual(shown["decision"], "PASS")
        self.assertNotIn("package", shown)

    def test_x_review_artifacts_are_git_ignored(self) -> None:
        candidate = (
            REPOSITORY_ROOT
            / "runtime"
            / "state"
            / "executions"
            / "reviews"
            / "review-probe.review.json"
        )
        result = subprocess.run(
            ["git", "check-ignore", str(candidate)],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
