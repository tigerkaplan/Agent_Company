# Telegram Connector Contract

## Purpose

Provide a provider-neutral contract for inbound command or event handling and approval-aware outbound messaging through Telegram-like channels.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Supported Read Operations

- Receive approved inbound command or event payloads from chats, users, or groups.
- Read approved message metadata and message content needed for routing or response drafting.
- Retrieve limited conversation context when approved and available.

## Supported Write/Action Operations

- Prepare outbound message drafts.
- Send outbound messages only with applicable approval.
- Modify, pin, delete, or react to messages only if a future implementation has explicit approval for that action.

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

Future implementations must use approved bot or delegated authentication. Bot tokens, secrets, and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Outbound messages are external communication and must remain approval-gated unless a specific future policy allows otherwise.
- Message deletion, pinning, reactions, group changes, or user actions require explicit approval.
- Sensitive, financial, legal, personal, reputational, or account-related commands should be escalated.

## Error/Fallback Behavior

- Validate payload source before trusting inbound content.
- If source validation fails, reject or quarantine the event and report the reason.
- If outbound approval is absent, return a draft response instead of sending.
- If command intent is unclear, ask for clarification or route to human review.

## Data Retention/Privacy Expectations

- Retain only the minimum message content and metadata needed for the approved task.
- Do not store bot tokens, chat dumps, unrelated messages, or unnecessary personal data.
- Keep operational chat state separate from long-term knowledge.

## Intended Agents/Skills

- Communications Agent: `skills/communications/inbox-manager`
- Sales Agent: `skills/sales/speed-to-lead`, `skills/sales/follow-up`
- Operations Agent: `skills/operations/report-builder`
- Project Manager Agent: command routing and coordination
