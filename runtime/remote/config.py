"""Remote runtime configuration and trusted identity mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.remote.models import RemoteCommandError, RemoteIdentity


DEFAULT_APPROVAL_TTL_SECONDS = 600


@dataclass(frozen=True)
class RemoteUser:
    channel: str
    platform_user_id: str
    mapped_human_identity: str
    enabled: bool = True


@dataclass(frozen=True)
class RemoteRuntimeConfig:
    users: tuple[RemoteUser, ...] = ()
    approval_ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS
    max_audit_records: int = 1000

    def __post_init__(self) -> None:
        if self.approval_ttl_seconds < 1:
            raise RemoteCommandError("Remote approval TTL must be positive")
        if self.max_audit_records < 1:
            raise RemoteCommandError("Remote audit retention must be positive")

    @classmethod
    def empty(cls) -> "RemoteRuntimeConfig":
        return cls()

    @classmethod
    def from_file(cls, path: Path) -> "RemoteRuntimeConfig":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RemoteCommandError(f"Could not read remote config: {error}") from error
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise RemoteCommandError("Remote config has invalid schema_version")
        raw_users = value.get("allowed_users", [])
        if not isinstance(raw_users, list):
            raise RemoteCommandError("Remote config allowed_users must be a list")
        users: list[RemoteUser] = []
        for item in raw_users:
            if not isinstance(item, dict):
                raise RemoteCommandError("Remote config user entry must be an object")
            users.append(
                RemoteUser(
                    channel=str(item.get("channel", "")),
                    platform_user_id=str(item.get("platform_user_id", "")),
                    mapped_human_identity=str(item.get("mapped_human_identity", "")),
                    enabled=bool(item.get("enabled", True)),
                )
            )
        return cls(
            users=tuple(users),
            approval_ttl_seconds=int(
                value.get("approval_ttl_seconds", DEFAULT_APPROVAL_TTL_SECONDS)
            ),
            max_audit_records=int(value.get("max_audit_records", 1000)),
        )

    def identify(self, *, channel: str, platform_user_id: str) -> RemoteIdentity:
        for user in self.users:
            if user.channel == channel and user.platform_user_id == platform_user_id:
                return RemoteIdentity(
                    channel=channel,
                    platform_user_id=platform_user_id,
                    mapped_human_identity=user.mapped_human_identity,
                    authenticated=True,
                    authorized=user.enabled,
                )
        return RemoteIdentity(
            channel=channel,
            platform_user_id=platform_user_id,
            mapped_human_identity=None,
            authenticated=True,
            authorized=False,
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "approval_ttl_seconds": self.approval_ttl_seconds,
            "max_audit_records": self.max_audit_records,
            "allowed_user_count": len(self.users),
        }

