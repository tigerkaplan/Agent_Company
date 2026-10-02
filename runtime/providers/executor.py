"""Executor implementation that bridges canonical jobs to local provider CLIs."""

from __future__ import annotations

from typing import Callable
from dataclasses import replace

from runtime.compute_policy import ComputeError, ComputeInputs, ComputePolicy, ProviderLimits, binding
from runtime.compute_policy.canonical import bind_project_context

from runtime.actions.runtime import ControlledWriteRuntime
from runtime.core.jobs import utc_now
from runtime.core.task_contract import TaskContractError
from runtime.execution.failures import TRUSTED_EXECUTION_FAILURES
from runtime.execution.models import ExecutionContractError, ExecutionRequest, ExecutionResult
from runtime.progress.models import ProgressError
from runtime.progress.runtime import tool_observation
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.context import ContextDiscoveryBlocked, ExecutionContextBuilder
from runtime.providers.models import ProviderExecutionResult, ProviderSelection
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
        compute_policy: ComputePolicy | None = None,
        compute_inputs: ComputeInputs | None = None,
    ) -> None:
        self.router = router
        self.context_builder = context_builder
        self.artifact_store = artifact_store
        self.clock = clock
        self.controlled_write_runtime = controlled_write_runtime
        # Only local runtime composition supplies these contracts. No provider
        # output or task metadata is promoted into routing policy.
        self.compute_policy = compute_policy if compute_policy is not None else ComputePolicy(
            tuple(ProviderLimits(p) for p in router.configuration.provider_ids))
        self.compute_inputs = compute_inputs

    def execute(self, request: ExecutionRequest, *, compute_inputs: ComputeInputs | None = None) -> ExecutionResult:
        from runtime.core.task_contract import require_tool
        require_tool(request, "provider_call")
        started_at = self.clock()
        selection: ProviderSelection | None = None
        compute_evidence = ()
        try:
            if type(self.compute_policy) is not ComputePolicy:
                raise ComputeError('Unsupported compute policy')
            inputs = compute_inputs if compute_inputs is not None else self.compute_inputs
            original_binding = binding(request)
            preliminary = self.compute_policy.decide(request, inputs)
            if any(p.provider_id not in self.router.configuration.provider_ids
                   for p in self.compute_policy.providers):
                raise ComputeError('Compute policy references an unconfigured provider')
            if preliminary.status != 'READY':
                raise ComputeError('No provider satisfies compute restrictions or budget')
            package = self.context_builder.build(request)
            if binding(request) != original_binding:
                raise ComputeError('Compute request changed during context discovery')
            if inputs is None:
                inputs = ComputeInputs(binding(request))
            inputs = bind_project_context(inputs, self.context_builder.repository_root,
                                          package.render())
            decision = self.compute_policy.decide(request, inputs)
            compute_evidence = ({
                'kind': 'observation', 'status': 'observed',
                'summary': f'Compute {decision.version}: {decision.status}/{decision.profile}; '
                           f'binding={decision.request_binding}; evidence={decision.evidence_digest}; '
                           + '; '.join(decision.reasons) + '; grants no authority',
            },)
            if decision.status != 'READY':
                raise ComputeError('No provider satisfies compute restrictions or budget')
            selection = self.router.resolve(
                request.capability, request.provider, request.execution_mode,
                eligible_providers=decision.eligible_providers,
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
            package = replace(package, compute_decision=decision)
            mutation_ref = None
            adapter = self.router.adapters[selection.actual_provider]
            from runtime.core.task_contract import require_provider_tool_confinement
            try:
                require_provider_tool_confinement(request, adapter)
            except TaskContractError:
                return ExecutionResult(
                    execution_id=request.execution_id, job_id=request.job_id,
                    status="blocked", summary=None, error=None,
                    blockers=({"code": "task_tools_unavailable", "message":
                        "The provider cannot enforce canonical task tool restrictions",
                        "retryable": False, "requires_human": False},),
                    provider=None, started_at=started_at, completed_at=self.clock(),
                    execution_mode=request.execution_mode, dry_run=request.dry_run)
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
                with tool_observation("provider_call"):
                    provider_result = adapter.execute(request, package)
            if not isinstance(provider_result, ProviderExecutionResult):
                raise ExecutionContractError("Provider adapter did not return its canonical result contract")
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
                    ) + compute_evidence,
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
                ) + compute_evidence,
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
        except ComputeError:
            return ExecutionResult(
                execution_id=request.execution_id, job_id=request.job_id,
                status='blocked', output_refs=(), summary=None, error=None,
                evidence=compute_evidence,
                blockers=({'code': 'compute_policy_blocked',
                           'message': 'Canonical compute inputs, eligibility, or budgets require resolution',
                           'retryable': False, 'requires_human': False},),
                provider=None, started_at=started_at, completed_at=self.clock(),
                execution_mode=request.execution_mode, dry_run=request.dry_run,
            )
        except ContextDiscoveryBlocked as blocked:
            return ExecutionResult(
                execution_id=request.execution_id, job_id=request.job_id,
                status="blocked", output_refs=(), summary=None, error=None,
                blockers=({"code": "context_unavailable",
                           "message": "Material clarification or a safe capability implementation is required before execution",
                           "retryable": False, "requires_human": False},),
                next_actions=tuple({"action": "supply_context", "description": question,
                                    "requires_human": False, "automatic": False}
                                   for question in (blocked.questions or (
                                       "Resolve the material context gap through canonical task inputs",))),
                provider=selection.actual_provider if selection is not None else None,
                started_at=started_at, completed_at=self.clock(),
                requested_provider=selection.requested_provider if selection is not None else request.provider,
                preferred_provider=selection.preferred_provider if selection is not None else None,
                fallback_used=selection.fallback_used if selection is not None else False,
                fallback_reason=selection.fallback_reason if selection is not None else None,
                execution_mode=request.execution_mode, dry_run=request.dry_run,
            )
        except ProgressError:
            raise
        except TRUSTED_EXECUTION_FAILURES:
            # Preserve typed canonical denials for the Worker. Flattening them
            # into provider runtime_error would lose trusted retry provenance.
            raise
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
