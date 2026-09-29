# Agent Company

Agent Company is a local-first, model-independent operating core for coordinating AI agents across multiple projects without losing context. It starts with Claude and Codex as execution providers, and is designed to support ChatGPT and other providers later.

The company is not any one model. Providers execute work. The company core defines the durable rules, roles, state boundaries, review expectations, and routing principles that let different engines work consistently.

## Architecture

At a high level, the system separates these concerns:

- Agents define who performs work.
- Skills define how reusable work is performed.
- Prompts define task-specific instructions.
- Workflows define execution order.
- Reviewers and gatekeepers independently validate important work.
- Operational state records current work in progress.
- Long-term knowledge records stable, reusable facts and decisions.
- Provider adapters translate canonical company rules into provider-specific bootstraps.

Canonical definitions must remain separate from generated provider files. Claude, Codex, ChatGPT, and future engines should all defer to the same company constitution and operating instructions.

## Current State

CORE-04 implementation commit `35f03f8` contains the committed Tool / Skill Discovery /
Deferred Loading implementation and closure state. CORE-05 Time / Execution
Budget is CLOSED / COMMITTED at `63813b5` after CORE-05R3 PASS.
Phases 1-7 are closed, the Social Media capability is committed, Phase 8A is
closed, and Phases 8B and 8C are completed and closed after successful
independent review. Phase 8D's independent architecture/security review passed
with no critical, major, or required-fix findings. Phase 8D is COMPLETED /
CLOSED and not deployed. Phase 8E is PAUSED / BLOCKED; deployment has not
started because the VPS has not yet been created. Phases 8F through 8H are NOT
STARTED.

CORE-01 Canonical Result Contract is COMPLETED / CLOSED and committed at
`3f6acb6`. CORE-02 Continuation Policy is COMPLETED / CLOSED and committed at
`9d5ead1` after CORE-02R6 PASS with no Critical, Major, or Minor findings.
CORE-03 Eval Framework is COMPLETED / CLOSED / COMMITTED at `80ead22` after
CORE-03R5 PASS with no Critical, Major, or Minor findings. CORE-04 Tool / Skill
Discovery is CLOSED / COMMITTED at `35f03f8` after CORE-04R5 PASS with no
Critical, Major, or Minor findings. It adds explicit immutable registration,
exact capability-first matching, deterministic bounded selection, and
selected-only definition/schema loading without granting tool or execution
authority. CORE-05 adds immutable logical-job active-time/execution-unit bounds,
atomic admission/reservation, a complete genesis-validated content-addressed
usage ledger with independently verified state/head caches, restart-safe
accounting, and structured fail-closed exhaustion without granting
approval, review, continuation, retry, write, Git, or deployment authority. It
is CLOSED / COMMITTED at `63813b5` after CORE-05R3 PASS. CORE-06 Retry / Stop
Policy is CLOSED / READY TO COMMIT after CORE-06R6 PASS; its implementation
remains uncommitted. CORE-07 through CORE-11 are NOT STARTED. The
aggregate serialized-result byte ceiling remains FUTURE HARDENING / NON-BLOCKING.

The runtime remains local-first. Phase 8D packages the canonical Phase 8C
foreground lifecycle into one non-root image definition and fixed Compose
services. It adds no systemd unit, Windows Service, Task Scheduler job,
automatic restart supervisor daemon, VPS, Hermes, public webhook hosting, TLS
termination, merge authority, or deployment authority.
`PROJECT_STATE.md` is the canonical current-status record and `ROADMAP.md` is
the canonical capability roadmap.

## Current Repository Structure

This is the physical structure in the current checkout; generated contents and
ignored local configuration are intentionally not expanded.

- `agents/` — 10 canonical roles: communications, knowledge-manager, marketing,
  operations, project-manager, research, reviewer, sales, social-media, and
  software. Each keeps `ROLE.md`, `GUARDRAILS.md`, and agent-specific `MEMORY.md`.
- `skills/` — separate reusable HOW definitions in communications, marketing,
  operations, sales, shared, and social-media families.
- `orchestrator/` — `dispatcher/`, `routing/`, `workflows/`, `approvals/`, and
  `dry-run/`.
- `providers/` — Claude and Codex execution-provider definitions only.
- `integrations/` — github, gmail, google-calendar, google-drive, obsidian,
  telegram, and webhooks; runtime implementations exist only where explicitly
  represented by source.
- `runtime/` — `actions/`, `approvals/`, `budget/`, `cli/`, `continuation/`,
  `core/`, `evals/`, `execution/`, `executors/`, `git/`, `host/`, `jobs/`,
  `notifications/`, `providers/`, `queue/`, `remote/`, `review/`, `retry/`,
  `scheduler/`, `storage/`, `tests/`, `tools/`, `webhooks/`, and `workers/`.
  `runtime/budget/` is the committed CORE-05 implementation and
  `runtime/retry/` is the uncommitted CORE-06 implementation, CLOSED / READY
  TO COMMIT after CORE-06R6 PASS. `runtime/state/`
  contains its tracked boundary README plus ignored operational state; it is not
  a future source-architecture namespace.
- `infrastructure/` — `HOST_ARCHITECTURE.md`, `SECURITY_MODEL.md`, its README,
  and `docker/` with non-secret per-service configuration and operating notes.
