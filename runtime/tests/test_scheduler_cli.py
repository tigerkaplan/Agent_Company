from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime


class SchedulerCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.jobs_root = self.root / "jobs"
        self.executions_root = self.root / "executions"
        self.schedules_root = self.root / "schedules"
        self.approvals_root = self.root / "approvals"
        self.scheduler_root = self.root / "scheduler-runtime"
        self.runtime = JobRuntime(self.jobs_root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def common(self) -> list[str]:
        return [
            "--state-root",
            str(self.jobs_root),
            "--execution-root",
            str(self.executions_root),
            "--schedule-root",
            str(self.schedules_root),
            "--approval-root",
            str(self.approvals_root),
            "--scheduler-runtime-root",
            str(self.scheduler_root),
        ]

    @staticmethod
    def payload() -> dict[str, object]:
        return {
            "task": "Run local CLI fixture",
            "task_class": "operations",
            "agent": "operations",
            "workflow": "operations",
            "capability": "operations_coordination",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": False,
            "max_attempts": 2,
            "input_refs": [],
            "output_refs": [],
            "created_by": "phase-6m-cli-test",
        }

    def invoke(self, *arguments: str) -> tuple[int, object, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run([*self.common, *arguments])
        output = stdout.getvalue()
        return code, json.loads(output) if output else None, stderr.getvalue()

    def test_job_schedule_reschedule_and_cancel(self) -> None:
        job = self.runtime.create(self.payload())
        code, scheduled, error = self.invoke(
            "job", "schedule", job["job_id"], "--delay-seconds", "600"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(scheduled["schedule_reason"], "scheduled")

        code, rescheduled, error = self.invoke(
            "job", "reschedule", job["job_id"], "--delay-seconds", "1200"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(rescheduled["schedule_reason"], "rescheduled")

        code, cancelled, error = self.invoke("job", "cancel", job["job_id"])
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(cancelled["status"], "cancelled")

    def test_scheduler_dry_run_does_not_execute_or_persist_state(self) -> None:
        job = self.runtime.create(self.payload())
        self.runtime.enqueue(job["job_id"])
        code, result, error = self.invoke("scheduler", "run-once", "--dry-run")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(self.runtime.show(job["job_id"])["status"], "queued")
        self.assertFalse((self.scheduler_root / "scheduler-state.json").exists())

    def test_scheduler_run_once_executes_one_local_job(self) -> None:
        first = self.runtime.create(self.payload())
        second = self.runtime.create({**self.payload(), "task": "second"})
        self.runtime.enqueue(first["job_id"])
        self.runtime.enqueue(second["job_id"])
        code, result, error = self.invoke("scheduler", "run-once")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(result["processed_count"], 1)
        states = {item["status"] for item in self.runtime.list()}
        self.assertEqual(states, {"completed", "queued"})

    def test_scheduler_status_list_due_and_stop_are_bounded(self) -> None:
        job = self.runtime.create(self.payload())
        self.runtime.enqueue(job["job_id"])
        code, due, error = self.invoke("scheduler", "list-due")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(due["eligible_jobs"], [job["job_id"]])

        code, status, error = self.invoke("scheduler", "status")
        self.assertEqual((code, error), (0, ""))
        self.assertFalse(status["running"])

        code, stopped, error = self.invoke("scheduler", "stop")
        self.assertEqual((code, error), (0, ""))
        self.assertFalse(stopped["stop_requested"])

    def test_scheduler_run_honours_max_cycles(self) -> None:
        code, result, error = self.invoke(
            "scheduler", "run", "--max-cycles", "1", "--poll-seconds", "0.01"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(result["reason"], "max_cycles_reached")
        self.assertEqual(len(result["cycles"]), 1)


if __name__ == "__main__":
    unittest.main()
