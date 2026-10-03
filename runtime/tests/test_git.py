from __future__ import annotations

from runtime.tests.contract_fixtures import declare_fixture_contract

import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from runtime.actions.authorization import authorization_fingerprint
from runtime.actions.models import ExecutionScope
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime
from runtime.cli.__main__ import run
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.git.models import GIT_CAPABILITIES, GitChangeSet, GitContractError
from runtime.git.runtime import GitRuntime, GitRuntimeError
from runtime.git.store import FileGitArtifactStore, GitStoreError
from runtime.providers.models import ContextEntry
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.review.context import ReviewContextBuilder
from runtime.review.models import (
    DeterministicCheck,
    ReviewPackage,
    ReviewResult,
    VerificationResult,
)
from runtime.review.store import FileReviewStore
from runtime.storage.execution_store import FileExecutionStore


RUNTIME_REPOSITORY = Path(__file__).resolve().parents[2]


class GitRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("Git is required")
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repository = self.root / "target"
        self.repository.mkdir()
        self.git("init", "-q")
        self.git("config", "--local", "user.name", "Agent Company Test")
        self.git("config", "--local", "user.email", "agent-company@example.invalid")
        (self.repository / "hello.txt").write_text("BEFORE\n", encoding="utf-8")
        (self.repository / "delete-me.txt").write_text("DELETE\n", encoding="utf-8")
        (self.repository / "unrelated.txt").write_text("UNCHANGED\n", encoding="utf-8")
        self.git("add", "--", "hello.txt", "delete-me.txt", "unrelated.txt")
        self.git("commit", "-q", "-m", "baseline")
        self.base_head = self.git("rev-parse", "HEAD").stdout.strip()

        self.jobs = JobRuntime(self.root / "state" / "jobs")
        self.executions = FileExecutionStore(self.root / "state" / "executions")
        self.reviews = FileReviewStore(self.root / "state" / "executions" / "reviews")
        self.mutations = FileMutationArtifactStore(
            self.root / "state" / "executions" / "mutations"
        )
        self.approval_store = FileApprovalStore(self.root / "state" / "approvals")
        self.approvals = ApprovalRuntime(
            self.jobs,
            self.approval_store,
            execution_store=self.executions,
            review_store=self.reviews,
        )
        self.git_store = FileGitArtifactStore(
            self.root / "state" / "executions" / "git"
        )
        self.runtime = GitRuntime(
            RUNTIME_REPOSITORY,
            self.jobs,
            self.executions,
            self.reviews,
            self.mutations,
            self.approvals,
            self.git_store,
        )
        self.job_id, self.execution_id = self.completed_write(
            modified={"hello.txt": "AFTER\n"}
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repository), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check,
            shell=False,
        )

    @staticmethod
    def digest(path: Path) -> str | None:
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def completed_write(
        self,
        *,
        modified: dict[str, str] | None = None,
        created: dict[str, str] | None = None,
        deleted: tuple[str, ...] = (),
        review_decision: str = "PASS",
    ) -> tuple[str, str]:
        modified = modified or {}
        created = created or {}
        changed = tuple(sorted((*modified, *created, *deleted), key=str.casefold))
        scope_dict = {
            "project_root": str(self.repository.resolve()),
            "allowed_paths": list(changed),
            "forbidden_paths": [],
            "write_mode": "CREATE_MODIFY_DELETE" if deleted else "CREATE_OR_MODIFY",
            "max_changed_files": 100,
            "max_artifact_bytes": 1024 * 1024,
            "allow_tests": False,
            "allow_git_reads": True,
            "allow_protected_paths": False,
            "dry_run": False,
        }
        created_job = self.jobs.create(
            declare_fixture_contract({
                "task": "Apply one verified controlled write",
                "task_class": "software",
                "project_id": self.repository.name,
                "agent": "software",
                "workflow": "software",
                "capability": "software_implementation",
                "risk_level": "approval_required",
                "approval_status": "required",
                "review_required": True,
                "input_refs": [],
                "output_refs": [],
                "created_by": "git-test",
                "execution_mode": "CONTROLLED_WRITE",
                "execution_scope": scope_dict,
            })
        )
        pending = self.approvals.request_execution(
            created_job["job_id"], reason="Authorize test controlled write"
        )
        approved = self.approvals.resolve(
            pending.request.approval_id,
            decision="APPROVED",
            decided_by="test-owner",
        )["job"]
        running = self.jobs.claim()
        assert running is not None
        execution_id = f"execution-{created_job['job_id']}"

        for path, content in modified.items():
            (self.repository / path).write_text(content, encoding="utf-8")
        for path, content in created.items():
            target = self.repository / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for path in deleted:
            (self.repository / path).unlink()

        scope = ExecutionScope.from_dict(scope_dict)
        post = {path: self.digest(self.repository / path) for path in changed}
        mutation = {
            "schema_version": 1,
            "execution_id": execution_id,
            "job_id": created_job["job_id"],
            "execution_mode": "CONTROLLED_WRITE",
            "dry_run": False,
            "authorization_required": True,
            "authorized_project_root": str(self.repository.resolve()),
            "allowed_paths": list(changed),
            "provider_eligibility": {
                "requested_provider": "codex",
                "executing_provider": "codex",
                "status": "selected_by_canonical_router",
            },
            "requested_sandbox_mode": "workspace-write",
            "effective_sandbox_mode": "workspace-write",
            "scope_fingerprint": scope.fingerprint,
            "created_files": sorted(created, key=str.casefold),
            "modified_files": sorted(modified, key=str.casefold),
            "deleted_files": sorted(deleted, key=str.casefold),
            "changed_files": list(changed),
            "proposed_created_files": sorted(created, key=str.casefold),
            "proposed_modified_files": sorted(modified, key=str.casefold),
            "proposed_deleted_files": sorted(deleted, key=str.casefold),
            "proposed_changed_files": list(changed),
            "applied_changed_files": list(changed),
            "mutation_kind": "applied",
            "scope_violations": [],
            "pre_fingerprints": {path: None for path in changed},
            "post_fingerprints": post,
            "target_post_fingerprints": post,
            "apply_status": "applied",
            "target_integrity": {"before": None, "after": None, "unchanged": None},
            "validation": {"status": "not_configured", "commands": []},
        }
        mutation_ref = self.mutations.create(
            execution_id, mutation, "fixture diff\n", max_diff_bytes=1024 * 1024
        )
        request = ExecutionRequest(
                      task_contract=approved["task_contract"],
            execution_id=execution_id,
            job_id=created_job["job_id"],
            task=created_job["task"],
            task_class="software",
            project_id=self.repository.name,
            agent="software",
            skill=None,
            workflow="software",
            capability="software_implementation",
            provider="codex",
            risk_level="approval_required",
            input_refs=(),
            context_refs=(),
            review_required=True,
            attempt=1,
            approval_status="approved",
            execution_mode="CONTROLLED_WRITE",
            execution_scope=scope_dict,
            authorization_fingerprint=approved["approval"]["authorization_fingerprint"],
        )
        execution_ref = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{execution_id}",
            "description": "Immutable normalized execution record",
        }
        result = ExecutionResult(
            execution_id=execution_id,
            job_id=created_job["job_id"],
            status="succeeded",
            output_refs=(mutation_ref,),
            summary="Controlled mutation applied",
            error=None,
            provider="codex",
            started_at="2026-09-23T10:00:00Z",
            completed_at="2026-09-23T10:00:01Z",
            execution_mode="CONTROLLED_WRITE",
            dry_run=False,
        )
        from runtime.core.capability_governance import certified_dispatch, consume_effect
        from runtime.workers.worker import Worker
        request = Worker._build_request(running, execution_id, ())
        self.executions.begin_decision(request, executor="deterministic-controlled-fixture", runtime=self.jobs, job=running)
        with certified_dispatch(self.executions, request):
            consume_effect(request, "controlled_write")
        self.executions.create(request, result)
        reviewing = self.jobs.record_execution_success(
            created_job["job_id"], [execution_ref, mutation_ref]
        )
        check = DeterministicCheck(
            name="controlled_mutation_valid",
            status="PASS",
            reason="Mutation evidence matches the target",
            evidence_refs=(mutation_ref,),
        )
        verification = VerificationResult(status="PASS", checks=(check,))
        review_id = f"review-{created_job['job_id']}"
        review = ReviewResult(
            review_id=review_id,
            job_id=created_job["job_id"],
            execution_id=execution_id,
            reviewer="reviewer",
            review_provider="codex",
            same_provider_review=True,
            model_review_performed=True,
            decision=review_decision,
            reason="Verified controlled mutation",
            evidence_refs=(mutation_ref,),
            deterministic_checks=(check.to_dict(),),
            created_at="2026-09-23T10:00:02Z",
        )
        package = ReviewPackage(
            review_id=review_id,
            job=reviewing,
            execution=result.to_dict(),
            verification=verification,
            context=(ContextEntry(ref="test", description="test", content="test"),),
            evidence=(),
        )
        with certified_dispatch(self.executions, request, purpose="review"):
            self.reviews.begin_decision(review_id, reviewing, request, result, "reviewer")
            review_ref = self.reviews.create(package, review, "review output", execution_request=request.to_dict())
        if review_decision == "PASS":
            self.jobs.apply_review_decision(
                created_job["job_id"],
                decision="PASS",
                reason="Verified controlled mutation",
                review_ref=review_ref,
            )
        else:
            completion = self.approvals.request_review_completion(
                created_job["job_id"], execution_id, review, review_ref
            )
            self.jobs.apply_review_decision(
                created_job["job_id"],
                decision="NEEDS_HUMAN",
                reason="Human completion required",
                review_ref=review_ref,
                approval_ref=completion.artifact_ref,
            )
            self.approvals.resolve(
                completion.request.approval_id,
                decision="APPROVED",
                decided_by="test-owner",
            )
        return created_job["job_id"], execution_id

    def prepare(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "repository_root": self.repository,
            "commit_message": "Apply verified hello update",
        }
        values.update(overrides)
        return self.runtime.prepare(**values)

    def approve(self, prepared: dict[str, object]) -> str:
        approval = prepared["approval"]
        assert isinstance(approval, dict)
        approval_id = str(approval["approval_id"])
        self.approvals.resolve(
            approval_id, decision="APPROVED", decided_by="test-owner"
        )
        change_set = prepared["change_set"]
        assert isinstance(change_set, dict)
        return str(change_set["change_set_id"])

    def test_a_capabilities_are_explicit_and_bounded(self) -> None:
        self.assertEqual(GIT_CAPABILITIES, {"GIT_INSPECT", "GIT_STAGE", "GIT_COMMIT"})

    def test_b_prepare_binds_actual_repository_and_base_head(self) -> None:
        prepared = self.prepare()
        change_set = prepared["change_set"]
        self.assertEqual(change_set["repository_root"], str(self.repository.resolve()))
        self.assertEqual(change_set["base_head"], self.base_head)
        self.assertEqual(change_set["modified_files"], ["hello.txt"])

    def test_c_commit_approval_binds_exact_authority(self) -> None:
        prepared = self.prepare()
        approval = prepared["approval"]
        change_set = prepared["change_set"]
        self.assertEqual(approval["requested_action"], "COMMIT_CHANGE_SET")
        self.assertEqual(approval["commit_scope"]["change_set_id"], change_set["change_set_id"])
        self.assertEqual(approval["commit_scope"]["changed_files"], ["hello.txt"])

    def test_d_exact_stage_commit_and_evidence(self) -> None:
        prepared = self.prepare()
        change_set_id = self.approve(prepared)
        outcome = self.runtime.commit(change_set_id)
        evidence = outcome["commit_evidence"]
        self.assertEqual(evidence["parent_hash"], self.base_head)
        self.assertEqual(evidence["committed_files"], ["hello.txt"])
        self.assertEqual((self.repository / "hello.txt").read_text(), "AFTER\n")
        self.assertEqual(self.git("status", "--porcelain").stdout, "")

    def test_e_restart_reload_is_idempotent(self) -> None:
        change_set_id = self.approve(self.prepare())
        first = self.runtime.commit(change_set_id)
        restarted = GitRuntime(
            RUNTIME_REPOSITORY,
            JobRuntime(self.root / "state" / "jobs"),
            FileExecutionStore(self.root / "state" / "executions"),
            FileReviewStore(self.root / "state" / "executions" / "reviews"),
            FileMutationArtifactStore(self.root / "state" / "executions" / "mutations"),
            ApprovalRuntime(
                JobRuntime(self.root / "state" / "jobs"),
                FileApprovalStore(self.root / "state" / "approvals"),
            ),
            FileGitArtifactStore(self.root / "state" / "executions" / "git"),
        )
        second = restarted.commit(change_set_id)
        self.assertEqual(first["commit_evidence"], second["commit_evidence"])
        self.assertEqual(self.git("rev-list", "--count", "HEAD").stdout.strip(), "2")

    def test_f_dry_run_never_touches_index_or_history(self) -> None:
        before_status = self.git("status", "--porcelain=v1").stdout
        preview = self.prepare(dry_run=True)
        self.assertEqual(preview["change_set"]["status"], "PREVIEW")
        self.assertIsNone(preview["approval"])
        self.assertEqual(self.git("status", "--porcelain=v1").stdout, before_status)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.base_head)
        with self.assertRaisesRegex(GitRuntimeError, "git_dry_run_forbidden"):
            self.runtime.commit(preview["change_set"]["change_set_id"])

    def test_g_unapproved_change_set_cannot_stage(self) -> None:
        prepared = self.prepare()
        with self.assertRaisesRegex(GitRuntimeError, "commit_approval_mismatch"):
            self.runtime.commit(prepared["change_set"]["change_set_id"])
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")

    def test_h_rejected_change_set_cannot_stage(self) -> None:
        prepared = self.prepare()
        approval_id = prepared["approval"]["approval_id"]
        self.approvals.resolve(approval_id, decision="REJECTED", decided_by="test-owner")
        with self.assertRaisesRegex(GitRuntimeError, "commit_approval_mismatch"):
            self.runtime.commit(prepared["change_set"]["change_set_id"])
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")

    def test_i_stale_head_blocks_staging(self) -> None:
        change_set_id = self.approve(self.prepare())
        self.git("add", "--", "hello.txt")
        self.git("commit", "-q", "-m", "outside commit")
        with self.assertRaisesRegex(GitRuntimeError, "git_head_stale"):
            self.runtime.commit(change_set_id)

    def test_j_stale_diff_blocks_staging(self) -> None:
        change_set_id = self.approve(self.prepare())
        (self.repository / "hello.txt").write_text("TAMPERED\n", encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "git_diff_stale"):
            self.runtime.commit(change_set_id)
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")

    def test_k_existing_index_change_blocks_prepare(self) -> None:
        self.git("add", "--", "hello.txt")
        with self.assertRaisesRegex(GitRuntimeError, "git_index_mismatch"):
            self.prepare()

    def test_l_repository_local_identity_is_required(self) -> None:
        change_set_id = self.approve(self.prepare())
        self.git("config", "--local", "--unset", "user.email")
        with self.assertRaisesRegex(GitRuntimeError, "git_identity_missing"):
            self.runtime.commit(change_set_id)
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")

    def test_m_runtime_repository_is_protected(self) -> None:
        with self.assertRaisesRegex(GitRuntimeError, "git_repository_protected"):
            self.runtime._validate_repository(RUNTIME_REPOSITORY)

    def test_n_non_repository_is_rejected(self) -> None:
        outside = self.root / "not-git"
        outside.mkdir()
        with self.assertRaisesRegex(GitRuntimeError, "git_repository_invalid"):
            self.runtime._validate_repository(outside)

    def test_o_nested_repository_path_is_rejected(self) -> None:
        nested = self.repository / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(GitRuntimeError, "git_repository_root_mismatch"):
            self.runtime._validate_repository(nested)

    def test_p_commit_message_is_one_bounded_non_secret_line(self) -> None:
        for message in ("", "line one\nline two", "password=secret", "x" * 201):
            with self.subTest(message=message), self.assertRaisesRegex(
                GitRuntimeError, "git_commit_message_invalid"
            ):
                self.prepare(commit_message=message)

    def test_q_created_file_is_staged_and_committed_exactly(self) -> None:
        self.runtime.commit(self.approve(self.prepare()))
        job_id, execution_id = self.completed_write(created={"created.txt": "NEW\n"})
        prepared = self.runtime.prepare(
            job_id=job_id,
            execution_id=execution_id,
            repository_root=self.repository,
            commit_message="Add verified file",
        )
        outcome = self.runtime.commit(self.approve(prepared))
        self.assertEqual(outcome["commit_evidence"]["committed_files"], ["created.txt"])

    def test_r_deleted_file_is_staged_and_committed_exactly(self) -> None:
        self.runtime.commit(self.approve(self.prepare()))
        job_id, execution_id = self.completed_write(deleted=("delete-me.txt",))
        prepared = self.runtime.prepare(
            job_id=job_id,
            execution_id=execution_id,
            repository_root=self.repository,
            commit_message="Delete verified file",
        )
        outcome = self.runtime.commit(self.approve(prepared))
        self.assertEqual(outcome["commit_evidence"]["committed_files"], ["delete-me.txt"])
        self.assertFalse((self.repository / "delete-me.txt").exists())

    def test_s_create_modify_delete_change_set_is_exact(self) -> None:
        self.runtime.commit(self.approve(self.prepare()))
        job_id, execution_id = self.completed_write(
            modified={"hello.txt": "SECOND\n"},
            created={"created.txt": "NEW\n"},
            deleted=("delete-me.txt",),
        )
        prepared = self.runtime.prepare(
            job_id=job_id,
            execution_id=execution_id,
            repository_root=self.repository,
            commit_message="Apply verified mixed change",
        )
        outcome = self.runtime.commit(self.approve(prepared))
        self.assertEqual(
            outcome["commit_evidence"]["committed_files"],
            ["created.txt", "delete-me.txt", "hello.txt"],
        )

    def test_t_unrelated_dirty_change_survives_unstaged(self) -> None:
        (self.repository / "unrelated.txt").write_text("DIRTY\n", encoding="utf-8")
        outcome = self.runtime.commit(self.approve(self.prepare()))
        self.assertEqual(outcome["commit_evidence"]["committed_files"], ["hello.txt"])
        self.assertEqual((self.repository / "unrelated.txt").read_text(), "DIRTY\n")
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")
        self.assertIn("unrelated.txt", self.git("status", "--porcelain").stdout)

    def test_u_changed_unrelated_file_makes_approval_stale(self) -> None:
        (self.repository / "unrelated.txt").write_text("DIRTY-1\n", encoding="utf-8")
        change_set_id = self.approve(self.prepare())
        (self.repository / "unrelated.txt").write_text("DIRTY-2\n", encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "git_unrelated_changes_stale"):
            self.runtime.commit(change_set_id)

    def test_v_new_unrelated_file_makes_approval_stale(self) -> None:
        change_set_id = self.approve(self.prepare())
        (self.repository / "outside.txt").write_text("OUTSIDE\n", encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "git_unrelated_changes_stale"):
            self.runtime.commit(change_set_id)

    def test_w_mutation_target_fingerprint_mismatch_is_rejected(self) -> None:
        path = self.mutations.root / f"{self.execution_id}.mutation.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["target_post_fingerprints"]["hello.txt"] = "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "mutation_evidence_mismatch"):
            self.prepare()

    def test_x_scope_violation_evidence_is_not_commit_eligible(self) -> None:
        path = self.mutations.root / f"{self.execution_id}.mutation.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["scope_violations"] = [
            {"code": "outside_scope", "path": "other.txt", "message": "outside"}
        ]
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "mutation_evidence_mismatch"):
            self.prepare()

    def test_y_dry_run_mutation_cannot_become_a_commit(self) -> None:
        path = self.mutations.root / f"{self.execution_id}.mutation.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["dry_run"] = True
        value["apply_status"] = "preview"
        value["mutation_kind"] = "proposed"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "mutation_evidence_mismatch"):
            self.prepare()

    def test_z_missing_review_reference_is_rejected(self) -> None:
        job_path = self.jobs.store.root / f"{self.job_id}.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        job["output_refs"] = [
            ref for ref in job["output_refs"] if not ref["ref"].startswith("runtime-review:")
        ]
        job_path.write_text(json.dumps(job), encoding="utf-8")
        with self.assertRaisesRegex(GitRuntimeError, "mutation_evidence_missing.*persisted independent review"):
            self.prepare()

    def test_aa_human_review_completion_is_commit_eligible(self) -> None:
        self.runtime.commit(self.approve(self.prepare()))
        job_id, execution_id = self.completed_write(
            modified={"hello.txt": "HUMAN\n"}, review_decision="NEEDS_HUMAN"
        )
        prepared = self.runtime.prepare(
            job_id=job_id,
            execution_id=execution_id,
            repository_root=self.repository,
            commit_message="Commit human-completed review",
        )
        outcome = self.runtime.commit(self.approve(prepared))
        self.assertEqual(outcome["commit_evidence"]["committed_files"], ["hello.txt"])

    def test_ab_commit_approval_survives_runtime_restart(self) -> None:
        prepared = self.prepare()
        approval_id = prepared["approval"]["approval_id"]
        restarted = ApprovalRuntime(
            JobRuntime(self.root / "state" / "jobs"),
            FileApprovalStore(self.root / "state" / "approvals"),
        )
        resolved = restarted.resolve(
            approval_id, decision="APPROVED", decided_by="restart-owner"
        )
        self.assertEqual(resolved["approval"]["status"], "APPROVED")

    def test_ac_tampered_commit_approval_fails_closed(self) -> None:
        prepared = self.prepare()
        approval_id = prepared["approval"]["approval_id"]
        approval_path = self.approval_store.root / f"{approval_id}.approval.json"
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        approval["commit_scope"]["commit_message"] = "Broadened"
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
        with self.assertRaisesRegex(ApprovalRuntimeError, "fingerprint"):
            self.approvals.resolve(
                approval_id, decision="APPROVED", decided_by="test-owner"
            )

    def test_ad_repository_hook_failure_blocks_commit_without_retry(self) -> None:
        change_set_id = self.approve(self.prepare())
        hook = self.repository / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)
        with self.assertRaisesRegex(GitRuntimeError, "git_commit_failed"):
            self.runtime.commit(change_set_id)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.base_head)

    def test_ae_runtime_source_excludes_dangerous_git_authority(self) -> None:
        source = (RUNTIME_REPOSITORY / "runtime" / "git" / "runtime.py").read_text()
        self.assertNotIn('"add", "."', source)
        self.assertNotIn('"add", "-A"', source)
        self.assertNotIn('"danger-full-access"', source)
        for argument in ("push", "merge", "rebase", "--amend", "--force", "--no-verify", "reset"):
            with self.subTest(argument=argument), self.assertRaisesRegex(
                GitRuntimeError, "git_command_forbidden"
            ):
                self.runtime._git(self.repository, [argument])

    def test_af_all_runtime_git_processes_use_shell_false(self) -> None:
        calls: list[dict[str, object]] = []

        def recording_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(kwargs)
            return subprocess.run(*args, **kwargs)

        observed = GitRuntime(
            RUNTIME_REPOSITORY,
            self.jobs,
            self.executions,
            self.reviews,
            self.mutations,
            self.approvals,
            self.git_store,
            runner=recording_runner,
        )
        observed.prepare(
            job_id=self.job_id,
            execution_id=self.execution_id,
            repository_root=self.repository,
            commit_message="Inspect structured process calls",
            dry_run=True,
        )
        self.assertTrue(calls)
        self.assertTrue(all(call.get("shell") is False for call in calls))

    def test_ag_change_set_authority_is_immutable_in_store(self) -> None:
        prepared = self.prepare()
        change_set = self.git_store.load_change_set(prepared["change_set"]["change_set_id"])
        tampered = GitChangeSet.from_dict(change_set.to_dict())
        object.__setattr__(tampered, "commit_message", "Changed after approval")
        with self.assertRaisesRegex(GitStoreError, "immutable"):
            self.git_store.save_change_set(tampered)

    def test_ah_tampered_commit_evidence_is_rejected_on_reload(self) -> None:
        outcome = self.runtime.commit(self.approve(self.prepare()))
        evidence_id = outcome["commit_evidence"]["evidence_id"]
        path = self.git_store.evidence / f"{evidence_id}.commit.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["commit_hash"] = "0" * 40
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(GitStoreError, "fingerprint"):
            self.git_store.load_evidence(evidence_id)

    def test_ai_change_set_round_trip_preserves_all_authority(self) -> None:
        prepared = self.prepare()
        loaded = self.git_store.load_change_set(prepared["change_set"]["change_set_id"])
        self.assertEqual(GitChangeSet.from_dict(loaded.to_dict()), loaded)

    def test_aj_commit_fingerprint_changes_with_file_list(self) -> None:
        prepared = self.prepare()
        approval = prepared["approval"]
        scope = dict(approval["commit_scope"])
        scope["changed_files"] = ["hello.txt", "other.txt"]
        from runtime.git.models import commit_authorization_fingerprint

        self.assertNotEqual(
            commit_authorization_fingerprint(scope), approval["authorization_fingerprint"]
        )

    def test_ak_duplicate_prepare_reuses_same_change_set_and_approval(self) -> None:
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(
            first["change_set"]["change_set_id"], second["change_set"]["change_set_id"]
        )
        self.assertEqual(first["approval"]["approval_id"], second["approval"]["approval_id"])

    def test_al_commit_message_and_author_are_verified_in_evidence(self) -> None:
        outcome = self.runtime.commit(self.approve(self.prepare()))
        evidence = outcome["commit_evidence"]
        self.assertEqual(evidence["commit_message"], "Apply verified hello update")
        self.assertEqual(evidence["author_name"], "Agent Company Test")
        self.assertEqual(evidence["author_email"], "agent-company@example.invalid")

    def test_am_bounded_diff_artifact_is_persisted(self) -> None:
        prepared = self.prepare()
        change_set_id = prepared["change_set"]["change_set_id"]
        diff = self.git_store.load_diff(change_set_id)
        self.assertIn("-BEFORE", diff)
        self.assertIn("+AFTER", diff)

    def test_an_global_git_identity_is_not_modified(self) -> None:
        before_name = subprocess.run(
            ["git", "config", "--global", "--get", "user.name"],
            capture_output=True,
            text=True,
            shell=False,
        ).stdout
        self.runtime.commit(self.approve(self.prepare()))
        after_name = subprocess.run(
            ["git", "config", "--global", "--get", "user.name"],
            capture_output=True,
            text=True,
            shell=False,
        ).stdout
        self.assertEqual(before_name, after_name)

    def test_ao_commit_evidence_fingerprint_is_recomputable(self) -> None:
        from runtime.git.models import commit_evidence_fingerprint

        evidence = self.runtime.commit(self.approve(self.prepare()))["commit_evidence"]
        fingerprint = evidence.pop("evidence_fingerprint")
        evidence.pop("schema_version")
        self.assertEqual(commit_evidence_fingerprint(evidence), fingerprint)

    def test_ap_change_set_and_commit_artifacts_are_git_ignored(self) -> None:
        candidate = RUNTIME_REPOSITORY / "runtime" / "state" / "executions" / "git" / "probe.json"
        result = subprocess.run(
            ["git", "check-ignore", str(candidate)],
            cwd=RUNTIME_REPOSITORY,
            capture_output=True,
            text=True,
            shell=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_aq_cli_prepare_dry_run_uses_canonical_runtime(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = run(
                [
                    "--state-root",
                    str(self.root / "state" / "jobs"),
                    "--execution-root",
                    str(self.root / "state" / "executions"),
                    "--approval-root",
                    str(self.root / "state" / "approvals"),
                    "--git-state-root",
                    str(self.root / "state" / "executions" / "git-cli"),
                    "git",
                    "prepare",
                    "--job-id",
                    self.job_id,
                    "--execution-id",
                    self.execution_id,
                    "--repository-root",
                    str(self.repository),
                    "--message",
                    "Preview exact Git change",
                    "--dry-run",
                ]
            )
        self.assertEqual(exit_code, 0, stderr.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["change_set"]["status"], "PREVIEW")
        self.assertEqual(self.git("diff", "--cached", "--name-only").stdout, "")

    def test_ar_reviewer_can_inspect_commit_evidence_without_authority(self) -> None:
        outcome = self.runtime.commit(self.approve(self.prepare()))
        job = self.jobs.show(self.job_id)
        job["output_refs"].extend(
            [
                self.git_store.change_set_ref(outcome["change_set"]["change_set_id"]),
                self.git_store.evidence_ref(outcome["commit_evidence"]["evidence_id"]),
            ]
        )
        builder = ReviewContextBuilder(
            RUNTIME_REPOSITORY,
            self.executions,
            FileProviderArtifactStore(self.root / "state" / "executions" / "provider-output"),
            self.mutations,
            self.git_store,
        )
        evidence = builder._git_evidence(job)
        self.assertEqual(
            {item.ref["ref"].split(":", 1)[0] for item in evidence},
            {"runtime-git-change-set", "runtime-git-commit"},
        )
        commit_approval = outcome["commit_evidence"]["approval_ref"]["ref"]
        self.assertTrue(commit_approval.startswith("runtime-approval:"))

    def test_as_protected_path_evidence_is_rejected_again_at_git_boundary(self) -> None:
        self.runtime.commit(self.approve(self.prepare()))
        job_id, execution_id = self.completed_write(created={".env": "SECRET=value\n"})
        with self.assertRaisesRegex(GitRuntimeError, "git_protected_path_violation"):
            self.runtime.prepare(
                job_id=job_id,
                execution_id=execution_id,
                repository_root=self.repository,
                commit_message="Must not commit protected file",
            )


if __name__ == "__main__":
    unittest.main()