- `Dockerfile`, `.dockerignore`, and `compose.yaml` — Phase 8D packaging for the
  existing canonical runtime; no image build or deployment is recorded.
- `shared/projects/` — operational project state; currently includes
  `brightshore/`.
- `shared/knowledge/` — indexed long-term knowledge, sources, raw material,
  operations, and synthesized wiki content.
- `schemas/` — persisted runtime contracts, summarized rather than expanded
  here.
- `config/` — tracked non-secret examples only: `host.example.json`,
  `remote.example.json`, and `webhooks.example.json`. Ignored local files,
  tokens, real IDs, and secret values are not documentation inputs.
- `.agents/` and `.claude/` — provider-specific adapters that defer to the
  canonical agents and skills; `agent-generation/` documents adapter generation.
- `docs/` and top-level `tests/` — physically present but empty; this audit
  created no files or hierarchy in either directory.

Agent = WHO. Skill = HOW. Workflow = ORDER. Provider = execution engine.
Execution Result = WHAT HAPPENED. Eval = HOW THE RESULT / BEHAVIOR MET DECLARED
EXPECTATIONS. `shared/projects/` is operational project
state, `shared/knowledge/` is long-term synthesized knowledge, agent
`MEMORY.md` files hold role-specific durable lessons, and `runtime/state/` is
runtime operational state. These stores remain separate.

## Future / Target Repository Structure

Every path in this section is PLANNED and absent from the current physical tree.
It records structural ownership only; implementation checkpoints create paths
when real content exists.

- CORE-07: `runtime/progress/`.
- CORE-08: `runtime/context/` and `runtime/code-intelligence/`.
- CORE-09: `runtime/cache/`.
- CORE-10: `runtime/compute-policy/`.
- CORE-11: `runtime/isolation/`.
- GOV-01: `governance/task-contract/`, `governance/delegation/`,
  `governance/stop-conditions/`, and `governance/completion/`.
- GOV-02: `governance/capability-certification/` and
  `governance/audit/decision-trace/`.
- ORCH-01: `orchestrator/graph/`.
- MEM-01 through MEM-03: `runtime/memory/` and `shared/memory/`.
- Agents 11-14: `agents/finance-pricing/`, `agents/analytics/`,
  `agents/content/`, and `agents/design/`.
- CAP-SEARCH-GROWTH-01: `skills/search-growth/` and
  `orchestrator/workflows/search-growth/`.
- Phase 9A: `observability/`.
- Phase 9B: `apps/control-room/`.
- DEC-01: `orchestrator/decision-engine/`.
- DEC-02: `orchestrator/decision-engine/adapters/jev/`.
- Phase 10: `project-packs/brightshore/` first. The existing
  `shared/projects/brightshore/` is current operational project state, not a
  production Project Pack.

The current 10 canonical agents may later be joined by Finance & Pricing,
Analytics, Content, and Design for a V1 total of 14. SEO, AEO, GEO, JEV,
Memory, SAGE, Sentinel, Chimera, Lead Finder, Firecrawl, and DataForSEO are not
canonical agents. JEV remains only a possible bounded DEC-02 adapter, never a
normal execution provider, Reviewer, approval authority, or security authority.

No planned directory in this section was created by this documentation task.

## Repository Tree Reconciliation Policy

After any structural checkpoint, use this sequence:

implementation -> validation -> review -> closure -> commit -> repository tree
audit -> DOC-TREE reconciliation when the filesystem changed.

Planned empty directories are never created merely for documentation
completeness. The Current Repository Structure above describes only physical
paths; this Future / Target section is the only place where absent paths are
presented as planned structure.

## Canonical V1 Target

V1 includes CORE-01 through CORE-11; GOV-01 and GOV-02; ORCH-01 Graph Execution
Runtime; the Knowledge / Memory / RAG foundation; 14 canonical agents;
essential Sales, Search Growth, and Reviewer capabilities; Code Intelligence;
Phase 9 Observability, Control Room, and Operating Layer; DEC-01 plus a bounded
DEC-02 JEV pilot; Phase 8E through 8H deployment/security completion; and
Brightshore as the first production Project Pack. Persistent Agent Mailbox, Git
Worktree Isolation, advanced Agent Teams, Credential / Secret Broker, Advanced
Knowledge Graph, Multi-model Council, additional memory providers, and advanced
context compaction remain later/important and do not block V1.

The current runtime does not implement merge, release, deployment, public
webhook hosting, TLS termination, remote task submission, remote scheduler or
filesystem/Git commands, general connector execution, infrastructure
deployment automation, Hermes integration, VPS hosting, Control Room, or a
dedicated observability platform.

## Operating Boundary

Provider execution is explicit and approval boundaries remain authoritative.
Remote users require an exact command permission; approval decisions also
require configured action/project scope and the current canonical approval
fingerprint. Telegram commands are private-chat only. Webhooks are authenticated
machine ingress on loopback and never human approval. The local scheduler is
sequential and file-backed; it does not install an operating-system service or
create approval authority.

## Quick Start

Read these files in order:

1. `INTENT.md`
2. `CONSTITUTION.md`
3. `AGENTS.md`
4. `PROJECT_STATE.md`
5. `ROADMAP.md`
6. Any provider-specific bootstrap, such as `CLAUDE.md`
