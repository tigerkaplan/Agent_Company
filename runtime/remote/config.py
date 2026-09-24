"""Remote runtime configuration and trusted identity mapping."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.approvals.models import REQUESTED_ACTIONS
from runtime.remote.models import (
    RemoteCommandError,
    RemoteIdentity,
    RemotePermission,
)


DEFAULT_APPROVAL_TTL_SECONDS = 600
DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS = 30
_CHANNEL_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_PLATFORM_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_TELEGRAM_USER_ID_PATTERN = re.compile(r"[1-9][0-9]{0,19}")
_PROJECT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


@dataclass(frozen=True)
class RemoteApprovalScope:
    allowed_actions: tuple[str, ...] = ()
    project_ids: tuple[str, ...] = ()
    allow_unscoped_projects: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.allow_unscoped_projects, bool):
            raise RemoteCommandError(
                "Remote approval scope allow_unscoped_projects must be a boolean"
            )
        if any(
            not isinstance(action, str) or action not in REQUESTED_ACTIONS
            for action in self.allowed_actions
        ):
            raise RemoteCommandError("Remote approval scope contains an unknown action")
        if len(self.allowed_actions) != len(set(self.allowed_actions)):
            raise RemoteCommandError("Remote approval scope actions must be unique")
        if any(
            not isinstance(project_id, str)
            or _PROJECT_ID_PATTERN.fullmatch(project_id) is None
            for project_id in self.project_ids
        ):
            raise RemoteCommandError("Remote approval scope project_id is invalid")
        if len(self.project_ids) != len(set(self.project_ids)):
            raise RemoteCommandError("Remote approval scope project_ids must be unique")

    def allows(self, approval: dict[str, Any], job: dict[str, Any]) -> bool:
        if approval.get("requested_action") not in self.allowed_actions:
            return False
        project_id = job.get("project_id")
        if project_id is None:
            return self.allow_unscoped_projects
        return isinstance(project_id, str) and project_id in self.project_ids


@dataclass(frozen=True)
class RemoteUser:
    channel: str
    platform_user_id: str
    mapped_human_identity: str
    enabled: bool = False
    permissions: tuple[RemotePermission, ...] = ()
    approval_scope: RemoteApprovalScope = RemoteApprovalScope()

    def __post_init__(self) -> None:
        if not isinstance(self.channel, str) or _CHANNEL_PATTERN.fullmatch(self.channel) is None:
            raise RemoteCommandError("Remote user channel is invalid")
        if not isinstance(self.platform_user_id, str):
            raise RemoteCommandError("Remote user platform_user_id must be a string")
        platform_pattern = (
            _TELEGRAM_USER_ID_PATTERN
            if self.channel == "telegram"
            else _PLATFORM_ID_PATTERN
        )
        if platform_pattern.fullmatch(self.platform_user_id) is None:
            raise RemoteCommandError("Remote user platform_user_id is invalid")
        if (
            not isinstance(self.mapped_human_identity, str)
            or not self.mapped_human_identity.strip()
            or len(self.mapped_human_identity) > 200
        ):
            raise RemoteCommandError("Remote mapped human identity is invalid")
        if not isinstance(self.enabled, bool):
            raise RemoteCommandError("Remote user enabled must be a boolean")
        if any(not isinstance(permission, RemotePermission) for permission in self.permissions):
            raise RemoteCommandError("Remote user contains an unknown permission")
        if len(self.permissions) != len(set(self.permissions)):
            raise RemoteCommandError("Remote user permissions must be unique")
        if not isinstance(self.approval_scope, RemoteApprovalScope):
            raise RemoteCommandError("Remote user approval_scope is invalid")


@dataclass(frozen=True)
class RemoteRuntimeConfig:
    users: tuple[RemoteUser, ...] = ()
    notification_targets: tuple[str, ...] = ()
    approval_ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS
    allowed_clock_skew_seconds: int = DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS
    max_audit_records: int = 1000

    def __post_init__(self) -> None:
        if (
            isinstance(self.approval_ttl_seconds, bool)
            or not isinstance(self.approval_ttl_seconds, int)
            or self.approval_ttl_seconds < 1
        ):
            raise RemoteCommandError("Remote approval TTL must be positive")
        if (
            isinstance(self.allowed_clock_skew_seconds, bool)
            or not isinstance(self.allowed_clock_skew_seconds, int)
            or not 0 <= self.allowed_clock_skew_seconds <= 300
        ):
            raise RemoteCommandError("Remote allowed clock skew is invalid")
        if (
            isinstance(self.max_audit_records, bool)
            or not isinstance(self.max_audit_records, int)
            or self.max_audit_records < 1
        ):
            raise RemoteCommandError("Remote audit retention must be positive")
        if any(not isinstance(user, RemoteUser) for user in self.users):
            raise RemoteCommandError("Remote users are invalid")
        identities = [(user.channel, user.platform_user_id) for user in self.users]
        if len(identities) != len(set(identities)):
            raise RemoteCommandError("Remote user identities must be unique")
        if any(
            not isinstance(target, str)
            or not target.strip()
            or len(target) > 200
            for target in self.notification_targets
        ):
            raise RemoteCommandError("Remote notification target is invalid")
        if len(self.notification_targets) != len(set(self.notification_targets)):
            raise RemoteCommandError("Remote notification targets must be unique")

    @classmethod
    def empty(cls) -> "RemoteRuntimeConfig":
        return cls()

    @classmethod
    def from_file(cls, path: Path) -> "RemoteRuntimeConfig":
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise RemoteCommandError(
                        f"Remote config contains duplicate JSON key: {key}"
                    )
                value[key] = item
            return value

        try:
            value = json.loads(
                path.read_text(encoding="utf-8-sig"),
                object_pairs_hook=unique_object,
            )
        except RemoteCommandError:
            raise
        except (OSError, json.JSONDecodeError) as error:
            raise RemoteCommandError(f"Could not read remote config: {error}") from error
        if (
            not isinstance(value, dict)
            or isinstance(value.get("schema_version"), bool)
            or not isinstance(value.get("schema_version"), int)
            or value.get("schema_version") != 1
        ):
            raise RemoteCommandError("Remote config has invalid schema_version")
        allowed_top_level = {
            "schema_version",
            "allowed_users",
            "notification_targets",
            "approval_ttl_seconds",
            "allowed_clock_skew_seconds",
            "max_audit_records",
        }
        if set(value) - allowed_top_level:
            raise RemoteCommandError("Remote config contains unsupported fields")
        raw_users = value.get("allowed_users", [])
        if not isinstance(raw_users, list):
            raise RemoteCommandError("Remote config allowed_users must be a list")
        users: list[RemoteUser] = []
        for item in raw_users:
            if not isinstance(item, dict):
                raise RemoteCommandError("Remote config user entry must be an object")
            allowed_user_fields = {
                "channel",
                "platform_user_id",
                "mapped_human_identity",
                "enabled",
                "permissions",
                "approval_scope",
            }
            required_user_fields = {
                "channel",
                "platform_user_id",
                "mapped_human_identity",
            }
            if set(item) - allowed_user_fields or not required_user_fields.issubset(item):
                raise RemoteCommandError(
                    "Remote config user has invalid or missing fields"
                )
            for field in required_user_fields:
                if not isinstance(item[field], str) or not item[field].strip():
                    raise RemoteCommandError(
                        f"Remote config user {field} must be a non-empty string"
                    )
            enabled = item.get("enabled", False)
            if not isinstance(enabled, bool):
                raise RemoteCommandError("Remote config user enabled must be a boolean")
            raw_permissions = item.get("permissions", [])
            if not isinstance(raw_permissions, list) or any(
                not isinstance(permission, str) for permission in raw_permissions
            ):
                raise RemoteCommandError(
                    "Remote config user permissions must be a list of strings"
                )
            try:
                permissions = tuple(
                    RemotePermission(permission) for permission in raw_permissions
                )
            except ValueError as error:
                raise RemoteCommandError(
                    "Remote config user contains an unknown permission"
                ) from error
            approval_scope = cls._parse_approval_scope(item.get("approval_scope"))
            users.append(
                RemoteUser(
                    channel=item["channel"],
                    platform_user_id=item["platform_user_id"],
                    mapped_human_identity=item["mapped_human_identity"],
                    enabled=enabled,
                    permissions=permissions,
                    approval_scope=approval_scope,
                )
            )
        raw_targets = value.get("notification_targets", [])
        if not isinstance(raw_targets, list) or any(
            not isinstance(target, str) for target in raw_targets
        ):
            raise RemoteCommandError(
                "Remote config notification_targets must be a list of strings"
            )
        approval_ttl_seconds = value.get(
            "approval_ttl_seconds", DEFAULT_APPROVAL_TTL_SECONDS
        )
        allowed_clock_skew_seconds = value.get(
            "allowed_clock_skew_seconds", DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS
        )
        max_audit_records = value.get("max_audit_records", 1000)
        for field, parsed in (
            ("approval_ttl_seconds", approval_ttl_seconds),
            ("allowed_clock_skew_seconds", allowed_clock_skew_seconds),
            ("max_audit_records", max_audit_records),
        ):
            if isinstance(parsed, bool) or not isinstance(parsed, int):
                raise RemoteCommandError(f"Remote config {field} must be an integer")
        return cls(
            users=tuple(users),
            notification_targets=tuple(raw_targets),
            approval_ttl_seconds=approval_ttl_seconds,
            allowed_clock_skew_seconds=allowed_clock_skew_seconds,
            max_audit_records=max_audit_records,
        )

    @staticmethod
    def _parse_approval_scope(value: Any) -> RemoteApprovalScope:
        if value is None:
            return RemoteApprovalScope()
        if not isinstance(value, dict):
            raise RemoteCommandError("Remote config approval_scope must be an object")
        allowed = {"allowed_actions", "project_ids", "allow_unscoped_projects"}
        if set(value) - allowed:
            raise RemoteCommandError(
                "Remote config approval_scope contains unsupported fields"
            )
        actions = value.get("allowed_actions", [])
        project_ids = value.get("project_ids", [])
        allow_unscoped = value.get("allow_unscoped_projects", False)
        if not isinstance(actions, list) or any(
            not isinstance(action, str) for action in actions
        ):
            raise RemoteCommandError(
                "Remote config approval_scope allowed_actions must be a list of strings"
            )
        if not isinstance(project_ids, list) or any(
            not isinstance(project_id, str) for project_id in project_ids
        ):
            raise RemoteCommandError(
                "Remote config approval_scope project_ids must be a list of strings"
            )
        if not isinstance(allow_unscoped, bool):
            raise RemoteCommandError(
                "Remote config approval_scope allow_unscoped_projects must be a boolean"
            )
        return RemoteApprovalScope(
            allowed_actions=tuple(actions),
            project_ids=tuple(project_ids),
            allow_unscoped_projects=allow_unscoped,
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

    def authorized_user(self, identity: RemoteIdentity) -> RemoteUser | None:
        if not identity.authenticated or not identity.authorized:
            return None
        for user in self.users:
            if (
                user.enabled
                and user.channel == identity.channel
                and user.platform_user_id == identity.platform_user_id
                and user.mapped_human_identity == identity.mapped_human_identity
            ):
                return user
        return None

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "approval_ttl_seconds": self.approval_ttl_seconds,
            "allowed_clock_skew_seconds": self.allowed_clock_skew_seconds,
            "max_audit_records": self.max_audit_records,
            "allowed_user_count": len(self.users),
            "notification_target_count": len(self.notification_targets),
        }
