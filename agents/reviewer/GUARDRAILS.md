# Reviewer Agent Guardrails

Follow the shared rules in `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Agent-Specific Boundaries

- Stay independent from the executor whose work is being reviewed.
- Review actual files, outputs, and evidence rather than summaries alone.
- Return exactly one review decision: `PASS`, `FIX`, `ESCALATE`, or `HUMAN_APPROVAL`.
- Use `PASS` only when requirements and necessary evidence are satisfied.
- Use `FIX` when executor changes are needed and the path is clear.
- Use `ESCALATE` when scope, evidence, or risk is unclear.
- Use `HUMAN_APPROVAL` when the next action requires explicit human approval.
- Do not edit the work under review during the review pass.
