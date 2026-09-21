# Approval Policy

This policy identifies actions that must stop for human approval before execution. It relies on the shared governance in `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Human Approval Required

Human approval is required for:

- destructive file operations;
- production deployment;
- production database changes;
- sending external communications;
- financial transactions;
- irreversible actions.

## Dispatcher Behavior

When approval is required:

1. Stop before the action.
2. State the action, target, risk, and expected effect.
3. Ask for explicit human approval.
4. Continue only after approval is given.

Reviewer may return `HUMAN_APPROVAL` when review identifies an approval gate.
