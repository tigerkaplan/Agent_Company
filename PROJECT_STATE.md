# Agent Company Project State

## Current Checkpoint

- CORE-04 implementation commit `35f03f8` contains the Tool Discovery /
  Deferred Loading implementation and closure state. It is not deployed.
- CORE-01 Canonical Result Contract is COMPLETED / CLOSED and committed at
  `3f6acb6`.
- CORE-02 Continuation Policy is COMPLETED / CLOSED after CORE-02R6 PASS and is
  committed at `9d5ead1`.
- CORE-03 Eval Framework is COMPLETED / CLOSED / COMMITTED at `80ead22` after
  CORE-03R5 PASS with no Critical, Major, or Minor findings.
- CORE-04 Tool / Skill Discovery is CLOSED / COMMITTED at `35f03f8` after CORE-04R5
  PASS with no Critical, Major, or Minor findings.
- CORE-05 Time / Execution Budget is CLOSED / COMMITTED at `63813b5` after
  CORE-05R3 PASS with no Critical, Major, or Minor findings.
- CORE-06 Retry / Stop Policy is CLOSED / COMMITTED at `4a6e5c4` after
  CORE-06R6 PASS.
- CORE-07 Progress Events is CLOSED / COMMITTED at `6bcffa4` after CORE-07R3
  PASS with no Critical, Major, or Minor findings. CORE-01-10 are CLOSED /
  COMMITTED. CORE-08 is committed at `1a1b029` after CORE-08R3 PASS;
  CORE-09 is committed at `fa7e30f` after CORE-09R2 PASS. CORE-10 is
  CLOSED / COMMITTED at `dd72cb2` after CORE-10R3 PASS; CORE-11 is NEXT / NOT STARTED.
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
- Phase 8E is PAUSED / BLOCKED. Deployment has not started because the VPS has
  not yet been created.
- Phase 8F is NOT STARTED.
- Phase 8G and Phase 8H are NOT STARTED.

## SYNC-05 Consolidated Architecture / Scope Freeze - 2026-10-01

Verified baseline HEAD `c31d392b30d57ccbbc4900a12a4eae1ee97721f9`, branch
`master`, clean starting tree. ACTIVE: None. NEXT: CORE-11 External Content
Isolation / NOT STARTED. CORE-01-10 remain CLOSED / COMMITTED; CORE-10 was
committed at `dd72cb2a8f5ff12b87e2238ee9b2925fa7596b8e` after CORE-10R3 PASS.
Recorded R3 results (46/46 targeted, 161/161 focused, 1153/1153 full runtime)
and closure rerun (56/56) below are historical evidence, not tests rerun here.
`runtime/isolation/` remains absent. Canonical agent directories with role and
guardrail definitions confirm 10 implemented agents; the frozen V1 target is 14,
with Finance & Pricing, Analytics, Content, and Design still planned.

V1 architecture discovery and scope freeze are ACTIVE. ROADMAP owns the additive
SYNC-04/04A/05 accepted refinements, exception criteria, unchanged V1 completion
definition, and DOC-GOV-01 health checks. CAP-CREATIVE-01 is accepted architecture
and non-blocking; CAP-SOC-01 retains its bounded V1 subset; CAP-DOC-01,
summary-indexed/long-document refinements, local inference, and fine-tuning
remain POST-V1 / LATER / REFERENCE as classified there.

This sync changes existing documentation only. Runtime/context/cache READMEs
now reflect CORE-10 CLOSED / COMMITTED and CORE-11 NEXT / NOT STARTED; dated
review and closure evidence is preserved. No runtime implementation, agent,
phase, checkpoint, installation, planned directory, root HANDOFF, commit, or
push is authorized or started by this reconciliation. CORE-11 must enter the
normal Build lifecycle through a separate task. STOP after documentation checks.

## DOC-TREE-CORE10 Post-Commit Reconciliation

Verified clean starting tree at `dd72cb2` on 2026-10-01. CORE-01-10 are
CLOSED / COMMITTED; CORE-10 commit is `dd72cb2`; CORE-11 is NEXT / NOT STARTED.
The CURRENT implementation is `runtime/compute_policy/` (`__init__.py`,
`policy.py`, `canonical.py`, and `README.md`), supported by
`runtime/tests/test_compute_policy.py`. The former planned
`runtime/compute-policy/` label is superseded and physically absent.
README CURRENT paths were checked against the filesystem; all target paths
remain PLANNED and physically absent, including `runtime/isolation/`.
Phase 8E-8H and the approved V1 scope remain unchanged. This reconciliation
changes documentation/state only; no runtime tests were rerun, future folders
created, commit made, or CORE-11 work begun.

## CORE-10 Compute / Effort Policy - CLOSED / COMMITTED at `dd72cb2`

Implemented against `3e71adc` and committed at `dd72cb2`. `runtime/compute_policy/`
provides deterministic FAST / STANDARD / DEEP / CRITICAL effort selection,
repository/context-bound exact request identity, bounded trusted routing inputs,
security-first provider eligibility, explicit budget blocking, and replayable
reason/evidence output.
ProviderExecutor evaluates before context/provider execution and passes the
eligible set through existing capability, mode, weight and fallback routing.
The decision is guidance and observation evidence, never execution authority.
Codex and Claude enforce native effort controls; unsupported adapters are
rejected. No DEC-01/JEV or CORE-11 work is included.
See `runtime/compute_policy/README.md` for defaults, trust boundaries and limits.
CORE-10R3 final decision on 2026-10-01: PASS — READY FOR CORE-10 CLOSURE.
The independent reviewer reported no Critical, Major, or Minor findings;
repository identity, documentation, and other CORE-10 guarantees all passed.
R3 recorded 46/46 CORE-10 tests, independent filesystem probes, 161/161 focused
regressions, and 1153/1153 full runtime tests; `git diff --check` passed.
The separate reviewer role used the same provider and made no modifications
or commits. Source: R3 final review in session
`01a0f785-5cef-7f21-93db-7c2ff85b24fc` at 2026-10-01 16:48:42 UTC.

Historical CORE-10C closure reconciliation: CLOSED / READY TO COMMIT; implementation and
closure documentation were uncommitted against HEAD `3e71adc`.
Closure-time validation passed `python -m unittest runtime.tests.test_compute_policy -q`:
56/56 tests (46 CORE-10 tests plus 10 imported adapter tests), and
`git diff --check`. Status/diff inspection confirmed documentation-only closure
edits, unchanged runtime/schema source hashes, and no `runtime/isolation/`.
CORE-01-09 remain CLOSED / COMMITTED; CORE-11 remains NOT STARTED.
DEC-01/JEV and runtime behavior are untouched by this reconciliation.

Historical initial executor validation on 2026-10-01 passed: 37/37 CORE-10 targeted tests;
245/245 focused compute/result-contract/provider/Worker/Reviewer/cache/budget
tests; and 1134/1134 full discovered runtime tests, including all 1097 existing
tests. The final full suite was partitioned by complete modules into groups of
368, 368 and 367 tests, followed by the 31 host-process tests in isolation.
The runner asserted complete, non-overlapping module coverage. `git diff
--check` passed; HEAD remains `3e71adc` and no commit was made.

An earlier sequential full run found one evidence-order regression: existing
provider-output evidence must remain first. Compute observations now append to
that evidence, and the affected result-contract tests and final full suite pass.
An earlier interrupted attempt also emitted Windows `WinError 5` in an existing
host-process concurrency test; both isolated host-suite reruns passed. No host
implementation was changed. These historical executor checks were not independent review or closure;
the R3 PASS and CORE-10C closure above supersede that checkpoint.
CORE-11 remains NOT STARTED.

## CORE-09 Context / Prompt Cache Policy - CLOSED / COMMITTED at `fa7e30f`

Committed at `fa7e30f`. `runtime/cache/` provides
bounded process-local, provider-neutral context-only reuse integrated into
`ExecutionContextBuilder`. Fresh discovery precedes every hit. Exact work,
project/root/user scope, selected skill metadata, options, policy, content, and
source provenance bind reuse. Cached and fresh packs satisfy the same canonical
contract and must have exactly equivalent serialized bytes. Source, skill, and
policy changes invalidate reuse; TTL, LRU, entry-count, and byte bounds apply.
Missing/invalid sources fail closed. Authority metadata is reconstructed from
the current request. No persisted cache, Phase 9C Operating Layer, or CORE-10
work is introduced. See
`runtime/cache/README.md` for identity, outcomes, bounds, and limitations.

Historical initial executor validation passed: 31/31 CORE-09
tests; 147/147 combined CORE-09/context/provider/Reviewer tests; 534/534 existing
CORE regressions; 287/287 focused Worker/Scheduler/Reviewer/approval/action/Git/
provider/job-runtime regressions; and 1085/1085 final full runtime tests in
733.596 seconds, with no failures, errors, or skips. All 162 runtime/integration
Python files and 32 schema/catalog JSON files parsed successfully. New-file
whitespace and `git diff --check` passed. These are implementation checks, not
independent-review closure.

### CORE-09R1 finding and CORE-09F1 bounded repair

R1 returned FIX with one required Minor finding: cached material with boolean
or float `start_line` compared equal to fresh integer material and could enter
a provider package as HIT / validated. No Critical or Major findings were
identified. The two nonblocking timestamp/accounting robustness observations
remain outside this single-finding repair.

