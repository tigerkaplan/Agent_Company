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

## Phase 1 Scope

Phase 1 initializes the company core with minimal provider-neutral foundations:

- `INTENT.md` defines the problem, desired outcome, stakeholders, scope, and open questions.
- `CONSTITUTION.md` defines non-negotiable company rules.
- `AGENTS.md` defines provider-independent operating instructions.
- `CLAUDE.md` gives Claude a minimal bootstrap that defers to canonical rules.
- `agents/` defines minimal canonical agent roles, guardrails, and memory files.
- `skills/` defines minimal shared reusable skills.
- `orchestrator/` defines minimal task classification, routing, approvals, workflows, and dry-run support.
- `.env.example` lists placeholder environment variable names.
- `.gitignore` protects secrets, runtime state, logs, caches, and local artifacts.

Phase 1 does not build provider routing, provider weighting, a runtime workflow engine, scheduling layer, connectors, integrations, queue, workers, LLM Wiki, or deployment system.

## Future Phases

Later phases may add:

- LLM Wiki support.
- INGEST, QUERY, and LINT commands.
- Obsidian integration.
- Hermes integration.
- Scheduling.
- Telegram operations.
- VPS deployment.
- Claude, Codex, and ChatGPT routing.
- Business operations skills and connectors.
- Project onboarding that does not require rewriting existing projects.

## Quick Start

Placeholder for Phase 2.

For now, read these files in order:

1. `INTENT.md`
2. `CONSTITUTION.md`
3. `AGENTS.md`
4. Any provider-specific bootstrap, such as `CLAUDE.md`
