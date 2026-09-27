"""Canonical deterministic EvalRunner."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from runtime.core.jobs import utc_now
from runtime.evals.evaluators import (
    EVALUATOR_REGISTRY,
    EvalContext,
    EvalEvaluatorError,
    Evaluator,
)
from runtime.evals.models import (
    CANONICAL_EVALUATOR_ID,
    FRAMEWORK_VERSION,
    MAX_AGGREGATE_EVIDENCE,
    EvalCheckResult,
    EvalCheckSpec,
    EvalContractError,
    EvalResult,
    EvalSpec,
    eval_input_digests,
)
from runtime.evals.store import FileEvalStore
from runtime.evals.validation import EvalResultValidator, EvalSpecValidator, EvalValidationError
from runtime.execution.models import ExecutionResult
from runtime.execution.validation import ExecutionResultValidationError, ExecutionResultValidator
from runtime.storage.execution_store import FileExecutionStore


class EvalRuntimeError(ValueError):
    """Raised when an evaluation cannot safely start or persist."""


class _EvaluatorOutputError(ValueError):
    """Raised only for deterministic evaluator-output boundary failures."""


@dataclass(frozen=True)
class EvalRun:
    result: EvalResult
    artifact_ref: dict[str, Any] | None


class EvalRunner:
    """Evaluate one exact result without granting or exercising runtime authority."""

    def __init__(
        self,
        store: FileEvalStore | None = None,
        *,
        clock=utc_now,
        registry: Mapping[str, Evaluator] | None = None,
    ) -> None:
        self.store = store
        self.clock = clock
        self.registry = dict(EVALUATOR_REGISTRY if registry is None else registry)
        self.spec_validator = EvalSpecValidator()
        self.result_validator = EvalResultValidator()
        self.execution_validator = ExecutionResultValidator()

    def run_persisted(
        self,
        spec: dict[str, Any] | EvalSpec,
        executions: FileExecutionStore,
    ) -> EvalRun:
        canonical_spec = self._load_spec(spec)
        try:
            execution = executions.load(canonical_spec.execution_id).result
        except ValueError as error:
            raise EvalRuntimeError(
                f"Could not load canonical execution result: {error}"
            ) from error
        return self.run(canonical_spec, execution)

    def run(
        self,
        spec: dict[str, Any] | EvalSpec,
        execution: dict[str, Any] | ExecutionResult,
    ) -> EvalRun:
        canonical_spec = self._load_spec(spec)
        if isinstance(execution, ExecutionResult):
            execution_payload = execution.to_dict()
        elif isinstance(execution, dict):
            execution_payload = deepcopy(execution)
        else:
            raise EvalRuntimeError("Evaluation input must be an ExecutionResult or object")

        try:
            spec_digest, execution_digest = eval_input_digests(
                canonical_spec,
                execution_payload,
            )
        except EvalContractError as error:
            raise EvalRuntimeError(str(error)) from error

        contract_error: str | None = None
        canonical_execution: ExecutionResult | None = None
        try:
            canonical_execution = self.execution_validator.validate(execution_payload)
            if canonical_execution.execution_id != canonical_spec.execution_id:
                contract_error = "EvalSpec execution_id does not match ExecutionResult"
                canonical_execution = None
            elif canonical_execution.job_id != canonical_spec.job_id:
                contract_error = "EvalSpec job_id does not match ExecutionResult"
                canonical_execution = None
        except ExecutionResultValidationError:
            contract_error = "ExecutionResult failed canonical CORE-01 validation"

        trusted_context = EvalContext(
            execution_id=canonical_spec.execution_id,
            execution=execution_payload,
            canonical_result=canonical_execution,
            contract_error=contract_error,
        )
        checks: list[EvalCheckResult] = []
        for trusted_check in canonical_spec.checks:
            if (
                canonical_spec.evaluator_id != CANONICAL_EVALUATOR_ID
                or canonical_spec.evaluator_version != FRAMEWORK_VERSION
            ):
                checks.append(
                    self._error_check(
                        trusted_check,
                        trusted_context,
                        "Unsupported evaluator identity/version; no evaluator executed",
                    )
                )
                continue
            evaluator = self.registry.get(trusted_check.evaluator_type)
            if evaluator is None:
                checks.append(
                    self._error_check(
                        trusted_check,
                        trusted_context,
                        "Evaluator type is not present in the explicit registry",
                    )
                )
                continue
            evaluator_check = EvalCheckSpec.from_dict(trusted_check.to_dict())
            evaluator_context = self._disposable_evaluator_context(trusted_context)
            try:
                evaluated = evaluator.evaluate(evaluator_check, evaluator_context)
            except EvalEvaluatorError:
                checks.append(
                    self._error_check(
                        trusted_check,
                        trusted_context,
                        "Evaluator reported a controlled evaluation error",
                    )
                )
            except Exception:
                checks.append(
                    self._error_check(
                        trusted_check,
                        trusted_context,
                        "Evaluator raised a controlled internal error",
                    )
                )
            else:
                try:
                    checks.append(
                        self._canonical_evaluator_result(trusted_check, evaluated)
                    )
                except _EvaluatorOutputError as error:
                    checks.append(
                        self._error_check(trusted_check, trusted_context, str(error))
                    )

        status = (
            "error" if any(check.status == "error" for check in checks)
            else "fail" if any(check.status == "fail" for check in checks)
            else "pass"
        )
        failures = tuple(
            check.check_id for check in checks if check.status in {"fail", "error"}
        )
        evidence = self._aggregate_evidence(checks)
        try:
            result = EvalResult.create(
                spec_digest=spec_digest,
                execution_digest=execution_digest,
                spec_id=canonical_spec.spec_id,
                execution_id=canonical_spec.execution_id,
                job_id=canonical_spec.job_id,
                evaluator_id=canonical_spec.evaluator_id,
                evaluator_version=canonical_spec.evaluator_version,
                status=status,
                checks=tuple(checks),
                score=None,
                evidence=evidence,
                failures=failures,
                warnings=(),
                metadata=canonical_spec.metadata,
                created_at=self.clock(),
            )
        except EvalContractError as error:
            raise EvalRuntimeError(f"Generated EvalResult is invalid: {error}") from error
        try:
            self.result_validator.validate_model(result)
        except EvalValidationError as error:
            raise EvalRuntimeError(f"Generated EvalResult failed validation: {error}") from error

        if self.store is None:
            return EvalRun(result=result, artifact_ref=None)
        try:
            persisted = self.store.create(result)
        except ValueError as error:
            raise EvalRuntimeError(f"Could not persist EvalResult: {error}") from error
        return EvalRun(
            result=persisted,
            artifact_ref={
                "ref_type": "artifact",
                "ref": f"runtime-eval:{persisted.eval_id}",
                "description": "Canonical deterministic EvalResult",
            },
        )

    def _load_spec(self, value: dict[str, Any] | EvalSpec) -> EvalSpec:
        try:
            if isinstance(value, EvalSpec):
                self.spec_validator.validate_model(value)
                return self.spec_validator.validate(deepcopy(value.to_dict()))
            if isinstance(value, dict):
                return self.spec_validator.validate(deepcopy(value))
        except EvalValidationError as error:
            raise EvalRuntimeError(f"EvalSpec validation failed: {error}") from error
        raise EvalRuntimeError("EvalSpec must be a canonical object")

    @staticmethod
    def _disposable_evaluator_context(context: EvalContext) -> EvalContext:
        canonical_result = (
            None
            if context.canonical_result is None
            else ExecutionResult.from_dict(context.canonical_result.to_dict())
        )
        return EvalContext(
            execution_id=context.execution_id,
            execution=deepcopy(context.execution),
            canonical_result=canonical_result,
            contract_error=context.contract_error,
        )

    @staticmethod
    def _canonical_evaluator_result(
        check: EvalCheckSpec,
        evaluated: object,
    ) -> EvalCheckResult:
        if not isinstance(evaluated, EvalCheckResult):
            raise _EvaluatorOutputError(
                "Evaluator did not return a canonical EvalCheckResult"
            )
        try:
            canonical = EvalCheckResult.from_dict(evaluated.to_dict())
        except Exception as error:
            raise _EvaluatorOutputError(
                "Evaluator returned a malformed canonical EvalCheckResult"
            ) from error
        expected_identity = (
            check.check_id,
            check.evaluator_type,
            check.severity,
        )
        returned_identity = (
            canonical.check_id,
            canonical.evaluator_type,
            canonical.severity,
        )
        if returned_identity != expected_identity:
            raise _EvaluatorOutputError(
                "Evaluator result identity does not match the originating EvalCheckSpec"
            )
        return canonical

    @staticmethod
    def _error_check(
        check,
        context: EvalContext,
        message: str,
    ) -> EvalCheckResult:
        return EvalCheckResult(
            check_id=check.check_id,
            evaluator_type=check.evaluator_type,
            status="error",
            severity=check.severity,
            expected="successful deterministic evaluator execution",
            observed="controlled evaluator error",
            message=message[:2000],
            evidence=(context.execution_reference,),
        )

    @staticmethod
    def _aggregate_evidence(
        checks: list[EvalCheckResult],
    ) -> tuple[dict[str, Any], ...]:
        values: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for check in checks:
            for reference in check.evidence:
                key = (str(reference["ref_type"]), str(reference["ref"]))
                if key not in seen:
                    values.append(dict(reference))
                    seen.add(key)
                    if len(values) == MAX_AGGREGATE_EVIDENCE:
                        return tuple(values)
        return tuple(values)
