# CORE-07 Progress Events

CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS with no Critical, Major,
or Minor findings.
CORE-01 through CORE-11 are CLOSED / COMMITTED. GOV-02 is NEXT / NOT STARTED;
graph execution and observability dashboards are not started.

`ProgressEvent` is a frozen, schema-validated, provider-neutral observation.
`progress != completion`. Event consumers must resolve canonical job, execution,
Reviewer, Approval, retry, continuation, and budget records for actual authority.
The progress module never mutates those records or grants their authority.
GOV-01F2 reads independent gate observations to veto inconsistent persisted task
authority; matching observations alone cannot authorize execution or DONE.
No provider-facing progress ingestion endpoint exists.

## Model and semantics

- A closed event vocabulary, logical-job/job identity, optional execution and
  canonical step identity, a bounded reason enum, and an optional evidence ID.
- `authoritative` is always false. Unknown fields and authority-shaped fields are
  rejected. No provider prose, command arguments, secrets, timestamps, or raw
  exception messages are copied into events.
- Event identity is SHA-256 of canonical content. Sequence is the serialized
  append order, not a wall clock. Replaying an identical boundary is a no-op.
- `task_gate_observed` binds a canonical gate boundary digest at task creation
  or review strengthening. Only the canonical TaskContractStore emits these
  observations, before its gate/job writes. Missing or conflicting history holds
  the task; reconciliation cannot recreate it from job snapshots. These events
  remain non-authoritative and consume the existing bounded journal capacity.
- A durable pending bundle reserves `transition_requested` and all resulting
  observations before a job write. Delivery occurs only after checking canonical
  state. A request event alone does not assert success. Heartbeats and unchanged
  state do not create a stream of duplicate events.
- `execution_started` means the Worker admitted an execution. `execution_completed`
  means a successful execution result was persisted; it does not satisfy review.
- `job_completed` is emitted only from canonical completed state and, for a
  continuation, terminal state with no remaining steps. An intermediate completed
  attempt emits `step_completed`, without claiming logical job completion.
- `tool_started`, `tool_completed`, and `tool_failed` wrap the actual host adapter
  invocation in both read-only and controlled-write execution. Tool completion
  means the call returned, not that its returned result passed validation. Hidden
  provider-internal tool calls are not observable here and are not invented.
- Retry decisions produce `retry_requested`, `stop_requested`, or
  `replan_requested`; executing an authorized retry produces `repair_started`.
  Replan events do not invoke a Planner or change a plan.
- Reviewer/human waits and failures, budget denial, cancellation, failed jobs,
  execution exits, and job-bound Worker exits leave evidence. An idle poll or an
  error with no identifiable canonical job is not fabricated into a job event;
  existing Scheduler audit/error records remain the runtime-level evidence.
- `recovery_completed` records the outcome actually returned by execution-result
  recovery (including a `worker_error` result). It does not invent an exit for the
  interrupted worker or imply successful task completion.
  An interrupted recovery with no durably returned outcome records `worker_error`,
  never an inferred success from the job's terminal state.

## Persistence and bounds

The configured jobs root contains `.progress/<logical-job-id>.sqlite3`. This
inherits existing host state-root routing and the jobs Git-ignore boundary.
SQLite is a Python standard-library dependency; canonical operational stores
remain unchanged. The existing cross-process file-store lock serializes journal
access. FULL synchronous transactions atomically append the event and update its
hash-chain head. First creation uses a temporary database and atomic replacement.
Event rows are transactional inserts, with SQL update/delete guards. The pending
delivery table is bounded coordination metadata, not an authority source. Its rows
are removed only after delivery or verification that the canonical write did not
occur. Full table/constraint and trigger definitions are checked on every access.
Intact R1/F1 journals are migrated transactionally to schema version 2; altered
definitions are rejected. A bounded `recovery` row reserves one outcome slot
before recovery can change job state. Its ready flag and closed event payload
store delivery state only, never execution or approval authority.

