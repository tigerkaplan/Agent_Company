"""Create, approve, stage, commit, and verify bounded local Git changes."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Sequence

from runtime.actions.models import ExecutionScope, ScopeContractError
from runtime.actions.runtime import ControlledWriteRuntime
from runtime.actions.store import FileMutationArtifactStore, MutationArtifactError
from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import ApprovalStoreError
from runtime.core.jobs import JobRuntime, RuntimeError as JobRuntimeError, utc_now
from runtime.git.models import (
    GitChangeSet,
    GitCommitEvidence,
    GitContractError,
    commit_evidence_fingerprint,
)
from runtime.git.store import FileGitArtifactStore, GitStoreError
from runtime.review.store import FileReviewStore, ReviewStoreError
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore


class GitRuntimeError(ValueError):
    """A precise fail-closed error from the controlled Git boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class GitRuntime:
    """Structured Git operations over one verified change set at a time."""

    _MAX_DIFF_BYTES = 1024 * 1024
    _ALLOWED_GIT_PROGRAMS = {"git", "git.exe"}
    _FORBIDDEN_ARGUMENTS = {
        "push",
        "merge",
        "rebase",
        "--amend",
        "--force",
        "--no-verify",
        "reset",
    }

    def __init__(
        self,
        runtime_repository_root: Path,
        job_runtime: JobRuntime,
        execution_store: FileExecutionStore,
        review_store: FileReviewStore,
        mutation_store: FileMutationArtifactStore,
        approval_runtime: ApprovalRuntime,
        store: FileGitArtifactStore,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        clock: Callable[[], str] = utc_now,
        allow_runtime_repository: bool = False,
    ) -> None:
        self.runtime_repository_root = Path(runtime_repository_root).resolve()
        self.jobs = job_runtime
        self.executions = execution_store
        self.reviews = review_store
        self.mutations = mutation_store
        self.approvals = approval_runtime
        self.store = store
        self.runner = runner
        self.clock = clock
        self.allow_runtime_repository = allow_runtime_repository
        executable = which("git")
        if executable is None or Path(executable).name.casefold() not in self._ALLOWED_GIT_PROGRAMS:
            raise GitRuntimeError("git_unavailable", "Allowlisted Git executable was not found")
        self.executable = str(Path(executable).resolve())

    def prepare(
        self,
        *,
        job_id: str,
        execution_id: str,
        repository_root: Path,
        commit_message: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Inspect actual state and persist an exact commit proposal."""

        message = self._validate_commit_message(commit_message)
        repository = self._validate_repository(repository_root)
        job, mutation, review_id = self._validate_completed_execution(
            job_id, execution_id, repository
        )
        snapshot = self._snapshot(repository)
        if snapshot["staged_files"]:
            self._fail(
                "git_index_mismatch",
                "Repository index must be empty before preparing a controlled change set",
            )
        created = self._path_tuple(mutation.get("created_files"), "created")
        modified = self._path_tuple(mutation.get("modified_files"), "modified")
        deleted = self._path_tuple(mutation.get("deleted_files"), "deleted")
        changed = tuple(sorted((*created, *modified, *deleted), key=str.casefold))
        if not changed or changed != self._path_tuple(
            mutation.get("changed_files"), "changed"
        ):
            self._fail("mutation_evidence_mismatch", "Mutation file sets are inconsistent")
        try:
            scope = ExecutionScope.from_dict(
                (self.executions.load(execution_id).request or {}).get(
                    "execution_scope", {}
                )
            )
        except (ExecutionStoreError, ScopeContractError) as error:
            self._fail("mutation_evidence_mismatch", str(error))
        if scope.fingerprint != mutation.get("scope_fingerprint"):
            self._fail("mutation_evidence_mismatch", "Mutation scope fingerprint differs")
        self._validate_mutation_state(
            repository,
            mutation,
            snapshot["worktree"],
            scope,
            created,
            modified,
            deleted,
        )
        unrelated = tuple(
            sorted(set(snapshot["worktree"]) - set(changed), key=str.casefold)
        )
        diff = self._canonical_diff(repository, snapshot["head"], changed, index=False)
        if not diff:
            self._fail("mutation_evidence_mismatch", "Verified mutation produced no Git diff")
        if len(diff.encode("utf-8")) > self._MAX_DIFF_BYTES:
            self._fail("git_diff_too_large", "Git change-set diff exceeds the bounded limit")
        diff_fingerprint = self._sha(diff.encode("utf-8"))
        identity = {
            "job_id": job_id,
            "execution_id": execution_id,
            "repository_root": str(repository),
            "base_head": snapshot["head"],
            "changed_files": list(changed),
            "diff_fingerprint": diff_fingerprint,
            "commit_message": message,
        }
        change_set_id = "change-set-" + self._sha(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )[:32]
        diff_ref = self.store.diff_ref(change_set_id)
        change_set = GitChangeSet(
            change_set_id=change_set_id,
            job_id=job_id,
            execution_id=execution_id,
            mutation_ref=self.mutations.artifact_ref(execution_id),
            repository_root=str(repository),
            base_head=snapshot["head"],
            changed_files=changed,
            created_files=created,
            modified_files=modified,
            deleted_files=deleted,
            diff_ref=diff_ref,
            diff_fingerprint=diff_fingerprint,
            scope_fingerprint=str(mutation["scope_fingerprint"]),
            worktree_fingerprint=self._state_fingerprint(
                snapshot["worktree"], changed
            ),
            unrelated_files=unrelated,
            unrelated_fingerprint=self._state_fingerprint(
                snapshot["worktree"], unrelated
            ),
            commit_message=message,
            created_at=self.clock(),
            status="PREVIEW" if dry_run else "PENDING_APPROVAL",
            dry_run=dry_run,
        )
        try:
            self.store.create_change_set(change_set, diff)
        except GitStoreError as error:
            if "already exists" not in str(error):
                self._fail("git_persistence_failed", str(error))
            existing = self.store.load_change_set(change_set_id)
            if (
                existing.commit_scope != change_set.commit_scope
                or existing.worktree_fingerprint != change_set.worktree_fingerprint
                or existing.unrelated_files != change_set.unrelated_files
                or existing.unrelated_fingerprint != change_set.unrelated_fingerprint
                or existing.scope_fingerprint != change_set.scope_fingerprint
                or existing.dry_run != change_set.dry_run
            ):
                self._fail("git_change_set_conflict", "Existing change set differs from proposal")
            change_set = existing
        if dry_run:
            return {"change_set": change_set.to_dict(), "approval": None}
        try:
            approval_run = self.approvals.request_commit_change_set(
                job_id,
                execution_id=execution_id,
                review_id=review_id,
                commit_scope=change_set.commit_scope,
                reason="Commit the exact independently verified Git change set",
                evidence_refs=(
                    self.store.change_set_ref(change_set_id),
                    change_set.mutation_ref,
                    change_set.diff_ref,
                ),
            )
            approval_ref = approval_run.artifact_ref
            if change_set.approval_ref is None:
                change_set = change_set.transition(
                    "PENDING_APPROVAL", approval_ref=approval_ref
                )
                self.store.save_change_set(change_set)
            elif change_set.approval_ref != approval_ref:
                self._fail("commit_approval_mismatch", "Change set has a different approval")
        except (ApprovalRuntimeError, GitStoreError) as error:
            self._fail("commit_approval_failed", str(error))
        return {
            "change_set": change_set.to_dict(),
            "approval": approval_run.request.to_dict(),
        }

    def commit(self, change_set_id: str) -> dict[str, Any]:
        """Revalidate, exactly stage, commit, and independently verify one change set."""

        try:
            change_set = self.store.load_change_set(change_set_id)
        except GitStoreError as error:
            self._fail("git_change_set_not_found", str(error))
        if change_set.dry_run or change_set.status == "PREVIEW":
            self._fail("git_dry_run_forbidden", "Dry-run change sets cannot stage or commit")
        repository = self._validate_repository(Path(change_set.repository_root))
        approval = self._approved_commit_authority(change_set)
        recovered = self._recover_committed(change_set, repository, approval)
        if recovered is not None:
            return recovered
        snapshot = self._snapshot(repository)
        self._assert_snapshot(change_set, snapshot, "before staging")
        author_name = self._local_identity(repository, "user.name")
        author_email = self._local_identity(repository, "user.email")
        stage = self._git(repository, ["add", "--", *change_set.changed_files])
        if stage.returncode != 0:
            self._fail("git_stage_failed", self._bounded_git_error(stage))
        staged = self._staged_paths(repository)
        if staged != change_set.changed_files:
            self._fail("git_index_mismatch", "Staged index does not match the approved file list")
        staged_diff = self._canonical_diff(
            repository, change_set.base_head, change_set.changed_files, index=True
        )
        if self._sha(staged_diff.encode("utf-8")) != change_set.diff_fingerprint:
            self._fail("git_diff_stale", "Staged diff differs from the approved diff")
        committed = self._git(
            repository,
            [
                "commit",
                "-m",
                change_set.commit_message,
                "--only",
                "--",
                *change_set.changed_files,
            ],
            timeout=180,
        )
        if committed.returncode != 0:
            self._fail("git_commit_failed", self._bounded_git_error(committed))
        return self._verify_and_persist_commit(
            change_set, repository, approval, author_name, author_email
        )

    def show(self, change_set_id: str) -> dict[str, Any]:
        try:
            change_set = self.store.load_change_set(change_set_id)
        except GitStoreError as error:
            self._fail("git_change_set_not_found", str(error))
        result: dict[str, Any] = {"change_set": change_set.to_dict()}
        if change_set.commit_evidence_ref is not None:
            evidence_id = change_set.commit_evidence_ref["ref"].split(":", 1)[1]
            result["commit_evidence"] = self.store.load_evidence(evidence_id).to_dict()
        return result

    def list(self) -> list[dict[str, Any]]:
        try:
            return [item.to_dict() for item in self.store.list_change_sets()]
        except GitStoreError as error:
            self._fail("git_persistence_failed", str(error))

    def _validate_completed_execution(
        self, job_id: str, execution_id: str, repository: Path
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        try:
            job = self.jobs.show(job_id)
            execution = self.executions.load(execution_id)
            mutation = self.mutations.load(execution_id)
        except (JobRuntimeError, ExecutionStoreError, MutationArtifactError) as error:
            self._fail("mutation_evidence_missing", str(error))
        request = execution.request or {}
        result = execution.result.to_dict()
        if (
            job.get("status") != "completed"
            or job.get("review_required") is not True
            or job.get("execution_mode") != "CONTROLLED_WRITE"
            or job.get("dry_run", False) is not False
            or request.get("job_id") != job_id
            or request.get("execution_id") != execution_id
            or request.get("execution_mode") != "CONTROLLED_WRITE"
            or request.get("dry_run", False) is not False
            or result.get("job_id") != job_id
            or result.get("execution_id") != execution_id
            or result.get("status") != "succeeded"
        ):
            self._fail(
                "job_not_commit_eligible",
                "Commit requires one completed reviewed non-dry-run controlled write",
            )
        if (
            mutation.get("job_id") != job_id
            or mutation.get("execution_id") != execution_id
            or mutation.get("apply_status") != "applied"
            or mutation.get("mutation_kind") != "applied"
            or mutation.get("dry_run") is not False
            or mutation.get("scope_violations") != []
            or Path(str(mutation.get("authorized_project_root", ""))).resolve()
            != repository
        ):
            self._fail(
                "mutation_evidence_mismatch",
                "Mutation evidence is not an applied in-scope change for this repository",
            )
        refs = {
            str(ref.get("ref"))
            for ref in job.get("output_refs", [])
            if isinstance(ref, dict)
        }
        if (
            f"runtime-execution:{execution_id}" not in refs
            or f"runtime-mutation:{execution_id}" not in refs
        ):
            self._fail("mutation_evidence_mismatch", "Job does not reference execution evidence")
        review_refs = sorted(ref for ref in refs if ref.startswith("runtime-review:"))
        if len(review_refs) != 1:
            self._fail("review_evidence_missing", "Exactly one final review is required")
        review_id = review_refs[0].split(":", 1)[1]
        try:
            review = self.reviews.load(review_id).get("result", {})
        except ReviewStoreError as error:
            self._fail("review_evidence_missing", str(error))
        checks = review.get("deterministic_checks")
        if (
            review.get("job_id") != job_id
            or review.get("execution_id") != execution_id
            or review.get("decision") not in {"PASS", "NEEDS_HUMAN"}
            or not isinstance(checks, list)
            or not checks
            or any(
                not isinstance(check, dict) or check.get("status") != "PASS"
                for check in checks
            )
        ):
            self._fail("review_evidence_invalid", "Final review did not deterministically pass")
        if review.get("decision") == "NEEDS_HUMAN" and not (
            job.get("approval_status") == "approved"
            and job.get("approval", {}).get("requested_action")
            == "COMPLETE_REVIEWED_JOB"
        ):
            self._fail("human_completion_missing", "Human review completion is not approved")
        return job, mutation, review_id

    def _validate_repository(self, requested_root: Path) -> Path:
        root = Path(requested_root).resolve()
        if not root.is_dir():
            self._fail("git_repository_invalid", "Repository root is not a directory")
        inside = self._git(root, ["rev-parse", "--is-inside-work-tree"])
        top = self._git(root, ["rev-parse", "--show-toplevel"])
        if inside.returncode != 0 or inside.stdout.strip() != "true" or top.returncode != 0:
            self._fail("git_repository_invalid", "Target is not a Git working tree")
        canonical = Path(top.stdout.strip()).resolve()
        if canonical != root:
            self._fail("git_repository_root_mismatch", "Authorized root is not the Git top level")
        if canonical == self.runtime_repository_root and not self.allow_runtime_repository:
            self._fail("git_repository_protected", "Agent Company repository is not an authorized target")
        return canonical

    def _snapshot(self, repository: Path) -> dict[str, Any]:
        head_result = self._git(repository, ["rev-parse", "--verify", "HEAD"])
        if head_result.returncode != 0:
            self._fail("git_head_missing", "Repository requires an existing baseline commit")
        status_result = self._git(
            repository, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        )
        if status_result.returncode != 0:
            self._fail("git_inspection_failed", self._bounded_git_error(status_result))
        worktree: dict[str, dict[str, str | None]] = {}
        staged: list[str] = []
        entries = status_result.stdout.split("\0")
        for entry in entries:
            if not entry:
                continue
            if len(entry) < 4 or entry[2] != " ":
                self._fail("git_status_invalid", "Git returned malformed porcelain status")
            code = entry[:2]
            path = entry[3:].replace("\\", "/")
            if "R" in code or "C" in code or "U" in code:
                self._fail("git_status_unsupported", "Renames, copies, and conflicts are not commit eligible")
            if code[0] not in {" ", "?"}:
                staged.append(path)
            if code == "??":
                kind = "created"
            elif code[0] == " " and code[1] == "M":
                kind = "modified"
            elif code[0] == " " and code[1] == "D":
                kind = "deleted"
            elif code[0] != " ":
                continue
            else:
                self._fail("git_status_unsupported", f"Unsupported Git status for {path}: {code}")
            worktree[path] = {
                "kind": kind,
                "fingerprint": self._file_fingerprint(repository / path),
            }
        return {
            "head": head_result.stdout.strip(),
            "worktree": worktree,
            "staged_files": tuple(sorted(set(staged), key=str.casefold)),
        }

    def _validate_mutation_state(
        self,
        repository: Path,
        mutation: dict[str, Any],
        worktree: dict[str, dict[str, str | None]],
        scope: ExecutionScope,
        created: tuple[str, ...],
        modified: tuple[str, ...],
        deleted: tuple[str, ...],
    ) -> None:
        expected = {
            **{path: "created" for path in created},
            **{path: "modified" for path in modified},
            **{path: "deleted" for path in deleted},
        }
        post = mutation.get("target_post_fingerprints")
        if not isinstance(post, dict):
            self._fail("mutation_evidence_mismatch", "Target fingerprints are missing")
        for path, kind in expected.items():
            allowed = any(
                path == prefix or path.startswith(prefix.rstrip("/") + "/")
                for prefix in scope.allowed_paths
            )
            forbidden = any(
                path == prefix or path.startswith(prefix.rstrip("/") + "/")
                for prefix in scope.forbidden_paths
            )
            protection = ControlledWriteRuntime(
                self.runtime_repository_root, self.mutations
            )._protection(path, repository)
            if not allowed or forbidden or protection is not None:
                self._fail(
                    "git_protected_path_violation",
                    f"Mutation path is not commit eligible: {path}",
                )
            observed = worktree.get(path)
            actual = self._file_fingerprint(repository / path)
            if observed is None or observed.get("kind") != kind or post.get(path) != actual:
                self._fail(
                    "mutation_evidence_mismatch",
                    f"Git state does not match mutation evidence for {path}",
                )

    def _assert_snapshot(
        self, change_set: GitChangeSet, snapshot: dict[str, Any], stage: str
    ) -> None:
        if snapshot["head"] != change_set.base_head:
            self._fail("git_head_stale", f"Repository HEAD changed {stage}")
        if snapshot["staged_files"]:
            self._fail("git_index_mismatch", f"Repository index changed {stage}")
        if self._state_fingerprint(snapshot["worktree"], change_set.changed_files) != change_set.worktree_fingerprint:
            self._fail("git_diff_stale", f"Approved files changed {stage}")
        unrelated = tuple(
            sorted(set(snapshot["worktree"]) - set(change_set.changed_files), key=str.casefold)
        )
        if unrelated != change_set.unrelated_files or self._state_fingerprint(
            snapshot["worktree"], unrelated
        ) != change_set.unrelated_fingerprint:
            self._fail("git_unrelated_changes_stale", f"Unrelated working-tree state changed {stage}")

    def _approved_commit_authority(self, change_set: GitChangeSet) -> dict[str, Any]:
        if change_set.approval_ref is None:
            self._fail("commit_approval_missing", "Change set has no commit approval")
        approval_id = change_set.approval_ref["ref"].split(":", 1)[-1]
        try:
            approval = self.approvals.store.load(approval_id)
        except ApprovalStoreError as error:
            self._fail("commit_approval_missing", str(error))
        if (
            approval.status != "APPROVED"
            or approval.requested_action != "COMMIT_CHANGE_SET"
            or approval.job_id != change_set.job_id
            or approval.execution_id != change_set.execution_id
            or approval.commit_scope != change_set.commit_scope
            or approval.authorization_fingerprint != change_set.authorization_fingerprint
        ):
            self._fail("commit_approval_mismatch", "Approval does not authorize this exact change set")
        if change_set.status == "PENDING_APPROVAL":
            try:
                change_set = change_set.transition("APPROVED")
                self.store.save_change_set(change_set)
            except GitStoreError as error:
                self._fail("git_persistence_failed", str(error))
        return approval.to_dict()

    def _recover_committed(
        self,
        change_set: GitChangeSet,
        repository: Path,
        approval: dict[str, Any],
    ) -> dict[str, Any] | None:
        if change_set.commit_evidence_ref is not None:
            evidence_id = change_set.commit_evidence_ref["ref"].split(":", 1)[1]
            evidence = self.store.load_evidence(evidence_id)
            if self._git(repository, ["rev-parse", "HEAD"]).stdout.strip() != evidence.commit_hash:
                self._fail("git_commit_evidence_mismatch", "Persisted commit is no longer HEAD")
            return {"change_set": change_set.to_dict(), "commit_evidence": evidence.to_dict()}
        head = self._git(repository, ["rev-parse", "HEAD"])
        if head.returncode == 0 and head.stdout.strip() != change_set.base_head:
            try:
                return self._verify_and_persist_commit(
                    change_set,
                    repository,
                    approval,
                    self._local_identity(repository, "user.name"),
                    self._local_identity(repository, "user.email"),
                )
            except GitRuntimeError as error:
                if error.code != "git_commit_evidence_mismatch":
                    raise
        return None

    def _verify_and_persist_commit(
        self,
        change_set: GitChangeSet,
        repository: Path,
        approval: dict[str, Any],
        configured_name: str,
        configured_email: str,
    ) -> dict[str, Any]:
        metadata = self._git(
            repository,
            ["show", "-s", "--format=%H%x00%P%x00%an%x00%ae%x00%aI%x00%B", "HEAD"],
        )
        if metadata.returncode != 0:
            self._fail("git_commit_evidence_mismatch", self._bounded_git_error(metadata))
        parts = metadata.stdout.split("\0", 5)
        if len(parts) != 6:
            self._fail("git_commit_evidence_mismatch", "Commit metadata is malformed")
        commit_hash, parents, author_name, author_email, committed_at, message = parts
        parent_values = parents.split()
        committed_files = self._committed_paths(repository, commit_hash)
        if (
            parent_values != [change_set.base_head]
            or committed_files != change_set.changed_files
            or message.strip() != change_set.commit_message
            or author_name != configured_name
            or author_email != configured_email
        ):
            self._fail("git_commit_evidence_mismatch", "Commit does not match approved authority")
        committed_diff = self._canonical_diff(
            repository, change_set.base_head, change_set.changed_files, commit=commit_hash
        )
        if self._sha(committed_diff.encode("utf-8")) != change_set.diff_fingerprint:
            self._fail("git_commit_evidence_mismatch", "Committed diff fingerprint differs")
        post = self._snapshot(repository)
        if post["head"] != commit_hash or post["staged_files"]:
            self._fail("git_commit_evidence_mismatch", "Post-commit HEAD or index is invalid")
        if any(path in post["worktree"] for path in change_set.changed_files):
            self._fail("git_commit_evidence_mismatch", "Committed files remain dirty")
        if tuple(sorted(post["worktree"], key=str.casefold)) != change_set.unrelated_files:
            self._fail("git_unrelated_changes_stale", "Commit altered unrelated working-tree paths")
        if self._state_fingerprint(post["worktree"], change_set.unrelated_files) != change_set.unrelated_fingerprint:
            self._fail("git_unrelated_changes_stale", "Commit altered unrelated working-tree content")
        evidence_id = f"commit-{commit_hash[:32]}"
        authority_ref = self.approvals.artifact_ref(str(approval["approval_id"]))
        fingerprint_input = {
            "evidence_id": evidence_id,
            "change_set_id": change_set.change_set_id,
            "job_id": change_set.job_id,
            "execution_id": change_set.execution_id,
            "repository_root": str(repository),
            "commit_hash": commit_hash,
            "parent_hash": change_set.base_head,
            "committed_files": list(committed_files),
            "commit_message": change_set.commit_message,
            "author_name": author_name,
            "author_email": author_email,
            "committed_at": committed_at.strip(),
            "approval_ref": authority_ref,
            "diff_fingerprint": change_set.diff_fingerprint,
        }
        evidence_fields = dict(fingerprint_input)
        evidence_fields["committed_files"] = committed_files
        evidence = GitCommitEvidence(
            **evidence_fields,
            evidence_fingerprint=commit_evidence_fingerprint(fingerprint_input),
        )
        try:
            self.store.create_evidence(evidence)
            evidence_ref = self.store.evidence_ref(evidence_id)
            committed_change_set = change_set.transition(
                "COMMITTED", commit_evidence_ref=evidence_ref, error=None
            )
            self.store.save_change_set(committed_change_set)
        except GitStoreError as error:
            self._fail("git_persistence_failed", str(error))
        return {
            "change_set": committed_change_set.to_dict(),
            "commit_evidence": evidence.to_dict(),
        }

    def _canonical_diff(
        self,
        repository: Path,
        base_head: str,
        paths: Sequence[str],
        *,
        index: bool = False,
        commit: str | None = None,
    ) -> str:
        sections: list[str] = []
        for path in paths:
            before = self._git_blob(repository, f"{base_head}:{path}")
            if commit is not None:
                after = self._git_blob(repository, f"{commit}:{path}")
            elif index:
                after = self._git_blob(repository, f":{path}")
            else:
                candidate = repository / path
                after = None if not candidate.is_file() else candidate.read_bytes()
            if before == after:
                continue
            if before is None:
                before = b""
            if after is None:
                after = b""
            try:
                before_text = before.decode("utf-8").replace("\r\n", "\n")
                after_text = after.decode("utf-8").replace("\r\n", "\n")
                before_lines = before_text.splitlines(keepends=True)
                after_lines = after_text.splitlines(keepends=True)
            except UnicodeDecodeError:
                sections.append(
                    f"Binary files differ: {path} {self._sha(before)} {self._sha(after)}\n"
                )
                continue
            sections.extend(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
        return "".join(sections)

    def _git_blob(self, repository: Path, spec: str) -> bytes | None:
        command = [self.executable, "-C", str(repository), "show", spec]
        completed = subprocess.run(
            command,
            cwd=repository,
            capture_output=True,
            shell=False,
            timeout=120,
        )
        if completed.returncode != 0:
            return None
        return completed.stdout

    def _staged_paths(self, repository: Path) -> tuple[str, ...]:
        result = self._git(repository, ["diff", "--cached", "--name-only", "-z"])
        if result.returncode != 0:
            self._fail("git_index_mismatch", self._bounded_git_error(result))
        return tuple(sorted((path for path in result.stdout.split("\0") if path), key=str.casefold))

    def _committed_paths(self, repository: Path, commit_hash: str) -> tuple[str, ...]:
        result = self._git(
            repository,
            ["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit_hash],
        )
        if result.returncode != 0:
            self._fail("git_commit_evidence_mismatch", self._bounded_git_error(result))
        return tuple(sorted((path for path in result.stdout.split("\0") if path), key=str.casefold))

    def _local_identity(self, repository: Path, key: str) -> str:
        result = self._git(repository, ["config", "--local", "--get", key])
        value = result.stdout.strip()
        if result.returncode != 0 or not value:
            self._fail("git_identity_missing", f"Repository-local {key} is required")
        return value

    def _git(
        self, repository: Path, arguments: list[str], *, timeout: int = 120
    ) -> subprocess.CompletedProcess[str]:
        lowered = {argument.casefold() for argument in arguments}
        if lowered & self._FORBIDDEN_ARGUMENTS:
            self._fail("git_command_forbidden", "Git argument is outside Phase 6I authority")
        command = [self.executable, "-C", str(repository), *arguments]
        try:
            return self.runner(
                command,
                cwd=repository,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                env=os.environ.copy(),
            )
        except (OSError, subprocess.SubprocessError) as error:
            self._fail("git_process_failed", str(error))

    @staticmethod
    def _validate_commit_message(value: str) -> str:
        if not isinstance(value, str):
            raise GitRuntimeError("git_commit_message_invalid", "Commit message must be text")
        message = value.strip()
        if (
            not message
            or len(message) > 200
            or any(character in message for character in "\r\n\0")
            or any(token in message.casefold() for token in ("password=", "api_key=", "secret="))
        ):
            raise GitRuntimeError(
                "git_commit_message_invalid",
                "Commit message must be one bounded non-secret line",
            )
        return message

    @staticmethod
    def _path_tuple(value: Any, label: str) -> tuple[str, ...]:
        if not isinstance(value, list) or not all(isinstance(path, str) for path in value):
            raise GitRuntimeError("mutation_evidence_mismatch", f"Mutation {label} paths are invalid")
        paths = tuple(sorted(set(value), key=str.casefold))
        if len(paths) != len(value) or len(paths) > 100:
            raise GitRuntimeError("mutation_evidence_mismatch", f"Mutation {label} paths are not bounded")
        return paths

    @staticmethod
    def _file_fingerprint(path: Path) -> str | None:
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise GitRuntimeError("git_path_unsupported", f"Unsupported file type: {path}")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _state_fingerprint(
        state: dict[str, dict[str, str | None]], paths: Sequence[str]
    ) -> str:
        boundary = [
            [path, state.get(path, {}).get("kind"), state.get(path, {}).get("fingerprint")]
            for path in paths
        ]
        return hashlib.sha256(
            json.dumps(boundary, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _sha(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _bounded_git_error(result: subprocess.CompletedProcess[str]) -> str:
        value = (result.stderr or result.stdout or "Git command failed").strip()
        return value[:2000]

    @staticmethod
    def _fail(code: str, message: str) -> None:
        raise GitRuntimeError(code, message)
