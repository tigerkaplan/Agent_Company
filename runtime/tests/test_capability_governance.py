"""GOV-02 adversarial coverage at canonical runtime and durable stores."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from runtime.core import capability_governance as gov
from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.core.task_contract import TaskContractError, encoded
from runtime.execution.models import ExecutionRequest
from runtime.storage.execution_store import ExecutionStoreError
from runtime.tests import test_task_contract as fixtures
from runtime.workers.worker import Worker


class CapabilityGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TaskContractTests()
        self.fixture.setUp()
        self.runtime = self.fixture.runtime
        self.root = self.fixture.root
        self.store = self.fixture.executions

    def tearDown(self):
        self.fixture.tearDown()

    def test_worker_certification_provenance_and_complete_trace(self):
        job, outcome = self.fixture.run_job()
        self.assertEqual(outcome.status, "completed")
        anchor = json.loads(self.runtime.task_contract_store._path(job["job_id"], "anchor").read_bytes())
        self.assertEqual(anchor["schema_version"], 3)
        self.assertEqual(anchor["governance"]["profile"], "READ_ONLY")
        intent = self.store._decision_pair(outcome.execution_id, "intent")
        self.assertEqual(intent["requested_action"], "EXECUTE")
        self.assertEqual(intent["request"]["job_id"], job["job_id"])
        self.assertTrue(intent["policy_evaluation"]["policy_sources"])
        self.assertEqual(intent["approval_received"], {})
        self.assertIn("LocalExecutor", intent["executor"])
        self.assertIsNotNone(self.store._decision_pair(outcome.execution_id, "result")["intent_digest"])
        self.store.load(outcome.execution_id)

    def test_uncertified_capability_is_rejected_at_admission(self):
        p = self.fixture.payload(capability="unregistered")
        with self.assertRaises(RuntimeError):
            self.runtime.create(p)

    def test_extra_uncertified_allowed_capability_cannot_hide_in_contract(self):
        p = self.fixture.payload(); p["task_contract"]["allowed_capabilities"].append("unregistered")
        with self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_profile_escalation_and_understated_effects_rejected(self):
        for profile in ("LOCAL_WRITE", "EXTERNAL_EXECUTE", "SENSITIVE_EXECUTE", "EXTERNAL_PREPARE"):
            p = self.fixture.payload(); p["task_contract"]["capability_profile"] = profile
            with self.subTest(profile=profile), self.assertRaises(RuntimeError):
                self.runtime.create(p)

    def test_read_profile_blast_and_reversibility_bypass_rejected(self):
        for field, value in (("blast_radius", "local"), ("reversibility", "reversible")):
            p = self.fixture.payload(); p["task_contract"][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError): self.runtime.create(p)

    def test_certificate_revocation_and_tampering_fail_on_restart(self):
        original = gov.policy()
        path = self.root / "policy.json"
        path.write_text(json.dumps(original))
        with patch.object(gov, "POLICY", path):
            job = self.runtime.create(self.fixture.payload())
            for mutation in ("revoked", "identity", "extra"):
                changed = deepcopy(original)
                cert = changed["certificates"][job["capability"]]
                if mutation == "revoked": cert["status"] = "revoked"
                elif mutation == "identity": cert["certificate_id"] = "model-authorized"
                else: changed["extra"] = "advice"
                path.write_text(json.dumps(changed))
                with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                    JobRuntime(self.root / "jobs", clock=self.runtime.clock).show(job["job_id"])
            path.write_text(json.dumps(original))
            self.runtime.show(job["job_id"])

    def test_missing_policy_cannot_be_replaced_by_model_signal(self):
        with patch.object(gov, "POLICY", self.root / "missing"):
            with self.assertRaises(RuntimeError): self.runtime.create(self.fixture.payload())

    def test_coherent_provenance_pair_tampering_conflicts_with_policy(self):
        job = self.runtime.create(self.fixture.payload())
        for suffix in ("anchor", "witness"):
            path = self.runtime.task_contract_store._path(job["job_id"], suffix)
            value = json.loads(path.read_bytes()); value["governance"]["policy_digest"] = "0" * 64
            path.write_bytes(encoded(value, max_bytes=512 * 1024))
        with self.assertRaises(RuntimeError): self.runtime.show(job["job_id"])

    def test_historical_authority_requires_recovery_without_migration(self):
        job = self.runtime.create(self.fixture.payload())
        for suffix in ("anchor", "witness"):
            path = self.runtime.task_contract_store._path(job["job_id"], suffix)
            value = json.loads(path.read_bytes()); value.pop("governance"); value["schema_version"] = 2
            path.write_bytes(encoded(value, max_bytes=512 * 1024))
        before = self.runtime.task_contract_store._path(job["job_id"], "anchor").read_bytes()
        with self.assertRaises(RuntimeError): self.runtime.show(job["job_id"])
        self.assertEqual(before, self.runtime.task_contract_store._path(job["job_id"], "anchor").read_bytes())

    def test_child_capability_tools_and_gate_escalation_denied(self):
        parent = self.runtime.create(self.fixture.payload())
        for mutation in ("capability", "tool", "level", "gate", "scope", "risk", "stop"):
            p = deepcopy(parent); child = deepcopy(parent); c = child["task_contract"]
            if mutation == "capability": c["allowed_capabilities"].append("planning")
            elif mutation == "tool": p["task_contract"]["allowed_tools"] = ["local_executor"]
            elif mutation == "level": c["delegation_level"] = "L3"
            elif mutation == "gate": p["task_contract"]["approval_requirements"]["execution"] = True
            elif mutation == "scope": c["write_scope"] = {"write_mode": "CREATE_MODIFY"}
            elif mutation == "risk": c["risk"] = "medium"
            else: c["stop_conditions"] = []
            with self.subTest(mutation=mutation), self.assertRaises(TaskContractError): gov.require_child(p, child)

    def prepared(self):
        job = self.runtime.create(self.fixture.payload())
        self.runtime.enqueue(job["job_id"])
        job = self.runtime.claim(claimed_by=self.fixture.worker.worker_id)
        request = Worker._build_request(job, "gov02-execution", ())
        return job, request

    def begin(self, job, request):
        return self.store.begin_decision(request, executor="trusted-fixture", runtime=self.runtime, job=job)

    def test_replayed_intent_denied_after_restart(self):
        job, request = self.prepared(); self.begin(job, request)
        self.runtime = JobRuntime(self.root / "jobs", clock=self.runtime.clock)
        with self.assertRaisesRegex(ExecutionStoreError, "consumed"): self.begin(job, request)

    def test_deleted_intent_pairs_do_not_refund_dispatch_authority(self):
        job, request = self.prepared(); self.begin(job, request)
        for suffix in ("anchor", "witness"):
            self.store._decision_path(request.execution_id, "intent", suffix).unlink()
        with self.assertRaises(ExecutionStoreError): self.begin(job, request)

    def test_crash_after_observation_holds_execution(self):
        job, request = self.prepared()
        with patch.object(self.store, "_decision_pair", side_effect=ExecutionStoreError("crash")):
            with self.assertRaises(ExecutionStoreError): self.begin(job, request)
        with self.assertRaises(ExecutionStoreError): self.begin(job, request)

    def test_exact_work_substitution_denied_before_dispatch(self):
        job, request = self.prepared()
        data = request.to_dict(); data["task"] = "different"; data["task_contract"]["objective"] = "different"
        request = ExecutionRequest.from_persisted_dict(data)
        with self.assertRaises(ExecutionStoreError): self.begin(job, request)

    def test_self_approval_has_no_canonical_human_artifact(self):
        job, request = self.prepared()
        job["approval_status"] = "approved"
        self.runtime.store.save(job)
        data = request.to_dict(); data["approval_status"] = "approved"
        request = ExecutionRequest.from_persisted_dict(data)
        with self.assertRaises(ExecutionStoreError): self.begin(job, request)

    def test_trace_pair_tampering_and_missing_result_fail_closed(self):
        job, outcome = self.fixture.run_job()
        path = self.store._decision_path(outcome.execution_id, "result", "anchor")
        original = path.read_bytes(); value = json.loads(original); value["request_digest"] = "0" * 64
        path.write_bytes(encoded(value))
        with self.assertRaises(ExecutionStoreError): self.store.load(outcome.execution_id)
        path.write_bytes(original); path.unlink()
        with self.assertRaises(ExecutionStoreError): self.store.load(outcome.execution_id)

    def test_coherent_intent_tamper_conflicts_with_independent_journal(self):
        _, outcome = self.fixture.run_job()
        value = self.store._decision_pair(outcome.execution_id, "intent")
        value["executor"] = "self-authorized-provider"
        from runtime.core.task_contract import digest
        for suffix in ("anchor", "witness"):
            self.store._decision_path(outcome.execution_id, "intent", suffix).write_bytes(encoded(value, max_bytes=512 * 1024))
            result = self.store._decision_pair(outcome.execution_id, "result") if suffix == "anchor" else result
            result["intent_digest"] = digest(value)
            self.store._decision_path(outcome.execution_id, "result", suffix).write_bytes(encoded(result))
        with self.assertRaises(ExecutionStoreError): self.store.load(outcome.execution_id)

    def test_direct_executor_rejects_uncertified_capability(self):
        job, request = self.prepared()
        data = request.to_dict(); data["capability"] = "fake"; data["task_contract"]["allowed_capabilities"] = ["fake"]
        request = ExecutionRequest.from_persisted_dict(data)
        with self.assertRaises(TaskContractError): self.fixture.worker.executor.execute(request)

    def test_dispatch_context_is_not_reenterable_after_restart(self):
        job, request = self.prepared(); self.begin(job, request)
        with gov.certified_dispatch(self.store, request):
            self.fixture.worker.executor.execute(request)
        with self.assertRaises(ExecutionStoreError):
            with gov.certified_dispatch(self.store, request): pass

    def test_effect_authority_cannot_be_issued_by_model_or_executor(self):
        job, request = self.prepared()
        data = request.to_dict()
        data["risk_level"] = "approval_required"
        data["approval_status"] = "approved"
        data["task_contract"]["risk"] = "approval_required"
        data["task_contract"]["approval_requirements"]["execution"] = True
        forged = ExecutionRequest.from_persisted_dict(data)
        with self.assertRaisesRegex(TaskContractError, "certified dispatch"):
            self.fixture.worker.executor.execute(forged)

    def test_request_substitution_inside_certified_dispatch_is_rejected(self):
        job, request = self.prepared(); self.begin(job, request)
        data = request.to_dict(); data["task"] = "changed"; data["task_contract"]["objective"] = "changed"
        forged = ExecutionRequest.from_persisted_dict(data)
        with gov.certified_dispatch(self.store, request):
            with self.assertRaises(TaskContractError): self.fixture.worker.executor.execute(forged)

    def test_coherent_result_and_trace_replacement_conflicts_with_journal(self):
        _, outcome = self.fixture.run_job()
        from runtime.core.task_contract import digest
        raw = self.store.load_raw(outcome.execution_id)
        raw["result"]["summary"] = "Replayed different result"
        self.store._path(outcome.execution_id).write_text(json.dumps(raw))
        trace = self.store._decision_pair(outcome.execution_id, "result")
        trace["result_digest"] = digest(raw["result"])
        for suffix in ("anchor", "witness"):
            self.store._decision_path(outcome.execution_id, "result", suffix).write_bytes(encoded(trace))
        with self.assertRaises(ExecutionStoreError): self.store.load(outcome.execution_id)

    def test_partial_dispatch_write_does_not_refund_authority(self):
        job, request = self.prepared(); self.begin(job, request)
        self.store._decision_path(request.execution_id, "dispatch-execute", "witness").write_bytes(b"{}")
        with self.assertRaises(ExecutionStoreError):
            with gov.certified_dispatch(self.store, request): pass

    def test_stale_deadline_denies_actual_executor_inside_dispatch(self):
        p = self.fixture.payload()
        p["task_contract"]["stop_conditions"].append({"kind": "deadline", "at": "2020-01-01T00:00:00Z"})
        job = self.runtime.create(p)
        request = Worker._build_request(job, "stale-execution", ())
        with self.assertRaisesRegex(TaskContractError, "stale"):
            self.fixture.worker.executor.execute(request)

    def test_certificate_primitive_types_and_duplicate_fields_fail_closed(self):
        path = self.root / "bad-policy"
        for raw in ('{"schema_version":1,"schema_version":1}',
                    json.dumps({**gov.policy(), "schema_version": True}),
                    json.dumps({**gov.policy(), "certificates": []})):
            path.write_text(raw)
            with patch.object(gov, "POLICY", path), self.assertRaises(TaskContractError): gov.policy()

    def test_native_provider_advice_does_not_certify_tools(self):
        from runtime.core.task_contract import require_provider_tool_confinement
        job, request = self.prepared()
        class Advisor:
            native_tools = {"write"}
            approved = True
            certificate = "SENSITIVE_EXECUTE"
        with self.assertRaises(TaskContractError): require_provider_tool_confinement(request, Advisor())

    def test_governance_policy_change_invalidates_pending_and_completed_tasks(self):
        policy = gov.policy(); path = self.root / "policy-change.json"
        path.write_text(json.dumps(policy))
        with patch.object(gov, "POLICY", path):
            pending = self.runtime.create(self.fixture.payload())
            completed, outcome = self.fixture.run_job()
            changed = deepcopy(policy)
            changed["certificates"]["planning"]["profiles"] = ["READ_ONLY"]
            path.write_text(json.dumps(changed))
            for job in (pending, completed):
                with self.assertRaises(RuntimeError): self.runtime.show(job["job_id"])
            with self.assertRaises(ExecutionStoreError): self.store.load(outcome.execution_id)

    def test_deleted_dispatch_pair_does_not_refund_dispatch(self):
        job, request = self.prepared(); self.begin(job, request)
        with gov.certified_dispatch(self.store, request): pass
        for suffix in ("anchor", "witness"):
            self.store._decision_path(request.execution_id, "dispatch-execute", suffix).unlink()
        with self.assertRaises(ExecutionStoreError):
            with gov.certified_dispatch(self.store, request): pass

    def test_review_context_cannot_replay_parent_executor(self):
        job, request = self.prepared(); self.begin(job, request)
        with gov.certified_dispatch(self.store, request, purpose="review"):
            with self.assertRaisesRegex(TaskContractError, "Reviewer cannot replay"):
                self.fixture.worker.executor.execute(request)

    def test_deleted_effect_pair_does_not_refund_effect(self):
        job, request = self.prepared(); self.begin(job, request)
        with gov.certified_dispatch(self.store, request):
            gov.consume_effect(request, "fixture-effect")
            for suffix in ("anchor", "witness"):
                self.store._decision_path(request.execution_id, "effect-fixture-effect", suffix).unlink()
            with self.assertRaises(ExecutionStoreError): gov.consume_effect(request, "fixture-effect")

    def test_stale_loaded_policy_implementation_requires_restart(self):
        with patch.object(gov, "_IMPLEMENTATION_DIGEST", "0" * 64):
            with self.assertRaises(TaskContractError): gov.policy()

    def test_decision_stage_path_injection_is_rejected(self):
        for stage in ("../outside", "bad/path", "x" * 101):
            with self.assertRaises(ExecutionStoreError):
                self.store._decision_pair("safe-execution", stage, {"schema_version": 1})

    def test_missing_consumption_trace_invalidates_persisted_result(self):
        _, outcome = self.fixture.run_job()
        self.store._decision_path(outcome.execution_id, "dispatch-execute", "witness").unlink()
        with self.assertRaises(ExecutionStoreError): self.store.load(outcome.execution_id)

    def test_primary_reviewer_capability_cannot_certify_write_profile(self):
        parent = self.runtime.create(self.fixture.payload())
        candidate = deepcopy(parent)
        candidate["capability"] = "independent_review"
        c = candidate["task_contract"]
        c.update(allowed_capabilities=["independent_review"], capability_profile="LOCAL_WRITE",
                 delegation_level="L2", write_scope={"write_mode": "CREATE_OR_MODIFY"},
                 blast_radius="local", reversibility="reversible")
        c["approval_requirements"].update(execution=True, review=True)
        candidate["execution_mode"] = "CONTROLLED_WRITE"
        with self.assertRaisesRegex(TaskContractError, "Uncertified"): gov.evaluate(candidate)

    def test_trace_version_requires_exact_integer(self):
        for value in (True, 1.0, "1"):
            for suffix in ("anchor", "witness"):
                path = self.store._decision_path("version-test", "result", suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encoded({"schema_version": value}))
            with self.assertRaises(ExecutionStoreError): self.store._decision_pair("version-test", "result")

    def test_readonly_request_cannot_execute_without_persisted_provenance(self):
        _, request = self.prepared()
        with self.assertRaisesRegex(TaskContractError, "persisted certified dispatch"):
            gov.require_dispatch(request)

    def test_deleted_parent_authority_after_intent_denies_dispatch(self):
        job, request = self.prepared(); self.begin(job, request)
        self.runtime.task_contract_store._path(job["job_id"], "witness").unlink()
        with self.assertRaises(ExecutionStoreError):
            with gov.certified_dispatch(self.store, request): pass

    def test_review_child_identity_and_evidence_scope_cannot_widen(self):
        job = self.runtime.create(self.fixture.payload(review_required=True))
        self.runtime.enqueue(job["job_id"])
        job = self.runtime.claim(claimed_by=self.fixture.worker.worker_id)
        request = Worker._build_request(job, "review-scope-parent", ())
        self.begin(job, request)
        base = request.to_dict()
        base.update(execution_id="review-execution-fixture", agent="reviewer", skill="review",
            workflow="review", capability="independent_review", context_refs=[], input_refs=[])
        base["task_contract"].update(allowed_tools=["provider_call"],
            allowed_capabilities=["independent_review"], capability_profile="READ_ONLY", inputs=[])
        with gov.certified_dispatch(self.store, request, purpose="review"):
            gov.require_dispatch(ExecutionRequest.from_persisted_dict(base))
            for field, value in (("job_id", "other-job"), ("project_id", "other-project"),
                                 ("agent", "executor"),
                                 ("input_refs", [{"ref_type": "artifact", "ref": "private:unrelated"}])):
                child = deepcopy(base); child[field] = value
                if field == "input_refs": child["task_contract"]["inputs"] = value
                with self.subTest(field=field), self.assertRaises(TaskContractError):
                    gov.require_dispatch(ExecutionRequest.from_persisted_dict(child))

    def test_primary_review_task_cannot_replay_itself_through_review_dispatch(self):
        job = self.runtime.create(self.fixture.payload(capability="independent_review"))
        self.runtime.enqueue(job["job_id"])
        job = self.runtime.claim(claimed_by=self.fixture.worker.worker_id)
        request = Worker._build_request(job, "primary-review", ())
        self.begin(job, request)
        with gov.certified_dispatch(self.store, request, purpose="review"):
            with self.assertRaisesRegex(TaskContractError, "Reviewer cannot replay"):
                gov.require_dispatch(request)

    def test_task_provenance_cannot_replace_canonical_worker_claim(self):
        job = self.runtime.create(self.fixture.payload())
        request = Worker._build_request(job, "unclaimed-execution", ())
        with self.assertRaisesRegex(ExecutionStoreError, "canonical execution authority"):
            self.begin(job, request)
        self.assertFalse(self.store._decision_path(request.execution_id, "intent", "anchor").exists())

    def test_budget_provenance_cannot_replace_active_core_reservation(self):
        from runtime.budget.runtime import ExecutionBudgetRuntime
        job = self.runtime.create(self.fixture.payload(execution_budget={"max_execution_units": 1}))
        self.runtime.enqueue(job["job_id"])
        job = self.runtime.claim(claimed_by=self.fixture.worker.worker_id)
        request = Worker._build_request(job, "budget-bound-dispatch", ())
        with self.assertRaisesRegex(ExecutionStoreError, "claim/budget"):
            self.begin(job, request)
        budget = ExecutionBudgetRuntime(self.runtime.budget_store, wall_clock=self.runtime.clock)
        admitted = budget.reserve_execution(job["execution_budget"], execution_id=request.execution_id, job_id=job["job_id"])
        self.assertEqual(admitted.status, "ALLOW")
        self.begin(job, request)
        with gov.certified_dispatch(self.store, request):
            gov.require_dispatch(request)
            budget.finalize_execution(job["execution_budget"], execution_id=request.execution_id)
            with self.assertRaisesRegex(ExecutionStoreError, "claim/budget"):
                gov.require_dispatch(request)

    def test_verified_review_strengthening_preserves_original_decision_binding(self):
        job, request = self.prepared(); self.begin(job, request)
        with gov.certified_dispatch(self.store, request):
            result = self.fixture.worker.executor.execute(request)
        self.store.create(request, result)
        self.runtime.record_execution_for_review(job["job_id"], [{"ref_type": "artifact",
            "ref": "runtime-execution:" + request.execution_id}])
        self.store.load(request.execution_id)
        with gov.certified_dispatch(self.store, request, purpose="review"):
            gov.require_review_dispatch(request)
        current = self.runtime.store.load(job["job_id"])
        current["review_required"] = False
        self.runtime.store.save(current)
        with self.assertRaises(ExecutionStoreError): self.store.load(request.execution_id)

    def test_consumable_intent_cannot_dispatch_after_claim_is_lost(self):
        job, request = self.prepared(); self.begin(job, request)
        current = self.runtime.store.load(job["job_id"])
        current["claimed_by"] = "other-worker"
        self.runtime.store.save(current)
        with self.assertRaises(ExecutionStoreError):
            with gov.certified_dispatch(self.store, request): pass

    def test_new_execution_id_cannot_refund_consumed_job_attempt(self):
        from runtime.storage.execution_store import FileExecutionStore
        job, request = self.prepared(); self.begin(job, request)
        with gov.certified_dispatch(self.store, request):
            self.fixture.worker.executor.execute(request)
        changed = Worker._build_request(job, "invented-new-execution-id", ())
        for store in (self.store, FileExecutionStore(self.root / "alternate-executions")):
            with self.subTest(store=store.root), self.assertRaisesRegex(ExecutionStoreError, "job attempt already consumed"):
                store.begin_decision(changed, executor="attempted-refund", runtime=self.runtime, job=job)

    def test_concurrent_new_ids_admit_only_one_job_attempt_intent(self):
        from concurrent.futures import ThreadPoolExecutor
        job, _ = self.prepared()
        def admit(index):
            request = Worker._build_request(job, "concurrent-intent-" + str(index), ())
            try:
                self.begin(job, request)
                return True
            except ExecutionStoreError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(admit, range(2))), 1)

    def test_missing_work_consumption_observation_invalidates_intent(self):
        job, request = self.prepared(); intent = self.begin(job, request)
        with patch.object(type(self.store), "_intent_work_id", return_value="absent-work-generation"):
            with self.assertRaises(ExecutionStoreError): self.store._verify_intent(intent)

    def test_loaded_execution_policy_source_change_requires_restart(self):
        stale = deepcopy(gov._SOURCE_IMPLEMENTATION_DIGESTS)
        stale["runtime/storage/execution_store.py"] = "0" * 64
        with patch.object(gov, "_SOURCE_IMPLEMENTATION_DIGESTS", stale):
            with self.assertRaisesRegex(TaskContractError, "restart required"): gov.policy()

    def test_interrupted_intent_cannot_refund_work_under_new_execution_id(self):
        job, request = self.prepared()
        with patch.object(self.store, "_decision_pair", side_effect=ExecutionStoreError("interrupted pair")):
            with self.assertRaises(ExecutionStoreError): self.begin(job, request)
        restarted = JobRuntime(self.root / "jobs", clock=self.runtime.clock)
        changed = Worker._build_request(job, "new-id-after-crash", ())
        with self.assertRaisesRegex(ExecutionStoreError, "job attempt already consumed"):
            self.store.begin_decision(changed, executor="restart-attempt", runtime=restarted, job=job)

    def test_real_human_resumption_receipt_permits_one_new_generation_only(self):
        from runtime.tests.test_continuation import ContinuationTests, ResultExecutor
        case = ContinuationTests(); case.setUp()
        try:
            case.create_planned(case.step("STEP-001", "Step one"))
            worker = case.worker(ResultExecutor("needs_human"))
            first = worker.run_once()
            case.approvals.resolve(first.approval["approval_id"], decision="APPROVED", decided_by="owner")
            job = case.jobs.claim(claimed_by=worker.worker_id)
            request = Worker._build_request(job, "human-authorized-generation", worker.resolver.resolve(job))
            intent = case.executions.begin_decision(request, executor="human-resumption-test", runtime=case.jobs, job=job)
            self.assertTrue(any(r["requested_action"] == "RESOLVE_HUMAN_CONDITION"
                                for r in intent["approval_received"].values()))
            with gov.certified_dispatch(case.executions, request): gov.require_dispatch(request)
            changed = Worker._build_request(job, "reuse-human-receipt-with-new-id", request.context_refs)
            with self.assertRaisesRegex(ExecutionStoreError, "job attempt already consumed"):
                case.executions.begin_decision(changed, executor="replayed-receipt", runtime=case.jobs, job=job)
        finally:
            case.tearDown()
