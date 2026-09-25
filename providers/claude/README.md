# Claude Provider

Claude is configured as an execution provider for canonical Agent Company work.

- `provider.yaml` declares provider identity, canonical dependencies, and availability inputs.
- `capabilities.yaml` declares routing eligibility against the canonical capability model.
- `runtime.json` declares the allowlisted local CLI command, timeout, and output bounds.

Routing preferences live in `../../orchestrator/routing/weights.yaml`; they are configuration choices, not factual claims about provider quality. Claude must follow `../../CONSTITUTION.md`, `../../AGENTS.md`, and the selected canonical agent, skill, and workflow.

Phase 6E can invoke `claude --print` through the provider-neutral runtime when provider mode is selected explicitly. The prompt is sent on stdin, the CLI runs in bare plan mode without session persistence, and bounded output is stored under ignored runtime state. No SDK/API integration, credentials, or provider-specific source-of-truth logic is included.

The adapter supplies a default-deny child environment. Claude receives required
system/locale variables plus only Claude-specific allowlisted authentication
variables. When `AGENT_COMPANY_PROVIDER_CREDENTIAL_ROOT` is configured,
`CLAUDE_CONFIG_DIR`, `HOME`, and `USERPROFILE` point to its dedicated `claude/`
child. Telegram, webhook, Codex, and arbitrary host secrets are not propagated.

Claude declares only `READ_ONLY` support. Its executable is currently unavailable locally, and controlled-write behavior has not been verified or enabled. A controlled-write request naming Claude may fall back through the canonical provider router to an eligible available provider; the runtime records requested provider, actual provider, execution mode, and fallback reason.
