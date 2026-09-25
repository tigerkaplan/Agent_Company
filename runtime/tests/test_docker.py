from __future__ import annotations

import json
import io
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from runtime.host.config import HostConfig
from runtime.host.healthcheck import run as run_healthcheck


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Phase8DDockerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.dockerignore = (REPOSITORY_ROOT / ".dockerignore").read_text(
            encoding="utf-8"
        )
        cls.compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")

    def service_block(self, name: str) -> str:
        match = re.search(
            rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|^[a-z])",
            self.compose,
        )
        self.assertIsNotNone(match, name)
        return match.group(1)

    def test_a_dockerfile_is_non_root_and_uses_fixed_cli_entrypoint(self) -> None:
        self.assertIn("FROM ${PYTHON_IMAGE}", self.dockerfile)
        self.assertIn("USER 10001:10001", self.dockerfile)
        self.assertIn(
            'ENTRYPOINT ["python", "-m", "runtime.cli"]', self.dockerfile
        )
        self.assertNotIn("ENTRYPOINT [\"/bin/sh\"", self.dockerfile)
        self.assertNotIn("ENTRYPOINT [\"sh\"", self.dockerfile)

    def test_b_dockerfile_contains_no_secret_or_local_state_input(self) -> None:
        forbidden = (
            "AGENT_COMPANY_TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "remote.local.json",
            "webhooks.local.json",
            "host.local.json",
        )
        for value in forbidden:
            self.assertNotIn(value, self.dockerfile)
        self.assertNotRegex(self.dockerfile, r"(?m)^COPY\s+.*\s\.\s*$")
        self.assertNotRegex(self.dockerfile, r"(?i)COPY\s+.*runtime/state")
        for required in (
            "CONSTITUTION.md",
            "agents ./agents",
            "orchestrator ./orchestrator",
            "runtime ./runtime",
            "schemas ./schemas",
            "shared ./shared",
            "skills ./skills",
        ):
            self.assertIn(required, self.dockerfile)

    def test_c_dockerignore_excludes_sensitive_and_generated_paths(self) -> None:
        required = (
            ".git/",
            ".env",
            ".env.*",
            "secrets/",
            "credentials/",
            "provider-credentials/",
            "runtime/state/",
            "config/*.local.json",
            "__pycache__/",
            "*.py[cod]",
            ".pytest_cache/",
            ".vscode/",
            "logs/",
            "tmp/",
        )
        for value in required:
            self.assertIn(value, self.dockerignore)

    def test_d_compose_has_only_fixed_canonical_services(self) -> None:
        service_names = re.findall(r"(?m)^  ([a-z][a-z0-9-]*):$", self.compose)
        service_section = self.compose.split("services:\n", 1)[1].split(
            "\nvolumes:\n", 1
        )[0]
        service_names = re.findall(
            r"(?m)^  ([a-z][a-z0-9-]*):$", service_section
        )
        self.assertEqual(service_names, ["scheduler", "telegram", "webhook-local"])
        self.assertIn('command: ["host", "run", "scheduler"]', self.compose)
        self.assertIn('command: ["host", "run", "telegram"]', self.compose)
        self.assertIn('command: ["host", "run", "webhook-local"]', self.compose)

    def test_e_services_share_one_persistent_canonical_state_volume(self) -> None:
        self.assertEqual(
            self.compose.count("agent-company-state:/var/lib/agent-company"),
            1,
        )
        self.assertEqual(
            self.compose.count("AGENT_COMPANY_STATE_ROOT=/var/lib/agent-company"),
            3,
        )
        self.assertRegex(self.compose, r"(?m)^volumes:\n  agent-company-state:$")

    def test_f_no_service_exposes_ports_or_weakens_container_isolation(self) -> None:
        forbidden = (
            "ports:",
            "privileged:",
            "network_mode:",
            "pid:",
            "/var/run/docker.sock",
            "0.0.0.0",
        )
        for value in forbidden:
            self.assertNotIn(value, self.compose)
        self.assertIn("cap_drop:\n    - ALL", self.compose)
        self.assertIn("no-new-privileges:true", self.compose)
        self.assertIn('restart: "no"', self.compose)

    def test_g_webhook_is_optional_and_has_no_public_mapping(self) -> None:
        block = self.service_block("webhook-local")
        self.assertIn('profiles: ["webhook-local"]', block)
        self.assertNotIn("ports:", block)

    def test_h_telegram_token_is_passed_only_by_environment_name(self) -> None:
        block = self.service_block("telegram")
        self.assertIn("- AGENT_COMPANY_TELEGRAM_BOT_TOKEN", block)
        self.assertNotRegex(
            block,
            r"AGENT_COMPANY_TELEGRAM_BOT_TOKEN\s*=\s*[^\s$]",
        )
        self.assertNotRegex(self.compose, r"[0-9]{5,}:[A-Za-z0-9_-]{20,}")

    def test_i_service_healthchecks_are_fixed_and_service_local(self) -> None:
        for process in ("scheduler", "telegram", "webhook-local"):
            self.assertIn(
                f'["CMD", "python", "-m", "runtime.host.healthcheck", "{process}"]',
                self.service_block(process),
            )

    def test_j_container_host_configs_are_strict_and_fail_closed(self) -> None:
        expected = {
            "scheduler": (True, False, False),
            "telegram": (False, True, False),
            "webhook-local": (False, False, True),
        }
        for name, enabled in expected.items():
            path = REPOSITORY_ROOT / "infrastructure" / "docker" / f"host.{name}.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            config = HostConfig.from_dict(value)
            self.assertEqual(config.environment_mode, "host")
            self.assertEqual(config.state_root, "/var/lib/agent-company")
            self.assertFalse(config.provider_execution_enabled)
            self.assertFalse(config.notifications_enabled)
            self.assertFalse(config.git_enabled)
            self.assertEqual(
                (config.scheduler_enabled, config.telegram_enabled, config.webhook_enabled),
                enabled,
            )

    def test_k_healthcheck_reads_lifecycle_evidence_without_pid_output(self) -> None:
        controller = Mock()
        controller.status.return_value = {
            "processes": [
                {
                    "process_type": "scheduler",
                    "enabled": True,
                    "state": "RUNNING",
                    "singleton_lock_held": True,
                    "heartbeat_stale": False,
                    "stale_record": False,
                    "pid": 123,
                    "owner_token": "must-not-be-rendered",
                }
            ]
        }
        output = io.StringIO()
        with patch(
            "runtime.host.healthcheck.HostProcessController",
            return_value=controller,
        ), patch(
            "runtime.host.healthcheck.StatePaths.resolve", return_value=Mock()
        ), redirect_stdout(output):
            exit_code = run_healthcheck(["scheduler"])

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn('"healthy": true', rendered)
        self.assertNotIn("pid", rendered)
        self.assertNotIn("owner_token", rendered)
        self.assertNotIn("must-not-be-rendered", rendered)

    def test_l_healthcheck_fails_closed_for_stale_process(self) -> None:
        controller = Mock()
        controller.status.return_value = {
            "processes": [
                {
                    "process_type": "scheduler",
                    "enabled": True,
                    "state": "RUNNING",
                    "singleton_lock_held": True,
                    "heartbeat_stale": True,
                    "stale_record": True,
                }
            ]
        }
        with patch(
            "runtime.host.healthcheck.HostProcessController",
            return_value=controller,
        ), patch(
            "runtime.host.healthcheck.StatePaths.resolve", return_value=Mock()
        ), redirect_stdout(io.StringIO()):
            exit_code = run_healthcheck(["scheduler"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
