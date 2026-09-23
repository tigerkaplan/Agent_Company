"""Bounded immutable persistence for independently observed mutation evidence."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


class MutationArtifactError(ValueError):
    """Raised when mutation evidence cannot be persisted or loaded."""


class FileMutationArtifactStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def create(
        self,
        execution_id: str,
        evidence: dict[str, Any],
        diff: str,
        *,
        max_diff_bytes: int,
    ) -> dict[str, Any]:
        path = self._path(execution_id)
        if path.exists():
            raise MutationArtifactError(
                f"Mutation artifact already exists: {execution_id}"
            )
        diff_bytes = diff.encode("utf-8")
        if len(diff_bytes) > max_diff_bytes:
            marker = b"\n[DIFF_TRUNCATED]\n"
            allowed = max(0, max_diff_bytes - len(marker))
            diff = diff_bytes[:allowed].decode("utf-8", errors="ignore") + marker.decode()
        self.root.mkdir(parents=True, exist_ok=True)
        diff_ref = None
        if diff:
            diff_path = self.root / f"{execution_id}.diff"
            self._write_text(diff_path, diff)
            diff_ref = {
                "ref_type": "artifact",
                "ref": f"runtime-mutation-diff:{execution_id}",
                "description": "Bounded runtime-generated mutation diff",
            }
        record = dict(evidence)
        record["diff_ref"] = diff_ref
        self._write_json(path, record)
        return self.artifact_ref(execution_id)

    def load(self, execution_id: str) -> dict[str, Any]:
        path = self._path(execution_id)
        if not path.is_file():
            raise MutationArtifactError(f"Mutation artifact not found: {execution_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MutationArtifactError(
                f"Could not read mutation artifact {execution_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise MutationArtifactError(
                f"Mutation artifact is not an object: {execution_id}"
            )
        return value

    @staticmethod
    def artifact_ref(execution_id: str) -> dict[str, Any]:
        return {
            "ref_type": "artifact",
            "ref": f"runtime-mutation:{execution_id}",
            "description": "Independent bounded mutation evidence",
        }

    def _path(self, execution_id: str) -> Path:
        if self._SAFE_ID.fullmatch(execution_id) is None:
            raise MutationArtifactError("Execution ID contains unsupported path characters")
        return self.root / f"{execution_id}.mutation.json"

    def _write_json(self, path: Path, value: dict[str, Any]) -> None:
        text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        self._write_text(path, text)

    def _write_text(self, path: Path, value: str) -> None:
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
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise MutationArtifactError(
                f"Could not persist mutation artifact {path.name}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
