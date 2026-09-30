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
- CORE-01 Canonical Result Contract: COMPLETED / CLOSED / COMMITTED at `3f6acb6`.
- CORE-02 Continuation Policy: COMPLETED / CLOSED / COMMITTED at `9d5ead1`.
- CORE-03 Eval Framework: COMPLETED / CLOSED / COMMITTED at `80ead22`.
- CORE-04 Tool / Skill Discovery: CLOSED / COMMITTED at `35f03f8` after
  CORE-04R5 PASS.
- CORE-05 Time / Execution Budget: CLOSED / COMMITTED at `63813b5` after
  CORE-05R3 PASS.
- CORE-06 Retry / Stop Policy: CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
- CORE-07 Progress Events: CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS.
- CORE-08: NEXT / NOT STARTED.
- CORE-09 through CORE-11: NOT STARTED.
- Phase 8E: PAUSED / BLOCKED; deployment not started because the VPS has not
  yet been created.
- Phase 8F: NOT STARTED.
- Phase 8G: NOT STARTED.
- Phase 8H: NOT STARTED.
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

- CORE-01 Canonical Result Contract: COMPLETED / CLOSED / COMMITTED at `3f6acb6`.
- CORE-02 Continuation Policy: COMPLETED / CLOSED / COMMITTED at `9d5ead1`.
- CORE-03 Eval Framework: COMPLETED / CLOSED / COMMITTED at `80ead22`.
- CORE-04 Tool / Skill Discovery: CLOSED / COMMITTED at `35f03f8` after
  CORE-04R5 PASS.
- CORE-05 Time / Execution Budget: CLOSED / COMMITTED at `63813b5` after
  CORE-05R3 PASS.
- CORE-06 Retry / Stop Policy: CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
- CORE-07 Progress Events: CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS.
- CORE-08 Context Discovery Before Action: NEXT / NOT STARTED.
- CORE-09 Context / Prompt Cache Policy: NOT STARTED.
- CORE-10 Compute / Effort Policy: NOT STARTED.
- CORE-11 External Content Isolation: NOT STARTED.

CORE-01 defines the canonical provider-agnostic Execution Result: WHAT HAPPENED.
Its final independent closure review passed with no Critical or Major findings.
CORE-02 is COMPLETED / CLOSED and committed at `9d5ead1` after CORE-02R6 PASS
with no Critical, Major, or Minor findings. CORE-03 now provides separate
provider-agnostic EvalSpec and EvalResult contracts, explicit deterministic
evaluators, content identity/versioning, typed immutable persistence, and a
minimal CLI. Eval is measurement evidence only: it grants no Reviewer,
approval, continuation, retry, Git, or deployment authority. CORE-03 is
COMPLETED / CLOSED / COMMITTED at `80ead22` after CORE-03R5 PASS with no
Critical, Major, or Minor findings. CORE-04 now provides an explicit immutable
tool registry, capability-first deterministic discovery, separate bounded
selection, and selected-only JSON definition/schema loading. Discovery and
loading grant no execution or governance authority. CORE-04 is implemented,
independently reviewed, closure-reconciled, and CLOSED / COMMITTED at `35f03f8`
after CORE-04R5 PASS with no Critical, Major, or Minor findings. CORE-05 now
provides immutable logical-job elapsed/execution-unit policy, atomic admission
and reservation, complete genesis-to-head validation of one content-addressed
append-only usage ledger, verified state/head caches, restart-safe accounting,
conservative crash recovery, and structured fail-closed exhaustion without
granting execution or governance authority. CORE-05 is CLOSED / COMMITTED at
`63813b5` after CORE-05R3 PASS. CORE-06 is CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
CORE-07 is CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS; CORE-08 is NEXT / NOT STARTED; CORE-09 through CORE-11 are NOT STARTED.
An aggregate
serialized-result byte ceiling is FUTURE HARDENING / NON-BLOCKING.

### CORE-06 Accepted Scope — CLOSED / COMMITTED at `4a6e5c4`

CORE-06 defines provider-neutral Retry Policy and Stop Policy, bounded
no-progress and stuck detection, cycle detection, unit-scoped repair,
repair-scope enforcement, safe retry of only the failed unit, local retry
limits, and the Retry -> Replan boundary. It must not treat provider prose,
`retryable`, `next_actions`, an available budget, or an unfinished job as retry
authority. The implementation is under `runtime/retry/`, with policy/state
schemas and Worker/Scheduler/job integration. `REPLAN_REQUIRED` is a boundary
only; automatic graph replanning remains owned by future ORCH-01. CORE-06 is
CLOSED / COMMITTED at `4a6e5c4` after R6 PASS. Exact-work and approval requirements
are preserved, restart/concurrency safety prevents consumed-attempt replay,
and canonical corruption fails closed. Retry remains separate from continuation
and retains the same CORE-05 logical budget without reset or refund.

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
reopen Phase 8D. Phase 8E is PAUSED / BLOCKED because the VPS has not yet been
created; deployment has not started. Phases 8F through 8H are NOT STARTED.

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

