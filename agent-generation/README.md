# Provider Adapter Generation

This directory documents how provider-native adapters are derived from Agent Company canonical definitions. Phase 4B includes no generator or runtime code.

## Authority Boundary

Canonical content remains in:

- `../agents/` for roles, agent boundaries, and agent memory;
- `../skills/` for reusable procedures;
- `../orchestrator/` for classification, workflows, routing, risk, and approvals;
- `../shared/` for project state and long-term knowledge.

`../.claude/` and `../.agents/` are replaceable provider-facing views. Editing an adapter does not change canonical behavior.

## Adaptation Procedure

1. Select an existing canonical role or skill.
2. Create the provider-native file at the expected path.
3. Link to the canonical definition instead of copying its contents.
4. Add only provider-specific loading, tool-use, or output guidance.
5. Validate relative links and confirm that no policy, state, memory, or knowledge was duplicated.
6. Recheck independent-review routing against `../orchestrator/routing/fallback.yaml` and `../orchestrator/routing/escalation.yaml`.

The `knowledge-manager` files adapt the canonical role at `../agents/knowledge-manager/` and link it to the existing canonical knowledge skills.

## Review Preference

When practical, route review to a provider different from the executor. This is a configurable preference, not a guarantee. Same-provider review and high-risk escalation remain governed by the canonical routing files, and provider adaptation never replaces human approval.
