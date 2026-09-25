from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.approvals.runtime import ApprovalRuntime
from runtime.approvals.store import FileApprovalStore
from runtime.cli.__main__ import run
from runtime.core.jobs import JobRuntime
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionRequest
from runtime.providers.adapters import CliProviderAdapter, build_provider_environment
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import (
    CliProviderConfig,
    ProviderConfigError,
    ProviderConfiguration,
)
from runtime.providers.context import ExecutionContextBuilder
from runtime.providers.executor import ProviderExecutor
from runtime.providers.models import (
    ProviderAvailability,
    ProviderExecutionResult,
)
from runtime.providers.routing import ProviderRouter
from runtime.storage.execution_store import FileExecutionStore
from runtime.workers.worker import Worker


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeAdapter:
    def __init__(
        self,
        provider_id: str,
        *,
        available: bool,
        result: ProviderExecutionResult | None = None,
    ) -> None:
        self.provider_id = provider_id
        self.available = available
        self.result = result or ProviderExecutionResult(
            status="succeeded",
            stdout=f"{provider_id} output",
            stderr="",
            exit_code=0,
        )
        self.calls: list[tuple[ExecutionRequest, object]] = []

    def is_available(self) -> ProviderAvailability:
        return ProviderAvailability(
            self.available,
            "fake_available" if self.available else "fake_unavailable",
            f"C:/fake/{self.provider_id}.exe" if self.available else None,
        )

    def execute(self, request: ExecutionRequest, context: object) -> ProviderExecutionResult:
        self.calls.append((request, context))
        return self.result


def request(**overrides: object) -> ExecutionRequest:
    values: dict[str, object] = {
        "execution_id": "execution-provider-001",
        "job_id": "job-provider-001",
        "task": "Return a concise repository assessment",
        "task_class": "software",
        "project_id": None,
        "agent": "software",
        "skill": None,
        "workflow": "software",
        "capability": "software_implementation",
        "provider": None,
        "risk_level": "low",
        "input_refs": (),
        "context_refs": (
            {
                "ref_type": "file",
                "ref": "agents/software/ROLE.md",
                "description": "Canonical software role",
            },
            {
                "ref_type": "file",
                "ref": "agents/software/GUARDRAILS.md",
                "description": "Canonical software guardrails",
            },
            {
                "ref_type": "file",
                "ref": "orchestrator/workflows/software.yaml",
                "description": "Canonical software workflow",
            },
        ),
        "review_required": False,
        "attempt": 1,
        "approval_status": "not_required",
    }
    values.update(overrides)
    return ExecutionRequest(**values)  # type: ignore[arg-type]


class ProviderRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = ProviderConfiguration(REPOSITORY_ROOT)

    def router(self, *, claude: bool, codex: bool) -> ProviderRouter:
        return ProviderRouter(
            self.configuration,
            {
                "claude": FakeAdapter("claude", available=claude),
                "codex": FakeAdapter("codex", available=codex),
            },
        )

    def test_a_capability_resolves_an_eligible_provider(self) -> None:
        selection = self.router(claude=True, codex=True).resolve("planning", None)
        self.assertEqual(selection.actual_provider, "claude")
        self.assertEqual(selection.preferred_provider, "claude")

    def test_b_preferred_available_is_selected(self) -> None:
        selection = self.router(claude=True, codex=True).resolve(
            "software_implementation", None
        )
        self.assertEqual(selection.actual_provider, "codex")
        self.assertFalse(selection.fallback_used)

    def test_c_unavailable_preference_uses_canonical_fallback(self) -> None:
        selection = self.router(claude=False, codex=True).resolve("planning", None)
        self.assertEqual(selection.preferred_provider, "claude")
        self.assertEqual(selection.actual_provider, "codex")
        self.assertTrue(selection.fallback_used)
        self.assertEqual(selection.fallback_reason, "preferred_provider_unavailable")

    def test_d_both_unavailable_is_explicit(self) -> None:
        selection = self.router(claude=False, codex=False).resolve("planning", None)
        self.assertIsNone(selection.actual_provider)
        self.assertEqual(selection.fallback_reason, "no_provider_available")

    def test_e_requested_provider_falls_back_without_changing_capability(self) -> None:
        selection = self.router(claude=False, codex=True).resolve("planning", "claude")
        self.assertEqual(selection.requested_provider, "claude")
        self.assertEqual(selection.actual_provider, "codex")
        self.assertEqual(
            self.configuration.weight(selection.actual_provider, "planning"), 30
        )


