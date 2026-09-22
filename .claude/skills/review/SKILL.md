---
name: review
description: Apply the canonical independent review skill through Claude.
---

# Claude Review Skill Adapter

Canonical skill: `../../../skills/shared/review/SKILL.md`

Read and execute the canonical skill against actual evidence. Apply `../../../orchestrator/routing/fallback.yaml` and `../../../orchestrator/routing/escalation.yaml` when provider independence is unavailable, and do not repair reviewed work during the review pass.
