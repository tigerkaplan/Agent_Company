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
| Communications task | Communications Agent | `../../agents/communications/ROLE.md` |
| Sales task | Sales Agent | `../../agents/sales/ROLE.md` |
| Marketing task | Marketing Agent | `../../agents/marketing/ROLE.md` |
| Operations task | Operations Agent | `../../agents/operations/ROLE.md` |
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
- Communications task: `inbox-manager` or `meeting-notes`, then `review` when output is important, high-risk, user-facing, or approval-gated.
- Sales task: `speed-to-lead`, `proposal-builder`, or `follow-up`, then `review` when output is important, high-risk, commercially consequential, user-facing, or approval-gated.
- Marketing task: `marketing-monday`, `reputation-review`, or `competitor-analysis`, then `review` when output is important, public-facing, reputationally sensitive, or approval-gated.
- Operations task: `report-builder` or `sop-builder`, then `review` when output is important, high-risk, externally consequential, or approval-gated.
- Coordination task: `handoff` when durable project state needs updating.
- Review task: `review`.

## Workflow Selection

- `project-continuation`: `../workflows/project-continuation.yaml`.
- `software`: `../workflows/software.yaml`.
- `project-audit`: `../workflows/project-audit.yaml`.
- `research`: `../workflows/research.yaml`.
- `knowledge`: `../workflows/knowledge.yaml`.
- `communications`: `../workflows/communications.yaml`.
- `sales`: `../workflows/sales.yaml`.
- `marketing`: `../workflows/marketing.yaml`.
- `operations`: `../workflows/operations.yaml`.
- `review`: `../workflows/review.yaml`.
- `coordination` and `status`: Project Manager handling as defined in `../../agents/project-manager/ROLE.md`.

## Connector Contracts

Connector contracts live under `../../integrations/`. They provide access, data, draft/action boundaries, and future implementation contracts. They do not own business logic, approval decisions, provider routing, or runtime execution.

Inbound receipt of a message or event is never permission for downstream external action. Draft creation is not sending. Calendar commitments are external actions. GitHub writes remain separate from read-only repository access.

## Provider Capability Selection

- Provider routing configuration lives in `providers.yaml`; eligibility, configurable preferences, fallback, and escalation remain separate inputs.
- Architecture requests remain `coordination` tasks, with `architecture` selected explicitly as the provider capability when appropriate.
- `long_context_review` is selected explicitly inside a `review` task when the review requires a large bounded evidence set.
- Knowledge workflow operation selection resolves to `knowledge_query`, `knowledge_ingest`, or `knowledge_lint`.
- Business task classes resolve to their matching canonical capabilities: `communications` to `business_communications`, `sales` to `sales_coordination`, `marketing` to `marketing_analysis`, and `operations` to `operations_coordination`.

## Current Configuration Scope

Provider-native Claude and Codex adaptations and routing configuration exist. Decisions are currently specification-driven: runtime/API execution, connector clients, listener queues, schedulers, and live provider availability checks are not implemented. Review independence and human approval remain governed by `fallback.yaml`, `escalation.yaml`, and `../approvals/APPROVAL_POLICY.md`.
