"""Atomic local persistence for execution request/result artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from runtime.execution.models import ExecutionRequest, ExecutionResult


class ExecutionStoreError(ValueError):
    """Raised when an execution artifact cannot be persisted."""


class FileExecutionStore:
    """Store one immutable request/result record per execution."""

    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def create(
        self,
        request: ExecutionRequest | None,
        result: ExecutionResult,
    ) -> Path:
        path = self._path(result.execution_id)
        if path.exists():
            raise ExecutionStoreError(
                f"Execution artifact already exists: {result.execution_id}"
            )
        record: dict[str, Any] = {
            "schema_version": 1,
            "request": request.to_dict() if request is not None else None,
            "result": result.to_dict(),
        }
        self._write(path, record)
        return path

    def load(self, execution_id: str) -> dict[str, Any]:
        path = self._path(execution_id)
        if not path.is_file():
            raise ExecutionStoreError(f"Execution artifact not found: {execution_id}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionStoreError(
                f"Could not read execution artifact {execution_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ExecutionStoreError(
                f"Execution artifact is not an object: {execution_id}"
            )
        return value

    def _path(self, execution_id: str) -> Path:
        if self._SAFE_ID.fullmatch(execution_id) is None:
            raise ExecutionStoreError("Execution ID contains unsupported path characters")
        return self.root / f"{execution_id}.json"

    def _write(self, path: Path, record: dict[str, Any]) -> None:
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
                json.dump(record, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise ExecutionStoreError(
                f"Could not persist execution artifact {path.stem}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

