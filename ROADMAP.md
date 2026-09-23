# Agent Company Roadmap

`PROJECT_STATE.md` is the canonical current-status record. This roadmap is the canonical forward capability roadmap after the verified Phase 6 checkpoint. Candidate capabilities below are planning scope unless explicitly marked as completed.

## Status Summary

- Phase 1-6: COMPLETED / COMMITTED.
- Phase 7: PLANNED / NEXT.
- Phase 8: PLANNED.
- Phase 9: PLANNED.
- Phase 10: PLANNED.

## Completed / Committed

### Phase 1-5: Core Architecture

- CORE: provider-neutral governance, canonical agents, skills, routing, project onboarding, and knowledge structure.
- CORE: Claude and Codex hybrid routing configuration.
- CORE: business agents, skills, workflows, and connector contracts.

### Phase 6: Verified Local Runtime

Phase 6 is completed and committed at `81aa9b3`. Verification evidence recorded in `PROJECT_STATE.md` includes 282/282 runtime tests passing, 71 Python files compiled, and 13 schemas checked. Phase 6M remains the highest explicit Phase 6 marker, and no Phase 6N is defined.

- RUNTIME: canonical job model and lifecycle engine.
- RUNTIME: Phase 6B local queue and traceable retries.
- RUNTIME: Worker and provider-neutral Executor contract.
- RUNTIME: Phase 6D deterministic one-time and recurring schedules.
- RUNTIME: Phase 6E opt-in local provider execution.
- RUNTIME: Phase 6F deterministic verification and Reviewer Runtime.
- RUNTIME: Phase 6G persisted scoped human approvals.
- RUNTIME: Phase 6H staged controlled write and dry-run enforcement.
- RUNTIME: Phase 6I controlled Git change set, approval, exact staging, and commit evidence.
- RUNTIME: Phase 6J remote validation, separately approved push, and separately approved pull-request creation.
- RUNTIME: Phase 6M bounded autonomous scheduler loop, claims, leases, heartbeat, retry backoff, restart recovery, audit status, and provider usage guards.

## Planned / Next

### Phase 7: Remote Control And Runtime Integrations

Goal: allow Agent Company to receive and expose runtime operations through safe remote interfaces while preserving existing approval and authority boundaries.

- REMOTE INTERFACE: define the threat and authority model for remote commands.
- REMOTE INTERFACE: define a remote-command contract for job/status inspection and bounded runtime operations.
- REMOTE INTERFACE: evaluate Telegram inbound commands, Telegram notifications, and approval/reject interaction as connector-backed interfaces.
- REMOTE INTERFACE: define webhook runtime ingestion and source-validation boundaries.
- RUNTIME: define the connector execution boundary without turning connectors into agents or orchestrators.
- CORE: ensure remote input never itself implies approval.
- CORE: define authentication and authorization expectations for remote commands.

Telegram is a candidate interface/connector for Phase 7, not an agent, orchestrator, or implemented runtime. Gmail, Drive, and Calendar write implementations are not automatically in Phase 7; they require explicit later design if included.

## Planned

### Phase 8: Always-On Runtime And Deployment

Goal: move the verified local runtime into an optional always-on execution environment.

- RUNTIME: plan background runtime hosting, process lifecycle, startup/restart behavior, and recovery.
- DEPLOYMENT: define environment and secrets management for optional hosted operation.
- DEPLOYMENT: evaluate Docker and VPS deployment options.
- DEPLOYMENT: evaluate Hermes only if it provides concrete value as a runtime or host integration.
- DEPLOYMENT: design backup/recovery for operational runtime state.
- CORE: define deployment authority before any deployment implementation exists.

Hermes is optional and must not be treated as the Agent Company core. Merge and deployment authority remain absent until deliberately implemented and approved.

### Phase 9: Observability, Control Room, And Hardening

Goal: make the system operationally understandable and production-ready.

- OBSERVABILITY: plan structured logs, metrics, runtime health, provider usage, and cost/token accounting where available.
- OBSERVABILITY: expose job, queue, scheduler, approval, reviewer, failure, retry, and recovery visibility.
- OBSERVABILITY: define audit trails and recovery tooling.
- CORE: plan security hardening for the runtime and remote interfaces.
- REMOTE INTERFACE: evaluate a Control Room as an operations and visualization layer over canonical Agent Company state.

The repository does not currently contain `apps/control-room`. A future Control Room must not become a second source of truth.

### Phase 10: Project / Capability Packs

Goal: use the stable Agent Company core for real projects and domain-specific capabilities.

- PROJECT PACKS: express project-specific functionality through project state, skills, workflows, connector configuration, and domain-specific capability packs.
- PROJECT PACKS: keep Brightshore Cleaning, YouTube, Instagram, Etsy digital products, and product research/shopping as example pack candidates rather than committed implementation scope.
- RUNTIME: use the same shared Agent Company runtime for project packs.
- CORE: require user approval before consequential purchase, publication, account, financial, production, or external communication actions.

Project packs must not create separate Agent Company runtimes per project unless a later approved architecture explicitly changes that rule.

## Deferred Or Not Implemented

- Merge: deferred and not implemented.
- Deployment: deferred and not implemented.
- Telegram or remote-command runtime: not started.
- Broader Gmail, Drive, Calendar, webhook, and Telegram integrations: contract-only.
- Infrastructure implementation: not started.
- Dedicated observability implementation: not started.
