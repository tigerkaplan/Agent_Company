# Agent Company Project State

## Current Checkpoint

- Current Git HEAD is `03a3a2e`, containing the committed Phase 7 remote core,
  Telegram transport and notifications, localhost webhook ingress, Phase 7
  security remediation, and the provider-neutral Social Media capability
  checkpoint.
- Phase 8A began from a clean working tree and is now PASS / COMPLETED. Its
  documentation changes are intentionally uncommitted; the working tree also
  contains the Phase 7 closure reconciliation. These changes add no runtime or
  deployment capability.
- Phase 6M, the Scheduler / Autonomous Run Loop, is the highest explicitly represented Phase 6 capability.
- No canonical Phase 6N subphase is defined.
- The runtime remains local-first, file-backed, and deliberately limited to one concurrent Worker.
- Phase 7 is completed and closed. The final repository-backed architecture and
  security review passed on 2026-09-24.
- Phase 8A architecture and threat-model design is completed under
  `infrastructure/`. The current baseline remains local; no deployment, service,
  Docker image, VPS, Hermes integration, or public webhook exposure exists.
- Phase 8B is NEXT and has not started. No technical blocker prevents Phase 8B
  after this documentation checkpoint is committed.

## Phase 8A Architecture Design Checkpoint

Phase 8A produced the infrastructure architecture, host/process model,
persistent-state model, secrets model, Docker feasibility assessment, VPS
requirements, Telegram always-on design, webhook public-exposure boundary,
deployment and merge authority boundaries, Hermes evaluation, backup/recovery
design, threat model, acceptance criteria, and staged Phase 8 implementation
plan. Phase 8A performed no deployment and implemented none of those stages.

## Social Media Capability Checkpoint

- Social Media owns channel-level content planning, individual content drafts,
  hooks, captions, calendars, repurposing, community signals, channel
  performance, social competitor monitoring, and weekly social reporting.
- Marketing retains strategy, positioning, campaigns, audience or customer
  analysis, market-level competitor analysis, and broader marketing priorities.
- `social_media` routes to the Social Media Agent through the `social-media`
  workflow and the provider-neutral `social_media_content` capability.
- Claude and Codex are configured as equally eligible at neutral weight. This is
  routing configuration, not an availability or quality claim.
- No real social API, connector, credential, scheduling, or publication action
  is implemented. Consequential external actions remain approval-gated.

## Committed

- Provider-neutral governance, canonical agents and skills, project onboarding, knowledge structure, hybrid provider routing configuration, and Phase 5 business agents, skills, workflows, and connector contracts.
- Canonical jobs, lifecycle, queue, attempts, retries, Worker, and Executor contracts.
- Phase 6B queue semantics and Phase 6D deterministic schedules.
- Phase 6E provider execution and Phase 6F independent review.
- Phase 6G persisted human approvals and Phase 6H controlled-write execution.
- Phase 6I controlled Git change sets and commits.
- Phase 6J separately approved push and pull-request creation.
- Phase 6M autonomous scheduling, claims, leases, heartbeat, retry backoff, restart recovery, audit state, and provider usage guards.
- Runtime schemas, provider runtime configuration, and supporting governance/documentation changes.
- Transport-independent remote commands with stable identity mapping,
  deny-by-default permissions, action/project-scoped authorization, persisted
  replay protection, durable mutation/reconciliation audit, and explicit
  command dispatch through canonical runtime surfaces.
- Telegram private-chat long polling and bounded proactive notification
  delivery for approval requested/resolved, job completion/failure, and
  runtime errors.
- Localhost-only authenticated webhook ingress with HMAC/timestamp/replay
  protection, canonical dispatch, durable provenance tombstones, and separate
  bounded audit records.
- Provider-neutral Social Media agent, skills, workflow, routing, provider
  capability configuration, schema support, and deterministic routing tests.

## Deferred

- Merge and deployment are not implemented and grant no runtime authority.
- Service installation, distributed execution, parallel provider execution, and broader connector execution remain outside the current local runtime.

## Not Implemented

- Agent Company infrastructure implementation; `infrastructure/` contains
  design documents only.
- Dedicated observability, metrics, or tracing implementation; `observability/` is absent.
- Phase 8 always-on hosting, TLS termination, public webhook exposure,
  Docker, VPS, Hermes, and operating-system service installation.

## Runtime Limitations

- State is stored in local JSON files rather than a database or distributed queue.
- Scheduler execution is sequential with `max_concurrent_jobs = 1`.
- Provider execution uses explicitly selected local CLI adapters; executable detection does not prove authentication or service availability.
- Scheduler audit records and runtime artifacts provide local visibility, not a full observability platform.
- Telegram exposes only six permission-scoped commands in authenticated
  private chats. It has no task-submission, scheduler-mutation, filesystem,
  shell, Git, merge, release, or deployment command.
- Webhook ingress is authenticated machine input on loopback only. It creates
  approval-required jobs through canonical routing and cannot approve, queue,
  execute, write, select providers, or invoke Git.

## Verification

Verified on 2026-09-24 for the current working tree:

- Targeted Phase 7 tests: 142 passed, 0 failed, and 0 skipped.
- Runtime tests: 430 passed, 0 failed, and 0 skipped.
- Python compilation: PASS for 100 files.
- Schemas: PASS for 15 JSON schemas parsed; runtime schema/model tests also passed.
- Git diff check: PASS.
- Secret and credential scan: PASS. One deliberate Telegram-token-shaped
  redaction fixture in `runtime/tests/test_notifications.py` is not a real
  credential; no production high-confidence secret hit was found.
- Provider runtime configuration: PASS for the Claude and Codex configurations.
- Generated-state ignore rules and temporary-artifact checks: PASS, including
  all 16 actual-path ignore probes.
- Architecture and security checks: PASS, including zero AST-detected
  `shell=True` calls, no project-specific business logic in runtime source, and
  no unexpected generated dirty paths.

This is the recorded final Phase 7 closure evidence. Phase 6 authority
boundaries remain green, and Phase 7 is COMPLETED / CLOSED. The Social Media
capability checkpoint is COMPLETED / COMMITTED. Phase 8A is PASS / COMPLETED
and documentation-only. Phase 8B is NEXT, has not started, and has no technical
blocker after checkpoint reconciliation. A different-provider full-repository
audit is recommended future validation, not a mandatory Phase 8 implementation
gate.
