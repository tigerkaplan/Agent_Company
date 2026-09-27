"""Schema and invariant validation for CORE-04 tool contracts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from runtime.core.validation import JobValidationError, JobValidator
from runtime.tools.models import (
    ToolContractError,
    ToolDescriptor,
    ToolDiscoveryRequest,
)


class ToolValidationError(ValueError):
    """Raised when compact metadata or a deferred definition fails validation."""


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


class ToolDescriptorValidator:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_validator = JobValidator(
            schema_path or _schema_path("tool-descriptor.schema.json")
        )

    def validate(self, value: Mapping[str, Any]) -> ToolDescriptor:
        payload = dict(value)
        try:
            self.schema_validator.validate(payload)
            return ToolDescriptor.from_dict(payload)
        except (JobValidationError, ToolContractError) as error:
            raise ToolValidationError(str(error)) from error


class ToolDiscoveryRequestValidator:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_validator = JobValidator(
            schema_path or _schema_path("tool-discovery-request.schema.json")
        )

    def validate(self, value: Mapping[str, Any]) -> ToolDiscoveryRequest:
        payload = dict(value)
        try:
            self.schema_validator.validate(payload)
            return ToolDiscoveryRequest.from_dict(payload)
        except (JobValidationError, ToolContractError) as error:
            raise ToolValidationError(str(error)) from error


class ToolDefinitionPayloadValidator:
    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_validator = JobValidator(
            schema_path or _schema_path("tool-definition.schema.json")
        )

    def validate(self, value: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(value)
        try:
            self.schema_validator.validate(payload)
        except JobValidationError as error:
            raise ToolValidationError(str(error)) from error
        return payload


class ToolInputSchemaValidator:
    """Validate a bounded local JSON Schema subset without resolving external refs."""

    _KEYWORDS = frozenset(
        {
            "$schema",
            "$defs",
            "$ref",
            "title",
            "description",
            "type",
            "properties",
            "required",
            "additionalProperties",
            "items",
            "enum",
            "const",
            "minLength",
            "maxLength",
            "minimum",
            "maximum",
            "minItems",
            "maxItems",
            "uniqueItems",
            "minProperties",
            "maxProperties",
            "pattern",
            "format",
            "oneOf",
            "anyOf",
            "allOf",
            "not",
            "if",
            "then",
            "else",
        }
    )
    _TYPES = frozenset(
        {"object", "array", "string", "integer", "number", "boolean", "null"}
    )
    _FORMATS = frozenset({"date-time"})
    _NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")

    def validate(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ToolValidationError("tool input schema must be an object")
        payload = dict(value)
        try:
            encoded = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        except (OverflowError, TypeError, ValueError) as error:
            raise ToolValidationError("tool input schema is not canonical JSON") from error
        if len(encoded) > 1024 * 1024:
            raise ToolValidationError("tool input schema exceeds the 1 MiB bound")
        self._validate_node(payload, "$", depth=0)
        if payload.get("type") != "object":
            raise ToolValidationError("tool input schema root type must be object")
        self._validate_local_refs(payload, payload, "$")
        return payload

    def _validate_local_refs(
        self,
        value: Any,
        root: Mapping[str, Any],
        path: str,
    ) -> None:
        if isinstance(value, Mapping):
            reference = value.get("$ref")
            if reference is not None:
                current: Any = root
                try:
                    for part in reference[2:].split("/"):
                        current = current[part.replace("~1", "/").replace("~0", "~")]
                except (KeyError, TypeError) as error:
                    raise ToolValidationError(
                        f"{path} contains an unresolved local $ref"
                    ) from error
                if not isinstance(current, Mapping):
                    raise ToolValidationError(
                        f"{path} local $ref does not resolve to a schema object"
                    )
            for name, item in value.items():
                self._validate_local_refs(item, root, f"{path}.{name}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                self._validate_local_refs(item, root, f"{path}[{index}]")

    def _validate_node(self, schema: Any, path: str, *, depth: int) -> None:
        if depth > 12:
            raise ToolValidationError("tool input schema exceeds maximum depth")
        if not isinstance(schema, Mapping):
            raise ToolValidationError(f"{path} must be a schema object")
        unknown = sorted(set(schema) - self._KEYWORDS)
        if unknown:
            raise ToolValidationError(
                f"{path} contains unsupported schema keywords: {', '.join(unknown)}"
            )
        if "$ref" in schema:
            reference = schema["$ref"]
            if (
                not isinstance(reference, str)
                or not reference.startswith("#/$defs/")
                or ".." in reference
                or "\\" in reference
            ):
                raise ToolValidationError(
                    f"{path} contains a prohibited external or traversing $ref"
                )
        if "type" in schema and schema["type"] not in self._TYPES:
            raise ToolValidationError(f"{path}.type is not supported")
        if "format" in schema and schema["format"] not in self._FORMATS:
            raise ToolValidationError(f"{path}.format is not supported")
        if "pattern" in schema:
            if not isinstance(schema["pattern"], str) or len(schema["pattern"]) > 500:
                raise ToolValidationError(f"{path}.pattern is invalid")
            try:
                re.compile(schema["pattern"])
            except re.error as error:
                raise ToolValidationError(f"{path}.pattern is invalid") from error
        for name in ("title", "description"):
            if name in schema and (
                not isinstance(schema[name], str) or len(schema[name]) > 2000
            ):
                raise ToolValidationError(f"{path}.{name} is invalid")
        if "$schema" in schema and schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
            raise ToolValidationError(f"{path} declares an unsupported JSON Schema draft")
        for name in (
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
            "minProperties",
            "maxProperties",
        ):
            if name in schema and (
                not isinstance(schema[name], int)
                or isinstance(schema[name], bool)
                or not 0 <= schema[name] <= 100000
            ):
                raise ToolValidationError(f"{path}.{name} is invalid")
        for name in ("minimum", "maximum"):
            if name in schema and (
                not isinstance(schema[name], (int, float))
                or isinstance(schema[name], bool)
            ):
                raise ToolValidationError(f"{path}.{name} is invalid")
        for name in ("uniqueItems",):
            if name in schema and not isinstance(schema[name], bool):
                raise ToolValidationError(f"{path}.{name} must be boolean")
        if "required" in schema:
            required = schema["required"]
            if (
                not isinstance(required, list)
                or len(required) > 100
                or len(required) != len(set(required))
                or any(not isinstance(item, str) or not item for item in required)
            ):
                raise ToolValidationError(f"{path}.required is invalid")
        if "enum" in schema:
            enum = schema["enum"]
            if not isinstance(enum, list) or not enum or len(enum) > 100:
                raise ToolValidationError(f"{path}.enum is invalid")
        properties = schema.get("properties")
        if properties is not None:
            if not isinstance(properties, Mapping) or len(properties) > 100:
                raise ToolValidationError(f"{path}.properties is invalid")
            for name, child in properties.items():
                if not isinstance(name, str) or self._NAME.fullmatch(name) is None:
                    raise ToolValidationError(f"{path}.properties contains an invalid name")
                self._validate_node(child, f"{path}.properties.{name}", depth=depth + 1)
            if "required" in schema and not set(schema["required"]) <= set(properties):
                raise ToolValidationError(
                    f"{path}.required contains a name absent from properties"
                )
        definitions = schema.get("$defs")
        if definitions is not None:
            if not isinstance(definitions, Mapping) or len(definitions) > 100:
                raise ToolValidationError(f"{path}.$defs is invalid")
            for name, child in definitions.items():
                if not isinstance(name, str) or self._NAME.fullmatch(name) is None:
                    raise ToolValidationError(f"{path}.$defs contains an invalid name")
                self._validate_node(child, f"{path}.$defs.{name}", depth=depth + 1)
        additional = schema.get("additionalProperties")
        if additional is not None:
            if isinstance(additional, Mapping):
                self._validate_node(
                    additional, f"{path}.additionalProperties", depth=depth + 1
                )
            elif not isinstance(additional, bool):
                raise ToolValidationError(f"{path}.additionalProperties is invalid")
        if "items" in schema:
            self._validate_node(schema["items"], f"{path}.items", depth=depth + 1)
        for name in ("not", "if", "then", "else"):
            if name in schema:
                self._validate_node(schema[name], f"{path}.{name}", depth=depth + 1)
        for name in ("oneOf", "anyOf", "allOf"):
            if name in schema:
                branches = schema[name]
                if not isinstance(branches, list) or not 1 <= len(branches) <= 20:
                    raise ToolValidationError(f"{path}.{name} is invalid")
                for index, child in enumerate(branches):
                    self._validate_node(
                        child, f"{path}.{name}[{index}]", depth=depth + 1
                    )
