# Remote Command Contract

## Canonical Shape

Every accepted remote command must normalize to this contract before touching
runtime state:

```text
RemoteCommand {
  schema_version: 1,
  command_id: string,
  source_channel: "telegram" | "webhook" | "local_test" | future_channel,
  source_event_id: string,
  received_at: timestamp,
  actor: RemoteActor,
  command_class: string,
  command_name: string,
  target: RemoteTarget | null,
  arguments: object,
  confirmation: ConfirmationBinding | null,
  idempotency_key: string,
  audit_redaction: object
}
```

`command_id` and `idempotency_key` must be deterministic for platform events
that may be delivered more than once. Free text is retained only when required
as accepted task input.

```text
RemoteActor {
  actor_kind: "trusted_human" | "trusted_machine",
  human_id: string | null,
  machine_source_id: string | null,
  platform: string,
  platform_user_id: string | null,
  platform_chat_id: string | null,
  display_label: string | null
}
```

Display labels are never authorization keys.

```text
ConfirmationBinding {
  approval_id: string | null,
  authorization_fingerprint: string | null,
  callback_token_id: string | null,
  expires_at: timestamp | null
}
```

## Command Classes

The initial contract defines command classes before enabling every command.

| Class | Commands | Authentication | Authorization | Risk | Mutates runtime state | Additional confirmation | Audit evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Read-only | `status`, `jobs`, `job show`, `scheduler status`, `approvals list`, `provider status` | Authenticated platform event from allow-listed human. | Read permission for requested runtime scope. | Low to medium depending on redaction. | No. | No. | Command ID, actor, source event, target, redaction policy, result status. |
| Task creation | `submit task`, `create work`, `schedule work` | Allow-listed human, or signed trusted machine webhook for configured routes. | Create/schedule permission for project or runtime scope. | Medium or approval_required depending on requested execution mode and downstream effects. | Yes: creates job/schedule or dispatch input. | Required for controlled-write, external, destructive, or ambiguous task creation through existing approval policy; not satisfied by remote submit alone. | Command ID, actor/source, normalized task fingerprint, created job/schedule refs, approval requirement. |
| Control | `cancel job`, `stop scheduler`, `stop run loop` | Allow-listed human only for operator controls. | Control permission for target job/scheduler state. | Medium to high; may interrupt work. | Yes. | Required when target is running, high-risk, or cancellation would discard irreversible work evidence. | Command ID, actor, target state before/after, lifecycle result, reason. |
| Human authorization | `approve`, `reject` | Allow-listed stable platform user mapped to trusted human. | Approval permission for exact pending approval and bound resource. | Approval_required. | Yes: resolves one pending approval through Approval Runtime. | Yes: explicit approval/rejection command or valid callback binding to current approval/fingerprint. | Command ID, actor, approval ID, authorization fingerprint, source channel, platform event, decision, timestamp, result. |

No command class grants arbitrary file, shell, provider, Git, connector-write,
deployment, merge, force-push, or credential authority.

## Supported Initial Command Names

Read-only candidates:

- `status`
- `jobs`
- `job show <job_id>`
- `scheduler status`
- `approvals list`
- `provider status`

Task creation candidates:

- `submit task <task_text>`
- `create work <validated_payload>`
- `schedule work <validated_payload>`

Control candidates:

- `cancel job <job_id>`
- `stop scheduler`
- `stop run loop`

Human authorization candidates:

- `approve <approval_id> <binding>`
- `reject <approval_id> <binding>`

The first implementation may enable only a subset. Disabled commands must
return `unsupported_command` without side effects.

## Validation Rules

Remote command parsing must:

- reject unknown commands;
- reject command aliases that imply broad authority, such as arbitrary shell or
  file operations;
- require explicit target IDs for target-specific commands;
- normalize timestamps to UTC;
- bound input length;
- fingerprint accepted task payloads;
- redact private content from generic audit records;
- return structured errors.

Authorization must happen after authentication and before runtime mutation.

## Approval Commands

`approve` and `reject` must call the existing Approval Runtime resolution path
or a Phase 7 extension of it. They must not edit approval JSON directly.

At decision time the service must reload:

- approval record;
- target job and lifecycle state;
- bound execution/review evidence where applicable;
- bound commit/push/PR plan where applicable.

The decision is valid only when the approval remains pending and its persisted
scope still matches the current authorization fingerprint.

## Idempotency

Every mutating command must be idempotent across duplicate delivery and restart.

- Duplicate read-only commands may be served again.
- Duplicate task creation with the same idempotency key must return the same
  created job/schedule ref or duplicate status.
- Duplicate cancellation of an already-cancelled target should return the
  canonical terminal state.
- Duplicate approval/rejection must return the previously recorded decision when
  it is exactly the same actor, command, and target; contradictory duplicate
  decisions fail closed.

Existing runtime idempotency remains authoritative for commit, push, PR, and
scheduler operations.

## Result Contract

Remote command results should normalize to:

```text
RemoteCommandResult {
  command_id: string,
  status: "accepted" | "rejected" | "duplicate" | "unsupported" | "failed",
  result_code: string,
  target: RemoteTarget | null,
  runtime_refs: object,
  message_summary: string,
  audit_ref: string | null
}
```

Result summaries should be safe to send over the source channel and should not
include secrets, tokens, raw credential-bearing URLs, or unnecessary private
message content.
