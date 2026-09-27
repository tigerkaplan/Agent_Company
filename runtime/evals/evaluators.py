"""Explicit deterministic evaluator registry for CORE-03."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from runtime.evals.models import (
    EVALUATOR_TYPES,
    FIELD_MATCH_PATHS,
    EvalCheckResult,
    EvalCheckSpec,
)
from runtime.execution.models import (
    EVIDENCE_KINDS,
    EVIDENCE_STATUSES,
    EXECUTION_RESULT_STATUSES,
    REFERENCE_TYPES,
    ExecutionResult,
)


_MISSING = object()


class EvalEvaluatorError(ValueError):
    """Raised for controlled evaluator configuration/runtime errors."""


@dataclass(frozen=True)
class EvalContext:
    execution_id: str
    execution: dict[str, Any]
    canonical_result: ExecutionResult | None
    contract_error: str | None

    @property
    def execution_reference(self) -> dict[str, Any]:
        return {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{self.execution_id}",
            "description": "Canonical execution result evaluated by CORE-03",
        }

    def require_result(self) -> ExecutionResult:
        if self.canonical_result is None:
            raise EvalEvaluatorError(
                "Canonical ExecutionResult validation failed; dependent check was not executed"
            )
        return self.canonical_result


class Evaluator(Protocol):
    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        ...


def _config(
    check: EvalCheckSpec,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    value = dict(check.config)
    allowed = required | (optional or set())
    if set(value) != required and not (required.issubset(value) and set(value) <= allowed):
        raise EvalEvaluatorError(
            f"{check.evaluator_type} configuration fields are incomplete or unexpected"
        )
    return value


def _result(
    check: EvalCheckSpec,
    status: str,
    expected: Any,
    observed: Any,
    message: str,
    context: EvalContext,
    *,
    evidence: tuple[dict[str, Any], ...] = (),
) -> EvalCheckResult:
    refs = (context.execution_reference, *evidence)
    deduplicated: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for reference in refs:
        key = (str(reference.get("ref_type")), str(reference.get("ref")))
        if key not in seen:
            deduplicated.append(reference)
            seen.add(key)
    return EvalCheckResult(
        check_id=check.check_id,
        evaluator_type=check.evaluator_type,
        status=status,
        severity=check.severity,
        expected=expected,
        observed=observed,
        message=message,
        evidence=tuple(deduplicated),
    )


class ExecutionResultContractEvaluator:
    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        _config(check, required=set())
        if context.contract_error is not None:
            return _result(
                check,
                "error",
                "valid canonical ExecutionResult",
                "invalid canonical ExecutionResult",
                context.contract_error,
                context,
            )
        result = context.require_result()
        aliases_match = result.artifacts == result.output_refs
        actions_inert = all(action["automatic"] is False for action in result.next_actions)
        if not aliases_match or not actions_inert:
            return _result(
                check,
                "error",
                "canonical artifacts and inert next_actions",
                "cross-field invariant mismatch",
                "ExecutionResult failed CORE-01 cross-field invariants",
                context,
            )
        return _result(
            check,
            "pass",
            "valid canonical ExecutionResult",
            "valid canonical ExecutionResult",
            "ExecutionResult passed schema and CORE-01 model validation",
            context,
        )


class ExpectedStatusEvaluator:
    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        config = _config(check, required={"expected_status"})
        expected = config["expected_status"]
        if expected not in EXECUTION_RESULT_STATUSES:
            raise EvalEvaluatorError("EXPECTED_STATUS expected_status is not canonical")
        actual = context.require_result().status
        passed = actual == expected
        return _result(
            check,
            "pass" if passed else "fail",
            expected,
            actual,
            "Execution status matched expectation" if passed else "Execution status did not match expectation",
            context,
        )


class RequiredEvidenceEvaluator:
    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        config = _config(check, required={"required"})
        required = config["required"]
        if not isinstance(required, (list, tuple)) or not 1 <= len(required) <= 50:
            raise EvalEvaluatorError("REQUIRED_EVIDENCE required must contain 1-50 selectors")
        evidence = context.require_result().evidence
        matched_refs: list[dict[str, Any]] = []
        missing = 0
        for selector in required:
            if not isinstance(selector, Mapping) or not selector or set(selector) - {"kind", "status", "ref"}:
                raise EvalEvaluatorError("REQUIRED_EVIDENCE selector is malformed")
            if "kind" in selector and selector["kind"] not in EVIDENCE_KINDS:
                raise EvalEvaluatorError("REQUIRED_EVIDENCE selector kind is not canonical")
            if "status" in selector and selector["status"] not in EVIDENCE_STATUSES:
                raise EvalEvaluatorError("REQUIRED_EVIDENCE selector status is not canonical")
            if "ref" in selector and (not isinstance(selector["ref"], str) or not selector["ref"]):
                raise EvalEvaluatorError("REQUIRED_EVIDENCE selector ref is invalid")
            match = next(
                (
                    item for item in evidence
                    if ("kind" not in selector or item["kind"] == selector["kind"])
                    and ("status" not in selector or item["status"] == selector["status"])
                    and (
                        "ref" not in selector
                        or (item.get("ref") is not None and item["ref"]["ref"] == selector["ref"])
                    )
                ),
                None,
            )
            if match is None:
                missing += 1
            elif match.get("ref") is not None:
                matched_refs.append(dict(match["ref"]))
        found = len(required) - missing
        passed = missing == 0
        return _result(
            check,
            "pass" if passed else "fail",
            len(required),
            found,
            "All required evidence entries are present" if passed else f"{missing} required evidence selector(s) were not satisfied",
            context,
            evidence=tuple(matched_refs),
        )


class RequiredArtifactsEvaluator:
    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        config = _config(check, required={"required"})
        required = config["required"]
        if not isinstance(required, (list, tuple)) or not 1 <= len(required) <= 50:
            raise EvalEvaluatorError("REQUIRED_ARTIFACTS required must contain 1-50 references")
        artifacts = context.require_result().artifacts
        matches: list[dict[str, Any]] = []
        for selector in required:
            if (
                not isinstance(selector, Mapping)
                or set(selector) != {"ref_type", "ref"}
                or selector.get("ref_type") not in REFERENCE_TYPES
                or not isinstance(selector.get("ref"), str)
                or not selector["ref"]
            ):
                raise EvalEvaluatorError("REQUIRED_ARTIFACTS reference selector is malformed")
            match = next(
                (
                    artifact for artifact in artifacts
                    if artifact["ref_type"] == selector["ref_type"] and artifact["ref"] == selector["ref"]
                ),
                None,
            )
            if match is not None:
                matches.append(dict(match))
        passed = len(matches) == len(required)
        return _result(
            check,
            "pass" if passed else "fail",
            len(required),
            len(matches),
            "All required artifacts are present" if passed else f"{len(required) - len(matches)} required artifact(s) are missing",
            context,
            evidence=tuple(matches),
        )


class ForbiddenConditionsEvaluator:
    _FIELDS = {
        "forbidden_statuses",
        "forbid_blockers",
        "forbid_human_blockers",
        "forbid_retryable",
        "forbidden_next_actions",
    }

    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        config = dict(check.config)
        if not config or set(config) - self._FIELDS:
            raise EvalEvaluatorError("FORBIDDEN_CONDITIONS configuration is empty or unexpected")
        result = context.require_result()
        violations: list[str] = []
        statuses = config.get("forbidden_statuses", ())
        if not isinstance(statuses, (list, tuple)) or any(status not in EXECUTION_RESULT_STATUSES for status in statuses):
            raise EvalEvaluatorError("FORBIDDEN_CONDITIONS forbidden_statuses is malformed")
        if result.status in statuses:
            violations.append("status")
        for name in ("forbid_blockers", "forbid_human_blockers", "forbid_retryable"):
            if name in config and config[name] is not True:
                raise EvalEvaluatorError(f"FORBIDDEN_CONDITIONS {name} must be true when present")
        if config.get("forbid_blockers") and result.blockers:
            violations.append("blockers")
        if config.get("forbid_human_blockers") and any(item["requires_human"] for item in result.blockers):
            violations.append("human_blockers")
        if config.get("forbid_retryable") and result.retryable:
            violations.append("retryable")
        forbidden_actions = config.get("forbidden_next_actions", ())
        if not isinstance(forbidden_actions, (list, tuple)) or any(
            not isinstance(action, str) or not action for action in forbidden_actions
        ):
            raise EvalEvaluatorError("FORBIDDEN_CONDITIONS forbidden_next_actions is malformed")
        if any(action["action"] in forbidden_actions for action in result.next_actions):
            violations.append("next_actions")
        passed = not violations
        return _result(
            check,
            "pass" if passed else "fail",
            "no configured forbidden condition",
            "none" if passed else ",".join(violations),
            "No forbidden condition was observed" if passed else "One or more forbidden conditions were observed",
            context,
        )


class FieldMatchEvaluator:
    def evaluate(self, check: EvalCheckSpec, context: EvalContext) -> EvalCheckResult:
        config = _config(check, required={"path", "expected"})
        path = config["path"]
        if path not in FIELD_MATCH_PATHS:
            raise EvalEvaluatorError("FIELD_MATCH path is not in the bounded allowlist")
        value: Any = context.require_result().to_dict()
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = _MISSING
                break
            value = value[part]
        expected = config["expected"]
        if isinstance(expected, (dict, list, tuple)):
            raise EvalEvaluatorError("FIELD_MATCH expected value must be a JSON scalar")
        passed = (
            value is not _MISSING
            and value == expected
            and type(value) is type(expected)
        )
        render = lambda item: json.dumps(item, sort_keys=True, ensure_ascii=True, allow_nan=False)
        return _result(
            check,
            "pass" if passed else "fail",
            render(expected),
            "MISSING" if value is _MISSING else render(value),
            (
                "Structured field matched"
                if passed
                else "Structured field is missing"
                if value is _MISSING
                else "Structured field did not match"
            ),
            context,
        )


EVALUATOR_REGISTRY: dict[str, Evaluator] = {
    "EXECUTION_RESULT_CONTRACT": ExecutionResultContractEvaluator(),
    "EXPECTED_STATUS": ExpectedStatusEvaluator(),
    "REQUIRED_EVIDENCE": RequiredEvidenceEvaluator(),
    "REQUIRED_ARTIFACTS": RequiredArtifactsEvaluator(),
    "FORBIDDEN_CONDITIONS": ForbiddenConditionsEvaluator(),
    "FIELD_MATCH": FieldMatchEvaluator(),
}

if set(EVALUATOR_REGISTRY) != EVALUATOR_TYPES:
    raise RuntimeError("Canonical evaluator registry is out of sync with evaluator types")
