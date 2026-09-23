# Human Approval Runtime

Phase 6G turns `waiting_approval` into a persisted human authorization boundary. Approval state is separate from job lifecycle state: a `PENDING` request is linked to a `waiting_approval` job through a compact `runtime-approval:` reference.

## Scoped Actions

- `EXECUTE_JOB` authorizes one pre-execution job boundary. `APPROVED` moves that job to `queued`; `REJECTED` moves it to `cancelled`.
- `COMPLETE_REVIEWED_JOB` authorizes acceptance after one exact execution and review. `APPROVED` moves the existing job directly to `completed`; `REJECTED` moves it to non-retryable `failed`.
- `COMMIT_CHANGE_SET` authorizes one immutable Git change set only after reviewed job completion. It binds the repository, base HEAD, exact file list, diff fingerprint, message, job, execution, and review. It does not change or rerun the completed job.
- `PUSH_GIT_COMMIT` authorizes one verified commit to one fingerprinted remote and exact branch at one expected remote HEAD.
- `CREATE_PULL_REQUEST` separately authorizes one PR repository, verified head commit, head/base branch pair, title, and body fingerprint. It grants no merge authority.

Approving reviewed work does not rerun its completed execution or review. It also does not grant broader permission to later attempts, executions, reviews, jobs, or actions.

## Creation And Persistence

Approval IDs are deterministic hashes of the job, optional execution, optional review, requested action, and exact authorization fingerprint. For commit approval, that fingerprint is derived from the immutable Git scope rather than the earlier execution scope. Repeating creation for the same unresolved boundary returns the existing request; a job cannot hold a second different pending request. Requests are stored as bounded JSON under `state/approvals/` and survive restart. If interruption occurs between request persistence and job linkage, the same explicit decision path verifies the persisted boundary and restores the missing link before resolution.

Every request records its reason, canonical risk level, execution mode, exactly one applicable execution/commit/remote scope, authorization fingerprint, compact evidence refs, and request time. Resolution records exactly one `APPROVED` or `REJECTED` decision, the self-asserted local operator identifier, `local_operator` actor type, timestamp, and optional reason. A resolved request cannot be changed or contradicted.

## Human Authority Boundary

Only the explicit `approval approve` or `approval reject` CLI path resolves a request in Phase 6G. Provider, executor, reviewer, task, prompt, workflow, skill, and artifact text has no approval authority. Strings such as `APPROVED` or `HUMAN CONFIRMED` remain untrusted content.

`--by` is a local audit label supplied by the operator. It is not authenticated identity, remote authorization, or proof that a particular person controlled the machine.

## Stale Protection

Resolution reloads canonical persisted job state and verifies the exact approval reference, job status, approval status, requested action, authorization fingerprint, and bound execution/review references. A changed or newer action scope is rejected as stale. Pending jobs are not queued and therefore are not claimed by Worker polling.

## Safety Boundary

Approval authorizes only the lifecycle continuation and exact action scope named by the request. Phase 6H may pass that scope to the controlled-write runtime; approval never grants unrestricted provider access. Push and PR approval are distinct and neither can authorize merge. There is still no unrestricted shell, deployment, or remote approval interface.
