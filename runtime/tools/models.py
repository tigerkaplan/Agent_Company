"""Immutable provider-neutral contracts for CORE-04 tool discovery."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any

from runtime.core.sanitization import contains_secret


class ToolContractError(ValueError):
    """Raised when a tool-discovery contract is malformed or inconsistent."""


TOOL_CLASSES = frozenset({"local", "connector", "mcp", "provider_native"})
TOOL_AVAILABILITY = frozenset({"available", "unavailable", "disabled"})
TOOL_STATUSES = frozenset({"active", "deprecated", "disabled"})
AUTHORITY_CLASSES = frozenset(
    {"READ_ONLY", "CONTROLLED_WRITE", "EXTERNAL_ACTION", "GIT", "DEPLOYMENT"}
)
RISK_LEVELS = ("low", "medium", "high", "approval_required")
DISCOVERY_STATUSES = frozenset({"matched", "no_match"})
MAX_REGISTERED_TOOLS = 1000
MAX_CANDIDATES = 50
MAX_REJECTIONS = 100
MAX_REQUIRED_CAPABILITIES = 20

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
_ADAPTER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")


class FrozenJsonMapping(Mapping[str, Any]):
    """A recursively immutable mapping used for loaded schemas."""

    __slots__ = ("__values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        frozen = {
            str(key): _freeze_json(item)
            for key, item in sorted(values.items(), key=lambda pair: str(pair[0]))
        }
        object.__setattr__(self, "_FrozenJsonMapping__values", MappingProxyType(frozen))

    def __getitem__(self, key: str) -> Any:
        return self.__values[key]

    def __iter__(self):
        return iter(self.__values)

    def __len__(self) -> int:
        return len(self.__values)

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("canonical tool mappings are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("canonical tool mappings are immutable")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, FrozenJsonMapping):
        return value
    if isinstance(value, Mapping):
        return FrozenJsonMapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _reject_secret_json_values(value: Any, name: str) -> None:
    if isinstance(value, str):
        if contains_secret(value):
            raise ToolContractError(f"{name} contains credential-like content")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_secret_json_values(item, f"{name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_json_values(item, f"{name}[{index}]")


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (OverflowError, TypeError, ValueError) as error:
        raise ToolContractError("tool value is not canonical JSON") from error
    if len(encoded) > 4 * 1024 * 1024:
        raise ToolContractError("tool value exceeds the bounded identity limit")
    return hashlib.sha256(encoded).hexdigest()


def _bounded_string(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ToolContractError(
            f"{name} must be a non-empty string no longer than {limit} characters"
        )
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ToolContractError(f"{name} contains prohibited control characters")
    if contains_secret(value):
        raise ToolContractError(f"{name} contains credential-like content")
    return value


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ToolContractError(f"{name} is not a bounded canonical identifier")
    if contains_secret(value):
        raise ToolContractError(f"{name} contains credential-like content")
    return value


def _optional_identifier(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, name)


def _enum(value: Any, name: str, allowed: frozenset[str] | tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ToolContractError(f"{name} is not canonical")
    return value


def _identifier_tuple(
    values: Any,
    name: str,
    *,
    allow_empty: bool,
    maximum: int = 100,
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ToolContractError(f"{name} must be an array")
    if (not allow_empty and not values) or len(values) > maximum:
        raise ToolContractError(f"{name} has an invalid number of items")
    canonical = tuple(sorted(_identifier(item, f"{name} item") for item in values))
    if len(canonical) != len(set(canonical)):
        raise ToolContractError(f"{name} contains duplicate items")
    return canonical


def _optional_identifier_tuple(
    values: Any,
    name: str,
    *,
    allowed: frozenset[str] | None = None,
) -> tuple[str, ...] | None:
    if values is None:
        return None
    canonical = _identifier_tuple(values, name, allow_empty=False)
    if allowed is not None and any(item not in allowed for item in canonical):
        raise ToolContractError(f"{name} contains a non-canonical item")
    return canonical


def _safe_relative_ref(value: Any, name: str) -> str:
    ref = _bounded_string(value, name, 500)
    if "\\" in ref or ":" in ref or ref.startswith(("/", "~")):
        raise ToolContractError(f"{name} must be a canonical relative path")
    path = PurePosixPath(ref)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ToolContractError(f"{name} must not traverse outside its root")
    if path.as_posix() != ref:
        raise ToolContractError(f"{name} must be a normalized relative path")
    return ref


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Compact registration metadata; it never contains a full tool schema."""

    tool_id: str
    name: str
    description: str
    version: str
    capabilities: tuple[str, ...]
    authority_class: str
    risk_level: str
    tool_class: str
    definition_ref: str
    schema_ref: str
    availability: str = "available"
    status: str = "active"
    provider_compatibility: tuple[str, ...] = ()
    agent_compatibility: tuple[str, ...] = ()
    workflow_compatibility: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    preference_rank: int = 100

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_id", _identifier(self.tool_id, "tool_id"))
        object.__setattr__(self, "name", _bounded_string(self.name, "name", 200))
        object.__setattr__(
            self, "description", _bounded_string(self.description, "description", 2000)
        )
        object.__setattr__(self, "version", _identifier(self.version, "version"))
        object.__setattr__(
            self,
            "capabilities",
            _identifier_tuple(self.capabilities, "capabilities", allow_empty=False),
        )
        object.__setattr__(
            self,
            "authority_class",
            _enum(self.authority_class, "authority_class", AUTHORITY_CLASSES),
        )
        object.__setattr__(
            self, "risk_level", _enum(self.risk_level, "risk_level", RISK_LEVELS)
        )
        object.__setattr__(
            self, "tool_class", _enum(self.tool_class, "tool_class", TOOL_CLASSES)
        )
        object.__setattr__(
            self,
            "definition_ref",
            _safe_relative_ref(self.definition_ref, "definition_ref"),
        )
        object.__setattr__(
            self, "schema_ref", _safe_relative_ref(self.schema_ref, "schema_ref")
        )
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, "availability", TOOL_AVAILABILITY),
        )
        object.__setattr__(self, "status", _enum(self.status, "status", TOOL_STATUSES))
        for field_name in (
            "provider_compatibility",
            "agent_compatibility",
            "workflow_compatibility",
            "tags",
        ):
            object.__setattr__(
                self,
                field_name,
                _identifier_tuple(
                    getattr(self, field_name), field_name, allow_empty=True
                ),
            )
        if (
            not isinstance(self.preference_rank, int)
            or isinstance(self.preference_rank, bool)
            or not 0 <= self.preference_rank <= 1000
        ):
            raise ToolContractError("preference_rank must be an integer from 0 to 1000")

    @property
    def identity(self) -> tuple[str, str]:
        return self.tool_id, self.version

    @property
    def digest(self) -> str:
        return _canonical_digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "authority_class": self.authority_class,
            "risk_level": self.risk_level,
            "tool_class": self.tool_class,
            "definition_ref": self.definition_ref,
            "schema_ref": self.schema_ref,
            "availability": self.availability,
            "status": self.status,
            "provider_compatibility": list(self.provider_compatibility),
            "agent_compatibility": list(self.agent_compatibility),
            "workflow_compatibility": list(self.workflow_compatibility),
            "tags": list(self.tags),
            "preference_rank": self.preference_rank,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ToolDescriptor":
        if not isinstance(value, Mapping):
            raise ToolContractError("ToolDescriptor must be an object")
        expected = {
            "tool_id",
            "name",
            "description",
            "version",
            "capabilities",
            "authority_class",
            "risk_level",
            "tool_class",
            "definition_ref",
            "schema_ref",
            "availability",
            "status",
            "provider_compatibility",
            "agent_compatibility",
            "workflow_compatibility",
            "tags",
            "preference_rank",
        }
        if set(value) != expected:
            raise ToolContractError("ToolDescriptor fields are incomplete or unexpected")
        return cls(**{name: value[name] for name in expected})


