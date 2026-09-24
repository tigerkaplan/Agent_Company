"""Scheduler adapter around the canonical task dispatcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.approvals.runtime import ApprovalRuntime
from runtime.core.dispatch import CanonicalDispatchError, CanonicalTaskDispatcher
from runtime.core.jobs import JobRuntime


class DispatchError(ValueError):
    """Raised when canonical dispatcher/routing configuration cannot resolve a task."""


class CanonicalDispatchAdapter:
    """Resolve a scheduled task through canonical workflow and routing files."""

    def __init__(
        self,
        job_runtime: JobRuntime,
        repository_root: Path | None = None,
        approval_runtime: ApprovalRuntime | None = None,
    ) -> None:
        self.dispatcher = CanonicalTaskDispatcher(
            job_runtime,
            repository_root=repository_root,
            approval_runtime=approval_runtime,
        )

    def dispatch(
        self,
        schedule: dict[str, Any],
        occurrence_key: str,
    ) -> dict[str, Any]:
        input_refs = [*schedule["input_refs"]]
        input_refs.append(
            {
                "ref_type": "other",
                "ref": f"schedule-occurrence:{occurrence_key}",
                "description": "Deterministic scheduler occurrence",
            }
        )
        try:
            return self.dispatcher.dispatch(
                task=schedule["task"],
                task_class=schedule.get("task_class", ""),
                created_by=f"scheduler:{schedule['schedule_id']}:{occurrence_key}",
                input_refs=input_refs,
                project_id=schedule.get("project_id"),
                approval_reason="Scheduled work requires explicit approval before execution",
            )
        except CanonicalDispatchError as error:
            message = str(error)
            if message.startswith("Task class is unresolved"):
                message = (
                    "Scheduled task_class is unresolved; no executable classifier "
                    "exists in Phase 6D"
                )
            raise DispatchError(message) from error
