# Approval Policy

## MEM-02B learning and planning

Only exact canonical local-operator SET_LEARNING_DISPOSITION resolution authorizes
PROMOTE, REVOKE or SUPERSEDE. Complete proposal/evidence/review/preparation/scope/
policy/genesis/index bindings are fingerprinted. Completion, provider text, memory
metadata and callbacks returning True do not approve dispositions. Operator labels
remain self-asserted. Existing approval and job completion rules are unchanged.

Manager must explicitly install the canonical foreground learning interface,
select for an exact project/root/task/workflow/agent/capability/conditions request,
then revalidate immediately before plan acceptance and every dependent reuse.
Changed/uncertain bindings hold affected use for Manager reassessment. Constraints
restrict or inform existing authority; they cannot widen permissions, override
human instructions, change acceptance criteria, cancel jobs, or authorize
execution/writes/Git/retries/continuation/recovery. No automatic promotion, repair,
replay or predecessor reactivation is permitted.

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
