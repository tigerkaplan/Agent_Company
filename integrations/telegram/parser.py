"""Explicit Telegram update and command parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from runtime.remote.models import RemoteCommand, RemoteCommandType


MAX_TELEGRAM_INPUT_CHARS = 4096
HELP_TEXT = (
    "Available commands:\n"
    "/status\n/jobs\n/job <job_id>\n/approvals\n"
    "/approve <approval_id> <authorization_fingerprint>\n"
    "/reject <approval_id> <authorization_fingerprint>"
)
SAFE_UNSUPPORTED_TEXT = "Unsupported command. Use /help for the allowed commands."
SAFE_TEXT_ONLY_RESPONSE = "Only explicit bot commands are supported. Use /help."
PRIVATE_CHAT_ONLY_RESPONSE = "Agent Company commands are available only in private chats."
_COMMAND_PATTERN = re.compile(r"^/([a-z]+)$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TelegramParseError(ValueError):
    """Raised when a Telegram update cannot be parsed safely."""


@dataclass(frozen=True)
class TelegramInboundMessage:
    update_id: int
    user_id: int
    chat_id: int
    chat_type: str
    issued_at: str
    text: str


@dataclass(frozen=True)
class TelegramParseOutcome:
    command: RemoteCommand | None
    direct_response: str | None = None


class TelegramUpdateParser:
    def parse(self, update: dict[str, Any]) -> TelegramInboundMessage | None:
        if not isinstance(update, dict):
            raise TelegramParseError("Telegram update must be an object")
        update_id = self._integer(update.get("update_id"), "update ID", minimum=0)
        message = update.get("message")
        if message is None:
            return None
        if not isinstance(message, dict):
            raise TelegramParseError("Telegram message must be an object")
        sender = message.get("from")
        chat = message.get("chat")
        if not isinstance(sender, dict) or not isinstance(chat, dict):
            raise TelegramParseError("Telegram message identity is missing")
        user_id = self._integer(sender.get("id"), "user ID", minimum=1)
        chat_id = self._integer(chat.get("id"), "chat ID")
        chat_type = chat.get("type")
        if not isinstance(chat_type, str) or chat_type not in {
            "private",
            "group",
            "supergroup",
            "channel",
        }:
            raise TelegramParseError("Telegram chat type is missing or invalid")
        timestamp = self._integer(message.get("date"), "message date", minimum=0)
        text = message.get("text")
        if text is None:
            return None
        if not isinstance(text, str):
            raise TelegramParseError("Telegram message text is invalid")
        if len(text) > MAX_TELEGRAM_INPUT_CHARS:
            raise TelegramParseError("Telegram message text exceeds the allowed size")
        try:
            issued_at = (
                datetime.fromtimestamp(timestamp, timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (OSError, OverflowError, ValueError):
            raise TelegramParseError("Telegram message date is invalid") from None
        return TelegramInboundMessage(
            update_id=update_id,
            user_id=user_id,
            chat_id=chat_id,
            chat_type=chat_type,
            issued_at=issued_at,
            text=text,
        )

    @staticmethod
    def update_id(update: dict[str, Any]) -> int:
        if not isinstance(update, dict):
            raise TelegramParseError("Telegram update must be an object")
        return TelegramUpdateParser._integer(
            update.get("update_id"), "update ID", minimum=0
        )

    @staticmethod
    def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TelegramParseError(f"Telegram {label} is invalid")
        if minimum is not None and value < minimum:
            raise TelegramParseError(f"Telegram {label} is invalid")
        return value


class TelegramCommandParser:
    _COMMANDS = {
        "status": RemoteCommandType.STATUS,
        "jobs": RemoteCommandType.JOBS_LIST,
        "job": RemoteCommandType.JOB_SHOW,
        "approvals": RemoteCommandType.APPROVALS_LIST,
        "approve": RemoteCommandType.APPROVE,
        "reject": RemoteCommandType.REJECT,
    }

    def parse(
        self,
        message: TelegramInboundMessage,
        *,
        received_at: str,
    ) -> TelegramParseOutcome:
        parts = message.text.strip().split()
        if not parts:
            return TelegramParseOutcome(None, SAFE_TEXT_ONLY_RESPONSE)
        match = _COMMAND_PATTERN.fullmatch(parts[0])
        if match is None:
            response = (
                SAFE_UNSUPPORTED_TEXT
                if parts[0].startswith("/")
                else SAFE_TEXT_ONLY_RESPONSE
            )
            return TelegramParseOutcome(None, response)
        name = match.group(1)
        if name == "help":
            if len(parts) != 1:
                return TelegramParseOutcome(None, "Usage: /help")
            return TelegramParseOutcome(None, HELP_TEXT)
        command_type = self._COMMANDS.get(name)
        if command_type is None:
            return TelegramParseOutcome(None, SAFE_UNSUPPORTED_TEXT)

        target_id: str | None = None
        approval_id: str | None = None
        fingerprint: str | None = None
        if name in {"status", "jobs", "approvals"}:
            if len(parts) != 1:
                return TelegramParseOutcome(None, f"Usage: /{name}")
        elif name == "job":
            if len(parts) != 2 or not _IDENTIFIER_PATTERN.fullmatch(parts[1]):
                return TelegramParseOutcome(None, "Usage: /job <job_id>")
            target_id = parts[1]
        else:
            if (
                len(parts) != 3
                or not _IDENTIFIER_PATTERN.fullmatch(parts[1])
                or not _FINGERPRINT_PATTERN.fullmatch(parts[2])
            ):
                return TelegramParseOutcome(
                    None,
                    f"Usage: /{name} <approval_id> <authorization_fingerprint>",
                )
            approval_id = parts[1]
            fingerprint = parts[2]

        command_id = f"telegram-update-{message.update_id}"
        return TelegramParseOutcome(
            RemoteCommand(
                command_id=command_id,
                channel="telegram",
                actor=str(message.user_id),
                command_type=command_type,
                target_id=target_id,
                approval_id=approval_id,
                authorization_fingerprint=fingerprint,
                issued_at=message.issued_at,
                received_at=received_at,
                idempotency_key=command_id,
                metadata={},
            )
        )
