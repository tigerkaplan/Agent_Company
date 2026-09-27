"""JSON Schema and Python invariant validation for canonical eval records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.core.validation import JobValidationError, JobValidator
from runtime.evals.models import EvalContractError, EvalResult, EvalSpec


def default_eval_spec_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "eval-spec.schema.json"


def default_eval_result_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "eval-result.schema.json"


class EvalValidationError(ValueError):
    """Raised when an eval schema or Python invariant rejects a value."""


class EvalSpecValidator:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_validator = JobValidator(schema_path or default_eval_spec_schema_path())

    def validate(self, value: dict[str, Any]) -> EvalSpec:
        try:
            self.schema_validator.validate(value)
            return EvalSpec.from_dict(value)
        except (JobValidationError, EvalContractError) as error:
            raise EvalValidationError(str(error)) from error

    def validate_model(self, spec: EvalSpec) -> None:
        try:
            self.schema_validator.validate(spec.to_dict())
        except JobValidationError as error:
            raise EvalValidationError(str(error)) from error


class EvalResultValidator:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_validator = JobValidator(schema_path or default_eval_result_schema_path())

    def validate(self, value: dict[str, Any]) -> EvalResult:
        try:
            self.schema_validator.validate(value)
            return EvalResult.from_dict(value)
        except (JobValidationError, EvalContractError) as error:
            raise EvalValidationError(str(error)) from error

    def validate_model(self, result: EvalResult) -> None:
        try:
            self.schema_validator.validate(result.to_dict())
            result.verify_identity()
        except (JobValidationError, EvalContractError) as error:
            raise EvalValidationError(str(error)) from error
