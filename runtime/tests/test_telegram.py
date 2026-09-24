from __future__ import annotations

import io
import json
import os
import socket
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from integrations.telegram.client import (
    TELEGRAM_API_ORIGIN,
    TelegramApiError,
    TelegramBotApiClient,
)
from integrations.telegram.formatter import TelegramResultFormatter
from integrations.telegram.parser import TelegramParseError, TelegramUpdateParser
from integrations.telegram.state import TelegramStateStore
from integrations.telegram.transport import TelegramTransport
from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime
from runtime.remote.config import RemoteApprovalScope, RemoteRuntimeConfig, RemoteUser
from runtime.remote.models import (
    RemoteCommandResult,
    RemotePermission,
    RemoteResultStatus,
)
from runtime.remote.service import RemoteCommandService
from runtime.remote.store import FileRemoteCommandStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MESSAGE_TIMESTAMP = int(
    datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc).timestamp()
)


class DeterministicClock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"2026-09-23T12:{self.value:02d}:00Z"


class TelegramIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"job-telegram-{self.value:03d}"


class FakeTelegramClient:
    def __init__(self, updates: list[dict] | None = None) -> None:
        self.updates = updates or []
        self.sent: list[dict] = []
        self.requested_offsets: list[int] = []

    def get_updates(self, *, offset: int, timeout_seconds: int = 0) -> list[dict]:
        self.requested_offsets.append(offset)
        return list(self.updates)

    def send_message(self, *, chat_id: int, text: str) -> dict:
        self.sent.append({"chat_id": chat_id, "text": text})
        return {"message_id": len(self.sent)}


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, size: int) -> bytes:
        return self.body[:size]


class TelegramTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = DeterministicClock()
        self.jobs = JobRuntime(
            self.root / "jobs",
            clock=self.clock,
            id_factory=TelegramIds(),
        )
        self.approvals = ApprovalRuntime(
            self.jobs,
            FileApprovalStore(self.root / "approvals"),
            clock=self.clock,
        )
        self.config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "telegram",
                    "12345",
                    "owner-human",
                    True,
                    tuple(RemotePermission),
                    RemoteApprovalScope(
                        allowed_actions=("EXECUTE_JOB",),
                        allow_unscoped_projects=True,
                    ),
                ),
            )
        )
        self.remote_store = FileRemoteCommandStore(self.root / "remote")
        self.service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=self.remote_store,
            config=self.config,
            clock=self.clock,
        )
        self.state = TelegramStateStore(self.root / "remote" / "telegram")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Prepare a bounded Telegram status report",
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
            "created_by": "telegram-test",
        }
        value.update(overrides)
        return value

    @staticmethod
    def update(
        update_id: int,
        text: str,
        *,
        user_id: int = 12345,
        username: str = "not-authoritative",
        chat_type: str = "private",
    ) -> dict:
        return {
            "update_id": update_id,
            "message": {
                "message_id": update_id,
                "date": MESSAGE_TIMESTAMP,
                "from": {
                    "id": user_id,
                    "username": username,
                    "first_name": "Ignored",
                },
                "chat": {"id": 7000, "type": chat_type},
                "text": text,
            },
        }

    def transport(self, client: FakeTelegramClient) -> TelegramTransport:
        return TelegramTransport(
            client=client,
            service=self.service,
            config=self.config,
            state=self.state,
            clock=self.clock,
        )

    def pending_approval(self):
        created = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        run_result = self.approvals.request_execution(
            str(created["job_id"]), reason="Telegram approval required"
        )
        assert run_result.request is not None
        return run_result.request

    def test_a_authorized_status(self) -> None:
        client = FakeTelegramClient([self.update(1, "/status")])
        result = self.transport(client).poll_once()
        self.assertEqual(result.processed_updates, 1)
        self.assertIn("Runtime status", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list()[0]["actor"]["platform_user_id"], "12345")

    def test_b_unauthorized_status(self) -> None:
        client = FakeTelegramClient([self.update(2, "/status", user_id=999)])
        self.transport(client).poll_once()
        self.assertIn("Request rejected", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list()[0]["result"]["error_code"], "unauthorized")

    def test_c_jobs(self) -> None:
        job = self.jobs.create(self.payload())
        client = FakeTelegramClient([self.update(3, "/jobs")])
        self.transport(client).poll_once()
        self.assertIn(str(job["job_id"]), client.sent[0]["text"])

    def test_d_job_valid_id(self) -> None:
        job = self.jobs.create(self.payload())
        client = FakeTelegramClient([self.update(4, f"/job {job['job_id']}")])
        self.transport(client).poll_once()
        self.assertIn(f"Job {job['job_id']}", client.sent[0]["text"])
        self.assertIn("Prepare a bounded", client.sent[0]["text"])

    def test_e_approvals(self) -> None:
        approval = self.pending_approval()
        client = FakeTelegramClient([self.update(5, "/approvals")])
        self.transport(client).poll_once()
        self.assertIn(approval.approval_id, client.sent[0]["text"])
        self.assertIn(approval.authorization_fingerprint, client.sent[0]["text"])

    def test_f_valid_approve(self) -> None:
        approval = self.pending_approval()
        command = f"/approve {approval.approval_id} {approval.authorization_fingerprint}"
        client = FakeTelegramClient([self.update(6, command)])
        self.transport(client).poll_once()
        self.assertEqual(self.approvals.store.load(approval.approval_id).status, "APPROVED")
        self.assertIn("approved", client.sent[0]["text"])

    def test_g_valid_reject(self) -> None:
        approval = self.pending_approval()
        command = f"/reject {approval.approval_id} {approval.authorization_fingerprint}"
        client = FakeTelegramClient([self.update(7, command)])
        self.transport(client).poll_once()
        self.assertEqual(self.approvals.store.load(approval.approval_id).status, "REJECTED")
        self.assertIn("rejected", client.sent[0]["text"])

    def test_h_malformed_approve(self) -> None:
        client = FakeTelegramClient([self.update(8, "/approve missing-fingerprint")])
        self.transport(client).poll_once()
        self.assertIn("Usage: /approve", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list(), [])

    def test_i_username_cannot_authorize(self) -> None:
        client = FakeTelegramClient(
            [self.update(9, "/status", user_id=999, username="12345")]
        )
        self.transport(client).poll_once()
        self.assertIn("Request rejected", client.sent[0]["text"])

    def test_j_ordinary_yes_cannot_approve(self) -> None:
        approval = self.pending_approval()
        client = FakeTelegramClient([self.update(10, "yes")])
        self.transport(client).poll_once()
        self.assertEqual(self.approvals.store.load(approval.approval_id).status, "PENDING")
        self.assertIn("Only explicit bot commands", client.sent[0]["text"])

    def test_k_unknown_slash_command_rejected(self) -> None:
        client = FakeTelegramClient([self.update(11, "/run something")])
        self.transport(client).poll_once()
        self.assertIn("Unsupported command", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list(), [])

    def test_command_addressed_to_unknown_bot_is_rejected(self) -> None:
        client = FakeTelegramClient([self.update(111, "/status@another_bot")])
        self.transport(client).poll_once()
        self.assertIn("Unsupported command", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list(), [])

    def test_l_shell_like_message_cannot_execute(self) -> None:
        client = FakeTelegramClient([self.update(12, "rm -rf important")])
        self.transport(client).poll_once()
        self.assertIn("Only explicit bot commands", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list(), [])

    def test_m_duplicate_update_id_does_not_mutate_twice(self) -> None:
        approval = self.pending_approval()
        command = f"/approve {approval.approval_id} {approval.authorization_fingerprint}"
        update = self.update(13, command)
        first = FakeTelegramClient([update])
        self.transport(first).poll_once()
        second = FakeTelegramClient([update])
        result = self.transport(second).poll_once()
        self.assertEqual(result.skipped_updates, 1)
        self.assertEqual(second.sent, [])
        self.assertEqual(len(self.remote_store.list()), 1)

    def test_n_restart_resumes_offset(self) -> None:
        first = FakeTelegramClient([self.update(14, "/status")])
        self.transport(first).poll_once()
        restarted = FakeTelegramClient([])
        self.transport(restarted).poll_once()
        self.assertEqual(restarted.requested_offsets, [15])

    def test_n2_authorized_group_chat_cannot_read_status(self) -> None:
        client = FakeTelegramClient(
            [self.update(140, "/status", chat_type="group")]
        )
        self.transport(client).poll_once()
        self.assertIn("only in private chats", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list(), [])

    def test_n3_group_chat_cannot_mutate_approval(self) -> None:
        approval = self.pending_approval()
        command = f"/approve {approval.approval_id} {approval.authorization_fingerprint}"
        client = FakeTelegramClient(
            [self.update(141, command, chat_type="supergroup")]
        )
        self.transport(client).poll_once()
        self.assertIn("only in private chats", client.sent[0]["text"])
        self.assertEqual(self.approvals.store.load(approval.approval_id).status, "PENDING")
        self.assertEqual(self.remote_store.list(), [])

    def test_n4_missing_chat_type_fails_closed(self) -> None:
        update = self.update(142, "/status")
        del update["message"]["chat"]["type"]
        with self.assertRaises(TelegramParseError):
            TelegramUpdateParser().parse(update)
        self.assertEqual(self.remote_store.list(), [])

    def test_r_response_formatting_is_bounded(self) -> None:
        formatter = TelegramResultFormatter(max_chars=128)
        result = RemoteCommandResult(
            command_id="bounded",
            status=RemoteResultStatus.ACCEPTED,
            result_type="other",
            message="x" * 500,
            processed_at="2026-09-23T12:00:00Z",
        )
        formatted = formatter.format(result)
        self.assertEqual(len(formatted), 128)
        self.assertTrue(formatted.endswith("[response truncated]"))

    def test_s_token_absent_fails_cleanly(self) -> None:
        with self.assertRaisesRegex(TelegramApiError, "is required"):
            TelegramBotApiClient(None)
        stderr = io.StringIO()
        with patch.dict(os.environ, {"AGENT_COMPANY_TELEGRAM_BOT_TOKEN": ""}):
            with redirect_stderr(stderr):
                exit_code = run(
                    [
                        "--state-root",
                        str(self.root / "cli-jobs"),
                        "--approval-root",
                        str(self.root / "cli-approvals"),
                        "--remote-state-root",
                        str(self.root / "cli-remote"),
                        "--remote-config",
                        str(self.root / "missing-config.json"),
                        "telegram",
                        "poll-once",
                    ]
                )
        self.assertEqual(exit_code, 2)
        self.assertNotIn("bot token:", stderr.getvalue().lower())

    def test_t_token_absent_from_persisted_state_and_audit(self) -> None:
        secret = "123456:TEST_SECRET_TOKEN_VALUE"
        responses = [
            TelegramApiClientTests.ok_response([self.update(15, "/status")]),
            TelegramApiClientTests.ok_response({"message_id": 1}),
        ]

        def opener(request, *, timeout):
            return responses.pop(0)

        client = TelegramBotApiClient(secret, opener=opener)
        self.transport(client).poll_once()
        persisted = "".join(
            path.read_text(encoding="utf-8")
            for path in self.root.rglob("*.json")
        )
        self.assertNotIn(secret, persisted)
        self.assertNotIn("TEST_SECRET", persisted)

    def test_offset_waits_for_send_acknowledgement(self) -> None:
        class FailingSendClient(FakeTelegramClient):
            def send_message(self, *, chat_id: int, text: str) -> dict:
                raise TelegramApiError("Telegram API request failed")

        update = self.update(17, "/status")
        with self.assertRaises(TelegramApiError):
            self.transport(FailingSendClient([update])).poll_once()
        self.assertEqual(self.state.load().next_update_id, 0)
        self.assertEqual(len(self.remote_store.list()), 1)

        retry = FakeTelegramClient([update])
        self.transport(retry).poll_once()
        self.assertEqual(self.state.load().next_update_id, 18)
        self.assertIn("Duplicate delivery", retry.sent[0]["text"])

    def test_run_uses_bounded_exponential_backoff(self) -> None:
        class FailingPollClient(FakeTelegramClient):
            def get_updates(self, *, offset: int, timeout_seconds: int = 0) -> list[dict]:
                raise TelegramApiError("Telegram API request failed")

        sleeps: list[float] = []
        transport = TelegramTransport(
            client=FailingPollClient(),
            service=self.service,
            config=self.config,
            state=self.state,
            clock=self.clock,
            sleeper=sleeps.append,
        )
        result = transport.run(backoff_seconds=1, max_cycles=4)
        self.assertEqual(result["api_errors"], 4)
        self.assertEqual(sleeps, [1, 2, 4])

    def test_v_no_shell_true_in_telegram_runtime(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPOSITORY_ROOT / "integrations" / "telegram").glob("*.py")
        )
        self.assertNotIn("shell=True", sources)

    def test_w_canonical_token_environment_name_is_consistent(self) -> None:
        paths = (
            REPOSITORY_ROOT / ".env.example",
            REPOSITORY_ROOT / "integrations" / "telegram" / "README.md",
            REPOSITORY_ROOT / "integrations" / "telegram" / "CONTRACT.md",
            REPOSITORY_ROOT / "runtime" / "remote" / "README.md",
        )
        for path in paths:
            content = path.read_text(encoding="utf-8-sig")
            self.assertIn("AGENT_COMPANY_TELEGRAM_BOT_TOKEN", content, path)
            self.assertNotIn("\nTELEGRAM_BOT_TOKEN=", content, path)

    def test_help_is_bounded_and_does_not_call_core(self) -> None:
        client = FakeTelegramClient([self.update(16, "/help")])
        self.transport(client).poll_once()
        self.assertIn("Available commands", client.sent[0]["text"])
        self.assertEqual(self.remote_store.list(), [])

    def test_malformed_negative_update_id_is_rejected_before_core(self) -> None:
        with self.assertRaises(TelegramParseError):
            TelegramUpdateParser().parse(self.update(-1, "/status"))
        self.assertEqual(self.remote_store.list(), [])


