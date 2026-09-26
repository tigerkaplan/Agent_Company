# Infrastructure

This directory contains the canonical Phase 8 hosting and deployment design
plus the Phase 8D Docker adaptation. It does not contain a deployment,
operating-system service, built image, public endpoint, credential, or
infrastructure automation.

## Status

- Phase 8A: COMPLETED / CLOSED on 2026-09-24; design and discovery only.
- Phase 8B: COMPLETED / CLOSED; no deployment.
- Phase 8C: COMPLETED / CLOSED after final independent re-review; no deployment.
- Phase 8D: COMPLETED / CLOSED after successful independent review; no
  deployment.
- Phase 8E: BLOCKED / PAUSED; deployment not started because the VPS has not
  yet been created.
- Phase 8F: NOT STARTED.
- Current runtime: local-first, file-backed, and single-worker.
- Deployment: not performed.
- Docker image definition and Compose packaging: implemented but not built or
  deployed; the local Docker daemon was unavailable for live validation.
- VPS, operating-system service, Hermes, and public webhook exposure: not
  installed or enabled.
- Merge and deployment authority: absent.

Phase 8C adds a supervisor-neutral lifecycle wrapper but does not install a
systemd unit, Windows Service, Task Scheduler job, automatic restart supervisor
daemon, VPS, Hermes, public webhook hosting, or TLS termination, and it
adds no merge or deployment authority. Non-blocking Phase 8C future hardening
is a different-provider full-repository audit, real subprocess singleton-race
validation, native Windows signal/ACL validation, and more race-resistant
status-lock probing. Race-resistant directory-handle containment remains a
separate non-blocking Phase 8B item.

## Documents

- `HOST_ARCHITECTURE.md` defines the host boundary, process and persistence
  models, startup and recovery behavior, Docker and VPS assessments, acceptance
  criteria, and proposed implementation stages.
- `SECURITY_MODEL.md` defines production secret handling, ingress and authority
  boundaries, backup safety, and the Phase 8 threat model.
- `docker/README.md` defines the Phase 8D single-image Compose model, provider
  prerequisite, persistent-state handling, healthchecks, and explicit
  exclusions.

## Phase 8B Host Foundation

`config/host.example.json` is the tracked, non-secret contract. Copy it to the
Git-ignored `config/host.local.json` only when a local override is needed. The
canonical base root resolves in this order: CLI `--base-root`,
`AGENT_COMPANY_STATE_ROOT`, host-config `state_root`, then the safe local
default `runtime/state/`. Existing component-specific root variables remain
compatibility fallbacks only when no canonical base root is configured. With a
configured base, every component path must equal its fixed derived path.

From the repository root:

```text
python -m runtime.cli host init [--config <path>] [--base-root <absolute-path>]
python -m runtime.cli host check [--config <path>] [--base-root <absolute-path>]
```

`host init` creates only the fixed canonical directory layout and is
idempotent; it never migrates or deletes state and makes no network/provider
calls. `host check` is read-only and reports deterministic PASS/WARN/FAIL
checks without printing secret values or raising on malformed dependent
configuration. Host mode requires an explicit dedicated state root outside and
non-overlapping with the repository. Broad directories and repository
ancestors are rejected before creation or permission changes.
`/var/lib/agent-company` remains the recommended Linux production value.

Provider subprocesses use a default-deny environment allowlist. They retain
only required system/locale variables plus variables explicitly approved for
that provider; a configured credential root maps to a separate provider home.
Telegram, webhook, arbitrary connector, and other-provider secrets are not
propagated. State, repository, provider credential, and secret locations are
checked for overlap in both directions. POSIX permission checks remain
enforced; Windows ACL status is WARN and requires operator validation.

State needed for recovery or authority evidence is backup-required: jobs,
executions, approvals, schedules/scheduler state, remote and Telegram replay
state, notifications, webhook provenance/audit, and Git action evidence.
Transient locks and caches are excluded; expendable retained logs are optional.
Secrets and provider credential homes are separate and excluded from ordinary
state backups. Phase 8F, not Phase 8B, owns backup automation.

## Phase 8C Process Lifecycle

The fixed process set is `scheduler`, `telegram`, and opt-in
`webhook-local`. Lifecycle metadata is written atomically below
`host/processes/`; OS-backed singleton locks remain below `locks/`. The wrapper
records `STARTING`, `RUNNING`, `STOPPING`, `STOPPED`, or `FAILED`, a bounded
heartbeat, restart/failure metadata, PID plus a per-run owner token and start
time, and never kills a PID. A released kernel lock makes a stale active record
recoverable after a crash.

```text
python -m runtime.cli host processes
python -m runtime.cli host status
python -m runtime.cli host run scheduler
python -m runtime.cli host run telegram
python -m runtime.cli host run webhook-local
python -m runtime.cli host request-stop <scheduler|telegram|webhook-local>
```

Every run performs Phase 8B readiness checks and fails closed when the
component is disabled or required configuration/secrets are absent. Scheduler
execution reuses `SchedulerLoop`; Telegram reuses `TelegramTransport`; the
optional webhook process reuses the existing server factory and binds
`127.0.0.1` only. Non-dry host scheduler runs require provider execution;
local executors remain test-only. SIGTERM/SIGINT and `KeyboardInterrupt`
request graceful stop.
Windows console delivery remains dependent on the launching terminal or future
supervisor; no forced termination is implemented.

The CLI performs no automatic restart. A future supervisor should use bounded
exponential delay, a burst cap, and an operator-required failed state after a
crash loop. Phase 8C metadata supports that policy without installing it.

## Phase 8D Docker Adaptation

The root `Dockerfile`, `.dockerignore`, and `compose.yaml` package the existing
runtime without creating a second source of truth. Scheduler, Telegram, and the
opt-in webhook-local process use fixed canonical commands, a single named state
volume, non-root execution, a read-only root filesystem, dropped capabilities,
and service-local read-only healthchecks. No port is published and no provider
CLI, credential, or secret is built into the image.

Provider-backed scheduling intentionally fails closed in the tracked config
until a separately reviewed derived image and credential mount exist. Telegram
requires its token at runtime. Webhook-local remains bound to `127.0.0.1` in
its container namespace. See `docker/README.md` for validation and operating
details. Phase 8D is COMPLETED / CLOSED after successful independent review;
Phase 8E deployment is blocked because the VPS has not yet been created.
Docker-daemon-dependent validation remains an explicit Phase 8E prerequisite.

## Authority Boundary

The host is an availability mechanism only. It may keep the existing runtime
processes alive and provide durable local storage. It must not classify work,
select business routing or providers, decide approvals or reviews, grant Git,
merge, release, or deployment authority, or reinterpret canonical runtime
state.

Any future implementation remains subordinate to `../CONSTITUTION.md`,
`../AGENTS.md`, the existing runtime authority surfaces, and exact human
approval for production deployment.
