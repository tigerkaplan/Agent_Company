"""Construct configured local CLI adapters without provider logic in the Worker."""

from __future__ import annotations

from pathlib import Path

from runtime.providers.adapters import CliProviderAdapter, ProviderAdapter
from runtime.providers.config import ProviderConfiguration
from runtime.providers.routing import ProviderRouter


def build_provider_router(repository_root: Path) -> ProviderRouter:
    configuration = ProviderConfiguration(repository_root)
    adapters: dict[str, ProviderAdapter] = {
        provider_id: CliProviderAdapter(
            configuration.cli_config(provider_id), repository_root
        )
        for provider_id in configuration.provider_ids
    }
    return ProviderRouter(configuration, adapters)
