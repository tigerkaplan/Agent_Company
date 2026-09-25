from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from runtime.cli.__main__ import run
from runtime.host.config import HostConfig, HostConfigError
from runtime.host.paths import StatePathError, StatePaths
from runtime.host.service import HostReadinessError, HostReadinessService


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def config_value(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 1,
        "environment_mode": "local",
        "state_root": None,
        "secret_file": None,
        "provider_execution_enabled": False,
        "provider_credential_root": None,
        "telegram_enabled": False,
        "webhook_enabled": False,
        "notifications_enabled": False,
        "scheduler_enabled": False,
        "git_enabled": False,
    }
    value.update(overrides)
    return value


class HostConfigAndPathTests(unittest.TestCase):
    def test_a_local_default_state_root(self) -> None:
        paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            HostConfig.local_default(),
            environment={},
        )

        self.assertEqual(paths.base_root, REPOSITORY_ROOT / "runtime" / "state")
        self.assertEqual(paths.path("jobs"), paths.base_root / "jobs")
        self.assertEqual(paths.path("telegram"), paths.base_root / "remote" / "telegram")
        self.assertEqual(paths.path("git"), paths.base_root / "executions" / "git")

    def test_b_explicit_external_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "agent-company-state"
            paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                cli_root=root,
                environment={},
            )

            self.assertEqual(paths.base_root, root.resolve())
            self.assertEqual(paths.source, "cli")

    def test_c_linux_style_host_root_config_parses(self) -> None:
        config = HostConfig.from_dict(
            config_value(
                environment_mode="host",
                state_root="/var/lib/agent-company",
            )
        )

        self.assertEqual(config.state_root, "/var/lib/agent-company")
        self.assertEqual(config.environment_mode, "host")

    def test_d_windows_path_support(self) -> None:
        config = HostConfig.from_dict(
            config_value(
                environment_mode="host",
                state_root=r"C:\AgentCompany\state",
                provider_credential_root=r"C:\AgentCompany\provider-home",
            )
        )

        self.assertEqual(config.state_root, r"C:\AgentCompany\state")

    def test_e_traversal_is_rejected(self) -> None:
        with self.assertRaises(HostConfigError):
            HostConfig.from_dict(
                config_value(state_root=r"C:\safe\..\escape")
            )
        with self.assertRaises(StatePathError):
            StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                cli_root=Path("../escape"),
                environment={},
            )

    def test_f_unsafe_repo_root_is_rejected_in_host_mode(self) -> None:
        root = REPOSITORY_ROOT / "runtime" / "state"
        config = HostConfig.from_dict(
            config_value(environment_mode="host", state_root=str(root))
        )

        with self.assertRaises(StatePathError):
            StatePaths.resolve(REPOSITORY_ROOT, config, environment={})

    def test_f2_local_mode_rejects_arbitrary_source_tree_root(self) -> None:
        with self.assertRaises(StatePathError):
            StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                cli_root=REPOSITORY_ROOT / "runtime" / "host-state",
                environment={},
            )

        paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            HostConfig.local_default(),
            cli_root=REPOSITORY_ROOT / "runtime" / "state",
            environment={},
        )
        self.assertEqual(paths.base_root, REPOSITORY_ROOT / "runtime" / "state")

    def test_g_canonical_environment_precedes_legacy_component_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "canonical-state"
            legacy = Path(temporary) / "legacy-jobs"
            environment = {
                "AGENT_COMPANY_STATE_ROOT": str(root),
                "AGENT_COMPANY_RUNTIME_STATE_ROOT": str(legacy),
            }
            paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                environment=environment,
            )

            self.assertEqual(
                paths.component_root(
                    "jobs",
                    explicit=None,
                    legacy_environment_name="AGENT_COMPANY_RUNTIME_STATE_ROOT",
                    environment=environment,
                ),
                root / "jobs",
            )

    def test_h_arbitrary_layout_key_is_rejected(self) -> None:
        paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            HostConfig.local_default(),
            environment={},
        )
        with self.assertRaises(StatePathError):
            paths.path("../../escape")

    def test_h2_component_override_cannot_escape_configured_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "canonical-state"
            paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                cli_root=root,
                environment={},
            )
            with self.assertRaises(StatePathError):
                paths.component_root(
                    "jobs",
                    explicit=Path(temporary) / "outside-jobs",
                    legacy_environment_name="AGENT_COMPANY_RUNTIME_STATE_ROOT",
                    environment={},
                )

    def test_i_secret_fields_are_rejected(self) -> None:
        value = config_value()
        value["telegram_token"] = "not-allowed"
        with self.assertRaises(HostConfigError):
            HostConfig.from_dict(value)

    def test_i2_schema_version_is_a_strict_integer(self) -> None:
        for invalid in (True, False, 1.0, "1", None):
            with self.subTest(invalid=invalid), self.assertRaises(HostConfigError):
                HostConfig.from_dict(config_value(schema_version=invalid))
        self.assertEqual(
            HostConfig.from_dict(config_value(schema_version=1)).schema_version,
            1,
        )

    def test_i3_host_root_precedence_is_resolved_before_mode_validation(self) -> None:
        host = HostConfig.from_dict(
            config_value(environment_mode="host", state_root=None)
        )
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            cli = temporary_path / "cli-state"
            environment_root = temporary_path / "environment-state"
            config_root = temporary_path / "config-state"
            configured = HostConfig.from_dict(
                config_value(environment_mode="host", state_root=str(config_root))
            )

            cli_paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                configured,
                cli_root=cli,
                environment={"AGENT_COMPANY_STATE_ROOT": str(environment_root)},
            )
            self.assertEqual(cli_paths.base_root, cli.resolve())
            self.assertEqual(cli_paths.source, "cli")

            environment_paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                configured,
                environment={"AGENT_COMPANY_STATE_ROOT": str(environment_root)},
            )
            self.assertEqual(environment_paths.base_root, environment_root.resolve())
            self.assertEqual(environment_paths.source, "environment")

            cli_only = StatePaths.resolve(
                REPOSITORY_ROOT, host, cli_root=cli, environment={}
            )
            self.assertEqual(cli_only.base_root, cli.resolve())
            environment_only = StatePaths.resolve(
                REPOSITORY_ROOT,
                host,
                environment={"AGENT_COMPANY_STATE_ROOT": str(environment_root)},
            )
            self.assertEqual(environment_only.base_root, environment_root.resolve())

        with self.assertRaisesRegex(StatePathError, "explicit canonical state root"):
            StatePaths.resolve(REPOSITORY_ROOT, host, environment={})

    def test_i4_dangerous_and_broad_roots_are_rejected(self) -> None:
        rejected = (
            Path(REPOSITORY_ROOT.anchor),
            REPOSITORY_ROOT,
            REPOSITORY_ROOT.parent,
        )
        for root in rejected:
            with self.subTest(root=root), self.assertRaises(StatePathError):
                StatePaths.resolve(
                    REPOSITORY_ROOT,
                    HostConfig.local_default(),
                    cli_root=root,
                    environment={},
                )

        with tempfile.TemporaryDirectory() as temporary:
            broad_workspace = Path(temporary)
            with self.assertRaisesRegex(StatePathError, "dedicated"):
                StatePaths.resolve(
                    REPOSITORY_ROOT,
                    HostConfig.local_default(),
                    cli_root=broad_workspace,
                    environment={},
                )
            dedicated = broad_workspace / "agent-company-state"
            paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                cli_root=dedicated,
                environment={},
            )
            self.assertEqual(paths.base_root, dedicated.resolve())

    def test_i5_configured_component_paths_must_be_exactly_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "agent-company-state"
            config = HostConfig.from_dict(
                config_value(environment_mode="host", state_root=str(root))
            )
            paths = StatePaths.resolve(REPOSITORY_ROOT, config, environment={})
            canonical = paths.path("jobs")
            self.assertEqual(
                paths.component_root(
                    "jobs",
                    explicit=canonical,
                    legacy_environment_name="AGENT_COMPANY_RUNTIME_STATE_ROOT",
                    environment={},
                ),
                canonical,
            )
            with self.assertRaisesRegex(StatePathError, "canonical path"):
                paths.component_root(
                    "jobs",
                    explicit=root / "alternate" / "jobs2",
                    legacy_environment_name="AGENT_COMPANY_RUNTIME_STATE_ROOT",
                    environment={},
                )

    def test_i6_rejected_root_is_never_created_or_chmodded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "agent-company-state"
            paths = StatePaths.resolve(
                REPOSITORY_ROOT,
                HostConfig.local_default(),
                cli_root=root,
                environment={},
            )
            (root / "unrelated-workspace").mkdir(parents=True)
            service = HostReadinessService(
                HostConfig.local_default(), paths, environment={}
            )
            with patch.object(Path, "mkdir") as mkdir, patch.object(
                Path, "chmod"
            ) as chmod, self.assertRaises(HostReadinessError):
                service.initialize()
            mkdir.assert_not_called()
            chmod.assert_not_called()


class HostInitializationAndCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "state"
        self.config = HostConfig.local_default()
        self.paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            self.config,
            cli_root=self.root,
            environment={},
        )

    def service(
        self,
        *,
        config: HostConfig | None = None,
        environment: dict[str, str] | None = None,
        paths: StatePaths | None = None,
    ) -> HostReadinessService:
        return HostReadinessService(
            config or self.config,
            paths or self.paths,
            environment={} if environment is None else environment,
        )

    def test_j_host_init_creates_expected_directories(self) -> None:
        result = self.service().initialize()

        self.assertEqual(result["status"], "PASS")
        for path in self.paths.directories():
            self.assertTrue(path.is_dir(), path)

    def test_k_init_is_idempotent(self) -> None:
        self.service().initialize()
        second = self.service().initialize()

        self.assertEqual(second["created"], [])
        self.assertIn("jobs", second["existing"])

    def test_l_init_never_deletes_existing_state(self) -> None:
        jobs = self.paths.path("jobs")
        jobs.mkdir(parents=True)
        sentinel = jobs / "existing-job.json"
        sentinel.write_text('{"preserve":true}\n', encoding="utf-8")

        self.service().initialize()

        self.assertEqual(sentinel.read_text(encoding="utf-8"), '{"preserve":true}\n')

    def test_m_host_check_passes_on_valid_fixture(self) -> None:
        service = self.service()
        service.initialize()

        with patch.object(service, "detect_repository_local_state", return_value=()):
            result = service.check()

        expected = "WARN" if os.name == "nt" else "PASS"
        self.assertEqual(result["status"], expected)
        if os.name == "nt":
            permissions = next(
                item for item in result["checks"] if item["name"] == "state_permissions"
            )
            self.assertEqual(permissions["status"], "WARN")
        else:
            self.assertTrue(all(item["status"] == "PASS" for item in result["checks"]))

    def test_n_missing_root_is_detected(self) -> None:
        result = self.service().check()

        self.assertEqual(result["status"], "FAIL")
        self.assertIn(
            {"name": "state_root_exists", "status": "FAIL", "detail": "missing"},
            result["checks"],
        )

    def test_o_invalid_file_root_is_handled_safely(self) -> None:
        self.root.parent.mkdir(parents=True, exist_ok=True)
        self.root.write_text("not a directory", encoding="utf-8")

        with self.assertRaises(HostReadinessError):
            self.service().initialize()
        result = self.service().check()
        self.assertEqual(result["status"], "FAIL")

    def test_p_telegram_enabled_missing_token_fails(self) -> None:
        config = HostConfig.from_dict(config_value(telegram_enabled=True))
        environment = {
            "AGENT_COMPANY_REMOTE_CONFIG": str(
                REPOSITORY_ROOT / "config" / "remote.example.json"
            )
        }
        service = self.service(config=config, environment=environment)
        result = service.check()

        token = next(item for item in result["checks"] if item["name"] == "telegram_token")
        self.assertEqual(token["status"], "FAIL")
        self.assertEqual(token["detail"], "missing")

    def test_q_disabled_telegram_does_not_require_token(self) -> None:
        self.service().initialize()

        result = self.service().check()

        token = next(item for item in result["checks"] if item["name"] == "telegram_token")
        self.assertEqual(token, {"name": "telegram_token", "status": "PASS", "detail": "not_required"})

    def test_r_webhook_enabled_missing_secret_reference_fails(self) -> None:
        webhook_path = Path(self.temporary.name) / "webhooks.json"
        webhook_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "sources": [
                        {
                            "source_id": "fixture",
                            "enabled": True,
                            "allowed_event_types": ["TASK_SIGNAL"],
                            "authentication_mode": "HMAC_SHA256",
                            "secret_env": "HOST_TEST_WEBHOOK_SECRET",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        config = HostConfig.from_dict(config_value(webhook_enabled=True))
        environment = {"AGENT_COMPANY_WEBHOOK_CONFIG": str(webhook_path)}
        service = self.service(config=config, environment=environment)
        service.initialize()

        result = service.check()

        webhook = next(item for item in result["checks"] if item["name"] == "webhook_secrets")
        self.assertEqual(webhook["status"], "FAIL")
        self.assertNotIn("HOST_TEST_WEBHOOK_SECRET", json.dumps(result))

    def test_r2_provider_credentials_must_be_separate(self) -> None:
        credential_root = self.root / "provider-home"
        credential_root.mkdir(parents=True)
        config = HostConfig.from_dict(
            config_value(
                provider_execution_enabled=True,
                provider_credential_root=str(credential_root),
            )
        )
        service = self.service(config=config)

        result = service.check()

        credentials = next(
            item for item in result["checks"] if item["name"] == "provider_credentials"
        )
        self.assertEqual(credentials["status"], "FAIL")
        self.assertEqual(credentials["detail"], "unsafe_location")

    def test_r3_external_provider_credentials_report_permission_boundary(self) -> None:
        credential_root = Path(self.temporary.name) / "provider-home"
        credential_root.mkdir(mode=0o700)
        if os.name != "nt":
            credential_root.chmod(0o700)
        config = HostConfig.from_dict(
            config_value(
                provider_execution_enabled=True,
                provider_credential_root=str(credential_root),
            )
        )
        service = self.service(config=config)
        service.initialize()

        result = service.check()

        credentials = next(
            item for item in result["checks"] if item["name"] == "provider_credentials"
        )
        self.assertEqual(credentials["status"], "WARN" if os.name == "nt" else "PASS")
        self.assertNotIn(str(credential_root), json.dumps(credentials))

    def test_r4_provider_credential_overlap_is_rejected_both_directions(self) -> None:
        self.service().initialize()

        inside_state = self.root / "provider-credentials"
        inside_state.mkdir()
        inside_config = HostConfig.from_dict(
            config_value(
                provider_execution_enabled=True,
                provider_credential_root=str(inside_state),
            )
        )
        inside_result = self.service(config=inside_config).check()
        inside_check = next(
            item
            for item in inside_result["checks"]
            if item["name"] == "provider_credentials"
        )
        self.assertEqual(inside_check["detail"], "unsafe_location")

        credential_parent = Path(self.temporary.name) / "credential-parent"
        nested_state = credential_parent / "state"
        nested_paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            HostConfig.local_default(),
            cli_root=nested_state,
            environment={},
        )
        nested_service = HostReadinessService(
            HostConfig.local_default(), nested_paths, environment={}
        )
        nested_service.initialize()
        contains_config = HostConfig.from_dict(
            config_value(
                provider_execution_enabled=True,
                provider_credential_root=str(credential_parent),
            )
        )
        contains_result = HostReadinessService(
            contains_config, nested_paths, environment={}
        ).check()
        contains_check = next(
            item
            for item in contains_result["checks"]
            if item["name"] == "provider_credentials"
        )
        self.assertEqual(contains_check["detail"], "unsafe_location")

    def test_r5_secret_and_state_overlap_is_rejected_both_directions(self) -> None:
        self.service().initialize()
        secret_inside = self.root / "host.env"
        secret_inside.write_text("HOST_SECRET=not-inspected\n", encoding="utf-8")
        inside_config = HostConfig.from_dict(
            config_value(secret_file=str(secret_inside))
        )
        inside_result = self.service(config=inside_config).check()
        inside_check = next(
            item
            for item in inside_result["checks"]
            if item["name"] == "host_secret_file"
        )
        self.assertEqual(inside_check["detail"], "unsafe_location")

        secret_root = Path(self.temporary.name) / "host-secrets"
        nested_state = secret_root / "state"
        nested_paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            HostConfig.local_default(),
            cli_root=nested_state,
            environment={},
        )
        nested_service = HostReadinessService(
            HostConfig.local_default(), nested_paths, environment={}
        )
        nested_service.initialize()
        secret_file = secret_root / "host.env"
        secret_file.write_text("HOST_SECRET=not-inspected\n", encoding="utf-8")
        contains_config = HostConfig.from_dict(
            config_value(secret_file=str(secret_file))
        )
        contains_result = HostReadinessService(
            contains_config, nested_paths, environment={}
        ).check()
        contains_check = next(
            item
            for item in contains_result["checks"]
            if item["name"] == "host_secret_file"
        )
        self.assertEqual(contains_check["detail"], "unsafe_location")

    def test_r6_malformed_webhook_numeric_config_is_a_bounded_failure(self) -> None:
        webhook_path = Path(self.temporary.name) / "webhooks-malformed.json"
        webhook_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "replay_window_seconds": "not-an-integer",
                    "sources": [
                        {
                            "source_id": "fixture",
                            "enabled": True,
                            "allowed_event_types": ["TASK_SIGNAL"],
                            "authentication_mode": "HMAC_SHA256",
                            "secret_env": "SENSITIVE_WEBHOOK_SECRET_NAME",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        config = HostConfig.from_dict(config_value(webhook_enabled=True))
        environment = {
            "AGENT_COMPANY_WEBHOOK_CONFIG": str(webhook_path),
            "SENSITIVE_WEBHOOK_SECRET_NAME": "not-output-secret-value",
        }
        service = self.service(config=config, environment=environment)
        service.initialize()

        result = service.check()

        webhook = next(
            item for item in result["checks"] if item["name"] == "webhook_secrets"
        )
        self.assertEqual(webhook["status"], "FAIL")
        self.assertEqual(webhook["detail"], "unavailable_or_invalid")
        serialized = json.dumps(result)
        self.assertNotIn("SENSITIVE_WEBHOOK_SECRET_NAME", serialized)
        self.assertNotIn("not-output-secret-value", serialized)

    def test_r7_malformed_remote_config_is_a_bounded_failure(self) -> None:
        remote_path = Path(self.temporary.name) / "remote-malformed.json"
        remote_path.write_bytes(b"\xff\xfe\x00")
        config = HostConfig.from_dict(config_value(telegram_enabled=True))
        environment = {
            "AGENT_COMPANY_REMOTE_CONFIG": str(remote_path),
            "AGENT_COMPANY_TELEGRAM_BOT_TOKEN": "not-output-telegram-token",
        }
        service = self.service(config=config, environment=environment)
        service.initialize()

        result = service.check()

        remote = next(
            item for item in result["checks"] if item["name"] == "remote_config"
        )
        self.assertEqual(remote["status"], "FAIL")
        self.assertEqual(remote["detail"], "unavailable_or_invalid")
        self.assertNotIn("not-output-telegram-token", json.dumps(result))

    def test_r8_windows_acl_checks_never_report_false_pass(self) -> None:
        self.service().initialize()
        secret_file = Path(self.temporary.name) / "secrets" / "host.env"
        secret_file.parent.mkdir()
        secret_file.write_text("HOST_SECRET=not-inspected\n", encoding="utf-8")
        config = HostConfig.from_dict(config_value(secret_file=str(secret_file)))
        with patch("runtime.host.service._is_windows", return_value=True):
            result = self.service(config=config).check()

        state_check = next(
            item for item in result["checks"] if item["name"] == "state_permissions"
        )
        secret_check = next(
            item for item in result["checks"] if item["name"] == "host_secret_file"
        )
        self.assertEqual(state_check["status"], "WARN")
        self.assertIn("operator_validation", state_check["detail"])
        self.assertEqual(secret_check["status"], "WARN")
        self.assertIn("not_inspected", secret_check["detail"])

    def test_s_existing_local_state_is_detected_and_not_moved(self) -> None:
        fake_repository = Path(self.temporary.name) / "repository"
        local_job = fake_repository / "runtime" / "state" / "jobs" / "job.json"
        local_job.parent.mkdir(parents=True)
        local_job.write_text("{}\n", encoding="utf-8")
        external = Path(self.temporary.name) / "external-state"
        paths = StatePaths.resolve(
            fake_repository,
            HostConfig.local_default(),
            cli_root=external,
            environment={},
        )
        service = HostReadinessService(
            HostConfig.local_default(), paths, environment={}
        )

        self.assertEqual(service.detect_repository_local_state(), ("jobs",))
        service.initialize()
        self.assertTrue(local_job.is_file())
        self.assertFalse((external / "jobs" / "job.json").exists())

    def test_t_host_config_and_generated_state_are_git_ignored(self) -> None:
        for probe in (
            "config/host.local.json",
            "runtime/state/locks/probe.lock",
            "runtime/state/audit/probe.json",
            "provider-credentials/provider/token",
        ):
            result = subprocess.run(
                ["git", "check-ignore", probe],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{probe}: {result.stderr}")

        nested_source_probe = "runtime/source/provider-credentials/module.py"
        nested = subprocess.run(
            ["git", "check-ignore", nested_source_probe],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(nested.returncode, 1, nested.stdout)

    def test_u_host_cli_does_not_construct_external_clients(self) -> None:
        output = io.StringIO()
        with patch(
            "runtime.cli.__main__.TelegramBotApiClient",
            side_effect=AssertionError("host commands must not construct Telegram clients"),
        ), redirect_stdout(output):
            exit_code = run(
                ["host", "init", "--base-root", str(self.root)]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["operation"], "host_init")

    def test_v_host_check_is_read_only(self) -> None:
        self.service().initialize()
        before = sorted(
            (path.relative_to(self.root).as_posix(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*")
        )

        self.service().check()

        after = sorted(
            (path.relative_to(self.root).as_posix(), path.stat().st_mtime_ns)
            for path in self.root.rglob("*")
        )
        self.assertEqual(after, before)

    def test_w_schema_fields_match_host_config(self) -> None:
        schema = json.loads(
            (REPOSITORY_ROOT / "schemas" / "host-config.schema.json").read_text(
                encoding="utf-8"
            )
        )
        example = json.loads(
            (REPOSITORY_ROOT / "config" / "host.example.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(set(schema["required"]), set(example))
        self.assertEqual(set(schema["properties"]), set(example))
        self.assertEqual(HostConfig.from_dict(example).to_safe_dict(), example)


if __name__ == "__main__":
    unittest.main()
