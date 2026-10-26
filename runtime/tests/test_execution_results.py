from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from runtime.core.validation import JobValidationError, JobValidator
from runtime.execution.models import (
    CANONICAL_INTEGER_MAX,
    CANONICAL_INTEGER_MIN,
    EXECUTION_RESULT_STATUSES,
    ExecutionContractError,
    ExecutionResult,
    FrozenMapping,
)
from runtime.execution.validation import (
    ExecutionResultValidationError,
    ExecutionResultValidator,
)
from runtime.executors.local import LocalExecutor
from runtime.providers.adapters import sanitize_provider_text
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfiguration
from runtime.providers.context import ExecutionContextBuilder
from runtime.tests.contract_fixtures import (
    CertifiedProviderFixture as ProviderExecutor,
    bounded_context_repository,
)
from runtime.providers.models import (
    ProviderAvailability,
    ProviderExecutionResult,
    ProviderSelection,
)
from runtime.providers.routing import ProviderRouter
from runtime.storage.execution_store import (
    ExecutionRecord,
    ExecutionStoreError,
    FileExecutionStore,
)
from runtime.tests.test_providers import request


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "execution-result.schema.json"
ARTIFACT = {
    "ref_type": "artifact",
    "ref": "runtime-output:result-001",
    "description": "Bounded generated output",
}
EVIDENCE = {
    "kind": "deterministic_check",
    "status": "passed",
    "summary": "Deterministic validation passed",
    "ref": ARTIFACT,
}
BLOCKER = {
    "code": "approval_required",
    "message": "Exact human approval is required",
    "retryable": False,
    "requires_human": True,
}
NON_HUMAN_BLOCKER = {
    "code": "capability_unavailable",
    "message": "A required capability is unavailable",
    "retryable": True,
    "requires_human": False,
}
NEXT_ACTION = {
    "action": "request_approval",
    "description": "Request exact approval without executing automatically",
    "requires_human": True,
    "automatic": False,
}


class FakeProviderAdapter:
    native_tools = frozenset()
    def __init__(self, provider_id: str, *, available: bool) -> None:
        self.provider_id = provider_id
        self.available = available

    def is_available(self) -> ProviderAvailability:
        return ProviderAvailability(
            self.available,
            "fake_available" if self.available else "fake_unavailable",
            f"C:/fake/{self.provider_id}.exe" if self.available else None,
        )

    def execute(self, request: object, context: object) -> ProviderExecutionResult:
        return ProviderExecutionResult(
            status="succeeded",
            stdout=f"{self.provider_id} output",
            stderr="",
            exit_code=0,
        )


def result(**overrides: object) -> ExecutionResult:
    values: dict[str, object] = {
        "execution_id": "execution-result-001",
        "job_id": "job-result-001",
        "status": "succeeded",
        "output_refs": (),
        "summary": "Canonical execution completed",
        "error": None,
        "provider": None,
        "started_at": "2026-09-26T10:00:00Z",
        "completed_at": "2026-09-26T10:00:01Z",
    }
    values.update(overrides)
    if "artifacts" in overrides and "output_refs" not in overrides:
        values.pop("output_refs")
    return ExecutionResult(**values)  # type: ignore[arg-type]


