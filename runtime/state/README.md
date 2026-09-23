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

Generated job records are stored as stable, pretty-printed JSON files under `jobs/`, one file per job. Execution request/result records use the same approach under `executions/`, with bounded provider, review, mutation, local Git, push, and pull-request plans/evidence below it; approval requests live under `approvals/`, schedule definitions under `schedules/`, and bounded Scheduler state/audit records under `scheduler-runtime/`. These generated directories are ignored by Git while canonical documentation remains tracked. Writes use a temporary file in the same directory followed by atomic replacement. Job claims use a short local transaction lock and the Scheduler uses a singleton OS file lock, while lease metadata provides restart recovery; this remains a local, sequential design rather than a distributed transaction system.

Job records must contain references rather than credentials, provider tokens, full project state, or duplicated knowledge content.

## Project State

Project state lives under `../../shared/projects/*`. Jobs may reference project state by `project_id` or file reference, but runtime state must not become a second project-state system.

## Agent Memory

Agent memory lives under `../../agents/*/MEMORY.md`. Runtime job records must not silently write or rewrite agent memory.

## Knowledge

Canonical long-term knowledge lives under `../../shared/knowledge/`. Runtime state may reference knowledge sources used during execution, but it must not become a second knowledge store.
