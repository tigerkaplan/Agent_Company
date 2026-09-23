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
A heartbeat extends the active lease. Expired claims fail with a retryable,
bounded error and create at most one canonical child attempt after deterministic
backoff. Non-retryable and exhausted attempts remain terminal.

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
loops sharing that state root. Restart reconciles expired leases, retryable
failures that lack a child attempt, due schedules, due retry jobs, and ordinary
queued jobs. Completed jobs and emitted occurrences are not recreated.

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
