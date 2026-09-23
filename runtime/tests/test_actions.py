from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.actions.authorization import authorization_fingerprint
from runtime.actions.models import ExecutionScope, ScopeContractError
from runtime.actions.runtime import ControlledWriteRuntime
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.execution.models import ExecutionRequest
from runtime.providers.adapters import CliProviderAdapter
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfiguration
from runtime.providers.context import ExecutionContextBuilder
from runtime.providers.executor import ProviderExecutor
from runtime.providers.models import ProviderAvailability, ProviderExecutionResult
from runtime.providers.routing import ProviderRouter
from runtime.review.verification import DeterministicVerifier
from runtime.storage.execution_store import FileExecutionStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class MutatingAdapter:
    provider_id = "codex"

    def __init__(self, mutate=None, result: ProviderExecutionResult | None = None) -> None:
        self.mutate = mutate or (lambda _: None)
        self.result = result or ProviderExecutionResult("succeeded", "done", "", 0)
        self.workspaces: list[Path] = []

    def is_available(self) -> ProviderAvailability:
        return ProviderAvailability(True, "fake_available", "C:/fake/codex.exe")

    def execute(self, request, context, *, working_directory=None):
        workspace = Path(working_directory)
        self.workspaces.append(workspace)
        self.mutate(workspace)
        return self.result


class UnavailableAdapter:
    provider_id = "claude"

    def is_available(self) -> ProviderAvailability:
        return ProviderAvailability(False, "fake_unavailable")

    def execute(self, request, context, *, working_directory=None):
        raise AssertionError("Unavailable adapter must not execute")


class ControlledWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.target = self.root / "target"
        self.target.mkdir()
        (self.target / "src").mkdir()
        (self.target / "src" / "existing.txt").write_text("before\n", encoding="utf-8")
        self.mutations = FileMutationArtifactStore(self.root / "mutations")
        self.runtime = ControlledWriteRuntime(REPOSITORY_ROOT, self.mutations)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def scope(self, **overrides):
        value = {
            "project_root": str(self.target),
            "allowed_paths": ["src"],
            "forbidden_paths": [],
            "write_mode": "CREATE_OR_MODIFY",
            "max_changed_files": 4,
            "max_artifact_bytes": 64 * 1024,
            "allow_tests": False,
            "allow_git_reads": False,
            "allow_protected_paths": False,
        }
        value.update(overrides)
        return value

    def request(self, scope=None, **overrides):
        scope = scope or self.scope()
        values = {
            "execution_id": "execution-write-001",
            "job_id": "job-write-001",
            "task": "Update the authorized file",
            "task_class": "software",
            "project_id": None,
            "agent": "software",
            "skill": None,
            "workflow": "software",
            "capability": "software_implementation",
            "provider": "codex",
            "risk_level": "approval_required",
            "input_refs": (),
            "context_refs": (),
            "review_required": True,
            "attempt": 1,
            "approval_status": "approved",
            "execution_mode": "CONTROLLED_WRITE",
            "execution_scope": scope,
        }
        values.update(overrides)
        values["authorization_fingerprint"] = authorization_fingerprint(values)
        return ExecutionRequest(**values)

    def execute_controlled(self, adapter, request=None):
        return self.runtime.execute(
            request or self.request(), SimpleNamespace(render=lambda: "task"), adapter
        )

    def test_a_scope_rejects_parent_traversal(self) -> None:
        with self.assertRaises(ScopeContractError):
            ExecutionScope.from_dict(self.scope(allowed_paths=["../outside.txt"]))

    def test_b_scope_rejects_absolute_allowed_path(self) -> None:
        with self.assertRaises(ScopeContractError):
            ExecutionScope.from_dict(self.scope(allowed_paths=["C:/outside.txt"]))

    def test_b2_scope_rejects_windows_alias_and_ads_paths(self) -> None:
        for path in ("src/CON.txt", "src/file.txt:stream", "src/trailing."):
            with self.subTest(path=path), self.assertRaises(ScopeContractError):
                ExecutionScope.from_dict(self.scope(allowed_paths=[path]))

    def test_c_job_requires_approval_and_review_for_controlled_write(self) -> None:
        jobs = JobRuntime(self.root / "jobs")
        payload = {
            "task": "Write",
            "task_class": "software",
            "agent": "software",
            "workflow": "software",
            "capability": "software_implementation",
            "risk_level": "medium",
            "approval_status": "not_required",
            "review_required": False,
            "input_refs": [],
            "output_refs": [],
            "created_by": "test",
            "execution_mode": "CONTROLLED_WRITE",
            "execution_scope": self.scope(),
        }
        with self.assertRaisesRegex(RuntimeError, "approval_status"):
            jobs.create(payload)

    def test_d_missing_exact_authorization_never_calls_provider(self) -> None:
        adapter = MutatingAdapter(lambda root: (root / "src" / "new.txt").write_text("x"))
        request = self.request(authorization_fingerprint="0" * 64)
        object.__setattr__(request, "authorization_fingerprint", "0" * 64)
        outcome = self.execute_controlled(adapter, request)
        self.assertEqual(outcome.provider_result.error_category, "write_not_authorized")
        self.assertEqual(adapter.workspaces, [])

    def test_d1_project_scope_must_match_canonical_project_root(self) -> None:
        adapter = MutatingAdapter()
        outcome = self.execute_controlled(
            adapter, self.request(project_id="brightshore")
        )
        self.assertEqual(outcome.provider_result.error_category, "write_scope_invalid")
        self.assertEqual(adapter.workspaces, [])

    def test_d2_approval_persists_and_applies_the_exact_write_scope(self) -> None:
        jobs = JobRuntime(self.root / "jobs")
        created = jobs.create(
            {
                "task": "Write",
                "task_class": "software",
                "agent": "software",
                "workflow": "software",
                "capability": "software_implementation",
                "risk_level": "approval_required",
                "approval_status": "required",
                "review_required": True,
                "input_refs": [],
                "output_refs": [],
                "created_by": "test",
                "execution_mode": "CONTROLLED_WRITE",
                "execution_scope": self.scope(),
            }
        )
        approvals = ApprovalRuntime(jobs, FileApprovalStore(self.root / "approvals"))
        pending = approvals.request_execution(created["job_id"], reason="Scoped write")
        self.assertEqual(pending.request.execution_mode, "CONTROLLED_WRITE")
        self.assertEqual(pending.request.execution_scope, self.scope())
        resolved = approvals.resolve(
            pending.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
            reason="Approved exact path boundary",
        )
        self.assertEqual(resolved["job"]["status"], "queued")
        self.assertEqual(
            resolved["job"]["approval"]["authorization_fingerprint"],
            pending.request.authorization_fingerprint,
        )

    def test_d3_changed_write_scope_makes_pending_approval_stale(self) -> None:
        jobs = JobRuntime(self.root / "jobs")
        created = jobs.create(
            {
                "task": "Write",
                "task_class": "software",
                "agent": "software",
                "workflow": "software",
                "capability": "software_implementation",
                "risk_level": "approval_required",
                "approval_status": "required",
                "review_required": True,
                "input_refs": [],
                "output_refs": [],
                "created_by": "test",
                "execution_mode": "CONTROLLED_WRITE",
                "execution_scope": self.scope(),
            }
        )
        approvals = ApprovalRuntime(jobs, FileApprovalStore(self.root / "approvals"))
        pending = approvals.request_execution(created["job_id"], reason="Scoped write")
        path = self.root / "jobs" / f"{created['job_id']}.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["execution_scope"]["allowed_paths"] = ["src/other.txt"]
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(ApprovalRuntimeError, "scope has changed"):
            approvals.resolve(
                pending.request.approval_id,
                decision="APPROVED",
                decided_by="owner",
                reason=None,
            )

    def test_e_create_is_applied_with_independent_evidence(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(
                lambda root: (root / "src" / "created.txt").write_text(
                    "created\n", encoding="utf-8"
                )
            )
        )
        self.assertEqual(outcome.provider_result.status, "succeeded")
        self.assertEqual(
            (self.target / "src" / "created.txt").read_text(encoding="utf-8"),
            "created\n",
        )
        evidence = self.mutations.load("execution-write-001")
        self.assertEqual(evidence["created_files"], ["src/created.txt"])
        self.assertEqual(evidence["apply_status"], "applied")
        self.assertEqual(evidence["scope_violations"], [])
        self.assertEqual(
            evidence["post_fingerprints"], evidence["target_post_fingerprints"]
        )

    def test_f_modify_is_applied_and_diff_is_bounded(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(
                lambda root: (root / "src" / "existing.txt").write_text(
                    "after\n", encoding="utf-8"
                )
            )
        )
        self.assertEqual(outcome.provider_result.status, "succeeded")
        evidence = self.mutations.load("execution-write-001")
        self.assertEqual(evidence["modified_files"], ["src/existing.txt"])
        diff = (self.root / "mutations" / "execution-write-001.diff").read_text(
            encoding="utf-8"
        )
        self.assertIn("-before", diff)
        self.assertIn("+after", diff)

    def test_g_delete_is_rejected_when_write_mode_disallows_it(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(lambda root: (root / "src" / "existing.txt").unlink())
        )
        self.assertEqual(outcome.provider_result.error_category, "mutation_scope_violation")
        self.assertTrue((self.target / "src" / "existing.txt").exists())

    def test_h_delete_is_applied_when_explicitly_allowed(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(lambda root: (root / "src" / "existing.txt").unlink()),
            self.request(self.scope(write_mode="CREATE_MODIFY_DELETE")),
        )
        self.assertEqual(outcome.provider_result.status, "succeeded")
        self.assertFalse((self.target / "src" / "existing.txt").exists())

    def test_i_out_of_scope_change_is_detected_and_not_applied(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(
                lambda root: (root / "outside.txt").write_text("no", encoding="utf-8")
            )
        )
        self.assertEqual(outcome.provider_result.error_category, "mutation_scope_violation")
        self.assertFalse((self.target / "outside.txt").exists())
        evidence = self.mutations.load("execution-write-001")
        self.assertEqual(evidence["scope_violations"][0]["path"], "outside.txt")

    def test_j_protected_secret_path_is_rejected_before_provider(self) -> None:
        adapter = MutatingAdapter()
        outcome = self.execute_controlled(
            adapter, self.request(self.scope(allowed_paths=[".env"]))
        )
        self.assertEqual(outcome.provider_result.error_category, "protected_path_violation")
        self.assertEqual(adapter.workspaces, [])

    def test_j2_explicit_forbidden_path_cannot_be_changed(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(
                lambda root: (root / "src" / "existing.txt").write_text("blocked")
            ),
            self.request(self.scope(forbidden_paths=["src/existing.txt"])),
        )
        self.assertEqual(outcome.provider_result.error_category, "mutation_scope_violation")
        self.assertEqual(
            (self.target / "src" / "existing.txt").read_text(encoding="utf-8"),
            "before\n",
        )

    def test_j3_agent_company_governance_requires_explicit_policy_opt_in(self) -> None:
        scope = self.scope(
            project_root=str(REPOSITORY_ROOT), allowed_paths=["CONSTITUTION.md"]
        )
        adapter = MutatingAdapter()
        outcome = self.execute_controlled(adapter, self.request(scope))
        self.assertEqual(outcome.provider_result.error_category, "protected_path_violation")
        self.assertEqual(adapter.workspaces, [])

    def test_k_changed_file_limit_is_enforced(self) -> None:
        def mutate(root: Path) -> None:
            (root / "src" / "one.txt").write_text("1", encoding="utf-8")
            (root / "src" / "two.txt").write_text("2", encoding="utf-8")

        outcome = self.execute_controlled(
            MutatingAdapter(mutate),
            self.request(self.scope(max_changed_files=1)),
        )
        self.assertEqual(outcome.provider_result.error_category, "mutation_scope_violation")
        self.assertFalse((self.target / "src" / "one.txt").exists())

    def test_l_no_mutation_is_not_success(self) -> None:
        outcome = self.execute_controlled(MutatingAdapter())
        self.assertEqual(outcome.provider_result.error_category, "mutation_evidence_missing")

    def test_m_provider_failure_never_applies_staged_mutation(self) -> None:
        outcome = self.execute_controlled(
            MutatingAdapter(
                lambda root: (root / "src" / "existing.txt").write_text("bad"),
                ProviderExecutionResult(
                    "failed", "", "failure", 7, "provider_execution_failed", "failed"
                ),
            )
        )
        self.assertEqual(outcome.provider_result.status, "failed")
        self.assertEqual(
            (self.target / "src" / "existing.txt").read_text(encoding="utf-8"),
            "before\n",
        )

    def test_m2_concurrent_target_change_is_not_overwritten(self) -> None:
        def mutate(root: Path) -> None:
            (root / "src" / "existing.txt").write_text("provider\n", encoding="utf-8")
            (self.target / "src" / "existing.txt").write_text(
                "concurrent\n", encoding="utf-8"
            )

        outcome = self.execute_controlled(MutatingAdapter(mutate))
        self.assertEqual(outcome.provider_result.error_category, "validation_failed")
        self.assertEqual(
            (self.target / "src" / "existing.txt").read_text(encoding="utf-8"),
            "concurrent\n",
        )

    def test_n_codex_adapter_uses_fixed_workspace_write_arguments(self) -> None:
        captured = {}

        def runner(arguments, **kwargs):
            captured["arguments"] = arguments
            captured.update(kwargs)
            return SimpleNamespace(
                returncode=0,
                stdout="done",
                stderr=(
                    "OpenAI Codex v0.154.0-alpha.6.2\n--------\n"
                    "sandbox: workspace-write [workdir, /tmp, $TMPDIR]\n--------\n"
                ),
            )

        config = ProviderConfiguration(REPOSITORY_ROOT).cli_config("codex")
        adapter = CliProviderAdapter(
            config, REPOSITORY_ROOT, runner=runner, which=lambda _: "C:/fake/codex.exe"
        )
        with tempfile.TemporaryDirectory(prefix="agent-company-write-") as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            result = adapter.execute(
                self.request(),
                SimpleNamespace(render=lambda: "task"),
                working_directory=workspace,
            )
        self.assertEqual(result.status, "succeeded")
        self.assertFalse(captured["shell"])
        self.assertEqual(captured["cwd"], str(workspace.resolve()))
        self.assertEqual(captured["env"]["TEMP"], str(workspace.resolve()))
        self.assertEqual(captured["env"]["TMP"], str(workspace.resolve()))
        self.assertEqual(captured["env"]["TMPDIR"], str(workspace.resolve()))
        self.assertEqual(
            captured["arguments"],
            [
                "C:/fake/codex.exe",
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--config",
                'windows.sandbox="elevated"',
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "-",
            ],
        )
        self.assertEqual(captured["input"], "task")
        self.assertNotIn("--add-dir", captured["arguments"])
        self.assertNotIn("danger-full-access", captured["arguments"])
        self.assertEqual(result.requested_sandbox_mode, "workspace-write")
        self.assertEqual(result.effective_sandbox_mode, "workspace-write")

    def test_n2_codex_sandbox_downgrade_fails_closed_before_apply(self) -> None:
        def runner(arguments, **kwargs):
            workspace = Path(kwargs["cwd"])
            (workspace / "src" / "existing.txt").write_text(
                "staged only\n", encoding="utf-8"
            )
            return SimpleNamespace(
                returncode=0,
                stdout="claimed success",
                stderr="OpenAI Codex test\n--------\nsandbox: read-only\n--------\n",
            )

        adapter = CliProviderAdapter(
            ProviderConfiguration(REPOSITORY_ROOT).cli_config("codex"),
            REPOSITORY_ROOT,
            runner=runner,
            which=lambda _: "C:/fake/codex.exe",
        )
        with patch.object(
            self.runtime,
            "_apply",
            side_effect=AssertionError("sandbox mismatch must not call _apply"),
        ) as apply:
            outcome = self.execute_controlled(adapter)

        apply.assert_not_called()
        self.assertEqual(
            outcome.provider_result.error_category, "provider_sandbox_mismatch"
        )
        self.assertEqual(outcome.provider_result.requested_sandbox_mode, "workspace-write")
        self.assertEqual(outcome.provider_result.effective_sandbox_mode, "read-only")
        self.assertEqual(
            (self.target / "src" / "existing.txt").read_text(encoding="utf-8"),
            "before\n",
        )
        evidence = self.mutations.load("execution-write-001")
        self.assertEqual(evidence["requested_sandbox_mode"], "workspace-write")
        self.assertEqual(evidence["effective_sandbox_mode"], "read-only")
        self.assertEqual(evidence["apply_status"], "not_applied")
        self.assertEqual(evidence["applied_changed_files"], [])

    def test_n2b_danger_full_access_is_a_controlled_write_mismatch(self) -> None:
        adapter = CliProviderAdapter(
            ProviderConfiguration(REPOSITORY_ROOT).cli_config("codex"),
            REPOSITORY_ROOT,
            runner=lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout="claimed success",
                stderr=(
                    "OpenAI Codex test\n--------\n"
                    "sandbox: danger-full-access\n--------\n"
                ),
            ),
            which=lambda _: "C:/fake/codex.exe",
        )
        with patch.object(
            self.runtime,
            "_apply",
            side_effect=AssertionError("sandbox mismatch must not call _apply"),
        ) as apply:
            outcome = self.execute_controlled(adapter)

        apply.assert_not_called()
        self.assertEqual(
            outcome.provider_result.error_category, "provider_sandbox_mismatch"
        )
        self.assertEqual(
            outcome.provider_result.effective_sandbox_mode, "danger-full-access"
        )

    def test_n3_unreported_controlled_write_sandbox_fails_closed(self) -> None:
        adapter = CliProviderAdapter(
            ProviderConfiguration(REPOSITORY_ROOT).cli_config("codex"),
            REPOSITORY_ROOT,
            runner=lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout="sandbox: workspace-write", stderr=""
            ),
            which=lambda _: "C:/fake/codex.exe",
        )
        outcome = self.execute_controlled(adapter)
        self.assertEqual(
            outcome.provider_result.error_category, "provider_sandbox_unverified"
        )
        self.assertEqual(outcome.provider_result.requested_sandbox_mode, "workspace-write")
        self.assertIsNone(outcome.provider_result.effective_sandbox_mode)
        self.assertEqual(
            (self.target / "src" / "existing.txt").read_text(encoding="utf-8"),
            "before\n",
        )

    def test_n4_executor_preserves_non_retryable_sandbox_mismatch(self) -> None:
        adapter = CliProviderAdapter(
            ProviderConfiguration(REPOSITORY_ROOT).cli_config("codex"),
            REPOSITORY_ROOT,
            runner=lambda *args, **kwargs: SimpleNamespace(
                returncode=0,
                stdout="claimed success",
                stderr="OpenAI Codex test\n--------\nsandbox: read-only\n--------\n",
            ),
            which=lambda _: "C:/fake/codex.exe",
        )
        executor = ProviderExecutor(
            ProviderRouter(
                ProviderConfiguration(REPOSITORY_ROOT),
                {"claude": UnavailableAdapter(), "codex": adapter},
            ),
            ExecutionContextBuilder(REPOSITORY_ROOT),
            FileProviderArtifactStore(self.root / "provider"),
            controlled_write_runtime=self.runtime,
        )

        result = executor.execute(self.request())

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error["code"], "provider_sandbox_mismatch")
        self.assertFalse(result.error["retryable"])
        artifact = FileProviderArtifactStore(self.root / "provider").load(
            "execution-write-001"
        )
        self.assertEqual(
            artifact["process"]["requested_sandbox_mode"], "workspace-write"
        )
        self.assertEqual(artifact["process"]["effective_sandbox_mode"], "read-only")

    def test_n5_sandbox_metadata_cannot_broaden_execution_scope(self) -> None:
        def runner(arguments, **kwargs):
            workspace = Path(kwargs["cwd"])
            (workspace / "outside.txt").write_text("outside\n", encoding="utf-8")
            return SimpleNamespace(
                returncode=0,
                stdout="claimed success",
                stderr=(
                    "OpenAI Codex test\n--------\n"
                    "sandbox: workspace-write [workdir, /tmp, $TMPDIR]\n--------\n"
                ),
            )

        adapter = CliProviderAdapter(
            ProviderConfiguration(REPOSITORY_ROOT).cli_config("codex"),
            REPOSITORY_ROOT,
            runner=runner,
            which=lambda _: "C:/fake/codex.exe",
        )
        outcome = self.execute_controlled(adapter)

        self.assertEqual(
            outcome.provider_result.error_category, "mutation_scope_violation"
        )
        self.assertFalse((self.target / "outside.txt").exists())
        evidence = self.mutations.load("execution-write-001")
        self.assertEqual(evidence["effective_sandbox_mode"], "workspace-write")
        self.assertEqual(evidence["scope_violations"][0]["path"], "outside.txt")

    def test_o_claude_is_ineligible_and_controlled_write_falls_back_to_codex(self) -> None:
        router = ProviderRouter(
            ProviderConfiguration(REPOSITORY_ROOT),
            {"claude": UnavailableAdapter(), "codex": MutatingAdapter()},
        )
        selection = router.resolve(
            "software_implementation", "claude", "CONTROLLED_WRITE"
        )
        self.assertEqual(selection.actual_provider, "codex")
        self.assertTrue(selection.fallback_used)
        self.assertEqual(selection.execution_mode, "CONTROLLED_WRITE")

    def test_p_provider_executor_and_verifier_use_mutation_evidence(self) -> None:
        codex = MutatingAdapter(
            lambda root: (root / "src" / "created.txt").write_text("ok\n")
        )
        router = ProviderRouter(
            ProviderConfiguration(REPOSITORY_ROOT),
            {"claude": UnavailableAdapter(), "codex": codex},
        )
        provider_store = FileProviderArtifactStore(self.root / "provider")
        executor = ProviderExecutor(
            router,
            ExecutionContextBuilder(REPOSITORY_ROOT),
            provider_store,
            controlled_write_runtime=self.runtime,
        )
        request = self.request()
        result = executor.execute(request)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.execution_mode, "CONTROLLED_WRITE")
        self.assertTrue(
            any(ref["ref"].startswith("runtime-mutation:") for ref in result.output_refs)
        )
        executions = FileExecutionStore(self.root / "executions")
        executions.create(request, result)
        execution_ref = {
            "ref_type": "artifact",
            "ref": "runtime-execution:execution-write-001",
        }
        job = {
            "job_id": request.job_id,
            "agent": request.agent,
            "skill": request.skill,
            "workflow": request.workflow,
            "capability": request.capability,
            "execution_mode": "CONTROLLED_WRITE",
            "status": "reviewing",
            "review_required": True,
            "output_refs": [*result.output_refs, execution_ref],
        }
        verification = DeterministicVerifier(
            executions, provider_store, self.mutations
        ).verify(job, request, result)
        self.assertEqual(verification.status, "PASS")
        self.assertIn(
            "mutation_evidence_valid", {check.name for check in verification.checks}
        )

    def test_q_dry_run_never_calls_apply_and_records_preview_evidence(self) -> None:
        request = self.request(self.scope(dry_run=True), dry_run=True)
        adapter = MutatingAdapter(
            lambda root: (root / "src" / "existing.txt").write_text(
                "proposed\n", encoding="utf-8"
            )
        )
        with patch.object(
            self.runtime,
            "_apply",
            side_effect=AssertionError("dry-run must not call _apply"),
        ) as apply:
            outcome = self.execute_controlled(adapter, request)

        apply.assert_not_called()
        self.assertEqual(outcome.provider_result.status, "succeeded")
        self.assertEqual(
            (self.target / "src" / "existing.txt").read_text(encoding="utf-8"),
            "before\n",
        )
        evidence = self.mutations.load(request.execution_id)
        self.assertTrue(evidence["dry_run"])
        self.assertEqual(evidence["apply_status"], "preview")
        self.assertEqual(evidence["mutation_kind"], "proposed")
        self.assertEqual(evidence["proposed_modified_files"], ["src/existing.txt"])
        self.assertEqual(evidence["applied_changed_files"], [])
        self.assertEqual(
            evidence["provider_eligibility"],
            {
                "requested_provider": "codex",
                "executing_provider": "codex",
                "status": "selected_by_canonical_router",
            },
        )
        self.assertTrue(evidence["target_integrity"]["unchanged"])
        self.assertEqual(
            evidence["target_integrity"]["before"]["fingerprint"],
            evidence["target_integrity"]["after"]["fingerprint"],
        )

    def test_r_reviewer_accepts_bounded_dry_run_preview_as_unapplied(self) -> None:
        request = self.request(self.scope(dry_run=True), dry_run=True)
        router = ProviderRouter(
            ProviderConfiguration(REPOSITORY_ROOT),
            {
                "claude": UnavailableAdapter(),
                "codex": MutatingAdapter(
                    lambda root: (root / "src" / "created.txt").write_text("preview\n")
                ),
            },
        )
        provider_store = FileProviderArtifactStore(self.root / "provider")
        executor = ProviderExecutor(
            router,
            ExecutionContextBuilder(REPOSITORY_ROOT),
            provider_store,
            controlled_write_runtime=self.runtime,
        )
        result = executor.execute(request)
        executions = FileExecutionStore(self.root / "executions")
        executions.create(request, result)
        execution_ref = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{request.execution_id}",
        }
        job = {
            "job_id": request.job_id,
            "agent": request.agent,
            "skill": request.skill,
            "workflow": request.workflow,
            "capability": request.capability,
            "execution_mode": "CONTROLLED_WRITE",
            "dry_run": True,
            "status": "reviewing",
            "review_required": True,
            "output_refs": [*result.output_refs, execution_ref],
        }

        verification = DeterministicVerifier(
            executions, provider_store, self.mutations
        ).verify(job, request, result)

        self.assertEqual(verification.status, "PASS")
        self.assertFalse((self.target / "src" / "created.txt").exists())
        evidence = self.mutations.load(request.execution_id)
        self.assertEqual(evidence["apply_status"], "preview")
        self.assertEqual(evidence["applied_changed_files"], [])

    def test_s_dry_run_is_bound_into_authorization_fingerprint(self) -> None:
        base = {
            "job_id": "job-boundary",
            "attempt": 1,
            "project_id": None,
            "capability": "software_implementation",
            "risk_level": "approval_required",
            "execution_mode": "CONTROLLED_WRITE",
            "execution_scope": self.scope(),
        }
        preview = {
            **base,
            "dry_run": True,
            "execution_scope": self.scope(dry_run=True),
        }
        self.assertNotEqual(
            authorization_fingerprint(base), authorization_fingerprint(preview)
        )

    def test_t_retry_preserves_dry_run_and_requires_fresh_approval(self) -> None:
        jobs = JobRuntime(self.root / "jobs")
        created = jobs.create(
            {
                "task": "Preview write",
                "task_class": "software",
                "agent": "software",
                "workflow": "software",
                "capability": "software_implementation",
                "risk_level": "approval_required",
                "approval_status": "required",
                "review_required": True,
                "max_attempts": 2,
                "input_refs": [],
                "output_refs": [],
                "created_by": "test",
                "execution_mode": "CONTROLLED_WRITE",
                "dry_run": True,
                "execution_scope": self.scope(dry_run=True),
            }
        )
        approvals = ApprovalRuntime(jobs, FileApprovalStore(self.root / "approvals"))
        pending = approvals.request_execution(created["job_id"], reason="Preview only")
        approved = approvals.resolve(
            pending.request.approval_id,
            decision="APPROVED",
            decided_by="owner",
            reason="Approve dry-run only",
        )["job"]
        running = jobs.claim()
        assert running is not None
        failed = jobs.fail(
            approved["job_id"], code="provider_unavailable", message="Retry"
        )
        retry = jobs.retry(failed["job_id"])

        self.assertTrue(retry["dry_run"])
        self.assertTrue(retry["execution_scope"]["dry_run"])
        self.assertEqual(retry["approval_status"], "required")
        self.assertNotIn("approval", retry)

    def test_u_dry_run_approval_cannot_authorize_real_execution(self) -> None:
        jobs = JobRuntime(self.root / "jobs")
        created = jobs.create(
            {
                "task": "Preview write",
                "task_class": "software",
                "agent": "software",
                "workflow": "software",
                "capability": "software_implementation",
                "risk_level": "approval_required",
                "approval_status": "required",
                "review_required": True,
                "input_refs": [],
                "output_refs": [],
                "created_by": "test",
                "execution_mode": "CONTROLLED_WRITE",
                "dry_run": True,
                "execution_scope": self.scope(dry_run=True),
            }
        )
        approvals = ApprovalRuntime(jobs, FileApprovalStore(self.root / "approvals"))
        pending = approvals.request_execution(created["job_id"], reason="Preview only")
        path = self.root / "jobs" / f"{created['job_id']}.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["dry_run"] = False
        tampered["execution_scope"]["dry_run"] = False
        path.write_text(json.dumps(tampered), encoding="utf-8")

        with self.assertRaisesRegex(ApprovalRuntimeError, "scope has changed"):
            approvals.resolve(
                pending.request.approval_id,
                decision="APPROVED",
                decided_by="owner",
                reason="Must not widen preview authority",
            )


if __name__ == "__main__":
    unittest.main()
