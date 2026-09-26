# Phase 8 Always-On Host Architecture

## Status And Scope

Phase 8A defined the smallest production-quality host boundary that could keep
the current Agent Company runtime alive continuously. Phase 8B now implements
the host-configuration and persistent-state foundation, now completed and
closed after its successful final independent re-review.
It does not deploy, install a service, create a VPS or container image, start a
provider or Hermes, expose an endpoint, or grant merge or deployment authority.

The Phase 8A evidence baseline was the clean `master` checkout inspected on
2026-09-24. The current Phase 8B working tree passes 469 runtime tests on Python
3.14.3. Executable discovery during Phase 8A observed Python, Git, and Codex; it
did not observe `gh` or Claude. Executable presence is not authentication or
service availability.

## Current Runtime Assumptions

| Assumption | Verified repository evidence | Safe on an always-on host only when |
| --- | --- | --- |
| Local-first | Runtime and connector documentation use local CLI and local state boundaries. | One explicitly managed host remains canonical. |
| File-backed state | Jobs, executions, approvals, schedules, remote, notification, webhook, and scheduler state use local JSON/artifact stores. | State is on a durable local filesystem supporting file locks, `fsync`, and atomic replace; it is not placed on object storage or assumed to be a database. |
| Single-worker execution | Scheduler configuration requires `max_concurrent_jobs = 1`. | The limit remains one and only one scheduler owns a state root. |
| Scheduler/run loop | `SchedulerLoop.run()` is a foreground polling loop. | A supervisor restarts that foreground process without adding a second scheduler. |
| Claims, leases, heartbeat | Job claims persist claimant, lease, and heartbeat data; local claim and scheduler locks exist. | All runtime processes share one local state root and no distributed guarantee is claimed. |
| Retry/backoff | Scheduler uses bounded retry attempts and deterministic backoff. | Retry policy and attempt identity remain canonical runtime state. |
| Restart recovery | Scheduler reconciles expired leases, missing retry children, due schedules, and queued jobs. | Durable state is mounted before startup and corrupt or missing state fails closed. |
| Provider execution | Provider-neutral adapters invoke allowlisted local CLIs with bounded output and `shell=False`. | Provider mode stays explicit, credentials remain external, and availability/authentication are checked separately. |
| Telegram transport | The implemented adapter uses private-chat long polling and stable numeric IDs. | Exactly one poller uses the persisted offset and current configured identity mapping. |
| Notifications | Canonical events and per-destination delivery evidence are persisted and retry-bounded. | Notification delivery stays opt-in and cannot alter canonical job or approval state. |
| Localhost webhook ingress | HMAC-verified `TASK_SIGNAL` ingress and a loopback-only HTTP adapter exist. | It stays disabled by default in Phase 8 and remains loopback-only if a future host entrypoint is added. |
| Approval and Reviewer boundaries | Approval state is persisted and fingerprinted; Reviewer decisions are evidence, not human authority. | Host lifecycle code calls existing runtimes and never edits their JSON directly. |
| Controlled writes and Git | Staged controlled writes, commit, push, and PR creation have separate exact gates. | Host configuration grants no new paths or actions; merge, release, and deployment remain absent. |

These are single-host guarantees. Atomic per-file persistence, local OS file
locks, and leases do not become multi-host transactions, consensus, distributed
locking, or exactly-once external execution merely because the host is always
on.

## Canonical Host Boundary

```text
Agent Company Core
  -> Runtime Host (availability only)
    -> Process supervisor
    -> Persistent local state
    -> Existing provider CLIs
    -> Telegram Bot API over outbound HTTPS
    -> Loopback ingress only when explicitly enabled
```

The host may start, stop, restart, health-check, and supply storage or secrets
to the existing runtime. It does not own business classification or routing,
approval or Reviewer decisions, provider-selection policy, Git authority,
merge authority, or deployment approval.

Project repositories remain external authorities. They must be mounted or
checked out at explicit stable paths and are not copied into runtime state.

## Process Model

**Decision: B - a small number of separate supervised processes.**

The minimum Phase 8 host process set is:

