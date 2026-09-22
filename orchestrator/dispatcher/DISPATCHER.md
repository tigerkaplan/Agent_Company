# Dispatcher

The dispatcher classifies an incoming task, selects the initial canonical agent route, and identifies whether review, dry-run, or human approval is required.

## Inputs

- User request.
- Active project or repository, if any.
- Relevant project state, if available.
- Applicable governance from `../../CONSTITUTION.md`, `../../AGENTS.md`, `../../agents/`, and `../../skills/`.

## Procedure

1. Classify the task using `TASK_CLASSIFICATION.md`.
2. Select the initial agent using `../routing/ROUTING.md`.
3. Check approval needs using `../approvals/APPROVAL_POLICY.md`.
4. Apply dry-run policy using `../dry-run/policy.yaml` when the task is onboarding, audit, or inspection.
5. Select the matching minimal workflow from `../workflows/`.
6. Resolve the provider capability and configured preference using `../routing/providers.yaml`.
7. Route important or high-risk output to Reviewer before acceptance.

## Current Configuration Scope

- Provider routing configuration and configurable weights exist for Claude and Codex.
- Provider-native Claude and Codex adaptations exist under `../../.claude/` and `../../.agents/`.
- Routing decisions are specification-driven; runtime/API execution and live availability checks are not implemented.
- Provider availability must be supplied as observed input rather than assumed.
- Do not start queues, workers, schedulers, integrations, deployments, or external messaging systems.
