"""Minimal bridge from scheduled task intent to canonical job creation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime, RuntimeError


class DispatchError(ValueError):
    """Raised when canonical dispatcher/routing configuration cannot resolve a task."""


class CanonicalDispatchAdapter:
    """Resolve a scheduled task through canonical workflow and routing files."""

    _SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(
        self,
        job_runtime: JobRuntime,
        repository_root: Path | None = None,
        approval_runtime: ApprovalRuntime | None = None,
    ) -> None:
        self.job_runtime = job_runtime
        self.repository_root = (
            Path(repository_root)
            if repository_root is not None
            else Path(__file__).resolve().parents[2]
        ).resolve()
        self.approval_runtime = approval_runtime or ApprovalRuntime(
            job_runtime,
            FileApprovalStore(job_runtime.store.root.parent / "approvals"),
            clock=job_runtime.clock,
        )

    def dispatch(
        self,
        schedule: dict[str, Any],
        occurrence_key: str,
    ) -> dict[str, Any]:
        created_by = f"scheduler:{schedule['schedule_id']}:{occurrence_key}"
        existing = self._find_existing(created_by)
        if existing is not None:
            return self._finish_governance_transition(existing)

        task_class = schedule.get("task_class")
        if not task_class:
            raise DispatchError(
                "Scheduled task_class is unresolved; no executable classifier exists in Phase 6D"
            )
        if self._SAFE_NAME.fullmatch(task_class) is None:
            raise DispatchError("Scheduled task_class contains unsupported characters")

        workflow_path = (
            self.repository_root
            / "orchestrator"
            / "workflows"
            / f"{task_class}.yaml"
        )
        workflow = self._top_level_scalar(workflow_path, "workflow")
        if workflow != task_class:
            raise DispatchError(
                f"Canonical workflow {workflow!r} does not match task class {task_class!r}"
            )
        agent = self._top_level_scalar(workflow_path, "initial_agent")
        capability = self._task_class_capability(task_class)

        input_refs = [*schedule["input_refs"]]
        input_refs.append(
            {
                "ref_type": "other",
                "ref": f"schedule-occurrence:{occurrence_key}",
                "description": "Deterministic scheduler occurrence",
            }
        )
        payload: dict[str, Any] = {
            "task": schedule["task"],
            "task_class": task_class,
            "agent": agent,
            "workflow": workflow,
            "capability": capability,
            "risk_level": "approval_required",
            "approval_status": "required",
            "review_required": True,
            "max_attempts": 1,
            "input_refs": input_refs,
            "output_refs": [],
            "created_by": created_by,
        }
        if "project_id" in schedule:
            payload["project_id"] = schedule["project_id"]

        try:
            job = self.job_runtime.create(payload)
            approval = self.approval_runtime.request_execution(
                job["job_id"],
                reason="Scheduled work requires explicit approval before execution",
            )
            if approval.job is None:
                raise DispatchError("Approval request did not return canonical job state")
            return approval.job
        except (RuntimeError, ApprovalRuntimeError) as error:
            raise DispatchError(f"Canonical job creation failed: {error}") from error

    def _find_existing(self, created_by: str) -> dict[str, Any] | None:
        try:
            matches = [
                job for job in self.job_runtime.list() if job["created_by"] == created_by
            ]
        except RuntimeError as error:
            raise DispatchError(f"Could not inspect occurrence jobs: {error}") from error
        if len(matches) > 1:
            raise DispatchError(
                f"Multiple jobs exist for one scheduled occurrence: {created_by}"
            )
        return matches[0] if matches else None

    def _finish_governance_transition(self, job: dict[str, Any]) -> dict[str, Any]:
        if job["status"] in {"created", "waiting_approval"}:
            try:
                approval = self.approval_runtime.request_execution(
                    job["job_id"],
                    reason="Scheduled work requires explicit approval before execution",
                )
                if approval.job is None:
                    raise DispatchError(
                        "Approval request did not return canonical job state"
                    )
                return approval.job
            except (RuntimeError, ApprovalRuntimeError) as error:
                raise DispatchError(
                    f"Could not finish scheduled job governance transition: {error}"
                ) from error
        return job

    def _task_class_capability(self, task_class: str) -> str:
        path = self.repository_root / "orchestrator" / "routing" / "providers.yaml"
        lines = self._read_lines(path)
        in_resolution = False
        in_defaults = False
        for line in lines:
            if line == "capability_resolution:":
                in_resolution = True
                continue
            if in_resolution and line == "  task_class_defaults:":
                in_defaults = True
                continue
            if in_defaults:
                match = re.fullmatch(
                    r"    ([A-Za-z0-9][A-Za-z0-9._-]*):\s*(\S+)", line
                )
                if match and match.group(1) == task_class:
                    return match.group(2)
                if line and not line.startswith("    "):
                    break
        raise DispatchError(
            f"No canonical capability default exists for task class: {task_class}"
        )

    def _top_level_scalar(self, path: Path, name: str) -> str:
        pattern = re.compile(rf"{re.escape(name)}:\s*(\S.*)")
        for line in self._read_lines(path):
            match = pattern.fullmatch(line)
            if match:
                return match.group(1).strip()
        raise DispatchError(
            f"Canonical field {name} is missing in {self._relative(path)}"
        )

    def _read_lines(self, path: Path) -> list[str]:
        if not path.is_file():
            raise DispatchError(
                f"Canonical routing file is missing: {self._relative(path)}"
            )
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise DispatchError(
                f"Could not read canonical routing file {self._relative(path)}: {error}"
            ) from error

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repository_root).as_posix()
        except ValueError:
            return str(path)