CORE-09F1 applies one canonical validation/serialization helper to both fresh
and cached packs. It requires exact pack/material fields and primitive types,
reconstructs materials through the canonical model, enforces assembly bounds,
rejects duplicate/noncanonical representations, and compares exact serialized
bytes before HIT. Malformed stored material is discarded as STALE / malformed;
only fresh validated context reaches the builder. Identity, TTL/LRU, isolation,
authority boundaries, and fresh discovery remain unchanged.

At the F1 checkpoint, CORE-09 remained uncommitted at `ecd975c` and awaited
independent re-review. CORE-10 was NOT STARTED.

2026-10-01 F1 executor validation passed: 43/43 CORE-09 tests; 159/159 combined
CORE-09/context/provider/Reviewer tests; 469/469 existing CORE regressions;
and 1097/1097 full runtime tests, with no failures, errors, or skips. The
boolean/float corruption reproductions failed before repair and passed after
repair, including the provider-package path. All 162 runtime/integration Python
files and 32 schema/catalog JSON files parsed; repair-file whitespace and
`git diff --check` passed. These were implementation checks before R2.

### CORE-09R2 independent re-review and closure

2026-10-01 CORE-09R2 returned PASS with no Critical, Major, or Minor findings.
Independent adversarial probes rejected malformed cached fields and nested
values, noncanonical pack shapes, and serialization mismatches as STALE; valid
unchanged material still HIT. Provider-builder probes confirmed that corrupted
context does not reach provider packages and current request authority is
preserved. Cache identity, project/task/scope isolation, source/skill/policy
invalidation, TTL/LRU/bounds, and fresh discovery on hits remained intact.
Cache content grants no approval, review, retry, continuation, budget, write,
tool, Git, or deployment authority. R2 validation passed 43/43 CORE-09 tests,
159/159 affected context/provider/Reviewer tests, 469/469 existing CORE
regressions, and 1097/1097 full runtime tests; `git diff --check` passed.
At the R2 closure checkpoint, CORE-09 was CLOSED / READY TO COMMIT and
uncommitted at `ecd975c`. It is now CLOSED / COMMITTED at `fa7e30f`.
At that committed checkpoint, CORE-01-09 were CLOSED / COMMITTED; CORE-10
was NEXT / NOT STARTED and CORE-11 was NOT STARTED.

## Historical Post-CORE-08 Documentation / Master Context Reconciliation

Verified implementation HEAD: `1a1b029` (`feat: add context discovery`), with
an initially clean working tree. CORE-01-08 are CLOSED / COMMITTED;
CORE-09 is NEXT / NOT STARTED; CORE-10-11 are NOT STARTED.
`README.md` owns DOC-TREE; `ROADMAP.md` owns accepted capability scope;
`TODO.md` mirrors outstanding work. The CURRENT context/index support is
physically implemented; advanced Code Intelligence and CORE-09+ remain planned.

This documentation-only reconciliation uses the approved SYNC-04 and SYNC-04A
requirements in the current human instruction. The SYNC documents are external
Build & Reviews architecture/roadmap context, not repository artifacts; repository
evidence remains the implementation source of truth.
Missing refinements and CAP-SOC-01 are recorded in ROADMAP without duplicating
canonical agents or runtime capability registrations. CAP-SOC-01 is PLANNED /
NOT STARTED; its Social Media HQ belongs to Phase 9B. Agent count remains
10 current / 14 V1 target. Target paths remain absent; no future folders were
created. Phase 8E-8H status and prerequisites are unchanged. No runtime tests
are rerun for this documentation-only reconciliation; prior results below are
historical evidence, not new validation.

## CORE-08 Context Discovery Before Action - CLOSED / COMMITTED

Committed at `1a1b029` after CORE-08R3 PASS. CORE-09 is
NEXT / NOT STARTED. Provider execution assembles
bounded, provenance-bearing context before calling the adapter. Canonical
request identity and authority remain unchanged. The implementation adds
metadata-first skill discovery and selected-only instruction loading,
provider-neutral skill/context ranking contracts with deterministic defaults,
read-only knowledge/memory interfaces, material clarification records,
conservative capability fallback, selective verbatim retention, and an explicit-root
repository index with Python syntax relationships. See `runtime/context/README.md`
for contracts, defaults, integration, and limitations.

No general connector execution, memory persistence, cache, new agent, Git action,
deployment, or CORE-09 work was introduced. Windows-safe filesystem identity
is shared by validation, exclusions, and deduplication. Every catalog-registered
instruction path is digest-validated before entering a context pack, including
selected, required, inherited, ordinary file, and repository-index selections.
Context remains evidence only and grants no execution, write, approval, retry,
continuation, budget, plan, Git, or deployment authority.

### Historical CORE-08R3 final independent review and CORE-08C closure - before commit

R3 returned PASS - READY FOR CORE-08 CLOSURE with no Critical, Major, or Minor
findings. Independent adversarial probes rejected stale registered
`docs/playbook.md` through direct file input, required context, repository
discovery/indexing, and `ExecutionContextBuilder`. Selected/required/inherited
checks, Reviewer inheritance, Windows aliases and junction protection, catalog
shape checks, ordinary file discovery, provenance, and authority neutrality
passed. Review used a separate same-provider reviewer; no cross-provider review
was performed.

R3 validation passed 65 CORE-08 tests and 51 provider/Reviewer tests (116 combined),
408 focused/existing regressions, and 1054 full runtime tests with zero failures,
errors, or skips. Additional independent adversarial probes passed. All 159
Python files compiled; 31 schemas and the skill catalog parsed;
`git diff --check` passed.

CORE-08C reconciles documentation only. CORE-01-07 remain CLOSED / COMMITTED;
CORE-08 is CLOSED / READY TO COMMIT and remains uncommitted at `b620cee`;
CORE-09 is NOT STARTED. Fresh CORE-08C targeted validation passed 65/65 tests;
`git diff --check` and status/diff inspection passed. Only the six documentation
files changed during closure; runtime and test content remained unchanged.
Historical implementation and repair evidence follows.

### Historical CORE-08 initial implementation - before R1

Implementation validation on 2026-09-30:

- CORE-08: 44 tests passed. The combined CORE-08, provider/reviewer, and two
  canonical-denial regression reproductions passed 97/97.
- Focused tool/Worker/approval/write/Git/continuation/budget/retry/progress
  regression: 408/408 passed.
- Full runtime regression after the final repair: 1033/1033 passed, with no
  failures, errors, or skips.
- Python compilation: 159 files passed. Schema/catalog JSON parsing: 32 files
  passed. Production AST checks found no `shell=True` calls. Diff check passed.

The initial full run exposed two canonical-denial regressions: intercepting
`ContextBuildError` bypassed the existing trusted failure contract. These were
repaired by reserving `ContextDiscoveryBlocked` for explicit material questions
or unresolved capabilities while preserving existing canonical denials. A
separate CORE-07 race test reported `BrokenBarrierError`; it passed unchanged
in isolation, in the complete 75-test progress suite, and in the final full
regression. No CORE-07 runtime or tests were modified. Earlier dated records
remain historical evidence. CORE-08 is ready for independent review, not closed
or committed.

### Historical CORE-08 R1 findings and CORE-08F1 bounded repair - before R2

R1 returned FIX with two Major findings (Windows path aliases bypassing
deduplication/exclusions and required skill references bypassing catalog
freshness) and one Minor finding (non-object catalog entries allowing duplicate
fields to collapse). Its existing full regression passed 1033 tests; adversarial
probes exposed the findings despite that result.

CORE-08F1 repairs only these findings. Validated filesystem identities are shared
by index visitation/exclusions, context deduplication, and skill instruction
lookup. Trailing-dot/space path components fail closed. Required/inherited skill
instructions, including the Reviewer's executor-skill evidence, use catalog
digest validation. Catalog entries must be JSON objects and duplicate keys
remain rejected. Ten direct adversarial tests cover the repairs and preserve
actual Windows junction rejection. No authority contract was changed.

CORE-08 remains IMPLEMENTED / pending independent re-review, uncommitted at
`b620cee`. CORE-09 has not started. F1 executor validation is not review closure.

F1 validation: 54 CORE-08 tests passed (10 new adversarial tests); the combined
CORE-08/provider/Reviewer suite passed 105 tests; the focused protected regression
passed 408 tests; and the full runtime regression passed 1043 tests with no
failures, errors, or skips. All 159 runtime/integration Python files compiled,
all 32 schema/catalog JSON files parsed, and `git diff --check` passed.

### Historical CORE-08 R2 finding and CORE-08F2 bounded repair - before R3

R2 returned FIX with one Major finding: catalog-registered instructions outside
the loader's naming conventions could bypass freshness validation. Its full
regression passed 1043 tests, but four additional adversarial tests reproduced
the bypass through file inputs, required context, indexing, and the provider
context builder.

CORE-08F2 removes that naming dependency. Local file discovery reads the bounded
catalog metadata once when present and checks each selected file's canonical
identity against its registrations. Registered instructions use the existing
digest validator regardless of pathname or source label. Unselected instruction
bodies stay unloaded. Ordinary files work without a catalog; malformed or
unreadable catalogs fail closed. No authority contract or CORE-09 work changed.

The four R2 reproductions failed before the fix and passed afterward. CORE-08
remains IMPLEMENTED / pending independent re-review, uncommitted at `b620cee`.

F2 validation: 65 CORE-08 tests passed, including 11 new tests; the combined
CORE-08/provider/Reviewer suite passed 116 tests; the focused protected regression
passed 408 tests; and the full runtime regression passed 1054 tests with no
failures, errors, or skips. All 159 runtime/integration Python files compiled,
all 32 schema/catalog JSON files parsed, and `git diff --check` passed.
These are executor results, not independent review closure.

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

