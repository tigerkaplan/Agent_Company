# Skill: Meeting Notes

## Purpose

Convert transcripts or meeting notes into concise summaries, confirmed decisions, action items, and follow-ups.

## Inputs

- Transcript, rough notes, or meeting recording-derived text.
- Meeting date, attendees, topic, and purpose, when available.
- Known project or business context.
- Preferred action-item owner and due-date format, if specified.

## Outputs

- Meeting summary.
- Confirmed decisions.
- Action items with owners and due dates when stated.
- Follow-up questions or next-step drafts.
- Unresolved topics and inferred items clearly labeled.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay provider-neutral and platform-neutral.
- Do not create connectors, runtime automation, or provider-specific copies.
- Do not invent attendees, decisions, owners, due dates, or approvals.
- Do not store operational state, secrets, or raw connector data dumps.

## Procedure

1. Identify the meeting purpose, participants, and source quality.
2. Extract the main topics in chronological or thematic order.
3. Separate confirmed decisions from discussion points.
4. Extract action items only when the source supports them.
5. Label inferred action items separately from confirmed action items.
6. Identify follow-ups, blockers, unresolved questions, and review needs.
7. Produce a concise summary suited for handoff or review.

## Approval Boundaries

- Do not publish, send, or file meeting notes into an external system without applicable approval.
- Escalate sensitive, contractual, legal, financial, or personnel-related decisions for review.

## Completion Checks

- Summary reflects the supplied transcript or notes.
- Confirmed decisions and inferred action items are distinct.
- Owners and dates are present only when supported or explicitly marked as missing.
- Follow-ups and unresolved questions are visible.
- No external publication or system update has occurred.
