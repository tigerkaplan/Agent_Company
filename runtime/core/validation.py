"""Dependency-free validation for the JSON Schema features used by job records."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class JobValidationError(ValueError):
    """Raised when a job does not satisfy the canonical schema."""


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "job.schema.json"


class JobValidator:
    """Validate the JSON Schema subset used by schemas/job.schema.json."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path = schema_path or default_schema_path()
        with self.schema_path.open("r", encoding="utf-8") as handle:
            self.schema = json.load(handle)

    def validate(self, value: dict[str, Any]) -> None:
        self._validate(value, self.schema, "$", self.schema)

    def _validate(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        root: dict[str, Any],
    ) -> None:
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"], root)

        for candidate in schema.get("allOf", []):
            self._validate(value, candidate, path, root)

        if "if" in schema:
            condition_matches = True
            try:
                self._validate(value, schema["if"], path, root)
            except JobValidationError:
                condition_matches = False
            branch = schema.get("then") if condition_matches else schema.get("else")
            if branch is not None:
                self._validate(value, branch, path, root)

        if "oneOf" in schema:
            matches = 0
            for candidate in schema["oneOf"]:
                try:
                    self._validate(value, candidate, path, root)
                except JobValidationError:
                    continue
                matches += 1
            if matches != 1:
                raise JobValidationError(f"{path}: must match exactly one allowed schema")
            return

        if "type" in schema and not self._has_type(value, schema["type"]):
            raise JobValidationError(f"{path}: expected {schema['type']}")

        if "const" in schema and value != schema["const"]:
            raise JobValidationError(f"{path}: expected constant {schema['const']!r}")

        if "enum" in schema and value not in schema["enum"]:
            allowed = ", ".join(repr(item) for item in schema["enum"])
            raise JobValidationError(f"{path}: expected one of {allowed}")

        if isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                raise JobValidationError(f"{path}: string is too short")
            if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
                raise JobValidationError(f"{path}: does not match required pattern")
            if schema.get("format") == "date-time":
                self._validate_datetime(value, path)

        if isinstance(value, int) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise JobValidationError(f"{path}: must be at least {schema['minimum']}")

        if isinstance(value, list) and "items" in schema:
            for index, item in enumerate(value):
                self._validate(item, schema["items"], f"{path}[{index}]", root)

        if isinstance(value, dict):
            required = schema.get("required", [])
            missing = [name for name in required if name not in value]
            if missing:
                raise JobValidationError(f"{path}: missing required fields: {', '.join(missing)}")

            properties = schema.get("properties", {})
            if schema.get("additionalProperties") is False:
                unexpected = sorted(set(value) - set(properties))
                if unexpected:
                    raise JobValidationError(
                        f"{path}: unexpected fields: {', '.join(unexpected)}"
                    )
            for name, item in value.items():
                if name in properties:
                    self._validate(item, properties[name], f"{path}.{name}", root)

    @staticmethod
    def _has_type(value: Any, expected: str) -> bool:
        checks = {
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "boolean": lambda item: isinstance(item, bool),
            "null": lambda item: item is None,
        }
        if expected not in checks:
            raise JobValidationError(f"Unsupported schema type: {expected}")
        return checks[expected](value)

    @staticmethod
    def _resolve_ref(reference: str, root: dict[str, Any]) -> dict[str, Any]:
        if not reference.startswith("#/"):
            raise JobValidationError(f"Unsupported schema reference: {reference}")
        current: Any = root
        for part in reference[2:].split("/"):
            current = current[part.replace("~1", "/").replace("~0", "~")]
        return current

    @staticmethod
    def _validate_datetime(value: str, path: str) -> None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise JobValidationError(f"{path}: invalid ISO 8601 date-time") from error
        if parsed.tzinfo is None:
            raise JobValidationError(f"{path}: date-time must include a timezone")
