# Integrations

This directory contains provider-neutral connector contracts for the Agent Company core. These contracts define expected boundaries for future integrations; they do not implement API clients, runtime listeners, credentials, or provider-specific execution logic.

All connector contracts defer to `../CONSTITUTION.md` and `../AGENTS.md`. Write actions, external communications, publication, account changes, destructive operations, and other externally consequential actions require the applicable approval before execution.

## Phase 5C Connector Contracts

- `gmail`
- `google-drive`
- `google-calendar`
- `github`
- `telegram`
- `webhooks`

## Contract Boundary

Each connector contract separates read operations from write or action operations. Future implementations must preserve that separation and must not turn a read-capable integration into an autonomous external actor.
