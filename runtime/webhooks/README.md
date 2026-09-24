# Webhook Runtime Ingress

`runtime.webhooks` is the Phase 7 local-first machine-ingress boundary. It accepts only authenticated, bounded `TASK_SIGNAL` events and routes them through `CanonicalTaskDispatcher`, the same canonical workflow/routing and job-creation boundary used by scheduled work.

The runtime sequence is:

`raw request bytes -> trusted source lookup -> HMAC/timestamp verification -> strict WebhookEvent validation -> durable reservation -> canonical dispatcher -> finalized approval-required job reference`

Webhook receipt is never human approval. An accepted event creates or recovers only a `created` job with `approval_status=required`; it does not create or resolve a human approval record, and the job cannot be queued until a separate human/operator flow establishes and resolves the canonical approval boundary. Webhook code cannot choose a provider, select an agent/workflow/capability directly, supply execution scope, execute a command, write files, or invoke Git, pull-request, merge, or deployment operations.

## Source configuration

Copy `config/webhooks.example.json` to ignored `config/webhooks.local.json`. Stable source IDs declare whether the source is enabled, its explicit allowed event types, `HMAC_SHA256`, an environment-variable name containing the secret, and an optional project binding. Actual shared secrets must not be placed in the tracked example or committed.

The only MVP event type is `TASK_SIGNAL`. Its bounded payload contains exactly `task` and `task_class`. Because the runtime has no executable free-text classifier, `task_class` is required and must resolve through the tracked canonical workflow and provider-capability routing files. A configured project binding is injected when absent and mismatches are rejected.

## Signing rule

Send:

- `Content-Type: application/json`
- `X-Agent-Webhook-Timestamp: <Unix seconds>`
- `X-Agent-Webhook-Signature: sha256=<lowercase hexadecimal HMAC>`

The exact signed bytes are:

`ASCII(timestamp) + b"." + raw HTTP request body bytes`

The secret is the UTF-8 value of the configured environment variable. Verification uses HMAC-SHA256 and constant-time comparison. Missing/invalid signatures, unknown or disabled sources, and timestamps outside the configured replay window fail closed. JSON is decoded only after signature verification, and duplicate JSON keys are rejected.

## Local HTTP adapter

`runtime.webhooks.http.create_local_http_server` provides only `POST /webhooks/<source_id>`. It binds to `127.0.0.1` by default and rejects non-loopback bind addresses. The adapter requires JSON, rejects chunked transfer input, enforces `Content-Length`, caps request size, applies a bounded socket timeout, has no directory serving or arbitrary routes, and performs no shell execution. No public listener, TLS termination, service installer, or hosted deployment command is included.

## State and retention

Durable provenance records and bounded audit records belong under ignored `runtime/state/webhooks/`. Expendable audit history retains bounded event/source/type identifiers, receipt time, verification and dedupe results, an optional job reference, and an error code. Neither store retains the raw body, payload, signature, secret, environment-variable name, or provider token.

Before dispatch, one atomic durable provenance record binds the source, primary event ID, primary idempotency key, their bounded alias sets, content fingerprint, deterministic provenance ID, state, timestamps, and canonical job reference when available. Its lifecycle is `RESERVED -> DISPATCH_ATTEMPTED -> COMPLETED` or `FAILED`. Every matching event ID or idempotency key later observed is atomically added as an alias of that same provenance before a duplicate response is returned. Once either identity is bound, chained reuse resolves to that provenance or fails as a content conflict; it cannot create new work. Alias bindings survive restart and ordinary audit churn.

A retry of `DISPATCH_ATTEMPTED` first looks up the deterministic canonical provenance and finalizes the existing job reference instead of creating another job.

Audit history is atomically written and bounded independently by `max_audit_records` (default 1000). Rejected, malformed, unauthenticated, invalid-signature, or stale traffic may prune older expendable audit history, but it cannot prune or replace accepted provenance identity.

Provenance files are not automatically pruned by normal audit retention. Incomplete provenance remains durable for recovery, and completed provenance remains as a minimal dedupe tombstone containing the identities, fingerprint, state, timestamps, and canonical job reference needed to prevent redispatch. Provenance or alias persistence failure before dispatch fails closed; finalization failure retains the attempted provenance for restart recovery. No time-based provenance expiry is defined for the local MVP.

## Not implemented

- public internet exposure, TLS, reverse proxy, or load balancer;
- cloud webhook deployment, Docker, VPS, or Hermes;
- webhook-based human approval;
- remote controlled-write, commit, push, pull-request, merge, or deployment authority;
- arbitrary event-to-function dispatch;
- live external network calls in the automated tests.
