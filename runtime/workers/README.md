# Workers

The single-process `worker run-once` coordinator claims at most one queued job, resolves canonical references, builds a provider-neutral execution request, delegates to an Executor, stores the request/result artifact, and updates the job through the existing lifecycle engine.

Phase 6E retains deterministic local success/failure Executors and adds an opt-in provider Executor. Phase 6F adds an optional Reviewer Runtime after successful execution. Phase 6G links `NEEDS_HUMAN` to a persisted approval request. Phase 6H lets an explicitly approved provider job request bounded staged mutation. Provider-mode CLI workers enable review; local test Executors remain read-only.

## Responsibility

A worker must:

- claim a queued job;
- resolve agent, optional skill, workflow, and capability references from canonical repository structures;
- resolve an optional `project_id` to ordered project-state references without copying project contents;
- verify approval state before risky or externally consequential execution;
- resolve the explicit execution mode and preserve its exact approved scope;
- build an `ExecutionRequest` and call one Executor;
- capture result references and execution evidence;
- hand important or high-risk outputs to a reviewer when required;
- update runtime state using the canonical lifecycle.

## Run-Once Flow

```text
queued -> running -> resolve references -> ExecutionRequest -> Executor
  success, review_required=false -> completed
  success, review_required=true  -> reviewing -> deterministic verification -> reviewer
    PASS                         -> completed
    FAIL                         -> failed
    RETRY                        -> failed attempt + bounded child attempt
    NEEDS_HUMAN                  -> PENDING COMPLETE_REVIEWED_JOB approval
      APPROVED                   -> completed without re-execution
      REJECTED                   -> failed, non-retryable
  failure                        -> failed
```

Missing canonical configuration produces an explicit failed execution artifact and a failed job. Provider failures are classified as `provider_unavailable`, `provider_timeout`, `provider_execution_failed`, `invalid_provider_output`, or `runtime_error`. A malformed job that cannot satisfy the canonical model returns an explicit worker error and remains available for inspection.

Controlled-write failures retain specific categories including `write_not_authorized`, `write_scope_invalid`, `path_escape_attempt`, `protected_path_violation`, `mutation_scope_violation`, `mutation_evidence_missing`, `controlled_execution_failed`, and `validation_failed`. They are not converted into a fake read-only success.

Project-state references are resolved against the configured canonical reading order and must remain inside the selected project directory. Raw Executor exception text is not persisted because it may contain sensitive implementation details.

## Must Not

A worker must not:

- bypass approval;
- resolve or infer a human approval;
- infer approval from inbound messages, connector reads, webhook receipt, or schedules;
- invent missing project state;
- own business routing or change canonical task classification;
- directly embed provider-specific business logic;
- collapse reviewer work into executor work;
- store long-term project state inside runtime job records.

## Local Coordination

The Worker remains a one-job execution coordinator. Phase 6M adds a separate foreground Scheduler loop that evaluates eligibility, creates a claim, delegates the claimed job to Worker, refreshes its lease through heartbeat, and recovers expired claims after bounded backoff. Scheduler concurrency is fixed at one and an OS-backed scheduler lock prevents two loops sharing one scheduler state root.

Provider mode must still be selected explicitly and is bounded by scheduler cycle/day guards. For review-required jobs it may consume one execution call and one separate review call. There is no distributed queue, parallel provider execution, connector runtime, or installed daemon/service. Automated tests use fake provider adapters and must not call real providers.
