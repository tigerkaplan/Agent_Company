# Skill: Project Audit

## Purpose

Inspect a project's current state, repository health, documentation, tests, blockers, and risks without modifying the target project by default.

## Inputs

- Target project path or project identifier.
- Audit objective.
- Known constraints, protected areas, or read-only requirements.
- Relevant project instructions or governance files.
- Available deterministic checks.

## Outputs

- Project state summary.
- Repository status summary.
- Documentation findings.
- Tests, build, or check results.
- Blockers and risks.
- Recommended next steps.
- Clear note of any checks not run.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Default to read-only and dry-run behavior.
- Do not modify the target project unless explicitly approved.
- Use deterministic commands and existing project tooling where available.
- Do not treat dormant files, generated summaries, or folder names as runtime evidence without verification.

## Procedure

1. Confirm the target project path or identifier.
2. Read the smallest relevant governance and project instruction files.
3. Inspect repository status without changing files.
4. Inspect relevant documentation for current state, decisions, and warnings.
5. Identify available tests, builds, linters, or validation commands.
6. Run safe read-only or approved deterministic checks when appropriate.
7. Record blockers, risks, uncertainty, and evidence.
8. Recommend narrow next steps.

## Checks

- The audit did not modify the target project unless explicitly approved.
- Repository status is reported from an actual tool result when available.
- Tests, builds, or skipped checks are clearly stated.
- Findings distinguish evidence from inference.
- Risks and blockers are visible, not buried in prose.
