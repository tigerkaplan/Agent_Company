# Agent Company Project State

## Current Checkpoint

- Current Git HEAD is `ef498bd`. The working tree contains the Phase 8D Docker
  adaptation described below; it is not committed or deployed.
- Phase 6M, the Scheduler / Autonomous Run Loop, is the highest explicitly represented Phase 6 capability.
- No canonical Phase 6N subphase is defined.
- The runtime remains local-first, file-backed, and deliberately limited to one concurrent Worker.
- Phase 7 is completed and closed. The final repository-backed architecture and
  security review passed on 2026-09-24.
- Phase 8A architecture and threat-model design is COMPLETED / CLOSED under
  `infrastructure/`. The current baseline remains local; no deployment,
  operating-system service, running container, VPS, Hermes integration, or
  public webhook exposure exists.
- Phase 8B is COMPLETED / CLOSED. Its final independent re-review passed on
  2026-09-25 with no critical, major, or required-fix findings.
- Phase 8C is COMPLETED / CLOSED. Its final independent re-review passed on
  2026-09-25 with no critical, major, or required-fix findings.
- Phase 8D is COMPLETED / CLOSED. Its independent architecture/security review
  passed on 2026-09-25 with no critical, major, or required-fix findings.
- Phase 8E is NEXT / NOT STARTED.

## Phase 8A Architecture Design Checkpoint

Phase 8A produced the infrastructure architecture, host/process model,
persistent-state model, secrets model, Docker feasibility assessment, VPS
requirements, Telegram always-on design, webhook public-exposure boundary,
deployment and merge authority boundaries, Hermes evaluation, backup/recovery
design, threat model, acceptance criteria, and staged Phase 8 implementation
plan. Phase 8A performed no deployment and implemented none of those stages.

## Phase 8B Host Foundation

Phase 8B implements a strict non-secret host configuration, the canonical
`AGENT_COMPANY_STATE_ROOT` contract, fixed exact state paths, idempotent
`host init`, and read-only `host check`. Local development continues to use
ignored `runtime/state/` by default; host mode requires an explicit external
dedicated root such as `/var/lib/agent-company`. Broad roots, repository
ancestors, and non-canonical existing directories are rejected before any
creation or permission change. Existing local state is detected and reported,
never moved or copied. Provider subprocesses receive a default-deny,
provider-specific environment and credential home. Provider credentials,
optional host secret files, runtime state, and the repository must not overlap
in either direction. Malformed readiness configuration produces bounded FAIL
results; Windows ACL checks remain WARN pending operator validation.

Phase 8B created no process lifecycle. Phase 8C now supplies the bounded
foreground lifecycle contract described below, while still creating no
installed supervisor, systemd unit, Windows Service, deployment, Docker
container, VPS, Hermes component, public webhook listener, backup automation,
merge authority, or deployment authority. Host configuration controls
component eligibility only and grants no runtime authority.

## Phase 8C Process Lifecycle

Phase 8C defines only `scheduler`, `telegram`, and opt-in `webhook-local`.
Atomic process records under `host/processes/` use explicit lifecycle states,
bounded restart/failure metadata, and a host heartbeat separate from job
leases. OS-backed per-component locks prevent duplicate live owners and are
released by the kernel after a crash; stale active metadata is recoverable.
PID evidence is paired with a per-run owner token and start time, is never
trusted alone, and is never used to kill a process.

The host CLI provides read-only lifecycle status, fixed process selection,
foreground run commands, and a persisted graceful-stop request. It performs
Phase 8B readiness validation before startup. Scheduler runs through the
existing `SchedulerLoop`; Telegram reuses the existing long-poll transport and
offset state; optional webhook-local reuses the authenticated adapter and is
hard-bound to `127.0.0.1`. SIGTERM/SIGINT and `KeyboardInterrupt` request
graceful shutdown through notification-only signal callbacks and coordinated
normal control flow. Explicit provider CLI selection cannot override the host
provider disable flag. Startup inspection and new-owner publication are
serialized with stop requests so a successful request is not overwritten. No
automatic restart loop is present; a future supervisor must apply bounded
backoff and a burst cap.

## Phase 8D Docker Adaptation

Phase 8D adds one provider-neutral Linux image definition and fixed Compose
services for `scheduler`, `telegram`, and opt-in `webhook-local`. Every service
uses the existing `python -m runtime.cli host run ...` lifecycle, runs as UID
and GID 10001 with a read-only root filesystem, drops Linux capabilities, and
shares one named volume at `/var/lib/agent-company`. The image contains no
tracked secrets, runtime state, provider credentials, or provider CLI.