## CORE-02 Continuation Policy — COMPLETED / CLOSED

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

CORE-02 closure reconciliation is complete. CORE-02 is COMPLETED / CLOSED and
committed at `9d5ead1`. The aggregate serialized-result byte ceiling remains
FUTURE HARDENING / NON-BLOCKING.

Phase 8E remains PAUSED / BLOCKED; deployment has not started. Phase 8F remains
NOT STARTED.
CORE-01 performed no VPS, deployment,
service-installation, public-exposure, Hermes, Phase 8F, continuation-policy,
retry-policy, or Eval Framework work.

## CORE-03 Eval Framework — COMPLETED / CLOSED / COMMITTED

CORE-03 is the first canonical provider-independent evaluation layer. It adds a
separate `EvalSpec`, `EvalResult`, and structured check-result contract without
changing `ExecutionResult.status` or creating an Eval Agent. A spec binds one
exact execution/job pair to a canonical evaluator identity/version and an
ordered set of bounded checks. A result distinguishes `pass`, `fail`, and
`error`, retains machine-readable checks and evidence references, and leaves
numeric score null for the deterministic milestone.

The explicit registry implements the CORE-01 contract check, expected status,
required evidence, required artifacts, forbidden conditions, and allowlisted
structured field matching. Contract evaluation reuses the canonical CORE-01
schema/model validator. Unregistered evaluator names, malformed configuration,
malformed execution input, and invalid persisted evals fail closed; no dynamic
import, arbitrary code, shell command, file execution, or provider invocation is
available from EvalSpec input.

Logical eval identity retains SHA-256 digests of the exact EvalSpec, exact
supplied ExecutionResult payload, and deterministic semantic result content.
The `eval-<32 hex>` ID is derived from that compact identity material;
`created_at` is excluded. Model, validation, persistence-create, and load
boundaries all verify the result digest and claimed ID. Typed atomic JSON
persistence lives under `executions/evals/`, safely deduplicates the same
semantic result, rejects identity collisions or tampering, and never overwrites
a different historical result. The runtime CLI supports `eval run`, `eval
list`, and `eval show` against persisted execution evidence.

CORE-03 shares CORE-01's canonical secret-key and credential-shape detection.
Structured field matching distinguishes missing fields from present nulls, and
its comparisons remain allowlisted and type-strict. Aggregate result evidence
is a deterministic ordered summary capped at 100 unique references while every
check retains its complete bounded local evidence.

Eval remains descriptive measurement evidence only. PASS cannot approve work,
complete Reviewer workflow, authorize continuation or retry, clear a CORE-02
recovery hold, mutate a job or authorized plan, invoke Git, deploy, or convert
provider prose into authority. CORE-03 is COMPLETED / CLOSED / COMMITTED at
`80ead22` after CORE-03R5 PASS. At that closure checkpoint, CORE-04 had not
started.

CORE-03 initial implementation validation passed: 24/24 targeted eval tests, 30/30
CORE-01 result-contract tests, 61/61 CORE-02 continuation tests, 359/359 focused
Worker/Scheduler/Reviewer/approval/controlled-write/Git/provider regressions,
and a clean full 635/635 runtime-suite rerun. One earlier full rerun and one of
three immediate isolated repeats hit the already documented Phase 8C timing
test `test_i4_stop_after_start_publication_targets_new_owner`; two isolated
repeats and the clean full rerun passed, and no CORE-03 path touches that host
process code. All 116 runtime Python files compiled; all
20 JSON schemas and the JSON-compatible lifecycle parsed; 68/68 host
configuration/lifecycle loader tests and a fresh eval/CLI import probe passed.
The production AST scan found zero `shell=True` calls, the changed-scope
high-confidence credential-pattern scan found zero findings, stale current-state
CORE-02/CORE-03 markers were absent, and `git diff --check` passed with
line-ending notices only. No live provider, external network, deployment, push,
PR, commit, external-system mutation, or CORE-04 work was performed.

CORE-03R1 returned FIX with four Major findings and no Critical findings.
CORE-03F repaired only those findings: persisted identity now verifies exact
input digests and deterministic result semantics; CORE-01 and CORE-03 share one
secret-detection policy; field matching distinguishes missing from null; and
aggregate evidence is a bounded summary without dropping check-local evidence.
Repair validation passed: 33/33 targeted eval tests, including 9/9 dedicated
repair tests; 30/30 CORE-01 tests; 61/61 CORE-02 tests; 359/359 focused runtime
regressions; and the full 644/644 runtime suite. All 117 runtime Python files
compiled, all 20 JSON schemas and the JSON-compatible lifecycle parsed, 68/68
host configuration/lifecycle loader tests passed, and fresh eval/CLI imports
succeeded. Production `shell=True` scanning found zero findings. CORE-03 remains
IMPLEMENTED / pending independent re-review; it is not closed. No live provider,
external network, deployment, push, PR, commit, external-system mutation, or
CORE-04 work was performed.

CORE-03R2 returned FIX with one remaining Major finding: a typed result from an
injected evaluator was not structurally bound to its originating check. The
CORE-03F2 bounded repair treats evaluator output as untrusted structured data,
revalidates every typed check result, and binds `check_id`, `evaluator_type`,
and `severity` to the originating `EvalCheckSpec` before aggregation. Any
malformed or identity-substituted output becomes a deterministic canonical
`error` for the original check, so only normalized output reaches semantic
identity and persistence. CORE-03 remains IMPLEMENTED / pending independent
re-review; it is not closed. CORE-04 remains NOT STARTED.

CORE-03F2 validation passed: 8/8 dedicated repair test methods covering all 12
required adversarial cases, 41/41 CORE-03 tests, 30/30 CORE-01 tests, 61/61
CORE-02 tests, 292/292 focused runtime regressions, and the full 652/652 runtime
suite. Host configuration/lifecycle validation passed 68/68; all 117 runtime
Python files compiled; all 20 JSON schemas and the JSON-compatible lifecycle
parsed; eval/CLI imports succeeded; and production `shell=True` and
high-confidence credential scans found zero findings. No live provider,
external network, deployment, push, PR, commit, external-system mutation, or
CORE-04 work was performed.

CORE-03R3 returned FIX with one remaining Major finding: an injected evaluator
could directly raise the runner's private output-validation exception and make
untrusted exception text cross the canonical error boundary. CORE-03F3
structurally separates evaluator invocation from runner-owned post-return
validation. Every evaluator-originated exception now maps to a fixed canonical
error for the original check, while the private validation exception is trusted
only when runner validation creates it after evaluator return. Raw exception
text is excluded from semantic identity and persistence. CORE-03 remains
IMPLEMENTED / pending independent re-review; it is not closed. CORE-04 remains
NOT STARTED.

CORE-03F3 validation passed: 4/4 dedicated evaluator-exception repair tests,
44/44 CORE-03 tests, 30/30 CORE-01 tests, 61/61 CORE-02 tests, 292/292 focused
runtime regressions, and the full 655/655 runtime suite. Explicit normalized
error persistence and Eval CLI tests passed 2/2; host configuration/lifecycle
validation passed 68/68; all 117 runtime Python files compiled; all 20 JSON
schemas and the JSON-compatible lifecycle parsed; and eval/CLI imports
succeeded. Production `shell=True`, high-confidence credential, and Eval
dangerous-API scans found zero findings. No live provider, external network,
deployment, push, PR, commit, external-system mutation, or CORE-04 work was
performed.

CORE-03R4 returned FIX with one remaining Major finding: the runner passed
canonical check and context objects directly to injected evaluator code, then
reused those evaluator-visible objects as trusted error, identity, and evidence
inputs. CORE-03F4 canonicalizes typed specs into new runner-owned models and
gives every evaluator invocation a disposable reconstructed check and isolated
context. Error construction, returned-output identity checks, later evaluators,
semantic identity, and persistence now use only untouched runner-owned values.
Evaluator-side mutation of check identity, execution references, payloads, or
canonical results cannot mutate caller input or cross the normalized error
boundary. CORE-03 remains IMPLEMENTED / pending independent re-review; it is
not closed. CORE-04 remains NOT STARTED.

CORE-03F4 validation passed: 5/5 dedicated mutable-input trust-boundary tests,
49/49 CORE-03 tests, 30/30 CORE-01 tests, 61/61 CORE-02 tests, 292/292 focused
runtime regressions, and the full 660/660 runtime suite. Explicit normalized
error persistence and Eval CLI tests passed 2/2; host configuration/lifecycle
validation passed 68/68; all 117 runtime Python files compiled; all 20 JSON
schemas and the JSON-compatible lifecycle parsed; and eval/CLI imports
succeeded. Production `shell=True`, high-confidence credential, and Eval
dangerous-API scans found zero findings. No live provider, external network,
deployment, push, PR, commit, external-system mutation, or CORE-04 work was
performed.

CORE-03R5 independently re-reviewed the CORE-03F4 trusted-snapshot isolation
repair and returned PASS with no Critical, Major, or Minor findings. It verified
that evaluator-side mutation cannot alter runner-owned check identity, execution
references, payloads, later evaluator inputs, normalized errors, semantic
identity, persistence identity, or caller-owned input. Independent validation
passed: 5/5 dedicated mutation probes, 49/49 CORE-03 tests, 30/30 CORE-01 tests,
61/61 CORE-02 tests, 292/292 focused runtime regressions, the full 660/660
runtime suite, 2/2 normalized-error persistence and Eval CLI tests, and 68/68
host configuration/lifecycle tests. All 117 runtime Python files compiled; all
20 JSON schemas and the JSON-compatible lifecycle parsed; eval/CLI imports and
production `shell=True`, high-confidence credential, and Eval dangerous-API
scans passed.

