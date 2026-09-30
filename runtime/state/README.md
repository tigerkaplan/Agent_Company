# Runtime State

Runtime state is operational execution coordination state. It must remain separate from project state, agent memory, and long-term knowledge.

## Runtime State

Runtime state may include:

- job status;
- attempts;
- timestamps;
- schedule timing, claim, lease, and heartbeat metadata;
- execution result references;
- approval and review state references;
- error references for failed attempts.

## Local Persistence

Generated job records are stored as stable, pretty-printed JSON files under `jobs/`, one file per job. Execution request/result records use the same approach under `executions/`, with bounded provider, review, mutation, local Git, push, pull-request, and deterministic eval evidence below it; canonical EvalResults live under `executions/evals/`. Approval requests live under `approvals/`, schedule definitions under `schedules/`, and bounded Scheduler state/audit records under `scheduler-runtime/`. These generated directories are ignored by Git while canonical documentation remains tracked. Writes use a temporary file in the same directory followed by atomic replacement. Job claims use a short local transaction lock and the Scheduler uses a singleton OS file lock, while lease metadata provides restart recovery; this remains a local, sequential design rather than a distributed transaction system.

Job records must contain references rather than credentials, provider tokens, full project state, or duplicated knowledge content.

CORE-07 is CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS.
It adds non-authoritative progress journals under `jobs/.progress/`, one
bounded SQLite file per logical job. Events and hash-chain heads commit together
in FULL synchronous transactions; update/delete guards enforce append-only event
rows. Bounded pending bundles reserve complete transition evidence before job
writes; restart delivery checks canonical state and never authorizes a transition.
Recovery reserves its outcome slot before lifecycle mutation and persists the
actual outcome before delivery. Ready recovery evidence replays for terminal
jobs too; insertion and delivery-record removal commit atomically.
Full SQLite protection definitions are validated. Canonical job and authority
records remain in their existing stores. See
`../progress/README.md` for restart reconciliation, limits, and integrity scope.

CORE-04 discovery and deferred-loading evidence remains ephemeral because it
does not mutate job or authority state. Immutable `ToolDiscoveryResult` and
`ToolLoadResult` values expose selection/load evidence to the current runtime
caller; no competing tool-discovery store or persistent cache is introduced.

## Project State

Project state lives under `../../shared/projects/*`. Jobs may reference project state by `project_id` or file reference, but runtime state must not become a second project-state system.

## Agent Memory

Agent memory lives under `../../agents/*/MEMORY.md`. Runtime job records must not silently write or rewrite agent memory.

## Knowledge

Canonical long-term knowledge lives under `../../shared/knowledge/`. Runtime state may reference knowledge sources used during execution, but it must not become a second knowledge store.
