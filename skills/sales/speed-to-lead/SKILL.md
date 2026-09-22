# Skill: Speed To Lead

## Purpose

Identify, prioritize, and prepare rapid response drafts for new leads while preserving approval boundaries.

## Inputs

- Approved lead details or inquiry text.
- Source, timestamp, requested service or product, and contact context, when available.
- Qualification criteria, response tone, and routing rules.
- Existing customer or opportunity context, when approved.
- Applicable approval policy for outbound communication.

## Outputs

- Lead priority and rationale.
- Qualification summary.
- Missing information or qualification questions.
- Rapid response draft or response options.
- Recommended next action and approval needs.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Stay provider-neutral and platform-neutral.
- Do not create connectors, CRM automation, runtime automation, or provider-specific copies.
- Do not make the skill specific to one business, sales funnel, or market.
- Do not store operational state, secrets, or raw connector data dumps.

## Procedure

1. Confirm the lead source and available context.
2. Classify the lead by urgency, fit, value signal, and response need.
3. Compare the lead against approved qualification criteria.
4. Identify missing facts and useful qualification questions.
5. Prepare a concise rapid response draft that matches the approved tone.
6. Recommend the next action, owner, and review need when known.
7. Label draft content and uncertainty clearly.

## Approval Boundaries

- Never send an external response without applicable approval.
- Do not make pricing, availability, contractual, or delivery commitments unless explicitly approved.
- Escalate high-value, sensitive, legal, financial, or reputational leads for human review.

## Completion Checks

- Lead priority and rationale are clear.
- Qualification gaps are visible.
- Response wording is labeled as draft.
- No external message was sent.
- Commercial commitments are absent unless approved.
