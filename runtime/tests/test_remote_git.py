from __future__ import annotations

import json
import io
import shutil
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout

from runtime.cli.__main__ import build_parser, run
from runtime.git.forge import ForgeError, GitHubCliPullRequestAdapter, PullRequestState
from runtime.git.remote_models import (
    REMOTE_GIT_CAPABILITIES,
    PullRequestEvidence,
    PullRequestPlan,
    PushEvidence,
    PushPlan,
    remote_evidence_fingerprint,
)
from runtime.git.remote_runtime import RemoteGitRuntime, RemoteGitRuntimeError
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.review.context import ReviewContextBuilder
from runtime.tests import test_git as phase_i_tests


class FakePullRequestAdapter:
    def __init__(self) -> None:
        self.state: PullRequestState | None = None
        self.create_calls = 0

    def inspect(self, repository_slug: str, head_branch: str, base_branch: str):
        return self.state

    def create(
        self,
        repository_slug: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PullRequestState:
        self.create_calls += 1
        self.state = PullRequestState(
            number=17,
            url=f"https://github.com/{repository_slug}/pull/17",
            repository_slug=repository_slug,
            head_branch=head_branch,
            base_branch=base_branch,
            head_commit=self.head_commit,
            title=title,
        )
        return self.state


class RemoteGitRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("Git is required")
        self.phase_i = phase_i_tests.GitRuntimeTests(
            "test_d_exact_stage_commit_and_evidence"
        )
        self.phase_i.setUp()
        committed = self.phase_i.runtime.commit(
            self.phase_i.approve(self.phase_i.prepare())
        )
        self.commit = committed["commit_evidence"]
        self.change_set = committed["change_set"]
        self.repository = self.phase_i.repository
        self.remote_repository = self.phase_i.root / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", "-q", str(self.remote_repository)],
            check=True,
            capture_output=True,
            shell=False,
        )
        self.phase_i.git("remote", "add", "origin", str(self.remote_repository))
        self.store = FileRemoteGitArtifactStore(
            self.phase_i.root / "state" / "executions" / "git"
        )
        self.adapter = FakePullRequestAdapter()
        self.runtime = RemoteGitRuntime(
            self.phase_i.runtime,
            self.phase_i.approvals,
            self.store,
            pull_request_adapter=self.adapter,
        )

    def tearDown(self) -> None:
        self.phase_i.tearDown()

    def prepare_push(self, **overrides: object):
        values: dict[str, object] = {
            "change_set_id": self.change_set["change_set_id"],
            "remote_name": "origin",
            "remote_branch": "phase-6j-test",
        }
        values.update(overrides)
        return self.runtime.prepare_push(**values)

    def approve(self, prepared: dict[str, object]) -> str:
        approval = prepared["approval"]
        assert isinstance(approval, dict)
        self.phase_i.approvals.resolve(
            approval["approval_id"],
            decision="APPROVED",
            decided_by="test-owner",
        )
        plan = prepared["push_plan"]
        assert isinstance(plan, dict)
        return plan["push_plan_id"]

    def push(self):
        prepared = self.prepare_push()
        return self.runtime.push(self.approve(prepared))

    def hosted_push_evidence(self) -> str:
        pushed = self.push()
        local_plan = self.store.load_push_plan(pushed["push_plan"]["push_plan_id"])
        local_evidence = self.store.load_push_evidence(
            pushed["push_evidence"]["push_evidence_id"]
        )
        plan_id = "push-plan-hosted-test"
        evidence_id = "push-hosted-test"
        plan = PushPlan(
            push_plan_id=plan_id,
            change_set_id=local_plan.change_set_id,
            commit_evidence_ref=local_plan.commit_evidence_ref,
            job_id=local_plan.job_id,
            execution_id=local_plan.execution_id,
            repository_root=local_plan.repository_root,
            commit_hash=local_plan.commit_hash,
            parent_hash=local_plan.parent_hash,
            local_branch=local_plan.local_branch,
            remote_name="origin",
            remote_kind="https",
            remote_host="github.com",
            repository_slug="agent-company/test-repository",
            remote_url_display="https://github.com/agent-company/test-repository.git",
            remote_url_fingerprint="1" * 64,
            remote_branch="phase-6j-test",
            expected_remote_head=local_plan.expected_remote_head,
            created_at=local_plan.created_at,
            status="PUSHED",
            dry_run=False,
            approval_ref=local_plan.approval_ref,
            push_evidence_ref=self.store.push_evidence_ref(evidence_id),
        )
        fields = {
            "push_evidence_id": evidence_id,
            "push_plan_id": plan_id,
            "change_set_id": plan.change_set_id,
            "commit_evidence_ref": plan.commit_evidence_ref,
            "repository_root": plan.repository_root,
            "commit_hash": plan.commit_hash,
            "remote_name": plan.remote_name,
            "remote_url_display": plan.remote_url_display,
            "remote_url_fingerprint": plan.remote_url_fingerprint,
            "remote_branch": plan.remote_branch,
            "remote_head_before": local_evidence.remote_head_before,
            "remote_head_after": plan.commit_hash,
            "approval_ref": local_evidence.approval_ref,
            "pushed_at": local_evidence.pushed_at,
            "already_present": False,
        }
        evidence = PushEvidence(
            **fields, evidence_fingerprint=remote_evidence_fingerprint(fields)
        )
        self.store.create_push_plan(plan)
        self.store.create_push_evidence(evidence)
        self.adapter.head_commit = plan.commit_hash
        self.runtime._remote_head = lambda *args, **kwargs: plan.commit_hash
        return evidence_id

    def prepare_pr(self, **overrides: object):
        evidence_id = overrides.pop("push_evidence_id", None) or self.hosted_push_evidence()
        values: dict[str, object] = {
            "push_evidence_id": evidence_id,
            "base_branch": "main",
            "title": "Phase 6J controlled pull request",
            "body": "Verified runtime change ready for independent review.",
        }
        values.update(overrides)
        return self.runtime.prepare_pull_request(**values)

    def approve_pr(self, prepared: dict[str, object]) -> str:
        approval = prepared["approval"]
        self.phase_i.approvals.resolve(
            approval["approval_id"], decision="APPROVED", decided_by="test-owner"
        )
        return prepared["pull_request_plan"]["pull_request_plan_id"]

    def test_a_capabilities_are_explicit_and_exclude_merge(self) -> None:
        self.assertEqual(
            REMOTE_GIT_CAPABILITIES,
            {"GIT_REMOTE_INSPECT", "GIT_PUSH", "PULL_REQUEST_CREATE"},
        )
        self.assertNotIn("MERGE", REMOTE_GIT_CAPABILITIES)

    def test_b_push_plan_binds_commit_remote_branch_and_expected_head(self) -> None:
        prepared = self.prepare_push()
        plan = prepared["push_plan"]
        self.assertEqual(plan["commit_hash"], self.commit["commit_hash"])
        self.assertEqual(plan["remote_name"], "origin")
        self.assertEqual(plan["remote_branch"], "phase-6j-test")
        self.assertIsNone(plan["expected_remote_head"])

    def test_c_push_requires_separate_exact_approval(self) -> None:
        prepared = self.prepare_push()
        approval = prepared["approval"]
        self.assertEqual(approval["requested_action"], "PUSH_GIT_COMMIT")
        plan = self.store.load_push_plan(prepared["push_plan"]["push_plan_id"])
        self.assertEqual(
            approval["remote_scope"],
            plan.approval_scope,
        )
        self.assertEqual(
            approval["remote_scope"]["remote_url_display"],
            f"local:{self.remote_repository.resolve()}",
        )

    def test_ca_push_approval_cannot_cross_execution_boundary(self) -> None:
        prepared = self.prepare_push()
        plan_id = self.approve(prepared)
        approval_path = self.phase_i.approvals.store._path(
            prepared["approval"]["approval_id"]
        )
        value = json.loads(approval_path.read_text(encoding="utf-8"))
        value["execution_id"] = "execution-different"
        approval_path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_approval_mismatch"):
            self.runtime.push(plan_id)

    def test_d_controlled_push_updates_only_exact_remote_branch(self) -> None:
        outcome = self.push()
        evidence = outcome["push_evidence"]
        self.assertEqual(evidence["remote_head_after"], self.commit["commit_hash"])
        remote_head = subprocess.run(
            [
                "git",
                "--git-dir",
                str(self.remote_repository),
                "rev-parse",
                "refs/heads/phase-6j-test",
            ],
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        ).stdout.strip()
        self.assertEqual(remote_head, self.commit["commit_hash"])

    def test_e_unapproved_push_does_not_mutate_remote(self) -> None:
        prepared = self.prepare_push()
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_approval_mismatch"):
            self.runtime.push(prepared["push_plan"]["push_plan_id"])
        refs = subprocess.run(
            ["git", "--git-dir", str(self.remote_repository), "show-ref"],
            capture_output=True,
            text=True,
            shell=False,
        ).stdout
        self.assertEqual(refs, "")

    def test_f_rejected_push_does_not_mutate_remote(self) -> None:
        prepared = self.prepare_push()
        self.phase_i.approvals.resolve(
            prepared["approval"]["approval_id"],
            decision="REJECTED",
            decided_by="test-owner",
        )
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_approval_mismatch"):
            self.runtime.push(prepared["push_plan"]["push_plan_id"])

    def test_g_push_dry_run_does_not_create_approval_or_remote_ref(self) -> None:
        prepared = self.prepare_push(dry_run=True)
        self.assertIsNone(prepared["approval"])
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_dry_run_forbidden"):
            self.runtime.push(prepared["push_plan"]["push_plan_id"])

    def test_ga_cli_push_preview_uses_canonical_remote_runtime(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = run(
                [
                    "--state-root",
                    str(self.phase_i.root / "state" / "jobs"),
                    "--execution-root",
                    str(self.phase_i.root / "state" / "executions"),
                    "--approval-root",
                    str(self.phase_i.root / "state" / "approvals"),
                    "--git-state-root",
                    str(self.store.root),
                    "git",
                    "push-prepare",
                    "--change-set-id",
                    self.change_set["change_set_id"],
                    "--branch",
                    "phase-6j-cli-preview",
                    "--dry-run",
                ]
            )
        self.assertEqual(exit_code, 0, stderr.getvalue())
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["push_plan"]["status"], "PREVIEW")
        self.assertIsNone(result["approval"])

    def test_h_remote_url_change_after_approval_is_stale(self) -> None:
        plan_id = self.approve(self.prepare_push())
        other = self.phase_i.root / "other.git"
        subprocess.run(["git", "init", "--bare", "-q", str(other)], check=True, shell=False)
        self.phase_i.git("remote", "set-url", "origin", str(other))
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_definition_stale"):
            self.runtime.push(plan_id)

    def test_i_remote_head_change_after_approval_is_stale(self) -> None:
        plan_id = self.approve(self.prepare_push())
        self.phase_i.git("push", "origin", f"{self.commit['parent_hash']}:refs/heads/phase-6j-test")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_head_stale"):
            self.runtime.push(plan_id)

    def test_j_diverged_remote_is_rejected_before_approval(self) -> None:
        tree = self.phase_i.git(
            "rev-parse", f"{self.phase_i.base_head}^{{tree}}"
        ).stdout.strip()
        other_commit = self.phase_i.git(
            "commit-tree", tree, "-m", "Diverged remote commit"
        ).stdout.strip()
        self.phase_i.git("push", "origin", f"{other_commit}:refs/heads/phase-6j-test")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_branch_diverged"):
            self.prepare_push()

    def test_k_invalid_branch_is_rejected(self) -> None:
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_branch_invalid"):
            self.prepare_push(remote_branch="bad branch")

    def test_l_embedded_https_credentials_are_rejected(self) -> None:
        self.phase_i.git("remote", "set-url", "origin", "https://user:secret@github.com/acme/repo.git")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_url_credentials_forbidden"):
            self.prepare_push()

    def test_m_insecure_remote_scheme_is_rejected(self) -> None:
        self.phase_i.git("remote", "set-url", "origin", "http://github.com/acme/repo.git")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_url_scheme_forbidden"):
            self.prepare_push()

    def test_ma_noncanonical_ssh_identity_is_rejected(self) -> None:
        for remote in (
            "ssh://operator@github.com/acme/repo.git",
            "github.com:acme/repo.git",
            "ssh://git@github.com:2222/acme/repo.git",
        ):
            with self.subTest(remote=remote):
                self.phase_i.git("remote", "set-url", "origin", remote)
                with self.assertRaisesRegex(
                    RemoteGitRuntimeError,
                    "remote_url_credentials_forbidden|remote_url_scheme_forbidden",
                ):
                    self.prepare_push()

    def test_n_force_delete_merge_and_tag_arguments_are_forbidden(self) -> None:
        for argument in ("--force", "--force-with-lease", "--delete", "merge", "tag"):
            with self.subTest(argument=argument), self.assertRaisesRegex(
                RemoteGitRuntimeError, "remote_git_command_forbidden"
            ):
                self.runtime._git(self.repository, ["push", argument])

    def test_o_push_is_idempotent_after_evidence_persistence(self) -> None:
        first = self.push()
        second = self.runtime.push(first["push_plan"]["push_plan_id"])
        self.assertEqual(first["push_evidence"], second["push_evidence"])

    def test_p_push_state_survives_store_reload(self) -> None:
        outcome = self.push()
        reloaded = FileRemoteGitArtifactStore(self.store.root).load_push_evidence(
            outcome["push_evidence"]["push_evidence_id"]
        )
        self.assertEqual(reloaded.remote_head_after, self.commit["commit_hash"])

    def test_pa_push_recovers_evidence_link_after_interrupted_persistence(self) -> None:
        pushed = self.push()
        plan = self.store.load_push_plan(pushed["push_plan"]["push_plan_id"])
        self.store.save_push_plan(
            plan.transition("APPROVED", push_evidence_ref=None)
        )
        recovered = self.runtime.push(plan.push_plan_id)
        self.assertEqual(recovered["push_evidence"], pushed["push_evidence"])
        self.assertEqual(recovered["push_plan"]["status"], "PUSHED")

    def test_q_local_head_change_after_approval_blocks_push(self) -> None:
        plan_id = self.approve(self.prepare_push())
        (self.repository / "later.txt").write_text("later\n", encoding="utf-8")
        self.phase_i.git("add", "--", "later.txt")
        self.phase_i.git("commit", "-q", "-m", "later")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "push_plan_stale"):
            self.runtime.push(plan_id)

    def test_r_pull_request_plan_requires_separate_approval(self) -> None:
        prepared = self.prepare_pr()
        self.assertEqual(prepared["approval"]["requested_action"], "CREATE_PULL_REQUEST")
        self.assertEqual(prepared["pull_request_plan"]["head_commit"], self.commit["commit_hash"])

    def test_s_pull_request_creation_persists_verified_evidence(self) -> None:
        prepared = self.prepare_pr()
        outcome = self.runtime.create_pull_request(self.approve_pr(prepared))
        evidence = outcome["pull_request_evidence"]
        self.assertEqual(evidence["pull_request_number"], 17)
        self.assertEqual(evidence["head_commit"], self.commit["commit_hash"])
        self.assertEqual(self.adapter.create_calls, 1)

    def test_t_unapproved_pull_request_is_not_created(self) -> None:
        prepared = self.prepare_pr()
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_approval_mismatch"):
            self.runtime.create_pull_request(
                prepared["pull_request_plan"]["pull_request_plan_id"]
            )
        self.assertEqual(self.adapter.create_calls, 0)

    def test_u_rejected_pull_request_is_not_created(self) -> None:
        prepared = self.prepare_pr()
        self.phase_i.approvals.resolve(
            prepared["approval"]["approval_id"],
            decision="REJECTED",
            decided_by="test-owner",
        )
        with self.assertRaisesRegex(RemoteGitRuntimeError, "remote_approval_mismatch"):
            self.runtime.create_pull_request(prepared["pull_request_plan"]["pull_request_plan_id"])

    def test_v_pull_request_body_change_after_approval_is_stale(self) -> None:
        prepared = self.prepare_pr()
        plan_id = self.approve_pr(prepared)
        path = self.store.pull_request_bodies / f"{plan_id}.body.md"
        path.write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(RemoteGitRuntimeError, "pull_request_body_stale"):
            self.runtime.create_pull_request(plan_id)

    def test_w_existing_pull_request_race_is_recorded_without_duplicate(self) -> None:
        prepared = self.prepare_pr()
        plan_id = self.approve_pr(prepared)
        plan = self.store.load_pull_request_plan(plan_id)
        self.adapter.state = PullRequestState(
            number=18,
            url=f"https://github.com/{plan.repository_slug}/pull/18",
            repository_slug=plan.repository_slug,
            head_branch=plan.head_branch,
            base_branch=plan.base_branch,
            head_commit=plan.head_commit,
            title=plan.title,
        )
        outcome = self.runtime.create_pull_request(plan_id)
        self.assertTrue(outcome["pull_request_evidence"]["already_present"])
        self.assertEqual(self.adapter.create_calls, 0)

    def test_x_missing_forge_adapter_fails_closed(self) -> None:
        runtime = RemoteGitRuntime(
            self.phase_i.runtime, self.phase_i.approvals, self.store
        )
        with self.assertRaisesRegex(RemoteGitRuntimeError, "forge_unavailable"):
            runtime.prepare_pull_request(
                push_evidence_id="missing",
                base_branch="main",
                title="Title",
                body="Body",
            )

    def test_y_equal_pr_head_and_base_are_rejected(self) -> None:
        with self.assertRaisesRegex(RemoteGitRuntimeError, "Head and base"):
            self.prepare_pr(base_branch="phase-6j-test")

    def test_z_sensitive_pr_content_is_rejected(self) -> None:
        with self.assertRaisesRegex(RemoteGitRuntimeError, "pull_request_content_sensitive"):
            self.prepare_pr(body="API_KEY=very-secret-value")

    def test_za_forge_adapter_exposes_no_merge_method(self) -> None:
        self.assertFalse(hasattr(self.adapter, "merge"))

    def test_zb_reviewer_reads_remote_evidence_without_remote_authority(self) -> None:
        prepared = self.prepare_pr()
        created = self.runtime.create_pull_request(self.approve_pr(prepared))
        push_evidence_id = prepared["pull_request_plan"]["push_evidence_ref"][
            "ref"
        ].split(":", 1)[1]
        push_evidence = self.store.load_push_evidence(push_evidence_id)
        job = self.phase_i.jobs.show(self.phase_i.job_id)
        job["output_refs"].extend(
            [
                self.store.push_plan_ref(push_evidence.push_plan_id),
                self.store.push_evidence_ref(push_evidence_id),
                self.store.pull_request_plan_ref(
                    prepared["pull_request_plan"]["pull_request_plan_id"]
                ),
                prepared["pull_request_plan"]["body_ref"],
                self.store.pull_request_evidence_ref(
                    created["pull_request_evidence"]["pull_request_evidence_id"]
                ),
            ]
        )
        builder = ReviewContextBuilder(
            phase_i_tests.RUNTIME_REPOSITORY,
            self.phase_i.executions,
            FileProviderArtifactStore(
                self.phase_i.root / "state" / "executions" / "provider-output"
            ),
            self.phase_i.mutations,
            self.store,
        )
        refs = {item.ref["ref"].split(":", 1)[0] for item in builder._git_evidence(job)}
        self.assertEqual(
            refs,
            {
                "runtime-git-push-plan",
                "runtime-git-push",
                "runtime-pull-request-plan",
                "runtime-pull-request-body",
                "runtime-pull-request",
            },
        )