## Accepted V1 Roadmap — Planned / Not Started

The following plan is accepted V1 scope, not implemented current capability.
Its labels define ownership and sequencing only; they grant no execution,
approval, review, write, Git, deployment, or provider authority.

Owner outcome-first UX is PLANNED: the owner specifies the outcome; Agent
Company selects the workflow, agents, skills, tools, context, and providers
within the applicable authority contract.

CORE-08 planned scope covers context discovery before action, graceful
degradation and fallback resolution, semantic skill selection, semantic
context selection/reranking, selective verbatim context retention, and Code
Intelligence / Repository Index. Fallback order is preferred connector,
alternative connector, file/CSV/upload, manual structured input, then explicit
BLOCKED. Fallback must preserve evidence and authority requirements. It remains
NEXT / NOT STARTED.

Skill architecture is planned as provider-neutral metadata and triggers with
name, description, required capabilities, inputs, outputs, prerequisites,
references, and templates. Load only skills relevant to the task. Workflows
request connector capabilities rather than hard-coded vendors.


### A. Governance

#### GOV-01 — Task & Authority Contract

GOV-01 will define the canonical Task Contract: objective, inputs, expected
outputs, allowed tools, write scope, acceptance criteria, required checks,
required evidence, and explicit stop conditions. It also owns Risk / Delegation
Levels L0-L5, blast radius, reversibility, approval requirements, and
Evidence-Gated Task Completion.

Executor or agent success is not task completion. `DONE` requires successful
execution plus satisfied acceptance criteria, required evidence, and every
required review or gate.

#### GOV-02 — Capability Governance

GOV-02 will define Capability Certification, Decision Audit Trace,
policy/authority provenance, blast-radius gates, and reversibility gates.
Capability profiles are READ_ONLY, LOCAL_WRITE, EXTERNAL_PREPARE,
EXTERNAL_EXECUTE, and SENSITIVE_EXECUTE, integrated with delegation, blast
radius, reversibility, approval, and capability certification.

### B. Graph Orchestration

#### ORCH-01 — Graph Execution Runtime

ORCH-01 is not CORE-12. A loop operates inside a node; a graph connects nodes.
The owner specifies outcomes rather than workflows; Agent Company selects
clarification, task contract, graph, agents, skills, context, tools/providers,
eval/review, and approval points. Planned scope includes Planner / Splitter,
Worker nodes, deterministic nodes,
gate nodes, human gates, dependencies, fan-out, fan-in/merge, correction,
replan, and learning edges, edge validation, isolated fan-out contexts, and
unit-level repair integration.

Deterministic nodes may perform merge, deduplication, sorting, hashing, diff,
schema validation, test execution, artifact verification, counting, or
dependency resolution.

### C. Knowledge / Memory / RAG

Knowledge is what the system knows. Memory is what happened or was learned.
State is what is happening now. These remain separate.

- MEM-01 — Knowledge / Memory Foundation: provider-neutral `MemoryInterface`,
  project isolation, provenance, confidence, and verification semantics.
- MEM-02 — Knowledge Lifecycle + Retrieval / RAG: capture, normalize,
  deduplicate, classify, connect, store, retrieve, rerank, build context packs,
  selectively retain relevant context, act, verify, and learn from run traces.
  Anchored evidence-backed memory may link to files,
  symbols, tasks, workflows, decisions, runs, tests, evidence, agents, or
  capabilities and record provenance, verification, confidence, validity, and
  supersession.
- MEM-02B — Learning Constraint Pipeline: observation -> candidate lesson ->
  evidence -> deduplication -> scope -> validation/review -> promotion -> active
  planning constraint. A PASS does not automatically become a permanent rule.
- MEM-03 — Memory Providers: local provider first. Hindsight is only a future
  prototype provider behind `MemoryInterface`; SwarmVault and Vault Curate are
  reference patterns, not core dependencies.

### D. Agent Expansion

The current canonical agent count is 10. V1 targets 14 by later adding:

11. Finance & Pricing
12. Analytics
13. Content
14. Design

SEO, AEO, GEO, JEV, Memory, SAGE, Sentinel, Chimera, Lead Finder, Firecrawl,
and DataForSEO are not canonical agents.

### E. Capability Expansion

- CAP-SALES: lead finding, lead research, qualification, outreach, and
  follow-up.
- CAP-SEARCH-GROWTH-01: one cross-agent Search Growth system covering SEO, AEO,
  GEO, search intent, commercial keyword strategy, technical and on-page SEO,
  internal linking, content funnel, authority building, AI-search readiness,
  answer extractability, conversion, experiments, and seasonal planning.
