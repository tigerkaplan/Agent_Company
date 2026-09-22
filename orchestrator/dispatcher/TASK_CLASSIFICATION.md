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
| `coordination` | Status, planning, next-step selection, handoff coordination, or progress tracking. | `project-manager` |
| `review` | Independent validation of completed work or important evidence. | `reviewer` |

Continuation intents include `continue <project>`, `resume <project>`, `continue where we left off`, `where did we leave off?`, and `what should we work on next?`.

## Capability Notes

- Architecture requests classify under `coordination` unless another existing class is a closer fit. Project Manager owns coordination, and the explicit `architecture` capability may replace the class default for provider routing.
- `long_context_review` is a provider capability used within `review` tasks. It is not a separate task class.
- Within `knowledge`, the selected `knowledge-query`, `knowledge-ingest`, or `knowledge-lint` skill determines the matching provider capability.

## Review Triggers

Route to Reviewer when output is important, high-risk, user-facing, security-sensitive, irreversible, or requires independent validation under `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Approval Triggers

Check `../approvals/APPROVAL_POLICY.md` before any risky or irreversible action.
