"""Local-first Telegram long-poll adapter around RemoteCommandService."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from integrations.telegram.client import TelegramApiError
from integrations.telegram.formatter import TelegramResultFormatter
from integrations.telegram.parser import TelegramCommandParser, TelegramUpdateParser
from integrations.telegram.state import TelegramStateStore
from runtime.remote.config import RemoteRuntimeConfig
from runtime.remote.service import RemoteCommandService


class TelegramClient(Protocol):
    def get_updates(
        self, *, offset: int, timeout_seconds: int = 0
    ) -> list[dict[str, Any]]: ...

    def send_message(self, *, chat_id: int, text: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TelegramPollResult:
    fetched_updates: int
    processed_updates: int
    skipped_updates: int
    sent_messages: int
    next_update_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched_updates": self.fetched_updates,
            "processed_updates": self.processed_updates,
            "skipped_updates": self.skipped_updates,
            "sent_messages": self.sent_messages,
            "next_update_id": self.next_update_id,
        }


class TelegramTransport:
    def __init__(
        self,
        *,
        client: TelegramClient,
        service: RemoteCommandService,
        config: RemoteRuntimeConfig,
        state: TelegramStateStore,
        clock: Callable[[], str],
        update_parser: TelegramUpdateParser | None = None,
        command_parser: TelegramCommandParser | None = None,
        formatter: TelegramResultFormatter | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.service = service
        self.config = config
        self.state = state
        self.clock = clock
        self.update_parser = update_parser or TelegramUpdateParser()
        self.command_parser = command_parser or TelegramCommandParser()
        self.formatter = formatter or TelegramResultFormatter()
        self.sleeper = sleeper

    def poll_once(self, *, long_poll_seconds: int = 0) -> TelegramPollResult:
        state = self.state.load()
        updates = self.client.get_updates(
            offset=state.next_update_id,
            timeout_seconds=long_poll_seconds,
        )
        processed = 0
        skipped = 0
        sent = 0
        next_update_id = state.next_update_id
        for update in updates:
            update_id = self.update_parser.update_id(update)
            if update_id < next_update_id:
                skipped += 1
                continue
            message = self.update_parser.parse(update)
            if message is None:
                skipped += 1
            else:
                outcome = self.command_parser.parse(
                    message,
                    received_at=self.clock(),
                )
                if outcome.command is None:
                    response = outcome.direct_response or "Unsupported Telegram update."
                else:
                    identity = self.config.identify(
                        channel="telegram",
                        platform_user_id=str(message.user_id),
                    )
                    result = self.service.handle(outcome.command, identity)
                    response = self.formatter.format(result)
                self.client.send_message(chat_id=message.chat_id, text=response)
                processed += 1
                sent += 1
            advanced = self.state.advance(update_id, updated_at=self.clock())
            next_update_id = advanced.next_update_id
        return TelegramPollResult(
            fetched_updates=len(updates),
            processed_updates=processed,
            skipped_updates=skipped,
            sent_messages=sent,
            next_update_id=next_update_id,
        )

    def run(
        self,
        *,
        long_poll_seconds: int = 20,
        backoff_seconds: float = 5.0,
        max_cycles: int | None = None,
    ) -> dict[str, Any]:
        if not 0 <= long_poll_seconds <= 50:
            raise TelegramApiError("Telegram long-poll timeout is outside the allowed range")
        if not 0.1 <= backoff_seconds <= 60:
            raise TelegramApiError("Telegram retry backoff is outside the allowed range")
        if max_cycles is not None and max_cycles < 1:
            raise TelegramApiError("Telegram max cycles must be positive")
        cycles = 0
        api_errors = 0
        consecutive_errors = 0
        processed_updates = 0
        interrupted = False
        try:
            while max_cycles is None or cycles < max_cycles:
                cycles += 1
                try:
                    result = self.poll_once(long_poll_seconds=long_poll_seconds)
                except TelegramApiError:
                    api_errors += 1
                    consecutive_errors += 1
                    if max_cycles is not None and cycles >= max_cycles:
                        continue
                    delay = min(
                        backoff_seconds * (2 ** min(consecutive_errors - 1, 4)),
                        60.0,
                    )
                    self.sleeper(delay)
                    continue
                consecutive_errors = 0
                processed_updates += result.processed_updates
        except KeyboardInterrupt:
            interrupted = True
        return {
            "mode": "telegram_long_poll",
            "cycles": cycles,
            "processed_updates": processed_updates,
            "api_errors": api_errors,
            "interrupted": interrupted,
            "next_update_id": self.state.load().next_update_id,
        }
