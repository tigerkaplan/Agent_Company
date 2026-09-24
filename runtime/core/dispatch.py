"""Canonical routing bridge for bounded non-human runtime ingress."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.approvals.store import FileApprovalStore
from runtime.core.jobs import JobRuntime, RuntimeError


class CanonicalDispatchError(ValueError):
    """Raised when canonical routing cannot safely resolve an ingress signal."""


class CanonicalTaskDispatcher:
    """Resolve task intent through tracked routing and create approval-gated work."""

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
        *,
        task: str,
        task_class: str,
        created_by: str,
        input_refs: list[dict[str, Any]],
        approval_reason: str,
        project_id: str | None = None,
        request_approval: bool = True,
    ) -> dict[str, Any]:
        existing = self.find_existing(created_by)
        if existing is not None:
            if request_approval:
                return self._finish_governance_transition(existing, approval_reason)
            return existing
        if not task_class:
            raise CanonicalDispatchError(
                "Task class is unresolved; no executable classifier is available"
            )
        if self._SAFE_NAME.fullmatch(task_class) is None:
            raise CanonicalDispatchError("Task class contains unsupported characters")

        workflow_name = task_class.replace("_", "-")
        workflow_path = (
            self.repository_root
            / "orchestrator"
            / "workflows"
            / f"{workflow_name}.yaml"
        )
        workflow = self._top_level_scalar(workflow_path, "workflow")
        if workflow != workflow_name:
            raise CanonicalDispatchError(
                f"Canonical workflow {workflow!r} does not match resolved workflow "
                f"{workflow_name!r} for task class {task_class!r}"
            )
        agent = self._top_level_scalar(workflow_path, "initial_agent")
        capability = self._task_class_capability(task_class)
        payload: dict[str, Any] = {
            "task": task,
            "task_class": task_class,
            "agent": agent,
            "workflow": workflow,
            "capability": capability,
            "risk_level": "approval_required",
            "approval_status": "required",
            "review_required": True,
            "max_attempts": 1,
            "input_refs": [*input_refs],
            "output_refs": [],
            "created_by": created_by,
        }
        if project_id is not None:
            payload["project_id"] = project_id
        try:
            job = self.job_runtime.create(payload)
            if not request_approval:
                return job
            approval = self.approval_runtime.request_execution(
                job["job_id"], reason=approval_reason
            )
            if approval.job is None:
                raise CanonicalDispatchError(
                    "Approval request did not return canonical job state"
                )
            return approval.job
        except (RuntimeError, ApprovalRuntimeError) as error:
            raise CanonicalDispatchError(
                f"Canonical job creation failed: {error}"
            ) from error

    def find_existing(self, created_by: str) -> dict[str, Any] | None:
        """Return the one canonical job for deterministic ingress provenance."""
        try:
            matches = [
                job for job in self.job_runtime.list() if job["created_by"] == created_by
            ]
        except RuntimeError as error:
            raise CanonicalDispatchError(
                f"Could not inspect ingress jobs: {error}"
            ) from error
        if len(matches) > 1:
            raise CanonicalDispatchError(
                f"Multiple jobs exist for one ingress signal: {created_by}"
            )
        return matches[0] if matches else None

    def _finish_governance_transition(
        self, job: dict[str, Any], approval_reason: str
    ) -> dict[str, Any]:
        if job["status"] in {"created", "waiting_approval"}:
            try:
                approval = self.approval_runtime.request_execution(
                    job["job_id"], reason=approval_reason
                )
                if approval.job is None:
                    raise CanonicalDispatchError(
                        "Approval request did not return canonical job state"
                    )
                return approval.job
            except (RuntimeError, ApprovalRuntimeError) as error:
                raise CanonicalDispatchError(
                    f"Could not finish ingress governance transition: {error}"
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
        raise CanonicalDispatchError(
            f"No canonical capability default exists for task class: {task_class}"
        )

    def _top_level_scalar(self, path: Path, name: str) -> str:
        pattern = re.compile(rf"{re.escape(name)}:\s*(\S.*)")
        for line in self._read_lines(path):
            match = pattern.fullmatch(line)
            if match:
                return match.group(1).strip()
        raise CanonicalDispatchError(
            f"Canonical field {name} is missing in {self._relative(path)}"
        )

    def _read_lines(self, path: Path) -> list[str]:
        if not path.is_file():
            raise CanonicalDispatchError(
                f"Canonical routing file is missing: {self._relative(path)}"
            )
        try:
            return path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise CanonicalDispatchError(
                f"Could not read canonical routing file {self._relative(path)}: {error}"
            ) from error

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repository_root).as_posix()
        except ValueError:
            return str(path)
