"""Dependency-free validation for canonical runtime JSON schemas."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


class JobValidationError(ValueError):
    """Raised when a job does not satisfy the canonical schema."""


class SchemaIntegrityError(JobValidationError):
    """Raised when bounded schema processing cannot safely continue."""


SCHEMA_MAX_BYTES = 128 * 1024
W_MAX = 16_777_216
D_MAX = 128


@dataclass
class _ValidationState:
    work: int = 0
    depth: int = 0
    active: set[tuple[Path, int, str, str]] = field(default_factory=set)
    documents: dict[Path, tuple[dict[str, Any], bytes, str]] = field(
        default_factory=dict
    )
    failed: SchemaIntegrityError | None = None


_VALIDATION_STATE: ContextVar[_ValidationState | None] = ContextVar(
    "schema_validation_state", default=None
)


def _load_schema(path: Path, description: str) -> tuple[dict[str, Any], bytes, str]:
    """Load one complete schema while retaining its exact raw-byte identity."""
    try:
        with path.open("rb") as handle:
            initial_extent = os.fstat(handle.fileno()).st_size
            if initial_extent > SCHEMA_MAX_BYTES:
                raise SchemaIntegrityError(
                    f"{description.capitalize()} exceeds {SCHEMA_MAX_BYTES} raw bytes"
                )
            chunks: list[bytes] = []
            acquired = 0
            while acquired < initial_extent:
                chunk = handle.read(initial_extent - acquired)
                if not chunk:
                    raise SchemaIntegrityError(
                        f"{description.capitalize()} changed during acquisition"
                    )
                chunks.append(chunk)
                acquired += len(chunk)
            final_extent = os.fstat(handle.fileno()).st_size
    except OSError as error:
        raise JobValidationError(f"Could not load {description}") from error
    if final_extent != initial_extent:
        raise SchemaIntegrityError(
            f"{description.capitalize()} changed during acquisition"
        )
    raw = b"".join(chunks)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise JobValidationError(f"Could not load {description}") from error
    if not isinstance(document, dict):
        raise JobValidationError(f"{description.capitalize()} is not an object")
    return document, raw, hashlib.sha256(raw).hexdigest()


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "job.schema.json"


class JobValidator:
    """Validate the JSON Schema subset used by canonical runtime records."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path = schema_path or default_schema_path()
        self.schema, self.schema_raw_bytes, self.schema_sha256 = _load_schema(
            self.schema_path, "schema"
        )

    def validate(self, value: dict[str, Any]) -> None:
        state = _VALIDATION_STATE.get()
        if state is not None:
            self._validate(value, self.schema, "$", self.schema, self.schema_path)
            return
        state = _ValidationState()
        token = _VALIDATION_STATE.set(state)
        try:
            self._validate(value, self.schema, "$", self.schema, self.schema_path)
        finally:
            _VALIDATION_STATE.reset(token)

    def validate_schema_references(self) -> None:
        """Validate the complete schema-reference graph in one bounded operation."""
        state = _VALIDATION_STATE.get()
        token = None
        if state is None:
            state = _ValidationState()
            token = _VALIDATION_STATE.set(state)
        try:
            if state.failed is not None:
                raise state.failed
            schema_path = self.schema_path.resolve()
            cached = state.documents.get(schema_path)
            if cached is None:
                state.documents[schema_path] = (
                    self.schema,
                    self.schema_raw_bytes,
                    self.schema_sha256,
                )
            elif cached[1] != self.schema_raw_bytes:
                state.failed = SchemaIntegrityError(
                    "Schema changed during validation traversal"
                )
                raise state.failed
            self._walk_schema_references(
                self.schema,
                self.schema,
                schema_path,
                {schema_path},
            )
        finally:
            if token is not None:
                _VALIDATION_STATE.reset(token)

    @staticmethod
    def _charge(event: str) -> _ValidationState:
        state = _VALIDATION_STATE.get()
        if state is None:
            raise SchemaIntegrityError("Validation traversal state is unavailable")
        if state.failed is not None:
            raise state.failed
        if state.work >= W_MAX:
            state.failed = SchemaIntegrityError(
                f"Validation traversal exceeds W_MAX={W_MAX} before {event}"
            )
            raise state.failed
        state.work += 1
        return state

    def _walk_schema_references(
        self,
        value: Any,
        root: dict[str, Any],
        schema_path: Path,
        visited_documents: set[Path],
    ) -> None:
        state = self._charge("schema-reference discovery node visit")
        if state.depth >= D_MAX:
            state.failed = SchemaIntegrityError(
                f"Validation traversal exceeds D_MAX={D_MAX} active frames"
            )
            raise state.failed
        state.depth += 1
        try:
            if isinstance(value, dict):
                if "$ref" in value:
                    reference = value["$ref"]
                    if not isinstance(reference, str):
                        raise JobValidationError("Schema reference is not a string")
                    self._charge("reference resolution")
                    _, resolved_root, resolved_path = self._resolve_ref(
                        reference, root, schema_path
                    )
                    resolved_path = resolved_path.resolve()
                    if resolved_path not in visited_documents:
                        visited_documents.add(resolved_path)
                        self._walk_schema_references(
                            resolved_root,
                            resolved_root,
                            resolved_path,
                            visited_documents,
                        )
                for item in value.values():
                    self._walk_schema_references(
                        item, root, schema_path, visited_documents
                    )
            elif isinstance(value, list):
                for item in value:
                    self._walk_schema_references(
                        item, root, schema_path, visited_documents
                    )
        finally:
            state.depth -= 1

    def _validate(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        root: dict[str, Any],
        schema_path: Path,
    ) -> None:
        state = self._charge("schema evaluation")
        self._charge("instance node visit")
        if state.depth >= D_MAX:
            state.failed = SchemaIntegrityError(
                f"Validation traversal exceeds D_MAX={D_MAX} active frames"
            )
            raise state.failed
        state.depth += 1
        try:
            self._validate_frame(value, schema, path, root, schema_path, state)
        finally:
            state.depth -= 1

    def _validate_frame(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        root: dict[str, Any],
        schema_path: Path,
        state: _ValidationState,
    ) -> None:
        if "$ref" in schema:
            reference_chain: set[tuple[Path, int]] = set()
            while "$ref" in schema:
                reference_key = (schema_path.resolve(), id(schema))
                if reference_key in reference_chain:
                    state.failed = SchemaIntegrityError(
                        f"{path}: non-progressing recursive schema reference"
                    )
                    raise state.failed
                reference_chain.add(reference_key)
                self._charge("reference resolution")
                schema, root, schema_path = self._resolve_ref(
                    schema["$ref"], root, schema_path
                )
                if set(schema) != {"$ref"}:
                    break

        active_key = (schema_path.resolve(), id(schema), path, "evaluate")
        if active_key in state.active:
            state.failed = SchemaIntegrityError(
                f"{path}: non-progressing recursive schema evaluation"
            )
            raise state.failed
        state.active.add(active_key)
        try:
            self._validate_keywords(value, schema, path, root, schema_path)
        finally:
            state.active.discard(active_key)

    def _validate_keywords(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        root: dict[str, Any],
        schema_path: Path,
    ) -> None:

        for candidate in schema.get("allOf", []):
            self._charge("allOf branch attempt")
            self._validate(value, candidate, path, root, schema_path)

        if "if" in schema:
            condition_matches = True
            try:
                self._charge("if branch attempt")
                self._validate(value, schema["if"], path, root, schema_path)
            except SchemaIntegrityError:
                raise
            except JobValidationError:
                condition_matches = False
            branch = schema.get("then") if condition_matches else schema.get("else")
            if branch is not None:
                self._charge("conditional branch attempt")
                self._validate(value, branch, path, root, schema_path)

        if "oneOf" in schema:
            matches = 0
            for candidate in schema["oneOf"]:
                try:
                    self._charge("oneOf branch attempt")
                    self._validate(value, candidate, path, root, schema_path)
                except SchemaIntegrityError:
                    raise
                except JobValidationError:
                    continue
                matches += 1
            if matches != 1:
                raise JobValidationError(f"{path}: must match exactly one allowed schema")
            return

        if "anyOf" in schema:
            for candidate in schema["anyOf"]:
                try:
                    self._charge("anyOf branch attempt")
                    self._validate(value, candidate, path, root, schema_path)
                except SchemaIntegrityError:
                    raise
                except JobValidationError:
                    continue
                break
            else:
                raise JobValidationError(f"{path}: must match an allowed schema")

        if "not" in schema:
            try:
                self._charge("not branch attempt")
                self._validate(value, schema["not"], path, root, schema_path)
            except SchemaIntegrityError:
                raise
            except JobValidationError:
                pass
            else:
                raise JobValidationError(f"{path}: matches a prohibited schema")

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
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                raise JobValidationError(f"{path}: string is too long")
            if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
                raise JobValidationError(f"{path}: does not match required pattern")
            if schema.get("format") == "date-time":
                self._validate_datetime(value, path)

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not math.isfinite(value):
                raise JobValidationError(f"{path}: number must be finite")
            if "minimum" in schema and value < schema["minimum"]:
                raise JobValidationError(f"{path}: must be at least {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                raise JobValidationError(f"{path}: must be at most {schema['maximum']}")

        if isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                raise JobValidationError(f"{path}: array has too few items")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise JobValidationError(f"{path}: array has too many items")
            if schema.get("uniqueItems") is True:
                canonical = [
                    json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False)
                    for item in value
                ]
                if len(canonical) != len(set(canonical)):
                    raise JobValidationError(f"{path}: array items must be unique")
            if "items" in schema:
                for index, item in enumerate(value):
                    self._validate(
                        item,
                        schema["items"],
                        f"{path}[{index}]",
                        root,
                        schema_path,
                    )
            if "contains" in schema:
                if not any(
                    self._matches(
                        item,
                        schema["contains"],
                        f"{path}[{index}]",
                        root,
                        schema_path,
                    )
                    for index, item in enumerate(value)
                ):
                    raise JobValidationError(f"{path}: array lacks a required item")

        if isinstance(value, Mapping):
            if len(value) < schema.get("minProperties", 0):
                raise JobValidationError(f"{path}: object has too few properties")
            if "maxProperties" in schema and len(value) > schema["maxProperties"]:
                raise JobValidationError(f"{path}: object has too many properties")
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
            property_names = schema.get("propertyNames")
            if property_names is not None:
                for name in value:
                    self._validate(
                        name,
                        property_names,
                        f"{path} property name",
                        root,
                        schema_path,
                    )
            for name, item in value.items():
                if name in properties:
                    if name == "graph_plan" and path == "$":
                        from runtime.graph.models import reuse_root_plan_schema
                        if reuse_root_plan_schema(self, item, properties[name], value, schema_path):
                            continue
                    self._validate(
                        item,
                        properties[name],
                        f"{path}.{name}",
                        root,
                        schema_path,
                    )
                elif isinstance(schema.get("additionalProperties"), dict):
                    self._validate(
                        item,
                        schema["additionalProperties"],
                        f"{path}.{name}",
                        root,
                        schema_path,
                    )

    def _matches(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        root: dict[str, Any],
        schema_path: Path,
    ) -> bool:
        try:
            self._validate(value, schema, path, root, schema_path)
        except SchemaIntegrityError:
            raise
        except JobValidationError:
            return False
        return True

    @staticmethod
    def _has_type(value: Any, expected: str) -> bool:
        if isinstance(expected, list):
            return any(JobValidator._has_type(value, item) for item in expected)
        checks = {
            "object": lambda item: isinstance(item, Mapping),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: isinstance(item, (int, float))
            and not isinstance(item, bool),
            "boolean": lambda item: isinstance(item, bool),
            "null": lambda item: item is None,
        }
        if expected not in checks:
            raise JobValidationError(f"Unsupported schema type: {expected}")
        return checks[expected](value)

    def _resolve_ref(
        self,
        reference: str,
        root: dict[str, Any],
        schema_path: Path,
    ) -> tuple[dict[str, Any], dict[str, Any], Path]:
        document, separator, fragment = reference.partition("#")
        resolved_path = schema_path
        resolved_root = root
        if document:
            resolved_path = (schema_path.parent / document).resolve()
            allowed_root = self.schema_path.parent.resolve()
            try:
                resolved_path.relative_to(allowed_root)
            except ValueError as error:
                raise JobValidationError(
                    f"Schema reference escapes its canonical directory: {reference}"
                ) from error
            state = _VALIDATION_STATE.get()
            if state is None:
                raise SchemaIntegrityError("Validation traversal state is unavailable")
            cached = state.documents.get(resolved_path)
            if cached is None:
                loaded = _load_schema(
                    resolved_path, f"schema reference: {reference}"
                )
                state.documents[resolved_path] = loaded
                cached = loaded
            resolved_root = cached[0]
        if not separator or not fragment:
            return resolved_root, resolved_root, resolved_path
        if not fragment.startswith("/"):
            raise JobValidationError(f"Unsupported schema reference: {reference}")
        current: Any = resolved_root
        for part in fragment[1:].split("/"):
            current = current[part.replace("~1", "/").replace("~0", "~")]
        if not isinstance(current, dict):
            raise JobValidationError(f"Schema reference is not an object: {reference}")
        return current, resolved_root, resolved_path

    @staticmethod
    def _validate_datetime(value: str, path: str) -> None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise JobValidationError(f"{path}: invalid ISO 8601 date-time") from error
        if parsed.tzinfo is None:
            raise JobValidationError(f"{path}: date-time must include a timezone")
