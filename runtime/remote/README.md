# Remote Runtime Interface

Phase 7A defines how remote control may enter the local Agent Company runtime
without weakening the Phase 6 approval, review, controlled-write, Git, and
scheduler boundaries.

This directory contains the design plus the transport-independent remote
runtime core. The first Telegram long-poll adapter and proactive bounded
notification transport are implemented under `../../integrations/telegram/`.
Authenticated machine ingress is implemented under `../webhooks/` with an
optional loopback-only HTTP adapter. The runtime does not implement a public
listener, TLS termination, credential store, daemon, deployment target, or
provider integration.

## Status

- Phase: 7 Telegram command-response and proactive notification transport.
- Runtime implementation: first transport-independent core implemented.
- Transport implementation: local Telegram Bot API long polling implemented.
- Notification implementation: bounded approval, terminal-job, and runtime
  error events implemented through `../notifications/`.
- Webhook implementation: signed `TASK_SIGNAL` machine ingress and optional
  localhost-only HTTP adapter implemented through `../webhooks/`.
- Canonical command contract: `COMMAND_CONTRACT.md`.
- Authority and threat model: `AUTHORITY_MODEL.md`.

## Implemented Core

The executable Phase 7 remote core is transport-independent. It includes:

- `RemoteCommandService` with explicit enum dispatch only.
- Canonical `RemoteIdentity`, `RemoteCommand`, and `RemoteCommandResult`
  models.
- Local trusted identity mapping through injected config or ignored local config.
- Deny-by-default permissions: `READ_STATUS`, `READ_JOBS`, `READ_JOB`,
  `READ_APPROVALS`, `APPROVE`, and `REJECT`. There is no wildcard.
- Approval/rejection scope constrained by exact canonical approval action and
  project binding, including explicit opt-in for jobs without a project ID.
- A canonical 10 minute default approval interaction TTL, configurable through
  remote runtime configuration, plus a default 30 second permitted clock skew.
- Read-only runtime commands: `STATUS`, `JOBS_LIST`, `JOB_SHOW`, and
  `APPROVALS_LIST`.
- Human authorization commands: `APPROVE` and `REJECT`.
- Approval integration through `ApprovalRuntime`; remote code does not edit
  approval JSON directly.
- Persistent replay and audit records under ignored `runtime/state/remote/`.
- Every replay is re-authenticated against the current enabled identity,
  command permission, and applicable approval/resource scope before cached data
  can be returned. Revocation therefore takes effect for retained results.
- Durable approval audit stages `AUTHORIZED`, `MUTATION_ATTEMPTED`, and
  `COMPLETED`/`FAILED`, plus `RECONCILIATION_REQUIRED` when canonical approval
  state changed but its job transition did not complete. Audit preparation
  failure prevents mutation; retry of an attempted/partial transition reloads
  `ApprovalRuntime` truth and reconciles without resolving the approval twice.
  If canonical approval is still `PENDING`, recovery must still pass the
  original issued-at, current received-at, clock-skew, and TTL checks. An
  already persisted `APPROVED` or `REJECTED` decision may finish downstream
  reconciliation after that interaction window without re-deciding it.
- A development CLI harness under `python -m runtime.cli remote ...` that still
  authenticates through remote configuration and passes through
  `RemoteCommandService`.

Local identity mapping should use ignored `config/remote.local.json`. A safe
tracked placeholder lives at `../../config/remote.example.json`. Loading accepts
ordinary UTF-8 and UTF-8 with a BOM, but rejects duplicate JSON keys at every
object nesting level before any identity or permission is constructed.

Remote audit state is compact and bounded by `max_audit_records`, defaulting to
1000 records. Only terminal records are retention candidates. `AUTHORIZED`,
`MUTATION_ATTEMPTED`, and `RECONCILIATION_REQUIRED` evidence is never pruned;
if incomplete records occupy capacity, a new command fails closed until an
operator retries or reconciles the protected work.

The Telegram adapter exposes only the existing core operations in private
chats. It uses numeric
Telegram user IDs from ignored remote config, reads the bot token only from
`AGENT_COMPANY_TELEGRAM_BOT_TOKEN`, and persists only its polling offset under
ignored `runtime/state/remote/telegram/`. See
`../../integrations/telegram/README.md` for manual setup.

Proactive delivery is provider-neutral before it reaches Telegram:

```text
persisted runtime transition
  -> NotificationEvent
  -> NotificationService
  -> configured transport adapter
  -> existing Telegram Bot API client
```

Automatic delivery is opt-in per process with `--enable-notifications` and
targets only identities listed in local `notification_targets`. Notification
state is stored separately under ignored `runtime/state/notifications/`.
Delivery never approves a request or changes canonical runtime state.

## Boundary

Remote interfaces are input and control channels. They are not agents,
providers, reviewers, approvers, schedulers, connectors with runtime authority,
or independent sources of policy.

The only valid path is:

```text
remote transport adapter
  -> authenticate platform event
  -> map to trusted human or machine identity
  -> authorize command class and target resource
  -> parse canonical RemoteCommand
  -> RemoteCommandService
  -> existing runtime/orchestrator authority surface
  -> existing approval/lifecycle/audit system
```

Remote adapters must not directly execute provider commands, mutate files,
stage files, commit, push, create pull requests, alter approval records, bypass
routing, or modify scheduler state outside an approved runtime operation.

## Component Split

- Transport adapter: Telegram, webhook, or a future channel-specific adapter.
  It validates channel delivery details and produces a normalized inbound event.
- Remote command parser: converts trusted event content into one canonical
  command shape or rejects it.
- Identity/authentication: maps platform-specific identity to an explicit
  trusted human identity or machine source.
- Remote command service: authorizes and calls existing runtime/orchestrator
  operations.
- Notification formatter: renders informational messages and secure approval
  prompts without owning business logic.

Transport-specific code must stay thin. Business command decisions belong in
the remote command service and canonical runtime operations.

## Non-Goals

- No Telegram webhook endpoint, public webhook exposure, or TLS termination.
- No bot token, signing secret, or tracked allow-list secret.
- No public web server, Docker, VPS, Hermes, daemon, or deployment. The optional
  webhook HTTP adapter is loopback-only and manually started.
- No arbitrary shell or filesystem command bridge.
- No merge, force-push, release, deployment, or broad connector write authority.
- No approval based on message text alone.
- No task submission, schedule creation, scheduler mutation, job cancellation,
  controlled write, commit, push, pull request creation, merge, or deployment
  command in the first executable core.

## Phase 7 Acceptance Criteria

Before implementation can be accepted, the design requires tests and review
showing that:

- unauthorized identity cannot inspect sensitive runtime state;
- unauthorized identity cannot create jobs;
- unauthorized identity cannot approve or reject;
- authenticated commands map to canonical runtime operations;
- remote approval remains exact, current, and stale-safe;
- duplicate command delivery is idempotent;
- remote channels cannot invoke arbitrary shell or filesystem actions;
- Telegram or webhook outage cannot corrupt runtime state;
- no token or secret enters Git, runtime job artifacts, or audit payloads;
- the full Phase 6 regression suite remains green.

The command-response, proactive notification, and localhost webhook paths have
deterministic no-network coverage. The final repository-backed architecture and
security review passed on 2026-09-24 with 142/142 targeted Phase 7 tests and
430/430 full runtime tests. Phase 7 is completed and closed.
