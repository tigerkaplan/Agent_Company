# Agent Company Project State

## Current Checkpoint

- Current Git HEAD is `3f6acb6`, containing the committed CORE-01 Canonical
  Execution Result contract. It is not deployed.
- CORE-02 Continuation Policy is CLOSED / READY TO COMMIT after CORE-02R6 PASS.
  Its accumulated implementation and bounded repairs remain uncommitted.
- CORE-03 Eval Framework is NOT STARTED.
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
- Phase 8E is BLOCKED / PAUSED. Deployment has not started because the VPS has
  not yet been created.
- Phase 8F is NOT STARTED.

## CORE-01 Canonical Execution Result — COMPLETED / CLOSED

CORE-01 is a separate local core-runtime enhancement implemented on 2026-09-26
and is not a Phase 8 deployment stage. It extends the existing provider-neutral
`ExecutionResult` instead of creating a competing abstraction. The canonical
contract now records bounded status, structured evidence, artifact references,
concrete blockers, inert machine-readable next actions, explicit retryability,
existing execution/provider/timestamp/error metadata, and optional usage
metadata. Claude, Codex, future adapters, and local deterministic executors do
not own the format.

The execution-result status vocabulary is `succeeded`, `failed`, `blocked`,
`needs_review`, and `needs_human`; retryability remains separate descriptive
metadata and does not authorize Scheduler retry creation. `needs_review` enters
the existing independent Reviewer gate. `blocked` and `needs_human` remain
fail-closed without fabricating technical success or approval authority, and
`next_actions` never execute automatically. `artifacts` is the single canonical
artifact-reference field; `output_refs` is a derived compatibility alias and
conflicting inputs fail closed.

The initial independent CORE-01 review returned FIX with no Critical findings.
CORE-01F repaired its Major findings: canonical nested values are deeply
immutable, status invariants are exclusive, result retryability is separated
from job retry authority, actual schema bounds are enforced, error details and
secret handling are bounded, and persisted execution loading now returns a
validated typed `ExecutionResult`. Historical reads supply safe defaults and
bounded sanitization without rewriting source records.

The final independent re-review also returned FIX with no Critical findings and
five remaining Major findings. CORE-01F2 replaced the dict-subclass mapping with
a true immutable `Mapping`, added quoted JSON/config credential redaction,
bounded canonical integers to the signed 64-bit range while rejecting non-finite
floats, moved artifact-alias normalization before schema validation, and removed
the clean-import cycle through lazy package exports. JSON persistence now also
converts unexpected serialization failures into a controlled store error.

CORE-01R3 returned FIX with no Critical findings and four remaining Major
findings. CORE-01F3 now prevents ordinary backing-slot replacement or deletion,
normalizes only the artifact compatibility alias before strict new-record schema
validation, applies one signed-64 magnitude policy to integers and finite floats,
and converts serialization `OverflowError` into a sanitized atomic store error.
Historical defaulting remains confined to the explicit compatibility load path.

The final independent CORE-01 closure review returned PASS with no Critical or
Major findings. Final validation passed: 30 result-contract/adversarial tests,
131 focused execution/Worker/Reviewer/provider/Scheduler tests, 142 approval/
controlled-write/Git/remote-Git regression tests, the full 547-test runtime
regression, and 11 separate Reviewer adversarial probes. All 104 runtime Python
files compiled, 34 repository JSON files parsed, fresh-process import probes
passed, the production AST scan found zero `shell=True` calls, the production
credential-literal scan found zero findings, and `git diff --check` passed with
line-ending notices only. No live provider, network, or deployment call was
made. CORE-01 is COMPLETED / CLOSED and committed at `3f6acb6`.

## CORE-02 Continuation Policy — CLOSED / READY TO COMMIT

CORE-02 is a provider-independent deterministic continuation layer for explicit
pre-authorized job plans. Continuation means CONTINUE AUTHORIZED UNFINISHED
WORK; retry remains REPEAT FAILED WORK. The policy never derives authority from
provider prose, provider JSON, artifacts, retryability, or `next_actions`.

