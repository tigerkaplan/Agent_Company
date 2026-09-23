from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
import io
from pathlib import Path

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime
from runtime.remote.config import RemoteRuntimeConfig, RemoteUser
from runtime.remote.models import RemoteCommand, RemoteCommandType
from runtime.remote.service import RemoteCommandService
from runtime.remote.store import FileRemoteCommandStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class DeterministicClock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"2026-09-23T12:{self.value:02d}:00Z"


class RemoteIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"job-remote-{self.value:03d}"


class RemoteRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clock = DeterministicClock()
        self.jobs = JobRuntime(
            self.root / "jobs",
            clock=self.clock,
            id_factory=RemoteIds(),
        )
        self.approval_store = FileApprovalStore(self.root / "approvals")
        self.approvals = ApprovalRuntime(
            self.jobs,
            self.approval_store,
            clock=self.clock,
        )
        self.config = RemoteRuntimeConfig(
            users=(
                RemoteUser("local_test", "test-human", "owner-human", True),
                RemoteUser("local_test", "disabled-human", "disabled-owner", False),
                RemoteUser("local_test", "other-human", "other-owner", True),
            )
        )
        self.store = FileRemoteCommandStore(self.root / "remote")
        self.service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=self.store,
            config=self.config,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "task": "Prepare a bounded remote status report",
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
            "created_by": "remote-test",
        }
        value.update(overrides)
        return value

    def identity(self, user: str = "test-human"):
        return self.config.identify(channel="local_test", platform_user_id=user)

    def command(
        self,
        command_type: RemoteCommandType,
        *,
        command_id: str | None = None,
        actor: str = "test-human",
        target_id: str | None = None,
        approval_id: str | None = None,
        authorization_fingerprint: str | None = None,
        issued_at: str = "2026-09-23T12:00:00Z",
        received_at: str = "2026-09-23T12:01:00Z",
    ) -> RemoteCommand:
        stable_id = command_id or f"remote-{command_type.value.lower()}-{len(self.store.list())}"
        return RemoteCommand(
            command_id=stable_id,
            channel="local_test",
            actor=actor,
            command_type=command_type,
            target_id=target_id,
            approval_id=approval_id,
            authorization_fingerprint=authorization_fingerprint,
            issued_at=issued_at,
            received_at=received_at,
            idempotency_key=stable_id,
            metadata={"ignored_body": "token=SHOULD_NOT_APPEAR"},
        )

    def pending_approval(self):
        created = self.jobs.create(
            self.payload(risk_level="approval_required", approval_status="required")
        )
        run_result = self.approvals.request_execution(
            str(created["job_id"]), reason="Remote approval required"
        )
        assert run_result.job is not None
        return run_result.job, run_result.request

    def test_a_authorized_status(self) -> None:
        result = self.service.handle(
            self.command(RemoteCommandType.STATUS),
            self.identity(),
        )
        self.assertEqual(result.status.value, "accepted")
        self.assertEqual(result.data_refs["jobs_total"], 0)

    def test_b_unauthorized_status_rejected(self) -> None:
        result = self.service.handle(
            self.command(RemoteCommandType.STATUS, actor="stranger"),
            self.config.identify(channel="local_test", platform_user_id="stranger"),
        )
        self.assertEqual(result.status.value, "rejected")
        self.assertEqual(result.error_code, "unauthorized")

    def test_c_authorized_jobs_list(self) -> None:
        self.jobs.create(self.payload())
        result = self.service.handle(
            self.command(RemoteCommandType.JOBS_LIST),
            self.identity(),
        )
        self.assertEqual(result.status.value, "accepted")
        self.assertEqual(result.data_refs["count"], 1)

    def test_d_job_show(self) -> None:
        job = self.jobs.create(self.payload(task="Show this one job"))
        result = self.service.handle(
            self.command(RemoteCommandType.JOB_SHOW, target_id=str(job["job_id"])),
            self.identity(),
        )
        self.assertEqual(result.status.value, "accepted")
        self.assertEqual(result.data_refs["job"]["job_id"], job["job_id"])
        self.assertEqual(result.data_refs["job"]["task"], "Show this one job")

    def test_e_pending_approvals_list(self) -> None:
        _, approval = self.pending_approval()
        result = self.service.handle(
            self.command(RemoteCommandType.APPROVALS_LIST),
            self.identity(),
        )
        self.assertEqual(result.status.value, "accepted")
        self.assertEqual(result.data_refs["approvals"][0]["approval_id"], approval.approval_id)
        self.assertEqual(
            result.data_refs["approvals"][0]["authorization_fingerprint"],
            approval.authorization_fingerprint,
        )

    def test_f_unknown_command_rejected(self) -> None:
        result = self.service.handle(
            {
                "command_id": "remote-unknown",
                "channel": "local_test",
                "actor": "test-human",
                "command_type": "BOGUS",
                "issued_at": "2026-09-23T12:00:00Z",
                "received_at": "2026-09-23T12:01:00Z",
                "idempotency_key": "remote-unknown",
            },
            self.identity(),
        )
        self.assertEqual(result.status.value, "unsupported")

    def test_g_shell_like_command_rejected(self) -> None:
        result = self.service.handle(
            {
                "command_id": "remote-shell",
                "channel": "local_test",
                "actor": "test-human",
                "command_type": "rm -rf .",
                "issued_at": "2026-09-23T12:00:00Z",
                "received_at": "2026-09-23T12:01:00Z",
                "idempotency_key": "remote-shell",
            },
            self.identity(),
        )
        self.assertEqual(result.status.value, "unsupported")

    def test_h_valid_remote_approve(self) -> None:
        _, approval = self.pending_approval()
        result = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            self.identity(),
        )
        self.assertEqual(result.status.value, "accepted")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "APPROVED")
        self.assertEqual(
            self.approval_store.load(approval.approval_id).decided_by,
            "owner-human",
        )

    def test_i_valid_remote_reject(self) -> None:
        _, approval = self.pending_approval()
        result = self.service.handle(
            self.command(
                RemoteCommandType.REJECT,
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            self.identity(),
        )
        self.assertEqual(result.status.value, "accepted")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "REJECTED")

    def test_j_username_alone_cannot_authorize(self) -> None:
        result = self.service.handle(
            self.command(RemoteCommandType.STATUS, actor="friendly-name"),
            self.config.identify(channel="local_test", platform_user_id="friendly-name"),
        )
        self.assertEqual(result.status.value, "rejected")
        self.assertEqual(result.error_code, "unauthorized")

    def test_k_wrong_human_mapping_rejected(self) -> None:
        result = self.service.handle(
            self.command(RemoteCommandType.STATUS, actor="test-human"),
            self.identity("other-human"),
        )
        self.assertEqual(result.status.value, "rejected")
        self.assertEqual(result.error_code, "actor_mismatch")

    def test_l_missing_approval_id_rejected(self) -> None:
        result = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                authorization_fingerprint="0" * 64,
            ),
            self.identity(),
        )
        self.assertEqual(result.status.value, "rejected")

    def test_m_wrong_fingerprint_rejected(self) -> None:
        _, approval = self.pending_approval()
        result = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                approval_id=approval.approval_id,
                authorization_fingerprint="0" * 64,
            ),
            self.identity(),
        )
        self.assertEqual(result.error_code, "authorization_fingerprint_mismatch")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_n_stale_fingerprint_rejected(self) -> None:
        waiting, approval = self.pending_approval()
        changed = dict(waiting)
        changed["risk_level"] = "high"
        changed["last_updated_at"] = self.clock()
        self.jobs.store.save(changed)
        result = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            self.identity(),
        )
        self.assertEqual(result.error_code, "approval_stale")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_o_expired_callback_rejected(self) -> None:
        _, approval = self.pending_approval()
        result = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
                issued_at="2026-09-23T12:00:00Z",
                received_at="2026-09-23T12:11:00Z",
            ),
            self.identity(),
        )
        self.assertEqual(result.error_code, "remote_interaction_expired")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_p_duplicate_command_idempotent(self) -> None:
        command = self.command(RemoteCommandType.STATUS, command_id="remote-repeat")
        first = self.service.handle(command, self.identity())
        second = self.service.handle(command, self.identity())
        self.assertEqual(first.status.value, "accepted")
        self.assertEqual(second.status.value, "duplicate")

    def test_p2_duplicate_idempotency_key_is_idempotent(self) -> None:
        first = self.command(RemoteCommandType.STATUS, command_id="remote-repeat-a")
        second = RemoteCommand(
            command_id="remote-repeat-b",
            channel=first.channel,
            actor=first.actor,
            command_type=first.command_type,
            target_id=first.target_id,
            approval_id=first.approval_id,
            authorization_fingerprint=first.authorization_fingerprint,
            issued_at=first.issued_at,
            received_at=first.received_at,
            idempotency_key=first.idempotency_key,
            metadata=first.metadata,
        )
        accepted = self.service.handle(first, self.identity())
        duplicate = self.service.handle(second, self.identity())
        self.assertEqual(accepted.status.value, "accepted")
        self.assertEqual(duplicate.status.value, "duplicate")

    def test_q_duplicate_approve_does_not_mutate_twice(self) -> None:
        _, approval = self.pending_approval()
        command = self.command(
            RemoteCommandType.APPROVE,
            command_id="remote-approve-repeat",
            approval_id=approval.approval_id,
            authorization_fingerprint=approval.authorization_fingerprint,
        )
        first = self.service.handle(command, self.identity())
        second = self.service.handle(command, self.identity())
        self.assertEqual(first.status.value, "accepted")
        self.assertEqual(second.status.value, "duplicate")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "APPROVED")
        self.assertEqual(len(self.store.list()), 1)

    def test_r_restart_preserves_replay_protection(self) -> None:
        command = self.command(RemoteCommandType.STATUS, command_id="remote-restart")
        self.service.handle(command, self.identity())
        restarted = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "remote"),
            config=self.config,
            clock=self.clock,
        )
        result = restarted.handle(command, self.identity())
        self.assertEqual(result.status.value, "duplicate")

    def test_s_resolved_approval_cannot_be_reused(self) -> None:
        _, approval = self.pending_approval()
        self.approvals.resolve(
            approval.approval_id,
            decision="APPROVED",
            decided_by="local-owner",
        )
        result = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                command_id="remote-consumed",
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            self.identity(),
        )
        self.assertEqual(result.error_code, "approval_not_pending")

    def test_t_audit_record_persisted(self) -> None:
        self.service.handle(self.command(RemoteCommandType.STATUS), self.identity())
        records = self.store.list()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["command_type"], "STATUS")
        self.assertEqual(records[0]["actor"]["mapped_human_identity"], "owner-human")

    def test_u_secrets_absent_from_audit(self) -> None:
        self.service.handle(self.command(RemoteCommandType.STATUS), self.identity())
        serialized = json.dumps(self.store.list(), sort_keys=True)
        self.assertNotIn("SHOULD_NOT_APPEAR", serialized)
        self.assertNotIn("token=", serialized)

    def test_v_remote_generated_state_git_ignored(self) -> None:
        probe = "runtime/state/remote/probe.remote-command.json"
        result = subprocess.run(
            ["git", "check-ignore", probe],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_w_cli_remote_status_uses_configured_identity(self) -> None:
        config_path = self.root / "remote.local.json"
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "approval_ttl_seconds": 600,
                    "allowed_users": [
                        {
                            "channel": "local_test",
                            "platform_user_id": "test-human",
                            "mapped_human_identity": "owner-human",
                            "enabled": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = run(
                [
                    "--state-root",
                    str(self.root / "jobs"),
                    "--approval-root",
                    str(self.root / "approvals"),
                    "--remote-state-root",
                    str(self.root / "remote-cli"),
                    "--remote-config",
                    str(config_path),
                    "remote",
                    "status",
                    "--actor",
                    "test-human",
                    "--command-id",
                    "remote-cli-status",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "accepted")

    def test_x_remote_config_accepts_utf8_bom(self) -> None:
        config_path = self.root / "remote-bom.local.json"
        config_path.write_bytes(
            b"\xef\xbb\xbf"
            + json.dumps(
                {
                    "schema_version": 1,
                    "approval_ttl_seconds": 600,
                    "max_audit_records": 1000,
                    "allowed_users": [
                        {
                            "channel": "telegram",
                            "platform_user_id": "123456789",
                            "mapped_human_identity": "owner-human",
                            "enabled": True,
                        }
                    ],
                }
            ).encode("utf-8")
        )

        config = RemoteRuntimeConfig.from_file(config_path)

        identity = config.identify(
            channel="telegram",
            platform_user_id="123456789",
        )
        self.assertTrue(identity.authorized)
        self.assertEqual(identity.mapped_human_identity, "owner-human")
        self.assertEqual(config.approval_ttl_seconds, 600)
        self.assertEqual(config.max_audit_records, 1000)


if __name__ == "__main__":
    unittest.main()
