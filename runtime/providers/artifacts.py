"""Bounded local persistence for provider process output."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.providers.models import ProviderExecutionResult, ProviderSelection


class ProviderArtifactError(ValueError):
    """Raised when provider process output cannot be persisted."""


class FileProviderArtifactStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def create(
        self,
        execution_id: str,
        selection: ProviderSelection,
        result: ProviderExecutionResult,
    ) -> dict[str, Any]:
        if self._SAFE_ID.fullmatch(execution_id) is None:
            raise ProviderArtifactError("Execution ID contains unsupported path characters")
        path = self._path(execution_id)
        if path.exists():
            raise ProviderArtifactError(f"Provider artifact already exists: {execution_id}")
        record = {
            "schema_version": 1,
            "execution_id": execution_id,
            "selection": {
                "requested_provider": selection.requested_provider,
                "preferred_provider": selection.preferred_provider,
                "actual_provider": selection.actual_provider,
                "fallback_used": selection.fallback_used,
                "fallback_reason": selection.fallback_reason,
                "execution_mode": selection.execution_mode,
            },
            "process": {
                "status": result.status,
                "exit_code": result.exit_code,
                "requested_sandbox_mode": result.requested_sandbox_mode,
                "effective_sandbox_mode": result.effective_sandbox_mode,
                "stdout": bound_text(sanitize_provider_text(result.stdout), 1024 * 1024),
                "stderr": bound_text(sanitize_provider_text(result.stderr), 64 * 1024),
                "error_category": result.error_category,
                "error_message": bound_text(
                    sanitize_provider_text(result.error_message), 4096
                ),
            },
        }
        self._write(path, record)
        return {
            "ref_type": "artifact",
            "ref": f"runtime-provider-output:{execution_id}",
            "description": "Bounded local provider process output",
        }

    def load(self, execution_id: str) -> dict[str, Any]:
        path = self._path(execution_id)
        if not path.is_file():
            raise ProviderArtifactError(f"Provider artifact not found: {execution_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            raise ProviderArtifactError(
                f"Could not read provider artifact {execution_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ProviderArtifactError(
                f"Provider artifact is not an object: {execution_id}"
            )
        return value

    def exists(self, execution_id: str) -> bool:
        return self._path(execution_id).is_file()

    def _path(self, execution_id: str) -> Path:
        if self._SAFE_ID.fullmatch(execution_id) is None:
            raise ProviderArtifactError("Execution ID contains unsupported path characters")
        return self.root / f"{execution_id}.provider.json"

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
            raise ProviderArtifactError(
                f"Could not persist provider artifact {path.stem}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