class TelegramApiClientTests(unittest.TestCase):
    @staticmethod
    def ok_response(result) -> FakeResponse:
        return FakeResponse(json.dumps({"ok": True, "result": result}).encode("utf-8"))

    def test_o_timeout_handled_safely(self) -> None:
        def timeout_opener(request, *, timeout):
            raise socket.timeout()

        client = TelegramBotApiClient("123456:secret", opener=timeout_opener)
        with self.assertRaisesRegex(TelegramApiError, "timed out"):
            client.get_updates(offset=0)

    def test_p_non_200_handled_safely_without_url(self) -> None:
        def error_opener(request, *, timeout):
            raise HTTPError(request.full_url, 500, "failure", {}, None)

        token = "123456:never-print-this"
        client = TelegramBotApiClient(token, opener=error_opener)
        with self.assertRaises(TelegramApiError) as caught:
            client.get_updates(offset=0)
        self.assertNotIn(token, str(caught.exception))
        self.assertNotIn(TELEGRAM_API_ORIGIN, str(caught.exception))

    def test_q_malformed_response_handled_safely(self) -> None:
        client = TelegramBotApiClient(
            "123456:secret", opener=lambda request, timeout: FakeResponse(b"{")
        )
        with self.assertRaisesRegex(TelegramApiError, "malformed JSON"):
            client.get_updates(offset=0)

    def test_u_fixed_https_endpoint_and_mocked_http(self) -> None:
        captured = []

        def opener(request, *, timeout):
            captured.append(request)
            return self.ok_response([])

        client = TelegramBotApiClient("123456:secret", opener=opener)
        self.assertEqual(client.get_updates(offset=44), [])
        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0].full_url.startswith(f"{TELEGRAM_API_ORIGIN}/bot"))
        self.assertEqual(captured[0].method, "POST")


if __name__ == "__main__":
    unittest.main()
