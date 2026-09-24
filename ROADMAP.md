# Agent Company Roadmap

`PROJECT_STATE.md` is the canonical current-status record. This roadmap is the canonical forward capability roadmap after the verified Phase 6 checkpoint. Candidate capabilities below are planning scope unless explicitly marked as completed.

## Status Summary

- Phase 1-6: COMPLETED / COMMITTED.
- Phase 7: IMPLEMENTED / PENDING FINAL RE-REVIEW.
- Social Media capability checkpoint: IMPLEMENTED / VERIFIED / PENDING COMMIT.
- Phase 8: PLANNED.
- Phase 9: PLANNED.
- Phase 10: PLANNED.

## Completed / Committed

### Phase 1-5: Core Architecture

- CORE: provider-neutral governance, canonical agents, skills, routing, project onboarding, and knowledge structure.
- CORE: Claude and Codex hybrid routing configuration.
- CORE: business agents, skills, workflows, and connector contracts.

### Phase 6: Verified Local Runtime

Phase 6 is completed and committed at `81aa9b3`. Phase 6M remains the highest
explicit Phase 6 marker, and no Phase 6N is defined. Current combined Phase 6/7
working-tree verification is recorded in `PROJECT_STATE.md`.

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

## Implemented / Pending Final Re-Review

### Phase 7: Remote Control And Runtime Integrations

Goal: allow Agent Company to receive and expose runtime operations through safe remote interfaces while preserving existing approval and authority boundaries.

- REMOTE INTERFACE: transport-independent `RemoteCommandService` with six
  explicit commands and deny-by-default per-user permissions.
- REMOTE INTERFACE: action and project-scoped remote approval/rejection through
  the existing Approval Runtime, with durable pre-mutation audit evidence.
- REMOTE INTERFACE: authenticated Telegram commands restricted to private chats.
- REMOTE INTERFACE: bounded proactive Telegram notifications for approval
  requested/resolved, job completion/failure, and runtime errors.
- REMOTE INTERFACE: authenticated localhost `TASK_SIGNAL` webhook ingress with
  HMAC verification, replay protection, and canonical task dispatch.
- CORE: Telegram humans and webhook machine sources remain separate identity
  and authority classes; neither inbound channel implies approval.

Telegram is an implemented interface/connector, not an agent or orchestrator.
The webhook adapter is loopback-only machine ingress, not public deployment.
Gmail, Drive, Calendar, remote task submission, scheduler mutation, remote
filesystem/Git commands, merge, and deployment are not Phase 7 capabilities.
Phase 7 remains open until a final independent re-review passes.

## Added Capability Checkpoint / Pending Commit

### Social Media Capability

This provider-neutral checkpoint sits between Phase 7 and Phase 8. It does not
redefine or begin Phase 8.

- CORE: dedicated Social Media Agent with an explicit boundary from Marketing.
- SKILLS: content calendar, post planning, caption writing, hook generation,
  content repurposing, social competitor monitoring, performance review,
  comment analysis, and weekly social reporting.
- ROUTING: canonical `social_media` task class, `social-media` workflow, and
  `social_media_content` provider capability.
- PROVIDERS: Claude and Codex are equally eligible at neutral configured weight;
  eligibility and weights do not claim runtime availability or quality.
- APPROVALS: planning, drafts, and analysis may remain internal; publication,
  live edits or deletion, public replies, paid campaign changes, budget spend,
  and account changes remain approval-gated external actions.
- CONNECTORS: no social-platform connector, API client, credential, scheduling,
  or autonomous publication capability is implemented.

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
- Public Telegram webhook mode and public webhook hosting: not implemented.
- Broader Gmail, Drive, and Calendar runtime integrations: contract-only.
- Infrastructure implementation: not started.
- Dedicated observability implementation: not started.
