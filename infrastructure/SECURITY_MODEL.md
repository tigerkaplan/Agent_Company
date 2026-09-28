# Phase 8 Security Model

## Security Objective

Keep the existing single-host runtime continuously available without turning
hosting, supervision, a provider, a remote channel, or infrastructure tooling
into a new authority source.

The safe default is stopped or read-only when canonical state, identity,
credentials, approvals, provenance, or recovery evidence is missing or
ambiguous.

## Secret Model

Secrets covered by Phase 8 include:

- Telegram bot token;
- webhook HMAC signing secrets;
- provider CLI authentication material;
- Git and forge credentials;
- future external connector credentials.

Secrets must never enter Git, a Docker image or image layer, runtime JSON,
provider/review artifacts, logs, job content, command arguments, webhook audit,
notification state, or ordinary runtime backups.

### Options considered

| Option | Strengths | Risks / limits | Phase 8 use |
| --- | --- | --- | --- |
| Host environment | Simple and supported by current Telegram/webhook/provider paths. | Visible to the process and potentially to same-user/root diagnostics; shell profiles and process dumps can leak it. | Use only when injected by the supervisor from a protected source, never from an interactive shell history. |
| Docker env file outside the repository | Easy container wiring and keeps values out of the image. | Plaintext host file; values become container environment; careless Compose inspection or backup may expose them. | Acceptable only if Docker is later approved, with root-only permissions and exclusion from image/build context/backups. |
| Docker secrets | Mounted files reduce environment exposure and image risk. | Native behavior varies by deployment mode; current code expects environment values for some secrets. | Prefer later where the chosen Docker runtime supports it, after adding explicit file-secret adapters. |
| VPS secret store or mounted credential files | Central rotation/audit can be stronger; file mounts avoid broad environment propagation. | Vendor/runtime coupling and additional bootstrap authority. | Preferred future model when a concrete host secret service is selected. |

### Phase 8 MVP decision

Use a dedicated non-login service account and a root-owned `0600` secret file
outside the repository and persistent runtime root. The process supervisor reads
that file and injects only the variables required by each unit. Provider CLI
authentication remains in a separate `0700` credential home owned by the
service account. The runtime receives a provider-specific home path, not copied
tokens. Git/forge credentials use the narrowest repository/action scope and
remain external to Agent Company state.

Phase 8B provider adapters construct child environments from a default-deny
allowlist. Required path, operating-system, temporary-directory, home, and
locale variables are retained; only the selected provider's explicitly
allowlisted authentication variables are added. A configured credential root
maps to a distinct home for each provider. Telegram and webhook secrets,
arbitrary host/connector credentials, and another provider's private variables
are not propagated. Git and `gh` retain their separate existing execution
boundary.

This is the simplest safe first host model compatible with current code. Phase
8B host configuration may reference an external secret file, and `host check`
validates its location, presence, and POSIX `0600`-or-stricter mode without
reading or printing it. Current Telegram and webhook paths still consume only
their existing environment/config interfaces; a future supervisor must inject
only the variables each process needs. Docker/file-secret adapters
remain later work. Secret rotation restarts only the affected process after a
safe scheduler stop where needed. Errors report presence or missing
configuration, never values.

The tracked host example contains only non-secret eligibility flags and paths.
Secret-shaped fields are rejected. Provider execution, when enabled, requires a
separate credential root outside the repository and state root; its contents
are not inspected or copied. State, credential, repository, and secret-root
overlap is rejected in both directions. On POSIX, `host init` applies `0700`
only after dedicated-root validation succeeds. Windows ACLs are not managed or
treated as equivalent to POSIX permissions; checks always report WARN and
require operator validation rather than claiming equivalent enforcement.
Explicit host CLI executor selection cannot override a false
`provider_execution_enabled` flag and is rejected before provider discovery,
credential readiness inspection, or provider Worker construction.

## Identity And Authority

- The process supervisor authenticates no human and decides no work.
- Telegram authorization remains stable numeric platform identity mapped to a
  configured canonical human, private-chat-only delivery, exact command
  permission, exact project/action scope, and persisted replay evidence.
