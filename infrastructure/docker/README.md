# Phase 8D Docker Adaptation

This directory adapts the existing Agent Company runtime to one Linux image and
fixed Compose services. It does not create a second runtime, deploy a VPS,
install a supervisor, expose a public webhook, or grant merge/deployment
authority.

## Status

Phase 8D is COMPLETED / CLOSED after its independent architecture/security
review passed with no critical, major, or required-fix findings. No image was
built and no container was started because the Docker daemon was unavailable.
Phase 8E is BLOCKED / NOT STARTED because the VPS has not yet been created.

## Container Model

`compose.yaml` builds one image and runs these fixed commands:

- `scheduler`: `python -m runtime.cli host run scheduler`
- `telegram`: `python -m runtime.cli host run telegram`
- optional profile `webhook-local`: `python -m runtime.cli host run webhook-local`

All services run as UID/GID `10001`, drop all Linux capabilities, set
`no-new-privileges`, use a read-only root filesystem plus bounded `/tmp`, and
share the local named volume mounted at `/var/lib/agent-company`. The volume is
the one canonical operational state backend. Multi-host Docker, Swarm,
Kubernetes, and distributed filesystems are unsupported.

The image entrypoint is the canonical Python CLI, not a shell. Compose uses
`init: true` so signals reach the Python process and child reaping does not
require an application supervisor. `restart: "no"` avoids an uncontrolled
crash loop. The six-minute stop grace period covers the current bounded
five-minute provider call plus coordinated lifecycle finalization; the runtime
itself never kills a persisted PID.

## Build And Configuration Validation

These commands validate configuration but do not start Telegram or providers:

```text
docker compose version
docker compose config
docker compose build
```

The build uses the repository-tested Python 3.14.3 official slim Bookworm image
by immutable multi-platform digest. The repository has no third-party Python
dependency manifest; the current runtime uses the standard library, so no
package installer or development dependency layer is added.

Docker build availability is separate from Compose syntax validation. Do not
install or start Docker merely to satisfy a test environment.

## Persistent State Initialization

Initialize the named volume once through the canonical host command:

```text
docker compose run --rm --no-deps scheduler host init
docker compose run --rm --no-deps scheduler host check
```

For a deterministic non-provider smoke after initialization:

```text
docker compose run --rm --no-deps scheduler host run scheduler --dry-run --max-cycles 1
```

`docker compose down` stops containers but preserves the named volume. Do not
use `docker compose down -v` unless destructive state deletion is separately
authorized and backed up.

## Provider Prerequisite

The base image intentionally installs no Codex or Claude CLI. The tracked
scheduler host configuration keeps `provider_execution_enabled` false, so a
normal non-dry scheduler start fails closed. CLI `--executor provider` cannot
override that gate.

Provider execution requires a separately reviewed Linux-compatible derived
image, an explicit non-secret host configuration enabling providers, and a
provider-specific credential mount. Mount only the selected provider directory
read-only where compatible - for example, the Codex directory at the canonical
root's `codex/` child—and never mount a host home directory or Windows
executable. Credential refresh/write access must be justified separately.
Provider environment construction remains default-deny and does not inherit
Telegram, webhook, or other-provider secrets.

## Telegram

Compose references `AGENT_COMPANY_TELEGRAM_BOT_TOKEN` by name only. Supply its
value at runtime and set `AGENT_COMPANY_REMOTE_CONFIG_FILE` to an ignored local
remote configuration before intentionally starting Telegram. The file is
mounted read-only; numeric identity authorization, private-chat restrictions,
replay protection, and the offset stored in the shared volume remain canonical.

`docker compose up telegram` is a live external operation and is not an
automated verification command. Notifications remain disabled in the container
host configuration.

## Webhook-Local

The service is behind the `webhook-local` profile, publishes no port, and keeps
the existing server bound to `127.0.0.1` inside its own container namespace.
Consequently it is process-local and is not ingress from the host or other
containers. Set `AGENT_COMPANY_WEBHOOK_CONFIG_FILE` to an ignored local config
and pass only the specific environment variables named by that config. HMAC,
replay, and provenance behavior are unchanged.

Public binding, port publication, a reverse proxy, DNS, and TLS belong to a
later explicitly reviewed deployment phase and are not enabled here.

## PID, Locks, Health, And Logs

Container PIDs are evidence only and are never used for cross-container
ownership or termination. Services share one local Docker-host volume, so the
existing kernel-backed file locks and owner tokens remain authoritative for
single-host singleton enforcement. Container names are not the safety control.

Each healthcheck runs inside its own service container. It reads only that
process's lifecycle record, lock state, and bounded heartbeat; it performs no
provider discovery, Telegram call, webhook mutation, job transition, approval,
or project write. It never treats PID visibility as liveness.

After an intentional live start, operators may inspect bounded local output:

```text
docker compose ps
docker compose logs scheduler
docker compose logs telegram
docker compose stop
docker compose down
```

## Explicit Exclusions And Phase 8E

Phase 8D includes no VPS, production server, systemd, Windows Service, Task
Scheduler, automatic supervisor daemon, host networking, host PID namespace,
Docker socket, privileged container, public webhook, DNS, TLS, reverse proxy,
Hermes, merge, or deployment authority. Target-host installation, credentials,
restart policy, firewall, backup/restore, and live smoke evidence remain Phase
8E or later work requiring separate review and human approval.

Before Phase 8E production use:

- build the pinned image on the target Linux architecture;
- perform an SBOM and vulnerability scan and verify or update the base-image
  digest where appropriate;
- verify fresh named-volume ownership and non-root `host init`;
- verify read-only-root and `/tmp` behavior;
- verify duplicate-process locking across containers;
- verify `docker stop` signal delivery, lifecycle final state after stop, and
  live health transitions;
- validate the derived Linux provider image and executable, provider-specific
  credential mount, provider authentication, and provider environment
  isolation; and
- perform live Telegram, provider, or public-ingress smoke tests only with
  separate explicit approval.

These runtime-validation items are Phase 8E prerequisites, not open Phase 8D
blockers.
