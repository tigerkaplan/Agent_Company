"""Load minimal provider runtime JSON referenced by canonical YAML configuration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProviderConfigError(ValueError):
    """Raised when canonical provider or routing configuration is invalid."""


@dataclass(frozen=True)
class CliProviderConfig:
    provider_id: str
    adapter: str
    executable: str
    arguments: tuple[str, ...]
    timeout_seconds: int
    max_stdout_bytes: int
    max_stderr_bytes: int
    controlled_write_arguments: tuple[str, ...] | None = None

    @property
    def supported_execution_modes(self) -> tuple[str, ...]:
        modes = ["READ_ONLY"]
        if self.controlled_write_arguments is not None:
            modes.append("CONTROLLED_WRITE")
        return tuple(modes)

    def arguments_for(self, execution_mode: str) -> tuple[str, ...]:
        if execution_mode == "READ_ONLY":
            return self.arguments
        if execution_mode == "CONTROLLED_WRITE" and self.controlled_write_arguments:
            return self.controlled_write_arguments
        raise ProviderConfigError(
            f"Provider {self.provider_id} does not support execution mode {execution_mode}"
        )


class ProviderConfiguration:
    """Read provider IDs and selection inputs from their canonical files."""

    _NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.routing_root = self.repository_root / "orchestrator" / "routing"
        self.registry = self._load_registry()
        self.provider_order = self._load_provider_order()
        self.weights = self._load_weights()
        self._validate_fallback_policy()

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(self.provider_order)

    def eligible(self, provider_id: str, capability: str) -> bool:
        entry = self._registry_entry(provider_id)
        path = self._resolve_from(self.routing_root / "providers.yaml", entry["capabilities"])
        values = self._indented_scalars(path, "eligibility", indent=0)
        return values.get(capability) == "true"

    def weight(self, provider_id: str, capability: str) -> int:
        path = self.routing_root / "weights.yaml"
        nested = self._nested_scalars(path, "weights")
        try:
            return int(nested[capability][provider_id])
        except (KeyError, ValueError) as error:
            raise ProviderConfigError(
                f"Missing canonical routing weight for {capability}/{provider_id}"
            ) from error

    def supports_execution_mode(self, provider_id: str, execution_mode: str) -> bool:
        return execution_mode in self.cli_config(provider_id).supported_execution_modes

    def cli_config(self, provider_id: str) -> CliProviderConfig:
        entry = self._registry_entry(provider_id)
        provider_yaml = self._resolve_from(
            self.routing_root / "providers.yaml", entry["provider"]
        )
        declared = self._top_level_scalar(provider_yaml, "provider_id")
        if declared != provider_id:
            raise ProviderConfigError(
                f"Provider file declares {declared!r}, expected {provider_id!r}"
            )
        runtime_ref = self._top_level_scalar(provider_yaml, "runtime_config")
        runtime_path = self._resolve_from(provider_yaml, runtime_ref)
        try:
            value = json.loads(runtime_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProviderConfigError(
                f"Could not read provider runtime config {self._relative(runtime_path)}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ProviderConfigError("Provider runtime config must be a JSON object")
        required: dict[str, type] = {
            "provider_id": str,
            "adapter": str,
            "executable": str,
            "arguments": list,
            "timeout_seconds": int,
            "max_stdout_bytes": int,
            "max_stderr_bytes": int,
        }
        for name, expected_type in required.items():
            if not isinstance(value.get(name), expected_type):
                raise ProviderConfigError(
                    f"Provider runtime config field {name} has the wrong type"
                )
        if value["provider_id"] != provider_id:
            raise ProviderConfigError("Provider runtime config identity does not match registry")
        if not all(isinstance(item, str) and item for item in value["arguments"]):
            raise ProviderConfigError("Provider runtime arguments must be non-empty strings")
        controlled = value.get("controlled_write_arguments")
        if controlled is not None and (
            not isinstance(controlled, list)
            or not all(isinstance(item, str) and item for item in controlled)
        ):
            raise ProviderConfigError(
                "Provider controlled-write arguments must be non-empty strings"
            )
        for name in ("timeout_seconds", "max_stdout_bytes", "max_stderr_bytes"):
            if value[name] < 1:
                raise ProviderConfigError(f"Provider runtime config field {name} must be positive")
        return CliProviderConfig(
            provider_id=provider_id,
            adapter=value["adapter"],
            executable=value["executable"],
            arguments=tuple(value["arguments"]),
            timeout_seconds=value["timeout_seconds"],
            max_stdout_bytes=value["max_stdout_bytes"],
            max_stderr_bytes=value["max_stderr_bytes"],
            controlled_write_arguments=(
                tuple(controlled) if controlled is not None else None
            ),
        )

    def _load_registry(self) -> dict[str, dict[str, str]]:
        path = self.routing_root / "providers.yaml"
        values = self._nested_scalars(path, "provider_registry")
        if not values:
            raise ProviderConfigError("Canonical provider registry is empty")
        return values

    def _load_provider_order(self) -> list[str]:
        path = self.routing_root / "providers.yaml"
        values = self._indented_list(path, "provider_order", indent=2)
        if set(values) != set(self.registry):
            raise ProviderConfigError(
                "Configured provider order must contain every registry provider"
            )
        return values

    def _load_weights(self) -> dict[str, dict[str, str]]:
        return self._nested_scalars(self.routing_root / "weights.yaml", "weights")

    def _validate_fallback_policy(self) -> None:
        path = self.routing_root / "fallback.yaml"
        content = self._read(path)
        required = (
            "select_next_highest_weight_eligible_available_provider",
            "preserve_selected_canonical_agent_skill_workflow_and_context",
            "record_fallback_and_reason_in_execution_output",
        )
        if any(value not in content for value in required):
            raise ProviderConfigError("Canonical provider fallback policy is incomplete")

    def _registry_entry(self, provider_id: str) -> dict[str, str]:
        try:
            return self.registry[provider_id]
        except KeyError as error:
            raise ProviderConfigError(
                f"Provider is not in canonical registry: {provider_id}"
            ) from error

    def _nested_scalars(self, path: Path, section: str) -> dict[str, dict[str, str]]:
        lines = self._read(path).splitlines()
        values: dict[str, dict[str, str]] = {}
        active = False
        current: str | None = None
        for line in lines:
            if line == f"{section}:":
                active = True
                continue
            if not active:
                continue
            if line and not line.startswith(" "):
                break
            parent = re.fullmatch(r"  ([A-Za-z0-9][A-Za-z0-9._-]*):", line)
            if parent:
                current = parent.group(1)
                values[current] = {}
                continue
            child = re.fullmatch(
                r"    ([A-Za-z0-9][A-Za-z0-9._-]*):\s*(\S.*)", line
            )
            if child and current is not None:
                values[current][child.group(1)] = child.group(2).strip()
        return values

    def _indented_scalars(self, path: Path, section: str, *, indent: int) -> dict[str, str]:
        lines = self._read(path).splitlines()
        values: dict[str, str] = {}
        marker = " " * indent + section + ":"
        child_indent = " " * (indent + 2)
        active = False
        for line in lines:
            if line == marker:
                active = True
                continue
            if not active:
                continue
            if line and not line.startswith(child_indent):
                break
            match = re.fullmatch(
                re.escape(child_indent) + r"([A-Za-z0-9][A-Za-z0-9._-]*):\s*(\S.*)",
                line,
            )
            if match:
                values[match.group(1)] = match.group(2).strip()
        return values

    def _indented_list(self, path: Path, section: str, *, indent: int) -> list[str]:
        lines = self._read(path).splitlines()
        marker = " " * indent + section + ":"
        item_prefix = " " * (indent + 2) + "- "
        values: list[str] = []
        active = False
        for line in lines:
            if line == marker:
                active = True
                continue
            if not active:
                continue
            if line.startswith(item_prefix):
                value = line[len(item_prefix) :].strip()
                if self._NAME.fullmatch(value) is None:
                    raise ProviderConfigError("Provider order contains an invalid provider ID")
                values.append(value)
                continue
            if line and not line.startswith(" " * (indent + 2)):
                break
        if not values:
            raise ProviderConfigError(f"Canonical list {section} is missing or empty")
        return values

    def _top_level_scalar(self, path: Path, name: str) -> str:
        pattern = re.compile(rf"{re.escape(name)}:\s*(\S.*)")
        for line in self._read(path).splitlines():
            match = pattern.fullmatch(line)
            if match:
                return match.group(1).strip()
        raise ProviderConfigError(
            f"Canonical field {name} is missing in {self._relative(path)}"
        )

    def _resolve_from(self, source: Path, configured: str) -> Path:
        path = (source.parent / configured).resolve()
        try:
            path.relative_to(self.repository_root)
        except ValueError as error:
            raise ProviderConfigError(
                f"Provider configuration escapes repository root: {configured}"
            ) from error
        return path

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise ProviderConfigError(
                f"Could not read provider configuration {self._relative(path)}: {error}"
            ) from error

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.repository_root).as_posix()
