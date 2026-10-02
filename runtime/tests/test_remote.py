from __future__ import annotations

from runtime.tests.contract_fixtures import declare_fixture_contract

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
import io
from pathlib import Path
from unittest.mock import patch

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError
from runtime.remote.config import (
    RemoteApprovalScope,
    RemoteRuntimeConfig,
    RemoteUser,
)
from runtime.remote.models import RemoteCommand, RemoteCommandType, RemotePermission
from runtime.remote.service import RemoteCommandService, RemoteCommandServiceError
from runtime.remote.store import FileRemoteCommandStore, RemoteStoreError


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


class RecordingRemoteStore(FileRemoteCommandStore):
    def __init__(
        self,
        root: Path,
        *,
        max_records: int = 1000,
        fail_save: bool = False,
        fail_update: int | None = None,
    ) -> None:
        super().__init__(root, max_records=max_records)
        self.fail_save = fail_save
        self.fail_update = fail_update
        self.update_calls = 0
        self.states: list[str] = []

    def save(self, record: dict[str, object]) -> None:
        if self.fail_save:
            raise RemoteStoreError("simulated preparation failure")
        self.states.append(str(record.get("audit_state")))
        super().save(record)

    def update(self, record: dict[str, object]) -> None:
        self.update_calls += 1
        if self.fail_update == self.update_calls:
            raise RemoteStoreError("simulated finalization failure")
        self.states.append(str(record.get("audit_state")))
        super().update(record)


