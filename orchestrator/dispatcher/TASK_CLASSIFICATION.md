# Task Classification

Use the smallest classification that fits the user's request.

## Classes

| Class | Description | Initial Route |
| --- | --- | --- |
| `project-audit` | Existing-project inspection, repository status, documentation, tests/build configuration, blockers, or risks without changes. | `software` |
| `software` | Implementation, debugging, tests, builds, or code changes. | `software` |
| `research` | Evidence collection, source verification, option comparison, or synthesis. | `research` |
| `coordination` | Status, planning, next-step selection, handoff coordination, or progress tracking. | `project-manager` |
| `review` | Independent validation of completed work or important evidence. | `reviewer` |

## Review Triggers

Route to Reviewer when output is important, high-risk, user-facing, security-sensitive, irreversible, or requires independent validation under `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Approval Triggers

Check `../approvals/APPROVAL_POLICY.md` before any risky or irreversible action.
