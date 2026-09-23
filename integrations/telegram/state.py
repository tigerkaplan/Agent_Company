"""Ignored local state for Telegram long-poll offsets."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TelegramStateError(ValueError):
    """Raised when Telegram transport state is invalid or unavailable."""


@dataclass(frozen=True)
class TelegramPollState:
    next_update_id: int = 0
    updated_at: str | None = None


class TelegramStateStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / "poll-state.json"

    def load(self) -> TelegramPollState:
        if not self.path.is_file():
            return TelegramPollState()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise TelegramStateError("Could not read Telegram transport state") from error
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise TelegramStateError("Telegram transport state is invalid")
        next_update_id = value.get("next_update_id")
        if (
            isinstance(next_update_id, bool)
            or not isinstance(next_update_id, int)
            or next_update_id < 0
        ):
            raise TelegramStateError("Telegram transport offset is invalid")
        updated_at = value.get("updated_at")
        if updated_at is not None and not isinstance(updated_at, str):
            raise TelegramStateError("Telegram transport timestamp is invalid")
        return TelegramPollState(next_update_id, updated_at)

    def advance(self, update_id: int, *, updated_at: str) -> TelegramPollState:
        if isinstance(update_id, bool) or not isinstance(update_id, int) or update_id < 0:
            raise TelegramStateError("Telegram update ID is invalid")
        current = self.load()
        next_update_id = max(current.next_update_id, update_id + 1)
        value: dict[str, Any] = {
            "schema_version": 1,
            "next_update_id": next_update_id,
            "updated_at": updated_at,
        }
        self._write(value)
        return TelegramPollState(next_update_id, updated_at)

    def _write(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=".poll-state.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise TelegramStateError("Could not persist Telegram transport state") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