- Webhooks remain machine sources. HMAC source trust can create or recover an
  approval-required job but cannot be a human approver.
- Approval Runtime remains the only human decision surface. Reviewer output is
  evidence, not approval.
- Providers execute already-authorized packages. They cannot select policy,
  approve, invoke Git, merge, deploy, or expand mounted paths.
- CORE-04 tool discovery uses only explicit registration and canonical
  descriptor records stored as immutable tuple content, detached from caller
  and public-snapshot objects. Each authoritative boundary revalidates that
  content and derives its registry digest from the exact records used by
  discovery, selection, and loading; Python privacy, frozen dataclasses, and
  slotted attributes are not integrity boundaries. Shared credential-shape
  detection protects serializable tool evidence, and candidate selection
  validates each streamed item before consuming the next while retaining a
  strict bound. Descriptor-schema and runtime reference rules agree, followed
  by resolved-path containment beneath one trusted root. Discovery/loading
  performs no network discovery, directory scan, dynamic import, shell fallback,
  or tool invocation. Deferred loading returns selected inert data only;
  declared authority class is a requirement, not a grant.
- CORE-05 execution budgets use immutable policy plus separate creation
  evidence, atomically locked restart-safe usage, deterministic logical-job
  inheritance, monotonic in-process timing, and conservative crash recovery.
  Content-addressed immutable events and separate write-once sequence claims
  form one linear usage ledger committed before the verified high-water head
  and current-state cache. Every load validates the complete bounded chain from
  deterministic policy-bound genesis and rejects gaps, branches, duplicates,
  removal, replay, broken links, unexpected files, or content/storage-identity
  mismatch. Separate first-use evidence prevents deletion of post-genesis
  history from making a used budget appear fresh. Missing/malformed state,
  stale bindings, coherent current-state/head/event rollback, removed
  reservations, counter decrement, duplicate reservations, interrupted
  persistence, and clock rollback fail closed.
  Expected lock I/O failures produce canonical errors without unlocked fallback.
  Remaining capacity is not approval, review, continuation, retry,
  controlled-write, Git, or deployment authority, and provider output cannot
  change limits or usage. This is an application/runtime-layer integrity
  boundary; it does not claim protection from a privileged OS actor that can
  coherently replace or delete all policy, creation, first-use, ledger, head,
  and state evidence.
- Commit, push, and pull-request creation remain separate persisted actions.
  Merge, release, and deployment remain absent.

## Network Boundary

The Phase 8 MVP has no public application listener.

- Telegram uses outbound HTTPS long polling; no inbound Telegram port exists.
- The webhook adapter stays disabled or bound to loopback only.
- Administrative SSH is key-only, restricted by firewall/source policy, and
  separate from application identity.
- Outbound access is limited to required DNS, NTP, Telegram, provider, package,
  and Git endpoints where practical.
- A future public webhook requires the separately authorized TLS/reverse-proxy
  boundary in `HOST_ARCHITECTURE.md`; opening port 443 alone is not approval.

## Filesystem And Process Boundary

- One dedicated service account owns runtime state and only the explicitly
  mounted project roots required for approved work.
- Canonical application files are read-only to runtime processes except when a
  separately approved controlled-write scope targets an external project.
- State and project filesystems are distinct. Credential paths are distinct
  from both and excluded from normal state backups.
- One scheduler and one Telegram poller are allowed per canonical state root.
- One optional loopback webhook process is allowed per canonical state root.
- Local file locks, atomic replacement, leases, and persisted dedupe are
  required. They are not distributed coordination.
- Phase 8C singleton enforcement uses kernel-released local file locks. PID is
  evidence only and is paired with an owner token and process start time; the
  lifecycle layer never kills a PID or trusts PID identity alone.
- OS signal callbacks set only an in-memory event. Coordinated lifecycle flow
  performs metadata persistence and component shutdown outside the callback.
