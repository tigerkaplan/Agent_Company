# Agent Company Project State

## Current Checkpoint

- Current Git HEAD is `bac9a4f`, the committed Phase 5 business agents and connectors checkpoint.
- Phase 6 runtime implementation exists in the working tree and is pending a checkpoint commit.
- Phase 6M, the Scheduler / Autonomous Run Loop, is the highest explicitly represented Phase 6 capability.
- No canonical Phase 6N or later numeric phase is defined.
- The runtime remains local-first, file-backed, and deliberately limited to one concurrent Worker.

## Committed

- Provider-neutral governance, canonical agents and skills, project onboarding, knowledge structure, hybrid provider routing configuration, and Phase 5 business agents, skills, workflows, and connector contracts.
- The committed repository does not contain the Phase 6 runtime or schemas.

## Implemented But Uncommitted

- Canonical jobs, lifecycle, queue, attempts, retries, Worker, and Executor contracts.
- Phase 6B queue semantics and Phase 6D deterministic schedules.
- Phase 6E provider execution and Phase 6F independent review.
- Phase 6G persisted human approvals and Phase 6H controlled-write execution.
- Phase 6I controlled Git change sets and commits.
- Phase 6J separately approved push and pull-request creation.
- Phase 6M autonomous scheduling, claims, leases, heartbeat, retry backoff, restart recovery, audit state, and provider usage guards.
- Runtime schemas, provider runtime configuration, and supporting governance/documentation changes.

## Deferred

- Merge and deployment are not implemented and grant no runtime authority.
- Service installation, distributed execution, parallel provider execution, and broader connector execution remain outside the current local runtime.

## Not Started

- Telegram or other remote-command runtime.
- Agent Company infrastructure implementation; `infrastructure/` is absent.
- Dedicated observability, metrics, or tracing implementation; `observability/` is absent.

## Runtime Limitations

- State is stored in local JSON files rather than a database or distributed queue.
- Scheduler execution is sequential with `max_concurrent_jobs = 1`.
- Provider execution uses explicitly selected local CLI adapters; executable detection does not prove authentication or service availability.
- Scheduler audit records and runtime artifacts provide local visibility, not a full observability platform.
- No merge, release, deployment, Telegram command, or general connector runtime exists.

## Verification

Verified on 2026-09-23:

- Runtime tests: 282 passed, 0 failed, and 0 skipped.
- Python compilation: PASS for 71 files.
- Schemas: PASS for 13 JSON schemas parsed and structurally checked; existing runtime schema and model tests also passed. The optional `jsonschema` package was not installed.
- Git diff check: PASS.
- Secret and credential scan: PASS. One deliberate credential-shaped rejection fixture in `runtime/tests/test_remote_git.py` is not a real credential.
- Provider runtime configuration: PASS for the Claude and Codex configurations.
- Generated-state ignore rules and temporary-artifact checks: PASS.
- Architecture and security checks: PASS, including no `shell=True`, no project-specific business logic in runtime source, and no unexpected dirty paths.

This verifies the current working-tree checkpoint; it does not make the uncommitted Phase 6 files part of Git history.
