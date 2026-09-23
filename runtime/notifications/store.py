"""Atomic bounded persistence for notification delivery evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


class NotificationStoreError(ValueError):
    """Raised when notification state cannot be persisted safely."""


class FileNotificationStore:
    def __init__(self, root: Path, *, max_records: int = 1000) -> None:
        if max_records < 1:
            raise NotificationStoreError("Notification retention must be positive")
        self.root = Path(root)
        self.max_records = max_records

    def load(self, notification_id: str) -> dict[str, Any] | None:
        path = self._path(notification_id)
        if not path.is_file():
            return None
        return self._load(path)

    def save(self, record: dict[str, Any]) -> None:
        notification_id = str(record.get("notification", {}).get("notification_id", ""))
        if not notification_id:
            raise NotificationStoreError("Notification record requires an ID")
        self._write(self._path(notification_id), record)
        self._prune()

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        records = [self._load(path) for path in self.root.glob("*.notification.json")]
        return sorted(
            records,
            key=lambda item: (
                item.get("notification", {}).get("created_at", ""),
                item.get("notification", {}).get("notification_id", ""),
            ),
        )

    def _path(self, notification_id: str) -> Path:
        digest = hashlib.sha256(notification_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.notification.json"

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise NotificationStoreError("Could not read notification state") from error
        if not isinstance(value, dict):
            raise NotificationStoreError("Notification state is not an object")
        return deepcopy(value)

    def _write(self, path: Path, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as error:
            raise NotificationStoreError("Could not persist notification state") from error
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _prune(self) -> None:
        paths = sorted(
            self.root.glob("*.notification.json"),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
        )
        for expired in paths[: max(0, len(paths) - self.max_records)]:
            try:
                expired.unlink()
            except OSError as error:
                raise NotificationStoreError("Could not prune notification state") from error
