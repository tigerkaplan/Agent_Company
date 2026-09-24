# Remote Authority Model And Threat Model

## Principles

- Remote control is an input channel, not an authority source.
- Existing Phase 6 runtime boundaries remain authoritative.
- Telegram username, display name, chat title, message text, or possession of a
  job or approval ID is never sufficient authority.
- Human approval must map to a trusted human identity recognized by the
  Approval Runtime.
- Machine-triggered webhook events may create or route work only through
  configured policy; they can never approve human-gated actions.
- Reviewer decisions remain evidence recommendations, not human authorization.

## Identity Model

Remote identity has three layers:

1. Platform identity: stable channel identifier such as Telegram numeric
   `user_id`, platform chat ID where relevant, or webhook source ID.
2. Trust mapping: explicit local allow-list entry mapping the platform identity
   to a canonical human identity or machine source.
3. Runtime actor identity: the identity recorded in the runtime decision or
   audit event.

Telegram usernames and display names are display metadata only. They may appear
in diagnostics, but must not be used as keys for authorization.

Allowed humans must be explicit. A valid remote approval requires:

- authenticated platform delivery;
- allow-listed stable platform user ID;
- mapping to the same human identity used by approval audit records;
- authorization for the specific command class;
- authorization for the target resource, when applicable;
- deterministic binding to the current pending approval or callback token.

Anonymous approval is forbidden. Approval based solely on task content, job
content, approval text, or a copied approval ID is forbidden.

## Authorization Model

Remote authorization is command-class and resource scoped.

The executable permission vocabulary is deliberately limited to
`READ_STATUS`, `READ_JOBS`, `READ_JOB`, `READ_APPROVALS`, `APPROVE`, and
`REJECT`. Enabled identity mapping is necessary but never sufficient; missing
permissions deny, and there is no wildcard. Approval/rejection additionally
requires a configured canonical approval-action scope and either an exact
project ID or explicit permission for an unscoped project.

- Read-only commands may be allowed for trusted operators, but sensitive state
  should still be redacted by default.
- Task creation requires an allow-listed human or explicitly trusted machine
  source and must route through existing orchestrator/runtime creation paths.
- Control commands require a trusted operator and must call existing lifecycle
  or scheduler controls.
- Human authorization commands require a trusted human identity, a concrete
  pending approval, and exact stale-state validation.

Possession of a tokenized callback is not enough on its own. Callback handling
must also confirm the platform actor maps to a human authorized for that
approval.

## Approval Model

Remote approval must preserve Phase 6 guarantees:

- reference exactly one persisted pending approval;
- bind to the current job, execution, review, commit, push, or pull-request
  scope through the existing authorization fingerprint;
- reload canonical state at decision time;
- reject stale, resolved, mismatched, cancelled, failed, or completed targets;
- record the approver identity;
- record source channel and platform event/update evidence;
- record timestamp;
- remain separate from Reviewer decisions.

Free-text messages such as `yes`, `ok`, or `do it` are never sufficient unless
they are deterministically parsed as an explicit approval command bound to the
specific approval being acted on. The preferred interface is:

```text
approve <approval_id> <approval_fingerprint_or_callback_token>
reject <approval_id> <approval_fingerprint_or_callback_token>
```

For button/callback transports, callback tokens must be short-lived references
to persisted pending approvals and current authorization fingerprints. Old
buttons fail closed after the approval is resolved, the fingerprint changes, or
the callback expires.

Phase 7 implementation must extend or wrap Approval Runtime resolution so
remote decisions record authenticated remote actor details. It must not mutate
approval JSON directly.

## Replay And Stale Protection

Remote command handling must persist a command audit record before or as part
of applying a mutating command. That record should use a deterministic command
ID derived from platform event identity, source channel, command type, target,
and canonical arguments. Repeated delivery of the same command must return the
same result or a duplicate/no-op response.

The local file-backed implementation records authorization durably, then marks
the mutation attempted before calling Approval Runtime, and finally records
completion or failure. Failure before the attempted stage prevents mutation.
An interrupted final update leaves a detectable `MUTATION_ATTEMPTED` record.
If canonical approval state changed without its downstream job transition, the
remote record is `RECONCILIATION_REQUIRED`. Replay first reauthorizes the
current identity and scope, then reloads canonical approval truth and either
reconciles the remaining transition idempotently or reports that reconciliation
is still required. Recovery may resolve a still-pending approval only while the
remote interaction remains inside its TTL and permitted clock skew. Once the
canonical approval is already resolved, downstream recovery does not replay or
reverse that human decision merely because the interaction later expires.

Incomplete `AUTHORIZED`, `MUTATION_ATTEMPTED`, and
`RECONCILIATION_REQUIRED` records are retention-protected. Only terminal audit
records may be pruned. If protected evidence consumes configured capacity, new
commands fail closed rather than discarding recovery evidence.

Protection must cover:

- repeated callback delivery;
- duplicate Telegram updates;
- old approval buttons;
- commands replayed after restart;
- stale approval plan;
- previously cancelled job;
- previously completed job.