class SandboxMetadataParserTests(unittest.TestCase):
    def test_exact_and_bounded_workspace_write_metadata_are_normalized(self) -> None:
        values = (
            "sandbox: workspace-write",
            "sandbox: workspace-write [workdir]",
            "sandbox: workspace-write [workdir, /tmp, $TMPDIR]",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    CliProviderAdapter._codex_effective_sandbox(value),
                    "workspace-write",
                )

    def test_exact_and_bounded_read_only_metadata_are_normalized(self) -> None:
        for value in ("sandbox: read-only", "sandbox: read-only [workdir]"):
            with self.subTest(value=value):
                self.assertEqual(
                    CliProviderAdapter._codex_effective_sandbox(value), "read-only"
                )

    def test_danger_full_access_is_recognized_for_mismatch_detection(self) -> None:
        self.assertEqual(
            CliProviderAdapter._codex_effective_sandbox(
                "sandbox: danger-full-access"
            ),
            "danger-full-access",
        )

    def test_unknown_missing_malformed_and_false_substrings_are_rejected(self) -> None:
        values = (
            "sandbox: unknown-mode",
            "sandbox:",
            "no sandbox metadata",
            "sandbox: workspace-write [workdir",
            "sandbox: workspace-write [work[dir]]",
            "sandbox: workspace-write-extra",
            "sandbox: foo-workspace-write",
            "sandbox: not-workspace-write",
            "sandbox: workspace-write [" + ("x" * 1025) + "]",
        )
        for value in values:
            with self.subTest(value=value):
                self.assertIsNone(
                    CliProviderAdapter._codex_effective_sandbox(value)
                )

    def test_harmless_outer_whitespace_is_accepted(self) -> None:
        self.assertEqual(
            CliProviderAdapter._codex_effective_sandbox(
                "  sandbox: workspace-write [workdir]  "
            ),
            "workspace-write",
        )