The scheduler configuration keeps provider execution disabled, so a normal
non-dry scheduler start fails closed until a separately reviewed derived image,
provider configuration, and read-only credential mount exist. Telegram accepts
its token only from the runtime environment. Webhook-local publishes no port
and remains bound to container-local `127.0.0.1`. Healthchecks read lifecycle,
lock, and heartbeat evidence only; they make no external or provider call and
do not treat a container PID as ownership proof. No image or container was
created because the local Docker daemon was unavailable.

Phase 8D did not add VPS deployment, systemd, a Windows Service, Task
Scheduler, a production restart supervisor, TLS, a reverse proxy, public
webhook ingress, Hermes, merge authority, deployment authority, production
provider installation, or live Telegram execution.

### Phase 8E Runtime Validation Prerequisites

The following are explicit Phase 8E prerequisites, not open Phase 8D blockers:

- build the pinned image on the target Linux architecture;
- perform an SBOM and vulnerability scan and verify or update the base-image
  digest where appropriate;
- verify fresh named-volume ownership and non-root `host init`;
- verify read-only-root and `/tmp` behavior;
- verify duplicate-process locking across containers;
- verify `docker stop` signal delivery, the final lifecycle state after stop,
  and live health transitions;
- validate the derived Linux provider image and executable, provider-specific
  credential mount, provider authentication, and provider environment
  isolation; and
- perform live Telegram, provider, or public-ingress smoke tests only with
  separate explicit approval.

## Social Media Capability Checkpoint

- Social Media owns channel-level content planning, individual content drafts,
  hooks, captions, calendars, repurposing, community signals, channel
  performance, social competitor monitoring, and weekly social reporting.
- Marketing retains strategy, positioning, campaigns, audience or customer
  analysis, market-level competitor analysis, and broader marketing priorities.
- `social_media` routes to the Social Media Agent through the `social-media`
  workflow and the provider-neutral `social_media_content` capability.
- Claude and Codex are configured as equally eligible at neutral weight. This is
  routing configuration, not an availability or quality claim.
- No real social API, connector, credential, scheduling, or publication action
  is implemented. Consequential external actions remain approval-gated.

## Committed

- Provider-neutral governance, canonical agents and skills, project onboarding, knowledge structure, hybrid provider routing configuration, and Phase 5 business agents, skills, workflows, and connector contracts.
- Canonical jobs, lifecycle, queue, attempts, retries, Worker, and Executor contracts.
- Phase 6B queue semantics and Phase 6D deterministic schedules.
- Phase 6E provider execution and Phase 6F independent review.
- Phase 6G persisted human approvals and Phase 6H controlled-write execution.
- Phase 6I controlled Git change sets and commits.
- Phase 6J separately approved push and pull-request creation.
- Phase 6M autonomous scheduling, claims, leases, heartbeat, retry backoff, restart recovery, audit state, and provider usage guards.
- Runtime schemas, provider runtime configuration, and supporting governance/documentation changes.
- Transport-independent remote commands with stable identity mapping,
  deny-by-default permissions, action/project-scoped authorization, persisted
  replay protection, durable mutation/reconciliation audit, and explicit
  command dispatch through canonical runtime surfaces.
- Telegram private-chat long polling and bounded proactive notification
  delivery for approval requested/resolved, job completion/failure, and
  runtime errors.
- Localhost-only authenticated webhook ingress with HMAC/timestamp/replay
  protection, canonical dispatch, durable provenance tombstones, and separate
  bounded audit records.
- Provider-neutral Social Media agent, skills, workflow, routing, provider
  capability configuration, schema support, and deterministic routing tests.

## Deferred

- Merge and deployment are not implemented and grant no runtime authority.
- Service installation, distributed execution, parallel provider execution, and broader connector execution remain outside the current local runtime.
- Non-blocking Phase 8C future hardening: a different-provider full-repository
  audit, real subprocess singleton-race validation, native Windows signal/ACL
  validation, and more race-resistant status-lock probing.
- Additional Phase 8B future hardening remains non-blocking: race-resistant
  directory-handle containment.
- Phase 8E runtime validation prerequisites remain pending and are recorded in
  the Phase 8D section above.

## Not Implemented

- Phase 8E is NEXT / NOT STARTED. VPS deployment, backup/recovery automation,
  target-host smoke testing, and final review remain later Phase 8 work.
- Operating-system supervisor installation, systemd, Windows Service, Task
  Scheduler integration, an automatic restart supervisor daemon, and forced
  process termination.
