"""Bounded bridge probes using canonical jobs, journals and evidence owners."""
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.store import FileApprovalStore
from runtime.core.task_contract import digest
from runtime.evals.store import FileEvalStore
from runtime.executors.local import LocalExecutor
from runtime.memory.action_trace import (
    ActionTraceError, ActionTraceOwners, ActionTraceRequest, EvidenceReference,
    build_action_candidates,
)
from runtime.memory.contracts import ClaimStatus, MemoryContractError
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.models import ProviderExecutionResult, ProviderSelection
from runtime.tests import test_task_contract as task_fixtures
from runtime.tests import test_review as review_fixtures
from runtime.tests.test_memory_readonly_inspection import no_persistent_mutations


def reference(kind, identity, value):
    return EvidenceReference(ref=kind + ":" + identity, sha256=digest(value))


class ActionTraceTests(unittest.TestCase):
    def fixture(self, cls=task_fixtures.TaskContractTests):
        fixture = cls()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        return fixture

    def completed(self, **overrides):
        fixture = self.fixture()
        _, outcome = fixture.run_job(fixture.payload(project_id="brightshore", **overrides))
        self.assertEqual(outcome.status, "completed")
        return fixture, fixture.runtime.store.load(outcome.job_id), outcome.execution_id

    def inputs(self, fixture, job, execution_id):
        runtime = fixture.runtime
        executions = getattr(fixture, "executions", None) or fixture.execution_store
        owners = ActionTraceOwners(jobs=runtime.store, tasks=runtime.task_contract_store,
            executions=executions, progress=runtime.progress.store,
            approvals=runtime.approval_store or FileApprovalStore(fixture.root / "approvals"),
            evaluations=FileEvalStore(fixture.root / "evals"),
            reviews=runtime.review_store,
            provider_outputs=getattr(runtime, "provider_artifact_store", None),
            mutation_outputs=getattr(runtime, "mutation_artifact_store", None))
        trace_id = runtime.progress.logical_id(job)
        trace = [event.to_dict() for event in owners.progress.read(trace_id)]
        execution = owners.executions.load(execution_id).to_dict()
        proof = job.get("task_completion")
        evaluation = reference("runtime-eval", proof["eval_id"],
            owners.evaluations.load(proof["eval_id"]).to_dict()) if proof else None
        reviews = [r["ref"].split(":", 1)[1] for r in job["output_refs"]
                   if r["ref"].startswith("runtime-review:")]
        review = reference("runtime-review", reviews[-1], owners.reviews.load(reviews[-1])) if reviews else None
        outputs = []
        for ref in job["output_refs"]:
            if ref["ref"].startswith("runtime-provider-output:"):
                identity = ref["ref"].split(":", 1)[1]
                outputs.append(reference("runtime-provider-output", identity, owners.provider_outputs.load(identity)))
        request = ActionTraceRequest(project_id=job["project_id"], job_id=job["job_id"],
            attempt=job["attempt"], execution=reference("runtime-execution", execution_id, execution),
            trace=reference("runtime-trace", trace_id, trace), evaluation=evaluation,
            review=review, outputs=tuple(outputs))
        return request, owners

    def build(self, fixture, request, owners, **kwargs):
        with no_persistent_mutations(self, fixture.root):
            return build_action_candidates(request, owners, **kwargs)

    def denied(self, fixture, request, owners):
        with no_persistent_mutations(self, fixture.root), self.assertRaises(ActionTraceError):
            build_action_candidates(request, owners)

    def test_exact_bindings_deterministic_replay_and_zero_writes(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        with no_persistent_mutations(self, fixture.root):
            with patch.object(Path, "glob", side_effect=AssertionError("Global scan")), \
                 patch.object(Path, "rglob", side_effect=AssertionError("Global scan")), \
                 patch.object(LocalExecutor, "execute", side_effect=AssertionError("Executor call")):
                first = build_action_candidates(request, owners)
                second = build_action_candidates(request, owners)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        observation, assertion = [json.loads(c.original.claim) for c in first]
        self.assertTrue(observation["gov_accepted"])
        self.assertEqual(observation["execution_status"], "succeeded")
        self.assertEqual(assertion["execution_result"], owners.executions.load(execution_id).result.to_dict())
        for candidate in first:
            self.assertEqual(candidate.original.status, ClaimStatus.REPORTED)
            self.assertIsNone(candidate.original.verification)
            self.assertEqual((candidate.original.trust, candidate.original.authority), ("untrusted", "none"))
            self.assertEqual((candidate.to_memory_record().trust, candidate.to_memory_record().authority),
                             ("untrusted", "none"))
            self.assertIsNone(candidate.decision)

    def test_project_job_attempt_trace_and_execution_substitutions(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        for field, value in (("project_id", "other"), ("job_id", "other"), ("attempt", 2),
                             ("execution", replace(request.execution, ref="runtime-execution:other")),
                             ("trace", replace(request.trace, ref="runtime-trace:other"))):
            with self.subTest(field=field):
                self.denied(fixture, replace(request, **{field: value}), owners)

    def test_every_selected_digest_is_checked(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        for field in ("execution", "trace", "evaluation"):
            with self.subTest(field=field):
                self.denied(fixture, replace(request, **{field: replace(getattr(request, field), sha256="0" * 64)}), owners)

    def test_missing_completion_evaluation_is_not_inferred(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        self.denied(fixture, replace(request, evaluation=None), owners)

    def test_missing_and_tampered_execution_evidence(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        path = owners.executions._path(execution_id)
        original = path.read_bytes()
        for attack in ("missing", "tampered", "witness"):
            with self.subTest(attack=attack):
                if attack == "missing":
                    path.unlink()
                elif attack == "tampered":
                    value = json.loads(original)
                    value["result"]["summary"] = "replacement"
                    path.write_text(json.dumps(value))
                else:
                    owners.executions._decision_path(execution_id, "result", "witness").write_text("{}")
                self.denied(fixture, request, owners)
                path.write_bytes(original)

    def test_missing_and_tampered_completion_receipt(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        path = owners.tasks._path(job["job_id"], "completion-witness")
        original = path.read_bytes()
        path.unlink()
        self.denied(fixture, request, owners)
        path.write_bytes(original)
        value = json.loads(original)
        value["proof"]["execution_id"] = "other"
        path.write_text(json.dumps(value))
        self.denied(fixture, request, owners)

    def test_tampered_eval_and_job_proof(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        path = owners.evaluations._path(request.evaluation.identity)
        value = json.loads(path.read_bytes())
        value["warnings"].append("replacement warning")
        path.write_text(json.dumps(value))
        self.denied(fixture, request, owners)

    def test_dry_run_is_retained_and_does_not_assert_effects(self):
        fixture, job, execution_id = self.completed(dry_run=True)
        request, owners = self.inputs(fixture, job, execution_id)
        candidates = self.build(fixture, request, owners)
        for candidate in candidates:
            body = json.loads(candidate.original.claim)
            self.assertTrue(body["dry_run"])
            self.assertNotIn("action_effects_verified", body)
        self.assertIn("no assertion of real-world effects", candidates[0].original.claim)

    def test_executor_success_without_declared_acceptance_is_observation(self):
        fixture = self.fixture()
        payload = fixture.payload(project_id="brightshore")
        payload.pop("task_contract")
        _, outcome = fixture.run_job(payload)
        job = fixture.runtime.store.load(outcome.job_id)
        request, owners = self.inputs(fixture, job, outcome.execution_id)
        observed = json.loads(self.build(fixture, request, owners)[0].original.claim)
        self.assertEqual(observed["execution_status"], "succeeded")
        self.assertFalse(observed["gov_accepted"])

    def test_failed_action_retains_error_failed_evidence_and_retry_assertion(self):
        fixture = self.fixture()
        fixture.worker.executor = LocalExecutor("failure", clock=fixture.runtime.clock)
        _, outcome = fixture.run_job(fixture.payload(project_id="brightshore", max_attempts=1))
        job = fixture.runtime.store.load(outcome.job_id)
        request, owners = self.inputs(fixture, job, outcome.execution_id)
        observed, reported = [json.loads(c.original.claim) for c in self.build(fixture, request, owners)]
        self.assertFalse(observed["gov_accepted"])
        self.assertEqual(reported["execution_result"]["error"]["code"], "local_executor_failure")
        self.assertEqual(reported["execution_result"]["evidence"][0]["status"], "failed")
        self.assertEqual(reported["execution_result"]["next_actions"][0]["action"], "retry_execution")

    def reviewed(self, decision):
        fixture = self.fixture(review_fixtures.WorkerReviewTests)
        original = fixture.payload
        fixture.payload = lambda **kwargs: original(project_id="brightshore", **kwargs)
        created, outcome, _ = fixture.run_worker_decision(decision, max_attempts=1)
        return fixture, fixture.runtime.store.load(created["job_id"]), outcome.execution_id

    def test_review_pass_requires_exact_review_completion_binding(self):
        fixture, job, execution_id = self.reviewed("PASS")
        self.assertEqual(job["status"], "completed")
        request, owners = self.inputs(fixture, job, execution_id)
        candidates = self.build(fixture, request, owners)
        self.assertTrue(json.loads(candidates[0].original.claim)["completion_verified"])
        self.denied(fixture, replace(request, review=None), owners)
        self.denied(fixture, replace(request, review=replace(request.review, sha256="0" * 64)), owners)

    def test_incomplete_and_failed_review_preserve_counterevidence(self):
        for decision in ("FAIL", "NEEDS_HUMAN"):
            with self.subTest(decision=decision):
                fixture, job, execution_id = self.reviewed(decision)
                request, owners = self.inputs(fixture, job, execution_id)
                candidates = self.build(fixture, request, owners)
                observation, assertions = [json.loads(c.original.claim) for c in candidates]
                self.assertFalse(observation["gov_accepted"])
                self.assertEqual(assertions["review_record"]["result"]["decision"], decision)
                self.assertTrue(assertions["review_record"]["result"]["deterministic_checks"])
                self.denied(fixture, replace(request, review=None), owners)

    def test_noncanonical_owners_fail_before_any_read(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        with patch("runtime.memory.action_trace.inspection_read", side_effect=AssertionError("Unexpected IO")):
            for field in ("jobs", "executions", "progress", "evaluations", "reviews"):
                with self.subTest(field=field), self.assertRaises(ActionTraceError):
                    build_action_candidates(request, replace(owners, **{field: object()}))

    def test_owner_redirection_is_denied_before_outside_read(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        path = owners.executions._decision_path(execution_id, "intent", "anchor")
        value = json.loads(path.read_bytes())
        value["authority_source"]["job_store_root"] = str(fixture.root / "outside")
        for suffix in ("anchor", "witness"):
            owners.executions._decision_path(execution_id, "intent", suffix).write_text(
                json.dumps(value, sort_keys=True, separators=(",", ":")))
        self.denied(fixture, request, owners)

    def test_completion_owner_redirection_is_denied(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        job["task_completion"]["execution_store_root"] = str(fixture.root / "outside")
        fixture.runtime.store.save(job)
        self.denied(fixture, request, owners)

    def test_missing_trace_and_unsupported_legacy_journal_fail_without_repair(self):
        from runtime.tests.test_memory_readonly_inspection import legacy_schema
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        path = owners.progress.path(request.trace.identity)
        original = path.read_bytes()
        path.unlink()
        self.denied(fixture, request, owners)
        path.write_bytes(original)
        legacy_schema(path, 1)
        self.denied(fixture, request, owners)

    def test_graph_bound_inspection_fails_closed(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        job["graph_plan"] = {}
        fixture.runtime.store.save(job)
        self.denied(fixture, request, owners)

    def test_request_and_candidate_limits_are_strict(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        for attempt in (True, 0, 101):
            with self.subTest(attempt=attempt), self.assertRaises(MemoryContractError):
                replace(request, attempt=attempt)
        for limit in (True, 0, 128 * 1024 + 1, 1):
            with self.subTest(limit=limit), no_persistent_mutations(self, fixture.root), self.assertRaises(ActionTraceError):
                build_action_candidates(request, owners, max_candidate_bytes=limit)
        for ref in ("file:/etc/passwd", "runtime-execution:../other", "runtime-trace:"):
            with self.subTest(ref=ref), self.assertRaises(MemoryContractError):
                EvidenceReference(ref=ref, sha256="0" * 64)

    def output_fixture(self, *, stdout="model claims acceptance", stderr="warning: conflicting evidence"):
        fixture = self.fixture()
        provider_store = FileProviderArtifactStore(fixture.root / "provider-output")
        original = fixture.worker.executor

        class OutputExecutor(LocalExecutor):
            def execute(self, request):
                ref = provider_store.create(request.execution_id,
                    ProviderSelection("codex", "codex", "codex", False, None),
                    ProviderExecutionResult(status="succeeded", stdout=stdout, stderr=stderr, exit_code=0))
                return replace(original.execute(request), output_refs=(ref,), artifacts=(ref,))

        fixture.worker.executor = OutputExecutor()
        fixture.runtime.provider_artifact_store = provider_store
        _, outcome = fixture.run_job(fixture.payload(project_id="brightshore"))
        job = fixture.runtime.store.load(outcome.job_id)
        return fixture, job, outcome.execution_id

    def mutation_fixture(self, *, diff="COUNTEREVIDENCE: unexpected mutation"):
        fixture = self.fixture()
        mutation_store = FileMutationArtifactStore(fixture.root / "mutation-output")
        original = fixture.worker.executor

        class MutationExecutor(LocalExecutor):
            def execute(self, request):
                result = original.execute(request)
                ref = mutation_store.create(request.execution_id,
                    {"execution_id": request.execution_id, "job_id": request.job_id},
                    diff, max_diff_bytes=1024)
                return replace(result, output_refs=(ref,), artifacts=(ref,))

        fixture.worker.executor = MutationExecutor()
        fixture.runtime.mutation_artifact_store = mutation_store
        _, outcome = fixture.run_job(fixture.payload(project_id="brightshore"))
        self.assertEqual(outcome.status, "completed")
        job = fixture.runtime.store.load(outcome.job_id)
        request, owners = self.inputs(fixture, job, outcome.execution_id)
        value = mutation_store.load(outcome.execution_id)
        request = replace(request, outputs=(reference("runtime-mutation", outcome.execution_id, value),))
        return fixture, job, request, owners

    def denied_mutation_diff(self, fixture, request, owners):
        for _ in range(2):
            with no_persistent_mutations(self, fixture.root), \
                 patch("runtime.memory.action_trace.prepare_candidate", side_effect=AssertionError("Partial candidate")), \
                 self.assertRaisesRegex(ActionTraceError, "Mutation diff inspection is unsupported"):
                build_action_candidates(request, owners)

    def test_linked_mutation_diff_is_rejected_before_candidates_without_writes(self):
        fixture, job, request, owners = self.mutation_fixture()
        diff = owners.mutation_outputs.root / (request.execution.identity + ".diff")
        self.assertEqual(diff.read_text(encoding="utf-8"), "COUNTEREVIDENCE: unexpected mutation")
        self.denied_mutation_diff(fixture, request, owners)
        self.assertEqual(owners.jobs.load(request.job_id), job)

    def test_replaced_and_deleted_linked_mutation_diff_are_rejected(self):
        fixture, job, request, owners = self.mutation_fixture()
        diff = owners.mutation_outputs.root / (request.execution.identity + ".diff")
        diff.write_text("REPLACED DIFF COUNTEREVIDENCE", encoding="utf-8")
        self.denied_mutation_diff(fixture, request, owners)
        diff.unlink()
        self.denied_mutation_diff(fixture, request, owners)
        self.assertEqual(request.outputs[0], reference("runtime-mutation", request.execution.identity,
            owners.mutation_outputs.load(request.execution.identity)))
        self.assertEqual(owners.jobs.load(request.job_id), job)

    def test_non_null_malformed_and_foreign_mutation_links_are_rejected(self):
        fixture, _, request, owners = self.mutation_fixture(diff="")
        path = owners.mutation_outputs._path(request.execution.identity)
        value = owners.mutation_outputs.load(request.execution.identity)
        links = (False, 0, "", [], {}, "runtime-mutation-diff:other",
            {"ref_type": "file", "ref": "../../foreign.diff"},
            {"ref_type": "artifact", "ref": "runtime-mutation-diff:other"},
            {"ref_type": "artifact", "ref": "runtime-mutation-diff:../outside"})
        for link in links:
            with self.subTest(link=link):
                changed = {**value, "diff_ref": link}
                path.write_text(json.dumps(changed), encoding="utf-8")
                selected = replace(request, outputs=(reference("runtime-mutation", request.execution.identity, changed),))
                self.denied_mutation_diff(fixture, selected, owners)

    def test_no_diff_mutation_capture_is_exact_deterministic_and_untrusted(self):
        fixture, job, request, owners = self.mutation_fixture(diff="")
        value = owners.mutation_outputs.load(request.execution.identity)
        self.assertIsNone(value["diff_ref"])
        first = self.build(fixture, request, owners)
        self.assertEqual(first, self.build(fixture, request, owners))
        observation, assertion = [json.loads(c.original.claim) for c in first]
        self.assertTrue(observation["completion_verified"])
        self.assertEqual(assertion["outputs"], {request.outputs[0].ref: value})
        for candidate in first:
            self.assertEqual(candidate.original.status, ClaimStatus.REPORTED)
            self.assertIsNone(candidate.original.verification)
            self.assertIsNone(candidate.decision)
            self.assertEqual((candidate.original.trust, candidate.original.authority), ("untrusted", "none"))
            record = candidate.to_memory_record()
            self.assertEqual((record.trust, record.authority), ("untrusted", "none"))
            self.assertIsNone(record.verification)
            source = next(s for s in candidate.original.sources if s.source_id == request.outputs[0].ref)
            self.assertEqual(source.source_digest, request.outputs[0].sha256)
            self.assertEqual(source.source_version, "sha256:" + request.outputs[0].sha256)
        self.assertEqual(owners.jobs.load(request.job_id), job)

    def test_no_diff_mutation_capture_rejects_digest_and_identity_substitutions(self):
        fixture, _, request, owners = self.mutation_fixture(diff="")
        self.denied(fixture, replace(request, outputs=(replace(request.outputs[0], sha256="0" * 64),)), owners)
        path = owners.mutation_outputs._path(request.execution.identity)
        value = owners.mutation_outputs.load(request.execution.identity)
        for field, foreign in (("job_id", "other-job"), ("execution_id", "other-execution")):
            with self.subTest(field=field):
                changed = {**value, field: foreign}
                path.write_text(json.dumps(changed), encoding="utf-8")
                selected = replace(request, outputs=(reference("runtime-mutation", request.execution.identity, changed),))
                self.denied(fixture, selected, owners)

    def test_outputs_preserve_model_claims_and_warnings_without_trust(self):
        fixture, job, execution_id = self.output_fixture()
        request, owners = self.inputs(fixture, job, execution_id)
        result = self.build(fixture, request, owners)
        content = json.loads(result[1].original.claim)["outputs"][request.outputs[0].ref]
        self.assertEqual(content["process"]["stdout"], "model claims acceptance")
        self.assertEqual(content["process"]["stderr"], "warning: conflicting evidence")
        self.assertEqual(result[1].original.status, ClaimStatus.REPORTED)
        self.denied(fixture, replace(request, outputs=()), owners)
        self.denied(fixture, replace(request, outputs=(replace(request.outputs[0], sha256="0" * 64),)), owners)

    def test_oversized_output_is_rejected_without_truncation(self):
        fixture, job, execution_id = self.output_fixture(stdout="bounded text " * (11 * 1024))
        request, owners = self.inputs(fixture, job, execution_id)
        self.denied(fixture, request, owners)

    def test_exact_serialized_candidate_byte_boundary(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        candidates = self.build(fixture, request, owners)
        boundary = max(len(c.to_memory_record().claim.encode("utf-8")) for c in candidates)
        self.assertEqual(self.build(fixture, request, owners, max_candidate_bytes=boundary), candidates)
        with no_persistent_mutations(self, fixture.root), self.assertRaises(ActionTraceError):
            build_action_candidates(request, owners, max_candidate_bytes=boundary - 1)

    def test_output_reference_limits_duplicates_and_unsupported_paths(self):
        output = EvidenceReference(ref="runtime-provider-output:execution", sha256="0" * 64)
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        for values in ((output, output), (output,) * 17,
                       (replace(output, ref="runtime-execution:execution"),)):
            with self.subTest(count=len(values)), self.assertRaises(MemoryContractError):
                replace(request, outputs=values)
        self.denied(fixture, replace(request, outputs=(output,)), owners)

    def test_completed_job_without_proof_is_denied(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        job.pop("task_completion")
        fixture.runtime.store.save(job)
        self.denied(fixture, request, owners)

    def test_evidence_changed_after_nested_checks_fails_before_return(self):
        from runtime.memory.lifecycle import prepare_candidate
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        path = owners.executions._path(execution_id)
        tampered = json.loads(path.read_bytes())
        tampered["result"]["summary"] = "changed during inspection"
        changed = json.dumps(tampered).encode()

        def adversary(*args, **kwargs):
            candidate = prepare_candidate(*args, **kwargs)
            path.write_bytes(changed)
            return candidate

        # The injected adversary is the writer; inspection must neither return
        # cached evidence nor repair this deliberately changed fixture.
        with patch("runtime.memory.action_trace.prepare_candidate", side_effect=adversary), \
             self.assertRaises(ActionTraceError):
            build_action_candidates(request, owners)
        self.assertEqual(path.read_bytes(), changed)

    def test_failed_evaluation_and_warning_are_retained_exactly(self):
        from runtime.evals.models import EvalResult
        from runtime.evals.runner import EvalRunner
        fixture = self.fixture()
        payload = fixture.payload(project_id="brightshore")
        payload.pop("task_contract")
        _, outcome = fixture.run_job(payload)
        job = fixture.runtime.store.load(outcome.job_id)
        request, owners = self.inputs(fixture, job, outcome.execution_id)
        spec = {"schema_version": 1, "spec_id": "counterevidence", "job_id": request.job_id,
            "execution_id": request.execution.identity, "evaluator_id": "canonical-deterministic",
            "evaluator_version": "1", "metadata": {}, "checks": [
                {"check_id": "contract", "evaluator_type": "EXECUTION_RESULT_CONTRACT", "severity": "critical", "config": {}},
                {"check_id": "counter", "evaluator_type": "EXPECTED_STATUS", "severity": "major", "config": {"expected_status": "failed"}}]}
        evaluated = EvalRunner(clock=fixture.runtime.clock).run_persisted(spec, owners.executions).result
        # Create an identified canonical observation including a retained warning.
        value = evaluated.to_dict()
        for field in ("eval_id", "identity", "schema_version"):
            value.pop(field)
        value["checks"] = evaluated.checks
        value["evidence"] = evaluated.evidence
        value["failures"] = evaluated.failures
        value["warnings"] = ("retained uncertainty",)
        warned = EvalResult.create(spec_digest=evaluated.identity.spec_digest,
            execution_digest=evaluated.identity.execution_digest, **value)
        owners.evaluations.create(warned)
        selected = replace(request, evaluation=reference("runtime-eval", warned.eval_id, warned.to_dict()))
        candidates = self.build(fixture, selected, owners)
        observation = json.loads(candidates[0].original.claim)
        self.assertEqual(observation["evaluation"], warned.to_dict())
        self.assertEqual(observation["evaluation"]["failures"], ["counter"])
        self.assertEqual(observation["evaluation"]["warnings"], ["retained uncertainty"])
        self.assertFalse(observation["gov_accepted"])

    def test_evaluation_from_other_execution_cannot_be_substituted(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        _, other = fixture.run_job(fixture.payload(project_id="brightshore"))
        other_job = fixture.runtime.store.load(other.job_id)
        other_request, _ = self.inputs(fixture, other_job, other.execution_id)
        self.denied(fixture, replace(request, evaluation=other_request.evaluation), owners)

    def test_review_from_other_execution_cannot_be_substituted(self):
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        reviewed, reviewed_job, reviewed_execution = self.reviewed("PASS")
        other_request, other_owners = self.inputs(reviewed, reviewed_job, reviewed_execution)
        self.denied(fixture, replace(request, review=other_request.review),
                    replace(owners, reviews=other_owners.reviews))

    def test_changed_trace_provenance_changes_assertion_candidate_identity(self):
        from runtime.progress.models import ProgressEvent
        fixture, job, execution_id = self.completed()
        request, owners = self.inputs(fixture, job, execution_id)
        first = self.build(fixture, request, owners)
        owners.progress.append(ProgressEvent("tool_failed", request.trace.identity,
            request.job_id, execution_id=execution_id, detail="error"))
        journal = [event.to_dict() for event in owners.progress.read(request.trace.identity)]
        newer = replace(request, trace=reference("runtime-trace", request.trace.identity, journal))
        second = self.build(fixture, newer, owners)
        self.assertEqual(first[1].original.claim, second[1].original.claim)
        self.assertNotEqual(first[1].original.record_id, second[1].original.record_id)
        self.assertNotEqual(first[1].reference, second[1].reference)
        self.assertIn("tool_failed", second[0].original.claim)
        self.denied(fixture, request, owners)


if __name__ == "__main__":
    unittest.main()
