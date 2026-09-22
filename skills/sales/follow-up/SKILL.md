# Skill: Follow-Up

## Purpose

Prepare follow-up context, draft sequences, and next-step recommendations while preserving tone, sales intent, and approval boundaries.

## Inputs

- Approved sales context, prior conversation notes, or lead history.
- Desired outcome, sales stage, and follow-up reason.
- Tone guidance, cadence constraints, and channel preference.
- Known objections, open questions, or promised next steps.
- Applicable approval policy for outbound communication.

## Outputs

- Follow-up context summary.
- Suggested sequence or single follow-up draft.
- Timing and channel recommendation.
- Personalization points and open questions.
- Approval needs and risk flags.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay provider-neutral and platform-neutral.
- Do not create connectors, CRM automation, runtime automation, or provider-specific copies.
- Preserve the approved tone and sales intent.
- Do not store operational state, secrets, or raw connector data dumps.

## Procedure

1. Review approved prior context and identify the sales stage.
2. Clarify the follow-up objective and recipient need.
3. Identify relevant personalization points and unresolved questions.
4. Draft concise follow-up wording or a short sequence.
5. Recommend timing and channel only from approved context.
6. Flag risks, missing facts, and approval requirements.
7. Keep all outbound wording in draft state.

## Approval Boundaries

- Do not send, schedule, or automate external follow-ups without applicable approval.
- Do not add new offers, discounts, deadlines, or commitments unless approved.
- Escalate sensitive, high-value, legal, financial, or reputational follow-ups.

## Completion Checks

- Follow-up purpose and context are clear.
- Tone and sales intent match the approved context.
- Drafts are labeled as drafts.
- No autonomous external send or scheduling occurred.
- Commitments and claims are approved or omitted.