1. `agent-company-scheduler`: the existing scheduler loop. It owns the
   synchronous Worker call and therefore does not need a separate Worker
   process. Provider mode and notifications remain explicit startup options.
2. `agent-company-telegram`: the existing Telegram long-poll loop, enabled only
   when its token and configured identity mapping are available.

No separate health process is required. A supervisor can report process state,
and a read-only status command can derive the minimum operational signals from
canonical state.

The webhook adapter is not part of the default process set. Phase 8C adds an
explicitly enabled `webhook-local` lifecycle entrypoint around the existing
HTTP server factory. It binds `127.0.0.1` only and creates no public listener,
TLS termination, reverse proxy, or deployment assumption.

Separate processes match the current foreground entrypoints, isolate Telegram
API failure from scheduling, allow independent restart limits, and avoid a new
in-process orchestrator. The cost is shared-file concurrency and two lifecycle
units. Phase 8 implementation must test those existing cross-process paths and
enforce one scheduler and one Telegram poller per state root. No distributed
worker, broker, database queue, or second source of truth is introduced.

## Startup, Shutdown, And Crash Recovery

### Startup order

1. Mount the persistent filesystem and verify ownership, free space, local
   locking, atomic replacement, and backup status.
2. Load non-secret host configuration and inject secrets from the external
   secret source. Do not copy them into the repository or runtime state.
3. Verify the pinned application revision, Python environment, schemas,
   configured project roots, provider executables, and credential paths. An
   executable check alone must not be reported as authenticated availability.
4. Validate the canonical state tree read-only. Missing, corrupt, duplicated,
   or permission-denied authority state stops startup.
5. Start the scheduler as the only scheduler for the state root.
6. Start Telegram long polling when configured. Telegram failure must not make
   canonical runtime state unavailable.
7. Start optional loopback webhook ingress only after its later entrypoint is
   implemented, tested, and explicitly enabled.

### Graceful shutdown order

1. Stop accepting optional webhook ingress.
2. Stop Telegram polling after the current bounded request/response cycle.
3. Request scheduler stop so it claims no new job.
4. Allow the active Worker call and heartbeat to finish within a documented
   shutdown deadline.
5. Persist final scheduler state, flush state and audit files, release locks,
   and stop the supervisor unit.

Phase 8C installs process-local SIGTERM/SIGINT handlers and handles
`KeyboardInterrupt`. The OS signal callbacks perform notification only by
setting an in-memory event. Normal lifecycle control flow then persists
`STOPPING`, requests component stop outside the metadata lock, and allows the
current bounded operation to finish. Windows console signal delivery depends on
the launching terminal or future supervisor. No forced PID termination exists.
If an outer supervisor deadline expires, it must not write false completion; a
persisted running claim remains recoverable only after its lease expires.

### Crash restart behavior

- The supervisor uses bounded exponential restart delay and start-rate limits.
  A crash loop becomes a stopped/failed service requiring operator action.
- Phase 8C records bounded restart count, last failure, exit reason, error, and
  heartbeat metadata but does not automatically restart a process.
- The singleton lock is acquired before the lifecycle metadata transaction.
  Prior-state inspection, pending-stop handling, and `STARTING` publication are
  serialized in that transaction; component and scheduler-internal stop work
  begins only after lifecycle metadata locking is released.
- Scheduler singleton locking prevents two live loops on the same host state
  root. A restarted scheduler records restart recovery and reconciles expired
  leases, failed attempts missing a retry, due schedules, and queued work.
- A claim is not stolen before lease expiry. Expired work becomes a failed
  attempt and, only when policy permits, one traceable child retry after
  backoff.
- Completed jobs and emitted schedule occurrence keys are not recreated.
- Approval requests and decisions remain persisted and fingerprint-bound.
  Recovery calls Approval Runtime; it never repeats a resolved human decision.
- Telegram loads `next_update_id`. The offset advances only after an update and
  its response are handled. A crash after sending but before offset persistence
  can repeat a harmless response, but the deterministic remote command record
  prevents a second approval mutation.