Every read/append validates the complete bounded journal: schema, binding,
canonical JSON, event identity, contiguous sequence, chain, and high-water head.
There are at most 128 events per physical job and 4,096 per logical job; each
event is at most 4,096 bytes and a database above 32 MiB is rejected. History is
never silently truncated or evicted. Duplicate delivery remains a no-op even at
capacity; new events at capacity fail closed. Capacity counts both delivered and
reserved events, so concurrent appends cannot consume reserved terminal slots.
Conflicting terminal states or duplicate terminal identities fail integrity
validation, including historical journals; invalid history is not rewritten.

These are local integrity checks, not cryptographic authentication against an
owner with arbitrary filesystem access. A complete database replacement/rollback
is outside this evidence store's threat boundary. Progress still grants no
authority even if someone fabricates a valid observation.

## Restart and failure handling

SQLite rollback recovery handles interrupted existing-journal transactions.
Deterministic event identities handle concurrent/replayed delivery. Worker and
Scheduler reconcile validated canonical job states and already-persisted retry
decisions before new work. A job write committed just before event delivery can
therefore be observed on restart, including an already-terminal job. Reconciliation
does not create retry decisions or reserve new work. A shared transition lock
serializes fresh lifecycle validation, state writes, and observations across
threads/processes. Changed source status rejects a stale transition, and terminal
canonical records cannot be rewritten. Before any subsequent job write, the
previous persisted state is also observed.

Before writing canonical state, the entire observation bundle reserves capacity
in a committed pending row, bound to the before/after job digests. Thus a terminal
write is always backed by durable reserved evidence, even during a delivery gap.
Reconciliation verifies the actual canonical state and exact expected bundle, then
atomically delivers the reserved events and removes the pending row. If the job
write never occurred, it cancels that reservation without completing the job.
An unexpected canonical digest or altered bundle fails closed. Progress intent
never writes or completes a job. A process exit midway through event insertion
rolls back the whole delivery transaction while preserving its reservation.

Execution result reconciliation emits from immutable validated results. A start
without a result remains an incomplete execution; progress does not infer success
or authorize re-execution. Existing lease recovery/CORE-06 decisions own recovery.
Malformed storage or exhausted capacity blocks further affected execution and
returns an error. When the evidence medium itself is unavailable, durable error
delivery cannot be guaranteed; the runtime reports the failure rather than
silently dropping an event or declaring completion.

Recovery attempts serialize under a separate cross-process lock. Before applying
a persisted result, the recovery reserves one slot in the same journal capacity
accounting used by transition bundles. The actual returned outcome is committed
to that reservation before event delivery. Event insertion, hash-chain/head update,
and reservation removal commit together. Job reconciliation drains ready delivery
records for every status, including terminal jobs, without executing work again.
Worker recovery also discovers abandoned unfinished reservations under its lock
and records an interrupted recovery as `worker_error`. It never invents a
`worker_exited` event or treats journal intent as permission to change a job.
Identical outcome delivery is idempotent. A recovery starting at 124/128 events
with an unobserved successful result rejects the terminal transition; at 123/128,
the result, terminal bundle, and recovery event fit exactly, including replay.

## Validation

R3 passed 14/14 recovery/adversarial tests, 75/75 CORE-07 targeted tests,
650/650 existing regressions, and 989/989 full regression. A separate reviewer
using the same provider independently reproduced interrupted post-terminal
delivery, both capacity boundaries, and repeated-recovery idempotency. This
is recorded review evidence, not a cross-provider audit.

Run `python -m unittest runtime.tests.test_progress runtime.tests.test_progress_f1 runtime.tests.test_progress_f2 -q` for contracts, real Worker
and provider-boundary instrumentation, gates, budget denial, retry/repair/replan,
continuation completion, authority isolation, bounded history, malformed storage,
thread/process duplicate delivery, process-crash rollback, and reconciliation.
See `PROJECT_STATE.md` for the exact implementation checkpoint validation results.
