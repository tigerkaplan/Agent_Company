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

## Source Of Truth

This orchestrator must not redefine global governance. When a rule belongs to company policy, agent behavior, or reusable skill procedure, reference the canonical file instead of copying it here.
