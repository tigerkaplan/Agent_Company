# GitHub Connector Contract

## Purpose

Provide a provider-neutral contract for repository read operations and approval-aware issue, pull request, and repository write actions.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

Phase 6J implements only the narrower runtime-controlled push and pull-request creation subset in `../../runtime/git/`. Merge and all other write operations listed by this general connector contract remain unavailable in Phase 6J.

## Supported Read Operations

- Read approved repository metadata, branches, commits, tags, files, issues, pull requests, checks, and releases.
- Search approved repositories, issues, pull requests, code, and discussions.
- Retrieve diffs, review comments, and CI status when approved.

## Supported Write/Action Operations

- Create or update issues with appropriate approval.
- Comment on issues or pull requests with appropriate approval.
- Create, update, close, merge, label, assign, or review pull requests only with applicable approval.
- Branch, commit, release, workflow, settings, or permission changes only with explicit approval.

## Input Contract

- Operation type: read, search, issue action, pull request action, repo action, or approved write.
- Approved repository owner, repository name, branch, ref, path, issue id, or pull request id.
- Query, content, patch, comment, review decision, or metadata.
- Scope limits such as branch, path, label, date range, or repository set.
- Approval evidence for any write, merge, release, workflow, settings, or permission action.

## Output Contract

- Operation status and timestamp.
- Repository, file, issue, pull request, diff, or check data for read operations.
- Proposed issue, comment, review, or patch when approval is absent.
- Applied action reference for approved writes.
- Errors, missing permissions, conflicts, skipped actions, or validation notes.

## Authentication Expectation

Future implementations must use approved delegated authentication or approved app installation permissions with least privilege. Secrets, tokens, and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Write actions to issues, pull requests, branches, releases, workflows, settings, or permissions require applicable approval.
- Merge, release, deployment, destructive, permission, or repository-history actions require explicit approval.
- Security-sensitive findings or secret exposure must be escalated and handled without leaking secrets.

## Error/Fallback Behavior

- If repository access is unavailable, report the limitation and do not infer repository state.
- If write approval is absent, return a proposed issue, comment, review, or patch instead of applying it.
- If branch state, checks, or permissions conflict, report the conflict and stop the action.

## Data Retention/Privacy Expectations

- Retain only the minimum repository data needed for the approved task.
- Do not store secrets, private repository dumps, unrelated code, or unnecessary personal data.
- Keep operational repository state separate from long-term knowledge.

## Intended Agents/Skills

- Software Agent: implementation, inspection, and repository work
- Reviewer: independent validation of changes and pull requests
- Project Manager Agent: issue and pull request coordination
- Research Agent: source inspection when approved
- Operations Agent: `skills/operations/report-builder` for approved repo status reporting