CORE-03 closure reconciliation changed canonical status documentation only. No
runtime behavior, tests, schemas, live provider, external network, deployment,
push, PR, commit, external-system mutation, or CORE-04 work was performed.
At that pre-commit checkpoint, CORE-03 was CLOSED / READY TO COMMIT and CORE-04
remained NOT STARTED. CORE-03 was subsequently committed at `80ead22`; CORE-04
was then the next allowed checkpoint.

## CORE-04 Tool Discovery — CLOSED / COMMITTED

CORE-04 adds a provider-independent runtime capability under `runtime/tools/`;
it does not create a Tool Discovery Agent or alter agent, skill, workflow, or
provider routing. Immutable `ToolDescriptor` metadata records stable identity,
exact capabilities, authority/risk requirements, compatibility, availability,
status, tags, preference, and trusted-root-relative definition/schema
references. `ToolDiscoveryRequest` applies bounded capability and policy
constraints. `ToolDiscoveryResult` records deterministic candidates,
match/ineligibility evidence, bounded rejections, an immutable registry digest,
and registered/considered/matched/selected/loaded counts.

`ToolRegistry` performs explicit registration only. It validates compact
descriptor schemas, rejects duplicate IDs and conflicting versions, and stores
canonical serialized records as immutable tuple content detached from
caller/public descriptor objects. Every authoritative boundary revalidates that
content and derives the registry digest from it; separately replaceable trusted
record/digest slots do not exist. Public snapshots reconstruct disposable
descriptor views. Ordering is deterministic: selectable state, least additional
capability exposure, preference rank, fixed tool-class order, stable tool ID,
then version. A canonical `no_match` result never invents a tool or falls back
to shell access. Selection is separate and recomputes discovery against the
canonical state, so callers and providers cannot promote hidden, unavailable,
ineligible, or mutated tools. Selection validates each iterable item immediately
and stops at the first unknown or duplicate ID or at the request bound plus one.
Required-capability schema and runtime bounds are both 20, and shared canonical
secret detection rejects credential-shaped serializable tool text.

`ToolDefinitionLoader` loads only selected JSON definitions and schemas. It
enforces normalized resolved-path containment beneath one trusted root, bounded
files, fixed definition-schema validation, a bounded local JSON Schema subset,
and exact descriptor/load identity. Non-selected definitions are not read and
non-selected schemas are not parsed. Loaded definitions are inert immutable
data with an opaque adapter ID; there is no dynamic import, callable, execution,
network discovery, filesystem scan, shell fallback, or provider-created tool.

Candidate, selected, loaded, and authorized remain distinct. Discovery/loading
cannot approve work, complete Reviewer decisions, continue or retry jobs, clear
recovery hold, authorize controlled write, invoke Git, deploy, or change CORE-01,
CORE-02, or CORE-03 semantics. Evidence remains ephemeral in immutable result
objects because it changes no job or authority state; no CORE-09 cache or new
persistence store was introduced.

CORE-04R1 returned FIX for exposed-descriptor mutation, missing shared secret
detection, a 100-versus-20 required-capability bound mismatch, and eager
selection-iterable materialization. CORE-04F repaired only those findings:
private canonical serialized records now anchor registry state and digest,
public descriptors are disposable reconstructions, serializable tool strings
reuse shared credential detection, schema/runtime required-capability bounds
are both 20, and selection rejects overflow after at most the bound plus one
item.

CORE-04F validation passed: 28/28 CORE-04 deterministic/adversarial tests,
including five focused repair probes and the 100-registered/one-selected
deferred-loading proof; 30/30 CORE-01,
61/61 CORE-02, and 49/49 CORE-03 regression tests; 287/287 focused Worker,
Scheduler, Reviewer, Approval, controlled-write, Git, remote-Git, provider, and
job-runtime regressions; and the full 688/688 runtime suite. The separate host
configuration/lifecycle set passed 68/68. All 130 runtime/integration Python
files compiled; 23 JSON schemas and the JSON-compatible lifecycle parsed; fresh
tool/CLI/provider/Worker imports passed; and production `shell=True`, high-
confidence credential, and dangerous dynamic-import/tool-loading scans found
zero findings. Final `git diff --check` passed with line-ending notices only.
No live provider, external network, deployment, push, PR, commit, external-
system mutation, or CORE-05 work was performed. At that repair checkpoint,
CORE-04 was IMPLEMENTED / pending independent re-review and CORE-05 was NOT
STARTED.

CORE-04R2 returned FIX for coordinated replacement of former registry
record/digest/snapshot slots, descriptor-reference schema/runtime disagreement,
and delayed rejection of unknown streamed selection IDs. CORE-04F2 repaired only
those findings: registry and snapshot canonical records are now structurally
immutable tuple content whose digest is derived at every authoritative boundary;
selection and loading fail closed on malformed or stale state; descriptor schema
and runtime reference validation agree for normal, traversal, absolute, URL,
mixed-separator, empty, and overlength cases; and selection rejects unknown and
duplicate IDs at the exact streamed item where encountered. Python privacy,
frozen dataclasses, and slotted attributes are explicitly not claimed as an
integrity boundary.

CORE-04F2 validation passed: 31/31 complete CORE-04 tests, including all three
bounded-repair adversarial tests and the retained deferred-loading proof; 30/30
CORE-01, 61/61 CORE-02, and 49/49 CORE-03 regression tests; 287/287 focused
Worker, Scheduler, Reviewer, Approval, controlled-write, Git, remote-Git,
provider, and job-runtime regressions; and the full 691/691 runtime suite. The
separate host configuration/lifecycle set passed 68/68. All 130
runtime/integration Python files compiled; 23 JSON schemas and the
JSON-compatible lifecycle parsed; runtime-loader initialization and fresh
tool/CLI/provider/Worker imports passed; and production `shell=True`,
high-confidence credential, dangerous dynamic-import/tool-loading, and
executable network-use scans found zero findings. The broad network-text scan's
only match was the inert fixed JSON Schema dialect URI. Final `git diff --check`
passed with line-ending notices only. No live provider, external network,
deployment, push, PR, commit, external-system mutation, or CORE-05 work was
performed. At that repair checkpoint, CORE-04 was IMPLEMENTED / pending
independent re-review and CORE-05 remained NOT STARTED.

CORE-04R3 returned FIX with one Minor schema/model/runtime parity finding: the
descriptor JSON Schema accepted 29 prohibited C0 control characters in deferred
definition/schema references that the runtime model rejected. CORE-04F3 changed
only the shared descriptor reference schema pattern and its parity coverage.
Both reference fields now reject U+0000-U+0008, U+000B-U+000C, and
U+000E-U+001F at schema and runtime layers, including after an explicitly
permitted newline; ordinary nested references and the existing tab, newline,
and carriage-return semantics remain accepted.

CORE-04F3 validation passed: the dedicated exhaustive F3 test and existing path
matrix passed; an independent 126-check parity probe passed; 32/32 complete
CORE-04 tests, 30/30 CORE-01, 61/61 CORE-02, 49/49 CORE-03, 287/287 focused, and
692/692 full runtime tests passed. The host configuration/lifecycle set passed
68/68. All 130 runtime/integration Python files compiled; 23 JSON schemas and
the JSON-compatible lifecycle parsed; runtime-loader initialization and fresh
tool/CLI/provider/Worker imports passed; and production `shell=True`,
high-confidence credential, dangerous dynamic-import/tool-loading, and
executable network-use scans found zero findings. The only broad network-text
match remained the inert fixed JSON Schema dialect URI. `git diff --check`
passed with line-ending notices only. No live provider, external network,
deployment, push, PR, commit, external-system mutation, or CORE-05 work was
performed. At that repair checkpoint, CORE-04 was IMPLEMENTED / pending
independent re-review and CORE-05 remained NOT STARTED.

CORE-04R4 returned FIX with one Minor LF-boundary parity finding: the remaining
backslash, colon, and traversal schema lookaheads used dot scans that stopped at
LF, while `$` treated a final LF differently from runtime path segmentation.
CORE-04F4 changed only the shared descriptor reference pattern and parity tests.
All relevant lookaheads now scan the entire string with an all-character class,
and terminal dot segments use an explicit no-character-remains assertion. The
runtime's existing TAB, LF, CR, relative-directory, and dot-in-filename policy
was not changed.

CORE-04F4 validation passed: the dedicated table-driven LF test and retained
reference/control tests passed; an independent sweep compared 16,195 reference
values across both fields (32,390 schema/runtime checks) with zero mismatches;
33/33 complete CORE-04 tests, 30/30 CORE-01, 61/61 CORE-02, 49/49 CORE-03,
287/287 focused, and 693/693 full runtime tests passed. The host
configuration/lifecycle set passed 68/68. All 130 runtime/integration Python
files compiled; 23 JSON schemas and the JSON-compatible lifecycle parsed;
runtime-loader initialization and fresh tool/CLI/provider/Worker imports passed;
and production `shell=True`, high-confidence credential, dangerous
dynamic-import/tool-loading, and executable network-use scans found zero
findings. The only broad network-text match remained the inert fixed JSON Schema
dialect URI. `git diff --check` passed with line-ending notices only. No live
provider, external network, deployment, push, PR, commit, external-system
mutation, or CORE-05 work was performed. At that repair checkpoint, CORE-04 was
IMPLEMENTED / pending independent re-review and CORE-05 remained NOT STARTED.

