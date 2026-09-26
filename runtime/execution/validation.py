"""Canonical JSON Schema and Python invariant validation for execution results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.core.validation import JobValidationError, JobValidator
from runtime.execution.models import ExecutionContractError, ExecutionResult


def default_execution_result_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "execution-result.schema.json"


class ExecutionResultValidationError(ValueError):
    """Raised when schema or model validation rejects an execution result."""


class ExecutionResultValidator:
    """Enforce declared schema constraints and Python-only cross-field invariants."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_validator = JobValidator(
            schema_path or default_execution_result_schema_path()
        )

    def validate(self, value: dict[str, Any]) -> ExecutionResult:
        try:
            canonical_payload = self._normalise_artifact_aliases(value)
            self.schema_validator.validate(canonical_payload)
            return ExecutionResult.from_dict(canonical_payload)
        except (JobValidationError, ExecutionContractError) as error:
            raise ExecutionResultValidationError(str(error)) from error

    @staticmethod
    def _normalise_artifact_aliases(value: dict[str, Any]) -> dict[str, Any]:
        """Normalize only the one declared compatibility alias before schema checks."""
        if not isinstance(value, dict):
            raise ExecutionContractError("ExecutionResult payload must be an object")
        canonical_payload = dict(value)
        has_artifacts = "artifacts" in canonical_payload
        has_output_refs = "output_refs" in canonical_payload
        if (
            has_artifacts
            and has_output_refs
            and canonical_payload["artifacts"] != canonical_payload["output_refs"]
        ):
            raise ExecutionContractError(
                "ExecutionResult.output_refs and artifacts must contain the same references"
            )
        if has_artifacts and not has_output_refs:
            canonical_payload["output_refs"] = canonical_payload["artifacts"]
        elif has_output_refs and not has_artifacts:
            canonical_payload["artifacts"] = canonical_payload["output_refs"]
        return canonical_payload

    def validate_model(self, result: ExecutionResult) -> None:
        try:
            self.schema_validator.validate(result.to_dict())
        except JobValidationError as error:
            raise ExecutionResultValidationError(str(error)) from error