class RemoteGitCliContractTests(unittest.TestCase):
    def test_remote_commands_are_part_of_existing_git_cli(self) -> None:
        parser = build_parser()
        push = parser.parse_args(
            [
                "git",
                "push-prepare",
                "--change-set-id",
                "changes-1",
                "--branch",
                "phase-6j",
                "--dry-run",
            ]
        )
        pr = parser.parse_args(
            [
                "git",
                "pr-prepare",
                "--push-evidence-id",
                "push-1",
                "--base",
                "main",
                "--title",
                "Bounded pull request",
                "--body-file",
                "body.md",
                "--dry-run",
            ]
        )
        self.assertEqual((push.resource, push.command), ("git", "push-prepare"))
        self.assertEqual((pr.resource, pr.command), ("git", "pr-prepare"))

    def test_remote_artifact_schemas_match_model_fields(self) -> None:
        root = phase_i_tests.RUNTIME_REPOSITORY / "schemas"
        contracts = {
            "git-push-plan.schema.json": PushPlan,
            "git-push-evidence.schema.json": PushEvidence,
            "pull-request-plan.schema.json": PullRequestPlan,
            "pull-request-evidence.schema.json": PullRequestEvidence,
        }
        for filename, model in contracts.items():
            with self.subTest(filename=filename):
                schema = json.loads((root / filename).read_text(encoding="utf-8"))
                self.assertEqual(
                    set(schema["required"]),
                    {"schema_version", *model.__dataclass_fields__},
                )

    def test_github_adapter_uses_fixed_non_shell_commands_and_stdin_body(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            if arguments[1:3] == ["pr", "create"]:
                return subprocess.CompletedProcess(
                    arguments,
                    0,
                    stdout="https://github.com/acme/repo/pull/7\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout=json.dumps(
                    {
                        "number": 7,
                        "url": "https://github.com/acme/repo/pull/7",
                        "headRefName": "feature",
                        "baseRefName": "main",
                        "headRefOid": "a" * 40,
                        "title": "Bounded PR",
                    }
                ),
                stderr="",
            )

        adapter = GitHubCliPullRequestAdapter(
            runner=runner,
            which=lambda name: "C:/tools/gh.exe",
        )
        state = adapter.create(
            "acme/repo", "feature", "main", "Bounded PR", "Verified body"
        )
        self.assertEqual(state.number, 7)
        self.assertEqual(calls[0][1]["input"], "Verified body")
        self.assertTrue(all(call[1]["shell"] is False for call in calls))
        self.assertFalse(any("merge" in argument for call in calls for argument in call[0]))

    def test_github_adapter_rejects_evidence_url_for_another_repository(self) -> None:
        with self.assertRaisesRegex(ForgeError, "pull_request_evidence_invalid"):
            GitHubCliPullRequestAdapter._state(
                "acme/repo",
                {
                    "number": 7,
                    "url": "https://github.com/other/repo/pull/7",
                    "headRefName": "feature",
                    "baseRefName": "main",
                    "headRefOid": "a" * 40,
                    "title": "Bounded PR",
                },
            )


if __name__ == "__main__":
    unittest.main()
