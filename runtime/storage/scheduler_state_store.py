"""Atomic bounded persistence for the autonomous scheduler and its audit trail."""

from __future__ import annotations

import json
import os
import re
import tempfile
import sys
from pathlib import Path
from typing import Any


class SchedulerStateStoreError(ValueError):
    """Raised when scheduler operational state cannot be persisted safely."""


class FileSchedulerStateStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path, *, max_audit_events: int = 1000) -> None:
        self.root = Path(root)
        self.state_path = self.root / "scheduler-state.json"
        self.audit_root = self.root / "audit"
        self.max_audit_events = max_audit_events
        self._run_lock_handle = None

    def acquire_run_lock(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / ".run.lock").open("a+b")
        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            handle.close()
            raise SchedulerStateStoreError("Another scheduler loop already holds the run lock") from error
        self._run_lock_handle = handle

    def release_run_lock(self) -> None:
        handle = self._run_lock_handle
        if handle is None:
            return
        try:
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise SchedulerStateStoreError("Could not release scheduler run lock") from error
        finally:
            handle.close()
            self._run_lock_handle = None

    def request_stop(self, recorded_at: str) -> bool:
        state = self.load()
        if state is None or state.get("status") not in {"running", "stopping"}:
            return False
        state["stop_requested"] = True
        state["status"] = "stopping"
        state["last_updated_at"] = recorded_at
        self.save(state)
        return True

    def load(self) -> dict[str, Any] | None:
        if not self.state_path.is_file():
            return None
        return self._load_json(self.state_path, "Scheduler state")

    def save(self, state: dict[str, Any]) -> None:
        self._write_json(self.state_path, state)

    def append_event(self, event: dict[str, Any]) -> None:
        event_id = str(event.get("event_id", ""))
        if self._SAFE_ID.fullmatch(event_id) is None:
            raise SchedulerStateStoreError("Scheduler audit event ID is invalid")
        path = self.audit_root / f"{event_id}.json"
        if path.exists():
            existing = self._load_json(path, "Scheduler audit event")
            if existing == event:
                return
            raise SchedulerStateStoreError("Scheduler audit event ID is not unique")
        self._write_json(path, event)
        paths = sorted(
            self.audit_root.glob("*.json"),
            key=lambda item: (item.stat().st_mtime_ns, item.name),
        )
        for expired in paths[: max(0, len(paths) - self.max_audit_events)]:
            expired.unlink()

    def list_events(self) -> list[dict[str, Any]]:
        if not self.audit_root.exists():
            return []
        values = [self._load_json(path, "Scheduler audit event") for path in self.audit_root.glob("*.json")]
        return sorted(values, key=lambda event: (event["recorded_at"], event["event_id"]))

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SchedulerStateStoreError(f"Could not read {label.lower()}: {error}") from error
        if not isinstance(value, dict):
            raise SchedulerStateStoreError(f"{label} is not a JSON object")
        return value

    def _write_json(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
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
            raise SchedulerStateStoreError(f"Could not persist {path.name}: {error}") from error
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
