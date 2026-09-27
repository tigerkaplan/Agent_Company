# Execution Contracts

CORE-01 Canonical Result Contract is COMPLETED / CLOSED after a successful
final independent closure review with no Critical or Major findings. CORE-02
Continuation Policy is CLOSED / READY TO COMMIT after CORE-02R6 PASS. An
aggregate serialized-result byte ceiling remains FUTURE HARDENING / NON-BLOCKING.

`ExecutionRequest` and `ExecutionResult` are provider-neutral, JSON-serializable runtime contracts. Execution Result = WHAT HAPPENED; it is not a provider response format, job lifecycle state, review decision, continuation policy, or authority to perform another action.

An execution request preserves the job's task, classification, canonical agent/skill/workflow/capability identity, risk, input references, resolved context references, review requirement, attempt, optional unresolved provider, explicit execution mode, optional bounded scope, and exact authorization fingerprint. It contains references rather than credentials, provider objects, project copies, or knowledge-base copies.

Authoritative crash reconciliation requires every canonical `ExecutionRequest`
field to be explicitly present in persisted evidence. Model defaults remain
construction conveniences only; they cannot fill omitted persisted fields and
thereby suppress a real execution.

An execution result records the matching execution and job IDs, one bounded status, structured evidence, bounded artifact references, concrete blockers, inert machine-readable next actions, retryability, execution mode, optional summary and error, optional provider-routing metadata, optional usage metadata, and start/completion timestamps. The canonical JSON representation is `../../schemas/execution-result.schema.json`.

The bounded execution-result statuses are:

- `succeeded`: execution produced a canonical successful outcome. This is still evidence, not verified job completion.
- `failed`: execution failed and includes structured error metadata; blockers are disallowed so failure does not overlap `blocked` or `needs_human`.
- `blocked`: execution cannot continue because at least one concrete non-human blocker exists. It has no execution error and may carry descriptive retryability.
- `needs_review`: execution produced work that must enter the existing independent Reviewer gate. It has no error, blockers, or human-required next action.
- `needs_human`: the result identifies at least one blocker that requires human action. Worker creates a scoped `RESOLVE_HUMAN_CONDITION` request; this is not blanket execution approval.

Retryability is descriptive result metadata only. It does not authorize retry, continuation, resubmission, or Scheduler retry creation. Existing Scheduler retry infrastructure remains governed by its separate job-level authority; Worker deliberately records canonical result failures as non-retry-authorized. Job states such as `reviewing`, `waiting_approval`, `completed`, and `failed` remain governed by the job lifecycle. Review decisions remain `PASS`, `FAIL`, `RETRY`, and `NEEDS_HUMAN`.

Evidence entries contain only a bounded kind, observation status, summary, and optional canonical reference. They may describe deterministic checks, file references, command results, observations, or bounded provider output. Hidden reasoning and raw chain-of-thought are neither required nor accepted as evidence. Artifacts are references rather than embedded large contents. Blockers are concrete inability-to-continue records, not warning lists. Every next action declares `automatic: false`; CORE-01 records possible continuation but executes none.

CORE-02 consumes only trusted canonical plan/checkpoint and gate state.
`next_actions` may be compared by a future authorized planner but never grants
continuation authority itself. Progress is not completion: a logical plan is
terminal only when its canonical remaining-work set is empty and all required
review and approval gates are satisfied.

Execution approval authorizes exact work rather than scope alone. Its
fingerprint binds task, task class, canonical agent, skill, workflow,
capability, project, input references, review requirement, risk, execution mode,
dry-run state, execution scope, plan digest, logical job, continuation sequence,
current step, attempt, and the remaining execution-authority fields.

Provider adapters keep native stdout/stderr in their existing bounded, sanitized provider artifact. `ProviderExecutor` normalizes the provider outcome into this contract and refers to that artifact, so consumers do not parse Claude, Codex, or future-provider prose. `LocalExecutor` emits the same contract without assuming an LLM, prose generation, or provider usage.

`artifacts` is the single canonical source of artifact references. `output_refs` remains only as a compatibility alias for existing Phase 6/7/8 consumers and is always derived from `artifacts`; conflicting inputs fail closed. New results serialize both with identical references. Typed `FileExecutionStore.load()` rehydrates through `ExecutionResult.from_dict()`, supplies safe defaults for historical results, bounds/sanitizes historical error details, and never rewrites a file merely by reading it. `load_raw()` exists only for narrow compatibility and diagnostics.

Canonical result values are deeply immutable after construction through immutable mapping values that do not inherit from `dict` and reject post-construction attribute replacement or deletion. Construction and typed loading reject malformed statuses, divergent artifact aliases, unbounded or ambiguous structured entries, credential-shaped content, secret-bearing field names, full environment fields, and hidden-reasoning fields. Error details are limited to a small flat scalar map; canonical integers and finite floating-point values use the signed 64-bit magnitude range, while NaN and infinity are rejected. Provider raw output remains outside the result object and bounded provider artifacts redact API, Telegram, GitHub, bearer-token, quoted JSON/config credential fields, and private-key shapes before persistence.

Canonical new-record validation normalizes only the `artifacts`/`output_refs` compatibility alias before enforcing every schema-required field. An `artifacts`-only canonical payload or an `output_refs`-only legacy payload is normalized to identical fields, while a payload containing unequal aliases fails closed. Canonical serialization continues to derive `output_refs` from `artifacts`. Broader historical defaulting remains confined to the explicit typed-load compatibility path and does not weaken new-record validation.

The `Executor` protocol performs exactly one request. Deterministic local success/failure stubs remain available for contract and lifecycle testing. Phase 6E adds an opt-in provider Executor that keeps routing, canonical context packaging, CLI adaptation, and normalized result handling outside the Worker.

Phase 6F treats `ExecutionResult.status == "succeeded"` as execution evidence, not verified completion. Both policy-required successful results and canonical `needs_review` results pass through deterministic verification and a separate normalized `ReviewResult` before the lifecycle can complete. `needs_human` preserves a fail-closed human-required result and creates only a scoped resolution request; it does not synthesize execution approval. Resumed execution revalidates the approved resolution and original `needs_human` request/result in their authoritative stores rather than trusting job-local duplicated references. Reviewer packages expose the structured CORE-01 fields directly rather than requiring provider-prose parsing.

Phase 6H keeps `READ_ONLY` as the default. A `CONTROLLED_WRITE` result can succeed only when independently observed mutation evidence was validated and applied within the exact approved scope.
