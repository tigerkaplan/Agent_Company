# Agent Company Project State

## Current Checkpoint

- Current Git HEAD is `794cb53`, containing the committed Phase 7 remote core,
  Telegram transport and notifications, localhost webhook ingress, and Phase 7
  security remediation.
- The working tree contains an uncommitted provider-neutral Social Media
  capability checkpoint. It adds a canonical agent, nine skills, task routing,
  workflow, provider capability configuration, schema support, and deterministic
  routing tests without adding a social-platform connector or publishing authority.
- Phase 6M, the Scheduler / Autonomous Run Loop, is the highest explicitly represented Phase 6 capability.
- No canonical Phase 6N subphase is defined.
- The runtime remains local-first, file-backed, and deliberately limited to one concurrent Worker.
- Phase 7 implementation is present; Phase 7 is not declared closed until the
  final architecture and security re-review passes.

## Uncommitted Capability Checkpoint

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
  persisted replay protection, and explicit command dispatch.
- Telegram private-chat long polling and bounded proactive notification
  delivery.

## Deferred

- Merge and deployment are not implemented and grant no runtime authority.
- Service installation, distributed execution, parallel provider execution, and broader connector execution remain outside the current local runtime.

## Not Implemented

- Agent Company infrastructure implementation; `infrastructure/` is absent.
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

- Runtime tests: 430 passed, 0 failed, and 0 skipped.
- Python compilation: PASS for 100 files.
- Schemas: PASS for 15 JSON schemas parsed; runtime schema/model tests also passed.
- Git diff check: PASS.
- Secret and credential scan: PASS. One deliberate credential-shaped rejection fixture in `runtime/tests/test_remote_git.py` is not a real credential.
- Provider runtime configuration: PASS for the Claude and Codex configurations.
- Generated-state ignore rules and temporary-artifact checks: PASS.
- Architecture and security checks: PASS, including no `shell=True`, no project-specific business logic in runtime source, and no unexpected dirty paths.

This verifies the Phase 6/7 runtime and the uncommitted Social Media capability
checkpoint without declaring Phase 7 closed. A fresh independent final Phase 7
review remains required.
