"""Canonical bounded webhook event and result models."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class WebhookContractError(ValueError):
    """Raised when webhook input violates the canonical contract."""


class WebhookEventType(str, Enum):
    TASK_SIGNAL = "TASK_SIGNAL"


class WebhookResultStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    FAILED = "failed"


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_SAFE_TASK_CLASS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_FORBIDDEN_KEY_PARTS = (
    "apikey",
    "credential",
    "password",
    "privatekey",
    "secret",
    "token",
)
_AUTHORITY_KEYS = {
    "agent",
    "approval",
    "approvalstatus",
    "approved",
    "capability",
    "command",
    "commit",
    "deployment",
    "doit",
    "executionscope",
    "git",
    "merge",
    "provider",
    "pullrequest",
    "push",
    "reviewresult",
    "risklevel",
    "shell",
    "skill",
    "userapproved",
    "workflow",
    "write",
}


@dataclass(frozen=True)
class WebhookEvent:
    event_id: str
    source_id: str
    event_type: WebhookEventType
    received_at: str
    idempotency_key: str
    payload: dict[str, Any]
    signature_metadata: dict[str, Any]
    occurred_at: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_body(
        cls,
        value: dict[str, Any],
        *,
        source_id: str,
        received_at: str,
        signature_metadata: dict[str, Any],
        configured_project_id: str | None = None,
    ) -> "WebhookEvent":
        if not isinstance(value, dict):
            raise WebhookContractError("Webhook body must be a JSON object")
        allowed = {
            "event_id",
            "event_type",
            "occurred_at",
            "idempotency_key",
            "payload",
            "project_id",
            "metadata",
        }
        unexpected = sorted(set(value) - allowed)
        if unexpected:
            raise WebhookContractError(
                f"Webhook body contains unsupported fields: {', '.join(unexpected)}"
            )
        required = {"event_id", "event_type", "idempotency_key", "payload"}
        missing = sorted(required - set(value))
        if missing:
            raise WebhookContractError(
                f"Webhook body is missing required fields: {', '.join(missing)}"
            )
        event_id = _bounded_identifier(value["event_id"], "event_id", 128)
        idempotency_key = _bounded_identifier(
            value["idempotency_key"], "idempotency_key", 256
        )
        try:
            event_type = WebhookEventType(value["event_type"])
        except (TypeError, ValueError) as error:
            raise WebhookContractError("Webhook event_type is unsupported") from error
        occurred_at = value.get("occurred_at")
        if occurred_at is not None:
            _timestamp(occurred_at, "occurred_at")
        project_id = value.get("project_id")
        if project_id is not None:
            project_id = _bounded_identifier(project_id, "project_id", 128)
        if configured_project_id is not None:
            if project_id is not None and project_id != configured_project_id:
                raise WebhookContractError(
                    "Webhook project_id does not match the trusted source binding"
                )
            project_id = configured_project_id
        payload = _task_signal_payload(value["payload"])
        metadata = value.get("metadata", {})
        _bounded_metadata(metadata)
        _timestamp(received_at, "received_at")
        return cls(
            event_id=event_id,
            source_id=source_id,
            event_type=event_type,
            received_at=received_at,
            occurred_at=occurred_at,
            idempotency_key=idempotency_key,
            payload=payload,
            signature_metadata=deepcopy(signature_metadata),
            project_id=project_id,
            metadata=deepcopy(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_id": self.source_id,
            "event_type": self.event_type.value,
            "received_at": self.received_at,
            "occurred_at": self.occurred_at,
            "idempotency_key": self.idempotency_key,
            "payload": deepcopy(self.payload),
            "signature_metadata": deepcopy(self.signature_metadata),
            "project_id": self.project_id,
            "metadata": deepcopy(self.metadata or {}),
        }


@dataclass(frozen=True)
class WebhookIngressResult:
    status: WebhookResultStatus
    message: str
    processed_at: str
    event_id: str | None = None
    source_id: str | None = None
    event_type: str | None = None
    job_id: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "processed_at": self.processed_at,
            "event_id": self.event_id,
            "source_id": self.source_id,
            "event_type": self.event_type,
            "job_id": self.job_id,
            "error_code": self.error_code,
        }


def _task_signal_payload(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise WebhookContractError("Webhook payload must be an object")
    allowed = {"task", "task_class"}
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise WebhookContractError(
            f"TASK_SIGNAL payload contains unsupported fields: {', '.join(unexpected)}"
        )
    if set(value) != allowed:
        raise WebhookContractError("TASK_SIGNAL requires task and task_class")
    task = value["task"]
    task_class = value["task_class"]
    if not isinstance(task, str) or not task.strip() or len(task) > 4000:
        raise WebhookContractError("TASK_SIGNAL task must be 1-4000 characters")
    if (
        not isinstance(task_class, str)
        or len(task_class) > 64
        or _SAFE_TASK_CLASS.fullmatch(task_class) is None
    ):
        raise WebhookContractError("TASK_SIGNAL task_class is invalid")
    return {"task": task, "task_class": task_class}


def _bounded_identifier(value: Any, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or _SAFE_ID.fullmatch(value) is None
    ):
        raise WebhookContractError(f"Webhook {label} is invalid")
    return value


def _timestamp(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise WebhookContractError(f"Webhook {label} must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise WebhookContractError(
            f"Webhook {label} must be an ISO 8601 timestamp"
        ) from error
    if parsed.tzinfo is None:
        raise WebhookContractError(f"Webhook {label} must include a timezone")


def _bounded_metadata(value: Any) -> None:
    if not isinstance(value, dict):
        raise WebhookContractError("Webhook metadata must be an object")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise WebhookContractError("Webhook metadata must contain JSON values") from error
    if len(encoded.encode("utf-8")) > 4096:
        raise WebhookContractError("Webhook metadata exceeds 4096 bytes")

    def visit(item: Any, depth: int) -> None:
        if depth > 6:
            raise WebhookContractError("Webhook metadata nesting is too deep")
        if isinstance(item, dict):
            for key, nested in item.items():
                if not isinstance(key, str) or len(key) > 100:
                    raise WebhookContractError("Webhook metadata key is invalid")
                normalized = re.sub(r"[^a-z0-9]", "", key.lower())
                if normalized in _AUTHORITY_KEYS or any(
                    part in normalized for part in _FORBIDDEN_KEY_PARTS
                ):
                    raise WebhookContractError(
                        "Webhook metadata contains an authority or secret-like field"
                    )
                visit(nested, depth + 1)
        elif isinstance(item, list):
            if len(item) > 50:
                raise WebhookContractError("Webhook metadata list is too large")
            for nested in item:
                visit(nested, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise WebhookContractError("Webhook metadata contains an unsupported value")

    visit(value, 0)
