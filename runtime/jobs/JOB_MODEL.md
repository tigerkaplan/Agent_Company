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
| `parent_job_id` | Optional failed-attempt parent reference used only for retry ancestry. |
| `continuation_plan` | Optional explicit pre-authorized bounded step plan. Provider output cannot create or extend it. |
| `continuation` | Runtime-managed bounded checkpoint for one logical job and current authorized step. |
| `continuation_parent_job_id` | Explicit provenance link to the prior successful step job; distinct from retry ancestry. |
| `execution_budget` | Optional runtime-managed binding to one immutable logical-job execution budget. Input creation may specify only bounded elapsed/execution-unit dimensions; persisted jobs carry only budget ID, logical job ID, and policy digest. |
| `error` | Optional structured error state for the current attempt. |
| `approval` | Compact audit metadata for one resolved scoped approval, including its exact authorization fingerprint and, for a resolved human condition, the exact execution ID. The full persisted approval and execution artifacts remain authoritative. |

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
- Controlled-write jobs require explicit approval and independent review. Execution approval binds the exact task class, agent, skill, workflow, task, input references, review requirement, continuation plan digest, logical job, sequence, current step, attempt, project, capability, risk, mode, and execution scope.
- A continuation step may explicitly require approval/review and may constrain mode, dry-run, risk, and execution scope. Job state may tighten but never weaken those canonical step requirements.

## Retry Rule

Phase 6B implements only the simplest traceable retry. A failed attempt remains terminal. If `attempt < max_attempts`, retry creates a new `created` job with:

- `attempt` incremented;
- `parent_job_id` set to the failed job;
- canonical identity fields copied;
- previous outputs and errors left on the failed job;
- approval requirements preserved, with fresh explicit approval required when approval was previously needed.
- execution mode and scope copied without broadening; controlled-write retries always require a fresh scoped approval.

Retry does not mutate the failed job, bypass approval, or change the canonical agent, skill, workflow, task class, or capability merely because a provider was unavailable.

Where configured, retry and continuation children preserve the exact same
logical-job execution-budget binding. A new physical job or attempt never
resets consumed elapsed time or execution units. Budget availability grants no
retry, continuation, approval, review, controlled-write, Git, or deployment
authority.

Continuation means continuing authorized unfinished work after a valid step.
It creates a deterministic child execution record bound to the same logical job
ID, immutable plan digest, sequence, and current step;
it is not a retry and does not consume or reset retry authority. Progress text,
provider JSON, artifacts, and `next_actions` cannot create a continuation plan.
Completed and remaining step IDs must be the exact ordered prefix and suffix of
the plan. Retry and continuation parents must satisfy their distinct lifecycle,
attempt, and identity invariants for every retry, including retries without a
continuation checkpoint. One deterministic continuation-child position may not
have competing job IDs. `logical_statuses()` selects one authoritative
current head and reports its attempt while all
ancestor step records remain available as historical evidence. A direct
`needs_human` result uses `RESOLVE_HUMAN_CONDITION`, which can resume only the
exact waiting step after the approval and execution stores independently prove
the compact binding; it does not grant general execution approval.
The job-embedded continuation plan and digest are mutable representations, not
their own authority. One write-once authorized-plan snapshot is persisted for
the logical root at initial planned-job creation, preceded by independent
durable creation evidence containing the same canonical authority. Root, child,
and retry loads must match both records exactly. If creation evidence exists but
the anchor is missing, the logical job enters recovery hold; ordinary creation
cannot restore even a byte-identical plan. Missing or malformed authority, plan
changes, step-policy changes, reordered steps, or a recomputed digest fail
closed. Load and restart recovery never synthesize or refresh authority, and
CORE-02 defines no operator restoration flow.
It is rejected when the failed job has exhausted `max_attempts` or its error explicitly records `retryable: false`.
