# Skill: Handoff

## Purpose

Convert completed work or session context into concise durable project state that another agent or future session can use without reading raw chat history.

## Inputs

- Completed work summary.
- Verified facts and evidence.
- Changed files or affected areas.
- Open tasks, blockers, and unresolved decisions.
- Relevant assumptions or uncertainties.
- Existing canonical project-state files, when present.
- Explicit human approvals or confirmations relevant to the session.

## Outputs

- The smallest sufficient set of updates to affected canonical project-state files.
- A concise closeout report identifying updated files, untouched files, unresolved items, and validation status.
- No project-state file changes when the session produced no durable state change.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Do not copy raw chat history.
- Do not invent completed work, approvals, or validation results.
- Preserve confirmed, provisional, inferred, and pending status.
- Never convert pending or provisional state to confirmed without evidence or explicit human confirmation.
- Preserve unresolved decisions, blockers, risks, and approval gates.
- Separate confirmed facts from assumptions and uncertainty.
- Do not mix temporary operational notes into long-term knowledge.
- Do not modify an external source repository as part of closeout unless separately approved.
- Do not update every project-state file by default.

## Project-State File Decision Rules

| File | Update only when |
| --- | --- |
| `HANDOFF.md` | Completed work or the resumable position changed. Keep it concise: what was completed, current focus, where to resume, and unresolved items. |
| `TODO.md` | Actionable work was completed, added, removed, reprioritized, or materially clarified. Do not store status narrative or non-actionable notes. |
| `DECISIONS.md` | A durable decision was made. Record its rationale and evidence or human authority; do not promote discussion or assumptions into decisions. |
| `ACTIVE_FILE_MAP.md` | Relevant active files, authorities, or navigation paths changed. Ordinary edits to an already-listed file do not require a map update. |
| `PROJECT_STATE.md` | The overall project phase, readiness, authority, or other material project state changed. Routine task progress belongs elsewhere. |
| `BLOCKERS.md` | A condition that prevents or stops intended progress was added, changed, or resolved. Do not place possible future harm here. |
| `RISKS.md` | A material uncertainty or possible future harm was added, changed, mitigated, or retired. Do not use risks as blockers unless progress is actually prevented. |
| `APPROVALS.md` | A human explicitly granted, denied, limited, or withdrew approval, or an approval gate materially changed. Preserve the exact scope; absence of refusal is not approval. |
| `ROADMAP.md` | A milestone, milestone status, dependency, or execution sequence materially changed. Routine task completion does not require a roadmap update. |
| `metadata.yaml` | A canonical path, authority designation, project identity, area structure, or other structural metadata changed. Do not store routine session progress in metadata. |

## Procedure

1. Identify the project and scope of completed work.
2. Gather only verified session results, explicit human confirmations or approvals, changed areas, validation evidence, and unresolved items.
3. Compare the verified end state with existing canonical project state. Classify each candidate change as confirmed, provisional, inferred, or pending.
4. Apply the project-state file decision rules and select the smallest affected file set. If no durable state changed, stop without updating project-state files.
5. Prepare concise updates without copying raw chat history. Keep facts, actionable tasks, durable decisions, blockers, risks, and approvals in their proper files.
6. Preserve unresolved and pending items unless evidence or explicit human confirmation changes them.
7. Check cross-file consistency, especially task completion, blocker status, risk status, authority, approval scope, and confirmed/provisional labels. Report conflicts instead of silently rewriting unrelated files.
8. Record validation completed and checks not run in the concise closeout report or affected handoff content.
9. Ask for approval before modifying external source files or taking any action gated by project policy or `../../../CONSTITUTION.md`.

## Checks

- No raw chat history is copied.
- Only files affected by durable state changes are updated.
- Facts, inferences, provisional state, pending state, blockers, risks, approvals, and unresolved decisions remain distinguishable.
- `HANDOFF.md` states what was completed, current focus, where to resume, and unresolved items without becoming a session transcript.
- `TODO.md` contains actionable work only.
- Durable decisions include rationale; approvals retain explicit human scope.
- Blockers and risks remain separate.
- Pending or provisional state is not promoted without evidence or explicit human confirmation.
- External source files are unchanged unless separately approved.
- If no durable state changed, no project-state file is changed.
- Validation status is honest and traceable.
- The closeout is the smallest sufficient durable state another agent needs to resume.
