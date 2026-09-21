# Skill: Handoff

## Purpose

Convert completed work or session context into concise durable project state that another agent or future session can use without reading raw chat history.

## Inputs

- Completed work summary.
- Verified facts and evidence.
- Changed files or affected areas.
- Open tasks, blockers, and unresolved decisions.
- Relevant assumptions or uncertainties.
- Existing project handoff files, when present.

## Outputs

- Updates suitable for `HANDOFF.md`.
- Updates suitable for `TODO.md`.
- Updates suitable for `DECISIONS.md`.
- Updates suitable for `ACTIVE_FILE_MAP.md`.
- A short note of unresolved blockers or decisions that remain.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Do not copy raw chat history.
- Do not invent completed work, approvals, or validation results.
- Preserve unresolved decisions and blockers.
- Separate confirmed facts from assumptions and uncertainty.
- Do not mix temporary operational notes into long-term knowledge.

## Procedure

1. Identify the project and scope of completed work.
2. Extract only durable facts, decisions, open tasks, active files, blockers, and validation evidence.
3. Classify each item as fact, assumption, unresolved decision, blocker, or next action.
4. Prepare concise updates for `HANDOFF.md`, `TODO.md`, `DECISIONS.md`, and `ACTIVE_FILE_MAP.md` as applicable.
5. Preserve unresolved items instead of silently resolving them.
6. Include validation status and any checks that were not run.
7. Ask for approval before modifying target project files when approval is required by project policy or task scope.

## Checks

- No raw chat history is copied.
- Facts, assumptions, blockers, and unresolved decisions are distinguishable.
- The four supported files are updated or explicitly marked not applicable.
- Validation status is honest and traceable.
- The handoff is concise enough for a future agent to read quickly.
