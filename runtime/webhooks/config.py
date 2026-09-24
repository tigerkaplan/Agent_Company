"""Trusted webhook source configuration without tracked secrets."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from runtime.webhooks.models import WebhookContractError, WebhookEventType


_SAFE_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


@dataclass(frozen=True)
class WebhookSource:
    source_id: str
    enabled: bool
    allowed_event_types: tuple[WebhookEventType, ...]
    authentication_mode: str
    secret_env: str
    project_id: str | None = None

    def __post_init__(self) -> None:
        if _SAFE_SOURCE.fullmatch(self.source_id) is None:
            raise WebhookContractError("Webhook source_id is invalid")
        if self.authentication_mode != "HMAC_SHA256":
            raise WebhookContractError("Webhook authentication_mode is unsupported")
        if not self.allowed_event_types:
            raise WebhookContractError("Webhook source requires allowed_event_types")
        if not self.secret_env or len(self.secret_env) > 128:
            raise WebhookContractError("Webhook secret_env is invalid")
        if self.project_id is not None and (
            not self.project_id.strip()
            or len(self.project_id) > 128
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", self.project_id) is None
        ):
            raise WebhookContractError("Webhook project binding is invalid")

    def resolve_secret(self, environment: Mapping[str, str] | None = None) -> bytes:
        values = os.environ if environment is None else environment
        value = values.get(self.secret_env)
        if value is None or len(value.encode("utf-8")) < 16:
            raise WebhookContractError(
                "Webhook signing secret is unavailable or shorter than 16 bytes"
            )
        return value.encode("utf-8")


@dataclass(frozen=True)
class WebhookRuntimeConfig:
    sources: tuple[WebhookSource, ...]
    replay_window_seconds: int = 300
    max_request_bytes: int = 65536
    max_audit_records: int = 1000

    def __post_init__(self) -> None:
        if not 1 <= self.replay_window_seconds <= 3600:
            raise WebhookContractError("Webhook replay window is outside 1-3600 seconds")
        if not 1024 <= self.max_request_bytes <= 1048576:
            raise WebhookContractError("Webhook request bound is outside 1024-1048576 bytes")
        if not 1 <= self.max_audit_records <= 100000:
            raise WebhookContractError("Webhook audit retention is outside 1-100000")
        identifiers = [source.source_id for source in self.sources]
        if len(identifiers) != len(set(identifiers)):
            raise WebhookContractError("Webhook source IDs must be unique")

    @classmethod
    def from_file(cls, path: Path) -> "WebhookRuntimeConfig":
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise WebhookContractError(f"Could not read webhook config: {error}") from error
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise WebhookContractError("Webhook config has invalid schema_version")
        allowed = {
            "schema_version",
            "replay_window_seconds",
            "max_request_bytes",
            "max_audit_records",
            "sources",
        }
        if set(value) - allowed:
            raise WebhookContractError("Webhook config contains unsupported fields")
        raw_sources = value.get("sources")
        if not isinstance(raw_sources, list):
            raise WebhookContractError("Webhook config sources must be a list")
        sources: list[WebhookSource] = []
        for raw in raw_sources:
            if not isinstance(raw, dict):
                raise WebhookContractError("Webhook source entry must be an object")
            source_allowed = {
                "source_id",
                "enabled",
                "allowed_event_types",
                "authentication_mode",
                "secret_env",
                "project_id",
            }
            if set(raw) - source_allowed:
                raise WebhookContractError("Webhook source contains unsupported fields")
            event_types = raw.get("allowed_event_types")
            if not isinstance(event_types, list):
                raise WebhookContractError("Webhook allowed_event_types must be a list")
            try:
                parsed_types = tuple(WebhookEventType(item) for item in event_types)
            except (TypeError, ValueError) as error:
                raise WebhookContractError(
                    "Webhook allowed_event_types contains an unsupported event"
                ) from error
            if not isinstance(raw.get("enabled"), bool):
                raise WebhookContractError("Webhook source enabled must be boolean")
            sources.append(
                WebhookSource(
                    source_id=str(raw.get("source_id", "")),
                    enabled=raw["enabled"],
                    allowed_event_types=parsed_types,
                    authentication_mode=str(raw.get("authentication_mode", "")),
                    secret_env=str(raw.get("secret_env", "")),
                    project_id=raw.get("project_id"),
                )
            )
        return cls(
            sources=tuple(sources),
            replay_window_seconds=int(value.get("replay_window_seconds", 300)),
            max_request_bytes=int(value.get("max_request_bytes", 65536)),
            max_audit_records=int(value.get("max_audit_records", 1000)),
        )

    def source(self, source_id: str) -> WebhookSource | None:
        return next(
            (source for source in self.sources if source.source_id == source_id), None
        )

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "replay_window_seconds": self.replay_window_seconds,
            "max_request_bytes": self.max_request_bytes,
            "max_audit_records": self.max_audit_records,
            "source_count": len(self.sources),
        }
