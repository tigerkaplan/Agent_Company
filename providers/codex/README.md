# Codex Provider

Codex is configured as an execution provider for canonical Agent Company work.

- `provider.yaml` declares provider identity, canonical dependencies, and availability inputs.
- `capabilities.yaml` declares routing eligibility against the canonical capability model.
- `runtime.json` declares the allowlisted local CLI command, timeout, and output bounds.

Routing preferences live in `../../orchestrator/routing/weights.yaml`; they are configuration choices, not factual claims about provider quality. Codex must follow `../../CONSTITUTION.md`, `../../AGENTS.md`, and the selected canonical agent, skill, and workflow.

`READ_ONLY` keeps the Phase 6E invocation: the prompt is sent on stdin and `codex exec` runs ephemerally with user config disabled and the fixed `read-only` sandbox option.

The adapter supplies a default-deny child environment. Codex receives required
system/locale variables plus only Codex-specific allowlisted authentication
variables. When `AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT` is configured,
`CODEX_HOME`, `HOME`, and `USERPROFILE` point to its dedicated `codex/` child.
Telegram, webhook, Claude, and arbitrary host secrets are not propagated.

Phase 6H declares Codex eligible for `CONTROLLED_WRITE` only through the controlled-write runtime. It uses fixed `workspace-write` and `--skip-git-repo-check` options with `shell=False` because the runtime-owned isolated staging workspace is intentionally not a Git repository. Because `--ignore-user-config` also removes the native Windows sandbox implementation setting, controlled write supplies the fixed invocation override `windows.sandbox="elevated"`; authentication still comes from `CODEX_HOME`, while other user configuration remains disabled. `TEMP`, `TMP`, and `TMPDIR` are set to that staged workspace so the native sandbox's implicit temporary-file allowance does not expose another `%TEMP%` location. The compatibility and Windows overrides are absent from READ_ONLY execution and cannot select an arbitrary working directory: the adapter accepts only the validated `%TEMP%/agent-company-write-*/workspace` shape.

The adapter reads the bounded Codex startup metadata from stderr and records both requested and effective sandbox modes. It accepts only a canonical mode token, optionally followed by bounded bracketed diagnostics such as `[workdir, /tmp, $TMPDIR]`; those diagnostics never grant Agent Company scope. Any requested/effective mismatch fails as `provider_sandbox_mismatch`, and missing or malformed effective metadata fails as `provider_sandbox_unverified`. Neither failure can reach target apply. Codex never receives arbitrary command arguments from its output, and it does not write directly to the target repository. The runtime independently validates and applies staged file changes. This is not a claim of live authentication or successful remote execution; automated tests and local sandbox probes consume no model usage.
