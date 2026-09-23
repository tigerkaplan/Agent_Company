"""Build one bounded provider-neutral package from canonical references."""

from __future__ import annotations

from pathlib import Path

from runtime.execution.models import ExecutionRequest
from runtime.providers.models import ContextEntry, ExecutionPackage


class ContextBuildError(ValueError):
    """Raised when canonical execution context cannot be loaded safely."""


class ExecutionContextBuilder:
    """Load only governance and Worker-resolved canonical context files."""

    def __init__(
        self,
        repository_root: Path,
        *,
        max_file_bytes: int = 128 * 1024,
        max_total_bytes: int = 512 * 1024,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

    def build(self, request: ExecutionRequest) -> ExecutionPackage:
        refs = [
            {
                "ref_type": "file",
                "ref": "CONSTITUTION.md",
                "description": "Canonical company governance",
            },
            {
                "ref_type": "file",
                "ref": "AGENTS.md",
                "description": "Canonical provider-independent operating instructions",
            },
            *request.context_refs,
        ]
        entries: list[ContextEntry] = []
        seen: set[str] = set()
        total_bytes = 0
        for reference in refs:
            if reference.get("ref_type") not in {"file", "project_state"}:
                continue
            relative = reference.get("ref")
            if not isinstance(relative, str) or not relative:
                raise ContextBuildError("Canonical context reference has no file path")
            path = (self.repository_root / relative).resolve()
            try:
                path.relative_to(self.repository_root)
            except ValueError as error:
                raise ContextBuildError(
                    f"Canonical context reference escapes repository root: {relative}"
                ) from error
            normalized = path.relative_to(self.repository_root).as_posix()
            if normalized in seen:
                continue
            if not path.is_file():
                raise ContextBuildError(f"Canonical context file is missing: {normalized}")
            size = path.stat().st_size
            if size > self.max_file_bytes:
                raise ContextBuildError(f"Canonical context file exceeds size limit: {normalized}")
            total_bytes += size
            if total_bytes > self.max_total_bytes:
                raise ContextBuildError("Canonical execution context exceeds total size limit")
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise ContextBuildError(
                    f"Could not read canonical context file {normalized}: {error}"
                ) from error
            entries.append(
                ContextEntry(
                    ref=normalized,
                    description=str(reference.get("description") or "Canonical context"),
                    content=content,
                )
            )
            seen.add(normalized)

        return ExecutionPackage(
            task=request.task,
            task_class=request.task_class,
            project_id=request.project_id,
            agent=request.agent,
            skill=request.skill,
            workflow=request.workflow,
            capability=request.capability,
            risk_level=request.risk_level,
            approval_status=request.approval_status,
            review_required=request.review_required,
            attempt=request.attempt,
            input_refs=request.input_refs,
            context=tuple(entries),
            execution_mode=request.execution_mode,
            execution_scope=request.execution_scope,
            dry_run=request.dry_run,
        )
