"""Provider-neutral executor interface."""

from __future__ import annotations

from typing import Protocol

from runtime.execution.models import ExecutionRequest, ExecutionResult


class Executor(Protocol):
    """Perform exactly one provider-neutral execution request."""

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Return a result without changing canonical job identity."""