Bounded checkpoints are persisted atomically inside canonical job records and
retain the logical job ID, plan ID, immutable plan digest, continuation sequence, current step,
completed and remaining step IDs, latest execution/review references, and gate
state. Successful non-terminal steps reserve one deterministic child job through
the existing queue and Scheduler. Child identity binds logical job, plan digest,
sequence, and step. Exact-work fingerprints bind task, task class, canonical
agent, skill, workflow, material input references, review requirement, mode,
dry-run, risk, scope, logical root, plan identity and digest, continuation
sequence, current step, attempt, and the existing execution authority; they are
revalidated at approval, enqueue, claim, and execution boundaries. Reviewer and
human gates remain authoritative, including the distinct resolvable
direct-execution `RESOLVE_HUMAN_CONDITION` boundary; no recursive provider loop
was introduced.

Persisted execution results are reconciled before expired-lease retry recovery,
so an interrupted job/checkpoint update does not repeat an already-recorded
external execution. Reconciliation now requires a canonical request whose full
serialized identity matches the current job, resolved context, result, and
continuation checkpoint; missing or mismatched evidence blocks same-cycle
expired-lease retry. Ordered prefix/suffix and ancestry validation rejects
duplicates, reordering, skipped steps, task mismatch, unrelated roots,
self-parented retry, invalid attempt progression, lifecycle-inconsistent
parents, and sequence rollback. Scheduler status derives one authoritative
logical head with its latest attempt, current step, continuation sequence,
completed and remaining work, gate state, terminality, and final execution
reference where applicable, while retaining every ancestor step record as
historical evidence. Competing authoritative heads fail closed rather than
being resolved by tie-breaking.

The second independent CORE-02 re-review returned FIX with one Critical and
four Major findings. CORE-02F2 repaired only those findings: the five omitted
execution-material authorization fields are now bound; persisted request/result
identity is exact and requestless success cannot reconcile; the logical view
reports its latest attempt; retry and continuation ancestry/lifecycle rules fail
closed; and a resolved human condition retains and revalidates its exact
execution ID through resumed execution. That repair checkpoint did not close
CORE-02; another independent re-review was required.

The third independent CORE-02 re-review returned FIX with two Critical and
three Major findings. CORE-02F3 repaired only those findings: current-step
approval, review, execution-mode, dry-run, risk, and write-scope policy is
monotonic; persisted execution requests require every canonical serialized
field; competing continuation children fail closed; ordinary and continuation
retry ancestry rejects invalid lifecycle, progression, provenance, forks, and
cycles; and resumed human-condition execution requires matching authoritative
approval and execution-store artifacts. That repair checkpoint did not close
CORE-02; another independent re-review was required.

The fourth independent CORE-02 re-review returned FIX with one Critical
finding: a coordinated rewrite of the mutable embedded plan, its digest, and
the matching job-local policy could replace the originally authorized work.
CORE-02F4 repaired only that finding. Each logical continuation root now has
one write-once canonical authorized-plan record outside the mutable job record.
It retains the full ordered plan snapshot and its digest; every planned-job
load requires the current plan and checkpoint identity to match that snapshot.
Continuation children and retries reuse the root record, while missing,
changed, or recomputed authority fails closed without automatic refresh or
rebinding. That repair checkpoint did not close CORE-02; another independent
re-review was required.

The fifth independent CORE-02 re-review returned FIX with one Critical and one
Major finding. Deleting the authorized-plan anchor erased the store's only
write-once evidence, so ordinary creation could rebind downgraded work; the
store's handwritten validation also accepted plans rejected by canonical
schemas. CORE-02F5 repaired only those findings. Initial authority creation now
persists an independent full-record creation-evidence manifest before the
anchor. Evidence with a missing anchor is a durable recovery hold across
restart, and ordinary creation rejects both identical and modified replacement
plans. Anchor and evidence records are validated against the canonical
authorized-plan schema and shared job-plan definitions on creation and load,
with duplicate step IDs rejected by the same runtime semantic rule. That repair
checkpoint did not close CORE-02; another independent re-review was required.

