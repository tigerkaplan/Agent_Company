"""Crash/rollback vetoes and read-only restart recognition, never repair/replay."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from runtime.approvals.runtime import ApprovalRuntime
from runtime.core.capability_actions import ActionDecision
from runtime.core.task_contract import digest
from runtime.memory.learning import encoded, learning_inspection
from runtime.tests.test_memory_learning import LearningFixture
from runtime.tests.test_memory_readonly_inspection import no_persistent_mutations


class LearningRecoveryTests(LearningFixture):
    def restart(self):
        return ApprovalRuntime(self.jobs, self.store, execution_store=self.executions,
            review_store=self.reviews, clock=self.clock, learning=self.install)

    def test_missing_genesis_never_means_zero_revision(self):
        with no_persistent_mutations(self, self.root), self.assertRaises(ValueError):
            self.owner.inspect_learning()

    def test_confirmed_restart_is_read_only_recognition(self):
        identity = self.promote(); restarted = self.restart()
        with no_persistent_mutations(self, self.root):
            diagnostic = restarted.check_learning(identity)
            self.assertTrue(diagnostic["confirmed"]); self.assertTrue(diagnostic["current_eligible"])
            self.assertFalse(diagnostic["planning_hold"])
            self.assertEqual(len(restarted.inspect_learning()["eligible"]), 1)

    def test_failures_at_each_persistence_boundary_hold_planning_and_replay(self):
        # Fresh fixtures exercise failures before/after every application stage.
        for stage in ("transition", "consume", "transition-observation", "genesis", "index", "result", "application-observation", "reservation-close"):
            with self.subTest(stage=stage):
                case = LearningFixture(); case.setUp()
                try:
                    identity = case.approved()
                    original_write = case.store._write_learning
                    original_observe = case.owner._learning_observe
                    def fail_write(project, name, value, **kwargs):
                        if (stage == "transition" and name.startswith("transition-") or stage == "genesis" and name == "genesis"
                                or stage == "index" and name == "index" or stage == "reservation-close" and name == "reservation"):
                            raise OSError("Injected fixture write interruption")
                        return original_write(project, name, value, **kwargs)
                    def fail_observe(kind, *args):
                        if (stage == "transition-observation" and kind == "learning_transition_observed"
                                or stage == "application-observation" and kind == "learning_application_observed"):
                            raise OSError("Injected fixture observation interruption")
                        return original_observe(kind, *args)
                    with patch.object(case.store, "_write_learning", side_effect=fail_write), \
                         patch.object(case.owner, "_learning_observe", side_effect=fail_observe):
                        if stage == "consume":
                            with patch.object(ActionDecision, "_consume_locked", side_effect=OSError("Before consumption")):
                                with self.assertRaises(OSError): case.owner.apply_learning(identity)
                        elif stage == "result":
                            with patch.object(ActionDecision, "finish", side_effect=OSError("Before confirmation")):
                                with self.assertRaises(OSError): case.owner.apply_learning(identity)
                        else:
                            with self.assertRaises(OSError): case.owner.apply_learning(identity)
                    with no_persistent_mutations(self, case.root):
                        self.assertTrue(case.owner.check_learning(identity)["planning_hold"])
                        with self.assertRaises(ValueError): case.owner.inspect_learning()
                    with self.assertRaises((ValueError, OSError)): case.owner.apply_learning(identity)
                finally:
                    case.doCleanups()

    def test_consumption_partial_pair_cannot_be_refunded(self):
        identity = self.approved()
        original = self.executions._decision_pair
        def interrupt(execution_id, stage, value=None):
            if stage == "action-effect" and value is not None:
                path = self.executions._decision_path(execution_id, stage, "witness")
                path.write_bytes(encoded(value))
                raise OSError("One consumption half survived")
            return original(execution_id, stage, value)
        # ActionDecision uses the same canonical root via its own store instance.
        original_class = type(self.executions)._decision_pair
        def class_interrupt(store, execution_id, stage, value=None):
            if stage == "action-effect" and value is not None:
                path = store._decision_path(execution_id, stage, "witness")
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(encoded(value))
                raise OSError("One consumption half survived")
            return original_class(store, execution_id, stage, value)
        with patch.object(type(self.executions), "_decision_pair", class_interrupt), self.assertRaises(OSError):
            self.owner.apply_learning(identity)
        with self.assertRaises(ValueError): self.owner.apply_learning(identity)
        self.assertTrue(self.owner.check_learning(identity)["planning_hold"])

    def test_missing_each_confirmed_pair_or_observation_denies_planning(self):
        identity = self.promote()
        for stage in ("action-policy", "action-effect", "action-result"):
            for suffix in ("anchor", "witness"):
                path = self.executions._decision_path(identity, stage, suffix); raw = path.read_bytes()
                path.unlink()
                try:
                    with no_persistent_mutations(self, self.root), self.assertRaises(ValueError): self.owner.inspect_learning()
                finally: path.write_bytes(raw)
        journal = self.jobs.progress.store.path("learning-journal"); backup = journal.read_bytes()
        journal.unlink()
        try:
            with self.assertRaises(ValueError): self.owner.inspect_learning()
        finally: journal.write_bytes(backup)

    def test_index_rollback_and_deleted_reservation_are_not_repaired(self):
        first = self.promote(); old = self.store._learning_path("alpha", "index").read_bytes()
        identity = self.approved(self.intent(operation="REVOKE", constraint_id="withdrawal", predecessor=self.head()))
        self.owner.apply_learning(identity)
        self.store._learning_path("alpha", "index").write_bytes(old)
        with no_persistent_mutations(self, self.root):
            self.assertTrue(self.owner.check_learning(identity)["planning_hold"])
            with self.assertRaises(ValueError): self.owner.inspect_learning()
        self.store._learning_path("alpha", "reservation").unlink()
        with self.assertRaises(ValueError): self.owner.apply_learning(first)

    def test_unconfirmed_supersession_exposes_neither_successor_nor_complete_replacement(self):
        self.promote()
        identity = self.approved(self.intent(operation="SUPERSEDE", constraint_id="successor", predecessor=self.head()))
        with patch.object(ActionDecision, "finish", side_effect=OSError("No result")), self.assertRaises(OSError):
            self.owner.apply_learning(identity)
        with self.assertRaises(ValueError): self.owner.inspect_learning()
        self.assertTrue(self.owner.check_learning(identity)["planning_hold"])


if __name__ == "__main__": unittest.main()
