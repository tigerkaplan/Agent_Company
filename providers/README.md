# Execution Providers

`providers/` contains provider adapters for execution engines. Providers execute canonical Agent Company work; they do not define company policy, agent roles, skills, workflows, project state, memory, or knowledge.

## Precedence

Every provider must defer to:

1. `../CONSTITUTION.md`
2. `../AGENTS.md`
3. Canonical definitions in `../agents/`, `../skills/`, `../orchestrator/`, and `../shared/`
4. Provider configuration in this directory

Provider files may declare identity, routing eligibility, availability inputs, and execution constraints. They must not redefine canonical work or claim a preference is an objective model capability.

## Routing Order

1. Classify the task and select the canonical agent, skill, workflow, risk, and approval requirements.
2. Resolve the provider-neutral capability needed for execution.
3. Filter to providers configured as eligible and currently available.
4. Apply configurable preferences from `../orchestrator/routing/weights.yaml`.
5. Apply fallback and escalation policy without weakening review or approval boundaries.

## Current Providers

- `claude/`: Claude execution-provider adapter.
- `codex/`: Codex execution-provider adapter.

Phase 4A contains configuration only. It has no provider API clients, authentication, runtime dispatch, queue, scheduler, Hermes, VPS, connector, or ChatGPT provider.

