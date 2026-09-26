"""Canonical job and lifecycle operations."""

from __future__ import annotations

from typing import Any

__all__ = ["JobRuntime", "RuntimeError"]


def __getattr__(name: str) -> Any:
    """Keep compatibility exports without importing storage during package setup."""
    if name in __all__:
        from .jobs import JobRuntime, RuntimeError

        return {"JobRuntime": JobRuntime, "RuntimeError": RuntimeError}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
