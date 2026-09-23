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

The committed repository currently ends at the Phase 5 business-agent and connector checkpoint. The local-first Phase 6 runtime is implemented and verified in the working tree, with 282/282 tests passing, 71 Python files compiled, and 13 schemas checked. It is pending checkpoint commit, not verification. Phase 6M remains the highest explicit Phase 6 marker, and no Phase 6N is defined. `PROJECT_STATE.md` is the canonical current-status record and `ROADMAP.md` is the canonical capability roadmap.

The repository now contains:

- `INTENT.md` defines the problem, desired outcome, stakeholders, scope, and current direction.
- `CONSTITUTION.md` defines non-negotiable company rules.
- `AGENTS.md` defines provider-independent operating instructions.
- `CLAUDE.md` gives Claude a provider bootstrap that defers to canonical rules.
- `agents/` and `skills/` define canonical roles and reusable methods.
- `orchestrator/` defines classification, routing, approvals, workflows, and dry-run policy.
- `runtime/` contains local job, worker, provider, review, approval, controlled-write, Git, remote-Git, and scheduler coordination.
- `schemas/` contains the persisted runtime contracts.
- `shared/projects/` and `shared/knowledge/` keep operational state separate from durable knowledge.
- `.env.example` lists placeholder environment variable names.
- `.gitignore` protects secrets, runtime state, logs, caches, and local artifacts.

The current runtime does not implement merge, release, deployment, Telegram command handling, general connector execution, infrastructure automation, or a dedicated observability platform.

## Operating Boundary

Provider execution is explicit and approval boundaries remain authoritative. The local scheduler is sequential and file-backed; it does not install an operating-system service or create approval authority. Connector contracts are not connector implementations.

## Quick Start

Read these files in order:

1. `INTENT.md`
2. `CONSTITUTION.md`
3. `AGENTS.md`
4. `PROJECT_STATE.md`
5. `ROADMAP.md`
6. Any provider-specific bootstrap, such as `CLAUDE.md`
