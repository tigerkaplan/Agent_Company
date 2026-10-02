"""Atomic local persistence for review artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.review.models import ReviewPackage, ReviewResult


class ReviewStoreError(ValueError):
    """Raised when review artifacts cannot be persisted or loaded."""


class FileReviewStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def create(
        self,
        package: ReviewPackage,
        result: ReviewResult,
        raw_output: str,
        *, execution_request: dict | None = None,
    ) -> dict[str, Any]:
        path = self._path(result.review_id)
        if path.exists():
            raise ReviewStoreError(f"Review artifact already exists: {result.review_id}")
        record = {
            "schema_version": 1,
            "package": bound_text(
                sanitize_provider_text(package.render()), 768 * 1024
            ),
            "raw_output": bound_text(sanitize_provider_text(raw_output), 256 * 1024),
            "result": result.to_dict(),
        }
        from runtime.core.task_contract import digest
        record["task_contract_digest"] = digest(package.job.get("task_contract"))
        record["execution_request_digest"] = digest(execution_request)
        self._write(path, record)
        return {
            "ref_type": "review",
            "ref": f"runtime-review:{result.review_id}",
            "description": "Normalized review decision and bounded evidence package",
        }

    def load(self, review_id: str) -> dict[str, Any]:
        path = self._path(review_id)
        if not path.is_file():
            raise ReviewStoreError(f"Review artifact not found: {review_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            raise ReviewStoreError(
                f"Could not read review artifact {review_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ReviewStoreError(f"Review artifact is not an object: {review_id}")
        return value

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        values = [
            self.load(path.name.removesuffix(".review.json"))
            for path in self.root.glob("*.review.json")
        ]
        return sorted(
            values,
            key=lambda value: (
                value.get("result", {}).get("created_at", ""),
                value.get("result", {}).get("review_id", ""),
            ),
        )

    def _path(self, review_id: str) -> Path:
        if self._SAFE_ID.fullmatch(review_id) is None:
            raise ReviewStoreError("Review ID contains unsupported path characters")
        return self.root / f"{review_id}.review.json"

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
            raise ReviewStoreError(
                f"Could not persist review artifact {path.stem}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
