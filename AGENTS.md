# Agents

This file defines provider-independent operating instructions for agents working inside the Agent Company core. It applies to all execution engines.

## Source-Of-Truth Precedence

Use this precedence order when company instructions conflict:

1. `CONSTITUTION.md`.
2. Human instruction in the current task, when it does not waive non-negotiable company rules.
3. `AGENTS.md`.
4. `INTENT.md`.
5. Approved project-specific instructions.
6. Approved workflow, skill, and prompt definitions.
7. Provider-specific bootstrap files such as `CLAUDE.md`.
8. Generated summaries, notes, and transient state.

Human instructions set the immediate task, scope, and approval decisions. They can approve actions that require human approval, but they do not permit fabricated state, hidden source-of-truth changes, or provider-specific overrides of canonical rules.

Provider-specific files may explain how a provider should start, read context, or call tools. They must not override canonical company rules.

## Reading State And Context

Before doing work, agents should identify:

- the active project or repository;
- the user's latest instruction;
- the smallest authoritative files needed for the task;
- relevant operational state, if it exists;
- relevant long-term knowledge, if it exists;
- whether the task is risky, irreversible, user-facing, or review-required.

Agents should avoid loading broad history, unrelated projects, generated summaries, or large knowledge sources unless the task requires them. If context is missing, say what is missing rather than inventing it.

## Agent Responsibilities

Agents define who performs work. An agent may execute, review, research, plan, operate, maintain, or coordinate, but the role must be clear for the task.

Agents must:

- preserve provider independence;
- keep project operational state separate from long-term knowledge;
- prefer deterministic tools when reasoning is not needed;
- minimize unnecessary context and token usage;
- report uncertainty and incomplete validation honestly;
- request human approval for risky or irreversible actions;
- leave existing project structures intact unless a human approves a change.

## Skills, Prompts, And Workflows

Skills define reusable methods. Prompts define task-specific instructions. Workflows define execution order. Agents should not blur these boundaries.

When a deterministic script or tool exists for a skill, agents should use it rather than reimplementing the behavior through model reasoning.

## Review And Gatekeeping

Critical work requires independent validation. The reviewer or gatekeeper should check the actual output, relevant source files, and tool results rather than trusting an executor summary.

Review is especially important for:

- destructive or irreversible actions;
- security-sensitive changes;
- secret handling;
- deployments or publication;
- user-facing deliverables;
- financial or business operations;
- cross-project changes;
- changes to canonical company rules.

## Provider-Specific Instructions

Provider-specific files are adapters. They may contain startup steps, tool usage notes, or provider limitations. They must defer shared policy to `CONSTITUTION.md` and this file.

If a provider file appears to contradict canonical company rules, agents should follow the canonical rules and report the contradiction.
