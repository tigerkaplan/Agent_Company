---
name: reviewer
description: Execute an independent canonical review through Claude.
---

# Claude Reviewer Adapter

Canonical role: `../../agents/reviewer/ROLE.md`  
Canonical boundaries: `../../agents/reviewer/GUARDRAILS.md`  
Canonical skill: `../../skills/shared/review/SKILL.md`

Read the canonical files before reviewing actual work and evidence. When Claude is selected to review Codex output, keep the reviewer role separate from the executor. For same-provider fallback or unavailable independent review, apply `../../orchestrator/routing/fallback.yaml` and `../../orchestrator/routing/escalation.yaml` and disclose the routing result; this adapter grants no approval authority.