CORE-04R5 independently re-reviewed the final LF-boundary repair and returned
PASS with no Critical, Major, or Minor findings. It confirmed zero mismatches
across 100,000 independently generated schema/runtime reference comparisons,
all 29 prohibited C0 controls, aligned TAB/LF/CR and exact dot-segment
semantics, trusted-root resolved-path containment, canonical registry/digest
integrity, exact-item streaming rejection, shared secret handling, genuine
selected-only deferred loading, six-field descriptor/load identity binding,
inert loaded definitions, provider neutrality, and unchanged authority
boundaries. R5 independently passed 33/33 CORE-04 tests, 30/30 CORE-01 tests,
61/61 CORE-02 tests, 49/49 CORE-03 tests, 287/287 focused regressions, 693/693
full runtime tests, and 68/68 host/lifecycle tests. It compiled 130 Python
files, parsed 23 JSON schemas and the JSON-compatible lifecycle, passed loader
and import probes, found zero production `shell=True`, credential/private-key,
dynamic-import, or executable tool-layer network findings, and passed
`git diff --check` with line-ending notices only.

CORE-04 closure reconciliation changed canonical status documentation only; it
did not change runtime behavior, tests, or schemas and did not rerun or replace
the R5 full-regression evidence above. At that pre-commit checkpoint, CORE-04
was CLOSED / READY TO COMMIT and CORE-05 was NOT STARTED. No live provider,
external network, deployment, push, PR, commit, or external-system mutation was
performed during closure.

CORE-04 implementation, repairs, tests, schemas, and closure documentation were
subsequently committed at `35f03f8` (`feat: add tool discovery and deferred
loading`). At that committed CORE-04 closure checkpoint, CORE-04 was CLOSED /
COMMITTED and CORE-05 was NEXT / NOT STARTED; CORE-05 could not become active
until the post-commit state reconciliation was committed and the working tree
was verified clean.

CORE-05 subsequently began only after that reconciliation was committed and
the clean working tree was verified at `6d681d3`.

## CORE-05 Time / Execution Budget — CLOSED / COMMITTED

CORE-05 adds a small provider-independent runtime capability under
`runtime/budget/`. An optional immutable policy bounds active elapsed
milliseconds and/or Worker-to-Executor execution units for one logical job.
Unset dimensions are distinct from a configured zero. Runtime/model/schema
bounds reject booleans, negative values, unknown dimensions, oversized values,
malformed identity, and noncanonical persisted state.

Policy creation writes independent durable creation evidence before the policy
anchor and binds both to a deterministic logical-job budget ID and SHA-256
digest. Usage persists separately through atomic replacement under a local
budget lock. Admission and reservation are one serialized operation, so two
workers cannot spend the last unit. Reservation consumes the unit before
reference resolution or Executor delegation; duplicate execution identities do
not charge twice and cannot authorize a second call.

Active time begins after exact job authority validation and successful
reservation, immediately before reference resolution, and ends immediately
after the Executor returns or raises. In-process measurement uses a monotonic
clock. Raw monotonic values are never persisted. Queue, schedule, approval,
Reviewer, human, continuation-pause, and post-execution lifecycle time do not
count. Restart recovery conservatively charges any active reservation through
the trusted persisted wall-clock recovery observation. Persisted usage never
decreases, and detected clock rollback latches a fail-closed fault rather than
increasing remaining capacity. CORE-05 denies new starts after exhaustion but
does not forecast duration or force-kill in-flight work.

The initial job, ordinary retry children, and CORE-02 continuation children
retain one exact budget binding and accumulate usage without reset. Budget
availability is never sufficient authority: it cannot approve, complete
Reviewer work, create continuation or retry authority, clear recovery hold,
authorize controlled write or Git, or deploy. Provider requests to increase,
reset, or reinterpret budget have zero canonical effect. Exhaustion fails the
claimed job with structured evidence and zero Executor calls; it fabricates no
successful `ExecutionResult`, retry, or continuation.

CORE-05 intentionally defines no token/cost accounting, monetary policy,
provider-rate limiting, retry/stop decision semantics, progress events, effort
routing, dashboard, unsafe force-kill, operator budget mutation, or separate
tool-call dimension. CORE-04 discovery/loading consumes no unit, and a future
tool-call counter requires a canonical tool-invocation boundary that does not
exist in the current runtime.

Initial implementation validation passed 24/24 CORE-05 deterministic and
adversarial tests, including exact-limit concurrency, duplicate identity,
crash/restart, continuation/retry inheritance, rollback, malformed state,
provider mutation, and authority-boundary cases. CORE-01 passed 30/30, CORE-02
61/61, CORE-03 49/49, and CORE-04 33/33 within the clean 717/717 full runtime
suite. The focused Worker, Scheduler, Reviewer, Approval, controlled-write,
Git, remote-Git, provider, and job-runtime set passed 484/484. All 135
runtime/integration Python files compiled; 25 JSON schemas and the
JSON-compatible lifecycle parsed; lifecycle/runtime-loader and fresh import
probes passed; production `shell=True` and high-confidence credential scans
found zero findings; and `git diff --check` passed with line-ending notices
only.

CORE-05R1 subsequently returned FIX for two bounded defects: a coherent rewrite
of the single mutable usage-state file could restore consumed capacity, and
ordinary lock-path/open `OSError` cases could escape the canonical error
boundary. CORE-05F repaired only those findings. Usage state now advances under
the budget lock through a store-managed sequence, append-only digest-chained
evidence, an independent high-water head, and then the current state. Evidence
binds the immutable policy, unit and elapsed high-water values, complete
reservation-history digest, and complete state digest. Old-state replay,
coherent zero/reset, partial decrement, removed charged identities, evidence
tampering, and interrupted evidence/head/state ordering fail closed. Expected
lock initialization/open/acquisition failures now become deterministic
canonical budget errors without raw OS detail, unlocked fallback, budget
mutation, or Executor/provider calls.

Bounded-repair validation passed 36/36 CORE-05 tests, including 12 repair tests,
496/496 focused regressions, and 729/729 full runtime tests. The preserved
CORE-01/02/03/04 groups passed 30/30, 61/61, 49/49, and 33/33. All 135 Python
files compiled; 26 JSON schemas and the JSON-compatible lifecycle parsed;
runtime-loader/import probes passed; production `shell=True`, credential, and
budget path/traversal scans found no issue; and `git diff --check` passed with
line-ending notices only.

CORE-05R2 then returned FIX for two remaining bounded defects: authoritative
loads checked only the current event and its immediate predecessor rather than
the complete chain to genesis, and a coordinated rewrite of mutable state,
head, and current event with recomputed public digests could restore capacity.
CORE-05F2 repairs only those defects. Each transition now persists a
content-addressed immutable event and an independent write-once sequence claim.
Every load deterministically validates the bounded, linear claim/event history
from exact policy-bound genesis through the derived current event, rejecting
missing or unexpected artifacts, gaps, duplicate sequences, branches, broken
links, content-address mismatch, historical corruption, and state/head drift.
Write-once first-use evidence also prevents a previously used budget from being
accepted as fresh genesis after later ledger loss. Mutable head and state are
verified caches, not historical authority.

Second bounded-repair validation passed all 23 F2-specific tests and 59/59
CORE-05 tests, including the exact coherent zero-unit, zero-elapsed, combined,
current-event redigest, old-snapshot, genesis-rebind, full-chain tamper, crash,
restart, idempotency, and concurrency cases. The named focused regression set
passed 524/524 and the full runtime suite passed 752/752. The preserved
CORE-01/02/03/04 groups remained 30/30, 61/61, 49/49, and 33/33 within those
runs. All 135 Python files compiled; 27 JSON schemas and the JSON-compatible
lifecycle parsed; runtime-loader/import probes passed; production `shell=True`,
high-confidence credential, and budget path/traversal scans found no issue;
and `git diff --check` passed with line-ending notices only.

CORE-05R3 independently returned `PASS — READY FOR CORE-05 CLOSURE
RECONCILIATION` with no Critical, Major, or Minor findings. It verified the
59/59 CORE-05 target, the protected CORE-01 through CORE-04 suites (30/30,
61/61, 49/49, and 33/33), all 524 focused logical tests, all 228 complementary
tests, all 752 current cases, compilation of 135 Python files, parsing of 27
schemas and lifecycle manifests, zero forbidden-pattern scan hits, and exact
cross-process `ALLOW` / `DENY` behavior. Two transient local Git subprocess
timeouts in the aggregate run passed on isolated rerun.

CORE-05 closure reconciliation is complete. CORE-05 is CLOSED / READY TO COMMIT
and remains uncommitted. CORE-06 is NOT STARTED. No live provider, external
network, deployment, push, PR, commit, or external-system mutation was
performed.

CORE-05 implementation, repairs, review evidence, and closure documentation
were subsequently committed at `63813b5` (`feat: add time and execution
budget`). At this post-commit checkpoint, CORE-05 is CLOSED / COMMITTED;
CORE-06 is NEXT / NOT STARTED; CORE-07 through CORE-11 are NOT STARTED.

## Historical Post-CORE-05 Documentation / Roadmap / Repository Tree Checkpoint