CORE-02F3 validation passed: 53 focused CORE-02 tests, 81 CORE-02/Scheduler-loop
targeted tests, 333 focused CORE-02/CORE-01/Worker/Scheduler/Reviewer/approval/
controlled-write/Git/provider tests, and a clean full 602-test runtime-suite
rerun. The first full-suite run had one isolated Phase 8C host-process timing
failure; that test then passed four consecutive isolated reruns and the clean
full rerun. Python compilation passed. All 17 JSON schemas and the
JSON-compatible canonical lifecycle parsed; runtime configuration loader
coverage passed. The production AST scan found zero `shell=True` calls, the
changed-scope high-confidence secret scan found zero findings, and
`git diff --check` passed with line-ending notices only. No live provider,
network, commit, push, deployment, VPS, Phase 8F, CORE-03, or retry/stop-policy
work was performed.

CORE-02F4 validation passed: 57 focused CORE-02 tests, 107 CORE-02/Scheduler
targeted tests, 337 focused CORE-02/CORE-01/Worker/Scheduler/Reviewer/approval/
controlled-write/Git/provider tests, and the full 606-test runtime suite. The
exact coordinated R4 rewrite failed before executor delegation with zero
executor calls; individual approval, review, mode, dry-run, risk, scope, task,
input, step-ID, step-order, and digest mutations also failed closed. Python
compilation passed. All 18 JSON schemas and the JSON-compatible canonical
lifecycle parsed; runtime configuration loader coverage passed. The production
AST scan found zero `shell=True` calls, the changed-scope high-confidence secret
scan found zero findings, and `git diff --check` passed with line-ending notices
only. The known Phase 8C timing failure did not recur. No live provider,
network, commit, push, deployment, VPS, Phase 8F, CORE-03, retry/stop-policy, or
closure-reconciliation work was performed.

CORE-02F5 validation passed: 61 focused CORE-02 tests, 112 CORE-02/Scheduler
targeted tests, 342 focused CORE-02/CORE-01/Worker/Scheduler/Reviewer/approval/
controlled-write/Git/provider tests, and the full 611-test runtime suite.
Deletion followed by identical or modified ordinary creation remained in
recovery hold with zero executor calls; an actual Scheduler cycle claimed and
executed nothing. Malformed authority create/load matrices rejected missing,
empty, unexpected, duplicate, overlength, invalid-policy, invalid-digest,
timestamp, input, and scope cases, while valid restart/child/retry paths passed.
Python compilation passed. All 18 JSON schemas and the JSON-compatible
canonical lifecycle parsed; runtime configuration loader coverage passed. The
production AST scan found zero `shell=True` calls, the changed-scope
high-confidence secret scan found zero findings, and `git diff --check` passed
with line-ending notices only. No live provider, network, commit, push,
deployment, VPS, Phase 8F, CORE-03, retry/stop-policy, operator authority-
restoration flow, or closure-reconciliation work was performed.

CORE-02R6 independently re-ran the authority-loss, rebinding, store-validation,
Scheduler/Worker/gate, R5/R4, and CORE-01 regression checks and returned PASS
with no Critical, Major, or Minor findings. Validation passed: 61/61 CORE-02
tests, 112/112 CORE-02/Scheduler tests, 342/342 focused regression tests, and the
full 611/611 runtime suite. Python compilation, all 18 JSON schemas, the
JSON-compatible lifecycle, 19/19 runtime-loader tests, production `shell=True`
scanning, changed-scope high-confidence secret scanning, and `git diff --check`
also passed; the diff check emitted line-ending notices only.

CORE-02 closure reconciliation is complete. CORE-02 is CLOSED / READY TO COMMIT
and is not yet committed. CORE-03 Eval Framework is NOT STARTED. The aggregate
serialized-result byte ceiling remains FUTURE HARDENING / NON-BLOCKING.

Phase 8E remains BLOCKED / PAUSED; deployment has not started. Phase 8F remains
NOT STARTED.
CORE-01 performed no VPS, deployment,
service-installation, public-exposure, Hermes, Phase 8F, continuation-policy,
retry-policy, or Eval Framework work.

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

- Phase 8E is BLOCKED / PAUSED because the VPS has not yet been created;
  deployment has not started.
  VPS deployment, backup/recovery automation, target-host smoke testing, and
  final review remain later Phase 8 work.
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
Phase 8E is BLOCKED / PAUSED because the VPS has not yet been created, and
deployment has not started. A
different-provider full-repository audit and the other recorded
Phase 8C hardening items remain recommended future validation, not a mandatory
Phase 8 implementation gate.
