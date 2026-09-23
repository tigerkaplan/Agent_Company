"""Atomic local JSON-file persistence for canonical schedules."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


class ScheduleStoreError(ValueError):
    """Raised when schedule persistence cannot satisfy an operation."""


class FileScheduleStore:
    """Store one canonical schedule per JSON file."""

    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def exists(self, schedule_id: str) -> bool:
        return self._path(schedule_id).is_file()

    def create(self, schedule: dict[str, Any]) -> None:
        path = self._path(schedule["schedule_id"])
        if path.exists():
            raise ScheduleStoreError(f"Schedule already exists: {schedule['schedule_id']}")
        self._write(path, schedule)

    def save(self, schedule: dict[str, Any]) -> None:
        path = self._path(schedule["schedule_id"])
        if not path.is_file():
            raise ScheduleStoreError(f"Schedule not found: {schedule['schedule_id']}")
        self._write(path, schedule)

    def load(self, schedule_id: str) -> dict[str, Any]:
        path = self._path(schedule_id)
        if not path.is_file():
            raise ScheduleStoreError(f"Schedule not found: {schedule_id}")
        return self._load_path(path)

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        schedules = [self._load_path(path) for path in self.root.glob("*.json")]
        return sorted(
            schedules,
            key=lambda schedule: (
                str(schedule.get("created_at", "")),
                str(schedule.get("schedule_id", "")),
            ),
        )

    def _path(self, schedule_id: str) -> Path:
        if not isinstance(schedule_id, str) or self._SAFE_ID.fullmatch(schedule_id) is None:
            raise ScheduleStoreError("Schedule ID contains unsupported path characters")
        return self.root / f"{schedule_id}.json"

    @staticmethod
    def _load_path(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise ScheduleStoreError(
                f"Could not read schedule file {path.name}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ScheduleStoreError(f"Schedule file is not an object: {path.name}")
        return value

    def _write(self, path: Path, schedule: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
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
                temporary_path = Path(handle.name)
                json.dump(schedule, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise ScheduleStoreError(
                f"Could not persist schedule {schedule['schedule_id']}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
