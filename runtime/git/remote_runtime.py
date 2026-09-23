"""Controlled remote push and pull-request execution gates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import ApprovalStoreError
from runtime.core.jobs import utc_now
from runtime.git.forge import ForgeError, PullRequestAdapter, PullRequestState
from runtime.git.models import GitContractError
from runtime.git.remote_models import (
    PullRequestEvidence,
    PullRequestPlan,
    PushEvidence,
    PushPlan,
    remote_evidence_fingerprint,
    validate_branch,
)
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.git.runtime import GitRuntime, GitRuntimeError
from runtime.git.store import GitStoreError
from runtime.providers.adapters import sanitize_provider_text


class RemoteGitRuntimeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class RemoteGitRuntime:
    """Publish one verified commit and optionally create one approved PR."""

    _FORBIDDEN = {
        "--force",
        "--force-with-lease",
        "--mirror",
        "--delete",
        "--prune",
        "--tags",
        "merge",
        "rebase",
        "tag",
    }

    def __init__(
        self,
        git_runtime: GitRuntime,
        approvals: ApprovalRuntime,
        store: FileRemoteGitArtifactStore,
        *,
        pull_request_adapter: PullRequestAdapter | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.git_runtime = git_runtime
        self.approvals = approvals
        self.store = store
        self.pull_request_adapter = pull_request_adapter
        self.runner = runner
        self.clock = clock
        executable = which("git")
        if executable is None or Path(executable).name.casefold() not in {"git", "git.exe"}:
            raise RemoteGitRuntimeError("git_unavailable", "Allowlisted Git executable was not found")
        self.executable = str(Path(executable).resolve())

    def prepare_push(
        self,
        *,
        change_set_id: str,
        remote_name: str,
        remote_branch: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        try:
            change_set = self.store.load_change_set(change_set_id)
            if change_set.status != "COMMITTED" or change_set.commit_evidence_ref is None:
                self._fail("commit_evidence_missing", "Push requires a committed Phase 6I change set")
            commit_evidence_id = change_set.commit_evidence_ref["ref"].split(":", 1)[1]
            commit = self.store.load_evidence(commit_evidence_id)
        except GitStoreError as error:
            self._fail("commit_evidence_missing", str(error))
        repository = self.git_runtime._validate_repository(Path(change_set.repository_root))
        if self._git(repository, ["rev-parse", "HEAD"]).stdout.strip() != commit.commit_hash:
            self._fail("local_head_stale", "Verified commit is no longer local HEAD")
        local_branch_result = self._git(repository, ["symbolic-ref", "--short", "HEAD"])
        if local_branch_result.returncode != 0:
            self._fail("local_branch_invalid", "Detached HEAD cannot be pushed by Phase 6J")
        try:
            local_branch = validate_branch(local_branch_result.stdout.strip(), "Local branch")
            remote_branch = validate_branch(remote_branch, "Remote branch")
        except GitContractError as error:
            self._fail("remote_branch_invalid", str(error))
        identity = self._remote_identity(repository, remote_name)
        expected_remote_head = self._remote_head(repository, remote_name, remote_branch)
        if expected_remote_head not in {None, commit.parent_hash, commit.commit_hash}:
            self._fail(
                "remote_branch_diverged",
                "Remote branch is not absent, the verified parent, or the verified commit",
            )
        boundary = {
            "change_set_id": change_set_id,
            "commit_hash": commit.commit_hash,
            "remote_name": remote_name,
            "remote_url_fingerprint": identity["fingerprint"],
            "remote_branch": remote_branch,
            "expected_remote_head": expected_remote_head,
        }
        plan_id = "push-plan-" + self._digest(boundary)[:32]
        plan = PushPlan(
            push_plan_id=plan_id,
            change_set_id=change_set_id,
            commit_evidence_ref=change_set.commit_evidence_ref,
            job_id=change_set.job_id,
            execution_id=change_set.execution_id,
            repository_root=str(repository),
            commit_hash=commit.commit_hash,
            parent_hash=commit.parent_hash,
            local_branch=local_branch,
            remote_name=remote_name,
            remote_kind=identity["kind"],
            remote_host=identity["host"],
            repository_slug=identity["slug"],
            remote_url_display=identity["display"],
            remote_url_fingerprint=identity["fingerprint"],
            remote_branch=remote_branch,
            expected_remote_head=expected_remote_head,
            created_at=self.clock(),
            status="PREVIEW" if dry_run else "PENDING_APPROVAL",
            dry_run=dry_run,
        )
        try:
            self.store.create_push_plan(plan)
        except GitStoreError as error:
            if "already exists" not in str(error):
                self._fail("remote_persistence_failed", str(error))
            existing = self.store.load_push_plan(plan_id)
            if existing.approval_scope != plan.approval_scope or existing.dry_run != plan.dry_run:
                self._fail("push_plan_conflict", "Existing push plan differs from current authority")
            plan = existing
        if dry_run:
            return {"push_plan": plan.to_dict(), "approval": None}
        try:
            run = self.approvals.request_remote_action(
                plan.job_id,
                execution_id=plan.execution_id,
                requested_action="PUSH_GIT_COMMIT",
                remote_scope=plan.approval_scope,
                reason="Push one exact verified commit to one exact remote branch",
                evidence_refs=(
                    self.store.push_plan_ref(plan_id),
                    plan.commit_evidence_ref,
                ),
            )
            if plan.approval_ref is None:
                plan = plan.transition("PENDING_APPROVAL", approval_ref=run.artifact_ref)
                self.store.save_push_plan(plan)
            elif plan.approval_ref != run.artifact_ref:
                self._fail("push_approval_mismatch", "Push plan has a different approval")
        except (ApprovalRuntimeError, GitStoreError) as error:
            self._fail("push_approval_failed", str(error))
        return {"push_plan": plan.to_dict(), "approval": run.request.to_dict()}

    def push(self, push_plan_id: str) -> dict[str, Any]:
        try:
            plan = self.store.load_push_plan(push_plan_id)
        except GitStoreError as error:
            self._fail("push_plan_missing", str(error))
        if plan.dry_run:
            self._fail("remote_dry_run_forbidden", "Dry-run push plans cannot mutate a remote")
        approval = self._approved(plan, "PUSH_GIT_COMMIT")
        if plan.push_evidence_ref is not None:
            evidence_id = plan.push_evidence_ref["ref"].split(":", 1)[1]
            evidence = self.store.load_push_evidence(evidence_id)
            current = self._remote_head(Path(plan.repository_root), plan.remote_name, plan.remote_branch)
            if current != evidence.remote_head_after:
                self._fail("remote_evidence_stale", "Persisted pushed commit is no longer remote branch HEAD")
            return {"push_plan": plan.to_dict(), "push_evidence": evidence.to_dict()}
        repository = self.git_runtime._validate_repository(Path(plan.repository_root))
        change_set = self.store.load_change_set(plan.change_set_id)
        commit = self.store.load_evidence(plan.commit_evidence_ref["ref"].split(":", 1)[1])
        if (
            change_set.status != "COMMITTED"
            or commit.commit_hash != plan.commit_hash
            or self._git(repository, ["rev-parse", "HEAD"]).stdout.strip() != plan.commit_hash
        ):
            self._fail("push_plan_stale", "Local commit evidence changed after push approval")
        identity = self._remote_identity(repository, plan.remote_name)
        if identity["fingerprint"] != plan.remote_url_fingerprint:
            self._fail("remote_definition_stale", "Remote URL changed after approval")
        remote_before = self._remote_head(repository, plan.remote_name, plan.remote_branch)
        if remote_before not in {plan.expected_remote_head, plan.commit_hash}:
            self._fail("remote_head_stale", "Remote branch HEAD changed after approval")
        already_present = remote_before == plan.commit_hash
        if not already_present:
            result = self._git(
                repository,
                [
                    "push",
                    "--porcelain",
                    "--",
                    plan.remote_name,
                    f"{plan.commit_hash}:refs/heads/{plan.remote_branch}",
                ],
                timeout=180,
            )
            if result.returncode != 0:
                self._fail("git_push_failed", self._bounded_error(result))
        remote_after = self._remote_head(repository, plan.remote_name, plan.remote_branch)
        if remote_after != plan.commit_hash:
            self._fail("remote_evidence_mismatch", "Remote branch does not contain the approved commit")
        evidence_id = "push-" + self._digest(
            {"push_plan_id": plan.push_plan_id, "commit_hash": plan.commit_hash}
        )[:32]
        approval_ref = self.approvals.artifact_ref(approval["approval_id"])
        try:
            recovered = self.store.load_push_evidence(evidence_id)
        except GitStoreError as error:
            if "not found" not in str(error):
                self._fail("remote_persistence_failed", str(error))
            recovered = None
        if recovered is not None:
            if (
                recovered.push_plan_id != plan.push_plan_id
                or recovered.commit_hash != plan.commit_hash
                or recovered.remote_url_fingerprint != plan.remote_url_fingerprint
                or recovered.remote_branch != plan.remote_branch
                or recovered.remote_head_after != plan.commit_hash
                or recovered.approval_ref != approval_ref
            ):
                self._fail("remote_evidence_mismatch", "Persisted push evidence does not match the approved plan")
            try:
                plan = plan.transition(
                    "PUSHED", push_evidence_ref=self.store.push_evidence_ref(evidence_id)
                )
                self.store.save_push_plan(plan)
            except GitStoreError as error:
                self._fail("remote_persistence_failed", str(error))
            return {"push_plan": plan.to_dict(), "push_evidence": recovered.to_dict()}
        fields = {
            "push_evidence_id": evidence_id,
            "push_plan_id": plan.push_plan_id,
            "change_set_id": plan.change_set_id,
            "commit_evidence_ref": plan.commit_evidence_ref,
            "repository_root": plan.repository_root,
            "commit_hash": plan.commit_hash,
            "remote_name": plan.remote_name,
            "remote_url_display": plan.remote_url_display,
            "remote_url_fingerprint": plan.remote_url_fingerprint,
            "remote_branch": plan.remote_branch,
            "remote_head_before": remote_before,
            "remote_head_after": remote_after,
            "approval_ref": approval_ref,
            "pushed_at": self.clock(),
            "already_present": already_present,
        }
        evidence = PushEvidence(
            **fields, evidence_fingerprint=remote_evidence_fingerprint(fields)
        )
        try:
            self.store.create_push_evidence(evidence)
            plan = plan.transition(
                "PUSHED", push_evidence_ref=self.store.push_evidence_ref(evidence_id)
            )
            self.store.save_push_plan(plan)
        except GitStoreError as error:
            self._fail("remote_persistence_failed", str(error))
        return {"push_plan": plan.to_dict(), "push_evidence": evidence.to_dict()}

    def prepare_pull_request(
        self,
        *,
        push_evidence_id: str,
        base_branch: str,
        title: str,
        body: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if self.pull_request_adapter is None:
            self._fail("forge_unavailable", "Pull-request adapter is not configured")
        try:
            push_evidence = self.store.load_push_evidence(push_evidence_id)
            push_plan = self.store.load_push_plan(push_evidence.push_plan_id)
            base_branch = validate_branch(base_branch, "PR base branch")
        except (GitStoreError, GitContractError) as error:
            self._fail("pull_request_plan_invalid", str(error))
        if push_plan.remote_host != "github.com" or not push_plan.repository_slug:
            self._fail("forge_unsupported", "Pull-request creation requires an approved github.com remote")
        title = self._bounded_content(title, 256, "Pull-request title", single_line=True)
        body = self._bounded_content(body, 64 * 1024, "Pull-request body")
        if base_branch == push_plan.remote_branch:
            self._fail("pull_request_plan_invalid", "Head and base branches must differ")
        current_remote = self._remote_head(
            Path(push_plan.repository_root), push_plan.remote_name, push_plan.remote_branch
        )
        if current_remote != push_evidence.commit_hash:
            self._fail("remote_evidence_stale", "Pushed branch changed before PR planning")
        try:
            existing = self.pull_request_adapter.inspect(
                push_plan.repository_slug, push_plan.remote_branch, base_branch
            )
        except ForgeError as error:
            self._fail(error.code, error.message)
        if existing is not None:
            self._fail("pull_request_already_exists", "An open pull request already exists for these branches")
        body_fingerprint = hashlib.sha256(body.encode("utf-8")).hexdigest()
        boundary = {
            "push_evidence_id": push_evidence_id,
            "repository_slug": push_plan.repository_slug,
            "head_branch": push_plan.remote_branch,
            "base_branch": base_branch,
            "head_commit": push_evidence.commit_hash,
            "title": title,
            "body_fingerprint": body_fingerprint,
        }
        plan_id = "pr-plan-" + self._digest(boundary)[:32]
        plan = PullRequestPlan(
            pull_request_plan_id=plan_id,
            push_evidence_ref=self.store.push_evidence_ref(push_evidence_id),
            job_id=push_plan.job_id,
            execution_id=push_plan.execution_id,
            forge="github",
            repository_slug=push_plan.repository_slug,
            head_branch=push_plan.remote_branch,
            base_branch=base_branch,
            head_commit=push_evidence.commit_hash,
            title=title,
            body_ref=self.store.pull_request_body_ref(plan_id),
            body_fingerprint=body_fingerprint,
            created_at=self.clock(),
            status="PREVIEW" if dry_run else "PENDING_APPROVAL",
            dry_run=dry_run,
        )
        try:
            self.store.create_pull_request_plan(plan, body)
        except GitStoreError as error:
            if "already exists" not in str(error):
                self._fail("remote_persistence_failed", str(error))
            existing_plan = self.store.load_pull_request_plan(plan_id)
            if existing_plan.approval_scope != plan.approval_scope or existing_plan.dry_run != plan.dry_run:
                self._fail("pull_request_plan_conflict", "Existing PR plan differs from current authority")
            plan = existing_plan
        if dry_run:
            return {"pull_request_plan": plan.to_dict(), "approval": None}
        try:
            run = self.approvals.request_remote_action(
                plan.job_id,
                execution_id=plan.execution_id,
                requested_action="CREATE_PULL_REQUEST",
                remote_scope=plan.approval_scope,
                reason="Create one exact pull request without merge authority",
                evidence_refs=(
                    self.store.pull_request_plan_ref(plan_id),
                    plan.push_evidence_ref,
                    plan.body_ref,
                ),
            )
            if plan.approval_ref is None:
                plan = plan.transition("PENDING_APPROVAL", approval_ref=run.artifact_ref)
                self.store.save_pull_request_plan(plan)
            elif plan.approval_ref != run.artifact_ref:
                self._fail("pull_request_approval_mismatch", "PR plan has a different approval")
        except (ApprovalRuntimeError, GitStoreError) as error:
            self._fail("pull_request_approval_failed", str(error))
        return {"pull_request_plan": plan.to_dict(), "approval": run.request.to_dict()}

    def create_pull_request(self, plan_id: str) -> dict[str, Any]:
        if self.pull_request_adapter is None:
            self._fail("forge_unavailable", "Pull-request adapter is not configured")
        try:
            plan = self.store.load_pull_request_plan(plan_id)
        except GitStoreError as error:
            self._fail("pull_request_plan_missing", str(error))
        if plan.dry_run:
            self._fail("remote_dry_run_forbidden", "Dry-run PR plans cannot create a pull request")
        approval = self._approved(plan, "CREATE_PULL_REQUEST")
        if plan.pull_request_evidence_ref is not None:
            evidence_id = plan.pull_request_evidence_ref["ref"].split(":", 1)[1]
            evidence = self.store.load_pull_request_evidence(evidence_id)
            return {"pull_request_plan": plan.to_dict(), "pull_request_evidence": evidence.to_dict()}
        push_evidence_id = plan.push_evidence_ref["ref"].split(":", 1)[1]
        push_evidence = self.store.load_push_evidence(push_evidence_id)
        push_plan = self.store.load_push_plan(push_evidence.push_plan_id)
        current_remote = self._remote_head(
            Path(push_plan.repository_root), push_plan.remote_name, plan.head_branch
        )
        if current_remote != plan.head_commit:
            self._fail("remote_evidence_stale", "PR head branch changed after approval")
        body = self.store.load_pull_request_body(plan_id)
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != plan.body_fingerprint:
            self._fail("pull_request_body_stale", "PR body changed after approval")
        try:
            state = self.pull_request_adapter.inspect(
                plan.repository_slug, plan.head_branch, plan.base_branch
            )
            already_present = state is not None
            if state is None:
                state = self.pull_request_adapter.create(
                    plan.repository_slug,
                    plan.head_branch,
                    plan.base_branch,
                    plan.title,
                    body,
                )
            self._validate_pr_state(plan, state)
        except ForgeError as error:
            self._fail(error.code, error.message)
        evidence_id = f"pr-{state.number}-{plan.head_commit[:20]}"
        fields = {
            "pull_request_evidence_id": evidence_id,
            "pull_request_plan_id": plan_id,
            "push_evidence_ref": plan.push_evidence_ref,
            "repository_slug": plan.repository_slug,
            "head_branch": plan.head_branch,
            "base_branch": plan.base_branch,
            "head_commit": plan.head_commit,
            "pull_request_number": state.number,
            "pull_request_url": state.url,
            "title": state.title,
            "body_fingerprint": plan.body_fingerprint,
            "approval_ref": self.approvals.artifact_ref(approval["approval_id"]),
            "created_at": self.clock(),
            "already_present": already_present,
        }
        evidence = PullRequestEvidence(
            **fields, evidence_fingerprint=remote_evidence_fingerprint(fields)
        )
        try:
            self.store.create_pull_request_evidence(evidence)
            plan = plan.transition(
                "EXISTING" if already_present else "CREATED",
                pull_request_evidence_ref=self.store.pull_request_evidence_ref(evidence_id),
            )
            self.store.save_pull_request_plan(plan)
        except GitStoreError as error:
            self._fail("remote_persistence_failed", str(error))
        return {"pull_request_plan": plan.to_dict(), "pull_request_evidence": evidence.to_dict()}

    def _approved(self, plan: PushPlan | PullRequestPlan, action: str) -> dict[str, Any]:
        approval_ref = plan.approval_ref
        if approval_ref is None:
            self._fail("remote_approval_missing", "Remote action has no approval")
        approval_id = approval_ref["ref"].split(":", 1)[1]
        try:
            approval = self.approvals.store.load(approval_id)
        except ApprovalStoreError as error:
            self._fail("remote_approval_missing", str(error))
        if (
            approval.status != "APPROVED"
            or approval.requested_action != action
            or approval.job_id != plan.job_id
            or approval.execution_id != plan.execution_id
            or approval.remote_scope != plan.approval_scope
            or approval.authorization_fingerprint != plan.authorization_fingerprint
        ):
            self._fail("remote_approval_mismatch", "Approval does not authorize this exact remote action")
        if plan.status == "PENDING_APPROVAL":
            updated = plan.transition("APPROVED")
            try:
                if isinstance(updated, PushPlan):
                    self.store.save_push_plan(updated)
                else:
                    self.store.save_pull_request_plan(updated)
            except GitStoreError as error:
                self._fail("remote_persistence_failed", str(error))
        return approval.to_dict()

    def _remote_identity(self, repository: Path, remote_name: str) -> dict[str, str | None]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", remote_name):
            self._fail("remote_name_invalid", "Remote name is invalid")
        fetch = self._git(repository, ["remote", "get-url", "--all", remote_name])
        push = self._git(repository, ["remote", "get-url", "--push", "--all", remote_name])
        if fetch.returncode != 0 or push.returncode != 0:
            self._fail("remote_not_found", "Configured Git remote was not found")
        fetch_urls = [value for value in fetch.stdout.splitlines() if value]
        push_urls = [value for value in push.stdout.splitlines() if value]
        if len(fetch_urls) != 1 or len(push_urls) != 1 or fetch_urls != push_urls:
            self._fail("remote_definition_ambiguous", "Remote must have one identical fetch and push URL")
        return self._canonical_remote_url(repository, push_urls[0])

    def _canonical_remote_url(self, repository: Path, value: str) -> dict[str, str | None]:
        raw = value.strip()
        if not raw or any(character in raw for character in "\r\n\0"):
            self._fail("remote_url_invalid", "Remote URL is empty or malformed")
        path_candidate = Path(raw)
        if path_candidate.is_absolute() or not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", raw) and ":" not in raw:
            resolved = (repository / path_candidate).resolve() if not path_candidate.is_absolute() else path_candidate.resolve()
            canonical = f"local:{resolved}"
            return {"kind": "local", "host": None, "slug": None, "display": canonical, "fingerprint": self._digest(canonical)}
        if raw.startswith("file://"):
            parsed = urlparse(raw)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                self._fail("remote_url_credentials_forbidden", "Remote URL embeds credentials or parameters")
            resolved = Path(unquote(parsed.path.lstrip("/") if re.match(r"^/[A-Za-z]:", parsed.path) else parsed.path)).resolve()
            canonical = f"local:{resolved}"
            return {"kind": "local", "host": None, "slug": None, "display": canonical, "fingerprint": self._digest(canonical)}
        scp = None
        if "://" not in raw:
            scp = re.fullmatch(r"git@([A-Za-z0-9.-]+):/?([^?#]+)", raw)
        if scp:
            host = scp.group(1).casefold()
            path = scp.group(2).strip("/")
            return self._hosted_identity("ssh", host, path, f"ssh://git@{host}/{path}")
        parsed = urlparse(raw)
        if parsed.scheme not in {"https", "ssh"} or not parsed.hostname:
            self._fail("remote_url_scheme_forbidden", "Only HTTPS, SSH, or local test remotes are allowed")
        try:
            port = parsed.port
        except ValueError:
            self._fail("remote_url_invalid", "Remote URL port is malformed")
        if port is not None:
            self._fail("remote_url_scheme_forbidden", "Custom remote URL ports are not allowed")
        if parsed.password or parsed.query or parsed.fragment or (parsed.username and parsed.scheme == "https"):
            self._fail("remote_url_credentials_forbidden", "Remote URL embeds credentials or parameters")
        if parsed.scheme == "ssh" and parsed.username != "git":
            self._fail("remote_url_credentials_forbidden", "SSH remote user must be the canonical git user")
        host = parsed.hostname.casefold()
        if (
            re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) is None
            or ".." in host
        ):
            self._fail("remote_url_invalid", "Remote URL host is malformed")
        path = parsed.path.strip("/")
        display = f"{parsed.scheme}://{'git@' if parsed.scheme == 'ssh' else ''}{host}/{path}"
        return self._hosted_identity(parsed.scheme, host, path, display)

    def _hosted_identity(self, kind: str, host: str, path: str, display: str) -> dict[str, str]:
        if (
            re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) is None
            or ".." in host
        ):
            self._fail("remote_url_invalid", "Remote URL host is malformed")
        slug = path.removesuffix(".git")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
            self._fail("remote_repository_invalid", "Hosted remote must identify one owner/repository")
        return {"kind": kind, "host": host, "slug": slug, "display": display, "fingerprint": self._digest(display)}

    def _remote_head(self, repository: Path, remote_name: str, branch: str) -> str | None:
        result = self._git(
            repository,
            ["ls-remote", "--heads", "--exit-code", remote_name, f"refs/heads/{branch}"],
        )
        if result.returncode == 2 and not result.stdout.strip():
            return None
        if result.returncode != 0:
            self._fail("remote_inspection_failed", self._bounded_error(result))
        lines = [line for line in result.stdout.splitlines() if line]
        if len(lines) != 1:
            self._fail("remote_state_ambiguous", "Remote branch inspection was ambiguous")
        head, ref = lines[0].split("\t", 1)
        if ref != f"refs/heads/{branch}" or not re.fullmatch(r"[a-f0-9]{40}", head):
            self._fail("remote_evidence_invalid", "Remote branch evidence is malformed")
        return head

    @staticmethod
    def _validate_pr_state(plan: PullRequestPlan, state: PullRequestState) -> None:
        if (
            state.repository_slug != plan.repository_slug
            or state.head_branch != plan.head_branch
            or state.base_branch != plan.base_branch
            or state.head_commit != plan.head_commit
            or state.title != plan.title
        ):
            raise RemoteGitRuntimeError(
                "pull_request_evidence_mismatch",
                "Pull-request state does not match approved plan",
            )

    def _git(
        self, repository: Path, arguments: list[str], *, timeout: int = 120
    ) -> subprocess.CompletedProcess[str]:
        if not arguments or arguments[0] not in {
            "remote",
            "ls-remote",
            "symbolic-ref",
            "rev-parse",
            "push",
        }:
            self._fail("remote_git_command_forbidden", "Git command is outside Phase 6J authority")
        if {argument.casefold() for argument in arguments} & self._FORBIDDEN:
            self._fail("remote_git_command_forbidden", "Force, delete, merge, tag, and broad push options are forbidden")
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "Never"
        try:
            return self.runner(
                [self.executable, "-C", str(repository), *arguments],
                cwd=repository,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as error:
            self._fail("remote_git_process_failed", str(error))

    @staticmethod
    def _bounded_content(value: str, limit: int, label: str, *, single_line: bool = False) -> str:
        if not isinstance(value, str):
            raise RemoteGitRuntimeError("pull_request_content_invalid", f"{label} must be text")
        normalized = value.strip()
        if not normalized or len(normalized.encode("utf-8")) > limit or "\0" in normalized:
            raise RemoteGitRuntimeError("pull_request_content_invalid", f"{label} is empty or exceeds its limit")
        if single_line and any(character in normalized for character in "\r\n"):
            raise RemoteGitRuntimeError("pull_request_content_invalid", f"{label} must be one line")
        if sanitize_provider_text(normalized) != normalized:
            raise RemoteGitRuntimeError("pull_request_content_sensitive", f"{label} appears to contain credential material")
        return normalized

    @staticmethod
    def _bounded_error(result: subprocess.CompletedProcess[str]) -> str:
        return (sanitize_provider_text(result.stderr or result.stdout or "Remote Git command failed").strip())[:2000]

    @staticmethod
    def _digest(value: Any) -> str:
        data = value if isinstance(value, str) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def _fail(code: str, message: str) -> None:
        raise RemoteGitRuntimeError(code, message)
