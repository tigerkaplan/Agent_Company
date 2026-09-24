"""Bounded local persistence for remote command replay and audit records."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class RemoteStoreError(ValueError):
    """Raised when remote command persistence fails."""


class FileRemoteCommandStore:
    _PROTECTED_AUDIT_STATES = {
        "AUTHORIZED",
        "MUTATION_ATTEMPTED",
        "RECONCILIATION_REQUIRED",
    }

    def __init__(self, root: Path, *, max_records: int = 1000) -> None:
        self.root = Path(root)
        self.max_records = max_records

    def load(self, command_id: str) -> dict[str, Any] | None:
        path = self._path(command_id)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RemoteStoreError(f"Could not read remote command record: {error}") from error
        if not isinstance(value, dict):
            raise RemoteStoreError("Remote command record is not an object")
        return value

    def find_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        for record in self.list():
            if record.get("idempotency_key") == idempotency_key:
                return record
        return None

    def save(self, record: dict[str, Any]) -> None:
        command_id = str(record.get("command_id", ""))
        if not command_id:
            raise RemoteStoreError("Remote command record requires command_id")
        path = self._path(command_id)
        if path.exists():
            raise RemoteStoreError(f"Remote command already recorded: {command_id}")
        self._make_capacity()
        self._write(path, record)

    def update(self, record: dict[str, Any]) -> None:
        command_id = str(record.get("command_id", ""))
        if not command_id:
            raise RemoteStoreError("Remote command record requires command_id")
        path = self._path(command_id)
        if not path.is_file():
            raise RemoteStoreError(f"Remote command record does not exist: {command_id}")
        self._write(path, record)

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        records = []
        for path in sorted(self.root.glob("*.remote-command.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RemoteStoreError(f"Could not read remote command record: {error}") from error
            if not isinstance(value, dict):
                raise RemoteStoreError("Remote command record is not an object")
            records.append(value)
        return sorted(records, key=lambda item: (item.get("processed_at", ""), item.get("command_id", "")))

    def _path(self, command_id: str) -> Path:
        digest = hashlib.sha256(command_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.remote-command.json"

    def _write(self, path: Path, value: dict[str, Any]) -> None:
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
                json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise RemoteStoreError(f"Could not persist remote command record: {error}") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _make_capacity(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        records = sorted(
            self.root.glob("*.remote-command.json"),
            key=lambda path: (path.stat().st_mtime, path.name),
        )
        while len(records) >= self.max_records:
            removable = next(
                (
                    path
                    for path in records
                    if self._audit_state(path) not in self._PROTECTED_AUDIT_STATES
                ),
                None,
            )
            if removable is None:
                raise RemoteStoreError(
                    "Remote audit capacity is occupied by incomplete recovery records"
                )
            records.remove(removable)
            try:
                removable.unlink()
            except OSError as error:
                raise RemoteStoreError(f"Could not prune remote command record: {error}") from error

    @staticmethod
    def _audit_state(path: Path) -> str:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RemoteStoreError(
                f"Could not inspect remote command record: {error}"
            ) from error
        if not isinstance(value, dict):
            raise RemoteStoreError("Remote command record is not an object")
        return str(value.get("audit_state", ""))
