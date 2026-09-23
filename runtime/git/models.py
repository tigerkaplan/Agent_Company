"""Canonical immutable contracts for controlled Git changes and commits."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Any


GIT_CAPABILITIES = frozenset({"GIT_INSPECT", "GIT_STAGE", "GIT_COMMIT"})
CHANGE_SET_STATUSES = frozenset(
    {"PREVIEW", "PENDING_APPROVAL", "APPROVED", "COMMITTED", "FAILED"}
)


class GitContractError(ValueError):
    """Raised when a Git artifact violates its canonical contract."""


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _validate_ref(value: dict[str, Any] | None, label: str) -> None:
    if value is None:
        return
    if (
        not isinstance(value, dict)
        or set(value) - {"ref_type", "ref", "description"}
        or not isinstance(value.get("ref_type"), str)
        or not isinstance(value.get("ref"), str)
        or not value["ref"]
        or (
            "description" in value
            and not isinstance(value["description"], str)
        )
    ):
        raise GitContractError(f"{label} is not a canonical reference")


def _validate_paths(paths: tuple[str, ...], label: str) -> None:
    if len(paths) > 100 or tuple(sorted(set(paths), key=str.casefold)) != paths:
        raise GitContractError(f"{label} must be unique, sorted, and bounded")
    for path in paths:
        pure = PurePosixPath(path)
        if (
            not isinstance(path, str)
            or not path
            or "\\" in path
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise GitContractError(f"{label} contains an unsafe repository path")


def commit_authorization_fingerprint(scope: dict[str, Any]) -> str:
    """Hash the exact commit authority presented to the local operator."""

    required = {
        "change_set_id",
        "repository_root",
        "base_head",
        "changed_files",
        "diff_fingerprint",
        "commit_message",
    }
    if not isinstance(scope, dict) or set(scope) != required:
        raise GitContractError("Commit approval scope has invalid fields")
    if not all(
        isinstance(scope[name], str) and scope[name]
        for name in required - {"changed_files"}
    ):
        raise GitContractError("Commit approval scope has invalid string fields")
    changed = scope["changed_files"]
    if not isinstance(changed, list) or not all(isinstance(path, str) for path in changed):
        raise GitContractError("Commit approval scope changed_files is invalid")
    _validate_paths(tuple(changed), "Commit approval paths")
    if not _is_digest(scope["diff_fingerprint"]):
        raise GitContractError("Commit approval diff fingerprint is invalid")
    return _digest(scope)


@dataclass(frozen=True)
class GitChangeSet:
    change_set_id: str
    job_id: str
    execution_id: str
    mutation_ref: dict[str, Any]
    repository_root: str
    base_head: str
    changed_files: tuple[str, ...]
    created_files: tuple[str, ...]
    modified_files: tuple[str, ...]
    deleted_files: tuple[str, ...]
    diff_ref: dict[str, Any]
    diff_fingerprint: str
    scope_fingerprint: str
    worktree_fingerprint: str
    unrelated_files: tuple[str, ...]
    unrelated_fingerprint: str
    commit_message: str
    created_at: str
    status: str
    dry_run: bool
    approval_ref: dict[str, Any] | None = None
    commit_evidence_ref: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "change_set_id",
            "job_id",
            "execution_id",
            "repository_root",
            "base_head",
            "commit_message",
            "created_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise GitContractError(f"GitChangeSet.{name} must be non-empty")
        if self.status not in CHANGE_SET_STATUSES:
            raise GitContractError("Git change-set status is not canonical")
        if not isinstance(self.dry_run, bool):
            raise GitContractError("Git change-set dry_run must be a boolean")
        if self.dry_run != (self.status == "PREVIEW"):
            raise GitContractError("Only a dry-run change set may be PREVIEW")
        for name in (
            "changed_files",
            "created_files",
            "modified_files",
            "deleted_files",
            "unrelated_files",
        ):
            _validate_paths(getattr(self, name), f"GitChangeSet.{name}")
        combined = tuple(
            sorted(
                (*self.created_files, *self.modified_files, *self.deleted_files),
                key=str.casefold,
            )
        )
        if combined != self.changed_files or not self.changed_files:
            raise GitContractError("Git change-set file classifications are inconsistent")
        if set(self.changed_files) & set(self.unrelated_files):
            raise GitContractError("Git change-set paths overlap unrelated changes")
        for name in (
            "diff_fingerprint",
            "scope_fingerprint",
            "worktree_fingerprint",
            "unrelated_fingerprint",
        ):
            if not _is_digest(getattr(self, name)):
                raise GitContractError(f"GitChangeSet.{name} is invalid")
        if (
            len(self.base_head) != 40
            or any(character not in "0123456789abcdef" for character in self.base_head)
        ):
            raise GitContractError("Git change-set base HEAD is invalid")
        if (
            not self.commit_message.strip()
            or len(self.commit_message) > 200
            or any(character in self.commit_message for character in "\r\n\0")
        ):
            raise GitContractError("Git commit message is invalid")
        _validate_ref(self.mutation_ref, "Mutation reference")
        _validate_ref(self.diff_ref, "Diff reference")
        _validate_ref(self.approval_ref, "Approval reference")
        _validate_ref(self.commit_evidence_ref, "Commit evidence reference")
        if self.error is not None and (
            not isinstance(self.error, dict)
            or set(self.error) != {"code", "message"}
            or not all(isinstance(value, str) and value for value in self.error.values())
        ):
            raise GitContractError("Git change-set error is invalid")

    @property
    def commit_scope(self) -> dict[str, Any]:
        return {
            "change_set_id": self.change_set_id,
            "repository_root": self.repository_root,
            "base_head": self.base_head,
            "changed_files": list(self.changed_files),
            "diff_fingerprint": self.diff_fingerprint,
            "commit_message": self.commit_message,
        }

    @property
    def authorization_fingerprint(self) -> str:
        return commit_authorization_fingerprint(self.commit_scope)

    def transition(self, status: str, **updates: Any) -> GitChangeSet:
        return replace(self, status=status, **updates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "change_set_id": self.change_set_id,
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "mutation_ref": deepcopy(self.mutation_ref),
            "repository_root": self.repository_root,
            "base_head": self.base_head,
            "changed_files": list(self.changed_files),
            "created_files": list(self.created_files),
            "modified_files": list(self.modified_files),
            "deleted_files": list(self.deleted_files),
            "diff_ref": deepcopy(self.diff_ref),
            "diff_fingerprint": self.diff_fingerprint,
            "scope_fingerprint": self.scope_fingerprint,
            "worktree_fingerprint": self.worktree_fingerprint,
            "unrelated_files": list(self.unrelated_files),
            "unrelated_fingerprint": self.unrelated_fingerprint,
            "commit_message": self.commit_message,
            "created_at": self.created_at,
            "status": self.status,
            "dry_run": self.dry_run,
            "approval_ref": deepcopy(self.approval_ref),
            "commit_evidence_ref": deepcopy(self.commit_evidence_ref),
            "error": deepcopy(self.error),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GitChangeSet:
        expected = set(cls.__dataclass_fields__) | {"schema_version"}
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise GitContractError("Git change-set record has invalid fields or version")
        path_fields = (
            "changed_files",
            "created_files",
            "modified_files",
            "deleted_files",
            "unrelated_files",
        )
        if any(
            not isinstance(value.get(name), list)
            or not all(isinstance(path, str) for path in value[name])
            for name in path_fields
        ):
            raise GitContractError("Git change-set path fields are invalid")
        fields = {name: deepcopy(value[name]) for name in cls.__dataclass_fields__}
        for name in path_fields:
            fields[name] = tuple(fields[name])
        return cls(**fields)


@dataclass(frozen=True)
class GitCommitEvidence:
    evidence_id: str
    change_set_id: str
    job_id: str
    execution_id: str
    repository_root: str
    commit_hash: str
    parent_hash: str
    committed_files: tuple[str, ...]
    commit_message: str
    author_name: str
    author_email: str
    committed_at: str
    approval_ref: dict[str, Any]
    diff_fingerprint: str
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "change_set_id",
            "job_id",
            "execution_id",
            "repository_root",
            "commit_message",
            "author_name",
            "author_email",
            "committed_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise GitContractError(f"GitCommitEvidence.{name} must be non-empty")
        for name in ("commit_hash", "parent_hash"):
            value = getattr(self, name)
            if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
                raise GitContractError(f"GitCommitEvidence.{name} is invalid")
        _validate_paths(self.committed_files, "GitCommitEvidence.committed_files")
        if not self.committed_files:
            raise GitContractError("Git commit evidence requires committed files")
        for name in ("diff_fingerprint", "evidence_fingerprint"):
            if not _is_digest(getattr(self, name)):
                raise GitContractError(f"GitCommitEvidence.{name} is invalid")
        _validate_ref(self.approval_ref, "Commit approval reference")
        fingerprint_input = {
            "evidence_id": self.evidence_id,
            "change_set_id": self.change_set_id,
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "repository_root": self.repository_root,
            "commit_hash": self.commit_hash,
            "parent_hash": self.parent_hash,
            "committed_files": list(self.committed_files),
            "commit_message": self.commit_message,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "committed_at": self.committed_at,
            "approval_ref": self.approval_ref,
            "diff_fingerprint": self.diff_fingerprint,
        }
        if _digest(fingerprint_input) != self.evidence_fingerprint:
            raise GitContractError("Git commit evidence fingerprint does not match")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "evidence_id": self.evidence_id,
            "change_set_id": self.change_set_id,
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "repository_root": self.repository_root,
            "commit_hash": self.commit_hash,
            "parent_hash": self.parent_hash,
            "committed_files": list(self.committed_files),
            "commit_message": self.commit_message,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "committed_at": self.committed_at,
            "approval_ref": deepcopy(self.approval_ref),
            "diff_fingerprint": self.diff_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GitCommitEvidence:
        expected = set(cls.__dataclass_fields__) | {"schema_version"}
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise GitContractError("Git commit evidence has invalid fields or version")
        fields = {name: deepcopy(value[name]) for name in cls.__dataclass_fields__}
        if not isinstance(fields["committed_files"], list):
            raise GitContractError("Git commit evidence files are invalid")
        fields["committed_files"] = tuple(fields["committed_files"])
        return cls(**fields)


def commit_evidence_fingerprint(value: dict[str, Any]) -> str:
    return _digest(value)
