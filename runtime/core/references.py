"""Resolve canonical execution references from existing repository structures."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from runtime.context.contracts import DiscoveryError, Limits, RepositoryReader


class ReferenceResolutionError(ValueError):
    """Raised when canonical execution configuration is absent or invalid."""


class CanonicalReferenceResolver:
    """Resolve IDs to canonical file references without loading their contents."""

    _SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, repository_root: Path | None = None, *, limits: Limits = Limits()) -> None:
        self.repository_root = (
            Path(repository_root) if repository_root is not None else Path(__file__).resolve().parents[2]
        ).resolve()

        self.limits = limits

    def resolve(self, job: dict[str, Any]) -> tuple[dict[str, str], ...]:
        self._reader = RepositoryReader(self.repository_root, self.limits)
        self._files_read = 0
        references: list[dict[str, str]] = []
        references.extend(self._resolve_agent(job["agent"]))
        if job.get("skill") is not None:
            references.append(self._resolve_skill(job["skill"]))
        references.append(self._resolve_workflow(job["workflow"]))
        references.append(self._resolve_capability(job["capability"]))
        if job.get("project_id") is not None:
            references.extend(self._resolve_project(job["project_id"]))
        return tuple(references)

    def _resolve_agent(self, agent: str) -> list[dict[str, str]]:
        config = self.repository_root / "orchestrator" / "routing" / "agents.yaml"
        entries = self._mapping_section(config, "canonical_agents")
        if agent not in entries:
            raise ReferenceResolutionError(f"Missing canonical agent reference: {agent}")

        references: list[dict[str, str]] = []
        for field in ("role", "guardrails"):
            configured = entries[agent].get(field)
            if configured is None:
                raise ReferenceResolutionError(
                    f"Canonical agent {agent} has no {field} reference"
                )
            path = self._resolve_config_path(config, configured)
            if not path.is_file():
                raise ReferenceResolutionError(
                    f"Canonical agent {agent} {field} file is missing: {self._relative(path)}"
                )
            references.append(
                self._file_ref(path, f"Canonical agent {agent} {field}")
            )
        return references

    def _resolve_skill(self, skill: str) -> dict[str, str]:
        self._require_safe_name(skill, "skill")
        matches = sorted(
            (self.repository_root / "skills").glob(f"*/{skill}/SKILL.md")
        )
        if not matches:
            raise ReferenceResolutionError(f"Missing canonical skill reference: {skill}")
        if len(matches) > 1:
            options = ", ".join(self._relative(path) for path in matches)
            raise ReferenceResolutionError(
                f"Ambiguous canonical skill reference {skill}: {options}"
            )
        return self._file_ref(matches[0], f"Canonical skill {skill}")

    def _resolve_workflow(self, workflow: str) -> dict[str, str]:
        self._require_safe_name(workflow, "workflow")
        path = self.repository_root / "orchestrator" / "workflows" / f"{workflow}.yaml"
        if not path.is_file():
            raise ReferenceResolutionError(
                f"Missing canonical workflow reference: {workflow}"
            )
        declared = self._top_level_scalar(path, "workflow")
        if declared != workflow:
            raise ReferenceResolutionError(
                f"Workflow file {self._relative(path)} declares {declared!r}, expected {workflow!r}"
            )
        return self._file_ref(path, f"Canonical workflow {workflow}")

    def _resolve_capability(self, capability: str) -> dict[str, str]:
        config = self.repository_root / "orchestrator" / "routing" / "capabilities.yaml"
        capabilities = self._mapping_section(config, "capabilities")
        if capability not in capabilities:
            raise ReferenceResolutionError(
                f"Missing canonical capability reference: {capability}"
            )
        return self._file_ref(config, f"Canonical capability {capability}")

    def _resolve_project(self, project_id: str) -> list[dict[str, str]]:
        self._require_safe_name(project_id, "project_id")
        project_root = self.repository_root / "shared" / "projects" / project_id
        if not project_root.is_dir():
            raise ReferenceResolutionError(
                f"Missing canonical project reference: {project_id}"
            )
        continuation = (
            self.repository_root
            / "orchestrator"
            / "workflows"
            / "project-continuation.yaml"
        )
        read_order = self._top_level_list(continuation, "canonical_read_order")
        resolved_project_root = project_root.resolve()
        references: list[dict[str, str]] = []
        for name in read_order:
            path = (project_root / name).resolve()
            try:
                path.relative_to(resolved_project_root)
            except ValueError as error:
                raise ReferenceResolutionError(
                    f"Project read-order reference escapes project root: {name}"
                ) from error
            if path.is_file():
                references.append(
                    {
                        "ref_type": "project_state",
                        "ref": self._relative(path),
                        "description": f"Canonical project state for {project_id}: {name}",
                    }
                )
        if not references:
            raise ReferenceResolutionError(
                f"Project {project_id} has no canonical state files from the configured read order"
            )
        return references

    def _mapping_section(
        self,
        path: Path,
        section: str,
    ) -> dict[str, dict[str, str]]:
        lines = self._read_lines(path)
        entries: dict[str, dict[str, str]] = {}
        in_section = False
        current: str | None = None
        for line in lines:
            if line == f"{section}:":
                in_section = True
                continue
            if not in_section:
                continue
            if line and not line.startswith(" "):
                break
            entry_match = re.fullmatch(r"  ([A-Za-z0-9][A-Za-z0-9._-]*):", line)
            if entry_match:
                current = entry_match.group(1)
                entries[current] = {}
                continue
            field_match = re.fullmatch(
                r"    ([A-Za-z0-9][A-Za-z0-9._-]*):\s*(\S.*)", line
            )
            if current is not None and field_match:
                entries[current][field_match.group(1)] = field_match.group(2).strip()
        if not entries:
            raise ReferenceResolutionError(
                f"Canonical section {section} is missing or empty in {self._relative(path)}"
            )
        return entries

    def _top_level_scalar(self, path: Path, name: str) -> str:
        pattern = re.compile(rf"{re.escape(name)}:\s*(\S.*)")
        for line in self._read_lines(path):
            match = pattern.fullmatch(line)
            if match:
                return match.group(1).strip()
        raise ReferenceResolutionError(
            f"Canonical field {name} is missing in {self._relative(path)}"
        )

    def _top_level_list(self, path: Path, name: str) -> list[str]:
        lines = self._read_lines(path)
        values: list[str] = []
        in_list = False
        for line in lines:
            if line == f"{name}:":
                in_list = True
                continue
            if not in_list:
                continue
            match = re.fullmatch(r"  -\s+(\S.*)", line)
            if match:
                values.append(match.group(1).strip())
                continue
            if line and not line.startswith(" "):
                break
        if not values:
            raise ReferenceResolutionError(
                f"Canonical list {name} is missing or empty in {self._relative(path)}"
            )
        return values

    def _read_lines(self, path: Path) -> list[str]:
        if not path.is_file():
            raise ReferenceResolutionError(
                f"Canonical configuration file is missing: {self._relative(path)}"
            )
        self._files_read += 1
        if self._files_read > self.limits.files:
            raise ReferenceResolutionError('Canonical metadata file count exceeds bound')
        try:
            return self._reader.read(self._relative(path)).splitlines()
        except (OSError, DiscoveryError) as error:
            raise ReferenceResolutionError(
                f"Could not read canonical configuration {self._relative(path)}: {error}"
            ) from error

    def _resolve_config_path(self, config: Path, configured: str) -> Path:
        path = (config.parent / configured).resolve()
        try:
            path.relative_to(self.repository_root)
        except ValueError as error:
            raise ReferenceResolutionError(
                f"Canonical reference escapes repository root: {configured}"
            ) from error
        return path

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repository_root).as_posix()
        except ValueError:
            return str(path)

    def _file_ref(self, path: Path, description: str) -> dict[str, str]:
        return {
            "ref_type": "file",
            "ref": self._relative(path),
            "description": description,
        }

    def _require_safe_name(self, value: str, label: str) -> None:
        if not isinstance(value, str) or self._SAFE_NAME.fullmatch(value) is None:
            raise ReferenceResolutionError(
                f"Canonical {label} contains unsupported path characters"
            )