class ExecutionResultContractTests(unittest.TestCase):
    def test_successful_result_serializes_canonical_fields(self) -> None:
        execution = result(
            evidence=(EVIDENCE,),
            artifacts=(ARTIFACT,),
            usage={"duration_ms": 1000, "total_units": 1, "unit": "operation"},
        )

        payload = execution.to_dict()
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["evidence"], [EVIDENCE])
        self.assertEqual(payload["artifacts"], [ARTIFACT])
        self.assertEqual(payload["output_refs"], [ARTIFACT])
        self.assertFalse(payload["retryable"])
        self.assertEqual(payload["usage"]["unit"], "operation")

    def test_failed_result_preserves_error_retryability(self) -> None:
        execution = result(
            status="failed",
            summary=None,
            error={
                "code": "validation_failed",
                "message": "A deterministic validation failed",
                "retryable": False,
            },
            evidence=(
                {
                    "kind": "command_result",
                    "status": "failed",
                    "summary": "The validation command returned failure",
                },
            ),
        )

        self.assertEqual(execution.status, "failed")
        self.assertFalse(execution.retryable)
        self.assertEqual(execution.to_dict()["error"]["code"], "validation_failed")

    def test_blocked_result_requires_concrete_blocker(self) -> None:
        execution = result(
            status="blocked",
            summary="Execution cannot continue",
            blockers=(NON_HUMAN_BLOCKER,),
            next_actions=({**NEXT_ACTION, "requires_human": False},),
        )
        self.assertEqual(execution.blockers[0]["code"], "capability_unavailable")
        self.assertFalse(execution.next_actions[0]["automatic"])

        with self.assertRaisesRegex(ExecutionContractError, "requires only non-human blockers"):
            result(status="blocked")

    def test_needs_human_requires_human_blocker(self) -> None:
        execution = result(
            status="needs_human",
            blockers=(BLOCKER,),
            next_actions=(NEXT_ACTION,),
        )
        self.assertEqual(execution.status, "needs_human")

    def test_artifact_compatibility_alias_cannot_diverge(self) -> None:
        execution = result(output_refs=(ARTIFACT,))
        self.assertEqual(execution.artifacts, execution.output_refs)
        with self.assertRaisesRegex(ExecutionContractError, "same references"):
            result(
                output_refs=(ARTIFACT,),
                artifacts=(
                    {"ref_type": "artifact", "ref": "runtime-output:different"},
                ),
            )

    def test_next_actions_are_representation_only(self) -> None:
        execution = result(
            status="blocked",
            blockers=(NON_HUMAN_BLOCKER,),
            next_actions=({**NEXT_ACTION, "requires_human": False},),
        )
        self.assertFalse(execution.to_dict()["next_actions"][0]["automatic"])
        with self.assertRaisesRegex(ExecutionContractError, "automatic=false"):
            result(
                status="blocked",
                blockers=(NON_HUMAN_BLOCKER,),
                next_actions=(
                    {**NEXT_ACTION, "requires_human": False, "automatic": True},
                ),
            )

    def test_local_deterministic_executor_normalizes_without_provider_prose(self) -> None:
        from runtime.tests.contract_fixtures import certified_fixture_dispatch
        execution_request = request(provider=None)
        with certified_fixture_dispatch(execution_request):
            execution = LocalExecutor().execute(execution_request)
        self.assertEqual(execution.status, "succeeded")
        self.assertIsNone(execution.provider)
        self.assertEqual(execution.evidence[0]["kind"], "deterministic_check")
        self.assertEqual(execution.artifacts, ())

    def test_provider_executor_normalizes_native_output_to_references(self) -> None:
        with bounded_context_repository() as context_root:
            with tempfile.TemporaryDirectory() as temporary:
                adapters = {
                    "claude": FakeProviderAdapter("claude", available=False),
                    "codex": FakeProviderAdapter("codex", available=True),
                }
                execution = ProviderExecutor(
                    ProviderRouter(ProviderConfiguration(REPOSITORY_ROOT), adapters),
                    ExecutionContextBuilder(context_root),
                    FileProviderArtifactStore(Path(temporary) / "provider-output"),
                ).execute(request(provider="claude"))
                self.assertEqual(execution.status, "succeeded")
                self.assertEqual(execution.evidence[0]["kind"], "provider_output")
                self.assertEqual(execution.artifacts, execution.output_refs)
                self.assertNotIn("codex output", json.dumps(execution.to_dict()))

    def test_malformed_status_is_rejected_by_model_and_schema(self) -> None:
        with self.assertRaisesRegex(ExecutionContractError, "not canonical"):
            result(status="maybe")

        payload = result().to_dict()
        payload["status"] = "maybe"
        with self.assertRaises(JobValidationError):
            JobValidator(SCHEMA_PATH).validate(payload)

    def test_schema_and_model_serialization_fields_match(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        payload = result(evidence=(EVIDENCE,), artifacts=(ARTIFACT,)).to_dict()

        self.assertEqual(set(schema["required"]), set(payload))
        self.assertEqual(set(schema["properties"]), set(payload))
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]),
            set(EXECUTION_RESULT_STATUSES),
        )
        JobValidator(SCHEMA_PATH).validate(payload)

    def test_secret_and_hidden_reasoning_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ExecutionContractError, "credential-like"):
            result(summary="API_KEY=fake-secret-value")
        with self.assertRaisesRegex(ExecutionContractError, "sensitive field"):
            result(
                status="failed",
                summary=None,
                error={
                    "code": "provider_failed",
                    "message": "Provider failed safely",
                    "retryable": False,
                    "details": {"chain_of_thought": "must not persist"},
                },
            )

    def test_execution_artifact_schema_version_is_strictly_typed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = FileExecutionStore(Path(temporary))
            canonical_result = result(execution_id="execution-envelope-version")
            path = store.create(None, canonical_result)

            loaded = store.load(canonical_result.execution_id)
            self.assertEqual(loaded.schema_version, 1)
            self.assertEqual(ExecutionRecord(1, None, canonical_result).schema_version, 1)

            artifact = json.loads(path.read_text(encoding="utf-8"))
            for invalid_version in (True, False, 0, 2, "1"):
                with self.subTest(schema_version=invalid_version):
                    artifact["schema_version"] = invalid_version
                    path.write_text(json.dumps(artifact), encoding="utf-8")
                    with self.assertRaises(ExecutionStoreError):
                        store.load(canonical_result.execution_id)
                    with self.assertRaises(ExecutionStoreError):
                        ExecutionRecord(invalid_version, None, canonical_result)

    def test_legacy_persisted_result_loads_through_narrow_adapter(self) -> None:
        legacy = {
            "execution_id": "execution-legacy-001",
            "job_id": "job-legacy-001",
            "status": "succeeded",
            "output_refs": [ARTIFACT],
            "summary": "Legacy result",
            "error": None,
            "provider": "codex",
            "started_at": "2026-09-20T10:00:00Z",
            "completed_at": "2026-09-20T10:00:01Z",
            "requested_provider": "codex",
            "preferred_provider": "codex",
            "fallback_used": False,
            "fallback_reason": None,
            "execution_mode": "READ_ONLY",
            "dry_run": False,
        }

        execution = ExecutionResult.from_dict(legacy)
        self.assertEqual(execution.artifacts, (ARTIFACT,))
        self.assertEqual(execution.evidence, ())
        self.assertFalse(execution.retryable)
        self.assertEqual(execution.schema_version, 1)

    def test_nested_canonical_values_are_deeply_immutable(self) -> None:
        mutable_evidence = {**EVIDENCE, "ref": dict(ARTIFACT)}
        mutable_details = {"attempt": 1}
        execution = result(
            status="failed",
            summary=None,
            error={
                "code": "provider_failed",
                "message": "Provider failed safely",
                "retryable": False,
                "details": mutable_details,
            },
            evidence=(mutable_evidence,),
        )
        mutable_evidence["summary"] = "mutated"
        mutable_evidence["ref"]["ref"] = "runtime-output:mutated"
        mutable_details["attempt"] = 2

        self.assertEqual(execution.evidence[0]["summary"], EVIDENCE["summary"])
        self.assertEqual(execution.evidence[0]["ref"]["ref"], ARTIFACT["ref"])
        self.assertEqual(execution.error["details"]["attempt"], 1)
        with self.assertRaises(TypeError):
            execution.evidence[0]["summary"] = "mutated"
        with self.assertRaises(TypeError):
            execution.error["details"]["attempt"] = 2

        human = result(
            status="needs_human",
            artifacts=(ARTIFACT,),
            blockers=(BLOCKER,),
            next_actions=(NEXT_ACTION,),
        )
        for canonical_mapping in (
            human.artifacts[0],
            human.blockers[0],
            human.next_actions[0],
        ):
            with self.assertRaises(TypeError):
                canonical_mapping["mutated"] = True

    def test_immutable_mapping_cannot_be_bypassed_or_aliased(self) -> None:
        details_source = {"attempt": 1}
        error_source = {
            "code": "provider_failed",
            "message": "Provider failed safely",
            "retryable": False,
            "details": details_source,
        }
        execution = result(
            status="failed",
            summary=None,
            error=error_source,
            usage={"duration_ms": 1, "unit": "operation"},
        )

        self.assertIsInstance(execution.error, FrozenMapping)
        self.assertNotIsInstance(execution.error, dict)
        serialized_before = execution.to_dict()
        with self.assertRaises(TypeError):
            dict.__setitem__(execution.error, "credential", "not-persisted")
        with self.assertRaises(TypeError):
            setattr(
                execution.error,
                "_FrozenMapping__values",
                MappingProxyType({"mutated": True}),
            )
        with self.assertRaises(TypeError):
            delattr(execution.error, "_FrozenMapping__values")
        self.assertEqual(execution.to_dict(), serialized_before)
        error_source["message"] = "mutated"
        details_source["attempt"] = 2
        self.assertEqual(execution.error["message"], "Provider failed safely")
        self.assertEqual(execution.error["details"]["attempt"], 1)

        first = FrozenMapping({"z": 1, "a": 2})
        second = FrozenMapping({"a": 2, "z": 1})
        self.assertEqual(list(first), ["a", "z"])
        self.assertEqual(first, second)
        self.assertEqual(
            json.dumps({"value": dict(first)}, sort_keys=True),
            json.dumps({"value": dict(second)}, sort_keys=True),
        )

    def test_persisted_result_cannot_be_changed_after_validation(self) -> None:
        execution = result(
            execution_id="immutable-persistence",
            status="failed",
            summary=None,
            error={
                "code": "provider_failed",
                "message": "Provider failed safely",
                "retryable": False,
                "details": {"attempt": 1},
            },
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = FileExecutionStore(Path(temporary))
            store.create(None, execution)
            with self.assertRaises(TypeError):
                dict.__setitem__(execution.error["details"], "attempt", 2)
            self.assertEqual(
                store.load(execution.execution_id).result.error["details"]["attempt"],
                1,
            )

    def test_artifacts_is_the_canonical_alias_source_at_all_boundaries(self) -> None:
        artifacts_only = result(artifacts=(ARTIFACT,))
        legacy_payload = result().to_dict()
        legacy_payload.pop("artifacts")
        legacy_payload["output_refs"] = [ARTIFACT]
        legacy_only = ExecutionResult.from_dict(legacy_payload)
        both_equal = ExecutionResult.from_dict(
            {**result().to_dict(), "artifacts": [ARTIFACT], "output_refs": [ARTIFACT]}
        )
        self.assertEqual(artifacts_only.artifacts, artifacts_only.output_refs)
        self.assertEqual(legacy_only.artifacts, legacy_only.output_refs)
        self.assertEqual(both_equal.to_dict()["artifacts"], both_equal.to_dict()["output_refs"])
        with self.assertRaisesRegex(ExecutionContractError, "same references"):
            ExecutionResult.from_dict(
                {
                    **result().to_dict(),
                    "artifacts": [ARTIFACT],
                    "output_refs": [
                        {"ref_type": "artifact", "ref": "runtime-output:different"}
                    ],
                }
            )

    def test_status_invariants_are_exclusive(self) -> None:
        with self.assertRaises(ExecutionContractError):
            result(status="failed", error={"code": "x", "message": "x", "retryable": False}, blockers=(NON_HUMAN_BLOCKER,))
        with self.assertRaises(ExecutionContractError):
            result(status="blocked", blockers=(BLOCKER,))
        with self.assertRaises(ExecutionContractError):
            result(status="needs_review", summary=None)
        with self.assertRaises(ExecutionContractError):
            result(status="needs_human", blockers=(NON_HUMAN_BLOCKER,))

    def test_actual_schema_validator_enforces_bounds_and_model_invariants(self) -> None:
        validator = ExecutionResultValidator(SCHEMA_PATH)
        payload = result(evidence=(EVIDENCE,), artifacts=(ARTIFACT,)).to_dict()
        self.assertEqual(validator.validate(payload).to_dict(), payload)

        oversized = dict(payload)
        oversized["evidence"] = [EVIDENCE] * 101
        with self.assertRaises(ExecutionResultValidationError):
            validator.validate(oversized)
        long_summary = dict(payload)
        long_summary["summary"] = "x" * 4001
        with self.assertRaises(ExecutionResultValidationError):
            validator.validate(long_summary)
        conflicting = dict(payload)
        conflicting["output_refs"] = []
        with self.assertRaises(ExecutionResultValidationError):
            validator.validate(conflicting)

    def test_validator_normalizes_artifact_aliases_before_schema_validation(self) -> None:
        validator = ExecutionResultValidator(SCHEMA_PATH)
        canonical = result(artifacts=(ARTIFACT,)).to_dict()
        artifacts_only = dict(canonical)
        artifacts_only.pop("output_refs")
        output_refs_only = dict(canonical)
        output_refs_only.pop("artifacts")

        for payload in (artifacts_only, output_refs_only, canonical):
            validated = validator.validate(payload)
            self.assertEqual(validated.artifacts, (ARTIFACT,))
            self.assertEqual(
                validated.to_dict()["artifacts"],
                validated.to_dict()["output_refs"],
            )

        conflicting = dict(canonical)
        conflicting["output_refs"] = []
        with self.assertRaises(ExecutionResultValidationError):
            validator.validate(conflicting)

        for required_field in ("status", "execution_id", "job_id", "evidence"):
            incomplete = dict(canonical)
            incomplete.pop(required_field)
            with self.subTest(required_field=required_field):
                with self.assertRaises(ExecutionResultValidationError):
                    validator.validate(incomplete)

    def test_error_details_are_flat_bounded_and_secret_safe(self) -> None:
        error = {
            "code": "provider_failed",
            "message": "Provider failed safely",
            "retryable": False,
        }
        with self.assertRaisesRegex(ExecutionContractError, "string value is too long"):
            result(status="failed", summary=None, error={**error, "details": {"note": "x" * 1001}})
        with self.assertRaisesRegex(ExecutionContractError, "bounded JSON scalars"):
            result(status="failed", summary=None, error={**error, "details": {"nested": {"x": 1}}})
        with self.assertRaisesRegex(ExecutionContractError, "sensitive field") as caught:
            result(status="failed", summary=None, error={**error, "details": {"Authorization": "secret-value"}})
        self.assertNotIn("secret-value", str(caught.exception))

    def test_canonical_numeric_values_are_bounded_and_finite(self) -> None:
        base_error = {
            "code": "provider_failed",
            "message": "Provider failed safely",
            "retryable": False,
        }
        accepted_values = (
            CANONICAL_INTEGER_MIN,
            CANONICAL_INTEGER_MAX,
            123.5,
            math.nextafter(float(2**63), 0.0),
            -float(2**63),
        )
        validator = ExecutionResultValidator(SCHEMA_PATH)
        for accepted in accepted_values:
            execution = result(
                status="failed",
                summary=None,
                error={**base_error, "details": {"numeric": accepted}},
            )
            json.dumps(execution.to_dict(), allow_nan=False)
            validator.validate_model(execution)

        for rejected in (
            CANONICAL_INTEGER_MIN - 1,
            CANONICAL_INTEGER_MAX + 1,
            10**5000,
            float(2**63),
            math.nextafter(-float(2**63), float("-inf")),
            1e100,
        ):
            with self.subTest(kind="bounded-number"):
                with self.assertRaisesRegex(ExecutionContractError, "out of bounds"):
                    result(
                        status="failed",
                        summary=None,
                        error={**base_error, "details": {"numeric": rejected}},
                    )
                payload = result(
                    status="failed",
                    summary=None,
                    error={**base_error, "details": {"numeric": 0}},
                ).to_dict()
                payload["error"]["details"]["numeric"] = rejected
                with self.assertRaises(ExecutionResultValidationError):
                    validator.validate(payload)

        for rejected in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(kind="float"):
                with self.assertRaisesRegex(ExecutionContractError, "finite"):
                    result(
                        status="failed",
                        summary=None,
                        error={**base_error, "details": {"numeric": rejected}},
                    )
                payload = result(
                    status="failed",
                    summary=None,
                    error={**base_error, "details": {"numeric": 0}},
                ).to_dict()
                payload["error"]["details"]["numeric"] = rejected
                with self.assertRaises(ExecutionResultValidationError):
                    validator.validate(payload)

        with self.assertRaisesRegex(ExecutionContractError, "bounded non-negative"):
            result(usage={"total_units": CANONICAL_INTEGER_MAX + 1})

    def test_persistence_wraps_unexpected_json_value_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = FileExecutionStore(Path(temporary))
            with patch(
                "runtime.storage.execution_store.json.dump",
                side_effect=ValueError("synthetic serialization failure"),
            ):
                with self.assertRaisesRegex(
                    ExecutionStoreError, "invalid or unserializable canonical data"
                ):
                    store.create(None, result(execution_id="serialization-failure"))

    def test_persistence_wraps_overflow_and_preserves_atomic_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = FileExecutionStore(root)
            existing = result(execution_id="existing-valid-result")
            existing_path = store.create(None, existing)
            original_bytes = existing_path.read_bytes()
            secret_marker = "synthetic-private-payload"

            with patch(
                "runtime.storage.execution_store.json.dump",
                side_effect=OverflowError(secret_marker),
            ):
                with self.assertRaisesRegex(
                    ExecutionStoreError, "invalid or unserializable canonical data"
                ) as caught:
                    store._write(existing_path, {"payload": secret_marker})
            self.assertNotIn(secret_marker, str(caught.exception))
            self.assertEqual(existing_path.read_bytes(), original_bytes)
            self.assertEqual(list(root.glob("*.tmp")), [])

            new_path = root / "new-overflow-result.json"
            with patch(
                "runtime.storage.execution_store.json.dump",
                side_effect=OverflowError(secret_marker),
            ):
                with self.assertRaises(ExecutionStoreError):
                    store._write(new_path, {"payload": secret_marker})
            self.assertFalse(new_path.exists())
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_additional_secret_shapes_are_rejected_and_provider_text_is_redacted(self) -> None:
        telegram = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
        github = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        private_key = "-----BEGIN PRIVATE KEY-----\nSENSITIVE\n-----END PRIVATE KEY-----"
        for secret in (telegram, github, private_key):
            with self.subTest(secret=secret[:8]):
                with self.assertRaisesRegex(ExecutionContractError, "credential-like"):
                    result(summary=secret)
                self.assertNotIn(secret, sanitize_provider_text(secret))

    def test_provider_text_redacts_json_and_config_sensitive_assignments(self) -> None:
        samples = {
            '"api_key":"json-api-value"': "json-api-value",
            '"password": "json-password-value"': "json-password-value",
            "'client_secret': 'single-quoted-value'": "single-quoted-value",
            "authorization=Bearer bearer-value": "bearer-value",
            "refresh_token=refresh-value": "refresh-value",
            '"token": "123456:telegram-shape"': "123456:telegram-shape",
        }
        for text, secret in samples.items():
            with self.subTest(text=text.split(":", 1)[0]):
                sanitized = sanitize_provider_text(text)
                self.assertNotIn(secret, sanitized)
                self.assertIn("[REDACTED]", sanitized)
        ordinary = "Token budgeting and authorization policy are ordinary discussion."
        self.assertEqual(sanitize_provider_text(ordinary), ordinary)

    def test_provider_artifact_persists_only_redacted_assignment_values(self) -> None:
        stdout = (
            '{"api_key":"json-api-value","password":"json-password-value"}\n'
            "authorization=Bearer bearer-value\n"
            "ordinary token discussion remains"
        )
        selection = ProviderSelection(None, "codex", "codex", False, None)
        provider_result = ProviderExecutionResult("succeeded", stdout, "", 0)
        with tempfile.TemporaryDirectory() as temporary:
            store = FileProviderArtifactStore(Path(temporary))
            store.create("redacted-provider-output", selection, provider_result)
            persisted = store.load("redacted-provider-output")["process"]["stdout"]
        for secret in ("json-api-value", "json-password-value", "bearer-value"):
            self.assertNotIn(secret, persisted)
        self.assertIn("ordinary token discussion remains", persisted)

    def test_execution_modules_support_clean_import_orders(self) -> None:
        commands = (
            "from runtime.execution.validation import ExecutionResultValidator",
            "from runtime.execution.models import ExecutionResult",
            "from runtime.storage.execution_store import FileExecutionStore",
            "from runtime.execution.validation import ExecutionResultValidator; "
            "from runtime.storage.execution_store import FileExecutionStore",
            "from runtime.storage.execution_store import FileExecutionStore; "
            "from runtime.execution.validation import ExecutionResultValidator",
        )
        for command in commands:
            with self.subTest(command=command):
                completed = subprocess.run(
                    [sys.executable, "-c", command],
                    cwd=REPOSITORY_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_typed_persistence_round_trips_every_status(self) -> None:
        cases = (
            result(execution_id="roundtrip-succeeded", artifacts=(ARTIFACT,), evidence=(EVIDENCE,)),
            result(execution_id="roundtrip-failed", status="failed", summary=None, error={"code": "failed", "message": "failed", "retryable": True}),
            result(execution_id="roundtrip-blocked", status="blocked", blockers=(NON_HUMAN_BLOCKER,), next_actions=({**NEXT_ACTION, "requires_human": False},)),
            result(execution_id="roundtrip-review", status="needs_review", evidence=(EVIDENCE,)),
            result(execution_id="roundtrip-human", status="needs_human", blockers=(BLOCKER,), next_actions=(NEXT_ACTION,)),
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = FileExecutionStore(Path(temporary))
            for expected in cases:
                store.create(None, expected)
                loaded = store.load(expected.execution_id)
                self.assertIsInstance(loaded.result, ExecutionResult)
                self.assertEqual(loaded.result.to_dict(), expected.to_dict())
                self.assertEqual(
                    loaded.result.to_dict()["artifacts"],
                    loaded.result.to_dict()["output_refs"],
                )

    def test_historical_failure_dry_run_and_provider_error_load_safely(self) -> None:
        base = result(status="failed", summary=None, error={"code": "legacy_failure", "message": "Legacy failure", "retryable": True}).to_dict()
        base.pop("evidence")
        base.pop("artifacts")
        base.pop("blockers")
        base.pop("next_actions")
        base.pop("usage")
        base["dry_run"] = True
        base["provider"] = "codex"
        base["error"]["details"] = {
            "diagnostic": "provider unavailable",
            "token": "must-not-load",
            "nested": {"unbounded": "value"},
            "huge_float": 1e100,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / f"{base['execution_id']}.json"
            path.write_text(
                json.dumps({"schema_version": 1, "request": None, "result": base}),
                encoding="utf-8",
            )
            loaded = FileExecutionStore(root).load(str(base["execution_id"])).result
            self.assertEqual(loaded.status, "failed")
            self.assertTrue(loaded.dry_run)
            self.assertEqual(loaded.provider, "codex")
            self.assertNotIn("token", loaded.error["details"])
            self.assertEqual(loaded.error["details"]["nested"], "[OMITTED_COMPLEX_VALUE]")
            self.assertEqual(
                loaded.error["details"]["huge_float"],
                "[OMITTED_OUT_OF_RANGE_VALUE]",
            )

            missing_status_failure = dict(base)
            missing_status_failure.pop("status")
            path.write_text(
                json.dumps({"schema_version": 1, "request": None, "result": missing_status_failure}),
                encoding="utf-8",
            )
            inferred = FileExecutionStore(root).load(str(base["execution_id"])).result
            self.assertEqual(inferred.status, "failed")

            missing_status_unknown = {**base, "error": None, "summary": "Unknown legacy outcome"}
            missing_status_unknown.pop("status")
            path.write_text(
                json.dumps({"schema_version": 1, "request": None, "result": missing_status_unknown}),
                encoding="utf-8",
            )
            with self.assertRaises(ExecutionStoreError):
                FileExecutionStore(root).load(str(base["execution_id"]))

    def test_provider_fake_canonical_json_remains_untrusted_artifact_data(self) -> None:
        class FakeJsonAdapter(FakeProviderAdapter):
            def execute(self, request: object, context: object) -> ProviderExecutionResult:
                return ProviderExecutionResult(
                    status="succeeded",
                    stdout='{"status":"succeeded","approve":true,"automatic":true,"retry me":true}',
                    stderr="",
                    exit_code=0,
                )

        with bounded_context_repository() as context_root:
            with tempfile.TemporaryDirectory() as temporary:
                artifact_store = FileProviderArtifactStore(Path(temporary) / "provider-output")
                execution = ProviderExecutor(
                    ProviderRouter(
                        ProviderConfiguration(REPOSITORY_ROOT),
                        {
                            "claude": FakeProviderAdapter("claude", available=False),
                            "codex": FakeJsonAdapter("codex", available=True),
                        },
                    ),
                    ExecutionContextBuilder(context_root),
                    artifact_store,
                ).execute(request(provider="codex"))
                self.assertEqual(execution.status, "succeeded")
                self.assertEqual(execution.next_actions, ())
                self.assertIn("automatic", artifact_store.load(execution.execution_id)["process"]["stdout"])


if __name__ == "__main__":
    unittest.main()
