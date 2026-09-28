# Jobs

Jobs are canonical runtime execution units created from orchestrator dispatch results. A job is narrower than a human request: it is the unit that can be queued, attempted, reviewed, completed, failed, or cancelled.

The canonical job model is defined in `JOB_MODEL.md`. Legal lifecycle states and transitions are defined in `lifecycle.yaml`. The deterministic JSON representation is defined in `../../schemas/job.schema.json`.

`lifecycle.yaml` is deliberately written as JSON-compatible YAML so the Phase 6B Python runtime can parse the canonical lifecycle with the standard library. Runtime code does not carry a second transition table.

Jobs may reference project state, connector inputs, generated outputs, and execution evidence, but they must not embed project state, credentials, connector secrets, or provider-specific business logic.

Human approval state is stored separately under `../state/approvals/` and linked through compact refs. The job keeps only its lifecycle-facing approval status and resolved audit summary; provider or reviewer text cannot populate that summary.

An optional `execution_budget` field is a runtime-managed immutable binding to
the logical job's CORE-05 policy and restart-safe usage state. Retry and
continuation jobs retain the same binding; budget availability never replaces
ordinary approval, continuation, recovery-hold, Reviewer, or lifecycle gates.
