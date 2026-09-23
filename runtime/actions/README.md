# Controlled Write Runtime

Phase 6H introduces two explicit execution modes: `READ_ONLY` and `CONTROLLED_WRITE`. The default remains `READ_ONLY`. Provider identity, agent selection, workflow text, task wording, and provider output never imply write authority.

Every controlled-write job carries an exact `execution_scope` with an absolute target root, normalized relative allow/deny paths, create/modify/delete policy, changed-file and artifact limits, and explicit test/Git-read flags. It must receive a scoped `EXECUTE_JOB` approval and independent review. The approval stores the mode, scope, and a SHA-256 authorization fingerprint over the job, attempt, project, capability, risk, mode, and scope. A changed or retried boundary needs fresh approval.

`dry_run` is canonical job state, defaults to `false`, is mirrored into controlled-write scope, and is included in the authorization boundary when enabled. A dry-run approval cannot authorize a later non-dry-run attempt. Retry preserves `dry_run` and controlled-write retries require a fresh scoped approval.

## Staged Mutation

The provider does not write directly to the target repository. The runtime copies only authorized paths into an intentionally non-Git temporary workspace, invokes an eligible adapter there, fingerprints pre/post file state, computes changed/created/deleted files and a bounded diff, validates every observed path, and only then applies validated changes to the target. Codex receives `--skip-git-repo-check` and the fixed native Windows `elevated` sandbox implementation override only through this validated controlled-write workspace path; its process temp variables also resolve to the staged workspace. READ_ONLY behavior is unchanged. Target fingerprints are checked again before apply so stale concurrent changes fail with `validation_failed`.

Requested and effective Codex sandbox modes are separate evidence fields. The parser accepts only `read-only`, `workspace-write`, or `danger-full-access`, optionally followed by bounded bracketed startup diagnostics. Those diagnostics do not alter `ExecutionScope`. Every Codex execution requires an exact requested/effective mode match: a different mode fails as `provider_sandbox_mismatch`, while absent or malformed startup metadata fails as `provider_sandbox_unverified`. Controlled-write failures are non-retryable and preserve staged evidence without calling `_apply()`.

Writes use temporary files plus `os.replace`. A multi-file apply is not a filesystem transaction; the runtime retains changed-file backups in memory and attempts rollback if an apply step fails. The runtime observes every staged change and rechecks each changed target before apply. Normal non-dry-run execution does not continuously snapshot unrelated files in the real target, so protection against a provider process writing outside its staged working directory depends on the configured Codex `workspace-write` sandbox. This is a single-process local control, not an OS/container security boundary.

In dry-run, the provider may still produce changes in the staged workspace, but the runtime never calls the target apply path. It records those files as proposed rather than applied and compares deterministic whole-target fingerprints from before and after staged execution. Successful preview evidence therefore requires bounded proposed changes, no scope violation, an empty applied-file list, and an unchanged target. Reviewer verification accepts this preview contract without claiming that a mutation was applied.

## Protected Paths

Git internals, environment/secret material, credential directories, and runtime evidence are always protected. Agent Company governance, routing, provider registry, and approval policy are protected unless the exact approved scope opts in, targets this repository, uses `software_implementation`, and carries `approval_required` risk. Scope violations never become successful executions and reviewer text cannot override them.

The runtime does not execute provider-generated commands. `allow_tests` and `allow_git_reads` are recorded policy fields for future structured allowlisted validation; Phase 6H does not turn either flag into arbitrary shell execution. Codex uses a fixed argument array and `shell=False`. Claude controlled-write support is not declared.

Mutation JSON and bounded diffs live under ignored `state/executions/mutations/`. Job state contains only compact artifact references.
