# Controlled Git Runtime

Phase 6I adds `GIT_INSPECT`, `GIT_STAGE`, and `GIT_COMMIT`. Phase 6J adds the separate `GIT_REMOTE_INSPECT`, `GIT_PUSH`, and `PULL_REQUEST_CREATE` gates. They are available only through the local Git runtimes; providers, prompts, reviewers, workflows, connector content, and model output receive no Git or forge command authority.

## Lifecycle

```text
completed reviewed CONTROLLED_WRITE
  -> independently loaded mutation evidence
  -> actual repository and working-tree inspection
  -> immutable Git change set and bounded diff
  -> COMMIT_CHANGE_SET human approval
  -> stale-state and local-identity revalidation
  -> exact-path staging
  -> exact-path commit with repository hooks enabled
  -> independently verified commit evidence
  -> immutable push plan and remote-state fingerprint
  -> PUSH_GIT_COMMIT human approval
  -> exact commit-to-branch push and verified remote evidence
  -> immutable pull-request plan and body fingerprint
  -> CREATE_PULL_REQUEST human approval
  -> bounded GitHub CLI creation and verified PR evidence
```

Change sets bind the job, execution, mutation reference, canonical repository root, base HEAD, exact created/modified/deleted files, diff fingerprint, scope fingerprint, unrelated dirty-state fingerprint, bounded commit message, creation time, and status. Commit approval binds the change-set ID, repository, base HEAD, file list, diff fingerprint, and message. Any HEAD, approved-file, unrelated-file, index, or approval change fails closed.

Unrelated unstaged changes are permitted only because the mutation evidence already supplies a narrower exact safe path. They are fingerprinted, never staged, and must remain unchanged through commit. A non-empty index is rejected. The runtime never uses `git add .` or `git add -A`.

Push plans bind one verified commit, repository, remote definition fingerprint, expected remote HEAD, and destination branch. Pull-request plans bind one verified push, repository slug, head/base branches, head commit, title, and body fingerprint. Each action has a separate approval; no earlier approval implies later authority.

## Security Boundary

Git is resolved from the local executable path and invoked with fixed structured argument lists, `shell=False`, bounded output, disabled interactive credential prompts, and timeouts. Push uses one exact `<commit>:refs/heads/<branch>` refspec. Force push, branch deletion, mirror, tags, merge, rebase, amend, hard reset, release, and deployment are not implemented. It does not use `--no-verify`; repository hooks run normally, and hook failure is terminal for that invocation.

Hosted remote URLs must use HTTPS or SSH, identify exactly one owner/repository, contain no embedded credentials or parameters, and have one identical fetch/push definition. Authentication remains delegated to existing Git credential handling. Runtime artifacts persist only a canonical remote display and fingerprint, never tokens or credential-bearing URLs. Local-path remotes are supported for deterministic local verification.

The only forge adapter is a narrow GitHub CLI bridge for inspect and create. It passes PR content through stdin, disables prompts, sanitizes bounded failures, and exposes no merge, update, close, delete, review, release, or repository-settings method. Authentication remains the GitHub CLI's external concern; Agent Company accepts and persists no token.

The Agent Company repository is protected by default. A target must be an existing Git worktree whose top level exactly equals the mutation evidence project root. Only repository-local `user.name` and `user.email` are accepted; the runtime never writes Git identity or configuration.

`--dry-run` persists a preview change set, push plan, or PR plan without approval or mutation. Dry-run plans cannot call commit, push, or PR creation.

## Persistence And Recovery

Artifacts live below the configured Git state root:

- `change-sets/*.change-set.json`
- `diffs/*.diff`
- `commit-evidence/*.commit.json`
- `push-plans/*.push-plan.json`
- `push-evidence/*.push.json`
- `pull-request-plans/*.pr-plan.json`
- `pull-request-bodies/*.body.md`
- `pull-request-evidence/*.pr.json`

Writes are atomic per artifact. Repeated commit, push, and PR-create calls return existing verified evidence. If push succeeds immediately before local linkage, recovery accepts only the exact approved commit at the exact remote branch and matching persisted evidence. PR recovery inspects the exact repository/head/base tuple before any create call. Any different remote movement is stale.

ReviewerRuntime may inspect local Git, push, PR plan, PR body, and remote evidence references. A reviewer decision never grants commit, push, pull-request, or merge authority.
