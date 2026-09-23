from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime.core.jobs import JobRuntime
from runtime.scheduler.dispatch import CanonicalDispatchAdapter, DispatchError
from runtime.scheduler.schedules import ScheduleRuntime, ScheduleRuntimeError


class FrozenClock:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class SequenceIds:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 1

    def __call__(self) -> str:
        result = f"{self.prefix}-{self.value:03d}"
        self.value += 1
        return result


class CrashAfterDispatch:
    def __init__(self, dispatcher: CanonicalDispatchAdapter) -> None:
        self.dispatcher = dispatcher

    def dispatch(self, schedule: dict[str, object], occurrence_key: str) -> dict[str, object]:
        self.dispatcher.dispatch(schedule, occurrence_key)
        raise DispatchError("Simulated crash after job persistence")


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repository"
        self.schedule_root = self.root / "state" / "schedules"
        self.job_root = self.root / "state" / "jobs"
        self.clock = FrozenClock("2026-03-01T12:00:00Z")
        self._create_canonical_fixture()
        self.schedules = ScheduleRuntime(
            self.schedule_root,
            clock=self.clock,
            id_factory=SequenceIds("schedule-test"),
        )
        self.jobs = JobRuntime(
            self.job_root,
            clock=self.clock,
            id_factory=SequenceIds("job-scheduled"),
        )
        self.dispatcher = CanonicalDispatchAdapter(self.jobs, self.repository)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def one_time_payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "name": "One-time operations report",
            "enabled": True,
            "schedule_type": "one_time",
            "task": "Prepare the scheduled operations report",
            "task_class": "operations",
            "recurrence": None,
            "next_run_at": "2026-03-01T11:00:00Z",
            "created_by": "human-owner",
            "input_refs": [],
        }
        value.update(overrides)
        return value

    @staticmethod
    def recurring_payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "name": "Recurring operations report",
            "enabled": True,
            "schedule_type": "recurring",
            "task": "Prepare the recurring operations report",
            "task_class": "operations",
            "recurrence": "hourly",
            "next_run_at": "2026-03-01T11:00:00Z",
            "created_by": "human-owner",
            "input_refs": [],
        }
        value.update(overrides)
        return value

    def test_a_create_one_time_schedule(self) -> None:
        schedule = self.schedules.create(self.one_time_payload())
        self.assertEqual(schedule["schedule_type"], "one_time")
        self.assertIsNone(schedule["recurrence"])
        self.assertTrue((self.schedule_root / f"{schedule['schedule_id']}.json").is_file())

    def test_b_create_recurring_schedule(self) -> None:
        schedule = self.schedules.create(self.recurring_payload())
        self.assertEqual(schedule["schedule_type"], "recurring")
        self.assertEqual(schedule["recurrence"], "hourly")

    def test_c_list_and_show_schedules(self) -> None:
        first = self.schedules.create(self.one_time_payload(name="First"))
        second = self.schedules.create(self.recurring_payload(name="Second"))
        self.assertEqual(
            [item["schedule_id"] for item in self.schedules.list()],
            [first["schedule_id"], second["schedule_id"]],
        )
        self.assertEqual(self.schedules.show(str(second["schedule_id"])), second)

    def test_d_disabled_schedule_does_not_fire(self) -> None:
        schedule = self.schedules.create(self.one_time_payload(enabled=False))
        outcome = self.schedules.tick(self.dispatcher)
        self.assertEqual(outcome["due_count"], 0)
        self.assertEqual(self.jobs.list(), [])
        self.assertFalse(self.schedules.show(str(schedule["schedule_id"]))["enabled"])

    def test_e_one_time_due_schedule_fires_once(self) -> None:
        schedule = self.schedules.create(self.one_time_payload())
        outcome = self.schedules.tick(self.dispatcher)
        updated = self.schedules.show(str(schedule["schedule_id"]))

        self.assertEqual(len(outcome["fired"]), 1)
        self.assertFalse(updated["enabled"])
        self.assertEqual(updated["last_run_at"], self.clock.value)
        self.assertIn("last_occurrence_key", updated)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_f_second_tick_does_not_duplicate_occurrence(self) -> None:
        self.schedules.create(self.one_time_payload())
        self.schedules.tick(self.dispatcher)
        second = self.schedules.tick(self.dispatcher)
        self.assertEqual(second["due_count"], 0)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_g_hourly_recurrence_calculates_next_occurrence(self) -> None:
        schedule = self.schedules.create(self.recurring_payload(recurrence="hourly"))
        self.schedules.tick(self.dispatcher)
        updated = self.schedules.show(str(schedule["schedule_id"]))
        self.assertEqual(updated["next_run_at"], "2026-03-01T12:00:00Z")

    def test_h_daily_recurrence_calculates_next_occurrence(self) -> None:
        schedule = self.schedules.create(
            self.recurring_payload(
                recurrence="daily",
                next_run_at="2026-03-01T09:30:00+00:00",
            )
        )
        self.schedules.tick(self.dispatcher)
        updated = self.schedules.show(str(schedule["schedule_id"]))
        self.assertEqual(updated["next_run_at"], "2026-03-02T09:30:00Z")

    def test_i_weekly_recurrence_calculates_next_occurrence(self) -> None:
        schedule = self.schedules.create(
            self.recurring_payload(
                recurrence="weekly",
                next_run_at="2026-02-23T08:00:00Z",
            )
        )
        self.schedules.tick(self.dispatcher)
        updated = self.schedules.show(str(schedule["schedule_id"]))
        self.assertEqual(updated["next_run_at"], "2026-03-02T08:00:00Z")

    def test_j_schedule_uses_canonical_routing_boundary(self) -> None:
        self.schedules.create(self.one_time_payload())
        self.schedules.tick(self.dispatcher)
        job = self.jobs.list()[0]
        self.assertEqual(job["agent"], "operations")
        self.assertEqual(job["workflow"], "operations")
        self.assertEqual(job["capability"], "operations_coordination")
        self.assertNotIn("skill", job)

    def test_k_schedule_does_not_choose_provider(self) -> None:
        schedule = self.schedules.create(self.one_time_payload())
        self.assertNotIn("provider", schedule)
        self.schedules.tick(self.dispatcher)
        self.assertNotIn("provider", self.jobs.list()[0])

    def test_l_schedule_does_not_imply_approval(self) -> None:
        self.schedules.create(self.one_time_payload())
        self.schedules.tick(self.dispatcher)
        job = self.jobs.list()[0]
        self.assertEqual(job["risk_level"], "approval_required")
        self.assertEqual(job["approval_status"], "requested")
        self.assertEqual(job["status"], "waiting_approval")
        self.assertNotIn("approval", job)

    def test_m_project_id_is_preserved(self) -> None:
        self.schedules.create(self.one_time_payload(project_id="brightshore"))
        self.schedules.tick(self.dispatcher)
        self.assertEqual(self.jobs.list()[0]["project_id"], "brightshore")

    def test_n_process_restart_avoids_duplicate_occurrence(self) -> None:
        schedule = self.schedules.create(self.one_time_payload())
        first = self.schedules.tick(CrashAfterDispatch(self.dispatcher))
        self.assertEqual(first["status"], "partial_failure")
        self.assertEqual(len(self.jobs.list()), 1)
        self.assertNotIn(
            "last_occurrence_key",
            self.schedules.show(str(schedule["schedule_id"])),
        )

        restarted_schedules = ScheduleRuntime(self.schedule_root, clock=self.clock)
        restarted_jobs = JobRuntime(self.job_root, clock=self.clock)
        restarted_dispatcher = CanonicalDispatchAdapter(restarted_jobs, self.repository)
        second = restarted_schedules.tick(restarted_dispatcher)

        self.assertEqual(second["status"], "ok")
        self.assertEqual(len(second["fired"]), 1)
        self.assertEqual(len(restarted_jobs.list()), 1)

    def test_o_malformed_schedule_is_rejected_safely(self) -> None:
        with self.assertRaisesRegex(ScheduleRuntimeError, "Invalid canonical schedule"):
            self.schedules.create(self.recurring_payload(recurrence="monthly"))
        with self.assertRaisesRegex(ScheduleRuntimeError, "timezone"):
            self.schedules.create(
                self.one_time_payload(next_run_at="2026-03-01T11:00:00")
            )
        self.assertEqual(self.schedules.list(), [])

    def test_p_future_schedule_does_not_fire_early(self) -> None:
        self.schedules.create(
            self.one_time_payload(next_run_at="2026-03-01T12:00:01Z")
        )
        outcome = self.schedules.tick(self.dispatcher)
        self.assertEqual(outcome["due_count"], 0)
        self.assertEqual(self.jobs.list(), [])

    def test_unresolved_task_class_records_error_without_advancing(self) -> None:
        payload = self.one_time_payload()
        payload.pop("task_class")
        schedule = self.schedules.create(payload)

        outcome = self.schedules.tick(self.dispatcher)
        updated = self.schedules.show(str(schedule["schedule_id"]))
        self.assertEqual(outcome["status"], "partial_failure")
        self.assertEqual(updated["last_error"]["code"], "dispatch_error")
        self.assertNotIn("last_occurrence_key", updated)
        self.assertEqual(self.jobs.list(), [])

    def test_enable_and_disable_schedule(self) -> None:
        schedule = self.schedules.create(self.one_time_payload())
        disabled = self.schedules.disable(str(schedule["schedule_id"]))
        enabled = self.schedules.enable(str(schedule["schedule_id"]))
        self.assertFalse(disabled["enabled"])
        self.assertTrue(enabled["enabled"])

    def test_secret_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(ScheduleRuntimeError, "forbidden"):
            self.schedules.create(
                self.one_time_payload(metadata={"nested": {"accessToken": "do-not-store"}})
            )

    def test_routing_and_provider_metadata_is_rejected(self) -> None:
        for key in ("provider", "agent", "skill", "workflow", "capability", "risk_level"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ScheduleRuntimeError, "forbidden"):
                    self.schedules.create(
                        self.one_time_payload(metadata={"routing": {key: "forbidden"}})
                    )

    def _create_canonical_fixture(self) -> None:
        files = {
            "orchestrator/workflows/operations.yaml": (
                "workflow: operations\n"
                "initial_agent: operations\n"
            ),
            "orchestrator/routing/providers.yaml": (
                "capability_resolution:\n"
                "  task_class_defaults:\n"
                "    operations: operations_coordination\n"
            ),
        }
        for relative, content in files.items():
            path = self.repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