Use existing lifecycle, approval, Git, scheduler, and artifact idempotency
where possible. Do not build a second job lifecycle.

## Runtime Boundary

RemoteCommandService may call only explicit runtime/orchestrator operations,
for example:

- list/show job state with redaction policy;
- create jobs from validated dispatch input;
- schedule or create work through existing scheduler/job interfaces;
- cancel a job through lifecycle controls;
- request scheduler stop through existing scheduler stop semantics;
- list/show approvals;
- approve/reject through Approval Runtime;
- inspect provider status through existing provider status surfaces.

It must not expose arbitrary Python imports, subprocess execution, shell
arguments, file paths, provider adapter invocation, Git commands, direct JSON
patching, connector writes, or hidden policy overrides.

## Telegram Boundary

Telegram belongs at the transport edge only.

- Telegram adapter validates bot update structure and extracts stable user,
  chat, message, callback, and update IDs.
- Executable commands are accepted only from Telegram `private` chats; missing,
  group, supergroup, and channel context fails closed before the remote core.
- Telegram adapter does not classify tasks, execute providers, resolve
  approvals, or own business logic.
- Telegram command parsing must produce canonical RemoteCommand objects.
- Telegram notification formatting may render approval prompts, job summaries,
  and errors, but those messages are informational unless tied to a secure
  command flow.
- Bot token and chat/user allow-lists must remain outside tracked files.

## Webhook Boundary

Generic webhooks belong in the same remote ingress architecture only as
machine-triggered inbound events.

Inbound webhooks may:

- validate source signatures and schemas;
- normalize event metadata;
- create or route work when configured policy allows it;
- provide idempotency keys for duplicate detection.

Inbound webhooks must not:

- act as human approval;
- gain controlled-write, commit, push, PR, merge, deployment, or shell
  authority;
- bypass downstream connector or runtime approval gates.

Webhook identities map to trusted machine sources, not human approvers.

## Notifications

Outbound notifications may be emitted for:

- approval requested;
- approval accepted or rejected;
- job completed;
- job failed;
- scheduler or runtime error.

Notifications are informational by default. A notification can enable action
only when it embeds or references a secure, expiring command binding for a
specific pending approval or target. Notification formatting must avoid storing
unnecessary private message content.

## Secrets Model

Secrets must never be committed or persisted in job/audit artifacts.

- Telegram bot token: environment variable or ignored local secret file.
- Allowed human IDs/config: ignored local config or environment-derived local
  configuration.
- Webhook signing secrets: environment variable or ignored local secret file.
- Logs and audit records must redact tokens, authorization headers, callback
  secrets, and credential-bearing URLs.

Tracked examples may document variable names with placeholder values only.

## Audit Trail

Remote audit evidence must retain the minimum needed to prove what happened:

- command ID;
- source channel;
- platform update/event/callback ID;
- mapped actor identity;
- platform identity reference;
- command type;
- target resource;
- canonical arguments fingerprint;
- timestamp;
- result;
- approval ID where applicable;
- idempotency status;
- error category for rejection or failure.

Avoid storing raw private chat content unless it is the task payload accepted
for job creation and required by runtime evidence.

## Failure And Abuse Cases

| Case | Expected defense | Residual risk | Fail-safe behavior |
| --- | --- | --- | --- |
| Stranger messages bot | Stable platform ID is not allow-listed; reject before command parsing exposes sensitive state. | Message metadata may be visible to transport logs. | Return generic unauthorized response and audit minimal event. |
| Attacker knows valid job ID | Resource authorization requires trusted identity and command permissions. | Existence probing if errors differ. | Use redacted not-found/unauthorized responses for unauthorized actors. |
| Duplicated Telegram update | Deterministic command ID from update/callback ID and canonical command. | Transport may retry after local crash before response. | Return prior result or duplicate no-op after restart. |
| Old Approve button pressed | Callback token binds approval ID, fingerprint, actor, and expiry; Approval Runtime reloads state. | User confusion if old chats remain visible. | Reject as stale/resolved and send current state summary. |
| Bot token leaked | Token alone cannot map attacker to allow-listed human; rotate token. | Attacker may receive/send bot traffic until revoked. | Disable remote ingress, revoke token, invalidate callback tokens, review audit. |
| Remote user attempts arbitrary shell command | Parser accepts only enumerated commands; service exposes no shell bridge. | Prompt-injected task content may request shell. | Treat as task content only; downstream approval/write gates still apply. |
| Remote user attempts arbitrary file path | Command schema does not accept filesystem mutation paths except validated runtime operations. | Job creation text may mention paths. | Route through normal job policy and controlled-write approval. |
| Approval target changes after notification | Approval fingerprint and callback binding are revalidated at decision time. | User may approve after reading old summary. | Reject stale approval and issue fresh notification if still pending. |
| Scheduler creates approval while user is offline | Pending approval persists; notifications are informational. | Work remains blocked until human acts. | Keep job in `waiting_approval`; no auto-approval or timeout success. |
| Telegram service unavailable | Runtime state does not depend on Telegram delivery. | User may miss notification or command response. | Continue local runtime safely; retry notification only through bounded policy. |
