"""GOV-02 exact approval transitions through real local Git/bare remotes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from runtime.core import capability_governance as gov
from runtime.core.capability_actions import ActionDecision
from runtime.core.task_contract import encoded, TaskContractError
from runtime.git.runtime import GitRuntimeError
from runtime.git.remote_runtime import RemoteGitRuntimeError
from runtime.storage.execution_store import FileExecutionStore
from runtime.tests import test_git as git_fixtures
from runtime.tests import test_remote_git as remote_fixtures
from runtime.tests import test_actions as write_fixtures


class CapabilityActionTests(unittest.TestCase):
    def local(self):
        case = git_fixtures.GitRuntimeTests()
        case.setUp(); self.addCleanup(case.tearDown)
        return case

    def remote(self):
        case = remote_fixtures.RemoteGitRuntimeTests()
        case.setUp(); self.addCleanup(case.tearDown)
        return case

    def test_local_commit_pins_certificate_human_approval_effect_and_result(self):
        case = self.local(); prepared = case.prepare(); identity = case.approve(prepared)
        result = case.runtime.commit(identity)
        approval_id = prepared["approval"]["approval_id"]
        store = FileExecutionStore(case.git_store.root)
        policy = store._decision_pair(approval_id, "action-policy")
        trace = store._decision_pair(approval_id, "action-result")
        self.assertEqual(policy["requested_action"], "COMMIT_CHANGE_SET")
        self.assertEqual(policy["policy_evaluation"]["profile"], "LOCAL_WRITE")
        self.assertEqual(policy["approval_received"]["decision_actor_type"], "local_operator")
        self.assertTrue(trace["effect_performed"])
        self.assertEqual(trace["evidence"], result)
        self.assertEqual(case.runtime.commit(identity), result)

    def test_missing_commit_result_pair_cannot_be_rebuilt_from_existing_commit(self):
        case = self.local(); prepared = case.prepare(); identity = case.approve(prepared)
        case.runtime.commit(identity)
        store = FileExecutionStore(case.git_store.root)
        for suffix in ("anchor", "witness"):
            store._decision_path(prepared["approval"]["approval_id"], "action-result", suffix).unlink()
        with self.assertRaises(GitRuntimeError): case.runtime.commit(identity)

    def test_missing_task_provenance_blocks_commit_before_staging(self):
        case = self.local(); prepared = case.prepare(); identity = case.approve(prepared)
        case.jobs.task_contract_store._path(case.job_id, "witness").unlink()
        with self.assertRaises(GitRuntimeError): case.runtime.commit(identity)
        self.assertEqual(case.git("rev-parse", "HEAD").stdout.strip(), case.base_head)
        self.assertEqual(case.git("diff", "--cached", "--name-only").stdout.strip(), "")

    def test_action_policy_pair_tampering_blocks_effect(self):
        case = self.local(); prepared = case.prepare(); identity = case.approve(prepared)
        change = case.git_store.load_change_set(identity)
        approval = case.approval_store.load(prepared["approval"]["approval_id"]).to_dict()
        audit = ActionDecision(case.jobs, case.approval_store, case.git_store,
                               approval, change.commit_scope, "canonical-local-git")
        value = deepcopy(audit.value); value["executor"] = "advisor"
        for suffix in ("anchor", "witness"):
            audit.store._decision_path(audit.identity, "action-policy", suffix).write_bytes(encoded(value, max_bytes=512 * 1024))
        with self.assertRaises(GitRuntimeError): case.runtime.commit(identity)
        self.assertEqual(case.git("rev-parse", "HEAD").stdout.strip(), case.base_head)

    def test_deleted_action_consumption_does_not_refund_effect(self):
        case = self.local(); prepared = case.prepare(); identity = case.approve(prepared)
        change = case.git_store.load_change_set(identity)
        approval = case.approval_store.load(prepared["approval"]["approval_id"]).to_dict()
        audit = ActionDecision(case.jobs, case.approval_store, case.git_store,
                               approval, change.commit_scope, "canonical-local-git")
        audit.consume()
        for suffix in ("anchor", "witness"):
            audit.store._decision_path(audit.identity, "action-effect", suffix).unlink()
        with self.assertRaises(GitRuntimeError): case.runtime.commit(identity)
        self.assertEqual(case.git("rev-parse", "HEAD").stdout.strip(), case.base_head)

    def test_remote_push_records_external_profile_and_explicit_human_transition(self):
        case = self.remote(); result = case.push()
        identity = result["push_plan"]["approval_ref"]["ref"].split(":", 1)[1]
        store = FileExecutionStore(case.store.root)
        policy = store._decision_pair(identity, "action-policy")
        self.assertEqual(policy["policy_evaluation"]["profile"], "EXTERNAL_EXECUTE")
        self.assertEqual(policy["policy_evaluation"]["blast_radius"], "external")
        self.assertEqual(policy["policy_evaluation"]["reversibility"], "irreversible")
        self.assertEqual(policy["authority_source"]["transition"], "separate-canonical-human-action-approval")
        self.assertTrue(store._decision_pair(identity, "action-result")["effect_performed"])

    def test_uncertified_remote_profile_cannot_be_granted_by_human_approval_alone(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            catalog = gov.policy()
            catalog["certificates"]["software_implementation"]["profiles"].remove("EXTERNAL_EXECUTE")
            path = Path(temporary) / "policy.json"; path.write_text(json.dumps(catalog))
            with patch.object(gov, "POLICY", path):
                case = self.remote(); plan = case.prepare_push(); identity = case.approve(plan)
                with self.assertRaises(RemoteGitRuntimeError): case.runtime.push(identity)
                self.assertEqual(case.phase_i.git("ls-remote", "--heads", "origin", "phase-6j-test").stdout.strip(), "")

    def test_policy_revocation_during_staging_blocks_target_apply(self):
        case = write_fixtures.ControlledWriteTests(); case.setUp()
        self.addCleanup(case.tearDown)
        catalog = gov.policy(); path = case.root / "policy.json"; path.write_text(json.dumps(catalog))
        def mutation(workspace):
            (workspace / "src" / "existing.txt").write_text("unauthorized")
            revoked = deepcopy(catalog); revoked["certificates"]["software_implementation"]["status"] = "revoked"
            path.write_text(json.dumps(revoked))
        with patch.object(gov, "POLICY", path):
            request = case.request()
            with self.assertRaises(TaskContractError):
                case.execute_controlled(write_fixtures.MutatingAdapter(mutation), request)
        self.assertEqual((case.target / "src" / "existing.txt").read_text(), "before\n")

    def test_governance_implementation_cannot_be_written_without_protected_opt_in(self):
        case = write_fixtures.ControlledWriteTests(); case.setUp()
        self.addCleanup(case.tearDown)
        adapter = write_fixtures.MutatingAdapter()
        scope = case.scope(project_root=str(write_fixtures.REPOSITORY_ROOT),
                           allowed_paths=["runtime/core/capability_actions.py"])
        result = case.execute_controlled(adapter, case.request(scope))
        self.assertEqual(result.provider_result.error_category, "protected_path_violation")
        self.assertEqual(adapter.workspaces, [])

    def test_known_git_failure_is_audited_without_retry_authority(self):
        case = self.local(); prepared = case.prepare(); identity = case.approve(prepared)
        hook = case.repository / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaises(GitRuntimeError): case.runtime.commit(identity)
        trace = FileExecutionStore(case.git_store.root)._decision_pair(prepared["approval"]["approval_id"], "action-failure")
        self.assertEqual(trace["result"]["status"], "FAILED")
        self.assertTrue(trace["result"]["effect_may_be_partial"])
        self.assertEqual(case.git("rev-parse", "HEAD").stdout.strip(), case.base_head)
