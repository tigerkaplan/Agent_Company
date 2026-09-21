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

## Out Of Scope For Phase 1

- Creating the full folder architecture.
- Building agent, skill, prompt, or workflow registries.
- Implementing LLM Wiki, INGEST, QUERY, or LINT.
- Integrating Obsidian, Hermes, Telegram, scheduling, VPS deployment, or business connectors.
- Implementing provider routing logic.
- Migrating or rewriting existing projects.

## Success Criteria

- Root governance files clearly define the company intent, rules, and operating model.
- Shared rules are canonical and not duplicated across provider bootstraps.
- Provider-specific files defer to canonical company files.
- The system explicitly separates agents, skills, prompts, workflows, review, state, and knowledge.
- The initial core can be extended in later phases without contradicting Phase 1.

## Open Questions

- What is the first concrete project to onboard?
- What should the minimum project onboarding record contain?
- Which actions are always gatekeeper-reviewed?
- Which deterministic commands should exist first: INGEST, QUERY, LINT, or another primitive?
- What local storage format should represent operational state?
- What local storage format should represent long-term knowledge?
- How should provider routing be decided once Claude, Codex, and ChatGPT are all available?
