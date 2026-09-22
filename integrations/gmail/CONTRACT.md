# Gmail Connector Contract

## Purpose

Provide a provider-neutral contract for reading, searching, summarizing, and drafting email replies while keeping email sending approval-gated.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Supported Read Operations

- Read approved message metadata and message bodies.
- Search messages by approved query, sender, recipient, date range, labels, or thread context.
- Retrieve thread context needed for triage, drafting, or reporting.

## Supported Write/Action Operations

- Create draft replies.
- Create draft new messages.
- Apply local draft metadata for review, when supported by a future implementation.
- Send, archive, delete, label, move, or mark messages only if a future implementation has explicit approval for that action.

## Input Contract

- Operation type: read, search, draft, or approved action.
- Approved account or mailbox identifier.
- Query, message id, thread id, or supplied message content.
- Requested output shape and relevant business context.
- Approval evidence for any write or external action.

## Output Contract

- Operation status and timestamp.
- Message or thread summaries for read operations.
- Draft text and draft metadata for draft operations.
- Action result for approved write operations.
- Errors, missing permissions, redactions, or skipped fields.

## Authentication Expectation

Future implementations must use approved delegated authentication. Secrets, tokens, and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Sending email is external communication and must remain approval-gated.
- Archiving, deleting, labeling, moving, or marking messages may affect live mailbox state and requires the applicable approval.
- Legal, financial, contractual, sensitive, or reputational messages should be escalated for human review.

## Error/Fallback Behavior

- If access, permissions, or message context are unavailable, report the limitation and do not infer mailbox state.
- If sending approval is absent, return a draft and approval requirement instead of sending.
- If a message cannot be read safely, return a redacted or partial result with the reason.

## Data Retention/Privacy Expectations

- Retain only the minimum message content needed for the approved task.
- Do not store secrets, raw mailbox dumps, unnecessary personal data, or unrelated threads.
- Keep operational mailbox state separate from long-term knowledge.

## Intended Agents/Skills

- Communications Agent: `skills/communications/inbox-manager`, `skills/communications/meeting-notes`
- Sales Agent: `skills/sales/speed-to-lead`, `skills/sales/follow-up`, `skills/sales/proposal-builder`
- Marketing Agent: `skills/marketing/reputation-review`, when approved email feedback is supplied
- Operations Agent: `skills/operations/report-builder`, when approved email-derived status is supplied
