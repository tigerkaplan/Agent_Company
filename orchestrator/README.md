# Phase 1 Orchestrator

This directory defines the minimal provider-neutral orchestrator for Phase 1. It is a canonical routing and policy layer, not a runtime service.

The orchestrator reuses:

- `../CONSTITUTION.md`
- `../AGENTS.md`
- `../agents/`
- `../skills/`

## Scope

Phase 1 orchestration defines:

- task classification;
- canonical agent routing;
- approval policy;
- dry-run policy;
- minimal workflow templates.

It does not implement provider weighting, Hermes, scheduler, queue, workers, integrations, VPS deployment, or LLM Wiki.

## Directory Map

- `dispatcher/`: task classification and dispatch rules.
- `routing/`: canonical agent route map.
- `approvals/`: human approval policy and risk levels.
- `workflows/`: minimal workflow skeletons.
- `dry-run/`: dry-run behavior for inspection-only work.

## Source Of Truth

This orchestrator must not redefine global governance. When a rule belongs to company policy, agent behavior, or reusable skill procedure, reference the canonical file instead of copying it here.
