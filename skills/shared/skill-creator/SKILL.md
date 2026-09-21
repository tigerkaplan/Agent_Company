# Skill: Skill Creator

## Purpose

Design a new reusable, provider-neutral skill package that can be tested, reviewed, and adapted by future providers without changing its canonical intent.

## Inputs

- Requested skill name.
- Problem or recurring task the skill should address.
- Expected users or agents.
- Known constraints and risks.
- Available deterministic tools, scripts, references, or examples.

## Outputs

- A canonical skill definition.
- Clear expected inputs and outputs for the skill.
- A repeatable procedure.
- Checks that can validate correct use.
- Notes about provider-specific adaptation needs, if any.

## Constraints

- Follow `../../../CONSTITUTION.md` and `../../../AGENTS.md`.
- Keep the skill provider-neutral unless a provider-specific adaptation is explicitly required later.
- Do not duplicate global company rules inside the skill.
- Prefer deterministic tools or scripts when reasoning is not required.
- Keep the package reusable; do not bind it to one chat session or project state.

## Procedure

1. Define the skill purpose in one short paragraph.
2. Define required and optional inputs.
3. Define expected outputs.
4. List constraints specific to this skill.
5. Write the procedure as ordered, repeatable steps.
6. Define checks that prove the skill was applied correctly.
7. Identify any review, escalation, or human approval needs.
8. Keep examples out unless they are strictly necessary for reuse.

## Checks

- The skill includes purpose, inputs, outputs, constraints, procedure, and checks.
- The skill is reusable across projects.
- The skill avoids provider-specific assumptions.
- The skill separates facts, assumptions, and unresolved decisions where relevant.
- The skill can be reviewed without reading raw chat history.
