# Agent Company TODO

## Core Runtime Enhancements

- [x] CORE-01 Canonical Result Contract — COMPLETED / CLOSED / COMMITTED at
  `3f6acb6` after final independent closure review PASS with no Critical or
  Major findings.
- [x] CORE-02 Continuation Policy — COMPLETED / CLOSED / COMMITTED at `9d5ead1`
  after CORE-02R6 PASS with no Critical, Major, or Minor findings.
- [x] CORE-03 Eval Framework — COMPLETED / CLOSED / COMMITTED at `80ead22`
  after CORE-03R5 PASS with no Critical, Major, or Minor findings.
- [x] CORE-04 Tool / Skill Discovery — CLOSED / COMMITTED at `35f03f8` after CORE-04R5
  PASS with no Critical, Major, or Minor findings.
  - [x] Implementation complete.
  - [x] Bounded repairs complete.
  - [x] Independent re-review complete.
  - [x] Closure reconciliation complete.
  - [x] Implementation commit complete at `35f03f8`.
- [x] CORE-05 Time / Execution Budget — CLOSED / COMMITTED at `63813b5` after
  CORE-05R3 PASS.
  - [x] Immutable bounded logical-job policy and schemas.
  - [x] Atomic execution-unit reservation and restart-safe active-time usage.
  - [x] Continuation/retry inheritance, crash recovery, and fail-closed
    exhaustion.
  - [x] Targeted and regression implementation validation.
  - [x] Initial independent review and bounded R1 repairs.
  - [x] R2 full-chain and coherent-current-layer bounded repairs.
  - [x] Independent re-review complete: CORE-05R3 PASS with no Critical, Major,
    or Minor findings.
  - [x] Closure reconciliation complete.
  - [x] Implementation commit complete at `63813b5`.
- [x] CORE-06 Retry / Stop Policy — CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6
  PASS.
  - [x] Define retry and stop policy without treating `retryable` as authority.
  - [x] Add bounded no-progress, stuck, and cycle detection.
  - [x] Define unit-scoped repair and enforce repair scope.
  - [x] Retry only the failed unit when safe, within local retry limits.
  - [x] Define the Retry -> Replan boundary without automatic replanning.
  - [x] Complete targeted implementation and regression validation.
  - [x] CORE-06R1 independent review returned FIX; bounded F1–F8 repairs applied.
  - [x] CORE-06R2 returned FIX; bounded CORE-06F2A repairs applied with adversarial tests.
  - [x] CORE-06R3 returned FIX; only its four Major findings received bounded CORE-06F3 repairs.
  - [x] CORE-06R4 returned FIX; only its three Major findings received bounded CORE-06F4 repairs.
  - [x] Independent re-review complete: CORE-06R6 PASS with no Critical, Major,
    or Minor findings; external evidence recorded in PROJECT_STATE.md.
  - [x] Closure reconciliation complete.
  - [x] Implementation commit complete at `4a6e5c4`.
- [x] CORE-07 Progress Events — CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS.
  - [x] Implementation, bounded repairs, and independent re-review complete.
  - [x] Closure documentation reconciled; progress remains non-authoritative.
  - [x] Implementation commit complete at `6bcffa4`.
- [x] CORE-08 Context Discovery Before Action - CLOSED / COMMITTED at `1a1b029`
  after CORE-08R3 PASS.
  - [x] Bounded context discovery, capability fallback, skill metadata and
    selected-only loading, ranking interfaces, and selective verbatim retention.
  - [x] Bounded in-memory repository index with Python syntax relationships;
    read-only knowledge/memory interface. See `runtime/context/README.md` for
    implemented limits; no connector execution or persistent memory is claimed.
- [x] CORE-09 Context / Prompt Cache Policy - CLOSED / COMMITTED at `fa7e30f`
  after CORE-09R2 PASS. CORE-01-09 are CLOSED / COMMITTED.
- [x] CORE-10 Compute / Effort Policy - CLOSED / READY TO COMMIT after CORE-10R3
  PASS; uncommitted. Security-aware routing lives in `runtime/compute_policy/`.
- [ ] CORE-11 External Content Isolation — NOT STARTED.
- [ ] FUTURE HARDENING / NON-BLOCKING: add an aggregate serialized-result byte
  ceiling.

## Accepted V1 Backlog — NOT STARTED

- [ ] Owner outcome-first UX: owner specifies the outcome; Agent Company selects
  workflow, agents, skills, tools, context, and providers within policy.
- [ ] GOV-01 Task & Authority Contract: canonical task contract, L0-L5 risk and
  delegation levels, blast radius, reversibility, approvals, explicit stop
  conditions, and evidence-gated completion.
- [ ] GOV-02 Capability Governance: capability certification, decision audit
  trace, policy/authority provenance, and blast-radius/reversibility gates. Add
  READ_ONLY, LOCAL_WRITE, EXTERNAL_PREPARE, EXTERNAL_EXECUTE, and
  SENSITIVE_EXECUTE profiles integrated with delegation, blast radius,
  reversibility, approval, and certification.
