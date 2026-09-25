# Infrastructure

This directory contains the canonical Phase 8 hosting and deployment design.
It does not contain a deployment, service definition, container image, public
endpoint, credential, or infrastructure automation.

## Status

- Phase 8A: PASS / COMPLETED on 2026-09-24; design and discovery only.
- Phase 8B: COMPLETED / CLOSED; no deployment.
- Phase 8C: NEXT / NOT STARTED.
- Current runtime: local-first, file-backed, and single-worker.
- Deployment: not performed.
- Docker, VPS, operating-system service, Hermes, and public webhook exposure:
  not installed or enabled.
- Merge and deployment authority: absent.

Phase 8B did not add a process supervisor or service lifecycle, systemd,
Windows Service, Docker, VPS deployment, Hermes, public webhook exposure,
backup automation, merge authority, or deployment authority. Future
cross-provider audit, native Windows ACL inspection, and race-resistant
directory-handle containment are non-blocking hardening items.

## Documents

- `HOST_ARCHITECTURE.md` defines the host boundary, process and persistence
  models, startup and recovery behavior, Docker and VPS assessments, acceptance
  criteria, and proposed implementation stages.
- `SECURITY_MODEL.md` defines production secret handling, ingress and authority
  boundaries, backup safety, and the Phase 8 threat model.

## Phase 8B Host Foundation

`config/host.example.json` is the tracked, non-secret contract. Copy it to the
Git-ignored `config/host.local.json` only when a local override is needed. The
canonical base root resolves in this order: CLI `--base-root`,
`AGENT_COMPANY_STATE_ROOT`, host-config `state_root`, then the safe local
default `runtime/state/`. Existing component-specific root variables remain
compatibility fallbacks only when no canonical base root is configured. With a
configured base, every component path must equal its fixed derived path.

From the repository root:

```text
python -m runtime.cli host init [--config <path>] [--base-root <absolute-path>]
python -m runtime.cli host check [--config <path>] [--base-root <absolute-path>]
```

`host init` creates only the fixed canonical directory layout and is
idempotent; it never migrates or deletes state and makes no network/provider
calls. `host check` is read-only and reports deterministic PASS/WARN/FAIL
checks without printing secret values or raising on malformed dependent
configuration. Host mode requires an explicit dedicated state root outside and
non-overlapping with the repository. Broad directories and repository
ancestors are rejected before creation or permission changes.
`/var/lib/agent-company` remains the recommended Linux production value.

Provider subprocesses use a default-deny environment allowlist. They retain
only required system/locale variables plus variables explicitly approved for
that provider; a configured credential root maps to a separate provider home.
Telegram, webhook, arbitrary connector, and other-provider secrets are not
propagated. State, repository, provider credential, and secret locations are
checked for overlap in both directions. POSIX permission checks remain
enforced; Windows ACL status is WARN and requires operator validation.

State needed for recovery or authority evidence is backup-required: jobs,
executions, approvals, schedules/scheduler state, remote and Telegram replay
state, notifications, webhook provenance/audit, and Git action evidence.
Transient locks and caches are excluded; expendable retained logs are optional.
Secrets and provider credential homes are separate and excluded from ordinary
state backups. Phase 8F, not Phase 8B, owns backup automation.

## Authority Boundary

The host is an availability mechanism only. It may keep the existing runtime
processes alive and provide durable local storage. It must not classify work,
select business routing or providers, decide approvals or reviews, grant Git,
merge, release, or deployment authority, or reinterpret canonical runtime
state.

Any future implementation remains subordinate to `../CONSTITUTION.md`,
`../AGENTS.md`, the existing runtime authority surfaces, and exact human
approval for production deployment.
