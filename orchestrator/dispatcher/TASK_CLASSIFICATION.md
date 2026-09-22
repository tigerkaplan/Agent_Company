# Task Classification

Use the smallest classification that fits the user's request.

## Classes

| Class | Description | Initial Route |
| --- | --- | --- |
| `project-continuation` | Resume a named or active project from canonical project state and select the next actionable task. | `project-manager` |
| `project-audit` | Existing-project inspection, repository status, documentation, tests/build configuration, blockers, or risks without changes. | `software` |
| `software` | Implementation, debugging, tests, builds, or code changes. | `software` |
| `research` | Evidence collection, source verification, option comparison, or synthesis. | `research` |
| `knowledge` | Query, ingest, or lint canonical long-term knowledge. | `knowledge-manager` |
| `communications` | Inbox/message triage, communication classification, meeting notes, summaries, or response drafts. | `communications` |
| `sales` | Lead handling, qualification, proposal drafting, sales follow-up planning, or sales response drafts. | `sales` |
| `marketing` | Campaign analysis, marketing briefs, audience/customer signal analysis, reputation review, or competitor comparison. | `marketing` |
| `operations` | Operational reports, SOPs, recurring checks, process coordination, or internal operational summaries. | `operations` |
| `coordination` | Status, planning, next-step selection, handoff coordination, or progress tracking. | `project-manager` |
| `review` | Independent validation of completed work or important evidence. | `reviewer` |

Continuation intents include `continue <project>`, `resume <project>`, `continue where we left off`, `where did we leave off?`, and `what should we work on next?`.

## Business Class Precedence

### Sales And Communications

- Sales owns lead qualification, opportunity-specific communication, proposals, commercial follow-up, and other work whose primary intent is sales.
- Communications owns generic inbox triage, classification, summarization, and wording or draft support when no domain-specific intent is primary.
- When a message represents a sales opportunity, route it to Sales as the primary agent even if Communications assists with wording or transport.

### Marketing And Sales

- Marketing owns aggregate audience or customer signals, campaign analysis, competitor analysis, reputation themes, and market-level analysis.
- Sales owns specific leads, accounts, opportunities, proposals, quote context, qualification, and commercial follow-up.
- Route aggregate or many-customer analysis to Marketing. Route an individual opportunity or commercial interaction to Sales.
- Aggregate lead analysis defaults to Marketing unless the task is specifically pipeline or sales-operations reporting, which remains Sales work.

### Operations Boundary

- Operations owns process coordination, SOPs, recurring checks, internal operational reporting, and cross-process coordination.
- Operations must not absorb domain-specific decisions owned by Sales, Marketing, Communications, Software, Research, or another canonical agent.
- When operational work exposes a domain decision, route that decision to the appropriate domain agent and keep Operations responsible only for the process coordination or reporting layer.

## Capability Notes

- Architecture requests classify under `coordination` unless another existing class is a closer fit. Project Manager owns coordination, and the explicit `architecture` capability may replace the class default for provider routing.
- `long_context_review` is a provider capability used within `review` tasks. It is not a separate task class.
- Within `knowledge`, the selected `knowledge-query`, `knowledge-ingest`, or `knowledge-lint` skill determines the matching provider capability.
- Within business classes, the selected workflow determines the matching business skill and connector contracts. Connectors provide access, data, or approved actions; they do not own business logic.

## Review Triggers

Route to Reviewer when output is important, high-risk, user-facing, security-sensitive, irreversible, or requires independent validation under `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Approval Triggers

Check `../approvals/APPROVAL_POLICY.md` before any risky or irreversible action.

Inbound receipt of a message or event is not permission for downstream external action. Draft creation is not sending, calendar commitments are external actions, and GitHub write actions remain separate from read-only repository access.
