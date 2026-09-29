# Retry / Stop Policy

CORE-06 is the provider-independent runtime policy for repeating failed work.
It is CLOSED / READY TO COMMIT after CORE-06R6 PASS. The implementation
remains uncommitted at HEAD `065b3e9`; CORE-07 remains NOT STARTED.
External R6 evidence and closure validation are recorded in `PROJECT_STATE.md`.

`max_attempts` and `max_total_attempts` count total attempts, including the
initial execution. A failed attempt may create one deterministic child only
after the canonical policy returns `RETRY`. Provider prose, provider error
codes, `retryable`, `next_actions`, Eval output, continuation eligibility, tool
discovery, and remaining budget never create that authority.

Each logical job has one immutable policy binding and one bounded, atomic,
restart-safe decision history under the job store's `.retry-policy/` namespace.
Write-once sequence claims link every content-addressed decision from genesis.
An independent write-once accepted-revision ledger, with genesis and paired
creation evidence, is committed before revision witnesses, events, claims, and
caches. A separate immutable terminal tombstone anchors STOP/REPLAN_REQUIRED.
All inventories must match the complete bounded chain. First-use evidence
prevents genesis reset; the mutable high-water head and state are verified
caches, not rollback anchors. Missing STOP/REPLAN suffix evidence fails closed,
including deletion of event/claim/revision witnesses plus older state/head
replay, or loss of accepted-revision suffixes while terminal evidence survives.
Decision events bind the logical root, failed unit, source attempt, original
execution reference when present, immutable pre-delegation request/failure
anchors, exact work digest, policy digest, repair
scope, and deterministic retry identity. Missing policy/state/event evidence,
rollback, deletion, malformed values, path traversal, stale work, or duplicate
attempt identity fails closed.

The canonical decisions are `RETRY`, `STOP`, `REPLAN_REQUIRED`,
`NEEDS_HUMAN`, and `ERROR`. `REPLAN_REQUIRED` stops local retry and reports that
broader planning may be needed. It does not call a Planner, alter a plan,
authorize continuation, grant a write, invoke Git, or deploy. ORCH-01 remains
not started.

No-progress compares canonical failure and accepted progress-evidence digests;
provider claims of progress are ignored. Stuck detection observes repeated
lack of accepted state change. Cycle detection recognizes bounded repeated
canonical state signatures, including self, two-state, and longer cycles.
History and all numeric policy fields are explicitly bounded.

Retry authorization is limited to the failed unit. The child preserves task,
plan/current-step identity, inputs, workflow, agent/skill, capability, mode,
risk, review requirement, controlled-write scope, continuation authority, and
the same CORE-05 logical budget. Repair validation rejects sibling units,
unapproved paths, and broader capabilities. Controlled-write permission is the
intersection of the parent authorized scope and canonical failed-unit repair
allocation, including when the unit allocation is wider than the parent.
Multi-unit plans without an explicit unit write scope deny write repair;
parent scope alone cannot allocate sibling paths. Traversal and absolute paths
are rejected by the existing canonical path normalizer. Runtime-observed scope,
policy, schema, malformed-result, and unsupported-mode denials are non-retryable,
regardless of provider labels. Worker-observed failure provenance is persisted
independently of provider output and survives result reconciliation after crash;
missing provenance cannot become transient. Immutable original request/admission
and failure evidence preserve the original Approval requirement: mutable
`approved -> not_required` cannot weaken it. Fresh Approval and Reviewer gates
remain mandatory where already required.

Scheduler recovery asks this policy for every failed attempt; it never derives
retry authority from `error.retryable`. Retry reservation is persisted before
the child record, so restart can materialize the same deterministic child after
a crash before materialization. Materialized/consumed child identities cannot
be recreated if the child is deleted. A write-once execution reservation is
consumed atomically before budget admission and Executor delegation. Independent
consumed-attempt evidence precedes the reservation itself; attempt-scoped and
per-execution admission evidence additionally precede delegation. Losing both
reservation and attempt-admission pairs cannot reopen a consumed attempt, even
without a CORE-05 budget. Surviving per-execution admission (either half) or
execution-result evidence also requires a hold when attempt indexes are gone.
CORE-06F4 additionally recognizes canonical failed-attempt evidence and either
half of Worker-observed runtime-failure provenance. Losing every local
reservation/admission/result index cannot reopen an attempt while that
independent evidence survives; replaying an earlier running job does not refund it.
Missing evidence is never reconstructed as an unused attempt. Duplicate
deliveries reuse that execution's state/result. A reservation with no recorded
result returns `execution_reserved`; restart does not delegate that attempt
again. Existing execution-result reconciliation prevents a persisted
successful retry from repeating external work, and the CORE-05 ledger prevents
a crash or new process from refunding consumed capacity.

Reviewer-requested retry uses the same structured decision path, including
exhaustion and no-progress `REPLAN_REQUIRED`, without converting it to a generic
Worker error. A resolved CORE-02 human condition on ordinary unfinished work
remains distinct from retry; request anchors are execution-scoped, while retry
consumption is attempt-scoped.

Execution authorization is revalidated against the current verified retry
history before reservation and again at request admission. Any persisted STOP
or REPLAN_REQUIRED in the logical retry chain revokes earlier RETRY execution
authority, even if the old running child is replayed. Historical binding checks
remain available only for inspection/reconciliation and structured terminal
reporting; they do not authorize execution or repair.

CORE-06F3 shares typed integrity/authority/policy exception classes between the
Worker and ProviderExecutor. Canonical persistence errors, including wrapped
ExecutionStoreError from schema validation and failures while saving a result,
are non-retryable; generic provider prose never selects this classification.
CORE-06F4 normalizes canonical JSON decoding failures, including invalid UTF-8,
malformed JSON, decoder depth errors, and oversized numeric decoding failures,
at the trusted storage boundary. Existing typed integrity/schema failures stay
non-retryable through the Worker and ProviderExecutor; canonical context
corruption does not invoke a provider adapter.
The shared path-scope matcher uses Windows ordinal name comparison plus
filesystem identity for positive case aliases, and exact case on POSIX.
It never applies linguistic Unicode casefolding: physically distinct
src/straße and src/strasse remain disjoint. Ambiguous future case aliases
cannot grant scope, and forbidden future case aliases remain denied.

Missing independent consumption or history evidence is fail-closed; legacy
CORE-06 state without the new evidence is not silently migrated or repaired.
These application-integrity checks do not claim protection against an OS actor
who replaces or erases every independent canonical authority/evidence file.