- Webhook `DISPATCH_ATTEMPTED` provenance is recovered against the deterministic
  canonical job. Completed provenance and aliases remain durable tombstones, so
  accepted work is not redispatched after an ordinary restart.
- Notification delivery records suppress delivered or in-flight event resend;
  failed delivery remains bounded to the existing retry count.

The runtime does not guarantee exactly-once provider consumption. If a provider
completed remotely but the host died before evidence persisted, lease recovery
may create a new canonical attempt and consume provider capacity again. Phase 8
must keep externally consequential effects behind their existing idempotency and
approval gates and expose this residual risk operationally.

## Canonical Persistent-State Root

Phase 8B defines one generated-state base root. Host mode requires a dedicated
root outside and non-overlapping with the Git checkout. Filesystem/system
roots, repository ancestors, broad workspaces, and existing directories with
non-canonical contents are rejected before any directory creation or
permission change. `/var/lib/agent-company` is the recommended Linux value:

```text
/var/lib/agent-company/
  jobs/
  executions/
    git/
  approvals/
  schedules/
  scheduler-runtime/
  remote/
    telegram/
  notifications/
  webhooks/
  host/
    processes/
  audit/
  locks/
```

Project repositories and provider credential homes are separate mounts; they
do not live below the state root. Remote/webhook identity configuration and an
optional protected host secret file also remain external to state. Repository,
state, credential, and secret-root relationships are rejected on overlap in
either direction. Phase 8B moves or copies no data.

The canonical root resolves as CLI `--base-root`, then
`AGENT_COMPANY_STATE_ROOT`, then host-config `state_root`, then the repository-
local `runtime/state/` development default. Existing per-component CLI options
remain available; when a canonical base root is configured they must resolve
exactly to the derived component path. Legacy `AGENT_COMPANY_*_STATE_ROOT`
variables are honored only as local-default compatibility fallbacks, so they
cannot split an explicitly configured host root.

| State class | Persistence | Git | Backup |
| --- | --- | --- | --- |
| Jobs, attempts, claims, leases, heartbeat | Must persist | Never commit | Required |
| Execution requests/results and provider artifacts | Must persist for recovery and evidence | Never commit | Required |
| Review and controlled-mutation evidence | Must persist | Never commit | Required |
| Approvals and exact authorization fingerprints | Must persist | Never commit | Required |
| Schedule definitions and occurrence state | Must persist | Never commit | Required |
| Scheduler state, provider counters, and bounded audit | Must persist | Never commit | Required |
| Remote command audit/replay/reconciliation records | Must persist | Never commit | Required |
| Telegram polling offset | Must persist | Never commit | Required |
| Notification delivery and dedupe records | Must persist | Never commit | Required |
| Webhook provenance, aliases, and completed tombstones | Must persist | Never commit | Required |
| Bounded webhook audit history | Must persist while retained | Never commit | Required with the runtime snapshot |
| Host lifecycle state, heartbeats, and bounded crash metadata | Must persist | Never commit | Required |
| Git change sets, diffs, commit/push/PR plans and evidence | Must persist | Never commit | Required |
| Ignored remote/webhook identity configuration | Must persist; sensitive configuration, not secret material | Never commit | Required in encrypted configuration backup |
| Lock files, caches, temporary controlled-write workspaces | May be recreated | Never commit | Exclude |
| Logs beyond canonical audit state | May be recreated under a retention policy | Never commit | Optional |

## Docker Feasibility

`DOCKER_FEASIBILITY: NEEDS_ADAPTATION`

Positive evidence:

- The runtime is Python standard-library code and already has Linux `fcntl`
  branches for local locks.
- Provider and Git subprocesses use fixed argument arrays with `shell=False`.
- State roots and provider executables are configurable enough to support a
  future immutable application image plus external volumes.

Blocking adaptations:

- Codex controlled write is deliberately pinned to
  `windows.sandbox="elevated"`; the adapter and tests require that exact
  Windows-specific command. Linux container controlled write would fail closed
  until a separately reviewed Linux sandbox contract and evidence parser exist.