class SchedulerCliTests(unittest.TestCase):
    def test_scheduler_cli_smoke(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            schedule_root = temporary_path / "schedules"
            job_root = temporary_path / "jobs"
            approval_root = temporary_path / "approvals"
            input_path = temporary_path / "schedule.json"
            input_path.write_text(
                json.dumps(
                    SchedulerTests.one_time_payload(
                        next_run_at="2020-01-01T00:00:00Z"
                    )
                ),
                encoding="utf-8",
            )
            created = self._run_cli(
                repository,
                schedule_root,
                job_root,
                approval_root,
                "create",
                "--from",
                str(input_path),
            )
            listed = self._run_cli(
                repository, schedule_root, job_root, approval_root, "list"
            )
            ticked = self._run_cli(
                repository, schedule_root, job_root, approval_root, "tick"
            )

            self.assertEqual(listed[0]["schedule_id"], created["schedule_id"])
            self.assertEqual(ticked["status"], "ok")
            self.assertEqual(len(ticked["fired"]), 1)
            jobs = list(job_root.glob("*.json"))
            self.assertEqual(len(jobs), 1)

    @staticmethod
    def _run_cli(
        repository: Path,
        schedule_root: Path,
        job_root: Path,
        approval_root: Path,
        command: str,
        *arguments: str,
    ) -> object:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "runtime.cli",
                "--state-root",
                str(job_root),
                "--schedule-root",
                str(schedule_root),
                "--approval-root",
                str(approval_root),
                "scheduler",
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


class SchedulerGitIgnoreTests(unittest.TestCase):
    def test_q_scheduler_state_is_git_ignored(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--",
                "runtime/state/schedules/schedule-example.json",
            ],
            cwd=repository,
            check=False,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
