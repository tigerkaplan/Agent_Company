"""Atomic immutable persistence for canonical EvalResult records."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from runtime.evals.models import EvalContractError, EvalResult
from runtime.evals.validation import EvalResultValidator, EvalValidationError


class EvalStoreError(ValueError):
    """Raised when an EvalResult cannot be safely persisted or loaded."""


class FileEvalStore:
    _SAFE_ID = re.compile(r"eval-[0-9a-f]{32}\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.validator = EvalResultValidator()

    def create(self, result: EvalResult) -> EvalResult:
        try:
            self.validator.validate_model(result)
            result.verify_identity()
        except (EvalValidationError, EvalContractError) as error:
            raise EvalStoreError(f"Invalid EvalResult: {error}") from error
        path = self._path(result.eval_id)
        if path.exists():
            existing = self.load(result.eval_id)
            if existing.semantic_dict() != result.semantic_dict():
                raise EvalStoreError(
                    f"EvalResult identity collision or immutable record mismatch: {result.eval_id}"
                )
            return existing
        self._write(path, result.to_dict())
        return result

    def load(self, eval_id: str) -> EvalResult:
        path = self._path(eval_id)
        if not path.is_file():
            raise EvalStoreError(f"EvalResult not found: {eval_id}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise EvalStoreError(f"Could not read EvalResult {eval_id}: {error}") from error
        if not isinstance(value, dict):
            raise EvalStoreError(f"Persisted EvalResult is not an object: {eval_id}")
        try:
            result = self.validator.validate(value)
            result.verify_identity()
        except (EvalValidationError, EvalContractError) as error:
            raise EvalStoreError(f"Invalid persisted EvalResult {eval_id}: {error}") from error
        if result.eval_id != eval_id:
            raise EvalStoreError(f"Persisted EvalResult identity mismatch: {eval_id}")
        return result

    def list(self) -> list[EvalResult]:
        if not self.root.exists():
            return []
        values = [
            self.load(path.name.removesuffix(".eval.json"))
            for path in self.root.glob("*.eval.json")
        ]
        return sorted(values, key=lambda value: (value.created_at, value.eval_id))

    def _path(self, eval_id: str) -> Path:
        if self._SAFE_ID.fullmatch(eval_id) is None:
            raise EvalStoreError("Eval ID contains unsupported path characters")
        return self.root / f"{eval_id}.eval.json"

    def _write(self, path: Path, value: dict) -> None:
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
                json.dump(
                    value,
                    handle,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise EvalStoreError(
                f"Could not persist EvalResult {path.stem}: invalid or unserializable canonical data"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