- [ ] ORCH-01 Graph Execution Runtime: owner specifies outcomes, not workflows;
  Agent Company selects clarification, task contract, graph, agents, skills,
  context, tools/providers, eval/review, and approval points. Include
  planner/splitter, worker and deterministic nodes, gates, dependencies,
  fan-out/fan-in, correction/replan/learning edges, edge validation, isolated
  branch contexts, and unit-level repair integration. ORCH-01 is not CORE-12;
  loops remain inside nodes and graphs connect nodes.
- [ ] MEM-01 Knowledge / Memory Foundation: provider-neutral MemoryInterface,
  project isolation, provenance, confidence, and verification semantics while
  preserving Knowledge != Memory != State.
- [ ] MEM-02 Knowledge Lifecycle + Retrieval / RAG: normalized, deduplicated,
  classified, connected, evidence-backed retrieval/RAG, reranking, context
  packs, anchored/evidence-backed memory, trace-derived lessons, learning
  constraints, selective context retention, action verification, and learning.
- [ ] MEM-02B Learning Constraint Pipeline: promote observations to planning
  constraints only after evidence, deduplication, scoping, and review; PASS is
  not automatically a permanent rule.
- [ ] MEM-03 Memory Providers: local provider first; Hindsight only as a future
  provider behind MemoryInterface; SwarmVault/Vault Curate are references, not
  core dependencies.
- [ ] Add canonical Agent 11 Finance & Pricing.
- [ ] Add canonical Agent 12 Analytics.
- [ ] Add canonical Agent 13 Content.
- [ ] Add canonical Agent 14 Design.
- [ ] CAP-SALES: lead finding, research, qualification, outreach, and follow-up.
- [ ] CAP-SEARCH-GROWTH-01: one cross-agent SEO/AEO/GEO and search-growth system;
  do not create SEO, AEO, or GEO agents.
- [ ] CAP-REV-01: QA, Security, Knowledge, Release, External / Client-Facing
  Output Review, Citation Verification, Extraction Verification, Semantic
  Completion Verification, and Change Impact Review.
- [ ] Advanced Code Intelligence beyond the committed CORE-08 bounded index:
  cross-language semantic call resolution, advanced graphs, and persistent
  architectural memory integration remain deferred.
- [ ] Phase 9A Observability: Unified Run Trace, Exact Replay, Trace → Eval,
  Semantic Regression, provider/model behavioural comparison, and Trace → Eval →
  Lesson Candidate (subject to MEM-02B).
- [ ] Phase 9B Control Room over canonical state; Owner Home natural-language
  goal entry: "What do you want to do?"; manual agent/skill/workflow selection
  is not the primary UX.
- [ ] Phase 9C Operating Layer: Morning Map, State Delta, Weekly Close, Lessons
  Learned, Automation Opportunities, and Pre-flight Review.
- [ ] DEC-01 provider-neutral Decision Engine with deterministic rules, worker,
  skill, context, and option selectors; classification, scoring, ranking,
  confidence, and escalation; decision authority remains separate from execution
  authority.
- [ ] DEC-02 bounded JEV pilot for next-worker routing, skill selection,
  context relevance/reranking, and semantic eval. Context compaction selection,
  stuck detection, and citation/extraction verification are later candidates
  only if metrics justify them. JEV judges. Policy authorizes. Executor acts.
  JEV is not an agent, Reviewer, approval authority, or normal generation
  provider.
- [ ] Phase 10 Project / Domain Packs, beginning with Brightshore; packs may
  reference skills, workflows, knowledge, policies, connector capability
  requirements, templates, and project configuration, without duplicating the
  runtime or canonical agents.

- [ ] DEC-01: Decision State Contract, Live Candidate Menu, Decision escape hatch,
  and composite scoring within policy; details owned by ROADMAP.
- [ ] Phase 9A: decision/JEV quality, confidence, escalation, cost, and latency metrics.
- [ ] GOV-01: preserve execution/eval/review/approval/task-completion separation.
- [ ] Creative Media Generation: capability/workflow/tool integration, no new agent;
  Higgsfield optional/non-blocking; verify third-party performance claims.
- [ ] CAP-SOC-01 One-Person Social Media Team / Social Media Operating System:
  lifecycle, approval/scheduling, repurposing, basic community triage, human
  handoff, performance -> memory, and basic Phase 9B Social Media HQ.
  Existing Social Media agent owns the domain; roadmap defines role boundaries.

## Later / Important — Not V1 Blockers

- [ ] CAP-SOC-01 advanced DM autonomy, influencer automation, advanced attribution,
  complete platform coverage, and full autonomous community management.
- [ ] Persistent Agent Mailbox.
- [ ] Git Worktree Isolation.
- [ ] Advanced Agent Teams / parallel execution.
- [ ] Credential / Secret Broker.
- [ ] Advanced Knowledge Graph.
- [ ] Multi-model Council / disagreement escalation.
- [ ] Additional memory providers.
- [ ] Advanced context compaction.
- [ ] Browser Semantic Action Selector.
- [ ] Typed Tool-call Semantic Compiler.
- [ ] Jevgrep.
- [ ] Beacon importer/adapter.
- [ ] Later JEV / Beacon experiments beyond the bounded DEC-02 V1 pilot.

