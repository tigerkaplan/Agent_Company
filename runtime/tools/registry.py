"""Explicit immutable registry and deterministic capability-first discovery."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any

from runtime.tools.models import (
    MAX_REGISTERED_TOOLS,
    MAX_REJECTIONS,
    RISK_LEVELS,
    RejectedTool,
    ToolCandidate,
    ToolContractError,
    ToolDescriptor,
    ToolDiscoveryMetrics,
    ToolDiscoveryRequest,
    ToolDiscoveryResult,
    _canonical_digest,
    _identifier,
)
from runtime.tools.validation import (
    ToolDescriptorValidator,
    ToolDiscoveryRequestValidator,
    ToolValidationError,
)


class ToolRegistryError(ValueError):
    """Raised when registration, discovery, or selection fails closed."""


class ToolRegistrySnapshot(tuple):
    """Tuple-backed public view with a digest derived from its canonical records."""

    __slots__ = ()

    def __new__(
        cls,
        descriptors: tuple[ToolDescriptor, ...],
        digest: str,
    ):
        if not isinstance(descriptors, tuple):
            raise ToolRegistryError("registry descriptors must be an immutable tuple")
        canonical = tuple(_canonical_descriptor(item) for item in descriptors)
        ids = tuple(item.tool_id for item in canonical)
        if len(ids) != len(set(ids)):
            raise ToolRegistryError("duplicate tool IDs are prohibited")
        payloads = tuple(_descriptor_payload(item) for item in canonical)
        expected = _payload_digest(payloads)
        if digest != expected:
            raise ToolRegistryError("registry snapshot digest is inconsistent")
        return tuple.__new__(cls, (payloads,))

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("canonical registry snapshots are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("canonical registry snapshots are immutable")

    @property
    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(
            _descriptor_from_payload(payload)
            for payload in self._canonical_payloads()
        )

    @property
    def digest(self) -> str:
        return _payload_digest(self._canonical_payloads())

    @property
    def by_id(self) -> Mapping[str, ToolDescriptor]:
        return MappingProxyType({item.tool_id: item for item in self.descriptors})

    def _canonical_payloads(self) -> tuple[str, ...]:
        if tuple.__len__(self) != 1:
            raise ToolRegistryError("registry snapshot state is malformed")
        payloads = tuple.__getitem__(self, 0)
        if not isinstance(payloads, tuple) or any(
            not isinstance(payload, str) for payload in payloads
        ):
            raise ToolRegistryError("registry snapshot state is malformed")
        canonical = tuple(
            _descriptor_payload(_descriptor_from_payload(payload))
            for payload in payloads
        )
        if canonical != payloads:
            raise ToolRegistryError("registry snapshot state is not canonical")
        return payloads


def _canonical_descriptor(descriptor: ToolDescriptor) -> ToolDescriptor:
    if not isinstance(descriptor, ToolDescriptor):
        raise ToolRegistryError("registry snapshot contains a non-canonical descriptor")
    try:
        return ToolDescriptor.from_dict(descriptor.to_dict())
    except ToolContractError as error:
        raise ToolRegistryError("registry snapshot contains a malformed descriptor") from error


def _descriptor_payload(descriptor: ToolDescriptor) -> str:
    return json.dumps(
        descriptor.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _descriptor_from_payload(payload: str) -> ToolDescriptor:
    try:
        value = json.loads(payload)
        return ToolDescriptor.from_dict(value)
    except (json.JSONDecodeError, ToolContractError, TypeError, ValueError) as error:
        raise ToolRegistryError("canonical registry state is malformed") from error


def _payload_digest(payloads: tuple[str, ...]) -> str:
    try:
        values = [json.loads(payload) for payload in payloads]
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ToolRegistryError("canonical registry state is malformed") from error
    return _canonical_digest(values)


class ToolRegistry(tuple):
    """A fixed registry. There is no dynamic import, scan, or provider mutation."""

    __slots__ = ()

    _TOOL_CLASS_ORDER = {
        "local": 0,
        "connector": 1,
        "mcp": 2,
        "provider_native": 3,
    }

    def __new__(
        cls,
        descriptors: Iterable[ToolDescriptor | Mapping[str, Any]],
    ):
        canonical: list[ToolDescriptor] = []
        validator = ToolDescriptorValidator()
        try:
            for descriptor in descriptors:
                if len(canonical) >= MAX_REGISTERED_TOOLS:
                    raise ToolContractError(
                        f"registry exceeds the {MAX_REGISTERED_TOOLS}-tool bound"
                    )
                if isinstance(descriptor, ToolDescriptor):
                    descriptor = validator.validate(descriptor.to_dict())
                elif isinstance(descriptor, Mapping):
                    descriptor = validator.validate(dict(descriptor))
                else:
                    raise ToolContractError("registry entry is not a ToolDescriptor")
                canonical.append(descriptor)
        except (ToolContractError, ToolValidationError) as error:
            raise ToolRegistryError(f"malformed tool descriptor: {error}") from error
        canonical.sort(key=lambda item: (item.tool_id, item.version))
        tool_ids = [item.tool_id for item in canonical]
        if len(tool_ids) != len(set(tool_ids)):
            raise ToolRegistryError(
                "duplicate tool IDs or conflicting versions are prohibited"
            )
        frozen = tuple(canonical)
        payloads = tuple(_descriptor_payload(item) for item in frozen)
        _payload_digest(payloads)
        return tuple.__new__(cls, (payloads,))

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("canonical tool registries are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("canonical tool registries are immutable")

    @property
    def snapshot(self) -> ToolRegistrySnapshot:
        payloads, digest = self._canonical_state()
        return ToolRegistrySnapshot(
            descriptors=self._trusted_descriptors(payloads),
            digest=digest,
        )

    @property
    def registered_count(self) -> int:
        payloads, _ = self._canonical_state()
        return len(payloads)

    def descriptor(self, tool_id: str) -> ToolDescriptor | None:
        """Return a detached descriptor resolved from private canonical state."""
        payloads, _ = self._canonical_state()
        for descriptor in self._trusted_descriptors(payloads):
            if descriptor.tool_id == tool_id:
                return descriptor
        return None

    def _canonical_state(self) -> tuple[tuple[str, ...], str]:
        if tuple.__len__(self) != 1:
            raise ToolRegistryError("canonical registry state is malformed")
        payloads = tuple.__getitem__(self, 0)
        if not isinstance(payloads, tuple) or any(
            not isinstance(payload, str) for payload in payloads
        ):
            raise ToolRegistryError("canonical registry state is malformed")
        if len(payloads) > MAX_REGISTERED_TOOLS:
            raise ToolRegistryError("canonical registry state exceeds its bound")
        descriptors = tuple(_descriptor_from_payload(payload) for payload in payloads)
        canonical = tuple(_descriptor_payload(descriptor) for descriptor in descriptors)
        if canonical != payloads:
            raise ToolRegistryError("canonical registry state is not normalized")
        identities = tuple(descriptor.tool_id for descriptor in descriptors)
        if len(identities) != len(set(identities)):
            raise ToolRegistryError("canonical registry state contains duplicate tool IDs")
        if (
            tuple(sorted(descriptors, key=lambda item: (item.tool_id, item.version)))
            != descriptors
        ):
            raise ToolRegistryError("canonical registry state ordering is invalid")
        return payloads, _payload_digest(payloads)

    @staticmethod
    def _trusted_descriptors(
        payloads: tuple[str, ...],
    ) -> tuple[ToolDescriptor, ...]:
        return tuple(
            _descriptor_from_payload(payload)
            for payload in payloads
        )

    def discover(
        self,
        request: ToolDiscoveryRequest | Mapping[str, Any],
    ) -> ToolDiscoveryResult:
        validator = ToolDiscoveryRequestValidator()
        try:
            canonical_request = (
                validator.validate(dict(request))
                if isinstance(request, Mapping)
                else validator.validate(request.to_dict())
                if isinstance(request, ToolDiscoveryRequest)
                else None
            )
        except (ToolContractError, ToolValidationError) as error:
            raise ToolRegistryError(f"malformed discovery request: {error}") from error
        if canonical_request is None:
            raise ToolRegistryError("discovery request is not canonical")

        payloads, registry_digest = self._canonical_state()
        descriptors = self._trusted_descriptors(payloads)
        matched: list[ToolCandidate] = []
        rejected: list[RejectedTool] = []
        required = set(canonical_request.required_capabilities)
        for descriptor in descriptors:
            missing = sorted(required - set(descriptor.capabilities))
            if missing:
                self._reject(
                    rejected,
                    descriptor,
                    ("missing required capabilities: " + ", ".join(missing),),
                )
                continue
            reasons = tuple(
                f"exact capability match: {capability}"
                for capability in canonical_request.required_capabilities
            )
            ineligible = self._ineligibility_reasons(descriptor, canonical_request)
            matched.append(
                ToolCandidate(
                    descriptor=descriptor,
                    match_reasons=reasons,
                    available=descriptor.availability == "available",
                    eligible=not ineligible,
                    ineligibility_reasons=ineligible,
                )
            )

        matched_count = len(matched)
        matched.sort(
            key=lambda candidate: (
                0 if candidate.selectable else 1,
                len(candidate.descriptor.capabilities)
                - len(canonical_request.required_capabilities),
                candidate.descriptor.preference_rank,
                self._TOOL_CLASS_ORDER[candidate.descriptor.tool_class],
                candidate.descriptor.tool_id,
                candidate.descriptor.version,
            )
        )
        bounded = matched[: canonical_request.maximum_candidates]
        for candidate in matched[canonical_request.maximum_candidates :]:
            self._reject(
                rejected,
                candidate.descriptor,
                ("outside maximum_candidates bound",),
            )
        candidates = tuple(bounded)
        selectable = any(item.selectable for item in candidates)
        metrics = ToolDiscoveryMetrics(
            registered=len(descriptors),
            considered=len(descriptors),
            matched=matched_count,
            selected=0,
            loaded=0,
        )
        return ToolDiscoveryResult(
            request=canonical_request,
            registry_digest=registry_digest,
            status="matched" if selectable else "no_match",
            candidates=candidates,
            rejected=tuple(rejected[:MAX_REJECTIONS]),
            selected_tool_ids=(),
            loaded_tool_ids=(),
            metrics=metrics,
        )

    def select(
        self,
        discovery: ToolDiscoveryResult,
        tool_ids: Iterable[str],
    ) -> ToolDiscoveryResult:
        self.verify_discovery(discovery)
        selectable = {
            candidate.descriptor.tool_id
            for candidate in discovery.candidates
            if candidate.selectable
        }
        try:
            iterator = iter(tool_ids)
        except TypeError as error:
            raise ToolRegistryError("selection must be an iterable of tool IDs") from error
        requested_values: list[str] = []
        seen: set[str] = set()
        for tool_id in iterator:
            if len(requested_values) >= discovery.request.maximum_candidates:
                raise ToolRegistryError("selection exceeds the request candidate bound")
            try:
                canonical_tool_id = _identifier(tool_id, "selected tool ID")
            except ToolContractError as error:
                raise ToolRegistryError("selection contains a malformed tool ID") from error
            if canonical_tool_id in seen:
                raise ToolRegistryError("selection contains duplicate tool IDs")
            if canonical_tool_id not in selectable:
                raise ToolRegistryError(
                    "selection contains unknown, unavailable, or ineligible tools: "
                    + canonical_tool_id
                )
            seen.add(canonical_tool_id)
            requested_values.append(canonical_tool_id)
        requested = tuple(requested_values)
        if not requested:
            raise ToolRegistryError("selection must contain at least one tool ID")
        requested_set = set(requested)
        ordered = tuple(
            candidate.descriptor.tool_id
            for candidate in discovery.candidates
            if candidate.descriptor.tool_id in requested_set
        )
        try:
            return discovery.with_selection(ordered)
        except ToolContractError as error:
            raise ToolRegistryError(f"invalid tool selection: {error}") from error

    def verify_discovery(self, discovery: ToolDiscoveryResult) -> None:
        if not isinstance(discovery, ToolDiscoveryResult):
            raise ToolRegistryError("discovery result is not canonical")
        _, registry_digest = self._canonical_state()
        if discovery.registry_digest != registry_digest:
            raise ToolRegistryError("discovery result belongs to a different registry")
        expected = self.discover(discovery.request)
        comparable_actual = discovery.with_selection(())
        if comparable_actual.to_dict() != expected.to_dict():
            raise ToolRegistryError(
                "discovery evidence was mutated or does not match the registry snapshot"
            )

    @staticmethod
    def _reject(
        rejected: list[RejectedTool],
        descriptor: ToolDescriptor,
        reasons: tuple[str, ...],
    ) -> None:
        if len(rejected) < MAX_REJECTIONS:
            rejected.append(
                RejectedTool(
                    tool_id=descriptor.tool_id,
                    version=descriptor.version,
                    reasons=reasons,
                )
            )

    @staticmethod
    def _ineligibility_reasons(
        descriptor: ToolDescriptor,
        request: ToolDiscoveryRequest,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if descriptor.status != "active":
            reasons.append(f"tool status is {descriptor.status}")
        if request.execution_mode == "READ_ONLY" and descriptor.authority_class != "READ_ONLY":
            reasons.append("execution mode does not permit the authority class")
        if request.execution_mode == "CONTROLLED_WRITE" and descriptor.authority_class not in {
            "READ_ONLY",
            "CONTROLLED_WRITE",
        }:
            reasons.append("execution mode does not permit the authority class")
        if (
            request.allowed_authority_classes is not None
            and descriptor.authority_class not in request.allowed_authority_classes
        ):
            reasons.append("authority class is not allowed by the request")
        if RISK_LEVELS.index(descriptor.risk_level) > RISK_LEVELS.index(
            request.max_risk_level
        ):
            reasons.append("risk level exceeds the request maximum")
        if (
            request.allowed_tool_classes is not None
            and descriptor.tool_class not in request.allowed_tool_classes
        ):
            reasons.append("tool class is not allowed by the request")
        if (
            request.allowed_provider_ids is not None
            and descriptor.provider_compatibility
            and not set(request.allowed_provider_ids).intersection(
                descriptor.provider_compatibility
            )
        ):
            reasons.append("no allowed provider is compatible")
        if (
            request.agent is not None
            and descriptor.agent_compatibility
            and request.agent not in descriptor.agent_compatibility
        ):
            reasons.append("agent is not compatible")
        if (
            request.workflow is not None
            and descriptor.workflow_compatibility
            and request.workflow not in descriptor.workflow_compatibility
        ):
            reasons.append("workflow is not compatible")
        return tuple(reasons)
