"""Canonical Phase 8B state-root resolution and fixed path layout."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from runtime.host.config import HostConfig


class StatePathError(ValueError):
    """Raised when a state root or derived path is unsafe."""


_LAYOUT = {
    "jobs": ("jobs",),
    "executions": ("executions",),
    "approvals": ("approvals",),
    "schedules": ("schedules",),
    "scheduler": ("scheduler-runtime",),
    "remote": ("remote",),
    "telegram": ("remote", "telegram"),
    "notifications": ("notifications",),
    "webhooks": ("webhooks",),
    "git": ("executions", "git"),
    "locks": ("locks",),
    "audit": ("audit",),
}
_CANONICAL_TOP_LEVEL = frozenset(parts[0] for parts in _LAYOUT.values())

PERSISTENT_STATE_KEYS = (
    "jobs",
    "executions",
    "approvals",
    "schedules",
    "scheduler",
    "remote",
    "telegram",
    "notifications",
    "webhooks",
    "git",
    "audit",
)
EPHEMERAL_STATE_KEYS = ("locks",)


@dataclass(frozen=True)
class StatePaths:
    base_root: Path
    repository_root: Path
    environment_mode: str
    source: str

    @classmethod
    def resolve(
        cls,
        repository_root: Path,
        config: HostConfig,
        *,
        cli_root: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> "StatePaths":
        values = os.environ if environment is None else environment
        repository = Path(repository_root).resolve()
        configured: str | Path | None
        if cli_root is not None:
            configured = cli_root
            source = "cli"
        elif values.get("AGENT_COMPANY_STATE_ROOT"):
            configured = values["AGENT_COMPANY_STATE_ROOT"]
            source = "environment"
        elif config.state_root is not None:
            configured = config.state_root
            source = "host_config"
        else:
            if config.environment_mode == "host":
                raise StatePathError(
                    "Host mode requires an explicit canonical state root from "
                    "CLI, environment, or host config"
                )
            configured = repository / "runtime" / "state"
            source = "local_default"

        raw = Path(configured)
        if source != "local_default":
            if ".." in raw.parts:
                raise StatePathError("Canonical state root must not contain traversal")
            if not raw.is_absolute():
                raise StatePathError("Canonical state root must be absolute")
            if raw.exists() and raw.is_symlink():
                raise StatePathError("Canonical state root must not be a symlink")
        root = raw.resolve(strict=False)
        if root == Path(root.anchor):
            raise StatePathError("Canonical state root must not be a filesystem root")
        if cls._overlaps(root, repository / ".git"):
            raise StatePathError("Canonical state root must not be inside Git metadata")
        if cls._overlaps(root, repository):
            local_root = (repository / "runtime" / "state").resolve(strict=False)
            if source != "local_default" and root != local_root:
                raise StatePathError(
                    "Canonical state root must not overlap the source repository"
                )
            if config.environment_mode == "host":
                raise StatePathError(
                    "Host-mode canonical state root must be outside the source repository"
                )
        local_root = (repository / "runtime" / "state").resolve(strict=False)
        explicit_local_compatibility = (
            config.environment_mode == "local" and root == local_root
        )
        if source != "local_default" and not explicit_local_compatibility:
            cls._validate_dedicated_root(root)
        return cls(
            base_root=root,
            repository_root=repository,
            environment_mode=config.environment_mode,
            source=source,
        )

    def path(self, key: str) -> Path:
        try:
            parts = _LAYOUT[key]
        except KeyError as error:
            raise StatePathError(f"Unknown canonical state path: {key}") from error
        candidate = self.base_root.joinpath(*parts)
        resolved = candidate.resolve(strict=False)
        if not self._contained(resolved, self.base_root):
            raise StatePathError(f"Canonical state path escapes base root: {key}")
        return candidate

    def directories(self) -> tuple[Path, ...]:
        ordered = [self.base_root]
        for key in (*PERSISTENT_STATE_KEYS, *EPHEMERAL_STATE_KEYS):
            path = self.path(key)
            if path not in ordered:
                ordered.append(path)
        return tuple(ordered)

    def relative_layout(self) -> dict[str, str]:
        return {
            key: Path(*parts).as_posix()
            for key, parts in _LAYOUT.items()
        }

    def component_root(
        self,
        key: str,
        *,
        explicit: Path | None,
        legacy_environment_name: str,
        environment: Mapping[str, str] | None = None,
    ) -> Path:
        if explicit is not None:
            candidate = Path(explicit)
            if self.source != "local_default":
                if not candidate.is_absolute():
                    raise StatePathError(
                        "Component state override must be absolute when a canonical "
                        "base root is configured"
                    )
                if candidate.resolve(strict=False) != self.path(key).resolve(strict=False):
                    raise StatePathError(
                        "Component state override must equal its canonical path"
                    )
                return self.path(key)
            return candidate
        values = os.environ if environment is None else environment
        if self.source == "local_default" and values.get(legacy_environment_name):
            return Path(values[legacy_environment_name])
        return self.path(key)

    @staticmethod
    def _contained(candidate: Path, parent: Path) -> bool:
        try:
            candidate.resolve(strict=False).relative_to(parent.resolve(strict=False))
        except ValueError:
            return False
        return True

    @classmethod
    def _overlaps(cls, first: Path, second: Path) -> bool:
        return cls._contained(first, second) or cls._contained(second, first)

    @classmethod
    def _validate_dedicated_root(cls, root: Path) -> None:
        """Reject broad roots before initialization can create or chmod anything."""
        if root.exists() and root.is_symlink():
            raise StatePathError("Canonical state root must not be a symlink")
        anchor = Path(root.anchor)
        relative_parts = root.parts[len(anchor.parts) :]
        if len(relative_parts) < 3:
            raise StatePathError(
                "Canonical state root must be a dedicated path, not a broad directory"
            )
        leaf = re.sub(r"[^a-z0-9]", "", root.name.lower())
        if not leaf.endswith("state") and "agentcompany" not in leaf:
            raise StatePathError(
                "Canonical state root must identify a dedicated Agent Company state directory"
            )
        if not root.exists():
            return
        if not root.is_dir():
            return
        try:
            unexpected = [
                child.name
                for child in root.iterdir()
                if child.is_symlink()
                or not child.is_dir()
                or child.name not in _CANONICAL_TOP_LEVEL
            ]
        except OSError as error:
            raise StatePathError(
                "Canonical state root could not be inspected safely"
            ) from error
        if unexpected:
            raise StatePathError(
                "Canonical state root contains non-canonical entries and is not dedicated"
            )

    def validate_for_initialization(self) -> None:
        local_root = (
            self.repository_root / "runtime" / "state"
        ).resolve(strict=False)
        explicit_local_compatibility = (
            self.environment_mode == "local" and self.base_root == local_root
        )
        if self.source != "local_default" and not explicit_local_compatibility:
            self._validate_dedicated_root(self.base_root)
        if self._overlaps(self.base_root, self.repository_root):
            if self.source != "local_default" or self.base_root != local_root:
                if not explicit_local_compatibility:
                    raise StatePathError(
                        "Canonical state root must not overlap the source repository"
                    )
