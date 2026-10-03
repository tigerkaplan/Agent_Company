"""Acceptance assertions for observed review attacks; failures are findings."""
import json,unittest
from pathlib import Path
observed={r['probe']:r for r in json.loads(Path(__file__).with_name('adversarial-results.json').read_text())}
class ReviewAcceptance(unittest.TestCase):
 def test_imported_observation_cannot_authorize_completion(self):
  r=observed['imported_execution_without_intent']
  self.assertNotEqual(r.get('actual_job_status'),'completed',r)
 def test_unobserved_review_cannot_enable_completed_git_work(self):
  r=observed['unobserved_review_to_completed_job_to_git_action']
  self.assertFalse(r.get('commit_created'),r)
 def test_missing_effect_evidence_must_deny_target_apply(self):
  r=observed['delete_effect_trace_before_apply']
  self.assertEqual(r.get('target_contents','before\n'),'before\n',r)
 def test_single_journal_rollback_cannot_refund_work(self):
  r=observed['single_journal_rollback_new_execution_id']
  self.assertFalse(r.get('second_dispatch_accepted'),r)
if __name__=='__main__':unittest.main(verbosity=2)
