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

Git HEAD `6da9e0f` contains the committed CORE-03 post-commit state
reconciliation. CORE-04 implementation and closure-reconciliation changes are
uncommitted.
Phases 1-7 are closed, the Social Media capability is committed, Phase 8A is
closed, and Phases 8B and 8C are completed and closed after successful
independent review. Phase 8D's independent architecture/security review passed
with no critical, major, or required-fix findings. Phase 8D is COMPLETED /
CLOSED and not deployed. Phase 8E is BLOCKED / PAUSED; deployment has not
started because the VPS has not yet been created. Phase 8F is NOT STARTED.

CORE-01 Canonical Result Contract is COMPLETED / CLOSED and committed at
`3f6acb6`. CORE-02 Continuation Policy is COMPLETED / CLOSED and committed at
`9d5ead1` after CORE-02R6 PASS with no Critical, Major, or Minor findings.
CORE-03 Eval Framework is COMPLETED / CLOSED / COMMITTED at `80ead22` after
CORE-03R5 PASS with no Critical, Major, or Minor findings. CORE-04 Tool
Discovery is CLOSED / READY TO COMMIT after CORE-04R5 PASS with no Critical,
Major, or Minor findings. It adds explicit immutable registration, exact
capability-first matching, deterministic bounded selection, and selected-only
definition/schema loading without granting tool or execution authority. CORE-05
is NOT STARTED; CORE-06 through CORE-11 remain planned and unimplemented. The
aggregate serialized-result byte ceiling remains FUTURE HARDENING /
NON-BLOCKING.

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
- `runtime/` — `actions/`, `approvals/`, `cli/`, `continuation/`, `core/`,
  `evals/`, `execution/`, `executors/`, `git/`, `host/`, `jobs/`, `notifications/`,
  `providers/`, `queue/`, `remote/`, `review/`, `scheduler/`, `storage/`,
  `tests/`, `webhooks/`, and `workers/`. `runtime/state/` is generated, ignored
  operational state, not source architecture.
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
- `docs/` — physically present but empty and without a tracked detailed-doc
  convention, so this audit created no new docs hierarchy.

Agent = WHO. Skill = HOW. Workflow = ORDER. Provider = execution engine.
Execution Result = WHAT HAPPENED. Eval = HOW THE RESULT / BEHAVIOR MET DECLARED
EXPECTATIONS. `shared/projects/` is operational project
state, `shared/knowledge/` is long-term synthesized knowledge, agent
`MEMORY.md` files hold role-specific durable lessons, and `runtime/state/` is
runtime operational state. These stores remain separate.

## Planned Structure

Everything in this section is FUTURE ONLY and does not currently exist unless
explicitly described above.

- Canonical agent target: add Finance & Pricing, Analytics, Content, and Design
  to the current 10 roles, keeping the architecture near 14 durable agents
  rather than creating 20-30 micro-agents.
- Planned skill expansion: Finance/Pricing, Analytics, Content, Design, Sales
  lead generation, SEO, and Reviewer QA/Security skill packs. Skills remain
  separate from agents.
- After Phase 9 observability, evaluate
  `orchestrator/decision-engine/{rules,scoring,classify,rank,confidence,adapters/jev}`.
  JEV would be an optional bounded classification/ranking/filtering/choice and
  confidence-gating adapter—not an agent, human approval authority, or normal
  Claude/Codex-style execution provider.
- Phase 9 may add `observability/{logs,metrics,audit,health}` and
  `apps/control-room/`. Control Room would visualize and operate over canonical
  state, never become a second source of truth.
- Phase 10 may add project/domain packs for Brightshore, YouTube, Instagram,
  Etsy, Travel, and Product Research/Amazon-style research. Packs are not
  canonical agents; they reuse canonical agents, skills, workflows, connectors,
  and the same shared runtime.
- No planned directory above has been created by this documentation task.

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