The post-commit repository tree contains the committed CORE-05 implementation
at `runtime/budget/`; the repository uses that singular path. No CORE-06 through
CORE-11 implementation directory exists. The current canonical agent count is
10, and the accepted V1 target is 14 after later addition of Finance & Pricing,
Analytics, Content, and Design.

`ROADMAP.md` now records the accepted V1 sequence after CORE-01 through CORE-11:
GOV-01 and GOV-02, ORCH-01 Graph Execution Runtime, MEM-01 through MEM-03,
agent and capability expansion, Phase 9A through 9C, DEC-01 and the bounded
DEC-02 JEV pilot, Phase 8E through 8H completion, and Brightshore as the first
Phase 10 production Project Pack. These are planned, not implemented. JEV,
SEO/AEO/GEO, Memory, and named tools or patterns are not canonical agents.

`README.md` is the canonical repository-tree summary. It separates current
physical paths from absent future target paths and records the DOC-TREE policy:
structural implementation is followed by validation, review, closure, commit,
repository-tree audit, and documentation reconciliation. This checkpoint
created no future directories and changed no runtime behavior.

## Historical Post-CORE-07 Documentation / Master Context Sync

Implementation HEAD is `6bcffa4` (`feat: add progress events`). This documentation
sync extends the earlier post-commit reconciliation; only Markdown status/tree
files are modified. CORE-01–07 are CLOSED
/ COMMITTED; CORE-08 is NEXT / NOT STARTED; CORE-09–11 are NOT STARTED.

The physical CURRENT tree includes `runtime/progress/`, its schema, three test
modules, and existing runtime integration paths documented in `README.md`.
Future paths remain PLANNED; no future directories are created. The canonical
agent count remains 10, with 14 planned for V1.

`ROADMAP.md` owns the accepted V1 scope. This sync adds missing CORE-08
connector/file/manual fallback, provider-neutral skill metadata and capability-
requesting connector architecture; GOV-02 profiles; outcome-first ORCH-01;
expanded CAP-REV-01; retrieval, trace-derived lessons, and selective retention;
Phase 9A replay/regression/provider comparison; Phase 9B natural-language Owner
Home; expanded DEC-01 selectors and bounded DEC-02 pilot/later candidates; and
Phase 10 pack references.
JEV judges. Policy authorizes. Executor acts. Later JEV / Beacon experiments
remain outside the bounded V1 pilot. All these future capabilities remain
PLANNED / NOT STARTED. Existing governance, graph, memory, capability,
Phase 9C, Decision Engine, and Brightshore-first Project Pack scope is retained.
Phase 8E remains PAUSED / BLOCKED; Phase 8F–8H remain NOT STARTED and required.
Historical validation below is preserved; this sync does not rerun runtime tests.

## Historical CORE-07 Closure Reconciliation — Before Implementation Commit

CORE-07R3 final decision: PASS — READY FOR CORE-07 CLOSURE. Recovery durability,
capacity safety, and replay/idempotency passed with no Critical, Major, or Minor
findings. A separate reviewer independently inspected the F2 repair and reproduced
the R2 failure cases. This was same-provider separate-reviewer validation, not a
cross-provider audit.

R3 validation passed 14/14 recovery/adversarial tests, the full 75/75 CORE-07
targeted suite, 650/650 existing regressions, and 989/989 full regression in
472.019 seconds. All 145 Python files and 31 JSON schemas parsed successfully;
`git diff --check` passed. This records R3 evidence, not a closure-time full-suite
rerun.

Closed scope: structured, schema-validated, non-authoritative progress events;
bounded append-only, tamper-evident hash-chain persistence; consistent terminal
outcomes; restart/replay idempotency; and durable, capacity-reserved terminal and
recovery evidence. Interrupted recovery delivery remains reachable after terminal
state and replays exactly once without inventing a worker exit. The exact 124/128
case fails closed before completion; 123/128 completes with required evidence.
`progress != completion`: events grant no approval, review completion, execution,
retry, continuation, budget mutation, write, Git, or deployment authority.

CORE-07C reconciles documentation only. CORE-01–06 remain CLOSED / COMMITTED;
CORE-07 is CLOSED / READY TO COMMIT and remains uncommitted at HEAD `28ab085`.
CORE-08 is NOT STARTED. Runtime behavior is unchanged; no commit or next-phase
work is performed. CORE-07C fresh targeted validation passed 75/75 tests in
52.074 seconds; `git diff --check` passed. R3's full-regression evidence above
is retained without claiming a closure-time full-regression rerun.

## Historical CORE-07F2 Bounded R2 Repair - Before CORE-07R3

CORE-07R2 returned FIX for one remaining Major finding: recovery could commit
canonical state before delivering its recovery outcome, then permanently miss
that evidence because later recovery scanned only running jobs.

CORE-07F2 adds a bounded durable recovery delivery record to the existing SQLite
journal. It reserves one outcome slot before recovery lifecycle mutation, persists
the actual returned outcome before append, and atomically inserts the event and
removes its delivery record. Reconciliation includes ready evidence for terminal
jobs. A separate recovery lock serializes attempts; an interrupted attempt without
a durably returned outcome records worker_error rather than inferred success.
No worker exit is invented, and recovery metadata grants no execution authority.

Validation: all 14 new F2 durability tests passed as part of the full CORE-07
suite (75/75). Coverage includes the exact R2 append-interruption/restart and
124/128 capacity cases, exact-fit 123/128 delivery, process exit, transaction
rollback, repeated reconciliation, concurrent recovery, review-wait neutrality,
logical capacity, schema migration, and missing/altered protection definitions.
CORE-01-06 regressions passed 394/394; focused integration regressions passed
256/256; full regression passed 989/989 in 633.023 seconds. Syntax parsing passed
for 145 Python files and all 31 JSON schemas; `git diff --check` passed. Journal
and recovery-lock paths remain covered by the existing jobs ignore boundary.

The repair remains uncommitted at base HEAD `28ab085`; independent re-review
remains pending. CORE-08 is NOT STARTED. No commit, deployment, graph runtime,
dashboard, or next-phase work was performed.

## Historical CORE-07F1 Bounded R1 Repair - Before CORE-07R2

CORE-07R1 returned FIX. CORE-07F1 repairs only its four findings, remains
uncommitted at base HEAD `28ab085`, and does not begin CORE-08.

- Lifecycle saves and reconciliation share a cross-process transition lock.
  Validation reloads current canonical state under that lock, rejects changed
  source status and terminal rewrites, and serializes state persistence with
  progress observation. Journal validation rejects contradictory terminal states
  and duplicate terminal identities; invalid historical evidence is not rewritten.
- Complete event bundles reserve bounded capacity in a durable SQLite pending
  row before canonical writes. Before/after job digests and exact generated events
  bind delivery to actual canonical state. Delivery commits events/head and pending
  removal together; a pre-write interruption cancels the reservation without
  changing the job. Pending capacity cannot be stolen by concurrent appends.
- Execution-result recovery records its actual returned outcome using
  `recovery_completed`, without inventing an interrupted worker's exit.
- Journal access verifies full SQLite table/constraint and trigger definitions.
  Only intact R1 schema can migrate to the reservation-aware schema; altered or
  missing protection definitions fail closed.

F1 targeted validation passed 23/23 tests; the complete CORE-07 suite passed
61/61. Coverage includes controlled completion/failure and duplicate-completion
races, cross-process stale transitions, capacity rejection/exact fit, reservations
across real process exits before/during event delivery, tamper, and recovery outcomes.
CORE-01-06 regressions passed 394/394 and focused regressions passed 292/292.
Full regression passed 975/975 in 559.364 seconds. Syntax parsing passed for
144 Python files and all 31 JSON schemas; `git diff --check` passed. The journal
and transition-lock paths remain covered by the existing jobs ignore boundary.

Progress remains evidence only. Reservations cannot approve or perform job state
changes, retry, continuation, budget mutation, plan changes, controlled writes,
Git, or deployment. CORE-01-06 authority rules remain in their existing modules.
Independent re-review has not occurred. No commit, deployment, graph runtime,
dashboard, or CORE-08 work was performed.

## Historical CORE-07 Initial Implementation Checkpoint - Before CORE-07R1

CORE-07 is IMPLEMENTED / pending independent review, uncommitted at base HEAD
`28ab085`. The new `runtime/progress/` package and
`schemas/progress-event.schema.json` define deterministic, typed, bounded,
non-authoritative observations. `progress != completion`.

Integration covers canonical job persistence, Worker execution/result and exit
boundaries, actual host provider calls (including controlled-write staging),
Scheduler reconciliation, continuation steps, retry/repair, Reviewer/human gates,
CORE-05 budget denial, and CORE-06 stop/replan decisions. Tool events describe
host calls; hidden provider-internal tool activity is not fabricated.

Each logical job has an append-only SQLite journal under the configured jobs
root's `.progress/` directory. Standard-library SQLite FULL synchronous
transactions atomically commit each event and its hash-chain head; initial
creation uses atomic replacement. SQL update/delete guards, complete read-time
schema/identity/chain validation, existing cross-process file-store locking,
deterministic deduplication, and canonical-state reconciliation provide local
integrity and restart behavior. Bounds are 128 events per physical job, 4,096 per
logical job, 4,096 bytes per event, and a 32 MiB database read ceiling. Full or
malformed history fails closed without eviction. Arbitrary owner replacement of
the entire database is outside this local evidence store's integrity boundary.

Progress grants no Approval, Reviewer completion, retry/continuation, budget,
plan mutation, write, Git, or deployment authority. Journals are not policy inputs.
An unavailable journal returns an error; successful evidence delivery is never
claimed when persistence failed. Only canonical terminal continuation state with
no remaining steps produces logical completion evidence.

