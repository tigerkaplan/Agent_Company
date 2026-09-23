# Skill: Review

## Purpose

Independently validate completed work for quality, safety, requirement coverage, and evidence before acceptance, escalation, or human approval.

## Inputs

- User request or acceptance criteria.
- Executor output.
- Changed files, artifacts, or findings.
- Runtime-observed mutation evidence for controlled-write executions, including scope violations and target fingerprints.
- Tool results and validation evidence.
- Known risks, constraints, and required approvals.

## Outputs

- One decision: `PASS`, `FAIL`, `RETRY`, or `NEEDS_HUMAN`.
- Concise rationale.
- Evidence checked.
- Required fixes, escalation reason, or approval question.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay independent from the executor.
- Do not silently repair executor output while reviewing.
- Review actual evidence instead of relying only on summaries.
- Do not use `PASS` when required checks are missing or unresolved risks remain.
- Do not use `PASS` for controlled writes when mutation evidence is missing, unapplied, out of scope, or conflicts with the target state.

## Procedure

1. Identify the requested outcome and acceptance criteria.
2. Inspect the executor output and relevant evidence.
3. Check whether requirements were satisfied.
4. Check quality, safety, source-of-truth discipline, and validation status.
5. Decide whether the result passes, fails, justifies a bounded retry, or needs a human decision.
6. Return exactly one decision: `PASS`, `FAIL`, `RETRY`, or `NEEDS_HUMAN`.
7. Provide concise rationale and next action.

## Checks

- The review decision is exactly one of `PASS`, `FAIL`, `RETRY`, or `NEEDS_HUMAN`.
- The reviewer did not silently modify the work under review.
- Evidence checked is named.
- Missing validation is reported.
- Human approval is requested when the next action is risky or irreversible.
