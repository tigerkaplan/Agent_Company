# Host Lifecycle

`runtime.host` owns host configuration, canonical state paths, readiness, and
Phase 8C process lifecycle only. It does not classify work, route business
tasks, approve or review work, invoke providers directly, mutate projects,
operate Git, merge, or deploy.

## Fixed Process Model

- `scheduler` wraps the existing `SchedulerLoop` and keeps its job leases,
  provider guards, recovery, and scheduler lock.
- `telegram` wraps the existing `TelegramTransport`; private-chat/numeric-ID
  authorization and persisted offsets are unchanged.
- `webhook-local` is disabled unless host configuration enables it. It reuses
  the authenticated webhook service and binds loopback only.

Lifecycle states are `STOPPED`, `STARTING`, `RUNNING`, `STOPPING`, and
`FAILED`. Atomic non-secret records live in `<state-root>/host/processes/`.
Each run holds an OS-backed lock in `<state-root>/locks/`. Lock release after a
crash permits recovery; stale `RUNNING` metadata is never treated as proof of a
live owner. PID, run token, and start time are evidence only. No PID is killed.

The host heartbeat is distinct from scheduler job-lease heartbeats. It updates
only lifecycle metadata. Errors and exit reasons are bounded. Status is
read-only and omits owner tokens and environment values.

## Commands

```text
python -m runtime.cli host init
python -m runtime.cli host check
python -m runtime.cli host processes
python -m runtime.cli host status
python -m runtime.cli host run scheduler
python -m runtime.cli host run telegram
python -m runtime.cli host run webhook-local
python -m runtime.cli host request-stop <process>
```

Runs fail closed when Phase 8B readiness fails, the component is disabled, a
required token/configuration is missing, provider mode has no available
executable, or another owner holds the singleton lock. Non-dry host scheduler
runs require provider execution, and explicit `--executor provider` selection
cannot override `provider_execution_enabled: false`; local-success/local-failure
remain test-only. Prior-state inspection and `STARTING` publication share the
lifecycle metadata transaction, so a successful concurrent stop request is
either consumed before startup or targets the newly published owner.

SIGTERM and SIGINT handlers only set an in-memory notification. Normal
coordinated lifecycle flow persists `STOPPING` and invokes the component stop
method after the handler returns and outside the metadata lock.
`KeyboardInterrupt` uses the same coordinated stop path. Windows console signal
delivery is limited by the launching terminal or future supervisor. No PID is
forcibly terminated.

No service definition or restart daemon is included. A future supervisor must
run one foreground command, preserve the same state root, use bounded
exponential backoff and a burst limit, send a graceful stop signal, and leave a
crash loop failed for operator action.
