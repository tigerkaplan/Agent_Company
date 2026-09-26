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
- Phase 7 provides permission-scoped private Telegram commands, bounded
  notifications, and authenticated localhost webhook machine ingress.
- Merge, deployment, public webhook exposure, TLS termination, remote task
  submission, remote scheduler/file/Git commands, general connector execution,
  infrastructure automation, and dedicated observability are not current
  runtime capabilities.
- Existing projects remain external authorities and must not be migrated or rewritten merely to be managed.

## Success Criteria

- Root governance files clearly define the company intent, rules, and operating model.
- Shared rules are canonical and not duplicated across provider bootstraps.
- Provider-specific files defer to canonical company files.
- The system explicitly separates agents, skills, prompts, workflows, review, state, and knowledge.
- The initial core can be extended in later phases without contradicting Phase 1.

## Current Direction

The final repository-backed architecture and security review of the Phase 7
remote-control and runtime-ingress boundary passed on 2026-09-24, so Phase 7 is
completed and closed. Phase 8A Always-On Runtime and Deployment Architecture
Design is PASS / COMPLETED. It changed no local-first runtime capability,
performed no deployment, and installed no Docker, VPS, or Hermes component.
Phase 8B host configuration and persistent-state foundations are COMPLETED /
CLOSED after their successful final independent re-review; they add no service,
deployment, or new authority. Phase 8C is COMPLETED / CLOSED after its
successful final independent re-review; it adds a supervisor-neutral process
lifecycle but installs no service or supervisor and grants no new authority.
Phase 8D is COMPLETED / CLOSED after its successful independent
architecture/security review. It added Docker adaptation only and performed no
VPS deployment, operating-system service or production supervisor installation,
TLS, reverse proxy, public webhook ingress, Hermes integration, production
provider installation, live Telegram/provider execution, merge, or deployment.
Phase 8E is BLOCKED / PAUSED because the VPS has not yet been created;
deployment has not started, and its recorded target-host runtime validation
prerequisites remain required. Phase 8F is NOT STARTED. A
future different-provider full-repository
audit and the other recorded Phase 8C hardening items remain recommended
validation, not a mandatory Phase 8 implementation gate.
