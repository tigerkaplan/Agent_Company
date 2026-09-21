# Software Agent Guardrails

Follow the shared rules in `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Agent-Specific Boundaries

- Inspect before editing.
- Keep changes scoped to the task and active repository.
- Prefer existing project patterns over new abstractions.
- Use deterministic tests, builds, linters, parsers, and scripts when available.
- Report checks that were not run instead of implying validation.
- Do not overwrite user work or unrelated changes.
- Do not create provider-specific agent files during Phase 1.
- Escalate risky, destructive, deployment, secret, or cross-project actions for human approval.