Validation: CORE-07 targeted tests passed 38/38; CORE-01-06 regressions passed
394/394; focused Worker/Scheduler/Reviewer/Approval/actions/Git/provider/runtime
regressions passed 292/292. The final full runtime regression passed 952/952
in 541.546 seconds. `git diff --check` passed.
Python syntax parsing passed for 143 runtime files; all 31 JSON schemas parsed;
the journal path is covered by the existing jobs ignore rule. No live provider,
deployment, commit, CORE-08, graph runtime, or dashboard work was performed.
Independent review has not been performed; this is implementation evidence only.

## Historical Post-CORE-06 Documentation / Roadmap / Repository Tree Checkpoint

CORE-06 implementation, validation, R6 PASS evidence, and closure documentation
are committed at `4a6e5c4` (`feat: add retry and stop policy`). The working tree
was clean before this reconciliation. CORE-01 through CORE-06 are CLOSED /
COMMITTED; CORE-07 Progress Events is NEXT / NOT STARTED. ORCH-01 remains
NOT STARTED. Phase 8E remains PAUSED / BLOCKED with deployment not started;
Phases 8F through 8H remain NOT STARTED.

Physical-tree audit confirmed the CURRENT implementation at `runtime/retry/`
with `__init__.py`, `models.py`, `runtime.py`, `store.py`, and `README.md`;
`runtime/execution/failures.py`; the retry policy/state and execution-artifact
schemas under `schemas/`; and the five `runtime/tests/test_retry*.py` modules.
The canonical implementation path is `runtime/retry/`, not a planned alias.
All 26 future paths listed in README remain absent, including CORE-07's
`runtime/progress/`. No directories were created. The current canonical agent
count remains 10 and the accepted V1 target remains 14.

`README.md` remains the canonical DOC-TREE summary. The accepted V1 master
roadmap/backlog and its future paths are preserved. This checkpoint follows
implementation -> validation -> review -> closure -> commit -> physical-tree
audit -> DOC-TREE reconciliation. Only documentation changed; historical review,
repair, and pre-commit closure evidence below retains its original context.

## Historical CORE-06 Closure Reconciliation - Before Implementation Commit

CORE-06R6 final decision: PASS - READY FOR CORE-06 CLOSURE. The human supplied
this authoritative external independent-review report during CORE-06C on
2026-09-29; the report was produced in the preceding review step and had not
previously been reconciled into repository documentation. R6 changed no
repository files and retained HEAD `065b3e9`.

External R6 evidence (reported review results, not rerun by this closure):

- Schema version validation: PASS; corrupted artifact retry: PASS.
- Execution store: 31/31; CORE-06: 161/161; full regression: 914/914.
- CORE-01-05: 233/233; focused regression: 268/268.
- 30 schema JSON files parsed; `git diff --check`: PASS.
- Critical: NONE; Major: NONE; Minor: NONE.

The final Retry / Stop Policy provides bounded retry, no-progress/stuck/cycle
detection, and repair scoped to the failed unit. `REPLAN_REQUIRED` stops local
retry without invoking a Planner or changing a plan. Exact-work identity,
original approval requirements, review gates, and authorized repair scope are
preserved. Atomic reservations and independent persisted evidence prevent
restart/concurrent delivery from reopening consumed attempts; terminal policy
history revokes stale retry authority. Canonical corruption, including invalid
artifact schema versions, fails closed rather than authorizing provider retry.
Retry remains separate from CORE-02 continuation and retains the same CORE-05
logical budget and consumed usage without reset, refund, or extension.

CORE-06C fresh closure validation: `python -m unittest discover -s runtime/tests
-p 'test_retry*.py'` passed 161/161 tests. `git diff --check` passed. Final
status/diff inspection confirmed an empty index, unchanged HEAD `065b3e9`,
and documentation-only closure edits with existing implementation preserved.

CORE-06C changes canonical documentation only. CORE-01-05 remain CLOSED /
COMMITTED; CORE-06 is CLOSED / READY TO COMMIT and remains uncommitted at HEAD
`065b3e9`. CORE-07 and ORCH-01 remain NOT STARTED. Phase 8E remains PAUSED /
BLOCKED with deployment not started; Phases 8F-8H remain NOT STARTED.
Historical implementation and FIX/repair checkpoints below preserve their
then-current review status and do not supersede this closure.

## CORE-06 Initial Implementation Checkpoint — Before CORE-06R1

CORE-06 adds a provider-independent retry policy, typed decisions, immutable
logical-job policy binding, bounded restart-safe decision history, deterministic
attempt identity, exact-work authorization, and unit-scoped repair enforcement
under `runtime/retry/`. Total attempts include the initial attempt. Retry never
resets its count, continuation lineage, logical CORE-05 budget, consumed usage,
approval, review, recovery-hold, controlled-write, Git, or deployment state.

Scheduler retry and expired-lease recovery now ask canonical policy rather than
treating `retryable` as authority. Trusted failure class, exact work, policy,
attempt history, accepted progress-evidence digests, approval/recovery state,
and CORE-05 exhaustion drive deterministic `RETRY`, `STOP`,
`REPLAN_REQUIRED`, `NEEDS_HUMAN`, or `ERROR` decisions. Provider prose,
provider error labels, `next_actions`, Eval results, available budget,
continuation eligibility, and tool loading cannot authorize retry.

No-progress, stuck, and self/two-state/longer-cycle detection use bounded
canonical signatures and persist across restart. Retry reservation precedes
deterministic child creation; duplicate delivery and concurrent reservation
converge on one attempt. Existing execution-result reconciliation and CORE-05
reservation accounting preserve crash consistency without duplicating recorded
success or refunding uncertain work.

Implementation validation passed 51/51 CORE-06 tests, 30/30 CORE-01, 61/61
CORE-02, 49/49 CORE-03, 33/33 CORE-04, 59/59 CORE-05, 268/268 focused
Worker/Scheduler/Reviewer/Approval/controlled-write/Git/remote-Git/provider
regressions, and the full 803/803 runtime suite. A Windows claim-lock
initialization race exposed by the first aggregate concurrency run was repaired;
the dedicated same-attempt concurrency case then passed 20 consecutive stress
runs and the final aggregate suite. All 140 repository Python files compiled,
29 JSON schemas and the JSON-compatible lifecycle parsed, 56/56 runtime/host
loader tests and fresh import probes passed, production `shell=True` and
changed-scope credential scans found zero findings, retry path/traversal and
bounded-directory tests passed, and `git diff --check` passed with line-ending
notices only.

`REPLAN_REQUIRED` is only a stop/control boundary. It does not modify a plan,
call a Planner, create a graph, or grant new authority. CORE-07 and ORCH-01
remain NOT STARTED. At this initial checkpoint, before CORE-06R1, CORE-06 had
not yet been independently reviewed, closed, or committed. No live provider,
network, deployment, push, PR, or external-system
mutation was performed.

## Historical CORE-06F1 Bounded R1 Repair — IMPLEMENTED / Pending Independent Re-Review

CORE-06R1 returned FIX. CORE-06F1 repairs only its eight concrete findings;
implementation validation is not independent acceptance or closure.

- F1: consume a write-once retry execution reservation atomically before budget
  admission or Executor delegation. Duplicate delivery reuses canonical state
  or result; crash/restart cannot reopen the consumed attempt. Request admission
  anchors are execution-scoped so ordinary CORE-02 human resume remains distinct.
- F2: carry failed-unit repair constraints into controlled-write validation and
  intersect them with existing approved scope. Unallocated multi-unit parent
  scopes fail closed. Canonical path normalization rejects traversal/escape;
  provider mutation of request constraints cannot broaden the validation snapshot.
- F3: verify bounded content-addressed decision events against chained write-once
  sequence claims, first-use evidence, and the high-water cache. Failure,
  materialization, and execution anchors prevent count/identity rollback or
  recreation of deleted consumed children.
- F4: exclude provider error labels, wording, metadata, and actions from detection
  signatures; trusted failure class, work, and accepted progress remain identity.
- F5: classify independently observed controlled-write scope/authority/policy
  denials as non-retryable, not from provider labels or free-text matching.
- F6: anchor work and complete request digest before delegation and immutable
  canonical failure evidence before failure persistence; first retry authenticates
  the persisted request and rejects material source/request changes.
- F7: Reviewer retry uses structured `retry_or_stop`, retaining
  `REPLAN_REQUIRED` through Worker outcomes instead of generic lifecycle errors.
- F8: reject boolean/non-integer policy versions consistently in model, schema,
  and store; repair paths retain bounded canonical model/runtime checks.

Final validation: 78/78 CORE-06 (51 original plus 27 new repair tests), 232/232
CORE-01–05, 268/268 focused, and 830/830 full runtime regression passed. Direct
duplicate-delivery stress covered 15 eight-thread rounds and a two-process
race; each retry delegated once. Crash-before-delegation, post-reservation,
post-budget-reservation, and persisted-success reconciliation tests passed.
Controlled-write sibling, mixed A+B, traversal, unrelated-path, valid repair,
and constraint-tampering tests passed. All 141 Python files compiled, 29 schemas
parsed, 107 runtime imports loaded, 56/56 runtime/host loader tests passed,
policy-version parity passed, production `shell=True` and credential-literal
scans found zero findings, and tracked/new-file whitespace checks passed.

