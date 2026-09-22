# Codex Provider

Codex is configured as an execution provider for canonical Agent Company work.

- `provider.yaml` declares provider identity, canonical dependencies, and availability inputs.
- `capabilities.yaml` declares routing eligibility against the canonical capability model.

Routing preferences live in `../../orchestrator/routing/weights.yaml`; they are configuration choices, not factual claims about provider quality. Codex must follow `../../CONSTITUTION.md`, `../../AGENTS.md`, and the selected canonical agent, skill, and workflow.

No API integration or provider-specific source-of-truth logic is implemented in Phase 4A.

