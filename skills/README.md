# Canonical Skills

This directory contains provider-neutral shared skills for the Agent Company core. A skill is a reusable SOP or capability that an agent can apply across tasks, projects, and providers.

Agents define who performs work. Skills define how reusable work is performed. Prompts define task-specific instructions. Workflows define execution order.

An agent may use multiple skills during one task. For example, a Software Agent may use `project-audit`, then `review`, then `handoff`; a Research Agent may use `research`, then hand the findings to Reviewer through `review`.

## Source Of Truth

Canonical skills live here first. Future Claude, Codex, ChatGPT, or other provider-specific skill adaptations must defer to:

1. `../CONSTITUTION.md`
2. `../AGENTS.md`
3. This `skills/` directory

Provider-specific adaptations may translate format or tool syntax, but they must not redefine the canonical purpose, constraints, or checks.

## Shared Skill Catalogue

Phase 1 core skills:

- `skill-creator`
- `handoff`
- `project-audit`
- `research`
- `review`

Phase 3B knowledge skills:

- `knowledge-ingest`: integrate sources into source cards and synthesized wiki pages.
- `knowledge-query`: retrieve minimum relevant indexed knowledge without silently mutating it.
- `knowledge-lint`: report knowledge quality, provenance, navigation, duplication, and gap findings.

Do not create provider-specific copies unless a later phase requires an adaptation.
