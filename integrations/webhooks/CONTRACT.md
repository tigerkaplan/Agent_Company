# Webhooks Connector Contract

## Purpose

Provide a provider-neutral contract for generic inbound webhook triggers with source and payload validation before routing to agents or skills.

This contract defers to `../../CONSTITUTION.md` and `../../AGENTS.md`.

The Phase 7 MVP implements this boundary locally in `../../runtime/webhooks/`. Webhooks are authenticated machine ingress, never human approval.

## Supported Read Operations

- Receive approved inbound event payloads.
- Read normalized event metadata, headers, source identifiers, and body content.
- Inspect payload validation status and routing context.

The only implemented event type is `TASK_SIGNAL`, with an exact bounded payload of `task` and `task_class`.

## Supported Write/Action Operations

- Acknowledge receipt through the optional implemented localhost listener.
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

The implemented mode is HMAC-SHA256 using a secret loaded from an environment variable named by ignored local source configuration. The signature covers `ASCII(timestamp) + b"." + exact raw body bytes`, is compared in constant time, and is accepted only inside the configured timestamp replay window. Secrets and credentials must not be stored in this contract directory or committed to the repository.

## Approval Boundaries

- Inbound webhook receipt does not approve downstream action.
- Any write, external communication, publication, account change, financial action, or destructive action triggered by a webhook remains subject to the relevant approval policy.
- Unknown, invalid, replayed, or unsigned payloads must not trigger actions.
- Webhooks map to trusted machine sources, not human approvers. They must never resolve `EXECUTE_JOB`, `COMPLETE_REVIEWED_JOB`, `COMMIT_CHANGE_SET`, `PUSH_GIT_COMMIT`, or `CREATE_PULL_REQUEST` approvals.

## Remote Ingress Boundary

Generic webhooks belong in the same remote ingress architecture only as machine-triggered inbound events. A runtime-capable webhook adapter must validate source identity, schema, replay window, and idempotency before producing a canonical remote command or normalized event.

The implemented adapter produces a canonical `WebhookEvent`, not a human `RemoteCommand`. `TASK_SIGNAL` is mapped through the canonical task dispatcher to a `created`, approval-required job. It does not create or resolve an approval record; a separate human/operator flow must establish that boundary before queueing. Source-configured project bindings are preserved and mismatches fail closed.

Webhook adapters may create or route work only through configured orchestrator/runtime operations. They must not execute providers directly, mutate files, commit, push, create pull requests, call arbitrary shell commands, or bypass downstream approval gates.

## Error/Fallback Behavior

- Reject or quarantine invalid, unsigned, replayed, stale, oversized, or schema-mismatched payloads.
- If source validation is unavailable, treat the event as untrusted.
- If routing is ambiguous, stop at normalized event output and request review.
- If downstream approval is absent, return a proposed action instead of executing it.

## Data Retention/Privacy Expectations

- Retain only the minimum payload data needed for validation, routing, and audit.
- Do not store secrets, raw event dumps, unrelated payload fields, or unnecessary personal data.
- Keep transient webhook events separate from long-term knowledge.
- Persist event IDs, source identifiers, validation result, idempotency status, command target, and outcome; avoid storing full raw payloads unless required for accepted job evidence.

Implemented state is stored under ignored `runtime/state/webhooks/` as two separate classes: bounded, prunable audit history and durable accepted provenance identity. Completed provenance is retained as a minimal tombstone containing event/idempotency aliases, content fingerprint, state, timestamps, and canonical job reference, and is not pruned by normal audit retention. Rejected or unauthenticated traffic cannot evict accepted dedupe identity. Raw request bodies, payloads, signatures, secrets, and secret environment-variable names are not persisted.

## Local HTTP Boundary

The optional adapter exposes only `POST /webhooks/<source_id>`, binds to localhost by default, refuses non-loopback bind configuration, requires JSON with a bounded `Content-Length`, rejects transfer encoding, and uses bounded request timeouts. It does not provide TLS, public hosting, directory serving, shell execution, or arbitrary routes.

## Explicitly Not Implemented

- Public internet exposure, TLS termination, external load balancing, or cloud deployment.
- OAuth or a general authentication framework.
- Human approval through webhook content or source trust.
- Direct provider, agent, skill, workflow, capability, file-write, Git, pull-request, merge, or deployment selection.
- Docker, VPS, Hermes, or an always-on service installation.

## Intended Agents/Skills

- Project Manager Agent: routing and coordination.
- Operations Agent: `skills/operations/report-builder`, `skills/operations/sop-builder`
- Communications Agent: `skills/communications/inbox-manager`, when events represent inbound messages
- Sales Agent: `skills/sales/speed-to-lead`, when events represent approved lead notifications
- Marketing Agent: `skills/marketing/marketing-monday`, when events represent approved marketing signals
