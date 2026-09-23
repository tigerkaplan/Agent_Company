"""Atomic persistence for controlled Git artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from runtime.git.models import GitChangeSet, GitCommitEvidence, GitContractError


class GitStoreError(ValueError):
    """Raised when Git artifact persistence cannot satisfy an operation."""


class FileGitArtifactStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
    _IMMUTABLE_CHANGE_SET_FIELDS = tuple(
        name
        for name in GitChangeSet.__dataclass_fields__
        if name not in {"status", "approval_ref", "commit_evidence_ref", "error"}
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.change_sets = self.root / "change-sets"
        self.evidence = self.root / "commit-evidence"
        self.diffs = self.root / "diffs"

    def create_change_set(self, change_set: GitChangeSet, diff: str) -> None:
        path = self._path(self.change_sets, change_set.change_set_id, ".change-set.json")
        if path.exists():
            raise GitStoreError(f"Git change set already exists: {change_set.change_set_id}")
        self._write_text(
            self._path(self.diffs, change_set.change_set_id, ".diff"), diff
        )
        self._write_json(path, change_set.to_dict())

    def save_change_set(self, change_set: GitChangeSet) -> None:
        existing = self.load_change_set(change_set.change_set_id)
        if any(
            getattr(existing, name) != getattr(change_set, name)
            for name in self._IMMUTABLE_CHANGE_SET_FIELDS
        ):
            raise GitStoreError("Git change-set update changed immutable authority")
        self._write_json(
            self._path(self.change_sets, change_set.change_set_id, ".change-set.json"),
            change_set.to_dict(),
        )

    def load_change_set(self, change_set_id: str) -> GitChangeSet:
        value = self._load_json(
            self._path(self.change_sets, change_set_id, ".change-set.json"),
            "Git change set",
        )
        try:
            return GitChangeSet.from_dict(value)
        except GitContractError as error:
            raise GitStoreError(f"Git change set is invalid: {change_set_id}: {error}") from error

    def list_change_sets(self) -> list[GitChangeSet]:
        if not self.change_sets.exists():
            return []
        values = [
            self.load_change_set(path.name.removesuffix(".change-set.json"))
            for path in self.change_sets.glob("*.change-set.json")
        ]
        return sorted(values, key=lambda item: (item.created_at, item.change_set_id))

    def load_diff(self, change_set_id: str) -> str:
        path = self._path(self.diffs, change_set_id, ".diff")
        if not path.is_file():
            raise GitStoreError(f"Git change-set diff not found: {change_set_id}")
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise GitStoreError(f"Could not read Git change-set diff: {error}") from error

    def create_evidence(self, evidence: GitCommitEvidence) -> None:
        path = self._path(self.evidence, evidence.evidence_id, ".commit.json")
        if path.exists():
            existing = self.load_evidence(evidence.evidence_id)
            if existing == evidence:
                return
            raise GitStoreError(f"Git commit evidence already exists: {evidence.evidence_id}")
        self._write_json(path, evidence.to_dict())

    def load_evidence(self, evidence_id: str) -> GitCommitEvidence:
        value = self._load_json(
            self._path(self.evidence, evidence_id, ".commit.json"),
            "Git commit evidence",
        )
        try:
            return GitCommitEvidence.from_dict(value)
        except GitContractError as error:
            raise GitStoreError(f"Git commit evidence is invalid: {evidence_id}: {error}") from error

    @staticmethod
    def change_set_ref(change_set_id: str) -> dict[str, str]:
        return {
            "ref_type": "artifact",
            "ref": f"runtime-git-change-set:{change_set_id}",
            "description": "Immutable runtime-generated Git change set",
        }

    @staticmethod
    def diff_ref(change_set_id: str) -> dict[str, str]:
        return {
            "ref_type": "artifact",
            "ref": f"runtime-git-diff:{change_set_id}",
            "description": "Bounded runtime-generated Git change-set diff",
        }

    @staticmethod
    def evidence_ref(evidence_id: str) -> dict[str, str]:
        return {
            "ref_type": "artifact",
            "ref": f"runtime-git-commit:{evidence_id}",
            "description": "Independently verified Git commit evidence",
        }

    def _path(self, root: Path, identifier: str, suffix: str) -> Path:
        if not isinstance(identifier, str) or self._SAFE_ID.fullmatch(identifier) is None:
            raise GitStoreError("Git artifact ID contains unsupported path characters")
        return root / f"{identifier}{suffix}"

    def _load_json(self, path: Path, label: str) -> dict[str, object]:
        if not path.is_file():
            raise GitStoreError(f"{label} not found: {path.stem}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise GitStoreError(f"Could not read {label.lower()}: {error}") from error
        if not isinstance(value, dict):
            raise GitStoreError(f"{label} is not a JSON object")
        return value

    def _write_json(self, path: Path, value: dict[str, object]) -> None:
        self._write_text(
            path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
        )

    @staticmethod
    def _write_text(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
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
                temporary_path = Path(handle.name)
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise GitStoreError(f"Could not persist Git artifact {path.name}: {error}") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
