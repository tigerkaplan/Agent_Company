"""Executor implementation that bridges canonical jobs to local provider CLIs."""

from __future__ import annotations

from typing import Callable

from runtime.actions.runtime import ControlledWriteRuntime
from runtime.core.jobs import utc_now
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.context import ExecutionContextBuilder
from runtime.providers.models import ProviderSelection
from runtime.providers.routing import ProviderRouter


class ProviderExecutor:
    supported_execution_modes = frozenset({"READ_ONLY", "CONTROLLED_WRITE"})

    def __init__(
        self,
        router: ProviderRouter,
        context_builder: ExecutionContextBuilder,
        artifact_store: FileProviderArtifactStore,
        *,
        controlled_write_runtime: ControlledWriteRuntime | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.router = router
        self.context_builder = context_builder
        self.artifact_store = artifact_store
        self.clock = clock
        self.controlled_write_runtime = controlled_write_runtime

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        started_at = self.clock()
        selection: ProviderSelection | None = None
        try:
            selection = self.router.resolve(
                request.capability, request.provider, request.execution_mode
            )
            if selection.actual_provider is None:
                return ExecutionResult(
                    execution_id=request.execution_id,
                    job_id=request.job_id,
                    status="blocked",
                    output_refs=(),
                    summary=None,
                    error=None,
                    blockers=(
                        {
                            "code": "provider_unavailable",
                            "message": "No eligible configured provider is locally available",
                            "retryable": True,
                            "requires_human": False,
                        },
                    ),
                    next_actions=(
                        {
                            "action": "retry_execution",
                            "description": "Retry after an eligible provider becomes available",
                            "requires_human": False,
                            "automatic": False,
                        },
                    ),
                    provider=None,
                    started_at=started_at,
                    completed_at=self.clock(),
                    requested_provider=selection.requested_provider,
                    preferred_provider=selection.preferred_provider,
                    fallback_used=selection.fallback_used,
                    fallback_reason=selection.fallback_reason,
                    execution_mode=request.execution_mode,
                    dry_run=request.dry_run,
                )
            package = self.context_builder.build(request)
            mutation_ref = None
            adapter = self.router.adapters[selection.actual_provider]
            if request.execution_mode == "CONTROLLED_WRITE":
                if self.controlled_write_runtime is None:
                    return ExecutionResult(
                        execution_id=request.execution_id,
                        job_id=request.job_id,
                        status="needs_human",
                        output_refs=(),
                        summary=None,
                        error=None,
                        blockers=(
                            {
                                "code": "capability_unavailable",
                                "message": "Controlled-write runtime is not configured",
                                "retryable": False,
                                "requires_human": True,
                            },
                        ),
                        next_actions=(
                            {
                                "action": "configure_capability",
                                "description": "A human must configure the controlled-write runtime before retrying",
                                "requires_human": True,
                                "automatic": False,
                            },
                        ),
                        provider=selection.actual_provider,
                        started_at=started_at,
                        completed_at=self.clock(),
                        requested_provider=selection.requested_provider,
                        preferred_provider=selection.preferred_provider,
                        fallback_used=selection.fallback_used,
                        fallback_reason=selection.fallback_reason,
                        execution_mode=request.execution_mode,
                        dry_run=request.dry_run,
                    )
                controlled = self.controlled_write_runtime.execute(
                    request, package, adapter
                )
                provider_result = controlled.provider_result
                mutation_ref = controlled.artifact_ref
            else:
                provider_result = adapter.execute(request, package)
            artifact_ref = self.artifact_store.create(
                request.execution_id, selection, provider_result
            )
            output_refs = (
                (artifact_ref, mutation_ref)
                if mutation_ref is not None
                else (artifact_ref,)
            )
            if provider_result.status == "succeeded":
                return ExecutionResult(
                    execution_id=request.execution_id,
                    job_id=request.job_id,
                    status="succeeded",
                    output_refs=output_refs,
                    summary=(
                        f"Provider {selection.actual_provider} completed; bounded "
                        f"{'preview' if request.dry_run else 'output'} is stored in the "
                        "provider artifact."
                    ),
                    error=None,
                    evidence=(
                        {
                            "kind": "provider_output",
                            "status": "observed",
                            "summary": "Bounded provider process output was persisted",
                            "ref": artifact_ref,
                        },
                    ),
                    artifacts=output_refs,
                    provider=selection.actual_provider,
                    started_at=started_at,
                    completed_at=self.clock(),
                    requested_provider=selection.requested_provider,
                    preferred_provider=selection.preferred_provider,
                    fallback_used=selection.fallback_used,
                    fallback_reason=selection.fallback_reason,
                    execution_mode=request.execution_mode,
                    dry_run=request.dry_run,
                )
            retryable = provider_result.error_category not in {
                "invalid_provider_output",
                "write_not_authorized",
                "write_scope_invalid",
                "path_escape_attempt",
                "protected_path_violation",
                "mutation_scope_violation",
                "mutation_evidence_missing",
                "provider_sandbox_mismatch",
                "provider_sandbox_unverified",
                "validation_failed",
            }
            error_code = provider_result.error_category or "provider_execution_failed"
            error_message = provider_result.error_message or "Provider execution failed"
            return ExecutionResult(
                execution_id=request.execution_id,
                job_id=request.job_id,
                status="failed",
                output_refs=output_refs,
                summary=None,
                error={
                    "code": error_code,
                    "message": error_message,
                    "retryable": retryable,
                },
                evidence=(
                    {
                        "kind": "provider_output",
                        "status": "failed",
                        "summary": "Bounded failed provider process output was persisted",
                        "ref": artifact_ref,
                    },
                ),
                artifacts=output_refs,
                next_actions=(
                    {
                        "action": "retry_execution" if retryable else "inspect_failure",
                        "description": (
                            "Retry the execution after the provider condition clears"
                            if retryable
                            else "A human must inspect the persisted provider failure"
                        ),
                        "requires_human": not retryable,
                        "automatic": False,
                        "ref": artifact_ref,
                    },
                ),
                provider=selection.actual_provider,
                started_at=started_at,
                completed_at=self.clock(),
                requested_provider=selection.requested_provider,
                preferred_provider=selection.preferred_provider,
                fallback_used=selection.fallback_used,
                fallback_reason=selection.fallback_reason,
                execution_mode=request.execution_mode,
                dry_run=request.dry_run,
            )
        except Exception:
            return ExecutionResult(
                execution_id=request.execution_id,
                job_id=request.job_id,
                status="failed",
                output_refs=(),
                summary=None,
                error={
                    "code": "runtime_error",
                    "message": "Provider runtime failed before a result could be persisted",
                    "retryable": True,
                },
                next_actions=(
                    {
                        "action": "retry_execution",
                        "description": "Retry the provider execution through the canonical Worker",
                        "requires_human": False,
                        "automatic": False,
                    },
                ),
                provider=selection.actual_provider if selection is not None else None,
                started_at=started_at,
                completed_at=self.clock(),
                requested_provider=(
                    selection.requested_provider if selection is not None else request.provider
                ),
                preferred_provider=(
                    selection.preferred_provider if selection is not None else None
                ),
                fallback_used=selection.fallback_used if selection is not None else False,
                fallback_reason=(
                    selection.fallback_reason if selection is not None else None
                ),
                execution_mode=request.execution_mode,
                dry_run=request.dry_run,
            )
