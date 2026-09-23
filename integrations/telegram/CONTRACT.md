# Telegram Connector Contract

## Purpose

Provide the provider-neutral boundary for Telegram command handling and bounded
command-response messages around the canonical remote runtime.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Supported Read Operations

- Receive Telegram Bot API message updates through local long polling.
- Read only the update ID, numeric sender ID, numeric chat ID, message timestamp,
  and explicit command text needed for command processing.
- Execute `/status`, `/jobs`, `/job`, and `/approvals` through the canonical
  remote command service.

## Supported Write/Action Operations

- Send one bounded command-response message to the originating chat.
- Resolve `/approve` or `/reject` only through `RemoteCommandService` and
  `ApprovalRuntime` with the exact current approval binding.
- Proactive messages, message modification, pinning, deletion, reactions, and
  group changes are not implemented.

## Input Contract

- Operation type: inbound event, command, read context, draft, or approved action.
- Chat, user, message, command, or event identifier.
- Message content, command arguments, and relevant metadata.
- Routing context and intended agent or skill.
- Approval evidence for outbound messages or chat-modifying actions.

## Output Contract

- Operation status and timestamp.
- Normalized inbound event or command.
- Routing recommendation or parsed command intent.
- Draft outbound message, when useful.
- Applied action result for approved outbound or chat-modifying actions.
- Errors, missing permissions, invalid commands, or untrusted source warnings.

## Authentication Expectation

The implementation uses a bot token from
`AGENT_COMPANY_TELEGRAM_BOT_TOKEN`. Bot tokens, secrets, and credentials must
not be stored in this contract directory, remote config, runtime state, audit
records, logs, or committed files. Authorization uses only the stable numeric
Telegram user ID mapped through ignored `config/remote.local.json`.

## Approval Boundaries

- The current transport permits only an immediate bounded response to the
  originating command. It does not permit unsolicited or proactive outbound
  communication.
- Message deletion, pinning, reactions, group changes, or user actions require explicit approval.
- Sensitive, financial, legal, personal, reputational, or account-related commands should be escalated.
- Telegram inbound messages are not approval by themselves. Remote approve/reject interactions must map a stable platform user ID to an explicit trusted human identity and must resolve exactly one pending runtime approval through the remote command contract in `../../runtime/remote/`.
- Telegram usernames, display names, chat titles, message text, or possession of job/approval content are not authoritative identity or authorization.

## Runtime Boundary

The first runtime implementation keeps these separate components:

- Telegram transport adapter: validates update structure and extracts stable update, user, chat, message, and callback identifiers.
- Remote command parser: converts trusted Telegram content into canonical remote commands.
- Identity/authentication: maps stable Telegram user IDs to trusted humans through explicit allow-list configuration outside Git.
- Runtime command service: calls existing runtime/orchestrator operations and approval lifecycle surfaces.
- Notification formatter: renders bounded informational messages and secure approval prompts.

The implemented transport uses long polling only. It persists the next update
offset under ignored runtime state after an update and its response have been
safely handled. Telegram `update_id` also supplies deterministic command and
idempotency identity; core replay protection remains authoritative.

Telegram code must not contain business routing, provider execution, approval mutation, file mutation, Git, push, pull-request, scheduler lifecycle, or connector-write authority. It must call the canonical remote runtime boundary instead.

## Error/Fallback Behavior

- Validate Bot API response and update structure before trusting content.
- Unknown or malformed commands receive a bounded safe response.
- Ordinary conversational text never resolves an approval.
- Telegram API failures use bounded errors and bounded retry backoff; an update
  offset is not advanced before its response is acknowledged.

## Data Retention/Privacy Expectations

- Retain only the minimum message content and metadata needed for the approved task.
- Do not store bot tokens, chat dumps, unrelated messages, or unnecessary personal data.
- Keep operational chat state separate from long-term knowledge.
- Remote audit evidence should store update/callback IDs, mapped actor identity, command type, target, result, and approval ID where applicable; avoid storing unnecessary private message content.
- Poll state stores only the next update ID and update timestamp. It does not
  store raw message history or the bot token.

## Intended Agents/Skills

- Communications Agent: `skills/communications/inbox-manager`
- Sales Agent: `skills/sales/speed-to-lead`, `skills/sales/follow-up`
- Operations Agent: `skills/operations/report-builder`
- Project Manager Agent: command routing and coordination