HEAD remains `065b3e9`; CORE-06 is uncommitted and pending independent re-review.
No Planner invocation, plan mutation, ORCH-01 runtime, budget reset/refund,
authority expansion, or CORE-07 work was introduced. CORE-07 and ORCH-01 remain
NOT STARTED. No live provider, network, deployment, push, PR, or external-system
mutation was performed.

## Historical CORE-06F2A Bounded R2 Repair — IMPLEMENTED / Pending Independent Re-Review

CORE-06R2 returned FIX. The 2026-09-29 CORE-06F2A checkpoint repairs only its
five remaining concrete findings; implementation validation is not independent
acceptance, closure, or permission to begin CORE-07.

- Execution identity: independent write-once attempt-admission evidence is
  persisted before Executor delegation. Losing both reservation files after
  admission is a recovery hold, not an unused attempt. The unchanged R2
  reproduction and new concurrent/restart probes keep Executor call count at 1.
- History rollback: independent bounded append-only revision witnesses precede
  events, decision claims, head, and state. Deleting STOP/REPLAN event/claim
  suffixes and replaying older head/state, or replaying genesis and deleting the
  exhausted child, cannot restore retry authority. Interrupted/missing witness
  evidence also fails closed; caches are not the sole rollback anchor.
- Trusted failures: Worker-observed typed mode, result-contract, schema,
  integrity, policy, and authority failures are non-retryable. Provider wrappers
  preserve canonical exceptions instead of flattening them into transient
  failures. Durable provenance survives crash/result reconciliation; missing
  provenance cannot authorize retry. Provider wording and metadata are excluded.
- Approval policy: immutable original request/admission and failure evidence
  preserve the original requirement. Mutable `approved -> not_required` on the
  source or child fails closed before retry decision/enqueue/delegation. Intact
  gated work still needs fresh canonical approval, with the same logical budget.
- Repair scope: effective paths are the hierarchical intersection of parent
  authorized scope and failed-unit allocation, never the wider unit scope.
  Sibling, mixed, unrelated, forbidden, traversal, and capability-expanded
  repairs are denied; valid narrow repair still enters the Reviewer boundary.

Validation passed: 26/26 new bounded adversarial tests; the five unchanged R2
evidence-loss/denial/scope reproductions; 104/104 full CORE-06 tests; 232/232
CORE-01–05; 268/268 focused; and 856/856 full runtime regression. The unchanged
10-round eight-thread retry stress test also passed independently, and the
CORE-06 suite includes two-process delivery and crash/restart cases. An initial
oversubscribed four-suite run hit that fixture's 10-second startup timeout;
final aggregate runs were serialized and passed without changing its timeout.
Approval/controlled-write/runtime-host validation passed 117/117. All 142
Python files compiled, 29 schemas parsed with 167 references resolved, 114
production imports and canonical runtime loaders passed, version-type parity
passed, and production `shell=True`/credential-literal scans found zero
findings. Tracked diff and new-file whitespace checks passed.

HEAD remains `065b3e9`; the index is empty and CORE-06 is uncommitted. CORE-06
remains IMPLEMENTED / pending independent re-review. CORE-07 and ORCH-01 remain
NOT STARTED. No Planner call, plan mutation, authority expansion, budget
reset/refund/extension, live provider, network, deployment, push, PR, or
external-system mutation was introduced. Missing new integrity evidence is
not silently migrated or reconstructed; these are application-integrity
guarantees, not protection against an OS actor erasing every independent
canonical authority/evidence file.

## Historical CORE-06F3 Bounded R3 Repair — IMPLEMENTED / Pending Independent Re-Review

CORE-06R3 returned FIX. This 2026-09-29 checkpoint repairs only its four Major
findings; implementation validation is not independent acceptance or closure.
The unchanged R3 attacks were reproduced before repair: Executor call count 2
without a budget after reservation/attempt-admission loss, accepted history
revision 2 -> 1 with REPLAN_REQUIRED removed, canonical schema-load failure
classified transient, and an actual Unicode sibling write.

- Consumption: an independent write-once consumed-attempt anchor precedes
  reservation. Missing reservation/admission evidence cannot reopen it.
  Surviving per-execution admission, including either half, or a persisted
  execution result also holds redelivery if all attempt indexes are lost.
  The exact no-budget R3 attack now keeps Executor call count at 1.
- History: a separate bounded accepted-revision ledger and its creation
  evidence anchor genesis and every accepted revision. An independent immutable
  terminal tombstone retains STOP/REPLAN_REQUIRED. Removing event, claim, and
  revision witness plus older head/state replay fails closed; removing accepted
  suffix evidence while retaining the terminal anchor also fails closed.
- Integrity: Worker and ProviderExecutor share typed canonical integrity,
  authority, and policy exceptions. Real ExecutionStoreError from invalid result
  schema and result-save failures are non-retryable, with durable trusted
  provenance and no provider-text classification.
- Paths: parent scope, unit intersection, plan-scope comparison, and staged
  write validation share the filesystem-aware matcher. Windows uses ordinal
  comparison and proven identity for positive case aliases, not linguistic
  Unicode casefolding; POSIX preserves exact case. Distinct straße/strasse
  directories remain disjoint. Sibling, mixed, unrelated, and normalized
  traversal writes fail before target application; valid case handling and
  negative scope for not-yet-created files remain protected.

Final validation passed: 34/34 new F3 adversarial tests within 138/138 CORE-06;
all 14 unchanged R3 probes and the unchanged actual Unicode-write probe;
232/232 CORE-01–05; 268/268 focused; 61/61 Approval/controlled-write; and
890/890 full runtime regression. CORE-06 includes crash/restart, eight-thread
stress, and two-process same-attempt delivery. The prior Phase 8C timing failure
did not reproduce in the isolated test or full regression; Phase 8C code was
not changed. All 144 Python files compiled, 29 schemas parsed with 167 references
resolved, 115 production imports and the canonical runtime loaders passed,
fresh integrity/provider/Worker-first imports passed, and production shell=True
and credential-literal scans found zero matches. These scans are not a live
credential audit. Tracked diff and new-file whitespace checks passed.

HEAD remains 065b3e9; the index is empty and CORE-06 remains uncommitted,
IMPLEMENTED / pending independent re-review. Approval-policy preservation,
exact-work binding, provider-resistant detection, structured REPLAN_REQUIRED,
retry limits, scope intersection, the same CORE-05 budget, Reviewer, and recovery
hold remain intact. No Planner call, plan mutation, budget refund/reset/extension,
deployment, live-provider action, or next-phase implementation was introduced.
CORE-07 and ORCH-01 remain NOT STARTED. Missing integrity evidence is not silently
migrated or reconstructed; these application-integrity guarantees do not cover
an OS actor erasing or replacing every independent canonical evidence file.

## Historical CORE-06F4 Bounded R4 Repair — IMPLEMENTED / Pending Independent Re-Review

CORE-06R4 returned FIX with three Major findings. The exact attacks were
reproduced before repair: a consumed attempt delegated twice despite intact
failure/runtime evidence; replaying an old running child executed after
STOP/REPLAN_REQUIRED; invalid UTF-8 became transient RETRY.

CORE-06F4 repairs only those findings:

- Missing reservation/admission/result indexes cannot hide canonical failed
  attempts or either surviving half of Worker-observed runtime-failure evidence.
  The exact no-budget R4 attack now preserves Executor call count 1, including
  concurrent restart/redelivery.
- Execution authorization verifies the current complete retry history before
  reservation and at request admission. Persisted STOP/REPLAN_REQUIRED revokes
  earlier RETRY execution and repair authority. Historical reads remain
  explicitly separate and preserve structured terminal reporting.
- Canonical store readers normalize UTF-8/JSON decoding failures into existing
  typed trusted storage errors. Schema/integrity failures remain non-retryable
  through Worker and ProviderExecutor. Corrupt canonical context causes STOP
  without invoking a provider adapter.

Validation passed 22/22 new F4 adversarial tests within 160/160 CORE-06,
232/232 CORE-01–05, 268/268 focused regression, 7/7 explicit crash/concurrency,
61/61 Approval/controlled-write, all 13 unchanged R4 and 14 unchanged R3 probes,
and the unchanged Unicode-write attack. Python compilation passed 145/145;
29 schemas and 167 references parsed/resolved, 115 production imports and
runtime-loader checks passed. Production shell=True and credential-literal
scans found zero matches; these are not live credential checks.
Full runtime regression passed 912/912 on an unchanged-code rerun. The first
full run recorded one failure in Phase 8C's
`test_i4_stop_after_start_publication_targets_new_owner`; that case passed
independently (1/1), the complete Phase 8C suite passed 31/31, and the full
rerun passed without Phase 8C code or timeout changes.

HEAD remains 065b3e9, the index is empty, and CORE-06 is uncommitted and pending
independent re-review, not closed. This is implementation evidence, not
independent acceptance. Unicode/path-scope matching, original Approval policy,
exact-work binding, provider-resistant detection, history integrity, shared
CORE-05 budget, Reviewer, and recovery hold remain preserved. Phase 8C code is
unchanged. No Planner, plan mutation, deployment, live provider action, budget
refund/reset/extension, or next-phase implementation was introduced. CORE-07
and ORCH-01 remain NOT STARTED.

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

- Phase 8E is PAUSED / BLOCKED because the VPS has not yet been created;
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
Phase 8E is PAUSED / BLOCKED because the VPS has not yet been created, and
deployment has not started. A
different-provider full-repository audit and the other recorded
Phase 8C hardening items remain recommended future validation, not a mandatory
Phase 8 implementation gate.
