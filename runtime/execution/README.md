# Execution Contracts

`ExecutionRequest` and `ExecutionResult` are provider-neutral, JSON-serializable runtime contracts.

An execution request preserves the job's task, classification, canonical agent/skill/workflow/capability identity, risk, input references, resolved context references, review requirement, attempt, optional unresolved provider, explicit execution mode, optional bounded scope, and exact authorization fingerprint. It contains references rather than credentials, provider objects, project copies, or knowledge-base copies.

An execution result records the matching execution and job IDs, `succeeded` or `failed` status, execution mode, output references, optional summary and error, optional provider, and start/completion timestamps.

The `Executor` protocol performs exactly one request. Deterministic local success/failure stubs remain available for contract and lifecycle testing. Phase 6E adds an opt-in provider Executor that keeps routing, canonical context packaging, CLI adaptation, and normalized result handling outside the Worker.

Phase 6F treats `ExecutionResult.status == "succeeded"` as execution evidence, not verified completion. Review-required results pass through deterministic verification and a separate normalized `ReviewResult` before the lifecycle can complete.

Phase 6H keeps `READ_ONLY` as the default. A `CONTROLLED_WRITE` result can succeed only when independently observed mutation evidence was validated and applied within the exact approved scope.