- The application image would need compatible Python, Git, optional `gh`, Node
  and provider CLIs, plus a verified way to supply provider authentication
  without baking it into an image.
- Canonical project repositories require explicit bind mounts at stable paths.
  Controlled-write staging, path allow-lists, repository roots, Git identity,
  hooks, and credential helpers must be revalidated against container paths.
- Local OS locks and atomic replacement require a suitable local persistent
  volume. Object storage and unverified network filesystems are unsuitable.
- Container restart policy cannot replace runtime lease, approval, or
  provenance recovery. The container must remain single-host and single-worker.
- The current webhook adapter has no production host entrypoint, and the loops
  still need explicit termination-signal tests.

Docker is optional packaging, not a security or authority boundary. Phase 8 may
first run directly on a hardened Linux host; Docker packaging should proceed
only after the same regression, persistence, provider, and recovery behavior is
proved inside the target image.

## VPS Requirements

Requirements precede vendor selection:

- Ubuntu LTS or another supported, patched Linux distribution; x86-64 is the
  conservative target until every provider CLI is verified on another
  architecture.
- Initial sizing: 2 vCPU, 4 GB RAM, and 40 GB SSD is a provisional minimum;
  4 vCPU and 8 GB RAM is the safer starting point for provider CLI execution and
  Git work. Final sizing must use observed workload and repository size.
- A durable local volume for `/var/lib/agent-company`, with free-space alerts
  and tested snapshot/restore. Project checkouts use a distinct explicit path.
- Outbound DNS, NTP, and HTTPS only to required provider, Telegram, package, and
  Git endpoints. No inbound application port for Telegram long polling.
- Git and the exact tested Python runtime. Install `gh` only if pull-request
  capability is enabled. Install each provider CLI and its runtime dependency
  only when that provider is enabled.
- A dedicated non-login service account, restrictive filesystem permissions,
  no password SSH login, no direct root SSH login, key rotation, host firewall,
  security updates, and restricted administrative access.
- Provider and Git credentials scoped to the minimum repositories and actions.
  Git push/PR credentials do not grant merge or deployment authority.
- Enough backup capacity for daily encrypted state snapshots plus a pre-upgrade
  snapshot, stored outside the VPS failure domain.

## Telegram Always-On Operation

Run one supervised `telegram run` long-poll process. Preserve stable numeric
Telegram user IDs, private-chat-only parsing, deny-by-default command
permissions, exact approval/project scopes, replay records, and the persisted
offset. The token stays outside Git and state. Long polling needs outbound HTTPS
only and requires no inbound firewall rule, TLS listener, or Telegram webhook.

The supervisor must not run two pollers against one token/state root. Telegram
outage uses the existing bounded backoff and does not stop the scheduler or
change canonical job state.

## Webhook Public-Exposure Boundary

Phase 8A and the Phase 8 MVP keep the webhook adapter localhost-only and disabled
unless a local consumer requires it. Public exposure is a separate future
authorization and implementation:

```text
Internet
  -> TLS termination
  -> hardened reverse proxy / ingress
  -> request-size, method, path, and rate limits
  -> authenticated webhook endpoint
  -> Agent Company service bound only to localhost
```

That future gate requires a named public hostname, certificate lifecycle,
source and rate policy, proxy-header trust policy, firewall rule, denial-of-
service bounds, logs without secrets, penetration/security review, rollback,
and exact human deployment approval. A reverse proxy must not turn machine
source trust into human approval or expose any other runtime route.

## Deployment And Merge Authority

A future deployment workflow is conceptual only:

```text
immutable deployment plan
  -> independent review
  -> exact human deployment approval
  -> allowlisted deployment action
  -> persisted deployment evidence
  -> explicit rollback when required
```

No current approval action authorizes deployment. Provider execution cannot
invoke the deployment action, edit its approval, or infer authority from a
completed job, commit, push, or pull request.

The boundaries remain separate:

- Pull-request creation is not merge.
- Merge is not deployment.
- Deployment is not provider authority.

Merge remains absent and is not a Phase 8 prerequisite.

## Hermes Evaluation

`HERMES_DECISION: EVALUATE_LATER`

