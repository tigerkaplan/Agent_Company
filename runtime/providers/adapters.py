"""Safe local CLI adapters for configured execution providers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from runtime.execution.models import ExecutionRequest
from runtime.providers.config import CliProviderConfig, ProviderConfigError
from runtime.providers.models import (
    ProviderAvailability,
    ProviderExecutionResult,
)


class ProviderAdapter(Protocol):
    provider_id: str

    def is_available(self) -> ProviderAvailability:
        """Return observed local executable availability."""

    def execute(
        self,
        request: ExecutionRequest,
        context: RenderableContext,
        *,
        working_directory: Path | None = None,
    ) -> ProviderExecutionResult:
        """Execute one canonical request without changing its identity."""


Runner = Callable[..., Any]
Which = Callable[[str], str | None]


class RenderableContext(Protocol):
    def render(self) -> str:
        """Return the bounded provider prompt supplied on stdin."""

_EXPECTED_EXECUTABLES = {"codex": "codex", "claude": "claude"}
_CODEX_WINDOWS_SANDBOX_OVERRIDE = 'windows.sandbox="elevated"'
_SANDBOX_MODES = {"read-only", "workspace-write", "danger-full-access"}
_EXPECTED_ARGUMENTS = {
    "codex": {
        "READ_ONLY": (
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
            "-",
        ),
        "CONTROLLED_WRITE": (
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--config",
            _CODEX_WINDOWS_SANDBOX_OVERRIDE,
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "-",
        ),
    },
    "claude": {
        "READ_ONLY": (
            "--bare",
            "--print",
            "--permission-mode",
            "plan",
            "--no-session-persistence",
            "Execute the Agent Company package provided on stdin.",
        )
    },
}
_BASE_ENVIRONMENT_ALLOWLIST = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)
_PROVIDER_ENVIRONMENT_ALLOWLIST = {
    "codex": ("CODEX_HOME", "OPENAI_API_KEY"),
    "claude": (
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_API_KEY",
    ),
}


def build_provider_environment(
    provider_id: str,
    source: Mapping[str, str],
    *,
    temporary_root: Path | None = None,
) -> dict[str, str]:
    """Build a default-deny child environment for one provider process."""
    try:
        provider_names = _PROVIDER_ENVIRONMENT_ALLOWLIST[provider_id]
    except KeyError as error:
        raise ProviderConfigError(
            f"Provider {provider_id} has no environment allowlist"
        ) from error

    casefolded = {name.upper(): value for name, value in source.items()}
    environment = {
        name: casefolded[name]
        for name in _BASE_ENVIRONMENT_ALLOWLIST
        if name in casefolded
    }
    environment.update(
        {
            name: casefolded[name]
            for name in provider_names
            if name in casefolded
        }
    )

    configured_root = casefolded.get("AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT")
    if configured_root:
        raw_root = Path(configured_root)
        if not raw_root.is_absolute() or ".." in raw_root.parts:
            raise ProviderConfigError(
                "Provider credential root must be an absolute path without traversal"
            )
        provider_home = raw_root.resolve(strict=False) / provider_id
        environment["HOME"] = str(provider_home)
        environment["USERPROFILE"] = str(provider_home)
        if provider_id == "codex":
            environment["CODEX_HOME"] = str(provider_home)
        else:
            environment["CLAUDE_CONFIG_DIR"] = str(provider_home)

    if temporary_root is not None:
        temporary = str(Path(temporary_root).resolve())
        environment.update({"TEMP": temporary, "TMP": temporary, "TMPDIR": temporary})
    return environment


def sanitize_provider_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_SECRET]", text)
    text = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|SECRET))"
        r"\s*[:=]\s*([^\s,;]+)",
        r"\1=[REDACTED]",
        text,
    )
    return text


def bound_text(value: str, limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    marker = "\n[OUTPUT_TRUNCATED]\n"
    marker_bytes = marker.encode("utf-8")
    allowed = max(0, limit - len(marker_bytes))
    return encoded[:allowed].decode("utf-8", errors="ignore") + marker


class CliProviderAdapter:
    """Invoke one allowlisted provider executable with a configured argument array."""

    def __init__(
        self,
        config: CliProviderConfig,
        repository_root: Path,
        *,
        runner: Runner = subprocess.run,
        which: Which = shutil.which,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        expected_executable = _EXPECTED_EXECUTABLES.get(config.provider_id)
        if expected_executable is None or config.executable != expected_executable:
            raise ProviderConfigError(
                f"Provider {config.provider_id} has an unsupported executable"
            )
        if config.adapter != "local_cli":
            raise ProviderConfigError(
                f"Provider {config.provider_id} has an unsupported runtime adapter"
            )
        if config.arguments != _EXPECTED_ARGUMENTS[config.provider_id]["READ_ONLY"]:
            raise ProviderConfigError(
                f"Provider {config.provider_id} has an unsupported command configuration"
            )
        controlled = _EXPECTED_ARGUMENTS[config.provider_id].get("CONTROLLED_WRITE")
        if config.controlled_write_arguments not in {None, controlled}:
            raise ProviderConfigError(
                f"Provider {config.provider_id} has an unsupported controlled-write configuration"
            )
        self.provider_id = config.provider_id
        self.config = config
        self.repository_root = Path(repository_root).resolve()
        self.runner = runner
        self.which = which
        self.environment = os.environ if environment is None else environment

    def is_available(self) -> ProviderAvailability:
        candidates = (
            (f"{self.config.executable}.exe", self.config.executable)
            if os.name == "nt"
            else (self.config.executable,)
        )
        executable_path = next(
            (resolved for candidate in candidates if (resolved := self.which(candidate))),
            None,
        )
        if executable_path is None:
            return ProviderAvailability(False, "executable_not_found")
        return ProviderAvailability(True, "executable_found", executable_path)

    def execute(
        self,
        request: ExecutionRequest,
        context: RenderableContext,
        *,
        working_directory: Path | None = None,
    ) -> ProviderExecutionResult:
        availability = self.is_available()
        if not availability.available or availability.executable_path is None:
            return ProviderExecutionResult(
                status="failed",
                stdout="",
                stderr="",
                exit_code=None,
                error_category="provider_unavailable",
                error_message=f"Provider {self.provider_id} executable is unavailable",
            )
        try:
            configured_arguments = self.config.arguments_for(request.execution_mode)
        except ProviderConfigError as error:
            return ProviderExecutionResult(
                status="failed",
                stdout="",
                stderr="",
                exit_code=None,
                error_category="provider_unavailable",
                error_message=str(error),
            )
        cwd = self.repository_root
        if request.execution_mode == "CONTROLLED_WRITE":
            if working_directory is None:
                return ProviderExecutionResult(
                    status="failed",
                    stdout="",
                    stderr="",
                    exit_code=None,
                    error_category="write_scope_invalid",
                    error_message="Controlled write requires a runtime-owned workspace",
                )
            cwd = Path(working_directory).resolve()
            temporary_root = Path(tempfile.gettempdir()).resolve()
            try:
                cwd.relative_to(temporary_root)
            except ValueError:
                return ProviderExecutionResult(
                    status="failed",
                    stdout="",
                    stderr="",
                    exit_code=None,
                    error_category="write_scope_invalid",
                    error_message="Controlled-write workspace is not runtime-owned",
                )
            if (
                not cwd.is_dir()
                or cwd.is_symlink()
                or cwd.name != "workspace"
                or not cwd.parent.name.startswith("agent-company-write-")
            ):
                return ProviderExecutionResult(
                    status="failed",
                    stdout="",
                    stderr="",
                    exit_code=None,
                    error_category="write_scope_invalid",
                    error_message="Controlled-write workspace is not runtime-owned",
                )
        arguments = [availability.executable_path, *configured_arguments]
        try:
            environment = build_provider_environment(
                self.provider_id,
                self.environment,
                temporary_root=(
                    cwd if request.execution_mode == "CONTROLLED_WRITE" else None
                ),
            )
        except ProviderConfigError as error:
            return ProviderExecutionResult(
                status="failed",
                stdout="",
                stderr="",
                exit_code=None,
                error_category="provider_unavailable",
                error_message=str(error),
                requested_sandbox_mode=self._requested_sandbox_mode(
                    configured_arguments
                ),
            )
        run_options: dict[str, Any] = {
            "input": context.render(),
            "text": True,
            "capture_output": True,
            "timeout": self.config.timeout_seconds,
            "cwd": str(cwd),
            "shell": False,
            "check": False,
            "env": environment,
        }
        try:
            completed = self.runner(arguments, **run_options)
        except subprocess.TimeoutExpired as error:
            requested_sandbox = self._requested_sandbox_mode(configured_arguments)
            effective_sandbox = (
                self._codex_effective_sandbox(error.stderr)
                if self.provider_id == "codex"
                else None
            )
            return ProviderExecutionResult(
                status="failed",
                stdout=self._normalise(error.stdout, self.config.max_stdout_bytes),
                stderr=self._normalise(error.stderr, self.config.max_stderr_bytes),
                exit_code=None,
                error_category="provider_timeout",
                error_message=f"Provider {self.provider_id} exceeded its configured timeout",
                requested_sandbox_mode=requested_sandbox,
                effective_sandbox_mode=effective_sandbox,
            )
        except OSError:
            return ProviderExecutionResult(
                status="failed",
                stdout="",
                stderr="",
                exit_code=None,
                error_category="provider_unavailable",
                error_message=f"Provider {self.provider_id} executable could not be started",
                requested_sandbox_mode=self._requested_sandbox_mode(configured_arguments),
            )

        stdout = self._normalise(completed.stdout, self.config.max_stdout_bytes)
        stderr = self._normalise(completed.stderr, self.config.max_stderr_bytes)
        requested_sandbox = self._requested_sandbox_mode(configured_arguments)
        effective_sandbox = (
            self._codex_effective_sandbox(completed.stderr)
            if self.provider_id == "codex"
            else None
        )
        if (
            self.provider_id == "codex"
            and effective_sandbox is not None
            and effective_sandbox != requested_sandbox
        ):
            return ProviderExecutionResult(
                status="failed",
                stdout=stdout,
                stderr=stderr,
                exit_code=int(completed.returncode),
                error_category="provider_sandbox_mismatch",
                error_message=(
                    "Provider effective sandbox does not match the requested execution mode"
                ),
                requested_sandbox_mode=requested_sandbox,
                effective_sandbox_mode=effective_sandbox,
            )
        if completed.returncode != 0:
            return ProviderExecutionResult(
                status="failed",
                stdout=stdout,
                stderr=stderr,
                exit_code=int(completed.returncode),
                error_category="provider_execution_failed",
                error_message=(
                    f"Provider {self.provider_id} exited with code {completed.returncode}"
                ),
                requested_sandbox_mode=requested_sandbox,
                effective_sandbox_mode=effective_sandbox,
            )
        if self.provider_id == "codex" and effective_sandbox is None:
            return ProviderExecutionResult(
                status="failed",
                stdout=stdout,
                stderr=stderr,
                exit_code=0,
                error_category="provider_sandbox_unverified",
                error_message="Provider effective sandbox could not be verified",
                requested_sandbox_mode=requested_sandbox,
                effective_sandbox_mode=None,
            )
        if not stdout.strip():
            return ProviderExecutionResult(
                status="failed",
                stdout=stdout,
                stderr=stderr,
                exit_code=0,
                error_category="invalid_provider_output",
                error_message=f"Provider {self.provider_id} returned no output",
                requested_sandbox_mode=requested_sandbox,
                effective_sandbox_mode=effective_sandbox,
            )
        return ProviderExecutionResult(
            status="succeeded",
            stdout=stdout,
            stderr=stderr,
            exit_code=0,
            requested_sandbox_mode=requested_sandbox,
            effective_sandbox_mode=effective_sandbox,
        )

    @staticmethod
    def _normalise(value: str | bytes | None, limit: int) -> str:
        return bound_text(sanitize_provider_text(value), limit)

    @staticmethod
    def _requested_sandbox_mode(arguments: tuple[str, ...]) -> str | None:
        try:
            index = arguments.index("--sandbox")
            mode = arguments[index + 1]
        except (ValueError, IndexError):
            return None
        return mode if mode in _SANDBOX_MODES else None

    @staticmethod
    def _codex_effective_sandbox(value: str | bytes | None) -> str | None:
        if value is None:
            return None
        text = (
            value.decode("utf-8", errors="replace")
            if isinstance(value, bytes)
            else str(value)
        )
        for line in text.splitlines()[:40]:
            match = re.fullmatch(
                r"\s*sandbox:\s*(read-only|workspace-write|danger-full-access)"
                r"(?:\s+\[[^\[\]\r\n]{0,1024}\])?\s*",
                line,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()
        return None