class CliAdapterTests(unittest.TestCase):
    @staticmethod
    def config(**overrides: object) -> CliProviderConfig:
        values: dict[str, object] = {
            "provider_id": "codex",
            "adapter": "local_cli",
            "executable": "codex",
            "arguments": (
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--sandbox",
                "read-only",
                "-",
            ),
            "timeout_seconds": 30,
            "max_stdout_bytes": 128,
            "max_stderr_bytes": 128,
        }
        values.update(overrides)
        return CliProviderConfig(**values)  # type: ignore[arg-type]

    def test_f_timeout_is_classified_without_real_provider_call(self) -> None:
        def timeout_runner(*args: object, **kwargs: object) -> object:
            raise subprocess.TimeoutExpired(args[0], 30, output="partial")

        adapter = CliProviderAdapter(
            self.config(),
            REPOSITORY_ROOT,
            runner=timeout_runner,
            which=lambda _: "C:/fake/codex.exe",
        )
        result = adapter.execute(
            request(), ExecutionContextBuilder(REPOSITORY_ROOT).build(request())
        )
        self.assertEqual(result.error_category, "provider_timeout")
        self.assertEqual(result.stdout, "partial")

    def test_g_nonzero_exit_and_stderr_are_normalized(self) -> None:
        def failed_runner(*args: object, **kwargs: object) -> object:
            return SimpleNamespace(
                returncode=7,
                stdout="partial output",
                stderr="OPENAI_API_KEY=TEST_SENTINEL_VALUE",
            )

        adapter = CliProviderAdapter(
            self.config(),
            REPOSITORY_ROOT,
            runner=failed_runner,
            which=lambda _: "C:/fake/codex.exe",
        )
        result = adapter.execute(
            request(), ExecutionContextBuilder(REPOSITORY_ROOT).build(request())
        )
        self.assertEqual(result.error_category, "provider_execution_failed")
        self.assertEqual(result.exit_code, 7)
        self.assertNotIn("TEST_SENTINEL_VALUE", result.stderr)
        self.assertIn("[REDACTED]", result.stderr)

    def test_h_task_is_stdin_not_an_option_and_shell_is_false(self) -> None:
        captured: dict[str, object] = {}

        def runner(arguments: list[str], **kwargs: object) -> object:
            captured["arguments"] = arguments
            captured.update(kwargs)
            return SimpleNamespace(
                returncode=0,
                stdout="safe output",
                stderr="OpenAI Codex test\n--------\nsandbox: read-only\n--------\n",
            )

        malicious = "--dangerously-bypass-approvals-and-sandbox; Remove-Item -Recurse"
        execution_request = request(task=malicious)
        adapter = CliProviderAdapter(
            self.config(),
            REPOSITORY_ROOT,
            runner=runner,
            which=lambda _: "C:/fake/codex.exe",
        )
        result = adapter.execute(
            execution_request,
            ExecutionContextBuilder(REPOSITORY_ROOT).build(execution_request),
        )
        self.assertEqual(result.status, "succeeded")
        self.assertFalse(captured["shell"])
        self.assertNotIn(malicious, captured["arguments"])
        self.assertNotIn("--skip-git-repo-check", captured["arguments"])
        self.assertIn(malicious, str(captured["input"]))
        self.assertEqual(
            captured["arguments"],
            [
                "C:/fake/codex.exe",
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--sandbox",
                "read-only",
                "-",
            ],
        )

    def test_h1_provider_child_environment_is_default_deny(self) -> None:
        captured: dict[str, object] = {}

        def runner(arguments: list[str], **kwargs: object) -> object:
            captured.update(kwargs)
            return SimpleNamespace(
                returncode=0,
                stdout="safe output",
                stderr="sandbox: read-only",
            )

        with tempfile.TemporaryDirectory() as temporary:
            credential_root = Path(temporary) / "provider-credentials"
            parent_environment = {
                "PATH": "C:/safe/bin",
                "PATHEXT": ".EXE;.CMD",
                "SYSTEMROOT": "C:/Windows",
                "WINDIR": "C:/Windows",
                "TEMP": str(Path(temporary) / "temp"),
                "HOME": "C:/Users/shared",
                "USERPROFILE": "C:/Users/shared",
                "LANG": "en_GB.UTF-8",
                "AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT": str(credential_root),
                "AGENT_COMPANY_TELEGRAM_BOT_TOKEN": "telegram-private",
                "WEBHOOK_SIGNING_SECRET": "webhook-private",
                "SYNTHETIC_UNRELATED_SECRET": "unrelated-private",
                "OPENAI_API_KEY": "codex-private",
                "CODEX_HOME": "C:/wrong/codex-home",
                "ANTHROPIC_API_KEY": "claude-private",
                "CLAUDE_CONFIG_DIR": "C:/wrong/claude-home",
            }
            adapter = CliProviderAdapter(
                self.config(),
                REPOSITORY_ROOT,
                runner=runner,
                which=lambda _: "C:/fake/codex.exe",
                environment=parent_environment,
            )
            result = adapter.execute(
                request(), ExecutionContextBuilder(REPOSITORY_ROOT).build(request())
            )

            self.assertEqual(result.status, "succeeded")
            child = captured["env"]
            self.assertIsInstance(child, dict)
            child_environment = child  # type: ignore[assignment]
            self.assertEqual(child_environment["PATH"], "C:/safe/bin")
            self.assertEqual(child_environment["SYSTEMROOT"], "C:/Windows")
            self.assertEqual(child_environment["LANG"], "en_GB.UTF-8")
            codex_home = str((credential_root / "codex").resolve())
            self.assertEqual(child_environment["CODEX_HOME"], codex_home)
            self.assertEqual(child_environment["HOME"], codex_home)
            self.assertEqual(child_environment["USERPROFILE"], codex_home)
            self.assertEqual(child_environment["OPENAI_API_KEY"], "codex-private")
            for stripped in (
                "AGENT_COMPANY_TELEGRAM_BOT_TOKEN",
                "WEBHOOK_SIGNING_SECRET",
                "SYNTHETIC_UNRELATED_SECRET",
                "ANTHROPIC_API_KEY",
                "CLAUDE_CONFIG_DIR",
                "AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT",
            ):
                self.assertNotIn(stripped, child_environment)

    def test_h1b_provider_private_environment_is_isolated_by_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            credential_root = Path(temporary) / "provider-credentials"
            source = {
                "PATH": "C:/safe/bin",
                "AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT": str(credential_root),
                "OPENAI_API_KEY": "codex-private",
                "CODEX_HOME": "C:/wrong/codex-home",
                "ANTHROPIC_API_KEY": "claude-private",
                "CLAUDE_CODE_OAUTH_TOKEN": "claude-oauth-private",
                "CLAUDE_CONFIG_DIR": "C:/wrong/claude-home",
            }

            codex = build_provider_environment("codex", source)
            claude = build_provider_environment("claude", source)

            self.assertEqual(
                codex["CODEX_HOME"], str((credential_root / "codex").resolve())
            )
            self.assertNotIn("ANTHROPIC_API_KEY", codex)
            self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", codex)
            self.assertNotIn("CLAUDE_CONFIG_DIR", codex)

            self.assertEqual(
                claude["CLAUDE_CONFIG_DIR"],
                str((credential_root / "claude").resolve()),
            )
            self.assertEqual(claude["ANTHROPIC_API_KEY"], "claude-private")
            self.assertNotIn("OPENAI_API_KEY", claude)
            self.assertNotIn("CODEX_HOME", claude)

    def test_h2_read_only_rejects_more_permissive_effective_modes(self) -> None:
        for effective in ("workspace-write", "danger-full-access"):
            with self.subTest(effective=effective):
                adapter = CliProviderAdapter(
                    self.config(),
                    REPOSITORY_ROOT,
                    runner=lambda *args, **kwargs: SimpleNamespace(
                        returncode=0,
                        stdout="claimed success",
                        stderr=f"OpenAI Codex test\n--------\nsandbox: {effective}\n--------\n",
                    ),
                    which=lambda _: "C:/fake/codex.exe",
                )
                result = adapter.execute(
                    request(), ExecutionContextBuilder(REPOSITORY_ROOT).build(request())
                )
                self.assertEqual(result.error_category, "provider_sandbox_mismatch")
                self.assertEqual(result.requested_sandbox_mode, "read-only")
                self.assertEqual(result.effective_sandbox_mode, effective)

    def test_h3_read_only_without_parseable_metadata_fails_closed(self) -> None:
        adapter = CliProviderAdapter(
            self.config(),
            REPOSITORY_ROOT,
            runner=lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout="claimed success", stderr="sandbox: unknown-mode"
            ),
            which=lambda _: "C:/fake/codex.exe",
        )
        result = adapter.execute(
            request(), ExecutionContextBuilder(REPOSITORY_ROOT).build(request())
        )
        self.assertEqual(result.error_category, "provider_sandbox_unverified")
        self.assertEqual(result.requested_sandbox_mode, "read-only")
        self.assertIsNone(result.effective_sandbox_mode)

    def test_i_windows_detection_prefers_native_executable(self) -> None:
        lookups: list[str] = []

        def which(candidate: str) -> str | None:
            lookups.append(candidate)
            if candidate == "codex.exe":
                return "C:/native/codex.exe"
            return "C:/shim/codex.cmd"

        adapter = CliProviderAdapter(
            self.config(), REPOSITORY_ROOT, runner=lambda *a, **k: None, which=which
        )
        availability = adapter.is_available()
        self.assertTrue(availability.available)
        if lookups[0] == "codex.exe":
            self.assertEqual(availability.executable_path, "C:/native/codex.exe")

    def test_i2_arbitrary_executable_is_rejected(self) -> None:
        with self.assertRaisesRegex(ProviderConfigError, "unsupported executable"):
            CliProviderAdapter(
                self.config(executable="C:/arbitrary/provider.exe"),
                REPOSITORY_ROOT,
                runner=lambda *args, **kwargs: None,
                which=lambda _: "C:/arbitrary/provider.exe",
            )

    def test_i3_controlled_write_requires_windows_sandbox_override(self) -> None:
        insecure = (
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "-",
        )
        with self.assertRaisesRegex(
            ProviderConfigError, "unsupported controlled-write configuration"
        ):
            CliProviderAdapter(
                self.config(controlled_write_arguments=insecure),
                REPOSITORY_ROOT,
                runner=lambda *args, **kwargs: None,
                which=lambda _: "C:/fake/codex.exe",
            )


class ProviderExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.configuration = ProviderConfiguration(REPOSITORY_ROOT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def executor(
        self, *, claude: FakeAdapter, codex: FakeAdapter
    ) -> ProviderExecutor:
        return ProviderExecutor(
            ProviderRouter(
                self.configuration,
                {"claude": claude, "codex": codex},
            ),
            ExecutionContextBuilder(REPOSITORY_ROOT),
            FileProviderArtifactStore(self.root / "provider-output"),
        )

    def test_j_output_is_referenced_and_trace_is_persisted(self) -> None:
        claude = FakeAdapter("claude", available=False)
        codex = FakeAdapter("codex", available=True)
        result = self.executor(claude=claude, codex=codex).execute(
            request(provider="claude")
        )
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.provider, "codex")
        self.assertTrue(result.fallback_used)
        self.assertNotIn("codex output", result.summary or "")
        artifact = json.loads(
            (self.root / "provider-output" / "execution-provider-001.provider.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(artifact["process"]["stdout"], "codex output")
        self.assertEqual(artifact["selection"]["requested_provider"], "claude")
        self.assertEqual(artifact["selection"]["actual_provider"], "codex")

    def test_j2_provider_artifact_persists_sandbox_diagnostics(self) -> None:
        store = FileProviderArtifactStore(self.root / "provider-output")
        selection = self.configuration.provider_ids
        self.assertIn("codex", selection)
        ref = store.create(
            "execution-sandbox-diagnostics",
            SimpleNamespace(
                requested_provider="codex",
                preferred_provider="codex",
                actual_provider="codex",
                fallback_used=False,
                fallback_reason=None,
                execution_mode="CONTROLLED_WRITE",
            ),
            ProviderExecutionResult(
                status="failed",
                stdout="",
                stderr="sandbox: read-only",
                exit_code=0,
                error_category="provider_sandbox_mismatch",
                error_message="mismatch",
                requested_sandbox_mode="workspace-write",
                effective_sandbox_mode="read-only",
            ),
        )
        self.assertEqual(ref["ref"], "runtime-provider-output:execution-sandbox-diagnostics")
        artifact = store.load("execution-sandbox-diagnostics")
        self.assertEqual(
            artifact["process"]["requested_sandbox_mode"], "workspace-write"
        )
        self.assertEqual(artifact["process"]["effective_sandbox_mode"], "read-only")

    def test_k_fallback_preserves_canonical_identity(self) -> None:
        claude = FakeAdapter("claude", available=False)
        codex = FakeAdapter("codex", available=True)
        original = request(
            provider="claude",
            agent="software",
            skill="review",
            workflow="software",
            capability="software_implementation",
        )
        self.executor(claude=claude, codex=codex).execute(original)
        delegated, package = codex.calls[0]
        self.assertEqual(delegated.agent, original.agent)
        self.assertEqual(delegated.skill, original.skill)
        self.assertEqual(delegated.workflow, original.workflow)
        self.assertEqual(delegated.capability, original.capability)
        self.assertEqual(package.agent, original.agent)
        self.assertEqual(package.capability, original.capability)

    def test_l_no_provider_available_returns_traceable_failure(self) -> None:
        result = self.executor(
            claude=FakeAdapter("claude", available=False),
            codex=FakeAdapter("codex", available=False),
        ).execute(request())
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "provider_unavailable")
        self.assertEqual(result.fallback_reason, "no_provider_available")

    def test_m_context_builder_loads_only_resolved_project_context(self) -> None:
        resolver = CanonicalReferenceResolver(REPOSITORY_ROOT)
        job = {
            "agent": "project-manager",
            "skill": None,
            "workflow": "project-continuation",
            "capability": "planning",
            "project_id": "brightshore",
        }
        execution_request = request(
            task_class="project-continuation",
            project_id="brightshore",
            agent="project-manager",
            workflow="project-continuation",
            capability="planning",
            context_refs=resolver.resolve(job),
        )
        package = ExecutionContextBuilder(REPOSITORY_ROOT).build(execution_request)
        refs = {entry.ref for entry in package.context}
        self.assertIn("CONSTITUTION.md", refs)
        self.assertIn("agents/project-manager/ROLE.md", refs)
        self.assertIn("shared/projects/brightshore/PROJECT_STATE.md", refs)
        self.assertNotIn("agents/software/ROLE.md", refs)
        self.assertFalse(any(ref.startswith("shared/knowledge/") for ref in refs))

    def test_n_provider_success_enters_reviewing_and_keeps_approval_gate(self) -> None:
        job_root = self.root / "jobs"
        execution_root = self.root / "executions"
        runtime = JobRuntime(job_root)
        codex = FakeAdapter("codex", available=True)
        executor = self.executor(
            claude=FakeAdapter("claude", available=False), codex=codex
        )
        payload = {
            "task": "Prepare a bounded review artifact",
            "task_class": "software",
            "agent": "software",
            "workflow": "software",
            "capability": "software_implementation",
            "provider": "codex",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": True,
            "input_refs": [],
            "output_refs": [],
            "max_attempts": 1,
            "created_by": "provider-test",
        }
        created = runtime.create(payload)
        runtime.enqueue(created["job_id"])
        outcome = Worker(
            runtime,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor,
            FileExecutionStore(execution_root),
        ).run_once()
        self.assertEqual(outcome.status, "reviewing")
        self.assertEqual(runtime.show(created["job_id"])["status"], "reviewing")

        approval_payload = dict(payload)
        approval_payload.update(
            {
                "task": "Approval-gated provider task",
                "approval_status": "required",
                "review_required": False,
            }
        )
        gated = runtime.create(approval_payload)
        ApprovalRuntime(
            runtime,
            FileApprovalStore(self.root / "approvals"),
        ).request_execution(
            gated["job_id"], reason="Provider execution requires approval"
        )
        calls_before = len(codex.calls)
        no_work = Worker(
            runtime,
            CanonicalReferenceResolver(REPOSITORY_ROOT),
            executor,
            FileExecutionStore(execution_root),
        ).run_once()
        self.assertEqual(no_work.status, "no_work")
        self.assertEqual(len(codex.calls), calls_before)


class ProviderCliTests(unittest.TestCase):
    def test_o_provider_status_emits_availability_without_execution(self) -> None:
        configuration = ProviderConfiguration(REPOSITORY_ROOT)
        fake_router = ProviderRouter(
            configuration,
            {
                "claude": FakeAdapter("claude", available=False),
                "codex": FakeAdapter("codex", available=True),
            },
        )
        output = io.StringIO()
        with patch(
            "runtime.cli.__main__.build_provider_router", return_value=fake_router
        ), redirect_stdout(output):
            exit_code = run(["provider", "status"])
        self.assertEqual(exit_code, 0)
        value = json.loads(output.getvalue())
        self.assertEqual(value[0]["provider_id"], "claude")
        self.assertFalse(value[0]["available"])
        self.assertEqual(value[1]["provider_id"], "codex")
        self.assertTrue(value[1]["available"])

    def test_p_provider_artifacts_are_git_ignored(self) -> None:
        candidate = (
            REPOSITORY_ROOT
            / "runtime"
            / "state"
            / "executions"
            / "provider-output"
            / "probe.provider.json"
        )
        result = subprocess.run(
            ["git", "check-ignore", str(candidate)],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