The repository does not identify a Hermes product/version or define a Hermes
contract; it contains only roadmap references and an unused `HERMES_ENDPOINT`
placeholder. The Nous Research Hermes Agent candidate has its own gateway and
cron/scheduled-agent execution model. That could supply generic wake-up and
messaging infrastructure, but it overlaps directly with Agent Company's
scheduler, run loop, provider invocation, state, and Telegram edge.

The existing Scheduler already supplies the Phase 8 requirements that matter:
canonical schedules, single claims, leases, heartbeat, retry/backoff, provider
guards, persisted recovery, approvals, and audit state. Adding a second job
model or orchestration loop would increase duplicate-execution and authority-
confusion risk without a demonstrated gap.

Hermes is not part of the Phase 8 MVP. Re-evaluate only against a pinned version
and a concrete missing host function. Any later adapter must be one-way and
non-authoritative: wake or transport an event into the existing Agent Company
surface, never own jobs, schedules, approvals, provider selection, memory, Git,
merge, or deployment. It must pass duplicate-schedule, restart, secret, and
authority-boundary tests before use.

Primary candidate references reviewed for this limited comparison:

- <https://hermes-agent.nousresearch.com/docs/>
- <https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/cron-internals.md>

## Backup And Recovery

The minimum strategy is a quiesced, encrypted snapshot of the canonical state
root once per day, an additional snapshot before every upgrade or migration,
and retention of at least seven daily and four weekly copies outside the host's
failure domain. Sensitive local identity configuration is backed up separately
with encryption; bot tokens, webhook secrets, provider credentials, and Git
credentials are excluded and restored from their secret authorities.

Use a filesystem or volume snapshot only after stopping ingress and asking the
scheduler to finish its current Worker. If a hot snapshot is unavoidable,
per-file atomicity prevents partial JSON files but does not make all directories
one transaction; recovery must reconcile canonical cross-references.

Provisional objectives are RPO 24 hours for host-loss recovery and RTO 4 hours
after a replacement host and credentials are available. Those objectives do
not mean an old backup may safely resume work immediately. Restore procedure:

1. Build a clean host from a pinned artifact with all processes disabled.
2. Restore the state snapshot and sensitive configuration, then set restrictive
   ownership and permissions.
3. Run offline schema, reference, duplicate-ID, approval, provenance, and
   tombstone validation.
4. Reconcile the snapshot time with Git remotes and other externally visible
   evidence. Missing or uncertain state fails closed.
5. Start in recovery hold: no provider execution, ingress, notification, push,
   PR, or deployment action.
6. Obtain human authorization to resume only after pending approvals, running
   leases, Telegram offset, webhook provenance, and Git evidence are understood.
7. Start scheduler, then Telegram, and observe one complete cycle.

Restoring an older snapshot can roll back dedupe evidence and therefore cannot
promise exactly-once behavior by itself. The recovery hold is the fail-safe.

## Minimum Operational Signals

Phase 8 exposes only the signals needed to operate the host safely:

- process alive/restart state from the supervisor;
- `last_cycle_at` and scheduler status from scheduler state;
- queued/eligible job count from canonical job records;
- pending approval count from canonical approval records;
- last scheduler error from scheduler state;
- provider executable availability from the existing provider status surface,
  clearly distinguished from authentication or service health.

No Control Room, metrics platform, tracing system, log aggregation stack, or
dashboard is introduced. Phase 9 owns broader observability.

## Phase 8 Acceptance Criteria

Implementation is acceptable only when all of the following are evidenced:

- The current full runtime regression and all new Phase 8 tests pass.
- One state root rejects a second scheduler and a second Telegram poller.
- Graceful stop prevents new claims and lets current work finish or leaves a
  recoverable lease without false completion.
- Forced host restart resumes the scheduler without duplicating a canonical job
  or completed schedule occurrence.
- Telegram resumes from the persisted offset; a replay cannot repeat an
  approval decision.
- Pending and resolved approvals remain exact, fingerprint-bound, and persisted.
- Webhook `DISPATCH_ATTEMPTED` recovery and completed provenance/tombstones
  survive restart without redispatching completed work.