- Startup holds the singleton lock before serializing prior-state inspection,
  pending-stop handling, and new-owner publication under the lifecycle metadata
  lock. A successful stop request is never overwritten by startup.
- Lifecycle status omits owner tokens and secrets. Errors are bounded, and
  host heartbeats never mutate jobs, leases, approvals, or routing state.
- Containerization, if used later, is defense in depth only. It does not replace
  controlled-write validation, approval, or host hardening.

## Deployment Authority Boundary

Production deployment is a new consequential action and requires a future
canonical action model. Its minimum binding is the immutable artifact digest,
target host/environment, configuration fingerprint excluding secret values,
exact migration/backup plan, health check, rollback plan, reviewer evidence,
expiry, and human actor.

The action sequence is plan, independent review, exact human approval,
allowlisted deployment, and persisted evidence. An approval for a job, write,
commit, push, or pull request cannot satisfy it. Provider output cannot create,
approve, or invoke it. Phase 8A/8B implement none of this sequence.

## Backup Security And Recovery Safety

- Backup required: jobs and execution evidence, approvals, schedules and
  scheduler state, remote audit/replay and Telegram offset, notification state,
  webhook provenance/tombstones and retained audit, and Git/PR evidence.
- Backup optional: expendable retained logs and bounded history only where the
  canonical design permits recreation. Transient locks, atomic-write temporary
  files, and caches are excluded.
- Secrets and provider credential homes are excluded from ordinary state
  backup. Phase 8B classifies these boundaries; Phase 8F owns automation.
- Encrypt backup contents and transport; store copies outside the VPS failure
  domain with access separate from the runtime service account.
- Exclude Telegram/webhook/provider/Git secrets and provider credential homes.
- Include authority and dedupe evidence together: jobs, executions, approvals,
  schedules, scheduler state, remote audit, Telegram offset, notifications,
  webhook provenance/tombstones, and Git/PR evidence.
- Record snapshot time, application revision, schema version, and a manifest of
  file hashes without secret values.
- Test restore into an isolated host with outbound network and provider actions
  disabled.
- An older snapshot enters recovery hold. It must not resume provider execution,
  Telegram/webhook ingress, notifications, Git actions, or deployment until an
  operator reconciles possible external progress.
- Continuation authority uses a write-once anchor plus independent creation
  evidence. Loss or mismatch detectable from either retained record enters
  recovery hold; ordinary runtime paths cannot recreate authority. These local
  records are not cryptographic tamper proofing: a privileged actor able to
  delete or coordinate changes to both remains inside the trusted-local-state
  boundary and requires host controls, backup evidence, and operator response.

## Threat Model

