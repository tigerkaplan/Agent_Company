# Telegram Connector

This directory contains the first live Phase 7 Telegram transport and its
canonical connector contract. The transport is a thin adapter around
`RemoteCommandService`; it does not contain business routing, approval
mutation, provider execution, scheduler mutation, or arbitrary command
execution.

## Implemented

- Local Telegram Bot API long polling through `getUpdates`.
- Command-response messages through `sendMessage`.
- Proactive bounded `APPROVAL_REQUESTED`, `APPROVAL_APPROVED`,
  `APPROVAL_REJECTED`, `JOB_COMPLETED`, `JOB_FAILED`, and `RUNTIME_ERROR`
  messages through the same `sendMessage` client.
- Stable numeric Telegram user ID mapping through ignored
  `../../config/remote.local.json`.
- Explicit parsing for `/status`, `/jobs`, `/job`, `/approvals`, `/approve`,
  `/reject`, and `/help`.
- Private-chat-only command handling; group, supergroup, channel, missing, or
  ambiguous chat contexts fail closed before the remote core.
- Canonical command execution only through `RemoteCommandService`.
- Persistent restart-safe polling offset under ignored
  `../../runtime/state/remote/telegram/`.
- Standard-library HTTPS client with fixed Telegram API origin, bounded
  timeouts, bounded responses, and safe errors.

## Token And Identity

Set the bot token in the process environment only:

```powershell
$env:AGENT_COMPANY_TELEGRAM_BOT_TOKEN = '<token-from-BotFather>'
```

Copy `../../config/remote.example.json` to the ignored
`../../config/remote.local.json` and map the trusted numeric Telegram user ID:

```json
{
  "schema_version": 1,
  "approval_ttl_seconds": 600,
  "allowed_clock_skew_seconds": 30,
  "max_audit_records": 1000,
  "notification_targets": ["local-owner"],
  "allowed_users": [
    {
      "channel": "telegram",
      "platform_user_id": "123456789",
      "mapped_human_identity": "local-owner",
      "enabled": true,
      "permissions": ["READ_STATUS"],
      "approval_scope": {
        "allowed_actions": [],
        "project_ids": [],
        "allow_unscoped_projects": false
      }
    }
  ]
}
```

Usernames, display names, chat names, and message text do not authorize a
command. The token is never read from this config and is not written to state,
audit records, or logs.

`enabled: true` does not grant commands by itself. Add only the exact permission
strings required by that human. `APPROVE` or `REJECT` also requires an explicit
`approval_scope`; an empty or missing scope denies every approval. Copy the
tracked example and replace placeholders only in ignored local configuration.

`notification_targets` contains mapped human identities, not Telegram names or
IDs. Each target resolves only to an enabled `telegram` entry in
`allowed_users`. A missing or disabled mapping receives nothing.

## Local Run

Process one update batch:

```powershell
python -m runtime.cli telegram poll-once
```

Run long polling until `Ctrl+C`:

```powershell
python -m runtime.cli telegram run
```

Enable proactive notifications for a runtime or scheduler command by placing
the global flag before the resource:

```powershell
python -m runtime.cli --enable-notifications scheduler run
```

Preview a fixed harmless test without contacting Telegram or writing delivery
state:

```powershell
python -m runtime.cli notification test --type JOB_COMPLETED --target-human local-owner --test-id phase7-smoke
```

Add `--send` only for an intentional live test. A live send still requires the
environment token and an enabled numeric Telegram mapping.

The first manual smoke test must use `/status`. Confirm the mapped identity and
read-only response before testing `/approve` or `/reject`.

## Not Implemented

- Telegram webhook mode, public webhook hosting, or TLS termination. The
  separate generic webhook runtime is localhost-only machine ingress.
- Remote task creation, cancellation, or scheduler mutation.
- Controlled writes, filesystem or shell commands, Git actions, merge, or
  deployment.
- OS service installation, Docker, VPS, or Hermes deployment.

See `CONTRACT.md` for the provider-neutral boundary.
