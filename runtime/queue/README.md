# Queue

Phase 6B represents the local queue through canonical job records whose status is `queued`. It does not maintain a second queue file. `claim` reads valid records in `(created_at, job_id)` order and moves the oldest queued job to `running`.

Per-job writes use atomic replacement. Claims are serialized with a local OS-backed file lock and persist `claimed_by`, `claimed_at`, `lease_until`, and `heartbeat_at` before a Worker receives the job. Expired claims are recovered through bounded retry semantics. This prevents concurrent duplicate claims within the shared local state root, but it is not a distributed queue or database transaction.

## Queue Rules

- Default ordering is FIFO.
- Priority may be supported later as an explicit scheduling/routing feature.
- The queue stores job references and runtime state, not business knowledge.
- The queue is provider-neutral; there must not be separate provider-specific queues for canonical jobs.
- The queue must not contain provider-specific execution logic.
- Jobs blocked on human approval or review remain in the corresponding lifecycle state rather than being silently requeued. An approved `EXECUTE_JOB` request returns a pre-execution job to `queued`, never directly to `running`. An approved `COMPLETE_REVIEWED_JOB` request completes the already-executed job without queueing or rerunning it.
