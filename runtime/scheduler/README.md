# Scheduler

Phase 6M extends the deterministic Phase 6D schedule model with a bounded,
local-first autonomous run loop. The Scheduler decides when work is eligible;
the existing Worker still decides how one claimed job executes through its
configured Executor.

## Responsibility Boundaries

- Scheduler = due-time evaluation, safe claim, lease recovery, and loop limits.
- Dispatcher = canonical scheduled task to job conversion.
- Queue and lifecycle = authoritative job eligibility and attempt state.
- Worker = execution, review, and approval-aware coordination.
- Executor and provider adapter = actual execution behind the Worker boundary.
- Approval Runtime = the only authority that resolves human-required states.
- Execution Budget Runtime = atomic capacity admission/accounting after all
  ordinary authority gates; it grants no authority itself.
- Retry Runtime = canonical failed-unit retry/stop decision and deterministic
  attempt reservation; it does not replan.

The Scheduler does not select agents, skills, routes, providers, or approval
outcomes. It never creates commit, push, pull-request, merge, release, or
deployment authority.

## Eligibility And Claims

Only `queued` jobs with approval already satisfied and `next_run_at` absent or
due may be claimed. `waiting_approval`, future, completed, failed, and cancelled
jobs are skipped. Claim updates are serialized through a local transaction lock
and persist `claimed_by`, `claimed_at`, `lease_until`, and `heartbeat_at` before
the Worker receives the job.

The initial loop is intentionally sequential: `max_concurrent_jobs` must be one.
A heartbeat extends the active lease. Expired claims fail with a canonical
lease-expiry class and may create at most one policy-authorized child attempt
after deterministic backoff. Descriptive `retryable` metadata is ignored as
authority. Exhaustion, permanent failure, stale authority, unsafe scope,
no-progress, stuck, and cycle conditions stop local retry or surface
`REPLAN_REQUIRED` according to policy.

## Scheduling And Recurrence

Jobs may be scheduled or rescheduled with a timezone-aware `next_run_at`.
Canonical timestamps are normalized to UTC. Existing schedule definitions retain
their `one_time` or `recurring` model with `hourly`, `daily`, and `weekly`
recurrence.

Each occurrence retains the deterministic Phase 6D key. Autonomous cycles emit
at most the next due occurrence for a schedule, then coalesce its next time to
the first future boundary. They do not launch a burst for every missed interval.
One-time schedules remain retained and disabled after successful dispatch.

## Restart And Shutdown

Scheduler state and bounded audit events are stored below
`runtime/state/scheduler-runtime/` by default. An OS-backed run lock prevents two
loops sharing that state root. Restart reconciles expired leases,
policy-eligible failures that lack a child attempt, due schedules, due retry
jobs, and ordinary
queued jobs. Completed jobs and emitted occurrences are not recreated.

CORE-02 restart reconciliation also inspects completed step jobs whose canonical
checkpoint is `ready`. It idempotently reserves or reactivates the deterministic
next-step child, then leaves ordinary queue claims, leases, approval eligibility,
and provider guards unchanged. A child that already exists is reused rather than
duplicated.

Before expired-lease retry handling, Scheduler reconciles immutable execution
results that survived an interrupted job/checkpoint transition. A persisted
result that cannot be bound to its exact canonical request blocks expired-lease
retry for that cycle instead of risking duplicate external execution. Status
derives one authoritative logical head, including its current attempt, per
continuation chain, so retained ancestor snapshots are evidence rather than
competing current states. A second job ID for the same canonical continuation
position is invalid state and fails closed instead of being hidden by head
tie-breaking. Ordinary and continuation retry ancestry use the same parent,
attempt, lifecycle, provenance, uniqueness, and cycle validation.
Scheduler recovery does not create continuation authority. Planned roots,
children, and retries must all reload the same write-once authorized-plan
snapshot; a missing snapshot or any full-plan/digest mismatch blocks recovery,
eligibility, and claim rather than rebinding the current mutable plan.
Independent durable creation evidence survives anchor-file loss. Evidence with
a missing anchor is a persistent recovery hold, not an uninitialized store, so
Scheduler restart, child reservation, retry recovery, and reconciliation cannot
recreate even an identical anchor through ordinary runtime APIs.

CORE-05 restart reconciliation also finalizes any persisted active budget
reservation conservatively before later claims. Retry and continuation jobs use
the original logical budget, so scheduler recovery cannot reset consumed time
or units. Exhaustion blocks a new Executor start but does not decide retry,
continuation, approval, review, Git, or deployment policy.

`scheduler stop` records a graceful stop request. The loop stops claiming new
work after its current Worker call returns. Interrupt handling leaves any
unfinished job claim in canonical job state for lease-based recovery rather than
marking false completion.

## Bounds And Dry Run

Safe defaults process one job per cycle with one concurrent Worker. Provider
mode is explicit and is additionally limited by generic per-cycle and per-day
run counters. These counters are a burst guard, not billing intelligence.

Scheduler dry-run only inspects eligible, future, blocked, retry, expired-claim,
and due-schedule state. It does not claim, dispatch, invoke a Worker or provider,
advance recurrence, persist scheduler state, or append audit events.

## CLI

```text
python -m runtime.cli scheduler run-once [--dry-run] [--executor local-success|local-failure|provider]
python -m runtime.cli scheduler run [--max-cycles N] [--poll-seconds N] [--dry-run]
python -m runtime.cli scheduler status
python -m runtime.cli scheduler stop
python -m runtime.cli scheduler list-due
python -m runtime.cli job schedule <job_id> (--at TIMESTAMP | --delay-seconds N)
python -m runtime.cli job reschedule <job_id> (--at TIMESTAMP | --delay-seconds N)
python -m runtime.cli job cancel <job_id>
```

The earlier `scheduler create/list/show/enable/disable/tick` commands remain
available. No Windows Service, Task Scheduler task, systemd unit, daemon
installation, distributed queue, database, or parallel provider execution is
introduced in Phase 6M.