class RecordingApprovalEmitter:
    def __init__(self) -> None:
        self.resolved: list[tuple[str, str]] = []

    def approval_requested(self, approval, job) -> None:
        return None

    def approval_resolved(self, approval, job) -> None:
        self.resolved.append((str(approval["approval_id"]), str(approval["status"])))


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
                RemoteUser(
                    "local_test",
                    "test-human",
                    "owner-human",
                    True,
                    tuple(RemotePermission),
                    RemoteApprovalScope(
                        allowed_actions=("EXECUTE_JOB",),
                        allow_unscoped_projects=True,
                    ),
                ),
                RemoteUser(
                    "local_test",
                    "disabled-human",
                    "disabled-owner",
                    False,
                    tuple(RemotePermission),
                ),
                RemoteUser(
                    "local_test",
                    "other-human",
                    "other-owner",
                    True,
                    tuple(RemotePermission),
                ),
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
        return declare_fixture_contract(value)

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

    @staticmethod
    def replay_command(
        command: RemoteCommand,
        *,
        command_id: str,
        received_at: str,
    ) -> RemoteCommand:
        return RemoteCommand(
            command_id=command_id,
            channel=command.channel,
            actor=command.actor,
            command_type=command.command_type,
            target_id=command.target_id,
            approval_id=command.approval_id,
            authorization_fingerprint=command.authorization_fingerprint,
            issued_at=command.issued_at,
            received_at=received_at,
            idempotency_key=command.idempotency_key,
            metadata=command.metadata,
        )

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
        self.assertEqual(result.error_code, "approval_not_available")
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

    def test_p3_replay_reauthorizes_current_permission(self) -> None:
        command = self.command(RemoteCommandType.STATUS, command_id="revoked-status")
        identity = self.identity()
        self.assertEqual(self.service.handle(command, identity).status.value, "accepted")
        self.service.config = RemoteRuntimeConfig(
            users=(RemoteUser("local_test", "test-human", "owner-human", True),)
        )

        replay = self.service.handle(command, identity)

        self.assertEqual(replay.status.value, "rejected")
        self.assertEqual(replay.error_code, "permission_denied")
        self.assertEqual(replay.data_refs, {})

    def test_p4_replay_reauthorizes_disabled_or_removed_identity(self) -> None:
        for suffix, config in (
            (
                "disabled",
                RemoteRuntimeConfig(
                    users=(
                        RemoteUser(
                            "local_test",
                            "test-human",
                            "owner-human",
                            False,
                            (RemotePermission.READ_STATUS,),
                        ),
                    )
                ),
            ),
            ("removed", RemoteRuntimeConfig.empty()),
        ):
            with self.subTest(suffix=suffix):
                self.service.config = self.config
                identity = self.identity()
                command = self.command(
                    RemoteCommandType.STATUS,
                    command_id=f"identity-{suffix}",
                )
                self.assertEqual(
                    self.service.handle(command, identity).status.value, "accepted"
                )
                self.service.config = config
                replay = self.service.handle(command, identity)
                self.assertEqual(replay.status.value, "rejected")
                self.assertEqual(replay.error_code, "unauthorized")
                self.assertEqual(replay.data_refs, {})

    def test_p5_replay_reauthorizes_current_approval_scope(self) -> None:
        _, approval = self.pending_approval()
        command = self.command(
            RemoteCommandType.APPROVALS_LIST,
            command_id="approval-list-scope-replay",
        )
        identity = self.identity()
        first = self.service.handle(command, identity)
        self.assertEqual(first.status.value, "accepted")
        self.assertEqual(
            first.data_refs["approvals"][0]["approval_id"], approval.approval_id
        )
        self.service.config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "local_test",
                    "test-human",
                    "owner-human",
                    True,
                    (RemotePermission.READ_APPROVALS,),
                    RemoteApprovalScope(),
                ),
            )
        )

        replay = self.service.handle(command, identity)

        self.assertEqual(replay.status.value, "rejected")
        self.assertEqual(replay.error_code, "approval_scope_denied")
        self.assertNotIn("approvals", replay.data_refs)

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
                            "permissions": ["READ_STATUS"],
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
                            "permissions": ["READ_STATUS"],
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

    def test_y_enabled_user_without_permission_is_denied(self) -> None:
        config = RemoteRuntimeConfig(
            users=(RemoteUser("local_test", "limited", "limited-human", True),)
        )
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "limited-remote"),
            config=config,
            clock=self.clock,
        )
        result = service.handle(
            self.command(RemoteCommandType.STATUS, actor="limited"),
            config.identify(channel="local_test", platform_user_id="limited"),
        )
        self.assertEqual(result.error_code, "permission_denied")

    def test_z_permission_is_command_specific(self) -> None:
        config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "local_test",
                    "reader",
                    "reader-human",
                    True,
                    (RemotePermission.READ_STATUS,),
                ),
            )
        )
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "reader-remote"),
            config=config,
            clock=self.clock,
        )
        identity = config.identify(channel="local_test", platform_user_id="reader")
        accepted = service.handle(
            self.command(RemoteCommandType.STATUS, actor="reader", command_id="reader-status"),
            identity,
        )
        denied = service.handle(
            self.command(
                RemoteCommandType.APPROVALS_LIST,
                actor="reader",
                command_id="reader-approvals",
            ),
            identity,
        )
        self.assertEqual(accepted.status.value, "accepted")
        self.assertEqual(denied.error_code, "permission_denied")

    def test_z2_read_approvals_cannot_approve(self) -> None:
        _, approval = self.pending_approval()
        config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "local_test",
                    "approval-reader",
                    "reader-human",
                    True,
                    (RemotePermission.READ_APPROVALS,),
                    RemoteApprovalScope(
                        allowed_actions=("EXECUTE_JOB",),
                        allow_unscoped_projects=True,
                    ),
                ),
            )
        )
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "approval-reader-remote"),
            config=config,
            clock=self.clock,
        )
        result = service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                actor="approval-reader",
                command_id="approval-reader-approve",
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            config.identify(
                channel="local_test", platform_user_id="approval-reader"
            ),
        )
        self.assertEqual(result.error_code, "permission_denied")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_z3_approve_permission_cannot_exceed_approval_scope(self) -> None:
        _, approval = self.pending_approval()
        config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "local_test",
                    "scoped",
                    "scoped-human",
                    True,
                    (RemotePermission.APPROVE,),
                    RemoteApprovalScope(
                        allowed_actions=("COMPLETE_REVIEWED_JOB",),
                        allow_unscoped_projects=True,
                    ),
                ),
            )
        )
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "scoped-remote"),
            config=config,
            clock=self.clock,
        )
        result = service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                actor="scoped",
                command_id="scoped-approve",
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            config.identify(channel="local_test", platform_user_id="scoped"),
        )
        self.assertEqual(result.error_code, "approval_scope_denied")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_z31_reject_permission_cannot_exceed_approval_scope(self) -> None:
        _, approval = self.pending_approval()
        config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "local_test",
                    "scoped-rejector",
                    "scoped-human",
                    True,
                    (RemotePermission.REJECT,),
                    RemoteApprovalScope(
                        allowed_actions=("COMPLETE_REVIEWED_JOB",),
                        allow_unscoped_projects=True,
                    ),
                ),
            )
        )
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "scoped-reject-remote"),
            config=config,
            clock=self.clock,
        )
        result = service.handle(
            self.command(
                RemoteCommandType.REJECT,
                actor="scoped-rejector",
                command_id="scoped-reject",
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            config.identify(
                channel="local_test", platform_user_id="scoped-rejector"
            ),
        )
        self.assertEqual(result.error_code, "approval_scope_denied")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_z4_strict_config_validation(self) -> None:
        base_user = {
            "channel": "telegram",
            "platform_user_id": "123456789",
            "mapped_human_identity": "owner-human",
            "enabled": False,
            "permissions": ["READ_STATUS"],
        }
        cases = (
            ({**base_user, "enabled": "false"}, "enabled"),
            ({**base_user, "enabled": "true"}, "enabled"),
            ({**base_user, "permissions": ["UNKNOWN"]}, "permission"),
            ({key: value for key, value in base_user.items() if key != "channel"}, "fields"),
        )
        for index, (user, message) in enumerate(cases):
            path = self.root / f"invalid-{index}.json"
            path.write_text(
                json.dumps({"schema_version": 1, "allowed_users": [user]}),
                encoding="utf-8",
            )
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, message):
                    RemoteRuntimeConfig.from_file(path)

        duplicate_path = self.root / "duplicate.json"
        duplicate_path.write_text(
            json.dumps(
                {"schema_version": 1, "allowed_users": [base_user, base_user]}
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            RemoteRuntimeConfig.from_file(duplicate_path)

        disabled_path = self.root / "disabled.json"
        disabled_path.write_text(
            json.dumps({"schema_version": 1, "allowed_users": [base_user]}),
            encoding="utf-8",
        )
        disabled = RemoteRuntimeConfig.from_file(disabled_path)
        self.assertFalse(
            disabled.identify(channel="telegram", platform_user_id="123456789").authorized
        )

        no_permissions = dict(base_user)
        no_permissions.pop("permissions")
        no_permissions["enabled"] = True
        no_permissions_path = self.root / "no-permissions.json"
        no_permissions_path.write_text(
            json.dumps(
                {"schema_version": 1, "allowed_users": [no_permissions]}
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            RemoteRuntimeConfig.from_file(no_permissions_path).users[0].permissions,
            (),
        )

        malformed_targets = self.root / "malformed-targets.json"
        malformed_targets.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "allowed_users": [],
                    "notification_targets": [{"human": "owner"}],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "notification_targets"):
            RemoteRuntimeConfig.from_file(malformed_targets)

        unknown_top = self.root / "unknown-top.json"
        unknown_top.write_text(
            json.dumps({"schema_version": 1, "allowed_users": [], "wildcard": True}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unsupported"):
            RemoteRuntimeConfig.from_file(unknown_top)

    def test_z41_duplicate_json_keys_are_rejected_at_every_level(self) -> None:
        cases = {
            "top": '{"schema_version":1,"schema_version":1,"allowed_users":[]}',
            "user": (
                '{"schema_version":1,"allowed_users":[{'
                '"channel":"telegram","platform_user_id":"123456789",'
                '"mapped_human_identity":"owner-human","enabled":false,'
                '"enabled":true,"permissions":["READ_STATUS"]}]}'
            ),
            "scope": (
                '{"schema_version":1,"allowed_users":[{'
                '"channel":"telegram","platform_user_id":"123456789",'
                '"mapped_human_identity":"owner-human","enabled":true,'
                '"permissions":["APPROVE"],"approval_scope":{'
                '"allowed_actions":["EXECUTE_JOB"],'
                '"allow_unscoped_projects":false,'
                '"allow_unscoped_projects":true}}]}'
            ),
        }
        for name, content in cases.items():
            path = self.root / f"duplicate-key-{name}.json"
            path.write_text(content, encoding="utf-8")
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                    RemoteRuntimeConfig.from_file(path)

        ordinary = self.root / "ordinary-utf8.json"
        ordinary.write_text(
            json.dumps({"schema_version": 1, "allowed_users": []}),
            encoding="utf-8",
        )
        self.assertEqual(RemoteRuntimeConfig.from_file(ordinary).users, ())

    def test_z42_approval_project_scope_is_enforced(self) -> None:
        created = self.jobs.create(
            self.payload(
                project_id="project-beta",
                risk_level="approval_required",
                approval_status="required",
            )
        )
        pending = self.approvals.request_execution(
            str(created["job_id"]), reason="Project-scoped approval"
        )
        config = RemoteRuntimeConfig(
            users=(
                RemoteUser(
                    "local_test",
                    "project-approver",
                    "project-human",
                    True,
                    (RemotePermission.APPROVE,),
                    RemoteApprovalScope(
                        allowed_actions=("EXECUTE_JOB",),
                        project_ids=("project-alpha",),
                    ),
                ),
            )
        )
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=FileRemoteCommandStore(self.root / "project-scope-remote"),
            config=config,
            clock=self.clock,
        )
        result = service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                actor="project-approver",
                command_id="project-scope-approve",
                approval_id=pending.request.approval_id,
                authorization_fingerprint=pending.request.authorization_fingerprint,
            ),
            config.identify(
                channel="local_test", platform_user_id="project-approver"
            ),
        )
        self.assertEqual(result.error_code, "approval_scope_denied")
        self.assertEqual(
            self.approval_store.load(pending.request.approval_id).status, "PENDING"
        )

    def test_z5_clock_skew_boundaries_fail_closed(self) -> None:
        _, approval = self.pending_approval()
        permitted = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                command_id="skew-permitted",
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
                issued_at="2026-09-23T12:01:30Z",
                received_at="2026-09-23T12:01:00Z",
            ),
            self.identity(),
        )
        self.assertEqual(permitted.status.value, "accepted")

        _, future_approval = self.pending_approval()
        excessive = self.service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                command_id="skew-excessive",
                approval_id=future_approval.approval_id,
                authorization_fingerprint=future_approval.authorization_fingerprint,
                issued_at="2026-09-23T12:01:31Z",
                received_at="2026-09-23T12:01:00Z",
            ),
            self.identity(),
        )
        self.assertEqual(excessive.error_code, "remote_interaction_future")
        self.assertEqual(
            self.approval_store.load(future_approval.approval_id).status, "PENDING"
        )

    def test_z6_audit_preparation_failure_prevents_mutation(self) -> None:
        _, approval = self.pending_approval()
        store = RecordingRemoteStore(self.root / "prepare-failure", fail_save=True)
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=store,
            config=self.config,
            clock=self.clock,
        )
        with self.assertRaises(RemoteCommandServiceError):
            service.handle(
                self.command(
                    RemoteCommandType.APPROVE,
                    command_id="prepare-failure",
                    approval_id=approval.approval_id,
                    authorization_fingerprint=approval.authorization_fingerprint,
                ),
                self.identity(),
            )
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "PENDING")

    def test_z7_successful_mutation_has_durable_stages(self) -> None:
        _, approval = self.pending_approval()
        store = RecordingRemoteStore(self.root / "recorded-stages")
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=store,
            config=self.config,
            clock=self.clock,
        )
        service.handle(
            self.command(
                RemoteCommandType.APPROVE,
                command_id="recorded-stages",
                approval_id=approval.approval_id,
                authorization_fingerprint=approval.authorization_fingerprint,
            ),
            self.identity(),
        )
        self.assertEqual(
            store.states, ["AUTHORIZED", "MUTATION_ATTEMPTED", "COMPLETED"]
        )
        self.assertEqual(store.list()[0]["mutation_state"], "completed")

    def test_z8_post_mutation_audit_failure_is_visible_and_idempotent(self) -> None:
        _, approval = self.pending_approval()
        store = RecordingRemoteStore(self.root / "finalize-failure", fail_update=2)
        service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=store,
            config=self.config,
            clock=self.clock,
        )
        command = self.command(
            RemoteCommandType.APPROVE,
            command_id="finalize-failure",
            approval_id=approval.approval_id,
            authorization_fingerprint=approval.authorization_fingerprint,
        )
        with self.assertRaises(RemoteCommandServiceError):
            service.handle(command, self.identity())
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "APPROVED")
        self.assertEqual(store.list()[0]["audit_state"], "MUTATION_ATTEMPTED")
        retry = service.handle(command, self.identity())
        self.assertEqual(retry.status.value, "duplicate")
        self.assertIsNone(retry.error_code)
        self.assertEqual(store.list()[0]["audit_state"], "COMPLETED")
        self.assertEqual(self.approval_store.load(approval.approval_id).status, "APPROVED")

    def test_z81_partial_approval_transition_reconciles_once(self) -> None:
        for command_type, decision, job_status in (
            (RemoteCommandType.APPROVE, "APPROVED", "queued"),
            (RemoteCommandType.REJECT, "REJECTED", "cancelled"),
        ):
            with self.subTest(decision=decision):
                _, approval = self.pending_approval()
                emitter = RecordingApprovalEmitter()
                approvals = ApprovalRuntime(
                    self.jobs,
                    self.approval_store,
                    clock=self.clock,
                    notification_emitter=emitter,
                )
                store = FileRemoteCommandStore(
                    self.root / f"partial-{decision.lower()}"
                )
                service = RemoteCommandService(
                    jobs=self.jobs,
                    approvals=approvals,
                    store=store,
                    config=self.config,
                    clock=self.clock,
                )
                command = self.command(
                    command_type,
                    command_id=f"partial-{decision.lower()}",
                    approval_id=approval.approval_id,
                    authorization_fingerprint=approval.authorization_fingerprint,
                )
                with patch.object(
                    self.approval_store,
                    "resolve",
                    wraps=self.approval_store.resolve,
                ) as persist_decision:
                    with patch.object(
                        self.jobs,
                        "apply_approval_resolution",
                        side_effect=JobRuntimeError("simulated downstream failure"),
                    ):
                        first = service.handle(command, self.identity())

                    self.assertEqual(
                        first.error_code, "approval_reconciliation_required"
                    )
                    self.assertEqual(
                        self.approval_store.load(approval.approval_id).status,
                        decision,
                    )
                    self.assertEqual(
                        store.list()[0]["audit_state"],
                        "RECONCILIATION_REQUIRED",
                    )
                    self.assertEqual(store.list()[0]["mutation_state"], "uncertain")
                    self.assertEqual(emitter.resolved, [])

                    retry = service.handle(command, self.identity())

                    self.assertEqual(retry.status.value, "duplicate")
                    self.assertEqual(store.list()[0]["audit_state"], "COMPLETED")
                    self.assertEqual(
                        self.jobs.show(approval.job_id)["status"], job_status
                    )
                    self.assertEqual(
                        emitter.resolved,
                        [(approval.approval_id, decision)],
                    )
                    self.assertEqual(persist_decision.call_count, 1)

    def test_z82_pending_recovery_rechecks_ttl_and_future_time(self) -> None:
        cases = (
            ("expired", "2026-09-23T12:10:01Z", "remote_interaction_expired", False),
            ("future", "2026-09-23T11:59:29Z", "remote_interaction_future", False),
            ("within-ttl", "2026-09-23T12:10:00Z", None, True),
        )
        for suffix, received_at, error_code, should_resolve in cases:
            with self.subTest(suffix=suffix):
                _, approval = self.pending_approval()
                state_root = self.root / f"pending-recovery-{suffix}"
                store = FileRemoteCommandStore(state_root)
                service = RemoteCommandService(
                    jobs=self.jobs,
                    approvals=self.approvals,
                    store=store,
                    config=self.config,
                    clock=self.clock,
                )
                command = self.command(
                    RemoteCommandType.APPROVE,
                    command_id=f"pending-recovery-{suffix}-original",
                    approval_id=approval.approval_id,
                    authorization_fingerprint=approval.authorization_fingerprint,
                )
                with patch.object(
                    self.approvals,
                    "resolve",
                    side_effect=KeyboardInterrupt("simulated pre-mutation interruption"),
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        service.handle(command, self.identity())
                self.assertEqual(store.list()[0]["audit_state"], "MUTATION_ATTEMPTED")

                restarted = RemoteCommandService(
                    jobs=self.jobs,
                    approvals=self.approvals,
                    store=FileRemoteCommandStore(state_root),
                    config=self.config,
                    clock=self.clock,
                )
                retry = restarted.handle(
                    self.replay_command(
                        command,
                        command_id=f"pending-recovery-{suffix}-retry",
                        received_at=received_at,
                    ),
                    self.identity(),
                )

                self.assertEqual(retry.error_code, error_code)
                expected = "APPROVED" if should_resolve else "PENDING"
                self.assertEqual(
                    self.approval_store.load(approval.approval_id).status,
                    expected,
                )
                self.assertEqual(
                    store.list()[0]["audit_state"],
                    "COMPLETED" if should_resolve else "FAILED",
                )

    def test_z83_resolved_old_approval_reconciles_without_second_decision(self) -> None:
        for command_type, decision, job_status in (
            (RemoteCommandType.APPROVE, "APPROVED", "queued"),
            (RemoteCommandType.REJECT, "REJECTED", "cancelled"),
        ):
            with self.subTest(decision=decision):
                _, approval = self.pending_approval()
                emitter = RecordingApprovalEmitter()
                approvals = ApprovalRuntime(
                    self.jobs,
                    self.approval_store,
                    clock=self.clock,
                    notification_emitter=emitter,
                )
                state_root = self.root / f"old-recovery-{decision.lower()}"
                store = FileRemoteCommandStore(state_root)
                service = RemoteCommandService(
                    jobs=self.jobs,
                    approvals=approvals,
                    store=store,
                    config=self.config,
                    clock=self.clock,
                )
                command = self.command(
                    command_type,
                    command_id=f"old-recovery-{decision.lower()}-original",
                    approval_id=approval.approval_id,
                    authorization_fingerprint=approval.authorization_fingerprint,
                )
                with patch.object(
                    self.approval_store,
                    "resolve",
                    wraps=self.approval_store.resolve,
                ) as persist_decision:
                    with patch.object(
                        self.jobs,
                        "apply_approval_resolution",
                        side_effect=JobRuntimeError("simulated downstream failure"),
                    ):
                        first = service.handle(command, self.identity())
                    self.assertEqual(
                        first.error_code, "approval_reconciliation_required"
                    )

                    restarted = RemoteCommandService(
                        jobs=self.jobs,
                        approvals=approvals,
                        store=FileRemoteCommandStore(state_root),
                        config=self.config,
                        clock=self.clock,
                    )
                    retry = restarted.handle(
                        self.replay_command(
                            command,
                            command_id=f"old-recovery-{decision.lower()}-retry",
                            received_at="2026-09-23T12:20:00Z",
                        ),
                        self.identity(),
                    )

                    self.assertEqual(retry.status.value, "duplicate")
                    self.assertEqual(
                        self.approval_store.load(approval.approval_id).status,
                        decision,
                    )
                    self.assertEqual(self.jobs.show(approval.job_id)["status"], job_status)
                    self.assertEqual(persist_decision.call_count, 1)
                    self.assertEqual(
                        emitter.resolved,
                        [(approval.approval_id, decision)],
                    )

    def test_z84_incomplete_remote_records_are_retention_protected(self) -> None:
        for command_type, decision in (
            (RemoteCommandType.APPROVE, "APPROVED"),
            (RemoteCommandType.REJECT, "REJECTED"),
        ):
            with self.subTest(decision=decision):
                _, approval = self.pending_approval()
                emitter = RecordingApprovalEmitter()
                approvals = ApprovalRuntime(
                    self.jobs,
                    self.approval_store,
                    clock=self.clock,
                    notification_emitter=emitter,
                )
                state_root = self.root / f"retention-{decision.lower()}"
                store = FileRemoteCommandStore(state_root, max_records=1)
                service = RemoteCommandService(
                    jobs=self.jobs,
                    approvals=approvals,
                    store=store,
                    config=self.config,
                    clock=self.clock,
                )
                command = self.command(
                    command_type,
                    command_id=f"retention-{decision.lower()}",
                    approval_id=approval.approval_id,
                    authorization_fingerprint=approval.authorization_fingerprint,
                )
                with patch.object(
                    self.jobs,
                    "apply_approval_resolution",
                    side_effect=JobRuntimeError("simulated downstream failure"),
                ):
                    service.handle(command, self.identity())
                self.assertEqual(
                    store.list()[0]["audit_state"], "RECONCILIATION_REQUIRED"
                )

                restarted = RemoteCommandService(
                    jobs=self.jobs,
                    approvals=approvals,
                    store=FileRemoteCommandStore(state_root, max_records=1),
                    config=self.config,
                    clock=self.clock,
                )
                with self.assertRaisesRegex(
                    RemoteCommandServiceError, "capacity.*incomplete"
                ):
                    restarted.handle(
                        self.command(
                            RemoteCommandType.STATUS,
                            command_id=f"retention-{decision.lower()}-status",
                        ),
                        self.identity(),
                    )
                self.assertEqual(
                    store.list()[0]["audit_state"], "RECONCILIATION_REQUIRED"
                )

                retry = restarted.handle(command, self.identity())
                self.assertEqual(retry.status.value, "duplicate")
                self.assertEqual(store.list()[0]["audit_state"], "COMPLETED")
                self.assertEqual(
                    emitter.resolved,
                    [(approval.approval_id, decision)],
                )

                terminal = restarted.handle(
                    self.command(
                        RemoteCommandType.STATUS,
                        command_id=f"retention-{decision.lower()}-terminal",
                    ),
                    self.identity(),
                )
                self.assertEqual(terminal.status.value, "accepted")
                self.assertEqual(len(store.list()), 1)
                self.assertEqual(
                    store.list()[0]["command_id"],
                    f"retention-{decision.lower()}-terminal",
                )

    def test_z85_authorized_and_attempted_records_survive_capacity_churn(self) -> None:
        _, approval = self.pending_approval()
        authorized_store = RecordingRemoteStore(
            self.root / "authorized-retention",
            max_records=1,
            fail_update=1,
        )
        authorized_service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=authorized_store,
            config=self.config,
            clock=self.clock,
        )
        with self.assertRaises(RemoteCommandServiceError):
            authorized_service.handle(
                self.command(
                    RemoteCommandType.APPROVE,
                    command_id="authorized-retention",
                    approval_id=approval.approval_id,
                    authorization_fingerprint=approval.authorization_fingerprint,
                ),
                self.identity(),
            )
        self.assertEqual(authorized_store.list()[0]["audit_state"], "AUTHORIZED")
        with self.assertRaisesRegex(RemoteCommandServiceError, "capacity.*incomplete"):
            authorized_service.handle(
                self.command(
                    RemoteCommandType.STATUS,
                    command_id="authorized-retention-status",
                ),
                self.identity(),
            )
        self.assertEqual(authorized_store.list()[0]["audit_state"], "AUTHORIZED")

        _, attempted_approval = self.pending_approval()
        attempted_store = FileRemoteCommandStore(
            self.root / "attempted-retention", max_records=1
        )
        attempted_service = RemoteCommandService(
            jobs=self.jobs,
            approvals=self.approvals,
            store=attempted_store,
            config=self.config,
            clock=self.clock,
        )
        attempted_command = self.command(
            RemoteCommandType.APPROVE,
            command_id="attempted-retention",
            approval_id=attempted_approval.approval_id,
            authorization_fingerprint=attempted_approval.authorization_fingerprint,
        )
        with patch.object(
            self.approvals,
            "resolve",
            side_effect=KeyboardInterrupt("simulated pre-mutation interruption"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                attempted_service.handle(attempted_command, self.identity())
        with self.assertRaisesRegex(RemoteCommandServiceError, "capacity.*incomplete"):
            attempted_service.handle(
                self.command(
                    RemoteCommandType.STATUS,
                    command_id="attempted-retention-status",
                ),
                self.identity(),
            )
        self.assertEqual(
            attempted_store.list()[0]["audit_state"], "MUTATION_ATTEMPTED"
        )

    def test_z9_tracked_remote_example_is_safe_and_loadable(self) -> None:
        config = RemoteRuntimeConfig.from_file(
            REPOSITORY_ROOT / "config" / "remote.example.json"
        )
        self.assertEqual(config.allowed_clock_skew_seconds, 30)
        self.assertEqual(config.users[0].permissions, (RemotePermission.READ_STATUS,))
        self.assertEqual(config.users[0].approval_scope.allowed_actions, ())


if __name__ == "__main__":
    unittest.main()
