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
3. Filter to providers configured as eligible for the capability and requested execution mode, then observe local availability.
4. Apply configurable preferences from `../orchestrator/routing/weights.yaml`.
5. Apply fallback and escalation policy without weakening review or approval boundaries.

## Current Providers

- `claude/`: Claude execution-provider adapter.
- `codex/`: Codex execution-provider adapter.

Phase 6E adds minimal local CLI runtime metadata for Claude and Codex. Runtime code observes executable availability, applies canonical eligibility/preferences/fallback, and invokes the selected engine through a provider-neutral adapter. Phase 6H adds mode eligibility: both retain read-only behavior, while only Codex declares a fixed controlled-write invocation inside a runtime-owned staged workspace. Adapters contain no credentials or canonical business logic.

JEV is not a current or planned execution provider in this tree. If evaluated
after Phase 9 observability, it belongs only as an optional bounded adapter
under a future orchestrator decision engine; it grants no execution or human
approval authority.

There are no provider SDK/API clients, authentication setup, Hermes, VPS, connector, or ChatGPT provider. Executable presence is not proof of authentication or remote availability. Automated tests use fakes and do not consume provider usage.
