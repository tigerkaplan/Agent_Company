"""Shared canonical secret detection for persisted runtime contracts."""

from __future__ import annotations

import re
from typing import Any


_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "access_token",
        "auth_token",
        "bot_token",
        "client_secret",
        "credential",
        "credentials",
        "github_token",
        "password",
        "secret",
        "shared_secret",
        "private_key",
        "telegram_token",
        "token",
        "webhook_secret",
        "environment",
        "env",
        "chain_of_thought",
        "hidden_reasoning",
    }
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b\d{7,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(
        r"(?i)\b[A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|TOKEN|PASSWORD|SECRET)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def normalize_sensitive_key(value: Any) -> str:
    """Return the canonical normalized representation used for key checks."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_")


def is_sensitive_key(value: Any) -> bool:
    """Return whether a structured field name is canonically sensitive."""
    normalized = normalize_sensitive_key(value)
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        (
            "_api_key",
            "_access_token",
            "_auth_token",
            "_password",
            "_secret",
            "_token",
            "_credential",
        )
    )


def contains_secret(value: str) -> bool:
    """Return whether text contains a canonical high-confidence secret shape."""
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)
