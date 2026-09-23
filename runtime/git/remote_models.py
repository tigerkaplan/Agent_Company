"""Immutable contracts for controlled remote Git and pull-request actions."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

from runtime.git.models import GitContractError, _is_digest, _validate_ref


REMOTE_GIT_CAPABILITIES = frozenset(
    {"GIT_REMOTE_INSPECT", "GIT_PUSH", "PULL_REQUEST_CREATE"}
)
REMOTE_ACTIONS = frozenset({"PUSH_GIT_COMMIT", "CREATE_PULL_REQUEST"})
PUSH_PLAN_STATUSES = frozenset(
    {"PREVIEW", "PENDING_APPROVAL", "APPROVED", "PUSHED", "FAILED"}
)
PR_PLAN_STATUSES = frozenset(
    {"PREVIEW", "PENDING_APPROVAL", "APPROVED", "CREATED", "EXISTING", "FAILED"}
)
_SAFE_BRANCH = re.compile(
    r"(?!.*(?:\.\.|//|@\{|\\|\s))(?!/)(?!.*[/.]$)(?!.*\.lock(?:/|$))[A-Za-z0-9._/-]{1,200}\Z"
)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()


def validate_branch(value: str, label: str = "Branch") -> str:
    if not isinstance(value, str) or _SAFE_BRANCH.fullmatch(value) is None:
        raise GitContractError(f"{label} is not a safe bounded branch name")
    return value


def remote_authorization_fingerprint(
    requested_action: str, scope: dict[str, Any]
) -> str:
    if requested_action == "PUSH_GIT_COMMIT":
        required = {
            "push_plan_id",
            "change_set_id",
            "repository_root",
            "commit_hash",
            "remote_name",
            "remote_url_display",
            "remote_url_fingerprint",
            "remote_branch",
            "expected_remote_head",
        }
    elif requested_action == "CREATE_PULL_REQUEST":
        required = {
            "pull_request_plan_id",
            "push_evidence_id",
            "repository_slug",
            "head_branch",
            "base_branch",
            "head_commit",
            "title",
            "body_fingerprint",
        }
    else:
        raise GitContractError("Remote approval action is not canonical")
    if not isinstance(scope, dict) or set(scope) != required:
        raise GitContractError("Remote approval scope has invalid fields")
    nullable = {"expected_remote_head"} if requested_action == "PUSH_GIT_COMMIT" else set()
    for name in required - nullable:
        value = scope.get(name)
        if name == "body_fingerprint" or name == "remote_url_fingerprint":
            if not _is_digest(value):
                raise GitContractError("Remote approval fingerprint field is invalid")
        elif not isinstance(value, str) or not value:
            raise GitContractError("Remote approval scope has invalid string fields")
    if requested_action == "PUSH_GIT_COMMIT":
        head = scope.get("expected_remote_head")
        if head is not None and (
            not isinstance(head, str)
            or len(head) != 40
            or any(character not in "0123456789abcdef" for character in head)
        ):
            raise GitContractError("Expected remote HEAD is invalid")
        validate_branch(scope["remote_branch"], "Remote branch")
    else:
        validate_branch(scope["head_branch"], "PR head branch")
        validate_branch(scope["base_branch"], "PR base branch")
    return _digest({"requested_action": requested_action, "scope": scope})


@dataclass(frozen=True)
class PushPlan:
    push_plan_id: str
    change_set_id: str
    commit_evidence_ref: dict[str, Any]
    job_id: str
    execution_id: str
    repository_root: str
    commit_hash: str
    parent_hash: str
    local_branch: str
    remote_name: str
    remote_kind: str
    remote_host: str | None
    repository_slug: str | None
    remote_url_display: str
    remote_url_fingerprint: str
    remote_branch: str
    expected_remote_head: str | None
    created_at: str
    status: str
    dry_run: bool
    approval_ref: dict[str, Any] | None = None
    push_evidence_ref: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "push_plan_id",
            "change_set_id",
            "job_id",
            "execution_id",
            "repository_root",
            "commit_hash",
            "parent_hash",
            "local_branch",
            "remote_name",
            "remote_kind",
            "remote_url_display",
            "remote_branch",
            "created_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise GitContractError(f"PushPlan.{name} must be non-empty")
        if self.status not in PUSH_PLAN_STATUSES:
            raise GitContractError("Push plan status is not canonical")
        if self.dry_run != (self.status == "PREVIEW"):
            raise GitContractError("Only a dry-run push plan may be PREVIEW")
        if self.remote_kind not in {"local", "https", "ssh"}:
            raise GitContractError("Remote kind is not canonical")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", self.remote_name):
            raise GitContractError("Remote name is invalid")
        validate_branch(self.local_branch, "Local branch")
        validate_branch(self.remote_branch, "Remote branch")
        for name in ("commit_hash", "parent_hash"):
            value = getattr(self, name)
            if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
                raise GitContractError(f"PushPlan.{name} is invalid")
        if self.expected_remote_head is not None and (
            len(self.expected_remote_head) != 40
            or any(character not in "0123456789abcdef" for character in self.expected_remote_head)
        ):
            raise GitContractError("PushPlan.expected_remote_head is invalid")
        if not _is_digest(self.remote_url_fingerprint):
            raise GitContractError("Push plan remote URL fingerprint is invalid")
        if self.remote_kind == "local" and (self.remote_host or self.repository_slug):
            raise GitContractError("Local remote cannot contain hosted repository metadata")
        if self.remote_kind != "local" and (not self.remote_host or not self.repository_slug):
            raise GitContractError("Hosted remote requires host and repository slug")
        _validate_ref(self.commit_evidence_ref, "Commit evidence reference")
        _validate_ref(self.approval_ref, "Push approval reference")
        _validate_ref(self.push_evidence_ref, "Push evidence reference")

    @property
    def approval_scope(self) -> dict[str, Any]:
        return {
            "push_plan_id": self.push_plan_id,
            "change_set_id": self.change_set_id,
            "repository_root": self.repository_root,
            "commit_hash": self.commit_hash,
            "remote_name": self.remote_name,
            "remote_url_display": self.remote_url_display,
            "remote_url_fingerprint": self.remote_url_fingerprint,
            "remote_branch": self.remote_branch,
            "expected_remote_head": self.expected_remote_head,
        }

    @property
    def authorization_fingerprint(self) -> str:
        return remote_authorization_fingerprint("PUSH_GIT_COMMIT", self.approval_scope)

    def transition(self, status: str, **updates: Any) -> PushPlan:
        return replace(self, status=status, **updates)

    def to_dict(self) -> dict[str, Any]:
        value = {name: deepcopy(getattr(self, name)) for name in self.__dataclass_fields__}
        return {"schema_version": 1, **value}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PushPlan:
        expected = set(cls.__dataclass_fields__) | {"schema_version"}
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise GitContractError("Push plan has invalid fields or version")
        return cls(**{name: deepcopy(value[name]) for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class PushEvidence:
    push_evidence_id: str
    push_plan_id: str
    change_set_id: str
    commit_evidence_ref: dict[str, Any]
    repository_root: str
    commit_hash: str
    remote_name: str
    remote_url_display: str
    remote_url_fingerprint: str
    remote_branch: str
    remote_head_before: str | None
    remote_head_after: str
    approval_ref: dict[str, Any]
    pushed_at: str
    already_present: bool
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "push_evidence_id",
            "push_plan_id",
            "change_set_id",
            "repository_root",
            "commit_hash",
            "remote_name",
            "remote_url_display",
            "remote_branch",
            "remote_head_after",
            "pushed_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise GitContractError(f"PushEvidence.{name} must be non-empty")
        validate_branch(self.remote_branch, "Remote branch")
        for name in ("commit_hash", "remote_head_after"):
            value = getattr(self, name)
            if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
                raise GitContractError(f"PushEvidence.{name} is invalid")
        if self.remote_head_before is not None and (
            len(self.remote_head_before) != 40
            or any(character not in "0123456789abcdef" for character in self.remote_head_before)
        ):
            raise GitContractError("PushEvidence.remote_head_before is invalid")
        if not isinstance(self.already_present, bool):
            raise GitContractError("PushEvidence.already_present must be boolean")
        if not _is_digest(self.remote_url_fingerprint) or not _is_digest(self.evidence_fingerprint):
            raise GitContractError("Push evidence fingerprint is invalid")
        _validate_ref(self.commit_evidence_ref, "Commit evidence reference")
        _validate_ref(self.approval_ref, "Push approval reference")
        payload = self.to_dict()
        payload.pop("schema_version")
        payload.pop("evidence_fingerprint")
        if _digest(payload) != self.evidence_fingerprint:
            raise GitContractError("Push evidence fingerprint does not match")

    def to_dict(self) -> dict[str, Any]:
        value = {name: deepcopy(getattr(self, name)) for name in self.__dataclass_fields__}
        return {"schema_version": 1, **value}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PushEvidence:
        expected = set(cls.__dataclass_fields__) | {"schema_version"}
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise GitContractError("Push evidence has invalid fields or version")
        return cls(**{name: deepcopy(value[name]) for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class PullRequestPlan:
    pull_request_plan_id: str
    push_evidence_ref: dict[str, Any]
    job_id: str
    execution_id: str
    forge: str
    repository_slug: str
    head_branch: str
    base_branch: str
    head_commit: str
    title: str
    body_ref: dict[str, Any]
    body_fingerprint: str
    created_at: str
    status: str
    dry_run: bool
    approval_ref: dict[str, Any] | None = None
    pull_request_evidence_ref: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "pull_request_plan_id",
            "job_id",
            "execution_id",
            "forge",
            "repository_slug",
            "head_branch",
            "base_branch",
            "head_commit",
            "title",
            "created_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise GitContractError(f"PullRequestPlan.{name} must be non-empty")
        if self.forge != "github":
            raise GitContractError("Only the bounded GitHub forge adapter is supported")
        if self.status not in PR_PLAN_STATUSES:
            raise GitContractError("Pull-request plan status is not canonical")
        if self.dry_run != (self.status == "PREVIEW"):
            raise GitContractError("Only a dry-run pull-request plan may be PREVIEW")
        validate_branch(self.head_branch, "PR head branch")
        validate_branch(self.base_branch, "PR base branch")
        if self.head_branch == self.base_branch:
            raise GitContractError("Pull-request head and base branches must differ")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository_slug):
            raise GitContractError("Pull-request repository slug is invalid")
        if len(self.head_commit) != 40 or any(
            character not in "0123456789abcdef" for character in self.head_commit
        ):
            raise GitContractError("Pull-request head commit is invalid")
        if len(self.title) > 256 or any(character in self.title for character in "\r\n\0"):
            raise GitContractError("Pull-request title is invalid")
        if not _is_digest(self.body_fingerprint):
            raise GitContractError("Pull-request body fingerprint is invalid")
        _validate_ref(self.push_evidence_ref, "Push evidence reference")
        _validate_ref(self.body_ref, "Pull-request body reference")
        _validate_ref(self.approval_ref, "Pull-request approval reference")
        _validate_ref(self.pull_request_evidence_ref, "Pull-request evidence reference")

    @property
    def approval_scope(self) -> dict[str, Any]:
        return {
            "pull_request_plan_id": self.pull_request_plan_id,
            "push_evidence_id": self.push_evidence_ref["ref"].split(":", 1)[1],
            "repository_slug": self.repository_slug,
            "head_branch": self.head_branch,
            "base_branch": self.base_branch,
            "head_commit": self.head_commit,
            "title": self.title,
            "body_fingerprint": self.body_fingerprint,
        }

    @property
    def authorization_fingerprint(self) -> str:
        return remote_authorization_fingerprint(
            "CREATE_PULL_REQUEST", self.approval_scope
        )

    def transition(self, status: str, **updates: Any) -> PullRequestPlan:
        return replace(self, status=status, **updates)

    def to_dict(self) -> dict[str, Any]:
        value = {name: deepcopy(getattr(self, name)) for name in self.__dataclass_fields__}
        return {"schema_version": 1, **value}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PullRequestPlan:
        expected = set(cls.__dataclass_fields__) | {"schema_version"}
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise GitContractError("Pull-request plan has invalid fields or version")
        return cls(**{name: deepcopy(value[name]) for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class PullRequestEvidence:
    pull_request_evidence_id: str
    pull_request_plan_id: str
    push_evidence_ref: dict[str, Any]
    repository_slug: str
    head_branch: str
    base_branch: str
    head_commit: str
    pull_request_number: int
    pull_request_url: str
    title: str
    body_fingerprint: str
    approval_ref: dict[str, Any]
    created_at: str
    already_present: bool
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "pull_request_evidence_id",
            "pull_request_plan_id",
            "repository_slug",
            "head_branch",
            "base_branch",
            "head_commit",
            "pull_request_url",
            "title",
            "created_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise GitContractError(f"PullRequestEvidence.{name} must be non-empty")
        if self.pull_request_number < 1 or not isinstance(self.already_present, bool):
            raise GitContractError("Pull-request evidence number or state is invalid")
        validate_branch(self.head_branch, "PR head branch")
        validate_branch(self.base_branch, "PR base branch")
        if self.head_branch == self.base_branch:
            raise GitContractError("Pull-request evidence branches must differ")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository_slug):
            raise GitContractError("Pull-request evidence repository slug is invalid")
        if len(self.head_commit) != 40 or any(
            character not in "0123456789abcdef" for character in self.head_commit
        ):
            raise GitContractError("Pull-request evidence head commit is invalid")
        if self.pull_request_url != (
            f"https://github.com/{self.repository_slug}/pull/{self.pull_request_number}"
        ):
            raise GitContractError("Pull-request evidence URL is outside the approved repository")
        if len(self.title) > 256 or any(
            character in self.title for character in "\r\n\0"
        ):
            raise GitContractError("Pull-request evidence title is invalid")
        if not _is_digest(self.body_fingerprint) or not _is_digest(self.evidence_fingerprint):
            raise GitContractError("Pull-request evidence fingerprint is invalid")
        _validate_ref(self.push_evidence_ref, "Push evidence reference")
        _validate_ref(self.approval_ref, "Pull-request approval reference")
        payload = self.to_dict()
        payload.pop("schema_version")
        payload.pop("evidence_fingerprint")
        if _digest(payload) != self.evidence_fingerprint:
            raise GitContractError("Pull-request evidence fingerprint does not match")

    def to_dict(self) -> dict[str, Any]:
        value = {name: deepcopy(getattr(self, name)) for name in self.__dataclass_fields__}
        return {"schema_version": 1, **value}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PullRequestEvidence:
        expected = set(cls.__dataclass_fields__) | {"schema_version"}
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise GitContractError("Pull-request evidence has invalid fields or version")
        return cls(**{name: deepcopy(value[name]) for name in cls.__dataclass_fields__})


def remote_evidence_fingerprint(value: dict[str, Any]) -> str:
    return _digest(value)
