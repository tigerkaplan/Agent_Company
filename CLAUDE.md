# Claude

This file is Claude's provider-specific bootstrap for the Agent Company core.

Claude is an execution provider, not the company. Shared company rules live in:

1. `CONSTITUTION.md`
2. `AGENTS.md`
3. `INTENT.md`

On session start, Claude should read the canonical files needed for the task and follow their precedence. This file may guide Claude-specific startup behavior, but it must not redefine shared company rules.

For current implementation status and capability progression, read `PROJECT_STATE.md` and `ROADMAP.md`. Runtime-specific Claude configuration is an adapter under `providers/claude/`; it does not become company policy.

If this file conflicts with `CONSTITUTION.md` or `AGENTS.md`, Claude must follow the canonical files and report the conflict.

Claude must not infer approval, write authority, remote Git authority, merge authority, or deployment authority from this bootstrap.
