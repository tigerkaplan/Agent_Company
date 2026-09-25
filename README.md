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

Git HEAD `b1456f3` contains the committed Phase 8B host-configuration and
persistent-state foundation. The working tree contains the uncommitted Phase 8C
process lifecycle implementation.
Phase 7 is completed and closed, the Social Media checkpoint is completed and committed,
and Phase 8A is PASS / COMPLETED. Phase 8B is COMPLETED / CLOSED after its
successful final independent re-review.
The runtime remains local-first. Phase 8C is COMPLETED / CLOSED after its
successful final independent re-review and adds only a supervisor-neutral
foreground lifecycle. Phase 8D is NEXT / NOT STARTED. Phase 8C added no
systemd unit, Windows Service, Task Scheduler job, automatic restart supervisor
daemon, Docker, VPS, Hermes, public webhook hosting, TLS termination, merge
authority, or deployment authority.
`PROJECT_STATE.md` is the canonical current-status record and `ROADMAP.md` is
the canonical capability roadmap.

The repository now contains:

- `INTENT.md` defines the problem, desired outcome, stakeholders, scope, and current direction.
- `CONSTITUTION.md` defines non-negotiable company rules.
- `AGENTS.md` defines provider-independent operating instructions.
- `CLAUDE.md` gives Claude a provider bootstrap that defers to canonical rules.
- `agents/` and `skills/` define canonical roles and reusable methods.
- `orchestrator/` defines classification, routing, approvals, workflows, and dry-run policy.
- `runtime/` contains local job, worker, provider, review, approval,
  controlled-write, Git, scheduler, remote-command, notification, webhook, and
  Phase 8B host-state coordination.
- `schemas/` contains the persisted runtime contracts.
- `shared/projects/` and `shared/knowledge/` keep operational state separate from durable knowledge.
- `.env.example` lists placeholder environment variable names.
- `.gitignore` protects secrets, runtime state, logs, caches, and local artifacts.

The current runtime does not implement merge, release, deployment, public
webhook hosting, TLS termination, remote task submission, remote scheduler or
filesystem/Git commands, general connector execution, infrastructure
automation, Hermes integration, VPS/Docker hosting, Control Room, or a
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
