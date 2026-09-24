# Canonical Agents

This directory contains provider-neutral canonical agent definitions for the Agent Company core. These files define the durable roles that future Claude, Codex, ChatGPT, or other provider-specific agent files must derive from.

Provider-specific agents are adapters. They may translate these definitions into a provider's expected format, but they must not redefine the source-of-truth role, scope, or boundaries.

## Source Of Truth

Canonical agent definitions live here first. When provider-specific agent files are created later, they must defer to:

1. `../CONSTITUTION.md`
2. `../AGENTS.md`
3. This `agents/` directory

If a provider-specific agent conflicts with these files, the canonical definition wins and the conflict should be reported.

## Canonical Roles

- Project Manager
- Software Agent
- Research Agent
- Reviewer
- Knowledge Manager
- Sales Agent
- Marketing Agent
- Social Media Agent
- Operations Agent
- Communications Agent

## File Roles

Each agent directory contains:

- `ROLE.md`: purpose, scope, responsibilities, and what the agent must not own.
- `GUARDRAILS.md`: agent-specific execution boundaries that reference shared rules instead of duplicating them.
- `MEMORY.md`: agent-specific learned lessons, recurring mistakes, successful patterns, and operational notes.

`MEMORY.md` is the English canonical equivalent of the reference system's `defter.md` concept. It is for durable agent learning only. It must not contain project operational state, raw chat history, temporary run logs, or unreviewed context dumps.

## Agents, Skills, Prompts, And Workflows

Agents define who performs work.

Skills define how reusable work is performed.

Prompts define task-specific instructions.

Workflows define execution order.

These boundaries should stay separate so the company can route work across providers without turning one model, prompt, or chat session into the whole system.
