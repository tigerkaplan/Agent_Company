# Orchestrator

This directory defines the provider-neutral classification, routing, workflow, review, approval, and dry-run policy layer. It remains separate from the execution service implemented under `../runtime/`.

The orchestrator reuses:

- `../CONSTITUTION.md`
- `../AGENTS.md`
- `../agents/`
- `../skills/`

## Scope

The orchestrator defines:

- task classification;
- canonical agent routing;
- approval policy;
- dry-run policy;
- canonical workflow templates and review outcomes;
- provider capability preferences and fallback policy.

It does not itself execute providers, queue or claim jobs, run the Scheduler, mutate projects, invoke connectors, commit, push, create pull requests, merge, or deploy. Those capabilities, where implemented, remain behind their runtime and approval boundaries. Connector directories remain contracts unless an explicit runtime implementation exists.

## Directory Map

- `dispatcher/`: task classification and dispatch rules.
- `routing/`: canonical agent route map.
- `approvals/`: human approval policy and risk levels.
- `workflows/`: minimal workflow skeletons.
- `dry-run/`: dry-run behavior for inspection-only work.
- `graph/`: ORCH-01 graph invariants, acceptance contracts and validation evidence;
  execution coordination remains in `../runtime/graph/`.

## Planned Decision Engine

No `decision-engine/` directory exists now. After Phase 9 observability, a
future bounded design may use:

```text
decision-engine/
  rules/
  scoring/
  classify/
  rank/
  confidence/
  adapters/
    jev/
```

JEV would be an optional adapter for classification, ranking, filtering,
bounded choice, and confidence gating. It is not an agent, human approval
authority, or normal Claude/Codex-style execution provider. Observability must
exist first so any reduction in tokens, provider calls, cost, or routing errors
can be measured.

## Source Of Truth

This orchestrator must not redefine global governance. When a rule belongs to company policy, agent behavior, or reusable skill procedure, reference the canonical file instead of copying it here.
