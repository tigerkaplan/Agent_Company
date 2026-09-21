# Routing

Routing maps task classes to canonical agents and shared skills. It does not choose a model provider.

## Base Routes

| Task | Agent | Canonical Definition |
| --- | --- | --- |
| Project continuation task | Project Manager Agent | `../../agents/project-manager/ROLE.md` |
| Project audit task | Software Agent | `../../agents/software/ROLE.md` |
| Software task | Software Agent | `../../agents/software/ROLE.md` |
| Research task | Research Agent | `../../agents/research/ROLE.md` |
| Coordination or status task | Project Manager Agent | `../../agents/project-manager/ROLE.md` |
| Important or high-risk output | Reviewer Agent | `../../agents/reviewer/ROLE.md` |

## Shared Skills

Use shared skills from `../../skills/shared/` when the task needs a reusable procedure.

Common pairings:

- Project continuation task: select the agent, skill, and workflow for the next actionable task; use `handoff` when durable project state must be updated.
- Project audit task: `project-audit`, then `review` when required.
- Software implementation task: inspect relevant context, implement, then `review` when required.
- Research task: `research`, then `review` when required.
- Coordination task: `handoff` when durable project state needs updating.
- Review task: `review`.

## Workflow Selection

- `project-continuation`: `../workflows/project-continuation.yaml`.
- `software`: `../workflows/software.yaml`.
- `project-audit`: `../workflows/project-audit.yaml`.
- `research`: `../workflows/research.yaml`.
- `review`: `../workflows/review.yaml`.
- `coordination` and `status`: Project Manager handling as defined in `../../agents/project-manager/ROLE.md`.

## Current Scope Limits

Provider routing and provider weighting are not implemented in the current scope.
