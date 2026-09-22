# Claude Adapter Layer

`.claude/` exposes Agent Company roles and skills in Claude-native locations. It is an execution adapter, not a source of truth.

## Authority

Claude must follow, in order, `../CONSTITUTION.md`, `../AGENTS.md`, and the canonical definitions selected from `../agents/`, `../skills/`, `../orchestrator/`, and `../shared/`. `../CLAUDE.md` is the root Claude bootstrap. Files here may explain how Claude loads a selected definition, but they cannot redefine it.

## Use

1. Classify and route the task using the canonical orchestrator.
2. Open the selected adapter and its linked canonical role or skill.
3. Load only the project state or knowledge required by the selected workflow.
4. Execute through Claude tools and report evidence, uncertainty, and unavailable checks.

Provider selection and cross-provider review follow `../orchestrator/routing/providers.yaml`, `../orchestrator/routing/fallback.yaml`, and `../orchestrator/routing/escalation.yaml`. These adapters do not store project state, long-term knowledge, or agent memory.
