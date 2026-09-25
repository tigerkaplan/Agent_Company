# Agent Company Roadmap

`PROJECT_STATE.md` is the canonical current-status record. This roadmap is the canonical forward capability roadmap after the verified Phase 6 checkpoint. Candidate capabilities below are planning scope unless explicitly marked as completed.

## Status Summary

- Phase 1-6: COMPLETED / COMMITTED.
- Phase 7: COMPLETED / CLOSED.
- Social Media capability checkpoint: COMPLETED / COMMITTED.
- Phase 8A: PASS / COMPLETED / NO DEPLOYMENT.
- Phase 8B: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8C: NEXT / NOT STARTED.
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

## Completed / Closed

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
The final repository-backed Phase 7 architecture and security review passed on
2026-09-24: 142/142 targeted Phase 7 tests and 430/430 full runtime tests passed,
100 Python files compiled, and 15 schemas parsed. Phase 7 is closed. A future
different-provider full-repository audit remains recommended validation, not a
mandatory Phase 8 implementation gate.

## Completed / Committed Capability Checkpoint

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

## Phase 8A Completed; Phase 8B Completed / Closed

### Phase 8: Always-On Runtime And Deployment

Goal: move the verified local runtime into an optional always-on execution environment.

Phase 8A architecture design is PASS / COMPLETED. The canonical host and
threat-model design is in `infrastructure/`. It defines the infrastructure,
host/process, persistent-state, secrets, Docker, VPS, Telegram, webhook,
deployment/merge authority, Hermes, backup/recovery, threat-model, acceptance,
and staged implementation boundaries. The current baseline remains local; no
service, Docker image, VPS, Hermes integration, public endpoint, merge
authority, or deployment authority has been created.

- RUNTIME: plan background runtime hosting, process lifecycle, startup/restart behavior, and recovery.
- DEPLOYMENT: define environment and secrets management for optional hosted operation.
- DEPLOYMENT: evaluate Docker and VPS deployment options.
- DEPLOYMENT: evaluate Hermes only if it provides concrete value as a runtime or host integration.
- DEPLOYMENT: design backup/recovery for operational runtime state.
- CORE: define deployment authority before any deployment implementation exists.

Hermes is optional and must not be treated as the Agent Company core. Merge and deployment authority remain absent until deliberately implemented and approved.

Proposed implementation stages are Phase 8B host configuration and persistence,
8C background process lifecycle, 8D optional Docker adaptation and packaging,
8E VPS deployment, 8F backup/recovery, 8G deployment smoke testing, and 8H final
independent security review. Phase 8B is COMPLETED / CLOSED after its final
independent re-review passed with no critical, major, or required-fix findings.
It adds
the canonical state root, strict non-secret host configuration, fixed path
resolver, dedicated-root rejection before initialization, default-deny
provider child environments, symmetric state/credential/secret separation,
and deterministic readiness failures while preserving local defaults. Phase
8C is NEXT / NOT STARTED. No process supervisor or service lifecycle, systemd,
Windows Service, Docker/VPS/Hermes installation, public webhook exposure,
backup automation, merge authority, or deployment authority was added.

Future hardening remains separate from Phase 8B closure: a cross-provider audit
when available, native Windows ACL inspection, and race-resistant
directory-handle containment.

## Planned

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
- Phase 8C background process lifecycle and later infrastructure stages: not
  started.
- Dedicated observability implementation: not started.
