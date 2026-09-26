# Agent Company Roadmap

`PROJECT_STATE.md` is the canonical current-status record. This roadmap is the canonical forward capability roadmap after the verified Phase 6 checkpoint. Candidate capabilities below are planning scope unless explicitly marked as completed.

## Status Summary

- Phase 1-6: COMPLETED / COMMITTED.
- Phase 7: COMPLETED / CLOSED.
- Social Media capability checkpoint: COMPLETED / COMMITTED.
- Phase 8A: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8B: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8C: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8D: COMPLETED / CLOSED / NO DEPLOYMENT.
- CORE-01 Canonical Result Contract: COMPLETED / CLOSED.
- CORE-02 Continuation Policy: NEXT / NOT STARTED.
- Phase 8E: BLOCKED / PAUSED; deployment not started because the VPS has not
  yet been created.
- Phase 8F: NOT STARTED.
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

## Core Runtime Enhancements

- CORE-01 Canonical Result Contract: COMPLETED / CLOSED.
- CORE-02 Continuation Policy: NEXT / NOT STARTED.
- CORE-03 Eval Framework: PLANNED.
- CORE-04 Tool Discovery: PLANNED.
- CORE-05 Time Budget: PLANNED.
- CORE-06 Retry / Stop Policy: PLANNED.
- CORE-07 Progress Events: PLANNED.
- CORE-08 Context Discovery: PLANNED.
- CORE-09 Context Cache Policy: PLANNED.
- CORE-10 Effort Routing: PLANNED.
- CORE-11 External Content Isolation: PLANNED.

CORE-01 defines the canonical provider-agnostic Execution Result: WHAT HAPPENED.
Its final independent closure review passed with no Critical or Major findings.
CORE-02 through CORE-11 remain unimplemented. An aggregate serialized-result
byte ceiling is FUTURE HARDENING / NON-BLOCKING.

## Phases 8A, 8B, 8C, And 8D Closed

### Phase 8: Always-On Runtime And Deployment

Goal: move the verified local runtime into an optional always-on execution environment.

Phase 8A architecture design is COMPLETED / CLOSED. The canonical host and
threat-model design is in `infrastructure/`. It defines the infrastructure,
host/process, persistent-state, secrets, Docker, VPS, Telegram, webhook,
deployment/merge authority, Hermes, backup/recovery, threat-model, acceptance,
and staged implementation boundaries. The current baseline remains local; no
operating-system service, running container, VPS, Hermes integration, public
endpoint, merge authority, or deployment authority has been created.

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
8C is COMPLETED / CLOSED after its final independent re-review passed with no
critical, major, or required-fix findings. It adds fixed
scheduler/Telegram/webhook-local lifecycle wrappers, atomic process metadata,
OS-backed singleton enforcement, signals, host heartbeats, read-only status,
and stale-record recovery. The bounded Phase 8C repair makes provider enablement
fail closed before discovery, makes OS signal callbacks notification-only, and
serializes startup publication with persisted stop requests. It installs no
systemd unit, Windows Service, Task Scheduler job, automatic restart supervisor
daemon, Docker/VPS/Hermes component, public webhook hosting, TLS termination,
backup automation, merge authority, or deployment authority.

Phase 8D is COMPLETED / CLOSED after its independent architecture/security
review passed with no critical, major, or required-fix findings. It adds one non-root,
provider-neutral Linux image definition; fixed Compose services for scheduler,
Telegram, and optional webhook-local; one canonical named state volume; strict
per-service host configuration; and read-only lifecycle healthchecks. It adds
no provider CLI, embedded credential, public port, automatic restart policy,
VPS, TLS, reverse proxy, Hermes component, merge authority, or deployment
authority. Compose syntax and deterministic regressions pass, but a Docker
daemon was unavailable, so the image build and live-container smoke remain
unverified. These are Phase 8E runtime-validation prerequisites and do not
reopen Phase 8D. Phase 8E is BLOCKED / PAUSED because the VPS has not yet been
created; deployment has not started. Phase 8F is NOT STARTED.

Before Phase 8E production use, build the pinned image on the target Linux
architecture; perform an SBOM/vulnerability scan and verify or update the base
digest; validate fresh-volume ownership, non-root initialization, read-only-root
and `/tmp` behavior, cross-container singleton locks, `docker stop` signal and
final-state behavior, and live health transitions; validate the derived Linux
provider image/executable, provider-specific credential mount, authentication,
and environment isolation; and run live Telegram, provider, or public-ingress
smoke tests only with separate explicit approval.

Non-blocking Phase 8C future hardening is a different-provider full-repository
audit, real subprocess singleton-race validation, native Windows signal/ACL
validation, and more race-resistant status-lock probing. Phase 8B's
race-resistant directory-handle containment item also remains non-blocking.

## Planned

### Planned Canonical Capability Expansion

The current 10 canonical agents may later be joined by Finance & Pricing,
Analytics, Content, and Design. The target remains approximately 14 durable
canonical roles, not a collection of 20-30 micro-agents. Planned, unimplemented
skill expansion includes Finance/Pricing, Analytics, Content, Design, Sales lead
generation, SEO, and Reviewer QA/Security packs. Agent and skill definitions
remain separate.

### Phase 9: Observability, Control Room, And Hardening

Goal: make the system operationally understandable and production-ready.

- OBSERVABILITY: plan structured logs, metrics, runtime health, provider usage, and cost/token accounting where available.
- OBSERVABILITY: expose job, queue, scheduler, approval, reviewer, failure, retry, and recovery visibility.
- OBSERVABILITY: define audit trails and recovery tooling.
- CORE: plan security hardening for the runtime and remote interfaces.
- REMOTE INTERFACE: evaluate a Control Room as an operations and visualization layer over canonical Agent Company state.

The repository does not currently contain `apps/control-room`. A future Control Room must not become a second source of truth.

### Post-Phase-9 Decision Engine Evaluation

Only after Phase 9 observability exists, evaluate a bounded
`orchestrator/decision-engine/` with rules, scoring, classification, ranking,
confidence, and adapters. JEV may be considered only as an optional adapter for
classification, ranking, filtering, bounded choice, and confidence gating. It
is not an agent, human approval authority, or Claude/Codex-style execution
provider. Observability must measure whether it actually reduces token usage,
provider calls, cost, or routing mistakes before Phase 10 project packs.

### Phase 10: Project / Capability Packs

Goal: use the stable Agent Company core for real projects and domain-specific capabilities.

- PROJECT PACKS: express project-specific functionality through project state, skills, workflows, connector configuration, and domain-specific capability packs.
- PROJECT PACKS: keep Brightshore, YouTube, Instagram, Etsy, Travel, and Product
  Research/Amazon-style research as example pack candidates rather than
  committed implementation scope or canonical agents.
- RUNTIME: use the same shared Agent Company runtime for project packs.
- CORE: require user approval before consequential purchase, publication, account, financial, production, or external communication actions.

Project packs must not create separate Agent Company runtimes per project unless a later approved architecture explicitly changes that rule.

## Deferred Or Not Implemented

- Merge: deferred and not implemented.
- Deployment: deferred and not implemented.
- Public Telegram webhook mode and public webhook hosting: not implemented.
- Broader Gmail, Drive, and Calendar runtime integrations: contract-only.
- Phase 8D Docker adaptation and packaging: completed, closed, and not deployed.
- Phase 8E VPS deployment: BLOCKED / PAUSED because the VPS has not yet been
  created; deployment has not started and requires separate human approval.
- Phase 8F backup/recovery: NOT STARTED.
- Dedicated observability implementation: not started.