| Threat | Prevention | Fail-safe behavior | Residual risk |
| --- | --- | --- | --- |
| Host compromise | Patched minimal OS, dedicated account, restrictive permissions, key-only administration, firewall, egress restriction, external secrets, encrypted backups. | Stop services, revoke SSH/provider/Telegram/Git credentials, preserve evidence, rebuild from pinned artifact, restore into recovery hold. | Root compromise can read active process memory, credentials, state, and mounted projects. Rebuild and credential rotation are mandatory. |
| Leaked VPS or control-panel credentials | Unique hardware-backed/MFA-protected account where available, no shared keys, short key rotation, restricted administrator list. | Disable host/network, revoke access, rotate keys and secrets, inspect provider and Git audit trails. | Provider control-plane compromise may bypass guest firewall or snapshots. |
| Exposed webhook port | Adapter refuses non-loopback bind; host firewall denies application ports; no public unit in MVP. | Stop webhook unit and firewall the port; reject unsigned, stale, oversized, or unknown events without dispatch. | A future reverse proxy creates denial-of-service and proxy-trust risk even with HMAC. |
| Leaked environment secret | Supervisor injection from root-owned file, no shell profiles, redaction, bounded errors, no environment dumps or secret backup. | Disable affected connector/provider and rotate immediately; state remains authoritative without delivery. | Root/same-service-account inspection and process memory can reveal active values. File-secret support reduces but does not remove host-compromise risk. |
| Container escape or false isolation assumption | Non-root image, no privileged mode or Docker socket, minimal capabilities, read-only application mount, narrow state/project mounts. | Treat container compromise as host incident; stop, revoke, rebuild. | Docker does not create an approval or controlled-write boundary; kernel/runtime flaws remain. |
| Persistent state loss or corruption | Durable local filesystem, free-space checks, atomic writes, quiesced encrypted snapshots, hash manifests, restore drills. | Stop startup or enter recovery hold; never create replacement empty authority state over missing state. | Backup RPO can lose recent dedupe/approval evidence; safe reconciliation may require human investigation or abandonment of uncertain work. |
| Restart duplication | Singletons, leases, deterministic attempts, remote command replay records, Telegram offset, notification dedupe, webhook provenance/tombstones, Git action evidence. | Wait for lease expiry, reconcile canonical state, and fail closed on missing/mismatched evidence. | Telegram responses and provider consumption may repeat across a crash window even when approval and canonical job mutation do not. |
| Runaway provider usage | Single worker, per-cycle and persisted daily provider limits, timeouts, bounded retries, supervisor restart limits, explicit provider mode. | Stop claims when limit is reached; stop the unit after a crash loop; require operator action to resume. | Current counters govern scheduler provider runs, not every possible manual CLI invocation. Phase 8 host policy must prevent unsupervised provider commands and later consider a global budget. |
| Uncontrolled restart loop | Phase 8C persists bounded restart/failure metadata and performs readiness preflight; a future supervisor must add exponential delay and a burst cap. | The host CLI never restarts forever; leave the process failed and require operator action. | A future supervisor configured without the documented cap could still consume provider/API capacity. |
| Provider CLI credentials | Dedicated credential home, least privilege, no tokens in arguments/state/image, disabled providers by default, credential rotation. | Provider becomes unavailable and jobs fail or wait through canonical policy; no fallback may weaken approval or mode. | Provider CLI internals may store broad tokens or emit sensitive diagnostics; versions and redaction require review. |
| Git or forge credentials | Fine-grained repository/action scope, protected branches, exact remote/branch binding, disabled prompting, separate commit/push/PR approvals, no merge method. | Authentication failure is terminal for that action; stale remote evidence blocks mutation. | A stolen push credential may permit actions outside Agent Company. Server-side branch protection remains necessary. |
| Remote code/path exposure | No public runtime API, fixed provider/Git arguments, `shell=False`, explicit project mounts, staged controlled writes, protected paths, bounded payloads. | Reject unknown routes, paths, modes, commands, and provider sandbox mismatch; keep target unchanged. | Provider processes operate with service-account rights; current Windows controlled-write sandbox has not been ported to Linux/container. |
| Public ingress request flood | No public ingress in MVP; future proxy must enforce body, connection, method, path, and rate limits before localhost service. | Shed/reject traffic before dispatch and preserve accepted provenance capacity. | Volumetric attacks may exhaust upstream/network resources and need provider-level protection. |
| Malicious or stale backup | Encrypted authenticated storage, hash manifest, revision/schema binding, restricted restore authority, isolated restore validation. | Refuse mismatched or unverifiable backup; do not start runtime against it. | A privileged attacker able to replace both backup and manifest may still create plausible stale state. |

## Required Security Evidence Before Production

- Full runtime and new lifecycle/recovery tests pass on the target OS.
- No public socket exists except explicitly approved administrative access.
- Filesystem permissions and service-account ownership are captured.
- Secret scans cover repository, image layers, runtime state, logs, and backup
  manifest samples.
- Restart, crash-loop, full-disk, corrupt-state, lease-expiry, Telegram replay,
  webhook recovery, notification dedupe, and old-backup recovery-hold tests pass.
- Provider and Git credentials are demonstrably least-privilege and revocable.
- Docker, if used, passes a separate Linux controlled-write and mount review.
- Deployment and rollback evidence is exact and human-approved.
- Independent security review returns `PASS`; otherwise production use remains
  blocked.
