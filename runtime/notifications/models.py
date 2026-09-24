"""Canonical bounded models for operational notifications."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from runtime.providers.adapters import bound_text, sanitize_provider_text


class NotificationError(ValueError):
    """Raised when a notification contract is invalid."""


class NotificationType(str, Enum):
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    RUNTIME_ERROR = "RUNTIME_ERROR"


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_SENSITIVE_KEY = re.compile(
    r"(?i)(token|secret|password|credential|authorization|environment|api.?key)"
)
_TELEGRAM_TOKEN = re.compile(r"\b[0-9]{5,}:[A-Za-z0-9_-]{20,}\b")


def sanitize_notification_text(value: Any, limit: int) -> str:
    sanitized = sanitize_provider_text(str(value))
    sanitized = _TELEGRAM_TOKEN.sub("[REDACTED_TOKEN]", sanitized)
    return bound_text(sanitized.replace("\x00", ""), limit)


def sanitize_notification_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return sanitize_notification_text(value, 500)
    if isinstance(value, (list, tuple)):
        return [
            sanitize_notification_metadata(item, depth=depth + 1)
            for item in list(value)[:20]
        ]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in list(value.items())[:40]:
            key = sanitize_notification_text(raw_key, 100)
            result[key] = (
                "[REDACTED]"
                if _SENSITIVE_KEY.search(key)
                else sanitize_notification_metadata(item, depth=depth + 1)
            )
        return result
    return sanitize_notification_text(value, 500)


@dataclass(frozen=True)
class NotificationEvent:
    notification_id: str
    notification_type: NotificationType
    created_at: str
    target_human_identity: str
    source_type: str
    source_id: str
    severity: NotificationSeverity
    title: str
    summary: str
    approval_id: str | None = None
    authorization_fingerprint: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for label, value, limit in (
            ("notification_id", self.notification_id, 200),
            ("target_human_identity", self.target_human_identity, 200),
            ("source_type", self.source_type, 100),
            ("source_id", self.source_id, 300),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise NotificationError(f"Notification {label} is invalid")
        if not isinstance(self.notification_type, NotificationType):
            raise NotificationError("Notification type is invalid")
        if not isinstance(self.severity, NotificationSeverity):
            raise NotificationError("Notification severity is invalid")
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise NotificationError("Notification created_at is invalid") from error
        if created.tzinfo is None:
            raise NotificationError("Notification created_at must include a timezone")
        if self.approval_id is not None and (
            not self.approval_id.strip() or len(self.approval_id) > 200
        ):
            raise NotificationError("Notification approval_id is invalid")
        if self.authorization_fingerprint is not None and (
            len(self.authorization_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.authorization_fingerprint
            )
        ):
            raise NotificationError("Notification authorization fingerprint is invalid")
        object.__setattr__(self, "title", sanitize_notification_text(self.title, 200))
        object.__setattr__(self, "summary", sanitize_notification_text(self.summary, 1200))
        safe_metadata = sanitize_notification_metadata(self.metadata or {})
        encoded = json.dumps(
            safe_metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        if len(encoded.encode("utf-8")) > 4096:
            raise NotificationError("Notification metadata exceeds the allowed size")
        object.__setattr__(self, "metadata", safe_metadata)

    @classmethod
    def create(
        cls,
        *,
        notification_type: NotificationType,
        created_at: str,
        target_human_identity: str,
        source_type: str,
        source_id: str,
        severity: NotificationSeverity,
        title: str,
        summary: str,
        approval_id: str | None = None,
        authorization_fingerprint: str | None = None,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> "NotificationEvent":
        identity = {
            "notification_type": notification_type.value,
            "target_human_identity": target_human_identity,
            "source_type": source_type,
            "source_id": source_id,
            "approval_id": approval_id,
            "dedupe_key": dedupe_key,
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        notification_id = f"notification-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:32]}"
        return cls(
            notification_id=notification_id,
            notification_type=notification_type,
            created_at=created_at,
            target_human_identity=target_human_identity,
            source_type=source_type,
            source_id=source_id,
            severity=severity,
            title=title,
            summary=summary,
            approval_id=approval_id,
            authorization_fingerprint=authorization_fingerprint,
            metadata=deepcopy(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "notification_type": self.notification_type.value,
            "created_at": self.created_at,
            "target_human_identity": self.target_human_identity,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "severity": self.severity.value,
            "title": self.title,
            "summary": self.summary,
            "approval_id": self.approval_id,
            "authorization_fingerprint": self.authorization_fingerprint,
            "metadata": deepcopy(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NotificationEvent":
        if not isinstance(value, dict):
            raise NotificationError("Notification event must be an object")
        try:
            return cls(
                notification_id=str(value["notification_id"]),
                notification_type=NotificationType(str(value["notification_type"])),
                created_at=str(value["created_at"]),
                target_human_identity=str(value["target_human_identity"]),
                source_type=str(value["source_type"]),
                source_id=str(value["source_id"]),
                severity=NotificationSeverity(str(value["severity"])),
                title=str(value["title"]),
                summary=str(value["summary"]),
                approval_id=value.get("approval_id"),
                authorization_fingerprint=value.get("authorization_fingerprint"),
                metadata=deepcopy(value.get("metadata") or {}),
            )
        except (KeyError, ValueError) as error:
            raise NotificationError("Notification event is malformed") from error
