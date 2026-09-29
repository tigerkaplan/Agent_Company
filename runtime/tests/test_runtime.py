from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError


class DeterministicClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> str:
        value = self.current.isoformat().replace("+00:00", "Z")
        self.current += timedelta(seconds=1)
        return value


class DeterministicIds:
    def __init__(self) -> None:
        self.next_value = 1

    def __call__(self) -> str:
        value = f"job-test-{self.next_value:03d}"
        self.next_value += 1
        return value


class JobRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temporary.name) / "jobs"
        self.runtime = JobRuntime(
            self.state_root,
            clock=DeterministicClock(),
            id_factory=DeterministicIds(),
        )
        self.approvals = ApprovalRuntime(
            self.runtime,
            FileApprovalStore(Path(self.temporary.name) / "approvals"),
            clock=self.runtime.clock,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Prepare the weekly internal operations report",
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

    def create_running(self) -> dict[str, object]:
        created = self.runtime.create(self.payload())
        self.runtime.enqueue(str(created["job_id"]))
        claimed = self.runtime.claim()
        assert claimed is not None
        return claimed

    def test_a_create_job_persists_canonical_record(self) -> None:
        job = self.runtime.create(self.payload())

        self.assertEqual(job["status"], "created")
        self.assertEqual(job["attempt"], 1)
        self.assertEqual(job["created_at"], job["last_updated_at"])
        path = self.state_root / f"{job['job_id']}.json"
        self.assertTrue(path.is_file())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), job)

    def test_b_created_to_queued(self) -> None:
        job = self.runtime.create(self.payload())
        queued = self.runtime.enqueue(str(job["job_id"]))
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(queued["created_at"], job["created_at"])

    def test_c_queued_to_running(self) -> None:
        job = self.runtime.create(self.payload())
        self.runtime.enqueue(str(job["job_id"]))
        running = self.runtime.claim()
        self.assertIsNotNone(running)
        self.assertEqual(running["status"], "running")

    def test_d_running_to_completed(self) -> None:
        running = self.create_running()
        completed = self.runtime.complete(str(running["job_id"]))
        self.assertEqual(completed["status"], "completed")

    def test_e_completed_to_running_is_rejected(self) -> None:
        running = self.create_running()
        completed = self.runtime.complete(str(running["job_id"]))
        with self.assertRaisesRegex(
            JobRuntimeError, "Invalid lifecycle transition: completed -> running"
        ):
            self.runtime.transition(str(completed["job_id"]), "running")

    def create_waiting(self) -> tuple[dict[str, object], object]:
        created = self.runtime.create(
            self.payload(
                risk_level="approval_required",
                approval_status="required",
            )
        )
        approval = self.approvals.request_execution(
            str(created["job_id"]), reason="Explicit approval is required"
        )
        assert approval.job is not None
        return approval.job, approval.request

    def test_f_created_to_waiting_approval(self) -> None:
        waiting, approval = self.create_waiting()
        self.assertEqual(waiting["status"], "waiting_approval")
        self.assertEqual(waiting["approval_status"], "requested")
        self.assertEqual(approval.status, "PENDING")

    def test_g_waiting_approval_to_running_is_rejected(self) -> None:
        waiting, _ = self.create_waiting()
        with self.assertRaisesRegex(
            JobRuntimeError, "Invalid lifecycle transition: waiting_approval -> running"
        ):
            self.runtime.transition(str(waiting["job_id"]), "running")

    def test_h_waiting_approval_requires_explicit_approval_before_queue(self) -> None:
        waiting, approval = self.create_waiting()
        with self.assertRaisesRegex(JobRuntimeError, "resolved ApprovalRequest"):
            self.runtime.transition(str(waiting["job_id"]), "queued")

        resolved = self.approvals.resolve(
            approval.approval_id,
            decision="APPROVED",
            decided_by="human-owner",
        )
        approved = resolved["job"]
        self.assertEqual(approved["status"], "queued")
        self.assertEqual(approved["approval_status"], "approved")
        self.assertEqual(approved["approval"]["recorded_by"], "human-owner")

    def test_i_claim_is_fifo(self) -> None:
        first = self.runtime.create(self.payload(task="First task"))
        second = self.runtime.create(self.payload(task="Second task"))
        self.runtime.enqueue(str(first["job_id"]))
        self.runtime.enqueue(str(second["job_id"]))

        claimed = self.runtime.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["job_id"], first["job_id"])

    def test_j_failed_retry_creates_traceable_new_job(self) -> None:
        running = self.create_running()
        failed = self.runtime.fail(
            str(running["job_id"]),
            code="provider_unavailable",
            message="No execution provider is available",
        )
        retry = self.runtime.retry(str(failed["job_id"]))

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(self.runtime.show(str(failed["job_id"]))["status"], "failed")
        self.assertNotEqual(retry["job_id"], failed["job_id"])
        self.assertEqual(retry["parent_job_id"], failed["job_id"])
        self.assertEqual(retry["attempt"], failed["attempt"] + 1)
        self.assertEqual(retry["status"], "created")
        for field in ("agent", "workflow", "task_class", "capability"):
            self.assertEqual(retry[field], failed[field])

    def test_k_provider_may_remain_unresolved(self) -> None:
        job = self.runtime.create(self.payload())
        self.assertNotIn("provider", job)
        self.assertEqual(self.runtime.show(str(job["job_id"])), job)

    def test_approval_required_risk_cannot_claim_not_required_approval(self) -> None:
        with self.assertRaisesRegex(JobRuntimeError, "expected one of"):
            self.runtime.create(
                self.payload(
                    risk_level="approval_required",
                    approval_status="not_required",
                )
            )

    def test_retryable_metadata_does_not_replace_canonical_policy(self) -> None:
        running = self.create_running()
        failed = self.runtime.fail(
            str(running["job_id"]),
            code="invalid_authorization",
            retryable=True,
        )
        with self.assertRaisesRegex(JobRuntimeError, "authority_failure"):
            self.runtime.retry(str(failed["job_id"]))

    def test_schema_statuses_match_canonical_lifecycle(self) -> None:
        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "job.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]),
            set(self.runtime.lifecycle.statuses),
        )

    def test_review_required_job_must_pass_through_reviewing(self) -> None:
        created = self.runtime.create(self.payload(review_required=True))
        self.runtime.enqueue(str(created["job_id"]))
        running = self.runtime.claim()
        assert running is not None

        with self.assertRaisesRegex(JobRuntimeError, "only from: reviewing"):
            self.runtime.complete(str(running["job_id"]))

        reviewing = self.runtime.transition(str(running["job_id"]), "reviewing")
        completed = self.runtime.complete(str(reviewing["job_id"]))
        self.assertEqual(completed["status"], "completed")


