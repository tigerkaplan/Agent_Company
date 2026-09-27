# Continuation Policy

CORE-02 defines continuation as **CONTINUE AUTHORIZED UNFINISHED WORK**.
Retry remains **REPEAT FAILED WORK**. They are separate runtime concepts and
CORE-02 does not grant retry authority.

The canonical `ContinuationPolicy` decides only from an explicit persisted
`continuation_plan`, its deterministic SHA-256 plan digest, the job-embedded checkpoint, the normalized
`ExecutionResult` status, and resolved Reviewer or human-approval gates.
Provider prose, provider JSON, artifacts, `retryable`, and
`ExecutionResult.next_actions` have no continuation authority. In particular,
`next_actions` remains inert with `automatic: false`.

Approval authorizes exact work, not merely a capability or filesystem scope.
The authorization fingerprint binds task, task class, canonical agent, skill,
workflow, capability, project, input references, review requirement, risk,
execution mode/scope, plan digest, logical job, continuation sequence, current
step, and attempt. Provider selection remains outside approval identity so the
provider-neutral fallback policy can operate without changing canonical work.
The fingerprint is revalidated at approval resolution, enqueue, claim, and
immediately before Worker delegation. Changing any bound work requires a new
approval; the runtime never silently refreshes one.

The current plan step is also canonical policy, not advisory metadata. An
explicit step approval or review requirement cannot be weakened by mutable job
fields. Optional step mode, dry-run, risk, and scope policy is cross-validated
against the job; runtime policy may be stricter, but it cannot broaden scope,
lower risk, disable dry-run, or change the authorized execution mode.

The embedded plan and checkpoint digest are not self-authenticating authority.
When a logical continuation root is created, the runtime writes one immutable
authorized-plan record below the job store's `.continuation-authority/`
directory. Before that anchor is written, the runtime durably writes an
independent creation-evidence manifest containing the same canonical record.
Both records retain the full ordered plan snapshot and canonical digest and are
validated through the canonical authorization and job-plan schemas on creation
and load. Every planned-job load requires the anchor, creation evidence,
current full plan, and checkpoint digest to agree before policy, eligibility,
claim, review, approval, reconciliation, or execution may advance. Recomputing
a digest from a rewritten job does not update either authority record.

Creation evidence distinguishes a logical root that has never been authorized
from one whose anchor was lost. If evidence exists while the anchor is missing,
ordinary creation rejects both identical and modified plans and the logical job
remains in an explicit fail-closed recovery hold across restarts. Anchor loss is
not initialization, and no load, Scheduler, Worker, retry, continuation,
Reviewer, or approval path reconstructs it. No operator restoration flow is
defined by CORE-02.

The anchor and creation-evidence manifest are independent application records,
not cryptographic tamper proofing. Privileged deletion or coordinated mutation
of both records remains inside the documented trusted-local-state boundary;
CORE-02 does not claim operating-system protection against a privileged local
actor. Loss or corruption detectable from either retained record fails closed.

Each successful authorized step persists a bounded checkpoint in the canonical
job record. The checkpoint identifies the logical job, plan, sequence, current
step, completed and remaining step IDs, latest execution/review references, and
gate state. It contains references, not provider context dumps, credentials, or
hidden reasoning.

The checkpoint is validated as an ordered prefix/suffix of the authorized
linear plan. Duplicate, reordered, skipped, mismatched-task, unrelated-root,
sequence-regression, self-parented retry, invalid attempt, and lifecycle-
inconsistent ancestry states fail closed. Retry ancestry validation applies to
ordinary jobs as well as continuation jobs. Competing retry children and
competing continuation children for one canonical position are invalid rather
than resolved by status tie-breaking. Retry attempts reset only their
current checkpoint gate state to `active`; continuation sequence does not move.
Continuation children and retries reuse the logical root's same immutable
authorized-plan record; neither creates or refreshes plan authority.

When work remains, the runtime reserves one deterministic child job for the
logical-job/plan-digest/sequence/next-step boundary. That child retains the logical job
ID, names its continuation parent, and is queued through the existing Scheduler
and lease system. A step requiring approval enters the existing persisted
`EXECUTE_JOB` approval boundary and cannot be claimed first. Reviewer PASS may
enable a planned next step; Reviewer `NEEDS_HUMAN` must be explicitly resolved
before recovery can reserve it. A direct execution `needs_human` result enters
the distinct `RESOLVE_HUMAN_CONDITION` boundary. Resolving that condition
requeues only the exact incomplete step; it is not blanket execution approval.
Before eligibility, claim, and resumed execution, the compact job state is
authenticated against the persisted approved approval request and the matching
complete `needs_human` execution request/result artifact.

There is no recursive provider loop. Worker executes one job record at a time;
Scheduler or a later Worker invocation reconciles an already-persisted
execution result before lease expiry can create a retry. Reconciliation
requires a canonical request whose complete explicit serialized identity matches the
current job, resolved context, result, and continuation checkpoint. Missing or
mismatched fields fail closed before model defaults can be applied and suppress expired-lease retry for that
cycle. Scheduler then recovers a ready checkpoint and claims the persisted
child normally. Deterministic child identity makes recovery after a crash
idempotent, while a different job ID at the same canonical child position is an
invalid fork. Historical jobs without a continuation plan retain their
pre-CORE-02 terminal behavior, and unfinished work is never inferred from old
provider text.

Progress is not completion. A zero exit, success prose, one artifact, or one
completed step cannot complete the logical objective while canonical remaining
step IDs exist. Logical terminal success requires the authorized remaining set
to be empty after required review and approval gates are satisfied.

`JobRuntime.logical_statuses()` derives one authoritative head for each logical
job from retained step and retry evidence. Ancestors remain immutable historical
snapshots, but Scheduler status reports only the latest sequence and explicit
latest attempt as the current logical state.
