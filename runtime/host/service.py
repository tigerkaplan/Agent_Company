"""Deterministic host-state initialization and read-only readiness checks."""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Mapping

from runtime.host.config import HostConfig
from runtime.host.paths import EPHEMERAL_STATE_KEYS, PERSISTENT_STATE_KEYS, StatePathError, StatePaths
from runtime.providers.config import ProviderConfigError, ProviderConfiguration
from runtime.remote.config import RemoteRuntimeConfig
from runtime.remote.models import RemoteCommandError
from runtime.webhooks.config import WebhookRuntimeConfig
from runtime.webhooks.models import WebhookContractError


class HostReadinessError(ValueError):
    """Raised when host state cannot be initialized safely."""


def _is_windows() -> bool:
    return os.name == "nt"


class HostReadinessService:
    def __init__(
        self,
        config: HostConfig,
        paths: StatePaths,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.paths = paths
        self.environment = os.environ if environment is None else environment

    def initialize(self) -> dict[str, Any]:
        try:
            self.paths.validate_for_initialization()
        except StatePathError as error:
            raise HostReadinessError(str(error)) from error
        created: list[str] = []
        existing: list[str] = []
        for path in self.paths.directories():
            if path.is_symlink():
                raise HostReadinessError(
                    f"Canonical host-state path must not be a symlink: {path}"
                )
            if path.exists() and not path.is_dir():
                raise HostReadinessError(
                    f"Canonical host-state path is not a directory: {path}"
                )
            self._ensure_contained(path)
            was_present = path.is_dir()
            try:
                path.mkdir(parents=True, exist_ok=True)
                self._ensure_contained(path)
                if not _is_windows():
                    path.chmod(0o700)
            except OSError as error:
                raise HostReadinessError(
                    f"Could not initialize canonical host-state directory: {path}"
                ) from error
            relative = self._relative_label(path)
            (existing if was_present else created).append(relative)
        return {
            "status": "PASS",
            "operation": "host_init",
            "environment_mode": self.config.environment_mode,
            "state_root": str(self.paths.base_root),
            "created": created,
            "existing": existing,
            "persistent": list(PERSISTENT_STATE_KEYS),
            "ephemeral": list(EPHEMERAL_STATE_KEYS),
            "permissions": (
                "0700 applied to canonical directories"
                if not _is_windows()
                else "Windows ACLs unchanged; operator validation required"
            ),
            "migration": "not_performed",
        }

    def check(self) -> dict[str, Any]:
        checks: list[dict[str, str]] = []

        self._add(checks, "environment_mode", "PASS", self.config.environment_mode)
        root = self.paths.base_root
        if not root.exists():
            self._add(checks, "state_root_exists", "FAIL", "missing")
        elif not root.is_dir():
            self._add(checks, "state_root_exists", "FAIL", "not_a_directory")
        else:
            self._add(checks, "state_root_exists", "PASS", "directory")
            self._add(
                checks,
                "state_root_writable",
                "PASS" if os.access(root, os.W_OK) else "FAIL",
                "writable" if os.access(root, os.W_OK) else "not_writable",
            )

        missing = [
            self._relative_label(path)
            for path in self.paths.directories()[1:]
            if not path.is_dir()
        ]
        self._add(
            checks,
            "canonical_layout",
            "FAIL" if missing else "PASS",
            "missing:" + ",".join(missing) if missing else "complete",
        )

        inside_repository = StatePaths._contained(root, self.paths.repository_root)
        if self.config.environment_mode == "host" and inside_repository:
            self._add(checks, "repository_boundary", "FAIL", "host_state_inside_source")
        elif inside_repository:
            self._add(checks, "repository_boundary", "PASS", "local_mode_allowed")
        else:
            self._add(checks, "repository_boundary", "PASS", "external_state_root")
        self._check_permissions(checks)
        self._check_secret_file(checks)

        self._check_provider_config(checks)
        self._check_provider_credentials(checks)
        self._check_telegram(checks)
        self._check_webhooks(checks)
        self._check_git(checks)
        self._check_local_state_compatibility(checks)
        self._add(
            checks,
            "python_runtime",
            "PASS",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
        self._add(
            checks,
            "public_listener",
            "PASS",
            "not_created_by_host_check",
        )

        statuses = {item["status"] for item in checks}
        status = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
        return {
            "status": status,
            "operation": "host_check",
            "environment_mode": self.config.environment_mode,
            "state_root": str(root),
            "checks": checks,
            "migration": "not_performed",
        }

    def detect_repository_local_state(self) -> tuple[str, ...]:
        local_root = self.paths.repository_root / "runtime" / "state"
        detected: list[str] = []
        for key in (
            "jobs",
            "executions",
            "approvals",
            "schedules",
            "scheduler",
            "remote",
            "notifications",
            "webhooks",
            "processes",
        ):
            directory = local_root.joinpath(*self.paths.relative_layout()[key].split("/"))
            if directory.is_dir() and any(
                item.is_file()
                and item.name != "README.md"
                and item.suffix not in {".pyc"}
                for item in directory.rglob("*")
            ):
                detected.append(key)
        return tuple(detected)

    def _check_provider_config(self, checks: list[dict[str, str]]) -> None:
        try:
            configuration = ProviderConfiguration(self.paths.repository_root)
            for provider_id in configuration.provider_ids:
                configuration.cli_config(provider_id)
        except (ProviderConfigError, OSError, UnicodeError, TypeError, ValueError):
            self._add(checks, "provider_config", "FAIL", "invalid")
        else:
            self._add(checks, "provider_config", "PASS", "syntactically_valid")

    def _check_secret_file(self, checks: list[dict[str, str]]) -> None:
        configured = self.config.secret_file
        if configured is None:
            self._add(checks, "host_secret_file", "PASS", "not_configured")
            return
        path = Path(configured).resolve(strict=False)
        unsafe = (
            StatePaths._overlaps(path.parent, self.paths.base_root)
            or StatePaths._overlaps(path.parent, self.paths.repository_root)
        )
        if unsafe or not path.is_file():
            self._add(
                checks,
                "host_secret_file",
                "FAIL",
                "unsafe_location" if unsafe else "missing",
            )
            return
        if _is_windows():
            self._add(
                checks,
                "host_secret_file",
                "WARN",
                "present_windows_acl_not_inspected",
            )
            return
        permissions = stat.S_IMODE(path.stat().st_mode)
        self._add(
            checks,
            "host_secret_file",
            "PASS" if permissions & 0o077 == 0 else "FAIL",
            "mode_0600_or_stricter" if permissions & 0o077 == 0 else "permissions_too_broad",
        )

    def _check_provider_credentials(self, checks: list[dict[str, str]]) -> None:
        if not self.config.provider_execution_enabled:
            self._add(checks, "provider_credentials", "PASS", "not_required")
            return
        configured = self.environment.get(
            "AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT"
        ) or self.config.provider_credential_root
        if configured is None:
            self._add(checks, "provider_credentials", "FAIL", "root_not_configured")
            return
        root = Path(configured).resolve(strict=False)
        unsafe = StatePaths._overlaps(
            root, self.paths.base_root
        ) or StatePaths._overlaps(root, self.paths.repository_root)
        if unsafe or not root.is_dir():
            self._add(
                checks,
                "provider_credentials",
                "FAIL",
                "unsafe_location" if unsafe else "separate_root_missing",
            )
            return
        if _is_windows():
            self._add(
                checks,
                "provider_credentials",
                "WARN",
                "separate_root_present_windows_acl_not_inspected",
            )
            return
        permissions = stat.S_IMODE(root.stat().st_mode)
        self._add(
            checks,
            "provider_credentials",
            "PASS" if permissions & 0o077 == 0 else "FAIL",
            (
                "separate_root_mode_0700_or_stricter"
                if permissions & 0o077 == 0
                else "permissions_too_broad"
            ),
        )

    def _check_permissions(self, checks: list[dict[str, str]]) -> None:
        if not self.paths.base_root.is_dir():
            self._add(checks, "state_permissions", "FAIL", "root_unavailable")
            return
        if _is_windows():
            self._add(
                checks,
                "state_permissions",
                "WARN",
                "windows_acl_requires_operator_validation",
            )
            return
        insecure = []
        for path in self.paths.directories():
            if path.is_dir() and path.stat().st_mode & stat.S_IWOTH:
                insecure.append(self._relative_label(path))
        self._add(
            checks,
            "state_permissions",
            "FAIL" if insecure else "PASS",
            "world_writable:" + ",".join(insecure) if insecure else "not_world_writable",
        )

    def _check_telegram(self, checks: list[dict[str, str]]) -> None:
        enabled = self.config.telegram_enabled or self.config.notifications_enabled
        if not enabled:
            self._add(checks, "telegram_token", "PASS", "not_required")
            self._add(checks, "remote_config", "PASS", "not_required")
            return
        token_present = bool(self.environment.get("AGENT_COMPANY_TELEGRAM_BOT_TOKEN"))
        self._add(
            checks,
            "telegram_token",
            "PASS" if token_present else "FAIL",
            "present" if token_present else "missing",
        )
        path = self._configured_path(
            "AGENT_COMPANY_REMOTE_CONFIG", "config/remote.local.json"
        )
        try:
            RemoteRuntimeConfig.from_file(path)
        except (RemoteCommandError, OSError, UnicodeError, TypeError, ValueError):
            self._add(checks, "remote_config", "FAIL", "unavailable_or_invalid")
        else:
            self._add(checks, "remote_config", "PASS", "syntactically_valid")

    def _check_webhooks(self, checks: list[dict[str, str]]) -> None:
        if not self.config.webhook_enabled:
            self._add(checks, "webhook_secrets", "PASS", "not_required")
            return
        path = self._configured_path(
            "AGENT_COMPANY_WEBHOOK_CONFIG", "config/webhooks.local.json"
        )
        try:
            config = WebhookRuntimeConfig.from_file(path)
            enabled = [source for source in config.sources if source.enabled]
            if not enabled:
                raise WebhookContractError("No enabled webhook source")
            for source in enabled:
                source.resolve_secret(self.environment)
        except (
            WebhookContractError,
            OSError,
            UnicodeError,
            TypeError,
            ValueError,
            OverflowError,
        ):
            self._add(checks, "webhook_secrets", "FAIL", "unavailable_or_invalid")
        else:
            self._add(checks, "webhook_secrets", "PASS", "references_resolved")

    def _check_git(self, checks: list[dict[str, str]]) -> None:
        if not self.config.git_enabled:
            self._add(checks, "git_executable", "PASS", "not_required")
            return
        available = shutil.which("git") is not None
        self._add(
            checks,
            "git_executable",
            "PASS" if available else "FAIL",
            "available" if available else "missing",
        )

    def _check_local_state_compatibility(self, checks: list[dict[str, str]]) -> None:
        detected = self.detect_repository_local_state()
        local_root = (self.paths.repository_root / "runtime" / "state").resolve()
        if self.paths.base_root == local_root:
            self._add(checks, "legacy_local_state", "PASS", "selected_local_layout")
        elif detected:
            self._add(
                checks,
                "legacy_local_state",
                "WARN",
                "detected_not_moved:" + ",".join(detected),
            )
        else:
            self._add(checks, "legacy_local_state", "PASS", "none_detected")

    def _configured_path(self, environment_name: str, default: str) -> Path:
        configured = self.environment.get(environment_name)
        path = Path(configured) if configured else self.paths.repository_root / default
        if not path.is_absolute():
            path = self.paths.repository_root / path
        return path

    def _ensure_contained(self, path: Path) -> None:
        if not StatePaths._contained(path, self.paths.base_root):
            raise HostReadinessError(
                f"Canonical host-state path escapes base root: {path}"
            )

    def _relative_label(self, path: Path) -> str:
        if path == self.paths.base_root:
            return "."
        try:
            return path.relative_to(self.paths.base_root).as_posix()
        except ValueError as error:
            raise StatePathError("Host-state path is outside the canonical root") from error

    @staticmethod
    def _add(
        checks: list[dict[str, str]], name: str, status: str, detail: str
    ) -> None:
        checks.append({"name": name, "status": status, "detail": detail})
