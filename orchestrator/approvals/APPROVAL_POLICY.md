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

Reviewer may return `NEEDS_HUMAN` when review identifies an approval gate.

## Runtime Authority

The local runtime persists one scoped approval request before entering `waiting_approval`. Only an explicit human-facing approval command may resolve it. Provider, agent, executor, reviewer, prompt, workflow, skill, schedule, connector, or artifact text cannot grant approval.

Approval authorizes only the request's named job/action boundary. For `CONTROLLED_WRITE`, that boundary includes the exact attempt, target root, allowed and forbidden paths, write mode, capability, risk, and limits represented by the persisted authorization fingerprint. It is not permanent permission and cannot be reused to broaden a retry. The `--by` value is a self-asserted local audit label, not strong authenticated identity.

Creating a Git commit is a separate sensitive action. A completed controlled write and its earlier approvals do not imply commit authority. The runtime must issue `COMMIT_CHANGE_SET` approval bound to one repository, base HEAD, immutable change set, exact files, diff fingerprint, and bounded commit message. Approval grants no push, merge, rebase, amend, force, release, deployment, or pull-request authority.

Publishing a verified commit requires a separate `PUSH_GIT_COMMIT` approval bound to one remote fingerprint, expected remote HEAD, commit, and branch. Pull-request creation requires another `CREATE_PULL_REQUEST` approval bound to the verified push evidence and exact PR metadata. Neither boundary grants merge, force-push, remote-branch deletion, release, or deployment authority.