@dataclass(frozen=True, slots=True)
class ToolDiscoveryRequest:
    required_capabilities: tuple[str, ...]
    agent: str | None = None
    workflow: str | None = None
    execution_mode: str | None = None
    max_risk_level: str = "approval_required"
    allowed_authority_classes: tuple[str, ...] | None = None
    allowed_tool_classes: tuple[str, ...] | None = None
    allowed_provider_ids: tuple[str, ...] | None = None
    maximum_candidates: int = 10

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_capabilities",
            _identifier_tuple(
                self.required_capabilities,
                "required_capabilities",
                allow_empty=False,
                maximum=MAX_REQUIRED_CAPABILITIES,
            ),
        )
        object.__setattr__(self, "agent", _optional_identifier(self.agent, "agent"))
        object.__setattr__(
            self, "workflow", _optional_identifier(self.workflow, "workflow")
        )
        if self.execution_mode not in {None, "READ_ONLY", "CONTROLLED_WRITE"}:
            raise ToolContractError("execution_mode is not canonical")
        object.__setattr__(
            self,
            "max_risk_level",
            _enum(self.max_risk_level, "max_risk_level", RISK_LEVELS),
        )
        object.__setattr__(
            self,
            "allowed_authority_classes",
            _optional_identifier_tuple(
                self.allowed_authority_classes,
                "allowed_authority_classes",
                allowed=AUTHORITY_CLASSES,
            ),
        )
        object.__setattr__(
            self,
            "allowed_tool_classes",
            _optional_identifier_tuple(
                self.allowed_tool_classes,
                "allowed_tool_classes",
                allowed=TOOL_CLASSES,
            ),
        )
        object.__setattr__(
            self,
            "allowed_provider_ids",
            _optional_identifier_tuple(
                self.allowed_provider_ids, "allowed_provider_ids"
            ),
        )
        if (
            not isinstance(self.maximum_candidates, int)
            or isinstance(self.maximum_candidates, bool)
            or not 1 <= self.maximum_candidates <= MAX_CANDIDATES
        ):
            raise ToolContractError(
                f"maximum_candidates must be an integer from 1 to {MAX_CANDIDATES}"
            )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "required_capabilities": list(self.required_capabilities),
            "agent": self.agent,
            "workflow": self.workflow,
            "execution_mode": self.execution_mode,
            "max_risk_level": self.max_risk_level,
            "allowed_authority_classes": (
                None
                if self.allowed_authority_classes is None
                else list(self.allowed_authority_classes)
            ),
            "allowed_tool_classes": (
                None if self.allowed_tool_classes is None else list(self.allowed_tool_classes)
            ),
            "allowed_provider_ids": (
                None if self.allowed_provider_ids is None else list(self.allowed_provider_ids)
            ),
            "maximum_candidates": self.maximum_candidates,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ToolDiscoveryRequest":
        if not isinstance(value, Mapping):
            raise ToolContractError("ToolDiscoveryRequest must be an object")
        expected = {
            "required_capabilities",
            "agent",
            "workflow",
            "execution_mode",
            "max_risk_level",
            "allowed_authority_classes",
            "allowed_tool_classes",
            "allowed_provider_ids",
            "maximum_candidates",
        }
        if set(value) != expected:
            raise ToolContractError(
                "ToolDiscoveryRequest fields are incomplete or unexpected"
            )
        return cls(**{name: value[name] for name in expected})


