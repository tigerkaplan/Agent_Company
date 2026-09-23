# Telegram Connector

This directory contains the first live Phase 7 Telegram transport and its
canonical connector contract. The transport is a thin adapter around
`RemoteCommandService`; it does not contain business routing, approval
mutation, provider execution, scheduler mutation, or arbitrary command
execution.

## Implemented

- Local Telegram Bot API long polling through `getUpdates`.
- Command-response messages through `sendMessage`.
- Stable numeric Telegram user ID mapping through ignored
  `../../config/remote.local.json`.
- Explicit parsing for `/status`, `/jobs`, `/job`, `/approvals`, `/approve`,
  `/reject`, and `/help`.
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
  "max_audit_records": 1000,
  "allowed_users": [
    {
      "channel": "telegram",
      "platform_user_id": "123456789",
      "mapped_human_identity": "local-owner",
      "enabled": true
    }
  ]
}
```

Usernames, display names, chat names, and message text do not authorize a
command. The token is never read from this config and is not written to state,
audit records, or logs.

## Local Run

Process one update batch:

```powershell
python -m runtime.cli telegram poll-once
```

Run long polling until `Ctrl+C`:

```powershell
python -m runtime.cli telegram run
```

The first manual smoke test must use `/status`. Confirm the mapped identity and
read-only response before testing `/approve` or `/reject`.

## Not Implemented

- Proactive approval, completion, or failure notifications.
- Telegram webhook mode or a generic webhook runtime.
- Remote task creation, cancellation, or scheduler mutation.
- Controlled writes, filesystem or shell commands, Git actions, merge, or
  deployment.
- OS service installation, Docker, VPS, or Hermes deployment.

See `CONTRACT.md` for the provider-neutral boundary.