## Phase 7 Planning

- [x] Define the Phase 7 threat and authority model in `runtime/remote/AUTHORITY_MODEL.md`.
- [x] Define the remote-command contract in `runtime/remote/COMMAND_CONTRACT.md`.
- [x] Define the Telegram connector/runtime boundary in `integrations/telegram/CONTRACT.md`.
- [x] Define remote approval and rejection interaction in `runtime/remote/AUTHORITY_MODEL.md`.
- [x] Determine the webhook runtime ingestion boundary in `integrations/webhooks/CONTRACT.md`.
- [x] Define Phase 7 acceptance criteria in `runtime/remote/README.md`.

## Phase 7 Implementation Tasks

- [x] Add a canonical RemoteCommand model and deterministic command ID/idempotency validation.
- [x] Add explicit remote identity mapping from stable platform IDs to trusted human or machine identities without tracked secrets.
- [x] Add a RemoteCommandService that calls only existing runtime/orchestrator authority surfaces.
- [x] Persist remote approval audit evidence for authenticated remote actor, source channel, platform identity, command ID, and approval binding.
- [x] Add duplicate update/callback replay protection with persisted command audit records.
- [x] Add Telegram transport adapter tests without calling Telegram APIs.
- [x] Add authenticated local-first webhook ingress with signed trusted machine events, durable replay/idempotency state, canonical routing, bounded audit evidence, and rejected human-approval attempts.
- [x] Add remote notification formatting for approval requested/resolved, job completed/failed, and scheduler/runtime errors.
- [x] Add deny-by-default command permissions and action/project-scoped remote approval policy.
- [x] Restrict Telegram command handling to authenticated private chats.
- [x] Persist remote approval intent before mutation and expose incomplete mutation audit state.
- [x] Reject excessive future command timestamps with bounded clock skew.
- [x] Run the full Phase 6/7 regression suite after security remediation (424/424 PASS on 2026-09-24).
- [x] Pass the final repository-backed Phase 7 architecture and security review
  (142/142 targeted and 430/430 full runtime tests PASS on 2026-09-24).
- [x] Record Phase 7 as COMPLETED / CLOSED; retain a different-provider
  full-repository audit as recommended future validation rather than a gate.

## Phase 8A Design — COMPLETED / CLOSED

- [x] Inventory current always-on-safe runtime assumptions without claiming distributed guarantees.
- [x] Define the canonical host, process, persistent-state, secret, ingress, backup, and authority boundaries.
- [x] Assess Docker, a vendor-neutral VPS target, Telegram long polling, public webhook prerequisites, and optional Hermes use.
- [x] Define the Phase 8 threat model, acceptance criteria, and implementation stages in `infrastructure/`.
- [x] Close the recorded Phase 7 independent review gate before Phase 8 implementation.
- [x] Record Phase 8A as COMPLETED / CLOSED with no deployment and no Phase 8B implementation.
- [x] Implement Phase 8B host configuration, canonical persistence paths,
  initialization, and readiness checks without deploying.
- [x] Repair the Phase 8B independent-review security and correctness findings.
- [x] Pass the Phase 8B independent implementation/security re-review and
  record Phase 8B as COMPLETED / CLOSED.
- [x] Implement Phase 8C background process lifecycle and deterministic recovery
  validation without public exposure.
- [x] Repair the three Phase 8C review blockers: provider-enable bypass,
  signal-callback reentrancy, and startup/stop-request overwrite.
- [x] Complete the successful Phase 8C independent implementation/security
  re-review and record Phase 8C as COMPLETED / CLOSED.
- [x] Implement the Phase 8D Docker adaptation with one non-root image, fixed
  Compose services, persistent canonical state, and no public exposure.
- [x] Complete the Phase 8D independent implementation/security review with no
  critical, major, or required-fix findings and close Phase 8D.
- [ ] Phase 8E is PAUSED / BLOCKED because the VPS has not yet been created;
  deployment has not started.
- [ ] Before Phase 8E production use, build the pinned image on the target Linux
  architecture and perform an SBOM/vulnerability scan.
- [ ] Verify or update the base-image digest where appropriate.
- [ ] Verify fresh named-volume ownership, non-root `host init`, read-only-root
  behavior, and `/tmp` behavior.
- [ ] Verify duplicate-process locking across containers, `docker stop` signal
  delivery, lifecycle final state after stop, and live health transitions.
- [ ] Validate the derived Linux provider image/executable, provider-specific
  credential mount, provider authentication, and provider environment isolation.
- [ ] Run live Telegram, provider, or public-ingress smoke tests only with
  separate explicit approval.
- [ ] Require exact human approval before Phase 8E VPS deployment or any later public exposure.
- [ ] Phase 8F backup/recovery is NOT STARTED.
- [ ] Phase 8G production smoke testing is NOT STARTED.
- [ ] Phase 8H final deployment security review is NOT STARTED.

Non-blocking Phase 8C future hardening: different-provider full-repository
audit, real subprocess singleton-race validation, native Windows signal/ACL
validation, and more race-resistant status-lock probing. Race-resistant
directory-handle containment remains a separate non-blocking Phase 8B item.
