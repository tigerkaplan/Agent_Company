# Intent

## Problem

AI-assisted work across multiple projects can lose continuity when each model, tool, or chat session acts as the whole system. Context becomes scattered, project state is mixed with long-term knowledge, risky actions may happen without explicit approval, and provider-specific instructions can drift away from shared company rules.

## Desired Outcome

Build a local-first AI Agent Company core that coordinates agents, skills, prompts, workflows, review, and project context independently of any single provider. The core should begin with Claude and Codex, support ChatGPT later, and allow existing projects to be onboarded without rewriting their structure.

The system should make it clear:

- what is canonical company knowledge;
- what is current project state;
- which provider is executing a task;
- what context is required;
- when review is required;
- when human approval is required.

## Users And Stakeholders

- Human owner/operator who approves important decisions and irreversible actions.
- Agent operators that perform work on projects.
- Reviewers and gatekeepers that validate critical outputs independently.
- Existing project repositories that need onboarding without forced rewrites.
- Future business operations users who may interact through tools such as Obsidian, Hermes, Telegram, schedules, and connectors.

## Constraints

- The company core must be provider-independent.
- Claude, Codex, ChatGPT, and future engines are providers, not the company.
- Canonical definitions must remain separate from provider-specific generated files.
- Project operational state must remain separate from long-term knowledge.
- Deterministic tools and scripts are preferred when reasoning is not needed.
- Context and token usage should be minimized.
- Risky or irreversible actions require human approval.
- Existing projects must remain onboardable without restructuring them.

## Current Scope Boundary

- The core now includes canonical agents, skills, routing, project onboarding, structured knowledge, and a local execution runtime.
- Current implementation status belongs in `PROJECT_STATE.md`; capability progression belongs in `ROADMAP.md`.
- Merge, deployment, Telegram command handling, general connector execution, infrastructure automation, and dedicated observability are not current runtime capabilities.
- Existing projects remain external authorities and must not be migrated or rewritten merely to be managed.

## Success Criteria

- Root governance files clearly define the company intent, rules, and operating model.
- Shared rules are canonical and not duplicated across provider bootstraps.
- Provider-specific files defer to canonical company files.
- The system explicitly separates agents, skills, prompts, workflows, review, state, and knowledge.
- The initial core can be extended in later phases without contradicting Phase 1.

## Current Direction

The immediate task is to verify and checkpoint the existing Phase 6 runtime. No later numeric phase is canonically defined. New capability work must begin only after the current state, roadmap, tests, and approval boundaries are reconciled.
