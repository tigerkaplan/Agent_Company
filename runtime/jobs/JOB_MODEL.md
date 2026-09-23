# Canonical Job Model

A canonical job is one executable unit of work created by the runtime after the orchestrator has classified the task, selected the canonical route, and identified governance requirements.

## Required Fields

| Field | Meaning |
| --- | --- |
| `job_id` | Stable runtime job identifier. It is a string and does not have to be a UUID. |
| `created_at` | ISO 8601 timestamp for job creation. |
| `task` | Human or business intent being executed. This preserves the meaningful request, not runtime mechanics. |
| `task_class` | Orchestrator task class from `../../orchestrator/dispatcher/TASK_CLASSIFICATION.md`. |
| `agent` | Canonical agent responsible for the work. Agent means WHO. |
| `workflow` | Canonical workflow that defines the ordered procedure. Workflow means ORDER. |
| `capability` | Provider-neutral execution capability from `../../orchestrator/routing/capabilities.yaml`. |
| `risk_level` | Canonical risk level from `../../orchestrator/approvals/risk-levels.yaml`. |
| `approval_status` | Current approval gate state. This records explicit approval handling; it is never inferred from inbound messages or events. |
| `execution_mode` | Explicit `READ_ONLY` or `CONTROLLED_WRITE` runtime authority. Defaults to `READ_ONLY`; it is never inferred from provider or task text. |
| `execution_scope` | `null` for read-only work, otherwise the exact bounded target/path/write/limit policy approved for controlled mutation. |
| `review_required` | Boolean indicating whether independent review is required before final acceptance. |
| `status` | Runtime lifecycle status from `lifecycle.yaml`. |
| `attempt` | Positive integer for this execution attempt. |
| `max_attempts` | Positive integer ceiling for attempts allowed by the dispatch/runtime policy. |
| `input_refs` | Array of references to inputs, connector contracts, project files, messages, or evidence. References are not embedded credentials. |
| `output_refs` | Array of references to outputs, drafts, logs, artifacts, reviews, or execution evidence. |
| `created_by` | Identifier for the creator, such as `dispatcher`, `scheduler`, or a parent job. |
| `last_updated_at` | ISO 8601 timestamp for the latest runtime state update. |

## Optional Fields

| Field | Meaning |
| --- | --- |
| `project_id` | Optional project identifier. Project state remains in `../../shared/projects/`, not inside the job. |
| `skill` | Optional canonical skill used for HOW. Some jobs may use a workflow without a specific reusable skill. |
| `provider` | Optional execution provider. It may remain unresolved until execution time and may be changed by provider routing/fallback without changing the canonical agent, skill, workflow, task class, or capability. |
| `parent_job_id` | Optional parent job reference for decomposed work, review jobs, or retry jobs. |
| `error` | Optional structured error state for the current attempt. |
| `approval` | Compact audit metadata for one resolved scoped approval, including its exact authorization fingerprint. The full request remains a separate artifact. |

## Distinctions

- `task` is the human or business intent.
- `job` is the runtime execution unit created to carry out that intent.
- `provider` is the execution engine and may remain unresolved until runtime execution.
- `connector` references identify data or approved action boundaries; they are not embedded credentials and do not grant approval.
- `project_id` may link to project state, but project state is not stored inside the job.
- `approval_status` records approval handling; it must not be inferred from inbound messages, webhook receipt, schedules, or connector reads.
- Approval request state (`PENDING`, `APPROVED`, or `REJECTED`) remains separate from job lifecycle state and is linked through `output_refs`.
- `review_required` and the `reviewing` lifecycle state keep reviewer work distinct from executor work.
- Review decisions are stored as separate runtime artifacts and referenced from `output_refs`; provider text never becomes a lifecycle transition directly.
- Controlled-write jobs require explicit approval and independent review. Approval binds the exact attempt, project, capability, risk, mode, and execution scope.

## Retry Rule

Phase 6B implements only the simplest traceable retry. A failed attempt remains terminal. If `attempt < max_attempts`, retry creates a new `created` job with:

- `attempt` incremented;
- `parent_job_id` set to the failed job;
- canonical identity fields copied;
- previous outputs and errors left on the failed job;
- approval requirements preserved, with fresh explicit approval required when approval was previously needed.
- execution mode and scope copied without broadening; controlled-write retries always require a fresh scoped approval.

Retry does not mutate the failed job, bypass approval, or change the canonical agent, skill, workflow, task class, or capability merely because a provider was unavailable.
It is rejected when the failed job has exhausted `max_attempts` or its error explicitly records `retryable: false`.
