# Webhooks Connector

This directory defines the canonical connector contract for generic inbound webhook triggers.

The Phase 7 local-first implementation is in `../../runtime/webhooks/`. It provides HMAC-SHA256 source verification, timestamp replay protection, bounded persistent idempotency/audit state, one narrow `TASK_SIGNAL` event, canonical dispatcher routing, and an optional localhost-only HTTP adapter.

See `CONTRACT.md` for the provider-neutral boundary and `../../runtime/webhooks/README.md` for the exact signing and local operation rules. No public endpoint, TLS termination, hosted listener, webhook approval authority, remote Git/write authority, merge, or deployment is implemented.