@dataclass(frozen=True, slots=True)
class ToolCandidate:
    descriptor: ToolDescriptor
    match_reasons: tuple[str, ...]
    available: bool
    eligible: bool
    ineligibility_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, ToolDescriptor):
            raise ToolContractError("candidate descriptor is not canonical")
        for field_name in ("match_reasons", "ineligibility_reasons"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or len(values) > 20:
                raise ToolContractError(f"{field_name} must be a bounded tuple")
            for item in values:
                _bounded_string(item, f"{field_name} item", 500)
        if not isinstance(self.available, bool) or not isinstance(self.eligible, bool):
            raise ToolContractError("candidate availability/eligibility must be boolean")
        if self.eligible and self.ineligibility_reasons:
            raise ToolContractError("eligible candidate cannot have ineligibility reasons")
        if not self.eligible and not self.ineligibility_reasons:
            raise ToolContractError("ineligible candidate requires a reason")

    @property
    def selectable(self) -> bool:
        return self.available and self.eligible

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "descriptor": self.descriptor.to_dict(),
            "match_reasons": list(self.match_reasons),
            "available": self.available,
            "eligible": self.eligible,
            "selectable": self.selectable,
            "ineligibility_reasons": list(self.ineligibility_reasons),
        }


@dataclass(frozen=True, slots=True)
class RejectedTool:
    tool_id: str
    version: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.tool_id, "rejected tool_id")
        _identifier(self.version, "rejected version")
        if not isinstance(self.reasons, tuple) or not self.reasons:
            raise ToolContractError("rejected tool requires reasons")
        for item in self.reasons:
            _bounded_string(item, "rejection reason", 500)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "tool_id": self.tool_id,
            "version": self.version,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ToolDiscoveryMetrics:
    registered: int
    considered: int
    matched: int
    selected: int
    loaded: int

    def __post_init__(self) -> None:
        values = (
            self.registered,
            self.considered,
            self.matched,
            self.selected,
            self.loaded,
        )
        if any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in values):
            raise ToolContractError("discovery metrics must be non-negative integers")
        if self.considered != self.registered:
            raise ToolContractError("every immutable registry entry must be considered")
        if self.matched > self.considered:
            raise ToolContractError("matched count exceeds considered count")
        if self.selected > self.matched or self.loaded > self.selected:
            raise ToolContractError("selected/loaded counts are inconsistent")

    def to_dict(self) -> dict[str, int]:
        self.__post_init__()
        return {
            "registered": self.registered,
            "considered": self.considered,
            "matched": self.matched,
            "selected": self.selected,
            "loaded": self.loaded,
        }


