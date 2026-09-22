# Codex Adapter Layer

`.agents/` exposes canonical Agent Company skills and specialist roles in Codex-native locations. It is non-canonical and contains no project state, long-term knowledge, or agent memory.

## Authority

The root `../AGENTS.md` remains the global Codex instruction source below `../CONSTITUTION.md`. Files in this directory add provider-specific loading guidance only and must defer to canonical definitions in `../agents/`, `../skills/`, `../orchestrator/`, and `../shared/`.

## Use

- Root Codex handles Project Manager coordination by loading `../agents/project-manager/ROLE.md` and `../agents/project-manager/GUARDRAILS.md` when canonical routing selects that role.
- `skills/` exposes thin adapters to canonical shared skills.
- `subagents/` scopes specialist Codex execution without redefining the specialist role.
- Provider choice and independent review follow `../orchestrator/routing/providers.yaml`, `../orchestrator/routing/fallback.yaml`, and `../orchestrator/routing/escalation.yaml`.

Codex must resolve and read the linked canonical files before relying on an adapter.
