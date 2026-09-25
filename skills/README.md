# Canonical Skills

This directory contains provider-neutral shared skills for the Agent Company core. A skill is a reusable SOP or capability that an agent can apply across tasks, projects, and providers.

Agents define who performs work. Skills define how reusable work is performed. Prompts define task-specific instructions. Workflows define execution order.

An agent may use multiple skills during one task. For example, a Software Agent may use `project-audit`, then `review`, then `handoff`; a Research Agent may use `research`, then hand the findings to Reviewer through `review`.

## Source Of Truth

Canonical skills live here first. Future Claude, Codex, ChatGPT, or other provider-specific skill adaptations must defer to:

1. `../CONSTITUTION.md`
2. `../AGENTS.md`
3. This `skills/` directory

Provider-specific adaptations may translate format or tool syntax, but they must not redefine the canonical purpose, constraints, or checks.

## Current Physical Skill Families

Skills remain separate from agents: agents define WHO performs work; skills
define HOW reusable work is performed. The current physical families are
`communications/`, `marketing/`, `operations/`, `sales/`, `shared/`, and
`social-media/`.

Phase 1 core skills:

- `skill-creator`
- `handoff`
- `project-audit`
- `research`
- `review`

Phase 3B knowledge skills:

- `knowledge-ingest`: integrate sources into source cards and synthesized wiki pages.
- `knowledge-query`: retrieve minimum relevant indexed knowledge without silently mutating it.
- `knowledge-lint`: report knowledge quality, provenance, navigation, duplication, and gap findings.

Phase 5B business skills:

- Communications: `inbox-manager`, `meeting-notes`
- Sales: `speed-to-lead`, `proposal-builder`, `follow-up`
- Marketing: `marketing-monday`, `reputation-review`, `competitor-analysis`
- Operations: `report-builder`, `sop-builder`

Post-Phase-7 social media capability checkpoint:

- Social Media: `content-calendar`, `post-planner`, `caption-writer`, `hook-generator`, `content-repurpose`, `competitor-monitor`, `performance-review`, `comment-analysis`, `weekly-social-report`

## Planned Skill Expansion

Future, unimplemented skill packs may cover Finance/Pricing, Analytics,
Content, Design, Sales lead generation, SEO, and Reviewer QA/Security. These
plans do not create skill directories and do not move skills under agents.

Do not create provider-specific copies unless a later phase requires an adaptation.