@dataclass(frozen=True, slots=True)
class ToolDiscoveryResult:
    request: ToolDiscoveryRequest
    registry_digest: str
    status: str
    candidates: tuple[ToolCandidate, ...]
    rejected: tuple[RejectedTool, ...]
    selected_tool_ids: tuple[str, ...]
    loaded_tool_ids: tuple[str, ...]
    metrics: ToolDiscoveryMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.request, ToolDiscoveryRequest):
            raise ToolContractError("discovery request is not canonical")
        if not isinstance(self.registry_digest, str) or re.fullmatch(
            r"[0-9a-f]{64}", self.registry_digest
        ) is None:
            raise ToolContractError("registry_digest is invalid")
        _enum(self.status, "discovery status", DISCOVERY_STATUSES)
        if not isinstance(self.candidates, tuple) or len(self.candidates) > MAX_CANDIDATES:
            raise ToolContractError("candidates are not a bounded tuple")
        if not isinstance(self.rejected, tuple) or len(self.rejected) > MAX_REJECTIONS:
            raise ToolContractError("rejected tools are not a bounded tuple")
        candidate_ids = tuple(item.descriptor.tool_id for item in self.candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ToolContractError("candidate tool IDs must be unique")
        for name, ids in (
            ("selected_tool_ids", self.selected_tool_ids),
            ("loaded_tool_ids", self.loaded_tool_ids),
        ):
            if not isinstance(ids, tuple) or len(ids) != len(set(ids)):
                raise ToolContractError(f"{name} must be an immutable unique tuple")
            for tool_id in ids:
                _identifier(tool_id, f"{name} item")
        selectable = {item.descriptor.tool_id for item in self.candidates if item.selectable}
        if not set(self.selected_tool_ids) <= selectable:
            raise ToolContractError("selection contains an unavailable or ineligible tool")
        if not set(self.loaded_tool_ids) <= set(self.selected_tool_ids):
            raise ToolContractError("loaded tools must be selected first")
        expected_status = "matched" if selectable else "no_match"
        if self.status != expected_status:
            raise ToolContractError("discovery status does not match candidate eligibility")
        if self.metrics.selected != len(self.selected_tool_ids):
            raise ToolContractError("selected metric does not match selection")
        if self.metrics.loaded != len(self.loaded_tool_ids):
            raise ToolContractError("loaded metric does not match loaded identities")

    @property
    def succeeded(self) -> bool:
        return self.status == "matched"

    def with_selection(self, tool_ids: tuple[str, ...]) -> "ToolDiscoveryResult":
        return replace(
            self,
            selected_tool_ids=tool_ids,
            loaded_tool_ids=(),
            metrics=replace(self.metrics, selected=len(tool_ids), loaded=0),
        )

    def with_loaded(self, tool_ids: tuple[str, ...]) -> "ToolDiscoveryResult":
        return replace(
            self,
            loaded_tool_ids=tool_ids,
            metrics=replace(self.metrics, loaded=len(tool_ids)),
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "request": self.request.to_dict(),
            "registry_digest": self.registry_digest,
            "status": self.status,
            "succeeded": self.succeeded,
            "candidates": [item.to_dict() for item in self.candidates],
            "rejected": [item.to_dict() for item in self.rejected],
            "selected_tool_ids": list(self.selected_tool_ids),
            "loaded_tool_ids": list(self.loaded_tool_ids),
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A fully loaded definition. It contains data, never executable authority."""

    tool_id: str
    version: str
    adapter_id: str
    tool_class: str
    capabilities: tuple[str, ...]
    authority_class: str
    risk_level: str
    description_context: str
    input_schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_id", _identifier(self.tool_id, "tool_id"))
        object.__setattr__(self, "version", _identifier(self.version, "version"))
        if not isinstance(self.adapter_id, str) or _ADAPTER_ID.fullmatch(self.adapter_id) is None:
            raise ToolContractError("adapter_id is not canonical")
        if contains_secret(self.adapter_id):
            raise ToolContractError("adapter_id contains credential-like content")
        object.__setattr__(
            self, "tool_class", _enum(self.tool_class, "tool_class", TOOL_CLASSES)
        )
        object.__setattr__(
            self,
            "capabilities",
            _identifier_tuple(self.capabilities, "capabilities", allow_empty=False),
        )
        object.__setattr__(
            self,
            "authority_class",
            _enum(self.authority_class, "authority_class", AUTHORITY_CLASSES),
        )
        object.__setattr__(
            self, "risk_level", _enum(self.risk_level, "risk_level", RISK_LEVELS)
        )
        object.__setattr__(
            self,
            "description_context",
            _bounded_string(self.description_context, "description_context", 8000),
        )
        if not isinstance(self.input_schema, Mapping):
            raise ToolContractError("input_schema must be an object")
        _reject_secret_json_values(self.input_schema, "input_schema")
        object.__setattr__(self, "input_schema", FrozenJsonMapping(self.input_schema))

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "tool_id": self.tool_id,
            "version": self.version,
            "adapter_id": self.adapter_id,
            "tool_class": self.tool_class,
            "capabilities": list(self.capabilities),
            "authority_class": self.authority_class,
            "risk_level": self.risk_level,
            "description_context": self.description_context,
            "input_schema": _thaw_json(self.input_schema),
        }


@dataclass(frozen=True, slots=True)
class ToolLoadResult:
    discovery: ToolDiscoveryResult
    definitions: tuple[ToolDefinition, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.discovery, ToolDiscoveryResult):
            raise ToolContractError("load result discovery is not canonical")
        if not isinstance(self.definitions, tuple):
            raise ToolContractError("loaded definitions must be an immutable tuple")
        definition_ids = tuple(item.tool_id for item in self.definitions)
        if definition_ids != self.discovery.loaded_tool_ids:
            raise ToolContractError("loaded definition order/identity is inconsistent")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "discovery": self.discovery.to_dict(),
            "definitions": [item.to_dict() for item in self.definitions],
        }
