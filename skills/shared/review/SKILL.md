# Skill: Review

## Purpose

Independently validate completed work for quality, safety, requirement coverage, and evidence before acceptance, escalation, or human approval.

## Inputs

- User request or acceptance criteria.
- Executor output.
- Changed files, artifacts, or findings.
- Tool results and validation evidence.
- Known risks, constraints, and required approvals.

## Outputs

- One decision: `PASS`, `FIX`, `ESCALATE`, or `HUMAN_APPROVAL`.
- Concise rationale.
- Evidence checked.
- Required fixes, escalation reason, or approval question.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay independent from the executor.
- Do not silently repair executor output while reviewing.
- Review actual evidence instead of relying only on summaries.
- Do not use `PASS` when required checks are missing or unresolved risks remain.

## Procedure

1. Identify the requested outcome and acceptance criteria.
2. Inspect the executor output and relevant evidence.
3. Check whether requirements were satisfied.
4. Check quality, safety, source-of-truth discipline, and validation status.
5. Decide whether the result is acceptable, needs fixes, needs escalation, or needs human approval.
6. Return exactly one decision: `PASS`, `FIX`, `ESCALATE`, or `HUMAN_APPROVAL`.
7. Provide concise rationale and next action.

## Checks

- The review decision is exactly one of `PASS`, `FIX`, `ESCALATE`, or `HUMAN_APPROVAL`.
- The reviewer did not silently modify the work under review.
- Evidence checked is named.
- Missing validation is reported.
- Human approval is requested when the next action is risky or irreversible.
