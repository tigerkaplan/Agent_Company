"""Durable webhook provenance plus bounded expendable audit records."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


class WebhookStoreError(ValueError):
    """Raised when webhook provenance or audit persistence is unavailable."""


class FileWebhookStore:
    _MAX_ALIASES_PER_PROVENANCE = 256
    _AUDIT_SUFFIX = ".webhook-audit.json"
    _PROVENANCE_SUFFIX = ".webhook-provenance.json"

    def __init__(self, root: Path, *, max_records: int = 1000) -> None:
        self.root = Path(root)
        self.max_records = max_records

    def find_reservation(
        self, *, source_id: str, event_id: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        matches: list[dict[str, Any]] = []
        for record in self.list_provenance():
            if record.get("source_id") != source_id:
                continue
            event_ids = self._aliases(record, "event_ids", "event_id")
            idempotency_keys = self._aliases(
                record, "idempotency_keys", "idempotency_key"
            )
            if event_id in event_ids or idempotency_key in idempotency_keys:
                matches.append(record)
        provenance_ids = {
            str(item.get("provenance_id") or item.get("audit_id", ""))
            for item in matches
        }
        if len(provenance_ids) > 1:
            raise WebhookStoreError(
                "Webhook identities map to conflicting canonical provenances"
            )
        return matches[0] if matches else None

    def reserve(self, record: dict[str, Any]) -> dict[str, Any] | None:
        source_id = str(record.get("source_id", ""))
        event_id = str(record.get("event_id", ""))
        idempotency_key = str(record.get("idempotency_key", ""))
        if not source_id or not event_id or not idempotency_key:
            raise WebhookStoreError(
                "Webhook reservation requires source, event, and idempotency identifiers"
            )
        existing = self.find_reservation(
            source_id=source_id,
            event_id=event_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing
        provenance_id = str(record.get("audit_id", ""))
        if not provenance_id:
            raise WebhookStoreError("Webhook provenance requires audit_id")
        path = self._provenance_path(provenance_id)
        if path.exists() or self._audit_path(provenance_id).exists():
            raise WebhookStoreError("Webhook provenance already exists")
        self._write(path, record)
        return None

    def bind_aliases(
        self,
        record: dict[str, Any],
        *,
        event_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        updated = deepcopy(record)
        event_ids = self._aliases(updated, "event_ids", "event_id")
        idempotency_keys = self._aliases(
            updated, "idempotency_keys", "idempotency_key"
        )
        if event_id not in event_ids:
            event_ids.append(event_id)
        if idempotency_key not in idempotency_keys:
            idempotency_keys.append(idempotency_key)
        if (
            len(event_ids) > self._MAX_ALIASES_PER_PROVENANCE
            or len(idempotency_keys) > self._MAX_ALIASES_PER_PROVENANCE
        ):
            raise WebhookStoreError("Webhook provenance alias capacity is exhausted")
        updated["event_ids"] = event_ids
        updated["idempotency_keys"] = idempotency_keys
        self.update(updated)
        return updated

    def save(self, record: dict[str, Any], *, prune: bool = True) -> None:
        audit_id = str(record.get("audit_id", ""))
        if not audit_id:
            raise WebhookStoreError("Webhook audit record requires audit_id")
        if record.get("reservation"):
            path = self._provenance_path(audit_id)
        else:
            path = self._audit_path(audit_id)
        if path.exists():
            raise WebhookStoreError("Webhook record already exists")
        self._write(path, record)
        if prune and not record.get("reservation"):
            self._prune()

    def update(self, record: dict[str, Any]) -> None:
        audit_id = str(record.get("audit_id", ""))
        if not audit_id:
            raise WebhookStoreError("Webhook audit record requires audit_id")
        path = (
            self._provenance_path(audit_id)
            if record.get("reservation")
            else self._audit_path(audit_id)
        )
        if record.get("reservation") and not path.is_file():
            legacy_path = self._audit_path(audit_id)
            if legacy_path.is_file():
                path = legacy_path
        if not path.is_file():
            raise WebhookStoreError("Webhook record does not exist")
        self._write(path, record)

    def list(self) -> list[dict[str, Any]]:
        return self._sorted([*self.list_provenance(), *self.list_audit()])

    def list_provenance(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        records: dict[str, dict[str, Any]] = {}
        for path in sorted(self.root.glob(f"*{self._PROVENANCE_SUFFIX}")):
            value = self._read(path)
            records[str(value.get("audit_id", path.name))] = value
        for path in sorted(self.root.glob(f"*{self._AUDIT_SUFFIX}")):
            value = self._read(path)
            if value.get("reservation"):
                records.setdefault(str(value.get("audit_id", path.name)), value)
        return self._sorted(list(records.values()))

    def list_audit(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        records = []
        for path in sorted(self.root.glob(f"*{self._AUDIT_SUFFIX}")):
            value = self._read(path)
            if not value.get("reservation"):
                records.append(value)
        return self._sorted(records)

    @staticmethod
    def _sorted(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            records,
            key=lambda item: (item.get("received_at", ""), item.get("audit_id", "")),
        )

    def _audit_path(self, audit_id: str) -> Path:
        return self.root / f"{self._digest(audit_id)}{self._AUDIT_SUFFIX}"

    def _provenance_path(self, provenance_id: str) -> Path:
        return self.root / f"{self._digest(provenance_id)}{self._PROVENANCE_SUFFIX}"

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

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
            raise WebhookStoreError(f"Could not persist webhook record: {error}") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _prune(self) -> None:
        records = self._expendable_audit_paths()
        while len(records) > self.max_records:
            removable = records.pop(0)
            try:
                removable.unlink()
            except OSError as error:
                raise WebhookStoreError(f"Could not prune webhook audit record: {error}") from error

    def _expendable_audit_paths(self) -> list[Path]:
        if not self.root.exists():
            return []
        paths = []
        for path in self.root.glob(f"*{self._AUDIT_SUFFIX}"):
            if not self._read(path).get("reservation"):
                paths.append(path)
        return sorted(paths, key=lambda path: (path.stat().st_mtime, path.name))

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WebhookStoreError(
                f"Could not read webhook record: {error}"
            ) from error
        if not isinstance(value, dict):
            raise WebhookStoreError("Webhook record is not an object")
        return value

    @staticmethod
    def _aliases(
        record: dict[str, Any], list_field: str, primary_field: str
    ) -> list[str]:
        value = record.get(list_field)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return list(dict.fromkeys(value))
        primary = record.get(primary_field)
        return [primary] if isinstance(primary, str) and primary else []
