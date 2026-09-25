"""Strict, non-secret host configuration for Phase 8B."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class HostConfigError(ValueError):
    """Raised when host configuration is unsafe or malformed."""


_FIELDS = {
    "schema_version",
    "environment_mode",
    "state_root",
    "secret_file",
    "provider_execution_enabled",
    "provider_credential_root",
    "telegram_enabled",
    "webhook_enabled",
    "notifications_enabled",
    "scheduler_enabled",
    "git_enabled",
}
_BOOLEAN_FIELDS = (
    "provider_execution_enabled",
    "telegram_enabled",
    "webhook_enabled",
    "notifications_enabled",
    "scheduler_enabled",
    "git_enabled",
)
_SECRET_FIELD_PARTS = (
    "apikey",
    "botkey",
    "bottoken",
    "credentialvalue",
    "password",
    "privatekey",
    "secretvalue",
    "tokenvalue",
)


@dataclass(frozen=True)
class HostConfig:
    environment_mode: str = "local"
    state_root: str | None = None
    secret_file: str | None = None
    provider_execution_enabled: bool = False
    provider_credential_root: str | None = None
    telegram_enabled: bool = False
    webhook_enabled: bool = False
    notifications_enabled: bool = False
    scheduler_enabled: bool = False
    git_enabled: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != 1
        ):
            raise HostConfigError("Host config schema_version must be 1")
        if self.environment_mode not in {"local", "host"}:
            raise HostConfigError("Host environment_mode must be local or host")
        for field in _BOOLEAN_FIELDS:
            if not isinstance(getattr(self, field), bool):
                raise HostConfigError(f"Host config {field} must be a boolean")
        self._validate_path(self.state_root, "state_root")
        self._validate_path(self.secret_file, "secret_file")
        self._validate_path(
            self.provider_credential_root,
            "provider_credential_root",
        )

    @classmethod
    def local_default(cls) -> "HostConfig":
        return cls()

    @classmethod
    def from_file(cls, path: Path) -> "HostConfig":
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise HostConfigError(
                        f"Host config contains duplicate JSON key: {key}"
                    )
                value[key] = item
            return value

        try:
            value = json.loads(
                Path(path).read_text(encoding="utf-8-sig"),
                object_pairs_hook=unique_object,
            )
        except HostConfigError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise HostConfigError(f"Could not read host config: {error}") from error
        return cls.from_dict(value)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HostConfig":
        if not isinstance(value, dict):
            raise HostConfigError("Host config must be a JSON object")
        for key in value:
            normalized = "".join(character for character in key.lower() if character.isalnum())
            if any(part in normalized for part in _SECRET_FIELD_PARTS):
                raise HostConfigError("Host config must not contain secret values")
        unexpected = sorted(set(value) - _FIELDS)
        if unexpected:
            raise HostConfigError(
                f"Host config contains unsupported fields: {', '.join(unexpected)}"
            )
        schema_version = value.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise HostConfigError("Host config schema_version must be 1")
        mode = value.get("environment_mode")
        if not isinstance(mode, str):
            raise HostConfigError("Host config environment_mode must be a string")
        for field in _BOOLEAN_FIELDS:
            if not isinstance(value.get(field), bool):
                raise HostConfigError(f"Host config {field} must be a boolean")
        for field in ("state_root", "secret_file", "provider_credential_root"):
            if value.get(field) is not None and not isinstance(value[field], str):
                raise HostConfigError(f"Host config {field} must be a string or null")
        return cls(
            schema_version=schema_version,
            environment_mode=mode,
            state_root=value.get("state_root"),
            secret_file=value.get("secret_file"),
            provider_execution_enabled=value["provider_execution_enabled"],
            provider_credential_root=value.get("provider_credential_root"),
            telegram_enabled=value["telegram_enabled"],
            webhook_enabled=value["webhook_enabled"],
            notifications_enabled=value["notifications_enabled"],
            scheduler_enabled=value["scheduler_enabled"],
            git_enabled=value["git_enabled"],
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "environment_mode": self.environment_mode,
            "state_root": self.state_root,
            "secret_file": self.secret_file,
            "provider_execution_enabled": self.provider_execution_enabled,
            "provider_credential_root": self.provider_credential_root,
            "telegram_enabled": self.telegram_enabled,
            "webhook_enabled": self.webhook_enabled,
            "notifications_enabled": self.notifications_enabled,
            "scheduler_enabled": self.scheduler_enabled,
            "git_enabled": self.git_enabled,
        }

    @staticmethod
    def _validate_path(value: str | None, label: str) -> None:
        if value is None:
            return
        if not value or len(value) > 4096 or "\x00" in value:
            raise HostConfigError(f"Host config {label} is invalid")
        posix = PurePosixPath(value)
        windows = PureWindowsPath(value)
        if ".." in posix.parts or ".." in windows.parts:
            raise HostConfigError(f"Host config {label} must not contain traversal")
        if not posix.is_absolute() and not windows.is_absolute():
            raise HostConfigError(f"Host config {label} must be absolute")
