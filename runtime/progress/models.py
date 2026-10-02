"""Small, closed progress vocabulary; no provider prose or authority fields."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from runtime.core.validation import JobValidator


class ProgressError(ValueError):
    """Progress integrity/persistence failed; execution must not proceed."""


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProgressEvent:
    event_type: str
    logical_job_id: str
    job_id: str
    execution_id: str | None = None
    step_id: str | None = None
    detail: str = "none"
    evidence_id: str | None = None
    schema_version: int = 1
    authoritative: bool = False

    def __post_init__(self):
        try:
            _VALIDATOR.validate(asdict(self))
        except ValueError as error:
            raise ProgressError("Invalid progress event") from error
        if self.event_type.startswith("step_") and self.step_id is None:
            raise ProgressError("Step events require a canonical step")
        if self.event_type.startswith(("execution_", "tool_")) and self.execution_id is None:
            raise ProgressError("Execution/tool events require an execution identity")
        if self.event_type == "task_gate_observed" and (
                self.detail not in {"created", "review"} or self.execution_id is not None
                or self.evidence_id is None or len(self.evidence_id) != 64
                or any(character not in "0123456789abcdef" for character in self.evidence_id)):
            raise ProgressError("Task gate observations require bounded canonical evidence")

    def to_dict(self):
        return asdict(self)

    @property
    def event_id(self):
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value):
        try:
            _VALIDATOR.validate(value)
            return cls(**value)
        except (ValueError, TypeError) as error:
            raise ProgressError("Invalid persisted progress event") from error


_VALIDATOR = JobValidator(Path(__file__).resolve().parents[2] / "schemas" / "progress-event.schema.json")
