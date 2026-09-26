from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.executors.local import LocalExecutor
from runtime.review.models import ReviewResult, ReviewRun
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker


class RaisingExecutor:
    def execute(self, request: object) -> object:
        raise ValueError("SECRET_TOKEN_MUST_NOT_BE_PERSISTED")


class StaticResultExecutor:
    supported_execution_modes = frozenset({"READ_ONLY"})

    def __init__(self, status: str) -> None:
        self.status = status

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        common = {
            "execution_id": request.execution_id,
            "job_id": request.job_id,
            "status": self.status,
            "summary": f"Canonical {self.status} result",
            "error": None,
            "provider": None,
            "started_at": "2026-02-01T00:00:00Z",
            "completed_at": "2026-02-01T00:00:01Z",
        }
        if self.status == "failed":
            common.update(
                summary=None,
                error={"code": "retryable_failure", "message": "Retryable metadata only", "retryable": True},
            )
        elif self.status == "blocked":
            common["blockers"] = (
                {"code": "dependency_missing", "message": "Dependency missing", "retryable": True, "requires_human": False},
            )
        elif self.status == "needs_review":
            common["evidence"] = (
                {"kind": "observation", "status": "observed", "summary": "Work is ready for review"},
            )
        elif self.status == "needs_human":
            common["blockers"] = (
                {"code": "human_input_required", "message": "Human input is required", "retryable": False, "requires_human": True},
            )
        return ExecutionResult(**common)  # type: ignore[arg-type]


class RecordingReviewerRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        job: dict[str, object],
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> ReviewRun:
        self.calls += 1
        reference = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{result.execution_id}",
            "description": "Canonical execution record",
        }
        return ReviewRun(
            ReviewResult(
                review_id="review-needs-review-001",
                job_id=result.job_id,
                execution_id=result.execution_id,
                reviewer="test-reviewer",
                review_provider=None,
                same_provider_review=False,
                model_review_performed=False,
                decision="PASS",
                reason="Independent deterministic review passed",
                evidence_refs=(reference,),
                deterministic_checks=(),
                created_at="2026-02-01T00:00:02Z",
            ),
            {
                "ref_type": "review",
                "ref": "runtime-review:review-needs-review-001",
                "description": "Independent review result",
            },
        )


class DeterministicClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 2, 1, tzinfo=timezone.utc)

    def __call__(self) -> str:
        value = self.current.isoformat().replace("+00:00", "Z")
        self.current += timedelta(seconds=1)
        return value