- Dedicated observability, metrics, or tracing implementation; `observability/` is absent.
- Phase 8 always-on hosting, TLS termination, public webhook hosting, a built or
  deployed Docker workload, VPS, Hermes, merge authority, deployment authority,
  and operating-system service installation.

## Runtime Limitations

- State is stored in local JSON files rather than a database or distributed queue.
- Scheduler execution is sequential with `max_concurrent_jobs = 1`.
- Provider execution uses explicitly selected local CLI adapters; executable detection does not prove authentication or service availability.
- Scheduler audit records and runtime artifacts provide local visibility, not a full observability platform.
- Telegram exposes only six permission-scoped commands in authenticated
  private chats. It has no task-submission, scheduler-mutation, filesystem,
  shell, Git, merge, release, or deployment command.
- Webhook ingress is authenticated machine input on loopback only. It creates
  approval-required jobs through canonical routing and cannot approve, queue,
  execute, write, select providers, or invoke Git.

## Verification

Verified on 2026-09-25 for the Phase 8B closure working tree:

- Targeted host/provider/action tests: 98 passed, 0 failed, and 0 skipped.
- Runtime tests: 469 passed, 0 failed, and 0 skipped.
- Python compilation: PASS for 105 files.
- Schemas: PASS for 16 JSON schemas parsed; runtime schema/model tests also passed.
- Git diff check: PASS.
- Secret and credential scan: PASS; no high-confidence hit was found in
  tracked or untracked non-ignored files.
- Provider runtime configuration: PASS for the Claude and Codex configurations.
- Generated-state and host-local configuration ignore rules: PASS for all 15
  Phase 8B probes.
- Architecture and security checks: PASS, including zero AST-detected
  `shell=True` calls, no project-specific business logic in runtime source, and
  no unexpected generated dirty paths.

Phase 8C final closure validation on 2026-09-25:

- Phase 8C lifecycle tests: 31 passed, 0 failed, and 0 skipped.
- Combined Phase 8C and Phase 8B host/provider/action tests: 129 passed, 0
  failed, and 0 skipped.
- Focused scheduler/Telegram/webhook regression: 155 passed, 0 failed,
  and 0 skipped.
- Full runtime regression: 500 passed, 0 failed, and 0 skipped.
- Python compilation: PASS for 107 files.
- JSON schema/config parsing: PASS for 21 files.
- Generated lifecycle state ignore checks: PASS for all 5 probes.
- Changed-file secret scan: PASS across 18 files with no high-confidence hit.
- Runtime/integration AST scan: PASS with zero `shell=True` calls.
- Git diff check: PASS.

The three independent-review blockers were repaired: provider enablement now
fails closed before discovery, OS signal callbacks are notification-only, and
startup publication is serialized with persisted stop requests. The final
independent re-review passed on 2026-09-25 with no critical, major, or
required-fix findings. Phase 8C is COMPLETED / CLOSED.

Phase 8D implementation validation on 2026-09-25:

- Targeted Docker tests: 12 passed, 0 failed, and 0 skipped.
- Focused Docker/host/provider/scheduler/Telegram/webhook regression: 232
  passed, 0 failed, and 0 skipped.
- Full runtime regression: 512 passed, 0 failed, and 0 skipped.
- Python compilation: PASS for 109 files.
- JSON schema/config parsing: PASS for 24 files.
- Compose configuration parsing: PASS; service, profile, and volume discovery
  matched the fixed design.
- Runtime/integration AST scan: PASS with zero `shell=True` calls.
- Docker build and live container smoke: UNAVAILABLE because the Docker daemon
  was not running; no daemon was installed or started.

The independent Phase 8D architecture/security review passed on 2026-09-25
with no critical, major, or required-fix findings. Phase 8D is COMPLETED /
CLOSED. Docker-daemon-dependent validation remains an explicit Phase 8E
prerequisite and does not reopen Phase 8D.

Phase 6 authority boundaries remain green, and Phase 7 is COMPLETED / CLOSED.
The Social Media capability checkpoint is COMPLETED / COMMITTED. Phase 8A is
COMPLETED / CLOSED and documentation-only. Phase 8B is COMPLETED / CLOSED after
its successful final independent re-review. Phase 8C is COMPLETED / CLOSED
after its successful final independent re-review. Phase 8D is COMPLETED /
CLOSED after its successful independent architecture/security review, and
Phase 8E is NEXT / NOT STARTED. A
different-provider full-repository audit and the other recorded
Phase 8C hardening items remain recommended future validation, not a mandatory
Phase 8 implementation gate.
