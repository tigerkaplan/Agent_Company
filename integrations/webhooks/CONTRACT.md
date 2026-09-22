# Webhooks Connector Contract

## Purpose

Provide a provider-neutral contract for generic inbound webhook triggers with source and payload validation before routing to agents or skills.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

## Supported Read Operations

- Receive approved inbound event payloads.
- Read normalized event metadata, headers, source identifiers, and body content.
- Inspect payload validation status and routing context.

## Supported Write/Action Operations

- Acknowledge receipt when a future listener exists.
- Queue or route a validated event for review or processing when approved by system policy.
- Trigger downstream write or external actions only through the target connector's approval boundaries.

## Input Contract

- Operation type: inbound event, validate, normalize, route, or approved action.
- Source identifier, timestamp, headers, signature, and payload.
- Expected schema, allowed source, replay window, and routing rules.
- Idempotency key or event id, when available.
- Approval evidence for any downstream externally consequential action.

## Output Contract

- Operation status and timestamp.
- Validation result and normalized payload.
- Routing recommendation, rejected reason, or quarantine status.
- Idempotency or duplicate-detection result.
- Errors, schema mismatches, missing signatures, or untrusted source warnings.

## Authentication Expectation

Future implementations must validate source identity using an approved mechanism such as signatures, shared secrets, allowlists, or delegated platform verification. Secrets and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Inbound webhook receipt does not approve downstream action.
- Any write, external communication, publication, account change, financial action, or destructive action triggered by a webhook remains subject to the relevant approval policy.
- Unknown, invalid, replayed, or unsigned payloads must not trigger actions.

## Error/Fallback Behavior

- Reject or quarantine invalid, unsigned, replayed, stale, oversized, or schema-mismatched payloads.
- If source validation is unavailable, treat the event as untrusted.
- If routing is ambiguous, stop at normalized event output and request review.
- If downstream approval is absent, return a proposed action instead of executing it.

## Data Retention/Privacy Expectations

- Retain only the minimum payload data needed for validation, routing, and audit.
- Do not store secrets, raw event dumps, unrelated payload fields, or unnecessary personal data.
- Keep transient webhook events separate from long-term knowledge.

## Intended Agents/Skills

- Project Manager Agent: routing and coordination.
- Operations Agent: `skills/operations/report-builder`, `skills/operations/sop-builder`
- Communications Agent: `skills/communications/inbox-manager`, when events represent inbound messages
- Sales Agent: `skills/sales/speed-to-lead`, when events represent approved lead notifications
- Marketing Agent: `skills/marketing/marketing-monday`, when events represent approved marketing signals
