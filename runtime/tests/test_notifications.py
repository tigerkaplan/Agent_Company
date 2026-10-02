from __future__ import annotations

from runtime.tests.contract_fixtures import declare_fixture_contract, execute_fixture

import json
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from integrations.telegram.client import TelegramApiError
from integrations.telegram.formatter import TelegramNotificationFormatter
from integrations.telegram.notifications import TelegramNotificationTransport
from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime
from runtime.notifications.emitter import RuntimeNotificationEmitter
from runtime.notifications.models import (
    NotificationEvent,
    NotificationSeverity,
    NotificationType,
)
from runtime.notifications.service import (
    NotificationDestination,
    NotificationService,
)
from runtime.notifications.store import FileNotificationStore
from runtime.remote.config import RemoteRuntimeConfig, RemoteUser


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXED_TIME = "2026-09-23T14:00:00Z"


class FakeTelegramClient:
    def __init__(self, *, failing: bool = False) -> None:
        self.failing = failing
        self.sent: list[dict[str, object]] = []

    def send_message(self, *, chat_id: int, text: str) -> dict[str, object]:
        self.sent.append({"chat_id": chat_id, "text": text})
        if self.failing:
            raise TelegramApiError("simulated Telegram outage")
        return {"message_id": len(self.sent), "chat": {"id": chat_id}}


class FailingTransport:
    channel = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def destinations_for(self, target_human_identity: str):
        return [NotificationDestination("fake", target_human_identity)]

    def send(self, event: NotificationEvent, destination: NotificationDestination):
        self.calls += 1
        raise RuntimeError("simulated transport outage")


class NotificationRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = FakeTelegramClient()
        self.config = RemoteRuntimeConfig(
            users=(
                RemoteUser("telegram", "123456789", "owner-human", True),
                RemoteUser("telegram", "222222222", "disabled-human", False),
                RemoteUser("local_test", "owner", "owner-human", True),
            ),
            notification_targets=("owner-human",),
        )
        self.store = FileNotificationStore(self.root / "notifications")
        self.transport = TelegramNotificationTransport(
            client=self.client,
            config=self.config,
        )
        self.service = NotificationService(
            self.store,
            (self.transport,),
            clock=lambda: FIXED_TIME,
        )
        self.emitter = RuntimeNotificationEmitter(
            self.service,
            self.config.notification_targets,
            clock=lambda: FIXED_TIME,
        )
        self.jobs = JobRuntime(
            self.root / "jobs",
            clock=lambda: FIXED_TIME,
            id_factory=lambda: "job-notification-test",
            notification_emitter=self.emitter,
        )
        self.approval_store = FileApprovalStore(self.root / "approvals")
        self.approvals = ApprovalRuntime(
            self.jobs,
            self.approval_store,
            clock=lambda: FIXED_TIME,
            notification_emitter=self.emitter,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Run a bounded notification test",
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
            "created_by": "notification-test",
        }
        value.update(overrides)
        return declare_fixture_contract(value)

    def event(
        self,
        source_id: str = "job-event-test",
        *,
        target: str = "owner-human",
        summary: str = "Bounded notification summary.",
        metadata: dict[str, object] | None = None,
    ) -> NotificationEvent:
        return NotificationEvent.create(
            notification_type=NotificationType.JOB_COMPLETED,
            created_at=FIXED_TIME,
            target_human_identity=target,
            source_type="job",
            source_id=source_id,
            severity=NotificationSeverity.INFO,
            title="Job completed",
            summary=summary,
            metadata=metadata or {"task_class": "operations"},
        )

    def running_job(self) -> dict[str, object]:
        created = self.jobs.create(self.payload())
        self.jobs.enqueue(str(created["job_id"]))
        running = self.jobs.claim()
        assert running is not None
        return running

    def test_a_approval_request_notification_is_created(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        run_result = self.approvals.request_execution(
            str(job["job_id"]), reason="Explicit execution approval is required"
        )

        record = self.store.list()[0]
        event = record["notification"]
        self.assertEqual(event["notification_type"], "APPROVAL_REQUESTED")
        self.assertEqual(event["approval_id"], run_result.request.approval_id)
        self.assertEqual(
            event["authorization_fingerprint"],
            run_result.request.authorization_fingerprint,
        )

    def test_a2_approval_approved_notification_is_bounded(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        pending = self.approvals.request_execution(
            str(job["job_id"]), reason="Approval resolution notification"
        )
        resolved = self.approvals.resolve(
            pending.request.approval_id,
            decision="APPROVED",
            decided_by="owner-human",
        )
        events = [record["notification"] for record in self.store.list()]
        approved = next(
            event for event in events if event["notification_type"] == "APPROVAL_APPROVED"
        )
        self.assertEqual(resolved["approval"]["status"], "APPROVED")
        self.assertEqual(approved["authorization_fingerprint"], None)
        self.assertEqual(approved["metadata"]["decided_by"], "owner-human")

    def test_a3_approval_rejected_notification_is_created(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        pending = self.approvals.request_execution(
            str(job["job_id"]), reason="Approval rejection notification"
        )
        resolved = self.approvals.resolve(
            pending.request.approval_id,
            decision="REJECTED",
            decided_by="owner-human",
        )
        event_types = {
            record["notification"]["notification_type"] for record in self.store.list()
        }
        self.assertEqual(resolved["approval"]["status"], "REJECTED")
        self.assertIn("APPROVAL_REJECTED", event_types)

    def test_a4_resolution_delivery_failure_does_not_change_approval(self) -> None:
        emitter = self._emitter_for_client(FakeTelegramClient(failing=True))
        jobs = JobRuntime(
            self.root / "resolution-failed-jobs",
            clock=lambda: FIXED_TIME,
            id_factory=lambda: "job-resolution-failed",
            notification_emitter=emitter,
        )
        approvals = ApprovalRuntime(
            jobs,
            FileApprovalStore(self.root / "resolution-failed-approvals"),
            clock=lambda: FIXED_TIME,
            notification_emitter=emitter,
        )
        job = jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        pending = approvals.request_execution(
            str(job["job_id"]), reason="Delivery failure must be isolated"
        )
        resolved = approvals.resolve(
            pending.request.approval_id,
            decision="APPROVED",
            decided_by="owner-human",
        )
        self.assertEqual(resolved["approval"]["status"], "APPROVED")
        self.assertEqual(
            approvals.show(pending.request.approval_id)["approval"]["status"],
            "APPROVED",
        )

    def test_a5_duplicate_resolution_notification_is_suppressed(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        pending = self.approvals.request_execution(
            str(job["job_id"]), reason="Duplicate notification test"
        )
        resolved = self.approvals.resolve(
            pending.request.approval_id,
            decision="APPROVED",
            decided_by="owner-human",
        )
        self.emitter.approval_resolved(resolved["approval"], resolved["job"])
        approved_records = [
            record
            for record in self.store.list()
            if record["notification"]["notification_type"] == "APPROVAL_APPROVED"
        ]
        self.assertEqual(len(approved_records), 1)
        self.assertEqual(len(self.client.sent), 2)

    def test_b_job_completed_notification_is_created(self) -> None:
        completed = execute_fixture(self.jobs, self.running_job())

        event = self.store.list()[0]["notification"]
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(event["notification_type"], "JOB_COMPLETED")
        self.assertEqual(event["source_id"], completed["job_id"])

    def test_c_job_failed_notification_is_created(self) -> None:
        failed = self.jobs.fail(
            str(self.running_job()["job_id"]),
            code="provider_failed",
            message="Provider failed safely",
            retryable=True,
        )

        event = self.store.list()[0]["notification"]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(event["notification_type"], "JOB_FAILED")
        self.assertEqual(event["metadata"]["failure_category"], "provider_failed")

    def test_d_runtime_error_notification_is_created(self) -> None:
        self.emitter.runtime_error(
            source_type="scheduler",
            source_id="scheduler-test",
            error_code="schedule_tick_error",
        )

        event = self.store.list()[0]["notification"]
        self.assertEqual(event["notification_type"], "RUNTIME_ERROR")
        self.assertEqual(event["metadata"]["error_code"], "schedule_tick_error")

    def test_e_enabled_mapping_resolves_correct_human_destination(self) -> None:
        result = self.service.emit(self.event())

        self.assertEqual(result.status, "delivered")
        self.assertEqual(self.client.sent[0]["chat_id"], 123456789)

    def test_f_unknown_destination_fails_safely_without_send(self) -> None:
        result = self.service.emit(self.event(target="unknown-human"))

        self.assertEqual(result.status, "no_destination")
        self.assertEqual(self.client.sent, [])
        self.assertEqual(self.store.list()[0]["event_status"], "created")

    def test_g_disabled_mapping_receives_nothing(self) -> None:
        result = self.service.emit(self.event(target="disabled-human"))

        self.assertEqual(result.status, "no_destination")
        self.assertEqual(self.client.sent, [])

    def test_h_duplicate_notification_is_not_delivered_twice(self) -> None:
        event = self.event()
        first = self.service.emit(event)
        second = self.service.emit(event)

        self.assertEqual(first.delivered, 1)
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(len(self.client.sent), 1)

    def test_i_restart_preserves_delivery_dedupe(self) -> None:
        event = self.event()
        self.service.emit(event)
        restarted = NotificationService(
            FileNotificationStore(self.root / "notifications"),
            (self.transport,),
            clock=lambda: FIXED_TIME,
        )

        result = restarted.emit(event)

        self.assertEqual(result.status, "duplicate")
        self.assertEqual(len(self.client.sent), 1)

    def test_j_telegram_failure_does_not_alter_completed_job(self) -> None:
        failing_client = FakeTelegramClient(failing=True)
        emitter = self._emitter_for_client(failing_client)
        jobs = JobRuntime(
            self.root / "failed-send-jobs",
            clock=lambda: FIXED_TIME,
            id_factory=lambda: "job-failed-send",
            notification_emitter=emitter,
        )
        job = jobs.create(self.payload())
        jobs.enqueue(str(job["job_id"]))
        running = jobs.claim()

        completed = execute_fixture(jobs, running)

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(jobs.show(str(job["job_id"]))["status"], "completed")
        self.assertEqual(self._record_for("job-failed-send")["status"], "failed")

    def test_k_telegram_failure_does_not_alter_pending_approval(self) -> None:
        emitter = self._emitter_for_client(FakeTelegramClient(failing=True))
        jobs = JobRuntime(
            self.root / "approval-failed-send-jobs",
            clock=lambda: FIXED_TIME,
            id_factory=lambda: "job-approval-failed-send",
            notification_emitter=emitter,
        )
        approvals = ApprovalRuntime(
            jobs,
            FileApprovalStore(self.root / "approval-failed-send"),
            clock=lambda: FIXED_TIME,
            notification_emitter=emitter,
        )
        job = jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )

        run_result = approvals.request_execution(
            str(job["job_id"]), reason="Approval remains authoritative"
        )

        self.assertEqual(
            approvals.show(run_result.request.approval_id)["approval"]["status"],
            "PENDING",
        )
        self.assertEqual(run_result.job["status"], "waiting_approval")

    def test_l_approval_notification_does_not_approve(self) -> None:
        job = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        run_result = self.approvals.request_execution(
            str(job["job_id"]), reason="Explicit command still required"
        )

        approval = self.approvals.show(run_result.request.approval_id)["approval"]
        self.assertEqual(approval["status"], "PENDING")
        self.assertIn("/approve", str(self.client.sent[0]["text"]))
        self.assertIn("does not grant approval", str(self.client.sent[0]["text"]))

    def test_m_successful_send_records_delivery_evidence(self) -> None:
        event = self.event()
        self.service.emit(event)

        record = self.store.load(event.notification_id)
        assert record is not None
        delivery = record["deliveries"]["telegram:123456789"]
        self.assertEqual(delivery["status"], "delivered")
        self.assertEqual(delivery["attempt_count"], 1)
        self.assertEqual(delivery["transport_ref"], {"message_id": 1})

    def test_n_failed_delivery_retry_is_bounded(self) -> None:
        transport = FailingTransport()
        service = NotificationService(
            FileNotificationStore(self.root / "bounded-retry"),
            (transport,),
            max_delivery_attempts=3,
            clock=lambda: FIXED_TIME,
        )
        event = self.event()

        results = [service.emit(event) for _ in range(5)]

        self.assertEqual(transport.calls, 3)
        self.assertEqual(results[-1].status, "duplicate")
        record = service.store.load(event.notification_id)
        assert record is not None
        self.assertEqual(record["deliveries"]["fake:owner-human"]["attempt_count"], 3)

    def test_o_runtime_error_cooldown_prevents_notification_storm(self) -> None:
        for _ in range(20):
            self.emitter.runtime_error(
                source_type="scheduler",
                source_id="scheduler-test",
                error_code="schedule_tick_error",
            )

        self.assertEqual(len(self.client.sent), 1)
        self.assertEqual(len(self.store.list()), 1)

    def test_p_secrets_are_absent_from_notification_state(self) -> None:
        token = "123456:abcdefghijklmnopqrstuvwxyzABCDE"
        event = self.event(
            summary=f"Telegram token {token} API_KEY=top-secret",
            metadata={
                "task_class": "operations",
                "bot_token": token,
                "environment": {"API_KEY": "top-secret"},
            },
        )
        self.service.emit(event)

        serialized = json.dumps(self.store.list(), sort_keys=True)
        self.assertNotIn(token, serialized)
        self.assertNotIn("top-secret", serialized)
        self.assertIn("REDACTED", serialized)

    def test_q_formatter_output_is_bounded(self) -> None:
        formatter = TelegramNotificationFormatter(max_chars=256)
        event = self.event(summary="x" * 1200)

        output = formatter.format(event)

        self.assertLessEqual(len(output), 256)
        self.assertTrue(output.endswith("[response truncated]"))

    def test_r_generated_notification_state_is_git_ignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "runtime/state/notifications/probe.json"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_s_preview_cli_does_not_construct_live_telegram_client(self) -> None:
        state_root = self.root / "preview-state"
        with patch(
            "runtime.cli.__main__.TelegramBotApiClient",
            side_effect=AssertionError("live client must not be constructed"),
        ):
            with redirect_stdout(io.StringIO()):
                exit_code = run(
                    [
                        "--notification-state-root",
                        str(state_root),
                        "notification",
                        "test",
                        "--target-human",
                        "owner-human",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertFalse(state_root.exists())

    def test_t_schema_fields_match_canonical_event(self) -> None:
        schema = json.loads(
            (REPOSITORY_ROOT / "schemas" / "notification-event.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(set(schema["required"]), set(self.event().to_dict()))
        self.assertEqual(
            set(schema["properties"]["notification_type"]["enum"]),
            {item.value for item in NotificationType},
        )

    def _emitter_for_client(
        self, client: FakeTelegramClient
    ) -> RuntimeNotificationEmitter:
        service = NotificationService(
            self.store,
            (TelegramNotificationTransport(client=client, config=self.config),),
            clock=lambda: FIXED_TIME,
        )
        return RuntimeNotificationEmitter(
            service,
            self.config.notification_targets,
            clock=lambda: FIXED_TIME,
        )

    def _record_for(self, source_id: str) -> dict[str, object]:
        for record in self.store.list():
            if record["notification"]["source_id"] == source_id:
                return next(iter(record["deliveries"].values()))
        self.fail(f"No notification record for {source_id}")


if __name__ == "__main__":
    unittest.main()