class GitIgnoreTests(unittest.TestCase):
    def test_l_generated_runtime_state_is_ignored_by_git(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--",
                "runtime/state/jobs/example-job.json",
            ],
            cwd=repository,
            check=False,
        )
        self.assertEqual(result.returncode, 0)


class CliTests(unittest.TestCase):
    def test_cli_create_enqueue_claim_flow(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            state_root = temporary_path / "jobs"
            input_path = temporary_path / "input.json"
            input_path.write_text(
                json.dumps(JobRuntimeTests.payload()),
                encoding="utf-8",
            )

            created = self.run_cli(
                repository,
                state_root,
                "create",
                "--from",
                str(input_path),
            )
            job_id = created["job_id"]
            queued = self.run_cli(repository, state_root, "enqueue", job_id)
            claimed = self.run_cli(repository, state_root, "claim")

            self.assertEqual(queued["status"], "queued")
            self.assertEqual(claimed["status"], "running")
            self.assertEqual(claimed["job_id"], job_id)

    def test_cli_worker_run_once_smoke(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            state_root = temporary_path / "jobs"
            execution_root = temporary_path / "executions"
            input_path = temporary_path / "input.json"
            input_path.write_text(
                json.dumps(JobRuntimeTests.payload()),
                encoding="utf-8",
            )
            created = self.run_cli(
                repository,
                state_root,
                "create",
                "--from",
                str(input_path),
            )
            self.run_cli(repository, state_root, "enqueue", created["job_id"])

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runtime.cli",
                    "--state-root",
                    str(state_root),
                    "--execution-root",
                    str(execution_root),
                    "worker",
                    "run-once",
                    "--executor",
                    "local-success",
                ],
                cwd=repository,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr)
            outcome = json.loads(result.stdout)

            self.assertEqual(outcome["status"], "completed")
            self.assertEqual(outcome["job_id"], created["job_id"])
            self.assertTrue(list(execution_root.glob("*.json")))

    def test_cli_create_dry_run_serializes_job_and_controlled_scope(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            state_root = temporary_path / "jobs"
            target = temporary_path / "target"
            target.mkdir()
            input_path = temporary_path / "input.json"
            payload = JobRuntimeTests.payload(
                task="Preview a controlled write",
                task_class="software",
                agent="software",
                workflow="software",
                capability="software_implementation",
                risk_level="approval_required",
                approval_status="required",
                review_required=True,
                execution_mode="CONTROLLED_WRITE",
                execution_scope={
                    "project_root": str(target),
                    "allowed_paths": ["src"],
                    "forbidden_paths": [],
                    "write_mode": "CREATE_OR_MODIFY",
                    "max_changed_files": 4,
                    "max_artifact_bytes": 65536,
                    "allow_tests": False,
                    "allow_git_reads": False,
                    "allow_protected_paths": False,
                },
            )
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            created = self.run_cli(
                repository,
                state_root,
                "create",
                "--from",
                str(input_path),
                "--dry-run",
            )

            self.assertTrue(created["dry_run"])
            self.assertTrue(created["execution_scope"]["dry_run"])

    @staticmethod
    def run_cli(
        repository: Path,
        state_root: Path,
        command: str,
        *arguments: str,
    ) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "runtime.cli",
                "--state-root",
                str(state_root),
                "job",
                command,
                *arguments,
            ],
            cwd=repository,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
