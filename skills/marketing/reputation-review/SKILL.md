# Skill: Reputation Review

## Purpose

Analyze reviews, comments, or customer feedback, group themes, and draft response options without publishing them.

## Inputs

- Approved reviews, comments, testimonials, complaints, or feedback excerpts.
- Source, date, rating, product, service, or channel context, when available.
- Response tone guidance and escalation rules.
- Known business facts relevant to the feedback.
- Applicable approval policy for public or private responses.

## Outputs

- Feedback theme groups.
- Sentiment and urgency summary.
- Reputation risks and recurring issues.
- Draft response options.
- Escalation and approval recommendations.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay provider-neutral and platform-neutral.
- Do not create connectors, review-platform automation, runtime automation, or provider-specific copies.
- Do not publish responses or alter review records.
- Do not store operational state, secrets, or raw connector data dumps.

## Procedure

1. Confirm the feedback source, date range, and available context.
2. Group feedback into themes and sentiment categories.
3. Identify urgent, sensitive, or recurring issues.
4. Separate direct evidence from interpretation.
5. Draft response options when enough context exists.
6. Flag responses that need human, legal, operational, or reputational review.
7. Summarize lessons and recommended internal next steps.

## Approval Boundaries

- Do not publish, send, hide, delete, flag, or modify reviews or responses without applicable approval.
- Escalate legal threats, safety issues, discrimination claims, payment disputes, personal data, or reputational risks.

## Completion Checks

- Themes and sentiment are grounded in supplied feedback.
- Response drafts are labeled as drafts.
- Publication or platform modification has not occurred.
- High-risk feedback is flagged.
- Evidence, inference, and uncertainty remain distinct.
