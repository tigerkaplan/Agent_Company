"""Atomic persistence for push and pull-request plans and evidence."""

from __future__ import annotations

import json
from pathlib import Path

from runtime.git.models import GitContractError
from runtime.git.remote_models import (
    PullRequestEvidence,
    PullRequestPlan,
    PushEvidence,
    PushPlan,
)
from runtime.git.store import FileGitArtifactStore, GitStoreError


class FileRemoteGitArtifactStore(FileGitArtifactStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.push_plans = self.root / "push-plans"
        self.push_evidence = self.root / "push-evidence"
        self.pull_request_plans = self.root / "pull-request-plans"
        self.pull_request_bodies = self.root / "pull-request-bodies"
        self.pull_request_evidence = self.root / "pull-request-evidence"

    def create_push_plan(self, plan: PushPlan) -> None:
        self._create(self.push_plans, plan.push_plan_id, ".push-plan.json", plan.to_dict())

    def save_push_plan(self, plan: PushPlan) -> None:
        existing = self.load_push_plan(plan.push_plan_id)
        mutable = {"status", "approval_ref", "push_evidence_ref"}
        self._check_immutable(existing, plan, mutable, "Push plan")
        self._write_json(
            self._path(self.push_plans, plan.push_plan_id, ".push-plan.json"),
            plan.to_dict(),
        )

    def load_push_plan(self, plan_id: str) -> PushPlan:
        return self._load_model(
            self.push_plans, plan_id, ".push-plan.json", PushPlan.from_dict, "Push plan"
        )

    def create_push_evidence(self, evidence: PushEvidence) -> None:
        self._create(
            self.push_evidence,
            evidence.push_evidence_id,
            ".push.json",
            evidence.to_dict(),
            idempotent=True,
        )

    def load_push_evidence(self, evidence_id: str) -> PushEvidence:
        return self._load_model(
            self.push_evidence,
            evidence_id,
            ".push.json",
            PushEvidence.from_dict,
            "Push evidence",
        )

    def create_pull_request_plan(self, plan: PullRequestPlan, body: str) -> None:
        self._write_text(
            self._path(
                self.pull_request_bodies, plan.pull_request_plan_id, ".body.md"
            ),
            body,
        )
        self._create(
            self.pull_request_plans,
            plan.pull_request_plan_id,
            ".pr-plan.json",
            plan.to_dict(),
        )

    def save_pull_request_plan(self, plan: PullRequestPlan) -> None:
        existing = self.load_pull_request_plan(plan.pull_request_plan_id)
        mutable = {"status", "approval_ref", "pull_request_evidence_ref"}
        self._check_immutable(existing, plan, mutable, "Pull-request plan")
        self._write_json(
            self._path(
                self.pull_request_plans, plan.pull_request_plan_id, ".pr-plan.json"
            ),
            plan.to_dict(),
        )

    def load_pull_request_plan(self, plan_id: str) -> PullRequestPlan:
        return self._load_model(
            self.pull_request_plans,
            plan_id,
            ".pr-plan.json",
            PullRequestPlan.from_dict,
            "Pull-request plan",
        )

    def load_pull_request_body(self, plan_id: str) -> str:
        path = self._path(self.pull_request_bodies, plan_id, ".body.md")
        if not path.is_file():
            raise GitStoreError(f"Pull-request body not found: {plan_id}")
        try:
            if path.stat().st_size > 64 * 1024:
                raise GitStoreError("Pull-request body exceeds the bounded limit")
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise GitStoreError(f"Could not read pull-request body: {error}") from error

    def create_pull_request_evidence(self, evidence: PullRequestEvidence) -> None:
        self._create(
            self.pull_request_evidence,
            evidence.pull_request_evidence_id,
            ".pr.json",
            evidence.to_dict(),
            idempotent=True,
        )

    def load_pull_request_evidence(self, evidence_id: str) -> PullRequestEvidence:
        return self._load_model(
            self.pull_request_evidence,
            evidence_id,
            ".pr.json",
            PullRequestEvidence.from_dict,
            "Pull-request evidence",
        )

    @staticmethod
    def push_plan_ref(plan_id: str) -> dict[str, str]:
        return {"ref_type": "artifact", "ref": f"runtime-git-push-plan:{plan_id}", "description": "Immutable controlled Git push plan"}

    @staticmethod
    def push_evidence_ref(evidence_id: str) -> dict[str, str]:
        return {"ref_type": "artifact", "ref": f"runtime-git-push:{evidence_id}", "description": "Independently verified remote Git push evidence"}

    @staticmethod
    def pull_request_plan_ref(plan_id: str) -> dict[str, str]:
        return {"ref_type": "artifact", "ref": f"runtime-pull-request-plan:{plan_id}", "description": "Immutable pull-request creation plan"}

    @staticmethod
    def pull_request_body_ref(plan_id: str) -> dict[str, str]:
        return {"ref_type": "artifact", "ref": f"runtime-pull-request-body:{plan_id}", "description": "Bounded pull-request body"}

    @staticmethod
    def pull_request_evidence_ref(evidence_id: str) -> dict[str, str]:
        return {"ref_type": "artifact", "ref": f"runtime-pull-request:{evidence_id}", "description": "Verified pull-request creation evidence"}

    def _create(
        self,
        root: Path,
        identifier: str,
        suffix: str,
        value: dict[str, object],
        *,
        idempotent: bool = False,
    ) -> None:
        path = self._path(root, identifier, suffix)
        if path.exists():
            if idempotent and self._load_json(path, "Remote Git artifact") == value:
                return
            raise GitStoreError(f"Remote Git artifact already exists: {identifier}")
        self._write_json(path, value)

    def _load_model(self, root, identifier, suffix, loader, label):
        value = self._load_json(self._path(root, identifier, suffix), label)
        try:
            return loader(value)
        except GitContractError as error:
            raise GitStoreError(f"{label} is invalid: {identifier}: {error}") from error

    @staticmethod
    def _check_immutable(existing, updated, mutable: set[str], label: str) -> None:
        for name in existing.__dataclass_fields__:
            if name not in mutable and getattr(existing, name) != getattr(updated, name):
                raise GitStoreError(f"{label} update changed immutable authority")