class SequenceIds:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 1

    def __call__(self) -> str:
        result = f"{self.prefix}-{self.value:03d}"
        self.value += 1
        return result


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.job_root = self.root / "state" / "jobs"
        self.execution_root = self.root / "state" / "executions"
        self._create_canonical_fixture()
        self.runtime = JobRuntime(
            self.job_root,
            clock=DeterministicClock(),
            id_factory=SequenceIds("job-worker"),
        )
        self.approvals = ApprovalRuntime(
            self.runtime,
            FileApprovalStore(self.root / "state" / "approvals"),
            clock=self.runtime.clock,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Prepare a deterministic operations report",
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
            "created_by": "dispatcher",
        }
        value.update(overrides)
        return value

    def make_worker(self, mode: str = "success") -> tuple[Worker, LocalExecutor]:
        executor = LocalExecutor(mode, clock=DeterministicClock())
        worker = Worker(
            runtime=self.runtime,
            resolver=CanonicalReferenceResolver(self.repository),
            executor=executor,
            execution_store=FileExecutionStore(self.execution_root),
            clock=DeterministicClock(),
            id_factory=SequenceIds("execution-worker"),
        )
        return worker, executor

    def enqueue(self, **overrides: object) -> dict[str, object]:
        job = self.runtime.create(self.payload(**overrides))
        return self.runtime.enqueue(str(job["job_id"]))

    def test_a_queued_job_is_claimed_by_worker(self) -> None:
        queued = self.enqueue()
        worker, executor = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(outcome.job_id, queued["job_id"])
        self.assertIsNotNone(executor.last_request)
        self.assertEqual(self.runtime.show(str(queued["job_id"]))["status"], "completed")

    def test_b_no_queued_jobs_returns_no_work(self) -> None:
        worker, executor = self.make_worker()
        outcome = worker.run_once()
        self.assertEqual(outcome.to_dict(), {"status": "no_work"})
        self.assertIsNone(executor.last_request)

    def test_c_valid_job_produces_execution_request(self) -> None:
        queued = self.enqueue(input_refs=[{"ref_type": "message", "ref": "message:1"}])
        worker, executor = self.make_worker()
        worker.run_once()
        request = executor.last_request
        assert request is not None

        self.assertEqual(request.job_id, queued["job_id"])
        self.assertEqual(request.agent, queued["agent"])
        self.assertEqual(request.skill, queued["skill"])
        self.assertEqual(request.workflow, queued["workflow"])
        self.assertEqual(request.capability, queued["capability"])
        self.assertEqual(request.input_refs[0]["ref"], "message:1")
        self.assertTrue(request.context_refs)

    def test_c2_worker_propagates_canonical_dry_run_state(self) -> None:
        queued = self.enqueue(dry_run=True)
        worker, executor = self.make_worker()
        worker.run_once()
        request = executor.last_request
        assert request is not None

        self.assertTrue(queued["dry_run"])
        self.assertTrue(request.dry_run)
        execution = FileExecutionStore(self.execution_root).load(request.execution_id)
        assert execution.request is not None
        self.assertTrue(execution.request["dry_run"])
        self.assertTrue(execution.result.dry_run)

    def test_d_unresolved_provider_is_acceptable(self) -> None:
        self.enqueue()
        worker, executor = self.make_worker()
        outcome = worker.run_once()
        request = executor.last_request
        assert request is not None

        self.assertIsNone(request.provider)
        self.assertIsNone(outcome.result["provider"])
        self.assertEqual(outcome.status, "completed")

    def test_e_local_success_executor_persists_result(self) -> None:
        self.enqueue()
        worker, _ = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(outcome.result["status"], "succeeded")
        record = FileExecutionStore(self.execution_root).load(str(outcome.execution_id))
        self.assertEqual(record.result.to_dict(), outcome.result)
        self.assertIsNotNone(record.request)

    def test_f_local_failure_executor_fails_job_safely(self) -> None:
        queued = self.enqueue()
        worker, _ = self.make_worker("failure")
        outcome = worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"]["code"], "local_executor_failure")
        self.assertEqual(job["error"]["ref"]["ref"], f"runtime-execution:{outcome.execution_id}")

    def test_f2_result_retryability_is_not_job_retry_authority(self) -> None:
        queued = self.enqueue()
        worker = Worker(
            runtime=self.runtime,
            resolver=CanonicalReferenceResolver(self.repository),
            executor=StaticResultExecutor("failed"),
            execution_store=FileExecutionStore(self.execution_root),
            approval_runtime=self.approvals,
            clock=DeterministicClock(),
            id_factory=SequenceIds("execution-retry-metadata"),
        )
        outcome = worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertTrue(outcome.result["retryable"])
        self.assertFalse(job["error"]["retryable"])

    def test_f3_blocked_and_needs_human_remain_distinct_fail_closed_results(self) -> None:
        for status, expected_code in (
            ("blocked", "execution_blocked"),
            ("needs_human", "execution_needs_human"),
        ):
            with self.subTest(status=status):
                queued = self.enqueue()
                worker = Worker(
                    runtime=self.runtime,
                    resolver=CanonicalReferenceResolver(self.repository),
                    executor=StaticResultExecutor(status),
                    execution_store=FileExecutionStore(self.execution_root),
                    approval_runtime=self.approvals,
                    clock=DeterministicClock(),
                    id_factory=SequenceIds(f"execution-{status}"),
                )
                outcome = worker.run_once()
                job = self.runtime.show(str(queued["job_id"]))
                self.assertEqual(outcome.result["status"], status)
                self.assertEqual(job["status"], "failed")
                self.assertEqual(job["error"]["code"], expected_code)
                self.assertFalse(job["error"]["retryable"])
                self.assertEqual(job["approval_status"], "not_required")

    def test_g0_needs_review_enters_and_invokes_existing_reviewer_gate(self) -> None:
        queued = self.enqueue(review_required=False)
        reviewer = RecordingReviewerRuntime()
        worker = Worker(
            runtime=self.runtime,
            resolver=CanonicalReferenceResolver(self.repository),
            executor=StaticResultExecutor("needs_review"),
            execution_store=FileExecutionStore(self.execution_root),
            reviewer_runtime=reviewer,  # type: ignore[arg-type]
            approval_runtime=self.approvals,
            clock=DeterministicClock(),
            id_factory=SequenceIds("execution-needs-review"),
        )
        outcome = worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertEqual(reviewer.calls, 1)
        self.assertEqual(outcome.result["status"], "needs_review")
        self.assertEqual(job["status"], "completed")
        self.assertTrue(job["review_required"])

    def test_g_review_required_success_enters_reviewing(self) -> None:
        queued = self.enqueue(review_required=True)
        worker, _ = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(outcome.status, "reviewing")
        self.assertEqual(self.runtime.show(str(queued["job_id"]))["status"], "reviewing")

    def test_h_non_review_success_completes_via_lifecycle(self) -> None:
        queued = self.enqueue(review_required=False)
        worker, _ = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(outcome.status, "completed")
        self.assertEqual(self.runtime.show(str(queued["job_id"]))["status"], "completed")

    def test_i_approval_required_job_cannot_execute_without_approval(self) -> None:
        created = self.runtime.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Execution requires local approval"
        )
        assert approval.job is not None
        waiting = approval.job
        worker, executor = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(outcome.status, "no_work")
        self.assertIsNone(executor.last_request)
        self.assertEqual(waiting["status"], "waiting_approval")

    def test_j_approved_job_executes_after_valid_requeue(self) -> None:
        created = self.runtime.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Execution requires local approval"
        )
        approved = self.approvals.resolve(
            approval.request.approval_id,
            decision="APPROVED",
            decided_by="human-owner",
        )["job"]
        worker, executor = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(approved["status"], "queued")
        self.assertEqual(outcome.status, "completed")
        self.assertIsNotNone(executor.last_request)

    def test_k_missing_agent_reference_fails_safely(self) -> None:
        (self.repository / "agents" / "operations" / "ROLE.md").unlink()
        queued = self.enqueue()
        worker, executor = self.make_worker()
        outcome = worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertEqual(outcome.status, "failed")
        self.assertIsNone(executor.last_request)
        self.assertEqual(job["error"]["code"], "context_resolution_error")
        self.assertIn("role file is missing", job["error"]["message"])

    def test_l_missing_skill_reference_fails_safely(self) -> None:
        queued = self.enqueue(skill="missing-skill")
        worker, executor = self.make_worker()
        worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertIsNone(executor.last_request)
        self.assertEqual(job["status"], "failed")
        self.assertIn("Missing canonical skill", job["error"]["message"])

    def test_m_missing_workflow_reference_fails_safely(self) -> None:
        queued = self.enqueue(workflow="missing-workflow")
        worker, executor = self.make_worker()
        worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertIsNone(executor.last_request)
        self.assertEqual(job["status"], "failed")
        self.assertIn("Missing canonical workflow", job["error"]["message"])

    def test_n_capability_is_validated_against_canonical_routing(self) -> None:
        queued = self.enqueue(capability="testing")
        worker, executor = self.make_worker()
        worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertIsNone(executor.last_request)
        self.assertEqual(job["status"], "failed")
        self.assertIn("Missing canonical capability", job["error"]["message"])

    def test_o_project_id_resolves_ordered_refs_without_copying_state(self) -> None:
        self.enqueue(project_id="example-project")
        worker, executor = self.make_worker()
        worker.run_once()
        request = executor.last_request
        assert request is not None

        project_refs = [
            ref for ref in request.context_refs if ref["ref_type"] == "project_state"
        ]
        self.assertEqual(
            [Path(ref["ref"]).name for ref in project_refs],
            ["PROJECT_STATE.md", "HANDOFF.md", "metadata.yaml"],
        )
        self.assertNotIn("PRIVATE PROJECT CONTENT", json.dumps(request.to_dict()))

    def test_malformed_job_returns_explicit_worker_error(self) -> None:
        self.job_root.mkdir(parents=True)
        (self.job_root / "job-malformed.json").write_text("{not-json", encoding="utf-8")
        worker, executor = self.make_worker()
        outcome = worker.run_once()

        self.assertEqual(outcome.status, "worker_error")
        self.assertEqual(outcome.error["code"], "claim_error")
        self.assertIn("Could not read job file", outcome.error["message"])
        self.assertIsNone(executor.last_request)

    def test_executor_exception_details_are_not_persisted(self) -> None:
        queued = self.enqueue()
        worker = Worker(
            runtime=self.runtime,
            resolver=CanonicalReferenceResolver(self.repository),
            executor=RaisingExecutor(),
            execution_store=FileExecutionStore(self.execution_root),
            clock=DeterministicClock(),
            id_factory=SequenceIds("execution-raising"),
        )
        outcome = worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))
        record = FileExecutionStore(self.execution_root).load(str(outcome.execution_id))

        evidence = json.dumps(
            {"outcome": outcome.to_dict(), "job": job, "record": record.to_dict()}
        )
        self.assertEqual(outcome.status, "failed")
        self.assertNotIn("SECRET_TOKEN_MUST_NOT_BE_PERSISTED", evidence)
        self.assertIn("details were not persisted", job["error"]["message"])

    def test_project_read_order_cannot_escape_project_root(self) -> None:
        continuation = (
            self.repository
            / "orchestrator"
            / "workflows"
            / "project-continuation.yaml"
        )
        continuation.write_text(
            "workflow: project-continuation\n"
            "canonical_read_order:\n"
            "  - ../../outside-project.txt\n"
            "  - PROJECT_STATE.md\n",
            encoding="utf-8",
        )
        (self.repository / "shared" / "outside-project.txt").write_text(
            "SENSITIVE OUTSIDE PROJECT\n",
            encoding="utf-8",
        )
        queued = self.enqueue(project_id="example-project")
        worker, executor = self.make_worker()
        outcome = worker.run_once()
        job = self.runtime.show(str(queued["job_id"]))

        self.assertEqual(outcome.status, "failed")
        self.assertIsNone(executor.last_request)
        self.assertIn("escapes project root", job["error"]["message"])

    def test_q_worker_preserves_canonical_identity(self) -> None:
        queued = self.enqueue()
        identity_fields = ("task", "task_class", "agent", "skill", "workflow", "capability")
        before = {field: queued[field] for field in identity_fields}
        worker, _ = self.make_worker()
        worker.run_once()
        after_job = self.runtime.show(str(queued["job_id"]))
        after = {field: after_job[field] for field in identity_fields}

        self.assertEqual(after, before)

    def _create_canonical_fixture(self) -> None:
        files = {
            "orchestrator/routing/agents.yaml": (
                "canonical_agents:\n"
                "  operations:\n"
                "    role: ../../agents/operations/ROLE.md\n"
                "    guardrails: ../../agents/operations/GUARDRAILS.md\n"
            ),
            "orchestrator/routing/capabilities.yaml": (
                "capabilities:\n"
                "  operations_coordination:\n"
                "    description: Coordinate operations.\n"
            ),
            "orchestrator/workflows/operations.yaml": (
                "workflow: operations\n"
                "source: provider-neutral\n"
            ),
            "orchestrator/workflows/project-continuation.yaml": (
                "workflow: project-continuation\n"
                "canonical_read_order:\n"
                "  - PROJECT_STATE.md\n"
                "  - HANDOFF.md\n"
                "  - metadata.yaml\n"
            ),
            "agents/operations/ROLE.md": "# Operations Agent\n",
            "agents/operations/GUARDRAILS.md": "# Operations Guardrails\n",
            "skills/operations/report-builder/SKILL.md": "# Report Builder\n",
            "shared/projects/example-project/PROJECT_STATE.md": "PRIVATE PROJECT CONTENT\n",
            "shared/projects/example-project/HANDOFF.md": "# Handoff\n",
            "shared/projects/example-project/metadata.yaml": "project_id: example-project\n",
        }
        for relative, content in files.items():
            path = self.repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


class WorkerGitIgnoreTests(unittest.TestCase):
    def test_p_execution_artifacts_are_git_ignored(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--",
                "runtime/state/executions/execution-example.json",
            ],
            cwd=repository,
            check=False,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
