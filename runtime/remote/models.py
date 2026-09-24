"""Canonical transport-independent remote command models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any


class RemoteCommandError(ValueError):
    """Raised when a remote command contract is invalid."""


class RemoteCommandType(str, Enum):
    STATUS = "STATUS"
    JOBS_LIST = "JOBS_LIST"
    JOB_SHOW = "JOB_SHOW"
    APPROVALS_LIST = "APPROVALS_LIST"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class RemotePermission(str, Enum):
    READ_STATUS = "READ_STATUS"
    READ_JOBS = "READ_JOBS"
    READ_JOB = "READ_JOB"
    READ_APPROVALS = "READ_APPROVALS"
    APPROVE = "APPROVE"
    REJECT = "REJECT"


COMMAND_PERMISSIONS = {
    RemoteCommandType.STATUS: RemotePermission.READ_STATUS,
    RemoteCommandType.JOBS_LIST: RemotePermission.READ_JOBS,
    RemoteCommandType.JOB_SHOW: RemotePermission.READ_JOB,
    RemoteCommandType.APPROVALS_LIST: RemotePermission.READ_APPROVALS,
    RemoteCommandType.APPROVE: RemotePermission.APPROVE,
    RemoteCommandType.REJECT: RemotePermission.REJECT,
}


class RemoteResultStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class RemoteIdentity:
    channel: str
    platform_user_id: str
    mapped_human_identity: str | None
    authenticated: bool
    authorized: bool

    def __post_init__(self) -> None:
        if not self.channel.strip():
            raise RemoteCommandError("Remote identity channel is required")
        if not self.platform_user_id.strip():
            raise RemoteCommandError("Remote identity platform_user_id is required")
        if self.mapped_human_identity is not None and not self.mapped_human_identity.strip():
            raise RemoteCommandError("Remote mapped human identity is empty")

    @property
    def actor_ref(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "platform_user_id": self.platform_user_id,
            "mapped_human_identity": self.mapped_human_identity,
            "authenticated": self.authenticated,
            "authorized": self.authorized,
        }


@dataclass(frozen=True)
class RemoteCommand:
    command_id: str
    channel: str
    actor: str
    command_type: RemoteCommandType
    issued_at: str
    received_at: str
    idempotency_key: str
    target_id: str | None = None
    approval_id: str | None = None
    authorization_fingerprint: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.command_id.strip():
            raise RemoteCommandError("Remote command_id is required")
        if not self.channel.strip():
            raise RemoteCommandError("Remote command channel is required")
        if not self.actor.strip():
            raise RemoteCommandError("Remote command actor is required")
        if not isinstance(self.command_type, RemoteCommandType):
            raise RemoteCommandError("Remote command type is not supported")
        if not self.issued_at.strip() or not self.received_at.strip():
            raise RemoteCommandError("Remote command timestamps are required")
        if not self.idempotency_key.strip():
            raise RemoteCommandError("Remote command idempotency_key is required")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise RemoteCommandError("Remote command metadata must be an object")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RemoteCommand":
        if not isinstance(value, dict):
            raise RemoteCommandError("Remote command must be a JSON object")
        allowed = {
            "command_id",
            "channel",
            "actor",
            "command_type",
            "target_id",
            "approval_id",
            "authorization_fingerprint",
            "issued_at",
            "received_at",
            "idempotency_key",
            "metadata",
        }
        if set(value) - allowed:
            raise RemoteCommandError("Remote command contains unsupported fields")
        required = {
            "command_id",
            "channel",
            "actor",
            "command_type",
            "issued_at",
            "received_at",
            "idempotency_key",
        }
        if not required.issubset(value):
            raise RemoteCommandError("Remote command is missing required fields")
        try:
            command_type = RemoteCommandType(str(value["command_type"]))
        except ValueError as error:
            raise RemoteCommandError("Remote command type is not supported") from error
        string_fields = (
            "command_id",
            "channel",
            "actor",
            "issued_at",
            "received_at",
            "idempotency_key",
        )
        if any(not isinstance(value.get(field), str) for field in string_fields):
            raise RemoteCommandError("Remote command has invalid string fields")
        nullable_strings = ("target_id", "approval_id", "authorization_fingerprint")
        if any(
            item is not None and not isinstance(item, str)
            for item in (value.get(field) for field in nullable_strings)
        ):
            raise RemoteCommandError("Remote command has invalid optional string fields")
        return cls(
            command_id=value["command_id"],
            channel=value["channel"],
            actor=value["actor"],
            command_type=command_type,
            target_id=value.get("target_id"),
            approval_id=value.get("approval_id"),
            authorization_fingerprint=value.get("authorization_fingerprint"),
            issued_at=value["issued_at"],
            received_at=value["received_at"],
            idempotency_key=value["idempotency_key"],
            metadata=deepcopy(value.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "channel": self.channel,
            "actor": self.actor,
            "command_type": self.command_type.value,
            "target_id": self.target_id,
            "approval_id": self.approval_id,
            "authorization_fingerprint": self.authorization_fingerprint,
            "issued_at": self.issued_at,
            "received_at": self.received_at,
            "idempotency_key": self.idempotency_key,
            "metadata": deepcopy(self.metadata or {}),
        }


@dataclass(frozen=True)
class RemoteCommandResult:
    command_id: str
    status: RemoteResultStatus
    result_type: str
    message: str
    processed_at: str
    data_refs: dict[str, Any] | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result_type": self.result_type,
            "message": self.message,
            "data_refs": deepcopy(self.data_refs or {}),
            "error_code": self.error_code,
            "processed_at": self.processed_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RemoteCommandResult":
        if not isinstance(value, dict):
            raise RemoteCommandError("Remote command result must be an object")
        return cls(
            command_id=str(value["command_id"]),
            status=RemoteResultStatus(str(value["status"])),
            result_type=str(value["result_type"]),
            message=str(value["message"]),
            processed_at=str(value["processed_at"]),
            data_refs=deepcopy(value.get("data_refs") or {}),
            error_code=value.get("error_code"),
        )
