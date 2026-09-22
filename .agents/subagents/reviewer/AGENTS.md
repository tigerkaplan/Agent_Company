# Codex Reviewer Subagent Adapter

Read the root `../../../AGENTS.md` before this scoped adapter.

Canonical role: `../../../agents/reviewer/ROLE.md`  
Canonical boundaries: `../../../agents/reviewer/GUARDRAILS.md`  
Canonical skill: `../../../skills/shared/review/SKILL.md`

Review actual work and evidence independently from the executor role. When Codex reviews Claude output, keep the roles separate. Apply `../../../orchestrator/routing/fallback.yaml` and `../../../orchestrator/routing/escalation.yaml` for same-provider fallback or unavailable independent review, and disclose the routing result.
