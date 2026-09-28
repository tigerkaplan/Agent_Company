# Execution Budget

CORE-05 is CLOSED / COMMITTED at `63813b5` after CORE-05R3 PASS with no
Critical, Major, or Minor findings. CORE-06 is NEXT / NOT STARTED.

CORE-05 is a provider-independent runtime capability for bounding how much
already-authorized execution capacity one logical job may consume. It is not an
agent, approval source, retry policy, stop policy, provider-rate limit, token
account, or financial budget.

## Canonical Dimensions

- `max_elapsed_ms` bounds active execution time. Unset means this dimension is
  not configured; zero means exhausted before the first execution starts. The
  maximum configured value is seven days.
- `max_execution_units` bounds Worker-to-Executor delegations. Reservation of
  one unit occurs before context resolution and Executor invocation. Unset and
  zero retain the same distinct semantics. The maximum is 100,000.

Tool discovery and deferred definition/schema loading are not tool invocation
and consume no unit. CORE-05 defines no separate tool-call counter because the
current runtime has no canonical tool-invocation boundary. Adding one requires
an explicit later contract; provider prose cannot create it.

## Active Time

An active window begins after exact job authority is revalidated and one
execution unit is atomically reserved, immediately before canonical reference
resolution. It ends immediately after the Executor returns or raises. Reference
resolution, request construction, provider/executor work, and any tool work
inside that delegation count. Queue time, schedule delay, approval wait,
Reviewer work, human wait, continuation pause, and post-execution lifecycle
bookkeeping do not count.

In-process elapsed time uses a monotonic clock. Raw monotonic readings are never
persisted or compared across processes. Restart recovery uses trusted persisted
UTC boundaries and conservatively charges an active reservation through the
recovery observation time. A reservation is never silently refunded when work
may have begun. Persisted consumption never decreases; detected wall-clock
rollback latches a fail-closed clock fault and cannot increase remaining
capacity.

CORE-05 denies a new start when any configured dimension has zero remaining.
It does not forecast duration: positive remaining time permits one new start,
which may consume beyond the limit before future starts are denied. CORE-05
does not force-kill an in-flight process.

## Persistence And Identity

Each logical job has one deterministic budget ID. The immutable policy is
written with separate creation evidence and a SHA-256 content binding. Every
usage advancement has a store-managed monotonic sequence and writes a
content-addressed immutable event plus a separate write-once sequence claim
before updating the verified high-water head and current-state cache. Claims
and events form one linear digest chain. Every load walks the complete chain
from deterministic policy-bound genesis to its derived current event and
rejects gaps, missing records, duplicates, branches, unexpected files, broken
links, or content that differs from its storage identity. The mutable head and
state grant no historical authority; both must match the ledger-derived head.

Evidence binds the policy, counters, complete reservation-history digest, and
complete state digest. Independent write-once first-use evidence prevents a
previously used budget from being accepted as fresh genesis after its later
ledger is removed. A missing write or state/head/ledger mismatch after any
crash therefore fails closed rather than restoring capacity. History is
bounded by the existing 100,000-reservation limit: one record per reservation
and finalization, plus at most one latched clock-fault transition. Validation
rejects more than that fixed bound; observation-only reads and
denied/duplicate admissions do not append history.

Local file locking serializes admission, evidence, and state persistence,
preventing the final unit from being double-spent. Expected lock-path and lock
open/acquisition I/O failures become bounded canonical `ERROR` decisions; they
never fall back to unlocked mutation or execution. Malformed, missing, stale,
negative, decremented, overflowed, mismatched, or path-invalid state/evidence
fails closed. Restoring an older valid state, removing charged identities, or
coherently zeroing and re-digesting the mutable state, head, and current event
cannot reduce the independent write-once ledger evidence.

Reservation itself consumes the execution unit. Finalization is idempotent;
reusing an already-consumed execution identity never authorizes a second
delegation. Crash recovery marks uncertain active reservations reconciled and
charges elapsed wall time conservatively. The state schemas are
`../../schemas/execution-budget.schema.json` and
`../../schemas/budget-state.schema.json`; chained events and claims use
`../../schemas/budget-usage-anchor.schema.json` and
`../../schemas/budget-usage-claim.schema.json`.

## Logical-Job Inheritance

The initial physical job owns the logical budget. Ordinary retry children and
CORE-02 continuation children preserve the exact same `execution_budget`
binding. Neither a new attempt nor a new continuation step creates fresh
allowance. Retry ancestry (`parent_job_id`) remains distinct from continuation
ancestry (`continuation_parent_job_id`).

## Authority Boundary

Budget availability is necessary only where a budget is configured and is
never sufficient authority. Admission occurs after claim and exact approval /
continuation validation. An `ALLOW` decision cannot approve work, complete a
Reviewer decision, create continuation or retry authority, clear recovery hold,
authorize controlled write or Git, or deploy. Exhaustion produces a structured
`DENY_EXHAUSTED` decision and a failed job without fabricating a successful
`ExecutionResult`, retrying, continuing, or extending policy.

Providers receive no mutation handle for policy or usage. Provider requests for
more time, reset flags, counters, limits, or retry are descriptive content with
zero canonical effect. Budget policy is immutable after creation; CORE-05
implements no operator increase or tightening workflow.
