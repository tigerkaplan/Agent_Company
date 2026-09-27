"""Bounded deferred loader for explicitly selected canonical tools."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from runtime.tools.models import (
    ToolContractError,
    ToolDefinition,
    ToolDiscoveryResult,
    ToolLoadResult,
)
from runtime.tools.registry import ToolRegistry, ToolRegistryError
from runtime.tools.validation import (
    ToolDefinitionPayloadValidator,
    ToolInputSchemaValidator,
    ToolValidationError,
)


class ToolLoadError(ValueError):
    """Raised when a selected tool cannot be loaded without weakening bounds."""


class ToolDefinitionLoader:
    """Load selected JSON definitions only; never import or execute adapters."""

    _MAX_FILE_BYTES = 1024 * 1024

    def __init__(
        self,
        registry: ToolRegistry,
        definition_root: Path,
        *,
        reader: Callable[[Path], str] | None = None,
    ) -> None:
        if not isinstance(registry, ToolRegistry):
            raise ToolLoadError("loader requires an explicit ToolRegistry")
        root = Path(definition_root).resolve()
        if not root.is_dir():
            raise ToolLoadError("definition root must be an existing directory")
        self._registry = registry
        self._root = root
        self._reader = reader or self._read_text
        self._definition_validator = ToolDefinitionPayloadValidator()
        self._schema_validator = ToolInputSchemaValidator()

    def load(self, discovery: ToolDiscoveryResult) -> ToolLoadResult:
        try:
            self._registry.verify_discovery(discovery)
        except ToolRegistryError as error:
            raise ToolLoadError(str(error)) from error
        if discovery.loaded_tool_ids:
            raise ToolLoadError("discovery result already records loaded tools")
        if not discovery.selected_tool_ids:
            raise ToolLoadError("tools must be selected before deferred loading")
        definitions = tuple(
            self._load_one(discovery, tool_id)
            for tool_id in discovery.selected_tool_ids
        )
        try:
            loaded_discovery = discovery.with_loaded(
                tuple(definition.tool_id for definition in definitions)
            )
            return ToolLoadResult(
                discovery=loaded_discovery,
                definitions=definitions,
            )
        except ToolContractError as error:
            raise ToolLoadError(f"loaded tool evidence is inconsistent: {error}") from error

    def _load_one(
        self,
        discovery: ToolDiscoveryResult,
        tool_id: str,
    ) -> ToolDefinition:
        if tool_id not in discovery.selected_tool_ids:
            raise ToolLoadError("unknown or unselected tool load was rejected")
        descriptor = self._registry.descriptor(tool_id)
        if descriptor is None:
            raise ToolLoadError("selected tool is not present in the registry snapshot")
        candidate = next(
            (
                item
                for item in discovery.candidates
                if item.descriptor.tool_id == tool_id
            ),
            None,
        )
        if candidate is None or not candidate.selectable:
            raise ToolLoadError("selected tool is unavailable or ineligible")
        if candidate.descriptor.digest != descriptor.digest:
            raise ToolLoadError("descriptor identity drift was detected before load")

        definition_path = self._resolve(descriptor.definition_ref)
        schema_path = self._resolve(descriptor.schema_ref)
        definition_payload = self._read_json(definition_path, "tool definition")
        schema_payload = self._read_json(schema_path, "tool input schema")
        try:
            definition_payload = self._definition_validator.validate(
                definition_payload
            )
            schema_payload = self._schema_validator.validate(schema_payload)
        except ToolValidationError as error:
            raise ToolLoadError(f"selected tool definition is malformed: {error}") from error

        expected = {
            "tool_id": descriptor.tool_id,
            "version": descriptor.version,
            "tool_class": descriptor.tool_class,
            "capabilities": list(descriptor.capabilities),
            "authority_class": descriptor.authority_class,
            "risk_level": descriptor.risk_level,
        }
        for name, value in expected.items():
            observed = definition_payload.get(name)
            if name == "capabilities" and isinstance(observed, list):
                observed = sorted(observed)
            if observed != value:
                raise ToolLoadError(
                    f"descriptor/load identity mismatch for {name}"
                )
        try:
            return ToolDefinition(
                tool_id=definition_payload["tool_id"],
                version=definition_payload["version"],
                adapter_id=definition_payload["adapter_id"],
                tool_class=definition_payload["tool_class"],
                capabilities=tuple(definition_payload["capabilities"]),
                authority_class=definition_payload["authority_class"],
                risk_level=definition_payload["risk_level"],
                description_context=definition_payload["description_context"],
                input_schema=schema_payload,
            )
        except ToolContractError as error:
            raise ToolLoadError(f"loaded tool contract is malformed: {error}") from error

    def _resolve(self, configured: str) -> Path:
        candidate = (self._root / configured).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as error:
            raise ToolLoadError("tool definition path escapes the trusted root") from error
        if not candidate.is_file():
            raise ToolLoadError("selected tool definition file is missing")
        return candidate

    def _read_json(self, path: Path, kind: str) -> dict[str, Any]:
        try:
            text = self._reader(path)
        except (OSError, UnicodeError) as error:
            raise ToolLoadError(f"could not read selected {kind}") from error
        if not isinstance(text, str):
            raise ToolLoadError(f"selected {kind} reader returned invalid data")
        if len(text.encode("utf-8")) > self._MAX_FILE_BYTES:
            raise ToolLoadError(f"selected {kind} exceeds the 1 MiB bound")
        try:
            value = json.loads(text, object_pairs_hook=self._strict_object)
        except (json.JSONDecodeError, RecursionError, ToolLoadError) as error:
            raise ToolLoadError(f"selected {kind} is not valid JSON") from error
        if not isinstance(value, Mapping):
            raise ToolLoadError(f"selected {kind} must be a JSON object")
        return dict(value)

    @staticmethod
    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for name, item in pairs:
            if name in value:
                raise ToolLoadError("selected JSON contains duplicate object keys")
            value[name] = item
        return value