- CAP-REV-01: QA, Security, Knowledge, Release, External / Client-Facing
  Output Review, Citation Verification, Extraction Verification, Semantic
  Completion Verification, and Change Impact Review. Change Impact Review considers the task, acceptance criteria, diff, changed symbols,
  dependencies, architecture decisions, related memory, previous failures, and
  tests.
- Code Intelligence / Repository Index: planned under CORE-08 and the Software
  capability, covering symbols, dependencies, call relationships, affected
  files, repository context, and related architectural memory.

### F. Phase 9

- Phase 9A — Observability: task success, cost per completed task, latency,
  provider calls, tool errors, retries, continuation, replans, escalation, and
  eval history; Unified Run Trace, Exact Replay, Semantic Regression,
  Trace → Eval → Lesson Candidate, and provider/model behavioural comparison.
  Lesson candidates still require MEM-02B validation and promotion. Later graph
  metrics include planned/executed/skipped nodes,
  parallel branches, repairs, replans, gate failures, human interventions,
  rollbacks, critical-path time, provider/token cost, and wall-clock time.
- Phase 9B — Control Room: Projects, Agents, Jobs, Approvals, Providers, Costs,
  Reviews, Evals, Graph execution, Knowledge, Memory, Decisions, Lessons,
  Planning Constraints, and Context Packs. Control Room Owner Home is the
  primary natural-language goal entry: "What do you want to do?" Manual agent,
  skill, and workflow selection is not the primary UX. It remains a view/operator
  layer over canonical state, never a second source of truth.
- Phase 9C — Operating Layer: Morning Map, State Delta, Weekly Close / Weekly
  Compounding, Lessons Learned, Automation Opportunities, and Pre-flight Review.

### G. Decision Engine / JEV

- DEC-01 — Provider-neutral Decision Engine: deterministic rules plus worker,
  skill, context, and option selectors; classification, scoring, ranking,
  confidence, and escalation. Generation belongs to
  an execution provider, bounded decisions to the Decision Engine or possible
  JEV adapter, and exact rules to deterministic code. Decision authority stays
  separate from execution authority.
- DEC-02 — JEV Pilot: initially limited to low-risk next-worker routing, skill
  selection, context relevance/reranking, and semantic eval. Context compaction
  selection, stuck detection, and citation/extraction verification are later
  candidates only if metrics justify them. JEV is not an agent, Reviewer,
  approval/security authority, or normal generation provider.

Canonical JEV rule: **JEV judges. Policy authorizes. Executor acts.**

JEV is a bounded semantic judging component: it does not authorize actions,
serve as an agent or Reviewer, or act as a normal generation provider.

### H. Deployment

- Phase 8E — Real VPS deployment: PAUSED / NOT COMPLETE.
- Phase 8F — Backup / Recovery: NOT STARTED.
- Phase 8G — Production smoke tests: NOT STARTED.
- Phase 8H — Final deployment security review: NOT STARTED.

All four remain required before the system can be described as
production-deployed or always-on.

### I. Phase 10 — Project / Domain Packs

Brightshore is the first production Project Pack. A pack may reference skills,
workflows, knowledge, policies, connector capability requirements, templates,
and project configuration, but never duplicates the Agent Company runtime
or canonical agents. YouTube, social content, digital products, travel, Etsy, and other
packs are later expansion and do not block V1 unless explicitly approved.

## Canonical V1 Definition

V1 consists of CORE-01 through CORE-11; GOV-01 and GOV-02; ORCH-01; the
Knowledge / Memory / RAG foundation; 14 canonical agents; essential Sales,
Search Growth, and Reviewer capabilities; Code Intelligence; Phase 9A through
9C; DEC-01 and the bounded DEC-02 pilot; Phase 8E through 8H deployment and
security completion; and Brightshore as the first production Project Pack.

## Later / Important — Not V1 Blockers

- Persistent Agent Mailbox.
- Git Worktree Isolation.
- Advanced Agent Teams / parallel execution.
- Credential / Secret Broker.
- Advanced Knowledge Graph.
- Multi-model Council / disagreement escalation.
- Additional memory providers.
- Advanced context compaction.
- Browser Semantic Action Selector.
- Typed Tool-call Semantic Compiler.
- Jevgrep.
- Beacon importer/adapter.
- Later JEV / Beacon experiments beyond the bounded DEC-02 V1 pilot.

## Deferred Or Not Implemented

- Merge, release, and deployment authority are not implemented.
- Public Telegram webhook mode and public webhook hosting are not implemented.
- Broader Gmail, Drive, and Calendar runtime integrations remain contract-only.
- Phase 8D Docker adaptation and packaging is completed, closed, and not
  deployed.
- Phase 8E is PAUSED / NOT COMPLETE and requires separate human approval.
- Phases 8F, 8G, and 8H are NOT STARTED.
- Governance, graph orchestration, memory/RAG runtime, agents 11-14, capability
  expansion, Code Intelligence, Phase 9, Decision Engine/JEV, and Phase 10 are
  planned and unimplemented.
