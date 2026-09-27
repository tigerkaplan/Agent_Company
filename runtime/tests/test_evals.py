from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from runtime.evals.evaluators import EvalEvaluatorError
from runtime.evals.models import EvalCheckResult, EvalContractError, EvalResult
from runtime.evals.runner import EvalRunner, EvalRuntimeError, _EvaluatorOutputError
from runtime.evals.store import EvalStoreError, FileEvalStore
from runtime.evals.validation import EvalResultValidator, EvalSpecValidator, EvalValidationError
from runtime.execution.models import ExecutionResult
from runtime.storage.execution_store import FileExecutionStore


NOW = "2026-09-27T12:00:00Z"
LATER = "2026-09-27T12:00:01Z"


class InjectedEvaluator:
    def __init__(self, factory) -> None:
        self.factory = factory

    def evaluate(self, check, context):
        return self.factory(check, context)


class EvalFrameworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = FileEvalStore(self.root / "evals")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def execution(**overrides) -> ExecutionResult:
        values = {
            "execution_id": "execution-1",
            "job_id": "job-1",
            "status": "succeeded",
            "summary": "Completed deterministic work",
            "error": None,
            "provider": "codex",
            "started_at": NOW,
            "completed_at": LATER,
            "evidence": (
                {
                    "kind": "deterministic_check",
                    "status": "passed",
                    "summary": "Unit checks passed",
                    "ref": {"ref_type": "log", "ref": "test-log:1"},
                },
            ),
            "artifacts": (
                {"ref_type": "artifact", "ref": "artifact:report"},
            ),
            "blockers": (),
            "next_actions": (),
            "retryable": False,
        }
        values.update(overrides)
        return ExecutionResult(**values)

    @staticmethod
    def check(check_id: str, evaluator_type: str, config: dict, severity: str = "major") -> dict:
        return {
            "check_id": check_id,
            "evaluator_type": evaluator_type,
            "severity": severity,
            "config": config,
        }

    def spec(self, *checks: dict, **overrides) -> dict:
        value = {
            "schema_version": 1,
            "spec_id": "spec-1",
            "execution_id": "execution-1",
            "job_id": "job-1",
            "evaluator_id": "canonical-deterministic",
            "evaluator_version": "1",
            "checks": [
                self.check("contract", "EXECUTION_RESULT_CONTRACT", {}, "critical"),
                *checks,
            ],
            "metadata": {
                "project_id": "agent-company",
                "workflow": "core-03-test",
                "provider": "codex",
            },
        }
        value.update(overrides)
        return value

    def runner(self, *, persist: bool = False, clock=lambda: NOW) -> EvalRunner:
        return EvalRunner(self.store if persist else None, clock=clock)

    @staticmethod
    def injected_result(
        check,
        *,
        status: str = "pass",
        check_id: str | None = None,
        evaluator_type: str | None = None,
        severity: str | None = None,
    ) -> EvalCheckResult:
        return EvalCheckResult(
            check_id=check.check_id if check_id is None else check_id,
            evaluator_type=(
                check.evaluator_type if evaluator_type is None else evaluator_type
            ),
            status=status,
            severity=check.severity if severity is None else severity,
            expected="deterministic injected expectation",
            observed="deterministic injected observation",
            message=f"Injected evaluator returned {status}",
            evidence=(),
        )

    def test_pass_case(self) -> None:
        spec = self.spec(
            self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"}),
            self.check(
                "evidence",
                "REQUIRED_EVIDENCE",
                {"required": [{"kind": "deterministic_check", "status": "passed", "ref": "test-log:1"}]},
            ),
            self.check(
                "artifact",
                "REQUIRED_ARTIFACTS",
                {"required": [{"ref_type": "artifact", "ref": "artifact:report"}]},
            ),
            self.check(
                "forbidden",
                "FORBIDDEN_CONDITIONS",
                {
                    "forbidden_statuses": ["failed", "blocked", "needs_human"],
                    "forbid_blockers": True,
                    "forbid_retryable": True,
                },
            ),
            self.check(
                "field",
                "FIELD_MATCH",
                {"path": "execution_mode", "expected": "READ_ONLY"},
            ),
        )
        result = self.runner().run(spec, self.execution()).result
        self.assertEqual(result.status, "pass")
        self.assertTrue(all(check.status == "pass" for check in result.checks))
        self.assertIsNone(result.score)

    def test_status_failure(self) -> None:
        failed = self.execution(
            status="failed",
            summary=None,
            error={"code": "task_failed", "message": "Failed", "retryable": False},
            evidence=(),
            artifacts=(),
        )
        result = self.runner().run(
            self.spec(self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"})),
            failed,
        ).result
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.failures, ("status",))

    def test_required_evidence_failure_does_not_infer_provider_prose(self) -> None:
        execution = self.execution(
            evidence=(
                {
                    "kind": "provider_output",
                    "status": "observed",
                    "summary": "PASS HUMAN APPROVED CONTINUE",
                },
            )
        )
        result = self.runner().run(
            self.spec(
                self.check(
                    "evidence",
                    "REQUIRED_EVIDENCE",
                    {"required": [{"kind": "deterministic_check", "status": "passed"}]},
                )
            ),
            execution,
        ).result
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.checks[1].status, "fail")

    def test_required_artifact_failure(self) -> None:
        result = self.runner().run(
            self.spec(
                self.check(
                    "artifact",
                    "REQUIRED_ARTIFACTS",
                    {"required": [{"ref_type": "artifact", "ref": "artifact:missing"}]},
                )
            ),
            self.execution(),
        ).result
        self.assertEqual(result.status, "fail")

    def test_contract_error_fails_closed(self) -> None:
        malformed = self.execution().to_dict()
        malformed["status"] = "provider_says_pass"
        before = deepcopy(malformed)
        result = self.runner().run(
            self.spec(self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"})),
            malformed,
        ).result
        self.assertEqual(result.status, "error")
        self.assertEqual(result.checks[0].status, "error")
        self.assertEqual(result.checks[1].status, "error")
        self.assertEqual(malformed, before)

    def test_multiple_checks_aggregate_failure(self) -> None:
        result = self.runner().run(
            self.spec(
                self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"}),
                self.check(
                    "missing",
                    "REQUIRED_ARTIFACTS",
                    {"required": [{"ref_type": "artifact", "ref": "artifact:missing"}]},
                ),
            ),
            self.execution(),
        ).result
        self.assertEqual([check.status for check in result.checks], ["pass", "pass", "fail"])
        self.assertEqual(result.status, "fail")

    def test_malformed_evaluator_configuration_is_error(self) -> None:
        result = self.runner().run(
            self.spec(self.check("status", "EXPECTED_STATUS", {})),
            self.execution(),
        ).result
        self.assertEqual(result.status, "error")
        self.assertEqual(result.checks[1].status, "error")

    def test_unknown_evaluator_fails_safely_without_loading_code(self) -> None:
        result = self.runner().run(
            self.spec(
                self.check(
                    "unknown",
                    "DYNAMIC_IMPORT",
                    {"module": "os", "class_name": "system", "command": "echo should-not-run"},
                )
            ),
            self.execution(),
        ).result
        self.assertEqual(result.status, "error")
        self.assertIn("explicit registry", result.checks[1].message)

    def test_field_match_is_bounded_and_type_strict(self) -> None:
        mismatch = self.runner().run(
            self.spec(self.check("field", "FIELD_MATCH", {"path": "retryable", "expected": 0})),
            self.execution(),
        ).result
        self.assertEqual(mismatch.status, "fail")
        invalid = self.runner().run(
            self.spec(self.check("field", "FIELD_MATCH", {"path": "__class__", "expected": "x"})),
            self.execution(),
        ).result
        self.assertEqual(invalid.status, "error")

    def test_forbidden_conditions_detect_human_and_blocker_states(self) -> None:
        blocked = self.execution(
            status="needs_human",
            summary="Human input required",
            evidence=(),
            artifacts=(),
            blockers=(
                {"code": "owner_input", "message": "Owner input required", "retryable": False, "requires_human": True},
            ),
        )
        result = self.runner().run(
            self.spec(
                self.check(
                    "forbidden",
                    "FORBIDDEN_CONDITIONS",
                    {"forbidden_statuses": ["needs_human"], "forbid_human_blockers": True},
                )
            ),
            blocked,
        ).result
        self.assertEqual(result.status, "fail")

    def test_deterministic_semantics_and_identity_exclude_created_time(self) -> None:
        spec = self.spec(self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"}))
        first = self.runner(clock=lambda: NOW).run(spec, self.execution()).result
        second = self.runner(clock=lambda: LATER).run(spec, self.execution()).result
        self.assertEqual(first.eval_id, second.eval_id)
        self.assertEqual(first.semantic_dict(), second.semantic_dict())
        self.assertNotEqual(first.created_at, second.created_at)

    def test_identity_changes_with_spec_result_or_version(self) -> None:
        base = self.runner().run(self.spec(), self.execution()).result
        changed_spec = self.runner().run(self.spec(metadata={"project_id": "different"}), self.execution()).result
        changed_result = self.runner().run(self.spec(), self.execution(summary="Different")).result
        changed_version = self.runner().run(self.spec(evaluator_version="2"), self.execution()).result
        self.assertEqual(len({base.eval_id, changed_spec.eval_id, changed_result.eval_id, changed_version.eval_id}), 4)
        self.assertEqual(changed_version.status, "error")

    def test_persistence_round_trip_and_safe_deduplication(self) -> None:
        first = self.runner(persist=True, clock=lambda: NOW).run(self.spec(), self.execution())
        second = self.runner(persist=True, clock=lambda: LATER).run(self.spec(), self.execution())
        loaded = self.store.load(first.result.eval_id)
        self.assertEqual(loaded.to_dict(), first.result.to_dict())
        self.assertEqual(second.result.created_at, NOW)
        self.assertEqual(first.artifact_ref["ref"], f"runtime-eval:{first.result.eval_id}")
        self.assertEqual(len(self.store.list()), 1)

    def test_cli_runs_against_persisted_execution_and_supports_show(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        execution_root = self.root / "executions"
        FileExecutionStore(execution_root).create(None, self.execution())
        spec_path = self.root / "eval-spec.json"
        spec_path.write_text(json.dumps(self.spec()), encoding="utf-8")
        base = [
            sys.executable,
            "-m",
            "runtime.cli",
            "--state-root",
            str(self.root / "jobs"),
            "--execution-root",
            str(execution_root),
            "--approval-root",
            str(self.root / "approvals"),
        ]
        run_result = subprocess.run(
            [*base, "eval", "run", "--spec", str(spec_path)],
            cwd=repository,
            check=False,
            capture_output=True,
            text=True,
        )
        if run_result.returncode != 0:
            raise AssertionError(run_result.stderr)
        evaluated = json.loads(run_result.stdout)
        self.assertEqual(evaluated["status"], "pass")
        show_result = subprocess.run(
            [*base, "eval", "show", evaluated["eval_id"]],
            cwd=repository,
            check=False,
            capture_output=True,
            text=True,
        )
        if show_result.returncode != 0:
            raise AssertionError(show_result.stderr)
        self.assertEqual(json.loads(show_result.stdout), evaluated)

    def test_malformed_persisted_eval_fails_closed(self) -> None:
        result = self.runner(persist=True).run(self.spec(), self.execution()).result
        path = self.store.root / f"{result.eval_id}.eval.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["status"] = "pass" if result.status != "pass" else "error"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(EvalStoreError):
            self.store.load(result.eval_id)

    def test_store_rejects_path_traversal(self) -> None:
        with self.assertRaises(EvalStoreError):
            self.store.load("../outside")

    def test_schema_model_runtime_parity(self) -> None:
        spec = EvalSpecValidator().validate(self.spec())
        EvalSpecValidator().validate_model(spec)
        result = self.runner().run(spec, self.execution()).result
        self.assertEqual(EvalResultValidator().validate(result.to_dict()).to_dict(), result.to_dict())

    def test_schema_rejects_unknown_top_level_fields(self) -> None:
        spec = self.spec()
        spec["approval"] = "APPROVED"
        with self.assertRaises(EvalValidationError):
            EvalSpecValidator().validate(spec)

    def test_contract_check_is_mandatory_and_first(self) -> None:
        with self.assertRaises(EvalRuntimeError):
            self.runner().run(
                self.spec(
                    checks=[self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"})]
                ),
                self.execution(),
            )

    def test_eval_cannot_create_authority_or_mutate_inputs(self) -> None:
        spec = self.spec(
            self.check("status", "EXPECTED_STATUS", {"expected_status": "succeeded"})
        )
        execution = self.execution().to_dict()
        before_spec = deepcopy(spec)
        before_execution = deepcopy(execution)
        result = self.runner().run(spec, execution).result.to_dict()
        self.assertEqual(spec, before_spec)
        self.assertEqual(execution, before_execution)
        prohibited = {
            "approval",
            "approved",
            "continuation",
            "retry",
            "authorized_plan",
            "git",
            "deployment",
        }
        self.assertFalse(prohibited.intersection(result))

    def test_eval_result_nested_values_are_immutable(self) -> None:
        result = self.runner().run(self.spec(), self.execution()).result
        with self.assertRaises(TypeError):
            result.metadata["project_id"] = "changed"  # type: ignore[index]
        with self.assertRaises(TypeError):
            result.evidence[0]["ref"] = "changed"  # type: ignore[index]

    def test_secret_bearing_spec_is_rejected(self) -> None:
        with self.assertRaises(EvalRuntimeError):
            self.runner().run(
                self.spec(metadata={"api_key": "not-allowed"}),
                self.execution(),
            )

    def test_non_json_identity_input_is_controlled_error(self) -> None:
        payload = self.execution().to_dict()
        payload["summary"] = {"not": {"a": {"canonical": object()}}}
        with self.assertRaises(EvalRuntimeError):
            self.runner().run(self.spec(), payload)

    def test_result_model_rejects_inconsistent_aggregate(self) -> None:
        valid = self.runner().run(self.spec(), self.execution()).result.to_dict()
        valid["status"] = "error"
        with self.assertRaises(EvalContractError):
            EvalResult.from_dict(valid)

    def test_content_id_format_and_create_boundary_reject_forgery(self) -> None:
        result = self.runner().run(self.spec(), self.execution()).result
        self.assertRegex(result.eval_id, r"^eval-[0-9a-f]{32}$")
        for forged_id in ("forged-safe-id", f"eval-{'0' * 32}"):
            payload = result.to_dict()
            payload["eval_id"] = forged_id
            with self.subTest(forged_id=forged_id), self.assertRaises(EvalContractError):
                EvalResult.from_dict(payload)
            with self.subTest(
                validator_forged_id=forged_id
            ), self.assertRaises(EvalValidationError):
                EvalResultValidator().validate(payload)

        object.__setattr__(result, "eval_id", f"eval-{'0' * 32}")
        with self.assertRaises(EvalStoreError):
            self.store.create(result)

    def test_persisted_identity_tampering_fails_closed_on_restart(self) -> None:
        result = self.runner(persist=True).run(self.spec(), self.execution()).result
        path = self.store.root / f"{result.eval_id}.eval.json"
        original = result.to_dict()

        mutations = {
            "spec_digest": lambda value: value["identity"].__setitem__("spec_digest", "0" * 64),
            "execution_digest": lambda value: value["identity"].__setitem__("execution_digest", "1" * 64),
            "evaluator_version": lambda value: value.__setitem__("evaluator_version", "2"),
            "job_id": lambda value: value.__setitem__("job_id", "job-tampered"),
            "execution_id": lambda value: value.__setitem__("execution_id", "execution-tampered"),
            "aggregate_status": lambda value: value.__setitem__("status", "error"),
            "check_result": lambda value: value["checks"][0].__setitem__("message", "tampered"),
            "metadata": lambda value: value.__setitem__("metadata", {"project_id": "tampered"}),
        }
        restarted = FileEvalStore(self.store.root)
        for name, mutate in mutations.items():
            value = deepcopy(original)
            mutate(value)
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(EvalStoreError):
                restarted.load(result.eval_id)
        path.write_text(json.dumps(original), encoding="utf-8")
        self.assertEqual(restarted.load(result.eval_id).to_dict(), original)

    def test_identity_material_and_identical_repersistence(self) -> None:
        first = self.runner(persist=True, clock=lambda: NOW).run(
            self.spec(), self.execution()
        ).result
        second = self.runner(persist=True, clock=lambda: LATER).run(
            self.spec(), self.execution()
        ).result
        self.assertEqual(first.eval_id, second.eval_id)
        self.assertEqual(first.created_at, second.created_at)
        self.assertEqual(len(self.store.list()), 1)
        self.assertRegex(first.identity.spec_digest, r"^[0-9a-f]{64}$")
        self.assertRegex(first.identity.execution_digest, r"^[0-9a-f]{64}$")
        self.assertRegex(first.identity.result_digest, r"^[0-9a-f]{64}$")

    def test_secret_policy_matches_core01_across_spec_locations(self) -> None:
        secret_values = (
            "API_KEY=synthetic-secret",
            "PASSWORD=synthetic-secret",
            "TOKEN=synthetic-secret",
            "Bearer synthetic-secret-token",
            "sk-syntheticsecret12345",
        )
        for value in secret_values:
            with self.subTest(value=value), self.assertRaises(EvalRuntimeError):
                self.runner().run(
                    self.spec(metadata={"note": value}),
                    self.execution(),
                )
            with self.subTest(expected=value), self.assertRaises(EvalRuntimeError):
                self.runner().run(
                    self.spec(
                        self.check(
                            "field",
                            "FIELD_MATCH",
                            {"path": "summary", "expected": value},
                        )
                    ),
                    self.execution(),
                )

        for key in ("service_credential", "nested_credential"):
            with self.subTest(key=key), self.assertRaises(EvalRuntimeError):
                self.runner().run(
                    self.spec(
                        self.check("field", "FIELD_MATCH", {key: "synthetic-secret"})
                    ),
                    self.execution(),
                )

        allowed = self.runner().run(
            self.spec(metadata={"note": "API_KEY documentation only"}),
            self.execution(),
        ).result
        self.assertEqual(allowed.status, "pass")

    def test_secret_policy_rejects_tampered_result_locations(self) -> None:
        original = self.runner().run(self.spec(), self.execution()).result.to_dict()
        mutations = {
            "metadata": lambda value: value.__setitem__(
                "metadata", {"note": "API_KEY=synthetic-secret"}
            ),
            "expected": lambda value: value["checks"][0].__setitem__(
                "expected", "PASSWORD=synthetic-secret"
            ),
            "observed": lambda value: value["checks"][0].__setitem__(
                "observed", "TOKEN=synthetic-secret"
            ),
            "message": lambda value: value["checks"][0].__setitem__(
                "message", "Bearer synthetic-secret-token"
            ),
            "evidence": lambda value: value["checks"][0]["evidence"][0].__setitem__(
                "description", "PASSWORD=synthetic-secret"
            ),
        }
        for name, mutate in mutations.items():
            value = deepcopy(original)
            mutate(value)
            with self.subTest(name=name), self.assertRaises(EvalContractError):
                EvalResult.from_dict(value)

    def test_field_match_distinguishes_missing_null_and_types(self) -> None:
        cases = (
            ("missing-null", "usage.duration_ms", None, {"usage": None}, "fail"),
            ("present-null", "fallback_reason", None, {"usage": None}, "pass"),
            ("missing-value", "usage.duration_ms", 5, {"usage": None}, "fail"),
            ("nested-missing", "usage.output_units", 1, {"usage": {"duration_ms": 1}}, "fail"),
            ("int-string", "usage.duration_ms", "1", {"usage": {"duration_ms": 1}}, "fail"),
            ("bool-int", "dry_run", 1, {"dry_run": True}, "fail"),
            ("valid-nested", "usage.duration_ms", 1, {"usage": {"duration_ms": 1}}, "pass"),
        )
        for name, path, expected, overrides, status in cases:
            result = self.runner().run(
                self.spec(
                    self.check(
                        "field",
                        "FIELD_MATCH",
                        {"path": path, "expected": expected},
                    )
                ),
                self.execution(**overrides),
            ).result
            with self.subTest(name=name):
                self.assertEqual(result.checks[1].status, status)
                if name == "missing-null":
                    self.assertEqual(result.checks[1].observed, "MISSING")

        unknown = self.runner().run(
            self.spec(
                self.check(
                    "field",
                    "FIELD_MATCH",
                    {"path": "usage.__class__", "expected": None},
                )
            ),
            self.execution(),
        ).result
        self.assertEqual(unknown.status, "error")

    def test_aggregate_evidence_caps_summary_without_dropping_check_evidence(self) -> None:
        artifacts = tuple(
            {"ref_type": "artifact", "ref": f"artifact:{index}"}
            for index in range(100)
        )
        first = [
            {"ref_type": "artifact", "ref": f"artifact:{index}"}
            for index in range(50)
        ]
        second = [
            {"ref_type": "artifact", "ref": f"artifact:{index}"}
            for index in range(50, 100)
        ]
        result = self.runner().run(
            self.spec(
                self.check("first", "REQUIRED_ARTIFACTS", {"required": first}),
                self.check("second", "REQUIRED_ARTIFACTS", {"required": second}),
            ),
            self.execution(artifacts=artifacts),
        ).result
        self.assertEqual(result.status, "pass")
        self.assertEqual(len(result.evidence), 100)
        self.assertEqual(len(result.checks[1].evidence), 51)
        self.assertEqual(len(result.checks[2].evidence), 51)
        self.assertEqual(result.evidence[0]["ref"], "runtime-execution:execution-1")
        self.assertEqual(result.evidence[-1]["ref"], "artifact:98")

    def test_aggregate_evidence_exact_limit_duplicates_and_order(self) -> None:
        artifacts = tuple(
            {"ref_type": "artifact", "ref": f"artifact:{index}"}
            for index in range(99)
        )
        required = [dict(item) for item in artifacts[:50]]
        result = self.runner().run(
            self.spec(
                self.check("first", "REQUIRED_ARTIFACTS", {"required": required}),
                self.check("duplicate", "REQUIRED_ARTIFACTS", {"required": required}),
                self.check(
                    "second",
                    "REQUIRED_ARTIFACTS",
                    {"required": [dict(item) for item in artifacts[50:]]},
                ),
            ),
            self.execution(artifacts=artifacts),
        ).result
        self.assertEqual(len(result.evidence), 100)
        self.assertEqual(
            [item["ref"] for item in result.evidence[1:]],
            [f"artifact:{index}" for index in range(99)],
        )

    def test_maximum_check_count_and_invalid_registry_result_are_canonical(self) -> None:
        checks = tuple(
            self.check(
                f"status-{index}",
                "EXPECTED_STATUS",
                {"expected_status": "succeeded"},
            )
            for index in range(99)
        )
        maximum = self.runner().run(self.spec(*checks), self.execution()).result
        self.assertEqual(maximum.status, "pass")
        self.assertEqual(len(maximum.checks), 100)

        class InvalidEvaluator:
            def evaluate(self, check, context):
                return object()

        malformed = EvalRunner(
            registry={"EXECUTION_RESULT_CONTRACT": InvalidEvaluator()}
        ).run(self.spec(), self.execution()).result
        self.assertEqual(malformed.status, "error")
        self.assertIn("canonical EvalCheckResult", malformed.checks[0].message)

    def test_evaluator_result_identity_is_bound_to_originating_check(self) -> None:
        mismatches = {
            "check_id": {"check_id": "different"},
            "evaluator_type": {"evaluator_type": "EXPECTED_STATUS"},
            "severity": {"severity": "minor"},
            "combined": {
                "check_id": "different",
                "evaluator_type": "EXPECTED_STATUS",
                "severity": "minor",
            },
        }
        for name, overrides in mismatches.items():
            evaluator = InjectedEvaluator(
                lambda check, context, values=overrides: self.injected_result(
                    check, **values
                )
            )
            result = EvalRunner(
                registry={"EXECUTION_RESULT_CONTRACT": evaluator}
            ).run(self.spec(), self.execution()).result
            with self.subTest(name=name):
                self.assertEqual(result.status, "error")
                self.assertEqual(result.failures, ("contract",))
                self.assertEqual(result.checks[0].check_id, "contract")
                self.assertEqual(
                    result.checks[0].evaluator_type,
                    "EXECUTION_RESULT_CONTRACT",
                )
                self.assertEqual(result.checks[0].severity, "critical")
                self.assertIn("originating EvalCheckSpec", result.checks[0].message)

    def test_none_and_wrong_object_results_are_canonical_errors(self) -> None:
        for name, value in (("none", None), ("object", object())):
            result = EvalRunner(
                registry={
                    "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                        lambda check, context, returned=value: returned
                    )
                }
            ).run(self.spec(), self.execution()).result
            with self.subTest(name=name):
                self.assertEqual(result.status, "error")
                self.assertEqual(result.checks[0].status, "error")
                self.assertEqual(result.checks[0].check_id, "contract")
                self.assertIn("canonical EvalCheckResult", result.checks[0].message)

    def test_consistent_injected_results_preserve_status(self) -> None:
        for status in ("pass", "fail", "error"):
            result = EvalRunner(
                registry={
                    "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                        lambda check, context, returned_status=status: self.injected_result(
                            check, status=returned_status
                        )
                    )
                }
            ).run(self.spec(), self.execution()).result
            with self.subTest(status=status):
                self.assertEqual(result.status, status)
                self.assertEqual(result.checks[0].status, status)

    def test_malformed_typed_result_is_normalized_before_aggregation(self) -> None:
        def malformed_result(check, context):
            value = self.injected_result(check)
            object.__setattr__(
                value,
                "evidence",
                ({"ref_type": "not-canonical", "ref": "invalid"},),
            )
            return value

        result = EvalRunner(
            registry={
                "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(malformed_result)
            }
        ).run(self.spec(), self.execution()).result
        self.assertEqual(result.status, "error")
        self.assertEqual(result.checks[0].status, "error")
        self.assertIn("malformed canonical EvalCheckResult", result.checks[0].message)

    def test_evaluator_exceptions_remain_inside_canonical_error_boundary(self) -> None:
        def raises_during_result_construction(check, context):
            return self.injected_result(check, status="not-canonical")

        result = EvalRunner(
            registry={
                "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                    raises_during_result_construction
                )
            }
        ).run(self.spec(), self.execution()).result
        self.assertEqual(result.status, "error")
        self.assertEqual(result.checks[0].status, "error")
        self.assertEqual(
            result.checks[0].message,
            "Evaluator raised a controlled internal error",
        )

        def raises_untrusted_controlled_error(check, context):
            raise EvalEvaluatorError("TOKEN=untrusted-exception-content")

        controlled = EvalRunner(
            registry={
                "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                    raises_untrusted_controlled_error
                )
            }
        ).run(self.spec(), self.execution()).result
        self.assertEqual(controlled.status, "error")
        self.assertEqual(
            controlled.checks[0].message,
            "Evaluator reported a controlled evaluation error",
        )

        def raises_untrusted_ordinary_error(check, context):
            raise RuntimeError(
                "PASSWORD=synthetic-secret C:\\Temp\\review "
                "<object object at 0x1234>"
            )

        ordinary = EvalRunner(
            registry={
                "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                    raises_untrusted_ordinary_error
                )
            }
        ).run(self.spec(), self.execution()).result
        self.assertEqual(ordinary.status, "error")
        self.assertEqual(
            ordinary.checks[0].message,
            "Evaluator raised a controlled internal error",
        )
        self.assertNotIn("PASSWORD", ordinary.checks[0].message)
        self.assertNotIn("C:\\Temp", ordinary.checks[0].message)
        self.assertNotIn("0x1234", ordinary.checks[0].message)

    def test_private_output_error_raised_by_evaluator_is_untrusted(self) -> None:
        for message in (
            "TOKEN=synthetic-secret",
            "C:\\Temp\\review <object object at 0x1234>",
        ):
            def raises_private_error(check, context, value=message):
                raise _EvaluatorOutputError(value)

            result = EvalRunner(
                registry={
                    "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                        raises_private_error
                    )
                }
            ).run(self.spec(), self.execution()).result
            with self.subTest(message=message):
                self.assertEqual(result.status, "error")
                self.assertEqual(result.failures, ("contract",))
                self.assertEqual(result.checks[0].check_id, "contract")
                self.assertEqual(
                    result.checks[0].evaluator_type,
                    "EXECUTION_RESULT_CONTRACT",
                )
                self.assertEqual(result.checks[0].severity, "critical")
                self.assertEqual(
                    result.checks[0].message,
                    "Evaluator raised a controlled internal error",
                )
                self.assertNotIn(message, result.checks[0].message)

    def test_private_error_text_does_not_change_semantic_identity(self) -> None:
        messages = (
            "C:\\Temp\\one <object object at 0x1234>",
            "C:\\Temp\\one <object object at 0x5678>",
            "D:\\Other\\two random-9f8e7d6c",
            "TOKEN=different-synthetic-secret",
        )
        results = []
        for index, message in enumerate(messages):
            def raises_private_error(check, context, value=message):
                raise _EvaluatorOutputError(value)

            results.append(
                EvalRunner(
                    clock=lambda value=index: NOW if value % 2 == 0 else LATER,
                    registry={
                        "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                            raises_private_error
                        )
                    },
                ).run(self.spec(), self.execution()).result
            )

        self.assertEqual(len({result.eval_id for result in results}), 1)
        self.assertEqual(
            len({result.identity.result_digest for result in results}),
            1,
        )
        self.assertEqual(
            len(
                {
                    json.dumps(result.semantic_dict(), sort_keys=True)
                    for result in results
                }
            ),
            1,
        )

    def test_private_error_persistence_contains_only_normalized_content(self) -> None:
        messages = (
            "C:\\Temp\\review <object object at 0x1234>",
            "TOKEN=synthetic-secret",
        )
        persisted = []
        for index, message in enumerate(messages):
            def raises_private_error(check, context, value=message):
                raise _EvaluatorOutputError(value)

            persisted.append(
                EvalRunner(
                    self.store,
                    clock=lambda value=index: NOW if value == 0 else LATER,
                    registry={
                        "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                            raises_private_error
                        )
                    },
                ).run(self.spec(), self.execution()).result
            )

        self.assertEqual(persisted[0].eval_id, persisted[1].eval_id)
        self.assertEqual(persisted[1].created_at, NOW)
        self.assertEqual(len(self.store.list()), 1)
        loaded = self.store.load(persisted[0].eval_id)
        self.assertEqual(loaded.checks[0].check_id, "contract")
        self.assertEqual(loaded.checks[0].status, "error")
        self.assertEqual(
            loaded.checks[0].message,
            "Evaluator raised a controlled internal error",
        )
        raw = json.dumps(loaded.to_dict(), sort_keys=True)
        self.assertNotIn("C:\\\\Temp", raw)
        self.assertNotIn("0x1234", raw)
        self.assertNotIn("synthetic-secret", raw)

    def test_mutated_evaluator_inputs_cannot_change_error_boundary(self) -> None:
        cases = (
            (
                "private",
                _EvaluatorOutputError,
                "Evaluator raised a controlled internal error",
            ),
            (
                "ordinary",
                RuntimeError,
                "Evaluator raised a controlled internal error",
            ),
            (
                "controlled",
                EvalEvaluatorError,
                "Evaluator reported a controlled evaluation error",
            ),
        )
        for name, error_type, expected_message in cases:
            results = []
            for raw in (
                "C:\\Temp\\one <object object at 0x12345678>",
                "TOKEN=synthetic-secret",
            ):
                def mutates_then_raises(
                    check,
                    context,
                    value=raw,
                    exception_type=error_type,
                ):
                    check.__dict__["check_id"] = "mutated-check"
                    check.__dict__["evaluator_type"] = "EXPECTED_STATUS"
                    check.__dict__["severity"] = "minor"
                    context.__dict__["execution_id"] = value
                    context.execution["execution_id"] = value
                    if context.canonical_result is not None:
                        context.canonical_result.__dict__["execution_id"] = value
                    raise exception_type(value)

                result = EvalRunner(
                    registry={
                        "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                            mutates_then_raises
                        )
                    }
                ).run(self.spec(), self.execution()).result
                results.append(result)
                with self.subTest(kind=name, raw=raw):
                    self.assertEqual(result.status, "error")
                    self.assertEqual(result.failures, ("contract",))
                    self.assertEqual(result.checks[0].check_id, "contract")
                    self.assertEqual(
                        result.checks[0].evaluator_type,
                        "EXECUTION_RESULT_CONTRACT",
                    )
                    self.assertEqual(result.checks[0].severity, "critical")
                    self.assertEqual(result.checks[0].message, expected_message)
                    self.assertEqual(
                        result.checks[0].evidence[0]["ref"],
                        "runtime-execution:execution-1",
                    )
                    self.assertNotIn(raw, json.dumps(result.to_dict()))
            self.assertEqual(results[0].eval_id, results[1].eval_id)
            self.assertEqual(
                results[0].identity.result_digest,
                results[1].identity.result_digest,
            )

    def test_mutated_return_identity_is_checked_against_trusted_spec(self) -> None:
        def mutates_then_returns(check, context):
            check.__dict__["check_id"] = "mutated-check"
            check.__dict__["evaluator_type"] = "EXPECTED_STATUS"
            check.__dict__["severity"] = "minor"
            return self.injected_result(check)

        result = EvalRunner(
            registry={
                "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                    mutates_then_returns
                )
            }
        ).run(self.spec(), self.execution()).result
        self.assertEqual(result.status, "error")
        self.assertEqual(result.failures, ("contract",))
        self.assertEqual(result.checks[0].check_id, "contract")
        self.assertEqual(
            result.checks[0].evaluator_type,
            "EXECUTION_RESULT_CONTRACT",
        )
        self.assertEqual(result.checks[0].severity, "critical")
        self.assertIn("originating EvalCheckSpec", result.checks[0].message)

    def test_each_evaluator_receives_an_isolated_context(self) -> None:
        def mutates_context_then_passes(check, context):
            context.__dict__["execution_id"] = "mutated-execution"
            context.execution["status"] = "failed"
            if context.canonical_result is not None:
                context.canonical_result.__dict__["status"] = "failed"
            return self.injected_result(check)

        registry = dict(EvalRunner().registry)
        registry["EXECUTION_RESULT_CONTRACT"] = InjectedEvaluator(
            mutates_context_then_passes
        )
        result = EvalRunner(registry=registry).run(
            self.spec(
                self.check(
                    "status",
                    "EXPECTED_STATUS",
                    {"expected_status": "succeeded"},
                )
            ),
            self.execution(),
        ).result
        self.assertEqual(result.status, "pass")
        self.assertEqual([check.status for check in result.checks], ["pass", "pass"])
        self.assertEqual(
            result.checks[1].evidence[0]["ref"],
            "runtime-execution:execution-1",
        )

    def test_typed_spec_is_copied_before_evaluator_invocation(self) -> None:
        typed_spec = EvalSpecValidator().validate(self.spec())
        before = typed_spec.to_dict()

        def mutates_then_raises(check, context):
            check.__dict__["check_id"] = "caller-mutated"
            context.__dict__["execution_id"] = "caller-mutated"
            raise _EvaluatorOutputError("caller-mutated")

        result = EvalRunner(
            registry={
                "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                    mutates_then_raises
                )
            }
        ).run(typed_spec, self.execution()).result
        self.assertEqual(result.status, "error")
        self.assertEqual(result.checks[0].check_id, "contract")
        self.assertEqual(typed_spec.to_dict(), before)

    def test_mutated_inputs_do_not_reach_persistence_or_cli(self) -> None:
        messages = (
            "C:\\Temp\\review <object object at 0x12345678>",
            "TOKEN=synthetic-secret",
        )
        persisted = []
        for index, raw in enumerate(messages):
            def mutates_then_raises(check, context, value=raw):
                check.__dict__["check_id"] = "mutated-check"
                check.__dict__["severity"] = "minor"
                context.__dict__["execution_id"] = value
                raise _EvaluatorOutputError(value)

            persisted.append(
                EvalRunner(
                    self.store,
                    clock=lambda value=index: NOW if value == 0 else LATER,
                    registry={
                        "EXECUTION_RESULT_CONTRACT": InjectedEvaluator(
                            mutates_then_raises
                        )
                    },
                ).run(self.spec(), self.execution()).result
            )

        self.assertEqual(persisted[0].eval_id, persisted[1].eval_id)
        self.assertEqual(len(self.store.list()), 1)
        loaded = FileEvalStore(self.store.root).load(persisted[0].eval_id)
        self.assertEqual(loaded.checks[0].check_id, "contract")
        self.assertEqual(loaded.checks[0].severity, "critical")
        self.assertEqual(
            loaded.checks[0].evidence[0]["ref"],
            "runtime-execution:execution-1",
        )
        stored_text = (
            self.store.root / f"{loaded.eval_id}.eval.json"
        ).read_text(encoding="utf-8")
        for fragment in ("Temp", "0x12345678", "synthetic-secret", "mutated-check"):
            self.assertNotIn(fragment, stored_text)

        repository = Path(__file__).resolve().parents[2]
        base = [
            sys.executable,
            "-m",
            "runtime.cli",
            "--execution-root",
            str(self.root),
            "eval",
        ]
        for command in (("show", loaded.eval_id), ("list",)):
            shown = subprocess.run(
                [*base, *command],
                cwd=repository,
                check=False,
                capture_output=True,
                text=True,
            )
            with self.subTest(command=command):
                self.assertEqual(shown.returncode, 0, shown.stderr)
                self.assertIn('"status": "error"', shown.stdout)
                for fragment in (
                    "Temp",
                    "0x12345678",
                    "synthetic-secret",
                    "mutated-check",
                ):
                    self.assertNotIn(fragment, shown.stdout + shown.stderr)

    def test_identity_mismatch_overrides_otherwise_passing_aggregation(self) -> None:
        registry = dict(EvalRunner().registry)
        registry["EXPECTED_STATUS"] = InjectedEvaluator(
            lambda check, context: self.injected_result(
                check, check_id="substituted"
            )
        )
        result = EvalRunner(registry=registry).run(
            self.spec(
                self.check(
                    "status",
                    "EXPECTED_STATUS",
                    {"expected_status": "succeeded"},
                )
            ),
            self.execution(),
        ).result
        self.assertEqual([check.status for check in result.checks], ["pass", "error"])
        self.assertEqual(result.status, "error")
        self.assertEqual(result.failures, ("status",))
        self.assertEqual(result.checks[1].check_id, "status")

    def test_malformed_output_has_deterministic_semantic_identity(self) -> None:
        evaluator = InjectedEvaluator(
            lambda check, context: self.injected_result(
                check,
                check_id="different",
                evaluator_type="EXPECTED_STATUS",
                severity="minor",
            )
        )
        registry = {"EXECUTION_RESULT_CONTRACT": evaluator}
        first = EvalRunner(clock=lambda: NOW, registry=registry).run(
            self.spec(), self.execution()
        ).result
        second = EvalRunner(clock=lambda: LATER, registry=registry).run(
            self.spec(), self.execution()
        ).result
        self.assertEqual(first.eval_id, second.eval_id)
        self.assertEqual(first.identity.result_digest, second.identity.result_digest)
        self.assertEqual(first.semantic_dict(), second.semantic_dict())

    def test_persistence_receives_only_normalized_mismatch_error(self) -> None:
        evaluator = InjectedEvaluator(
            lambda check, context: self.injected_result(
                check,
                check_id="different",
                evaluator_type="EXPECTED_STATUS",
                severity="minor",
            )
        )
        registry = {"EXECUTION_RESULT_CONTRACT": evaluator}
        first = EvalRunner(
            self.store,
            clock=lambda: NOW,
            registry=registry,
        ).run(self.spec(), self.execution()).result
        second = EvalRunner(
            self.store,
            clock=lambda: LATER,
            registry=registry,
        ).run(self.spec(), self.execution()).result
        loaded = self.store.load(first.eval_id)
        self.assertEqual(first.eval_id, second.eval_id)
        self.assertEqual(second.created_at, NOW)
        self.assertEqual(loaded.checks[0].check_id, "contract")
        self.assertEqual(
            loaded.checks[0].evaluator_type,
            "EXECUTION_RESULT_CONTRACT",
        )
        self.assertEqual(loaded.checks[0].severity, "critical")
        self.assertEqual(loaded.checks[0].status, "error")


if __name__ == "__main__":
    unittest.main()
