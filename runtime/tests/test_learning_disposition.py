"""Real canonical local-store integration in isolated test fixtures."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import unittest

from runtime.approvals.models import ApprovalContractError, ApprovalRequest
from runtime.approvals.runtime import ApprovalRuntime
from runtime.core.capability_actions import ActionDecision
from runtime.core.task_contract import digest
from runtime.core.validation import JobValidator
from runtime.memory.learning import (
    ForegroundLearningInterface, LearningError, PlanningProjection,
    learning_fingerprint, learning_inspection,
)
from runtime.tests.test_memory_learning import LearningFixture
from runtime.tests.test_memory_readonly_inspection import no_persistent_mutations


class LearningDispositionTests(LearningFixture):
    def test_promote_requires_confirmation_and_does_not_change_completion(self):
        identity = self.approved()
        request = self.store.load(identity); job_before = self.jobs.show(request.job_id)
        self.assertNotIn("learning_scope", job_before.get("approval", {}))
        with self.assertRaises(ValueError): self.owner.inspect_learning()
        result = self.owner.apply_learning(identity)
        self.assertEqual(result["status"], "CONFIRMED")
        diagnostic = self.owner.check_learning(identity)
        self.assertTrue(diagnostic["confirmed"]); self.assertTrue(diagnostic["current_eligible"])
        self.assertFalse(diagnostic["planning_hold"])
        self.assertEqual(self.jobs.show(request.job_id), job_before)
        state = self.owner.inspect_learning()
        self.assertEqual(state["index"]["revision"], 1)
        self.assertEqual(len(state["eligible"]), 1)
        self.assertEqual(self.memory.get("alpha", "positive-candidate").trust, "untrusted")
        self.assertEqual(self.memory.get("alpha", "positive-candidate").authority, "none")

    def test_canonical_learning_approval_schema_and_compact_denial(self):
        identity = self.approved(); request = self.store.load(identity)
        JobValidator(Path(__file__).resolve().parents[2] / "schemas/approval.schema.json").validate(request.to_dict())
        with self.assertRaises(ApprovalContractError): request.compact()
        with self.assertRaises(ValueError):
            replace(request, learning_scope={**request.learning_scope, "extra": True})

    def test_single_use_and_no_separate_consumption_entry(self):
        identity = self.promote()
        with self.assertRaises(ValueError): self.owner.apply_learning(identity)
        request = self.store.load(identity)
        with self.assertRaises(ValueError):
            ActionDecision(self.jobs, self.store, self.executions, request.to_dict(), request.learning_scope, "caller")

    def test_supersession_is_one_revision_and_never_restores_predecessor(self):
        self.promote(); prior = self.head()
        value = self.intent(operation="SUPERSEDE", version=1, constraint_id="constraint-two", predecessor=prior)
        identity = self.approved(value); self.owner.apply_learning(identity)
        state = self.owner.inspect_learning()
        self.assertEqual(state["index"]["heads"]["constraint-one"]["state"], "SUPERSEDED")
        self.assertEqual(state["index"]["heads"]["constraint-two"]["state"], "PROMOTED")
        withdrawal = self.intent(operation="REVOKE", version=2, constraint_id="withdrawal", predecessor=self.head("constraint-two"))
        identity = self.approved(withdrawal); self.owner.apply_learning(identity)
        state = self.owner.inspect_learning()
        self.assertEqual(state["eligible"], [])
        self.assertEqual(state["index"]["heads"]["constraint-one"]["state"], "SUPERSEDED")

    def test_revocation_with_unavailable_original_positive_evidence(self):
        original = self.promote(); prior = self.head()
        negative = self.add_evidence("withdrawal")
        (self.project / "positive.txt").unlink()
        self.memory.records.pop(("alpha", "positive-candidate"))
        value = self.intent(operation="REVOKE", version=1, constraint_id="withdrawal", predecessor=prior, evidence=negative)
        identity = self.approved(value); self.owner.apply_learning(identity)
        self.assertEqual(self.owner.inspect_learning()["eligible"], [])
        diagnostic = self.owner.check_learning(original)
        self.assertTrue(diagnostic["confirmed"]); self.assertFalse(diagnostic["current_eligible"])
        self.assertFalse(diagnostic["planning_hold"])

    def test_revoked_version_needs_new_version_and_fresh_approval(self):
        self.promote()
        identity = self.approved(self.intent(operation="REVOKE", constraint_id="withdrawal", predecessor=self.head()))
        self.owner.apply_learning(identity)
        with self.assertRaises(ValueError): self.approved(self.intent(version=1))
        identity = self.approved(self.intent(version=2)); self.owner.apply_learning(identity)
        self.assertEqual(self.owner.inspect_learning()["eligible"][0]["proposal"]["version"], 2)

    def test_rejected_request_preserves_rationale_and_allows_fresh_request(self):
        scope = self.prepared_scope()
        pending = self.owner.request_learning_disposition(scope, reason="First request")
        self.owner.resolve(pending.request.approval_id, decision="REJECTED", decided_by="fixture-operator", reason="Evidence inadequate")
        with self.assertRaises(ValueError): self.owner.apply_learning(pending.request.approval_id)
        fresh = self.approved(self.intent(version=2)); self.owner.apply_learning(fresh)
        self.assertEqual(self.store.load(pending.request.approval_id).decision_reason, "Evidence inadequate")

    def test_completion_needs_human_cannot_substitute_for_pass_review(self):
        job, path = self.prepare(review_decision="NEEDS_HUMAN")
        self.assertEqual(self.jobs.show(job)["status"], "completed")
        with self.assertRaises(LearningError): self.owner.prepare_learning_scope(job, path)

    def test_incomplete_review_coverage_is_denied(self):
        job, path = self.prepare(coverage=False)
        with self.assertRaises(LearningError): self.owner.prepare_learning_scope(job, path)

    def test_exact_output_evidence_root_and_index_substitutions(self):
        scope = self.prepared_scope()
        for key in ("completion_digest", "execution_digest", "output_digest", "contract_digest"):
            substituted = deepcopy(scope); substituted["preparation"][key] = "0" * 64
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.owner.request_learning_disposition(substituted, reason="Substitution")
        for field in ("review_id", "digest", "reviewer"):
            substituted = deepcopy(scope); substituted["review"][field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.owner.request_learning_disposition(substituted, reason="Substitution")
        changed = deepcopy(scope); changed["intent"]["expected_index_digest"] = "0" * 64
        with self.assertRaises(ValueError): self.owner.request_learning_disposition(changed, reason="Substitution")
        changed = deepcopy(scope); changed["intent"]["genesis"]["owners"]["memory_source"] = "caller-selected"
        with self.assertRaises(ValueError): self.owner.request_learning_disposition(changed, reason="Substitution")

    def test_source_staleness_blocks_resolution_and_application(self):
        scope = self.prepared_scope(); pending = self.owner.request_learning_disposition(scope, reason="Exact evidence")
        (self.project / "positive.txt").write_text("changed")
        with self.assertRaises(ValueError):
            self.owner.resolve(pending.request.approval_id, decision="APPROVED", decided_by="fixture-operator")
        with self.assertRaises(ValueError): self.owner.apply_learning(pending.request.approval_id)

    def test_concurrent_requests_have_one_reserved_winner(self):
        scope = self.prepared_scope()
        def attempt():
            try:
                return self.owner.request_learning_disposition(scope, reason="Concurrent exact request").request.approval_id
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_concurrent_application_has_one_effect(self):
        identity = self.approved()
        def attempt():
            try: return self.owner.apply_learning(identity)
            except (ValueError, OSError): return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(self.owner.inspect_learning()["index"]["revision"], 1)

    def test_planning_selection_is_exact_and_revalidated_after_revocation(self):
        self.promote(); manager = ForegroundLearningInterface(self.owner)
        request = self.planning_request(); projection = manager.select(request)
        self.assertEqual(len(projection.to_dict()["constraints"]), 1)
        self.assertEqual(manager.revalidate(request, projection), projection)
        self.assertEqual(manager.select(self.planning_request(task="other-task")).to_dict()["constraints"], [])
        with self.assertRaises(LearningError): manager.select(self.planning_request(project_id="foreign"))
        identity = self.approved(self.intent(operation="REVOKE", constraint_id="withdrawal", predecessor=self.head()))
        self.owner.apply_learning(identity)
        with self.assertRaises(LearningError): manager.revalidate(request, projection)

    def test_planning_evidence_change_holds_use_without_fabricating_revocation(self):
        identity = self.promote(); manager = ForegroundLearningInterface(self.owner)
        request = self.planning_request(); projection = manager.select(request)
        (self.project / "positive.txt").write_text("changed")
        with self.assertRaises(ValueError): manager.revalidate(request, projection)
        with no_persistent_mutations(self, self.root):
            diagnostic = self.owner.check_learning(identity)
            self.assertTrue(diagnostic["confirmed"]); self.assertFalse(diagnostic["current_eligible"])
            self.assertTrue(diagnostic["planning_hold"])
        with learning_inspection():
            self.assertEqual(self.owner._learning_state()["heads"]["constraint-one"]["state"], "PROMOTED")

    def test_overlap_denied_but_disjoint_scopes_allowed(self):
        self.promote()
        with self.assertRaises(LearningError): self.prepared_scope(self.intent(constraint_id="conflict"))
        identity = self.approved(self.intent(constraint_id="disjoint", task="plan-other"))
        self.owner.apply_learning(identity)
        self.assertEqual(len(self.owner.inspect_learning()["eligible"]), 2)

    def test_inspection_and_reconciliation_create_no_locks_or_persistent_writes(self):
        identity = self.promote(); manager = ForegroundLearningInterface(self.owner)
        with no_persistent_mutations(self, self.root):
            self.assertTrue(self.owner.check_learning(identity)["confirmed"])
            request = self.planning_request(); projection = manager.select(request)
            manager.revalidate(request, projection)

    def test_review_checks_cannot_substitute_for_missing_packaged_bodies(self):
        job, path = self.prepare(package_bodies=False)
        self.assertEqual(self.jobs.show(job)["status"], "completed")
        with self.assertRaisesRegex(LearningError, "actual packaged learning evidence"):
            self.owner.prepare_learning_scope(job, path)
        self.assertEqual(self.store.list(), [])

    def test_historical_confirmation_survives_missing_or_expired_positive_evidence(self):
        identity = self.promote(); path = self.project / "positive.txt"; original = path.read_bytes()
        path.unlink()
        with no_persistent_mutations(self, self.root):
            diagnostic = self.owner.check_learning(identity)
            self.assertTrue(diagnostic["confirmed"]); self.assertFalse(diagnostic["current_eligible"])
            self.assertTrue(diagnostic["planning_hold"])
        path.write_bytes(original)
        self.owner.clock = lambda: "2031-01-01T00:00:00Z"
        with no_persistent_mutations(self, self.root):
            diagnostic = self.owner.check_learning(identity)
            self.assertTrue(diagnostic["confirmed"]); self.assertFalse(diagnostic["current_eligible"])
            self.assertTrue(diagnostic["planning_hold"])

    def test_default_runtime_remains_uninstalled(self):
        plain = ApprovalRuntime(self.jobs, self.store, execution_store=self.executions, review_store=self.reviews)
        self.assertIsNone(plain.learning)
        with self.assertRaises(LearningError): plain.inspect_learning()


if __name__ == "__main__": unittest.main()
