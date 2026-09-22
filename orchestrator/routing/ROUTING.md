# Routing

Routing first maps task classes to canonical agents, shared skills, and workflows. It then uses provider-neutral capability, eligibility, preference, fallback, and escalation configuration to specify a provider route.

## Base Routes

| Task | Agent | Canonical Definition |
| --- | --- | --- |
| Project continuation task | Project Manager Agent | `../../agents/project-manager/ROLE.md` |
| Project audit task | Software Agent | `../../agents/software/ROLE.md` |
| Software task | Software Agent | `../../agents/software/ROLE.md` |
| Research task | Research Agent | `../../agents/research/ROLE.md` |
| Knowledge task | Knowledge Manager Agent | `../../agents/knowledge-manager/ROLE.md` |
| Coordination or status task | Project Manager Agent | `../../agents/project-manager/ROLE.md` |
| Important or high-risk output | Reviewer Agent | `../../agents/reviewer/ROLE.md` |

## Shared Skills

Use shared skills from `../../skills/shared/` when the task needs a reusable procedure.

Common pairings:

- Project continuation task: select the agent, skill, and workflow for the next actionable task; use `handoff` when durable project state must be updated.
- Project audit task: `project-audit`, then `review` when required.
- Software implementation task: inspect relevant context, implement, then `review` when required.
- Research task: `research`, then `review` when required.
- Knowledge task: `knowledge-query`, `knowledge-ingest`, or `knowledge-lint` as selected by the requested operation.
- Coordination task: `handoff` when durable project state needs updating.
- Review task: `review`.

## Workflow Selection

- `project-continuation`: `../workflows/project-continuation.yaml`.
- `software`: `../workflows/software.yaml`.
- `project-audit`: `../workflows/project-audit.yaml`.
- `research`: `../workflows/research.yaml`.
- `knowledge`: `../workflows/knowledge.yaml`.
- `review`: `../workflows/review.yaml`.
- `coordination` and `status`: Project Manager handling as defined in `../../agents/project-manager/ROLE.md`.

## Provider Capability Selection

- Provider routing configuration lives in `providers.yaml`; eligibility, configurable preferences, fallback, and escalation remain separate inputs.
- Architecture requests remain `coordination` tasks, with `architecture` selected explicitly as the provider capability when appropriate.
- `long_context_review` is selected explicitly inside a `review` task when the review requires a large bounded evidence set.
- Knowledge workflow operation selection resolves to `knowledge_query`, `knowledge_ingest`, or `knowledge_lint`.

## Current Configuration Scope

Provider-native Claude and Codex adaptations and routing configuration exist. Decisions are currently specification-driven: runtime/API execution and live provider availability checks are not implemented. Review independence and human approval remain governed by `fallback.yaml`, `escalation.yaml`, and `../approvals/APPROVAL_POLICY.md`.
