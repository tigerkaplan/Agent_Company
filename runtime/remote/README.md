# Remote Runtime Interface

Phase 7A defines how remote control may enter the local Agent Company runtime
without weakening the Phase 6 approval, review, controlled-write, Git, and
scheduler boundaries.

This directory contains the design plus the transport-independent remote
runtime core. The first Telegram long-poll adapter and proactive bounded
notification transport are implemented under `../../integrations/telegram/`.
The runtime still does not implement a webhook listener, HTTP server,
credential store, daemon, deployment target, or provider integration.

## Status

- Phase: 7 Telegram command-response and proactive notification transport.
- Runtime implementation: first transport-independent core implemented.
- Transport implementation: local Telegram Bot API long polling implemented.
- Notification implementation: bounded approval, terminal-job, and runtime
  error events implemented through `../notifications/`.
- Canonical command contract: `COMMAND_CONTRACT.md`.
- Authority and threat model: `AUTHORITY_MODEL.md`.

## Implemented Core

The executable Phase 7 remote core is transport-independent. It includes:

- `RemoteCommandService` with explicit enum dispatch only.
- Canonical `RemoteIdentity`, `RemoteCommand`, and `RemoteCommandResult`
  models.
- Local trusted identity mapping through injected config or ignored local config.
- A canonical 10 minute default approval interaction TTL, configurable through
  remote runtime configuration.
- Read-only runtime commands: `STATUS`, `JOBS_LIST`, `JOB_SHOW`, and
  `APPROVALS_LIST`.
- Human authorization commands: `APPROVE` and `REJECT`.
- Approval integration through `ApprovalRuntime`; remote code does not edit
  approval JSON directly.
- Persistent replay and audit records under ignored `runtime/state/remote/`.
- A development CLI harness under `python -m runtime.cli remote ...` that still
  authenticates through remote configuration and passes through
  `RemoteCommandService`.

Local identity mapping should use ignored `config/remote.local.json`. A safe
tracked placeholder lives at `../../config/remote.example.json`.

Remote audit state is compact and bounded by `max_audit_records`, defaulting to
1000 records. The oldest records are pruned after the configured limit.

The Telegram adapter exposes only the existing core operations. It uses numeric
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

- No Telegram webhook endpoint or generic webhook ingress.
- No bot token, signing secret, or tracked allow-list secret.
- No web server, Docker, VPS, Hermes, daemon, or deployment.
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

The command-response and proactive notification transports satisfy these
criteria through deterministic fake-transport tests and the existing remote
runtime boundary. Webhook operation remains future Phase 7 work.
