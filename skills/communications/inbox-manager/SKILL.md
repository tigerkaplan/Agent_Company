# Skill: Inbox Manager

## Purpose

Classify, prioritize, summarize, and draft responses for inbound messages without sending or modifying external communications.

## Inputs

- Approved message text or message summaries.
- Known sender, channel, date, and context, when available.
- Business priorities, routing rules, or triage categories.
- Tone guidance or response constraints, when approved.
- Applicable approval policy for outbound communication.

## Outputs

- Message classification.
- Priority and recommended next action.
- Concise summary.
- Draft response or response options, when useful.
- Open questions, missing context, and approval needs.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay provider-neutral and platform-neutral.
- Do not create connectors, runtime automation, or provider-specific copies.
- Do not make triage categories specific to one business by default.
- Do not store operational state, secrets, or raw connector data dumps.

## Procedure

1. Identify the message source, sender context, and available metadata.
2. Classify the message by intent, topic, urgency, and required action.
3. Prioritize the message against approved business context and stated rules.
4. Summarize the message in neutral language.
5. Draft a response only when enough context exists.
6. Mark missing facts, uncertainty, and required approvals.
7. Separate internal notes from text that could be sent externally.

## Approval Boundaries

- Never send, schedule, forward, archive, delete, or externally publish messages without applicable approval.
- Treat all response wording as draft material until approved.
- Escalate messages involving legal, financial, safety, account, reputational, or contractual risk.

## Completion Checks

- Classification, priority, summary, and next action are clear.
- Drafts are labeled as drafts.
- External sending or message modification has not occurred.
- Missing context and approval needs are visible.
- Facts, assumptions, and uncertainty are not blurred.
