"""Narrow standard-library client for the Telegram Bot API."""

from __future__ import annotations

import json
import re
import socket
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TELEGRAM_API_ORIGIN = "https://api.telegram.org"
MAX_TELEGRAM_RESPONSE_BYTES = 1024 * 1024
MAX_HTTP_TIMEOUT_SECONDS = 70
_TOKEN_PATTERN = re.compile(r"^[0-9]{5,}:[A-Za-z0-9_-]{5,200}$")


class TelegramApiError(ValueError):
    """Raised when a bounded Telegram API request fails safely."""


class TelegramBotApiClient:
    def __init__(
        self,
        token: str | None,
        *,
        request_timeout_seconds: int = 30,
        max_response_bytes: int = MAX_TELEGRAM_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not token or not token.strip():
            raise TelegramApiError(
                "AGENT_COMPANY_TELEGRAM_BOT_TOKEN is required"
            )
        if _TOKEN_PATTERN.fullmatch(token) is None:
            raise TelegramApiError("Telegram bot token has an invalid format")
        if not 1 <= request_timeout_seconds <= MAX_HTTP_TIMEOUT_SECONDS:
            raise TelegramApiError("Telegram HTTP timeout is outside the allowed range")
        if not 1 <= max_response_bytes <= MAX_TELEGRAM_RESPONSE_BYTES:
            raise TelegramApiError("Telegram response bound is outside the allowed range")
        self._token = token
        self.request_timeout_seconds = request_timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._opener = opener

    def get_updates(self, *, offset: int, timeout_seconds: int = 0) -> list[dict[str, Any]]:
        if offset < 0:
            raise TelegramApiError("Telegram update offset cannot be negative")
        if not 0 <= timeout_seconds <= 50:
            raise TelegramApiError("Telegram long-poll timeout is outside the allowed range")
        response = self._call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout_seconds,
                "allowed_updates": ["message"],
            },
            timeout_seconds=max(
                self.request_timeout_seconds,
                min(timeout_seconds + 10, MAX_HTTP_TIMEOUT_SECONDS),
            ),
        )
        result = response.get("result")
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise TelegramApiError("Telegram getUpdates returned an invalid result")
        return result

    def send_message(self, *, chat_id: int, text: str) -> dict[str, Any]:
        if isinstance(chat_id, bool) or not isinstance(chat_id, int):
            raise TelegramApiError("Telegram chat ID is invalid")
        if not text or len(text) > 4096:
            raise TelegramApiError("Telegram response text is outside the allowed range")
        response = self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout_seconds=self.request_timeout_seconds,
        )
        result = response.get("result")
        if not isinstance(result, dict):
            raise TelegramApiError("Telegram sendMessage returned an invalid result")
        return result

    def _call(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        if method not in {"getUpdates", "sendMessage"}:
            raise TelegramApiError("Telegram API method is not allowed")
        encoded_token = quote(self._token, safe=":")
        endpoint = f"{TELEGRAM_API_ORIGIN}/bot{encoded_token}/{method}"
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
        request = Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                status = getattr(response, "status", response.getcode())
                if status != 200:
                    raise TelegramApiError(
                        f"Telegram API returned HTTP status {status}"
                    )
                length_header = response.headers.get("Content-Length")
                if length_header is not None:
                    try:
                        if int(length_header) > self.max_response_bytes:
                            raise TelegramApiError("Telegram API response is too large")
                    except ValueError as error:
                        raise TelegramApiError(
                            "Telegram API returned an invalid content length"
                        ) from error
                raw = response.read(self.max_response_bytes + 1)
        except TelegramApiError:
            raise
        except HTTPError as error:
            status = error.code
            error.close()
            raise TelegramApiError(
                f"Telegram API returned HTTP status {status}"
            ) from None
        except (TimeoutError, socket.timeout):
            raise TelegramApiError("Telegram API request timed out") from None
        except URLError:
            raise TelegramApiError("Telegram API request failed") from None
        except OSError:
            raise TelegramApiError("Telegram API request failed") from None
        if len(raw) > self.max_response_bytes:
            raise TelegramApiError("Telegram API response is too large")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TelegramApiError("Telegram API returned malformed JSON") from None
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise TelegramApiError("Telegram API rejected the request")
        return value
