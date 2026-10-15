# Human Approval Runtime

## MEM-02B exact learning disposition

SET_LEARNING_DISPOSITION supports only PROMOTE/REVOKE/SUPERSEDE. A host must
explicitly install LearningInstallation with one project/root, memory source and
existing fixed logical-job journal. LearningIntent describes the whole operation,
proposal, applicability, evidence/counterevidence, deduplication, conflicts,
explicit initialization and expected genesis/index/revision/predecessor.
LearningScope additionally pins exact preparation job/attempt/contract/execution,
original verified completion receipt, full output and independently persisted
PASS review with full-intent deterministic coverage, plus current governance.

The approved scope grants only that local operational disposition. It never enters
compact job approvals or completion evidence. Legacy actions retain their exact
serialization/fingerprints and reject learning scope. Local operator labels are
self-asserted audit claims, not authenticated signatures. Source changes invalidate
stale authority without migrating or re-attesting historical tasks/receipts.

The existing FileApprovalStore owns `.learning/<project-digest>/` genesis/index,
one separate reservation, and immutable before/after transitions. Approval,
single-use action consumption, revision chain, current index, result pair and
non-authoritative journal observations must agree for eligibility. Supersession
updates both heads in one index replacement. Rejection preserves rationale but
activates nothing. Terminal versions require a newly approved proposal version.
Withdrawal uses fresh reviewed negative evidence; original positive factual
evidence is unnecessary when the current authority chain remains verifiable.

The dedicated ActionDecision application boundary holds the existing transition
lock through shared consumption, effect and confirmation. It has no callback,
approval boolean or caller-controlled already-locked flag. Limits are 32 lineages,
32 retained transitions, 32 items per collection, 128 KiB per learning record and
1 MiB aggregate learning-artifact reads, with stricter existing bounds preserved.
Capacity exhaustion denies work without pruning, archival or migration.

prepare_learning_scope, inspect_learning, check_learning and CLI reconciliation
are read-only. They create no locks/directories/temp files or persistent writes.
Missing/partial/rolled-back evidence and unresolved reservations hold planning.
No replay, repaired approval, synthetic witness/result, refunded effect or
automatic hold release is available; other recovery needs separately scoped work.

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