- Notification delivery evidence remains restart-deduplicated and cannot alter
  canonical state.
- Secrets are absent from Git, images, job JSON, runtime artifacts, backups,
  and logs; credential-shaped fixture exceptions remain explicit.
- Scheduler provider-run limits remain persisted and effective across restart;
  host-level restart limits prevent a crash loop.
- Provider authentication and real read-only/controlled-write behavior are
  separately smoke-tested on the target platform without treating executable
  presence as success.
- Controlled-write sandbox behavior is proved on the target OS. Linux/Docker
  deployment cannot inherit the Windows-only Codex configuration.
- Commit, push, and PR gates remain distinct; no merge method or authority is
  introduced.
- No deployment action or approval exists implicitly. Any later deployment
  action is exact, reviewed, human-approved, and evidenced.
- The host can be reproduced from pinned configuration without copying secrets
  into the artifact.
- Backup and restore are tested, including recovery hold and preservation of
  approvals, webhook tombstones, remote replay state, and Git evidence.
- Firewall and socket inspection show no unintended public listener. Telegram
  long polling requires no inbound port.
- A final independent Phase 8 architecture and security review passes before
  production use.

## Proposed Phase 8 Implementation Stages

- **Phase 8A - Architecture and threat model:** these design documents, current
  runtime inventory, authority boundaries, feasibility decisions, acceptance
  criteria, and no deployment.
- **Phase 8B - Host configuration and persistence — COMPLETED / CLOSED:**
  canonical base-root contract, strict non-secret configuration,
  exact canonical path resolver, permission model, state detection without migration,
  readiness checks, and backup-exclusion rules. No service installation.
- **Phase 8C - Background process lifecycle — COMPLETED / CLOSED:** the final
  independent re-review passed with no critical, major, or required-fix
  findings. The implementation provides fixed process types, atomic lifecycle
  records, host heartbeats,
  OS-backed scheduler/Telegram/webhook-local singleton locks, tested graceful
  stop and stale-record recovery, serialized startup/stop handling,
  notification-only OS signal callbacks, a fail-closed provider-enable gate,
  and an opt-in loopback webhook entrypoint. No service installation or
  automatic restart daemon.
- **Phase 8D - Docker adaptation and packaging — COMPLETED / CLOSED:** one
  canonical non-root image definition, fixed Compose services, external
  canonical state, runtime-only secrets, and equivalent regression evidence.
  The successful independent review found no critical, major, or required-fix
  findings. No VPS, service/supervisor, public ingress, production provider,
  live Telegram/provider execution, merge, or deployment authority was added.
- **Phase 8E - VPS deployment — BLOCKED / NOT STARTED:** the VPS has not yet
  been created. The vendor-neutral host build and exact reviewed deployment
  plan require separate human deployment approval and the recorded target-host
  runtime validation evidence.
- **Phase 8F - Backup and recovery:** automated encrypted snapshots, retention,
  offline validation, restore rehearsal, and documented RPO/RTO evidence.
- **Phase 8G - Deployment smoke test:** restart, lease, Telegram offset, webhook
  provenance, notification dedupe, provider, firewall, and rollback tests on the
  approved target without merge authority.
- **Phase 8H - Final security review:** independent review of the actual host,
  secrets, firewall, process definitions, artifacts, recovery evidence, and all
  authority boundaries before production acceptance.

Non-blocking Phase 8C future hardening is a different-provider full-repository
audit, real subprocess singleton-race validation, native Windows signal/ACL
validation, and more race-resistant status-lock probing.

## Remaining Phase 8 Implementation Blockers

- No operating-system supervisor definition or forced-stop deadline has been
  installed or target-host tested.
- Codex controlled-write configuration is Windows-specific and cannot be
  claimed to work in Linux Docker.
- Provider authentication has not been verified on a target host; `gh` and
  Claude are absent in the inspected environment.
- Backup/restore automation and a recovery-hold mode do not exist.
- No target host, pinned build artifact, service definition, Docker image, VPS,
  or exact deployment approval exists.
