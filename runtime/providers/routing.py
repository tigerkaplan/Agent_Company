"""Canonical capability, preference, availability, and fallback resolution."""

from __future__ import annotations

from runtime.providers.adapters import ProviderAdapter
from runtime.providers.config import ProviderConfiguration, ProviderConfigError
from runtime.providers.models import ProviderAvailability, ProviderSelection


class ProviderRouter:
    def __init__(
        self,
        configuration: ProviderConfiguration,
        adapters: dict[str, ProviderAdapter],
    ) -> None:
        self.configuration = configuration
        self.adapters = dict(adapters)
        missing = set(configuration.provider_ids) - set(self.adapters)
        if missing:
            raise ProviderConfigError(
                f"Missing provider adapters: {', '.join(sorted(missing))}"
            )

    def resolve(
        self,
        capability: str,
        requested_provider: str | None,
        execution_mode: str = "READ_ONLY",
    ) -> ProviderSelection:
        eligible = [
            provider_id
            for provider_id in self.configuration.provider_ids
            if self.configuration.eligible(provider_id, capability)
            and self.configuration.supports_execution_mode(provider_id, execution_mode)
        ]
        if not eligible:
            raise ProviderConfigError(
                f"No configured provider is eligible for {capability}/{execution_mode}"
            )
        ranked = sorted(
            eligible,
            key=lambda provider_id: (
                -self.configuration.weight(provider_id, capability),
                self.configuration.provider_ids.index(provider_id),
            ),
        )
        if requested_provider is not None:
            if requested_provider not in self.configuration.provider_ids:
                raise ProviderConfigError(
                    f"Requested provider is not configured: {requested_provider}"
                )
            if requested_provider not in eligible:
                availability = self.availability()
                actual = next(
                    (
                        provider_id
                        for provider_id in ranked
                        if availability[provider_id].available
                    ),
                    None,
                )
                return ProviderSelection(
                    requested_provider=requested_provider,
                    preferred_provider=requested_provider,
                    actual_provider=actual,
                    fallback_used=actual is not None,
                    fallback_reason=(
                        "requested_provider_ineligible_for_execution_mode"
                        if actual is not None
                        else "no_provider_available"
                    ),
                    execution_mode=execution_mode,
                )
            preferred = requested_provider
        else:
            preferred = ranked[0]

        availability = self.availability()
        if availability[preferred].available:
            return ProviderSelection(
                requested_provider=requested_provider,
                preferred_provider=preferred,
                actual_provider=preferred,
                fallback_used=False,
                fallback_reason=None,
                execution_mode=execution_mode,
            )
        for provider_id in ranked:
            if provider_id != preferred and availability[provider_id].available:
                return ProviderSelection(
                    requested_provider=requested_provider,
                    preferred_provider=preferred,
                    actual_provider=provider_id,
                    fallback_used=True,
                    fallback_reason="preferred_provider_unavailable",
                    execution_mode=execution_mode,
                )
        return ProviderSelection(
            requested_provider=requested_provider,
            preferred_provider=preferred,
            actual_provider=None,
            fallback_used=False,
            fallback_reason="no_provider_available",
            execution_mode=execution_mode,
        )

    def availability(self) -> dict[str, ProviderAvailability]:
        return {
            provider_id: self.adapters[provider_id].is_available()
            for provider_id in self.configuration.provider_ids
        }

    def resolve_review(
        self,
        executor_provider: str | None,
        risk_level: str,
    ) -> ProviderSelection:
        """Prefer an eligible available provider distinct from the executor."""
        capability = "independent_review"
        eligible = [
            provider_id
            for provider_id in self.configuration.provider_ids
            if self.configuration.eligible(provider_id, capability)
        ]
        if not eligible:
            raise ProviderConfigError(
                "No configured provider is eligible for independent review"
            )
        ranked = sorted(
            eligible,
            key=lambda provider_id: (
                -self.configuration.weight(provider_id, capability),
                self.configuration.provider_ids.index(provider_id),
            ),
        )
        availability = self.availability()
        different = [
            provider_id
            for provider_id in ranked
            if provider_id != executor_provider and availability[provider_id].available
        ]
        if different:
            selected = different[0]
            return ProviderSelection(
                requested_provider=None,
                preferred_provider=selected,
                actual_provider=selected,
                fallback_used=False,
                fallback_reason=None,
            )

        same_available = (
            executor_provider in eligible
            and executor_provider is not None
            and availability[executor_provider].available
        )
        if same_available and risk_level not in {"high", "approval_required"}:
            return ProviderSelection(
                requested_provider=None,
                preferred_provider=executor_provider,
                actual_provider=executor_provider,
                fallback_used=True,
                fallback_reason="different_reviewer_provider_unavailable",
            )

        preferred = ranked[0]
        return ProviderSelection(
            requested_provider=None,
            preferred_provider=preferred,
            actual_provider=None,
            fallback_used=False,
            fallback_reason=(
                "no_independent_provider_for_high_risk_review"
                if same_available
                else "no_provider_available"
            ),
        )
