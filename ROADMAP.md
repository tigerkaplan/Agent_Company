# Agent Company Roadmap

## MEM-01 Current Status - 2026-10-10

MEM-01 Knowledge / Memory Foundation: **CLOSED / COMMITTED** at
`5e29cdb177838adb1682ab3b36728623d714c5e3` (`feat: add memory foundation contracts`).
Commit and GitHub push are owner-verified. Read-only filesystem checks corroborate
local `master` and `origin/master` refs at that commit. All three MEM-01 source
SHA-256 identities match the accepted closure evidence.
ACTIVE: None. NEXT: MEM-02 Knowledge Lifecycle + Retrieval / RAG / NOT STARTED,
by frozen sequence only.

The dated closure and earlier snapshots below remain unchanged historical
evidence; this current status supersedes their pre-commit status and next actions.
A1-A7 PASS, independent R03-M1 PASS / CLOSED, reported 232/232 PASS and their
limitations remain in the [closure record](PROJECT_STATE.md#mem-01-closure-reconciliation---2026-10-10).
V1 freeze stays ACTIVE; CORE-01-11, GOV-01/02 and ORCH-01 stay CLOSED / COMMITTED.
D1 optimization, measurements and formal closure remain unfinished; archived
runner M2 remains OPEN. Phase 8E stays PAUSED / BLOCKED; Phase 8F-8H stay NOT STARTED.
MEM-02 scope is unchanged. This task ends at documentation reconciliation.

CURRENT / COMMITTED MEM-01 contracts and test support retain their existing
`runtime/memory/` and `runtime/tests/test_memory_foundation.py` ownership.
`shared/memory/` stays PLANNED / absent; later MEM scope remains unchanged.

## MEM-01 Closure Reconciliation - 2026-10-10

MEM-01 Knowledge / Memory Foundation: **CLOSED / READY_TO_COMMIT**.
Closure assessment: **PASS** on owner-supplied acceptance, executor and independent
R03-M1 re-review evidence, with current source hashes verified locally.
**READY_FOR_COMMIT: YES.** Implementation and this reconciliation remain
UNCOMMITTED against HEAD `031028b6a57859b41b46123f0347cbd9570afe95`.
ACTIVE: None. NEXT: MEM-02 Knowledge Lifecycle + Retrieval / RAG / NOT STARTED,
by frozen sequence only. Next action: separately authorized MEM-01 commit.
No Git or MEM-02 implementation authority follows from this reconciliation.

See [acceptance, source hashes, 232/232 evidence and limitations](PROJECT_STATE.md#mem-01-closure-reconciliation---2026-10-10).
Review/test outcomes are owner-supplied reports; raw logs and a separate
repository review artifact have not been verified. No mandatory unrun MEM-01
validation gate was identified in the inspected rules; no review was repeated.
D1 runner optimization, measurements and formal closure remain unfinished;
archived runner M2 remains OPEN. V1 freeze and existing closed checkpoints remain intact.
Dated pre-MEM-01 records below retain their historical status and evidence.

MEM-01 implements contracts and test-local behavior only at `runtime/memory/`
and `runtime/tests/test_memory_foundation.py`. `shared/memory/` stays absent /
PLANNED; retrieval/RAG, lesson promotion, production storage/providers and runtime
integration remain later MEM checkpoint work.

## POST-ORCH-01 DOC-TREE - 2026-10-09

ORCH-01 Graph Execution Runtime: CLOSED / COMMITTED at `d38780817ca9f233051efa31b77d3a8eabe1473a`
(`feat: add graph execution runtime`). Independent R4 refresh-02 PASS and owner
closure PASS; no unresolved acceptance blockers. ACTIVE: None.
NEXT: MEM-01 Knowledge / Memory Foundation / NOT STARTED, by frozen roadmap order
only; no implementation authority follows from this reconciliation.
See [owner closure](orchestrator/graph/CLOSURE.md) and
[closure evidence](orchestrator/graph/CLOSURE_EVIDENCE.json).

## SYNC-06 R4/R2 Source Reconciliation - 2026-10-10

This documentation-only reconciliation maps the accepted SYNC-06 R4/R2 source
material onto existing owners. It does not create a new SYNC version, checkpoint,
runtime contract, agent, authority, implementation claim, or permission to begin
MEM-01. The V1 scope freeze remains ACTIVE; CORE-01-11, GOV-01, GOV-02, and
ORCH-01 remain CLOSED / COMMITTED. ACTIVE remains None and MEM-01 remains NEXT /
NOT STARTED by sequence only. D1-D8, H1-H11, SRC-01-30, UD-01-05, and EV-01-36
are source-transfer labels rather than canonical repository IDs or mandatory
test counts.

### Ownership and acceptance mapping

| Source area | Existing owner and accepted boundary | Evidence and acceptance placement |
| --- | --- | --- |
| D1 / H1 | Existing validation tooling and the affected checkpoint owner. Selection tiers do not require fully overlapping reruns. | Measure command wall-clock time, unique test IDs, overlap, incomplete causes, process cleanup, resource contention, and source/dependency/fixture/config/environment bindings. Preserve targeted, affected, focused, full, security, adversarial, acceptance, closure, and independent-review gates where the applicable checkpoint requires them. |
| D2 / H2 | CAP-REV-01, Software repair, Reviewer, and CORE-03. A concern or failed harness is not a confirmed defect. | Candidate -> valid reproduction -> confirmed finding/root cause -> separately authorized narrow repair -> before/after proof -> regression -> independent read-only verdict. |
| D3 / H2 | CORE-04 discovery, GOV-02 certification, current skill catalog, and CORE-03 evaluation. | Record identity/version, activation and non-activation, inputs, exclusions, requested tools, bounded procedure, destination, held-out cases, and keep/revert result. No third-party installation follows from this map. |
| D4 / H8 | ORCH-01, Manager/Orchestrator, and CORE-06. ORCH-01 is not reopened. | Keep data edges, shared-resource dependencies, approval order, quotas, and permissions distinct; invalidate affected dependents while retaining valid unaffected work. Temporary roles are execution profiles, not canonical agents. |
| D5 / H5 | Provider adapters, CORE-10, GOV-01/02, and action-specific approval. | Configured, eligible, loaded, and authorized remain distinct. External send, publishing, spend, deployment, and Git effects need exact authority; an uncertain acknowledgement never authorizes blind resend. |
| D6 / H2/H9/H10 | DEC-01/02, CORE-03, Reviewer, and Phase 9A. | Bind question, evidence span/version, eligible options, abstention/uncertainty, dataset/system/grader/rubric identity, citation entailment, and whole-artifact coverage. Shadow decisions never act. |
| D7 / H3/H4/H6/H7 | MEM-01/02/02B/03, Knowledge Manager, CORE-08/09, and durable operational state. | Preserve source identity/version, accepted/rejected/deferred rationale, conflicts, applicability, freshness, outcome, supersession, read coverage, and revisit triggers. Stored != selected != trusted != applied. |
| D8 / H4-H6 | Phase 9B/9C views, scheduler/recovery, connectors, and existing approval/operating state. | Separate read, evaluate, include, authorize, deliver, receipt, and bookmark commit. A failed read is not a quiet day; configured trigger is not completed work; dry-run must prevent external writes. |
| H11 domain methods | Existing Data/Analytics, Search Growth/SEO/GEO, Sales, Creative Media, WebMCP integration, Reviewer, CAP-SOC-01, and relevant Project Pack owners; AI Business Studio remains a separate B-track direction. | Data preserves snapshot/query/transformation and reconciliation; Search preserves existing URLs/forms/CTA/assets and the visible 12-item Local SEO set; Sales separates sourced qualification/drafts from send/follow-up authority; Creative separates artifact ownership, versioned renders and technical/visual/audio QA; WebMCP separates consumer/producer use with origin/session/schema and authorized fallback; Business Studio separates problem/workaround/interview/hypothesis/outcome. EV-29-31/36 and existing domain acceptance apply only when the relevant owner opens. Tools, pilots, installs, live data/assets, outreach and external actions require separate authority. |

H1-H11 remain portable navigation aliases, not canonical requirement IDs. H1 is
validation efficiency; H2 evidence audit, repair and skill adoption; H3 research
and decision memory; H4 read coverage; H5 delivery uncertainty; H6 state,
dry-run and recovery; H7 freshness and counterevidence; H8 graph repair; H9
decision/citation coverage; H10 observed provider/economics evidence; and H11
domain methods with pilots and the separate Business Studio B track kept distinct.

### Source-to-owner and acceptance traceability

This is a Roadmap crosswalk, not a second source ledger. Source claims remain
dated evidence, not implementation proof or user approval. The useful methods,
behavior, evidence gap, owner, acceptance, authority and timing are:

| Source identities and decision | Useful method and adapted behavior | Scope, evidence/gap, owner, acceptance, authority and timing |
| --- | --- | --- |
| SRC-01, SRC-10, SRC-13, SRC-14, SRC-23, SRC-26, SRC-27, SRC-28 | Measure accepted-outcome cost; distinguish requested/configured/observed provider, model and effort; use deterministic prechecks before semantic judgment; retain controlled learning as a candidate. | Existing CORE-10/adapters, DEC-01/02, Reviewer and Phase 9A. Historical source economics and model claims are unverified/currentness-sensitive. EV-07-10/27-28 apply to a separately authorized bounded pilot; no provider call, account connection, spend or automatic promotion follows now. |
| SRC-02, SRC-06, SRC-09, SRC-11, SRC-12, SRC-14, SRC-22, SRC-23 | Preserve bounded graph/loop distinctions, local repair, failure-first proof, affected-dependent invalidation and explicit stop/closure. | Closed ORCH-01, CORE-06, CAP-REV-01, Software and Reviewer remain owners; current closure evidence proves ORCH, not every source proposal. EV-01-06/08/32 apply when a relevant defect or change opens under separate repair/review authority; no ORCH reopen or new runner now. |
| SRC-03, SRC-10, SRC-18, SRC-29 | Preserve graduated autonomy, approval queues, source bookmarks, read/delivery separation, uncertain acknowledgements, durable state and recovery. | Existing GOV-01/02, approval, scheduler, connector and delivery/recovery owners. No live routine, token, schedule or send is evidenced. EV-17-26 apply when those existing operating obligations open; external effects and new routines need exact approval. |
| SRC-12, SRC-16, SRC-23, SRC-27, SRC-29, SRC-30 | Preserve stable source identity, rejected/deferred rationale, counterevidence, freshness, task-aware recall, outcomes and controlled lesson candidates. | MEM-01/02/02B/03, Knowledge Manager and CORE-08/09; current evidence is design direction, not a durable memory implementation. EV-11-18/33-35 apply during the relevant authorized MEM/context work; no database, scan, import or promotion now. |
| SRC-08 | Use snapshot/query/transformation lineage, currency/date handling, duplicate/missing checks, join-cardinality checks and total reconciliation. | Existing Data/Analytics and Reviewer/Project Pack work. No live dataset or accounting result is supplied. EV-36 plus existing domain checks apply when an authorized data task opens; synthetic analysis must not be represented as real accounting. |
| SRC-04, SRC-25, SRC-27 | Use commercial intent and source-backed briefs while preserving existing URL, form, CTA, embed, link and asset behavior; retain the visible 12 Local SEO audits without inventing eight more. | Existing Search Growth/SEO/GEO, Reviewer, CAP-SOC-01 and relevant Project Pack owners. No live site/source audit is evidenced. EV-36 and existing project acceptance apply only when that work opens; scanning, edits, publishing and outreach need separate authority. |
| SRC-15 | Keep sourced company/contact identity, ICP/qualification, personalized draft and retention separate from sending and follow-up. | Existing Sales, Reviewer and Project Pack owners. Repositories are references, not installed capability or verified leads. EV-19-21/36 and existing sales acceptance apply when authorized; research, CRM writes, outreach and follow-up remain separately approved effects. |
| SRC-05, SRC-07, SRC-20, SRC-24, SRC-26 | Preserve one artifact owner, seekable/versioned renders, beats/contact sheets/transition strips, format-specific composition, actual playback and separate technical/visual/audio QA. | Creative Media remains non-blocking; CAP-CREATIVE-01 and CAP-DOC-01 retain their classifications. No renderer, licensed asset or pilot result is evidenced. EV-29-31 apply when authorized; install, render, asset/voice use and publication require separate authority. |
| SRC-13, SRC-14, SRC-17, SRC-28 | Keep atomic questions, open-set/abstention behavior, state/source spans, citation entailment and whole-artifact coverage distinct from execution authority. | DEC-01/02, CORE-03 and Reviewer. Provider formulas and reported benchmarks are not revalidated. EV-07-16/32 apply to a separately authorized decision/eval pilot; shadow output never acts. |
| SRC-21 | Treat WebMCP consumption and site-provided tools as separate uses with origin, session, schema and authorized fallback boundaries. | Existing connector/provider and Project Pack owners; WebMCP remains reference/deferred and is not installed or connected. Relevant EV-17/22/24/36 apply only when an approved integration opens; browser/site writes require separate authority. |
| SRC-19, SRC-20 | Keep AI Business Studio problem-first: problem, workaround, interview, hypothesis and outcome remain distinct from platform features and live pilots. | Separate B-track research direction, not Agent Company core, Phase 10 replacement or a fifteenth agent. No customer validation is evidenced. EV-36 applies if separately authorized research begins; interviews, outreach, spend and pilots need separate approval. |

| User decision | Canonical effect, owner, acceptance and timing |
| --- | --- |
| UD-01 | Finish the accepted operational V1 without research-driven scope expansion. Existing Roadmap owners retain their obligations; acceptance is the existing checkpoint contract. Applies now and does not defer accepted V1 work. |
| UD-02 | AI Business Studio stays in a separate B-track; Brightshore is only a possible B-track pilot while remaining the first Phase 10 Project Pack. No code, agent, purchase, outreach or live pilot is authorized; revisit only by explicit decision. |
| UD-03 | Research/Decision Memory is an accepted design direction under MEM owners, with provenance, rationale and recall acceptance above. It is not proof of a database or unlimited implementation; revisit when the relevant MEM checkpoint opens. |
| UD-04 | Short approvals authorized further evaluation only. Existing approval owners must bind any installation, spending, schedule, source access or external action; timing is the relevant separately approved task. |
| UD-05 | Preserve detailed source and decision transfer in canonical planning without treating document production as project-change authority. This reconciliation satisfies documentation transfer only and remains subject to independent review. |

| Evaluation scenarios | Existing owner and acceptance placement |
| --- | --- |
| EV-01, EV-02, EV-03, EV-04, EV-05, EV-06, EV-08 | ORCH/CORE validation and CAP-REV-01: distinguish plan from execution and zero-test success from coverage; preserve unaffected work, invalidate dependents, serialize shared writes, stop retries without evidence, and fail closed on invalid decisions. Apply only to relevant authorized changes. |
| EV-07, EV-09, EV-10 | DEC/GOV/Reviewer: forbidden action stays denied despite confidence; other/incomplete/ambiguous remain distinct; option-order stability is measured. Use in a bounded authorized decision pilot. |
| EV-11, EV-12, EV-13, EV-14, EV-15, EV-16, EV-17, EV-18 | MEM/context/Reviewer/connectors: preserve counterevidence and old warnings, test citation entailment and implementation provenance, separate retrieval from validity, invalidate stale reuse, and expose failed/partial reads without advancing bookmarks. Apply at the relevant MEM, review or source-read checkpoint. |
| EV-19, EV-20, EV-21, EV-22, EV-23, EV-24, EV-25, EV-26 | Delivery/GOV/state/scheduler/recovery: reconcile uncertain posting, delivery-before-state failure and duplicates; do not default through missing preferences/state; enforce dry-run; recheck resume authority/budget; distinguish poll timeout from completion. Apply before authorized external or scheduled operation. |
| EV-27, EV-28 | CORE-10/adapters/Reviewer: record requested/configured/observed profiles and actual advisor invocation. Apply to authorized onboarding/routing evidence, not this documentation task. |
| EV-29, EV-30, EV-31 | Creative/Reviewer: reject bad frame/codec, separate technical from visual/audio QA, and invalidate QA after asset/source changes. Apply only to an authorized creative deliverable. |
| EV-32 | Reviewer/CAP-REV-01: truncated diffs cannot support whole-artifact safety. Apply whenever review coverage is incomplete. |
| EV-33, EV-34, EV-35 | MEM/GOV: preserve duplicate source identity/history, recall relevant rejected rationale, and prevent lessons from changing user policy without promotion/authority. Apply when MEM/learning work opens. |
| EV-36 | Domain owner/Reviewer: missing site, lead, budget or other business evidence must not become fabricated facts or live action. Applies to every relevant authorized domain task. |

These scenarios are acceptance examples, not 36 newly mandated tests. They are
adopted only through the existing owner's applicable checkpoint and authority.

### D1 development-time validation efficiency - bounded proposal

D1 belongs to existing validation tooling during development, not solely to
Phase 9A and not to a reopened ORCH-01 checkpoint. The exact observed owner is
`orchestrator/graph/run_validation.py`, which selects existing `unittest` modules
and records aggregate wall-clock time, count, completion, exit and log hash.
Preserved logs measured targeted 55 tests / 638.869s, affected 325 / 695.838s,
focused 761 / 2228.414s, and full 1364 / 3156.386s. The runner definitions show
structural overlap: focused includes all targeted modules and several affected
modules, while full discovery includes all runtime tests. The evidence does not
record a canonical fully-qualified unique-test-ID manifest, a tier-overlap matrix,
per-test timing, resource contention, or subprocess-cleanup telemetry. Therefore
the measured bottleneck is long aggregate execution with demonstrated overlapping
selection; the amount safely avoidable is still unknown and no speedup is claimed.

One smallest proposal: under separate authorization, extend only this existing
runner's report-generation path to enumerate the selected fully-qualified test
IDs before execution, store a sorted manifest plus digest, and calculate set
overlap against the other required tiers. Do not change tests, selection, order,
timeouts, assertions, sharding, or pass criteria. Before/after acceptance requires
identical required unique IDs and complete passing results for every applicable
targeted, affected, focused, full, deterministic, security, adversarial,
acceptance and closure gate; independent review remains separate. Compare runner
overhead and total wall-clock time, prove incomplete/interrupted runs remain
INCOMPLETE, bind source/tests/dependencies/fixtures/configuration/command/
environment/policy version, and retain earlier failures rather than laundering
them through reruns. Risks are discovery side effects, dynamic `load_tests`
behavior, stale manifests, extra reporting overhead and misuse of overlap as
permission to skip a required fresh stateful/concurrency test. Implementation,
benchmarking, policy change and any suite execution require separate approval;
this documentation repair authorizes none of them.

### D1 standalone diagnostics - current-source reconciliation - 2026-10-10

The bounded runner proposal above is retained as historical planning. The present
standalone [reporter](orchestrator/graph/run_validation_diagnostics.py) and
[tests](orchestrator/graph/test_run_validation_diagnostics.py) are uncommitted
files under the existing validation-tooling owner; they do not implement that
runner proposal or reopen ORCH-01. They report explicitly supplied log/JSON
observations, exact test-ID mentions, duplicate/conflicting/incomplete evidence,
logged or claimed timings, input hashes and exact-ID overlap. They do not load
or execute the validation runner/tests, discover suites, follow evidence
references, establish run provenance, or infer per-test timing.

Owner-supplied independent current-source re-attestation: PASS, 58/58 tests,
37 assertions, Python 3.14.3. The reporter and test SHA-256 identities were
verified against the owner-supplied values; see
[the source/review record](PROJECT_STATE.md#d1-standalone-diagnostics-source-and-review-status---2026-10-10).
Historical review hash binding remains UNAVAILABLE. This re-attestation is
separate current-source evidence, not reconstructed historical review provenance.

Overlap is OBSERVED (exact ID mentions only). Acceptance, compatibility,
coverage, execution reuse, test skipping and measured speedup remain UNKNOWN.
Byte-equal log hashes do not establish run association or compatible availability;
parser support is bounded and unparsed/ambiguous evidence retains uncertainty.
Runner optimization, source/dependency/fixture/configuration/command/environment/
policy binding, resource-contention/process-cleanup telemetry and before/after
runtime measurements remain unfinished. Per owner instruction, runner M2 remains
OPEN in archived experimental work; the committed
`orchestrator/graph/run_validation.py` does not contain that experimental change.
No runtime speedup, broad validation or D1 closure is claimed. All applicable
acceptance, independent-review and closure gates remain required; observations
provide no reuse or skipping authority.

### Preserved capability and deferred boundaries

- CORE-01 through CORE-11 retain their closed contracts and authority boundaries.
  These refinements guide future authorized work; they do not change schemas,
  runtime instructions, policies, or accepted closure evidence.
- CAP-REV-01 remains the artifact-native evidence-audit method under existing
  Reviewer/Software authority. NOT_REPRODUCED, BLOCKED, or broken control does
  not mean FIXED. Review must inspect the actual relevant artifact and provenance.
- MEM-01/02/02B/03 retain memory, provenance, retrieval, learning/promotion, and
  project-isolation ownership. Hindsight remains an optional future MEM-03
  provider; Beacon remains an optional importer/reference, not a core dependency.
- DEC-01/02 retain bounded decision ownership. Choice confidence, probability,
  composite score, and authorization threshold remain distinct. Invalid,
  ambiguous, unavailable, or timed-out output fails closed.
- CAP-SOC-01 remains PLANNED / NOT STARTED within the accepted V1 target. The
  committed Social Media checkpoint does not confer live posting authority.
- Phase 9A/B/C and Phase 10 remain planned under their existing owners;
  Brightshore remains the first production Project Pack for Phase 10.
- Hermes stays an optional adapter; Higgsfield an optional creative tool;
  CAP-CREATIVE-01 non-blocking; CAP-DOC-01 post-V1; and WebMCP, Worktree
  Isolation, Council, Advanced Teams, local inference, and fine-tuning retain
  their existing reference/deferred classifications.
- AI Business Studio remains a separate problem-first B-track research direction,
  not Agent Company core, a V1 checkpoint, a fifteenth agent, or a live pilot.
- The current canonical roster remains 10 agents and the frozen V1 target remains
  14 roles. Temporary graph roles and named tools/patterns are not agents.

### Deployment procurement decision

Hostinger is the preferred VPS provider, but no VPS has been purchased,
provisioned, or deployed. Defer paid procurement until as near V1 completion as
practical, then recheck capacity, current commercial terms, Linux/container and
credential needs, backups, security, and explicit action authority. Phase 8E
remains PAUSED / BLOCKED. Its Phase 8D live-image and target-Linux prerequisites
remain required; Phase 8F Backup/Recovery, 8G production smoke tests, and 8H
final independent deployment security review remain NOT STARTED and required.

Revisit these source-derived refinements only when the relevant approved
checkpoint opens, a defect is reproduced, evidence expires, a material source,
tool, provider, licence, or authority changes, or the owner makes an explicit
decision. Preserve conflicting and rejected evidence rather than replacing it
by inference.

## Historical ORCH-01 executor validation PASS - 2026-10-03

ACTIVE: ORCH-01 / IMPLEMENTED / EXECUTOR VALIDATION PASS / UNCOMMITTED.
NEXT: ORCH-01 independent review and owner closure. GOV-01/GOV-02 remain CLOSED.
MEM-01 is NOT STARTED. See [graph acceptance](orchestrator/graph/ACCEPTANCE.md)
and [validation](orchestrator/graph/VALIDATION.md).

## Historical POST-GOV-02 DOC-TREE - 2026-10-03

ACTIVE: None. CORE-01-11 and GOV-01 are CLOSED / COMMITTED.
GOV-02 Capability Governance: CLOSED / COMMITTED at `e6dbe3f`
(`feat: add capability governance`). NEXT: ORCH-01 / NOT STARTED;
sequence only, no authorization to begin.
Verified clean starting HEAD: `e6dbe3fa8df5aabd5923163b05f2fa59dc997997`.
V1 scope freeze, ordering and accepted scope remain unchanged.
CURRENT GOV-02 source, policy, schema, tests and governance/evidence paths are
listed in README; future target paths remain PLANNED and physically absent.
This reconciliation changes documentation only; no runtime tests rerun,
future directories created, commit made or ORCH-01 work begun.
The dated owner-closure and prior checkpoint sections below are historical
records; their pre-commit HEAD, status and validation evidence are preserved.

## Historical GOV-02 Owner Closure - 2026-10-03

ACTIVE: GOV-02 Capability Governance / CLOSED / READY TO COMMIT; implementation remains uncommitted.
NEXT CHECKPOINT: GOV-02 COMMIT. ORCH-01: NOT STARTED; no authorization to begin.
Verified HEAD: `c5de474`; V1 scope freeze remains ACTIVE.
Implementation and independent R5 review: PASS; all eight prior majors CLOSED;
0 critical / 0 major / 0 minor. Same-provider reviewer role separation satisfies
canonical independence; no provider-diverse review is claimed.
Closure verified 706 R5-pinned files, 213 accepted source files, 72 R5 artifact
hashes and complete review logs, including the uninterrupted 1,308-test full run.
Fresh closure syntax/schema/certificate and integrity checks: PASS.
See [owner closure and evidence](governance/capability-governance/CLOSURE.md).
The two superseded pre-F1 reports with unavailable original logs are excluded
from acceptance; historical records and all R1-R5/F1-F3 evidence are preserved.
GOV-01 and CORE-01-11 remain the canonical approval, review, scope, budget and state owners.
Certification, provenance, profile gates and decision traces now run in JobRuntime,
Worker, Reviewer and executor/tool paths. No general external executor is introduced.
Historical authority without GOV-02 provenance fails closed; no automatic migration.
See [GOV-02 implementation and acceptance evidence](governance/capability-governance/README.md).
No repository commit, push, deployment or ORCH-01 implementation has been performed.
The dated GOV-01 sections below preserve their historical checkpoint evidence.


## GOV-01 Historical Committed State - 2026-10-02

ACTIVE: None; GOV-01 Task & Authority Contract / CLOSED / COMMITTED at `852ec01`.
NEXT: GOV-02 / NOT STARTED; sequence only, no authorization to begin.
Verified clean starting tree at `852ec01` (`feat: add task and authority contract`).
V1 scope freeze remains ACTIVE.
CORE-01-11 foundations are reused; no separate approval, budget, review, or scope authority.
See [GOV-01 implementation and classification](governance/task-contract/README.md).
DOC-TREE-GOV01: post-commit filesystem reconciliation; documentation/state only.
GOV-01 source, schema, tests, and governance documentation are CURRENT.
GOV-02, ORCH, MEM, and later target paths remain PLANNED and physically absent.
V1 audit-gap dependency order and filesystem trust boundaries are unchanged.
No runtime tests rerun, future folders created, commit made, or GOV-02 work begun.
The dated closure/review records below preserve their pre-commit status and evidence.

### GOV-01C2 verified closure - 2026-10-02

GOV-01: CLOSED / READY TO COMMIT; implementation remains uncommitted.
GOV-02: NEXT / NOT STARTED; sequence only, no authorization to begin.
Repository evidence directly verified: final independent review PASS, fresh
separate reviewer role CONFIRMED (same provider), Critical/Major/Minor 0/0/0,
and 1227/1227 PASS in one complete uninterrupted full run (702.709 seconds).
See [review evidence](governance/task-contract/REVIEW_EVIDENCE.json),
[review history](governance/task-contract/REVIEW_HISTORY.md), and
[validation](governance/task-contract/VALIDATION.md).
All 52 reviewed implementation-source hashes and diagnostic log hashes match.
R1/F1/R2/F2 findings and validation remain preserved; actual R3 FIX and historical
R4 PASS retain provenance. R3's failed full run and independence limitation are
not rewritten as PASS. Fresh GOV-01C2 targeted tests: 60/60 PASS, exit 0,
94.824 seconds. The complete full run is verified review evidence, not a new
closure-time full-regression run.
Coherent replacement of every relevant trusted store with a historical snapshot
remains outside local rollback detection; hashes are not signatures or an
external monotonic counter. V1 freeze, remaining audit gaps, CORE-01-11 closure,
and accurate prior documentation-drift corrections remain intact.
Complete diff/status/tree inspected; GOV-02 and planned future paths absent
(excluding the explicitly CURRENT shared/projects/brightshore/). git diff --check PASS.
No runtime behavior change, commit, push, deployment or GOV-02 work performed.

### Historical GOV-01C incomplete closure verification - 2026-10-02

GOV-01: OPEN / CLOSURE INCOMPLETE; implementation remains uncommitted.
GOV-02: NEXT / NOT STARTED; no authorization to begin.
The owner reports Independent Re-review R4 PASS, but no R3/R4 review report
was located in repository documentation or local review evidence. R4 PASS has
not been independently verified by this closure task; no review history is
inferred or fabricated. Existing R1/F1/R2/F2 evidence is preserved. Closure to
CLOSED / READY TO COMMIT awaits the actual R4 report and its R3 provenance.
Fresh GOV-01C targeted validation: 60/60 PASS (30.708 seconds, exit 0).
V1 freeze and remaining audit gaps are unchanged. No runtime changes, commit,
or GOV-02 implementation were performed by GOV-01C.

The dated reconciliation below is historical evidence, not current GOV-01 status.

## DOC-TREE-CORE11 Post-Commit Reconciliation - 2026-10-01

Verified clean starting tree at `8bda7eb` (`feat: add external content isolation`).
CORE-01-11 are CLOSED / COMMITTED; CORE-11 is committed at `8bda7eb` after
Independent Re-review R2 PASS. Core Runtime Foundation = COMPLETE.
ACTIVE: None; NEXT: GOV-01 Task & Authority Contract / NOT STARTED, from the
frozen canonical V1 sequence. NEXT records order only, not implementation authority.
GOV/ORCH/MEM and Phase 9 remain NOT STARTED. Phase 8E-8H are unchanged.
The V1 scope freeze remains ACTIVE; SYNC-05 classifications are preserved.
Isolation lives in `runtime/context/`; no separate `runtime/isolation/` is required.
CURRENT paths and PLANNED absence were checked against the physical filesystem.
This reconciliation changes documentation/state only; no runtime tests rerun,
future folders created, commit made, or next implementation begun.
Historical closure validation: 14/14 CORE-11 tests and `git diff --check` passed.

`PROJECT_STATE.md` is the canonical current-status record. This roadmap is the canonical forward capability roadmap after the verified Phase 6 checkpoint. Candidate capabilities below are planning scope unless explicitly marked as completed.

## Status Summary

- Phase 1-6: COMPLETED / COMMITTED.
- Phase 7: COMPLETED / CLOSED.
- Social Media capability checkpoint: COMPLETED / COMMITTED.
- Phase 8A: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8B: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8C: COMPLETED / CLOSED / NO DEPLOYMENT.
- Phase 8D: COMPLETED / CLOSED / NO DEPLOYMENT.
- CORE-01 Canonical Result Contract: COMPLETED / CLOSED / COMMITTED at `3f6acb6`.
- CORE-02 Continuation Policy: COMPLETED / CLOSED / COMMITTED at `9d5ead1`.
- CORE-03 Eval Framework: COMPLETED / CLOSED / COMMITTED at `80ead22`.
- CORE-04 Tool / Skill Discovery: CLOSED / COMMITTED at `35f03f8` after
  CORE-04R5 PASS.
- CORE-05 Time / Execution Budget: CLOSED / COMMITTED at `63813b5` after
  CORE-05R3 PASS.
- CORE-06 Retry / Stop Policy: CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
- CORE-07 Progress Events: CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS.
- CORE-08: CLOSED / COMMITTED at `1a1b029` after CORE-08R3 PASS.
- CORE-09: CLOSED / COMMITTED at `fa7e30f` after CORE-09R2 PASS.
- CORE-10: CLOSED / COMMITTED at `dd72cb2` after CORE-10R3 PASS.
- CORE-11: CLOSED / COMMITTED at `8bda7eb`.
- GOV-01 Task & Authority Contract: CLOSED / COMMITTED at `852ec01`.
- GOV-02 Capability Governance: CLOSED / COMMITTED at `e6dbe3f`.
- ORCH-01 Graph Execution Runtime: CLOSED / COMMITTED at `d3878081`.
- MEM-01 Knowledge / Memory Foundation: CLOSED / COMMITTED at `5e29cdb177838adb1682ab3b36728623d714c5e3`.
- MEM-02 Knowledge Lifecycle + Retrieval / RAG: NEXT / NOT STARTED; sequence only.
- Phase 8E: PAUSED / BLOCKED; no VPS has been created or deployed. Hostinger is
  preferred, with paid procurement deferred until near V1 completion and still
  requiring separate approval.
- Phase 8F: NOT STARTED.
- Phase 8G: NOT STARTED.
- Phase 8H: NOT STARTED.
- Phase 9: PLANNED.
- Phase 10: PLANNED.

## V1 Scope Freeze - ACTIVE

Accepted on 2026-10-01 under V1-MASTER-CONTEXT-SYNC-05-CONSOLIDATED-FREEZE,
additive to SYNC-04 and SYNC-04A. Architecture discovery is frozen until V1
completion. Do not add V1 features, capabilities, canonical agents, phases,
checkpoints, mandatory workflows, or implementation requirements unless a
genuine implementation blocker, security vulnerability, data-loss risk,
authority/governance flaw, serious architectural inconsistency, or correctness
issue prevents V1 completion. Evaluate those exceptions through the normal
scope/authority and review gates; an exception is not execution approval.

NEW IDEA -> critical blocker / security / data loss / authority flaw /
serious inconsistency / completion correctness issue? YES -> evaluate for V1;
NO -> POST-V1 / LATER / REFERENCE. Later ideas must not interrupt the checkpoint
sequence or expand the existing Canonical V1 Definition below.

One ACTIVE and one NEXT checkpoint slot: ACTIVE = None;
NEXT = MEM-02 Knowledge Lifecycle + Retrieval / RAG / NOT STARTED, sequence only.
MEM-01 is CLOSED / COMMITTED at `5e29cdb177838adb1682ab3b36728623d714c5e3`.
GOV-01 remains CLOSED / COMMITTED at `852ec01`; GOV-02 is CLOSED / COMMITTED
at `e6dbe3f`; ORCH-01 is CLOSED / COMMITTED at `d3878081`.
CORE-11 is CLOSED / COMMITTED at `8bda7eb` after Independent Re-review R2 PASS. Lifecycle remains IMPLEMENT -> INDEPENDENT
REVIEW -> BOUNDED FIX if required -> RE-REVIEW -> CLOSURE -> COMMIT -> NEXT.
Core Runtime Foundation = COMPLETE. GOV-01 is CLOSED / COMMITTED at `852ec01`;
no next implementation is authorized or started by this reconciliation.

### Durable Instruction And Learning Ownership

AGENTS.md owns concise, durable action-changing runtime instructions, not a
historical lesson log. CONSTITUTION owns durable governance principles;
ROADMAP owns intended direction; PROJECT_STATE owns current operational truth;
SKILLS own methods; KNOWLEDGE / MEMORY own facts and learning; the TASK CONTRACT
owns current scope, authority, acceptance, and limits.

CORRECTION -> LESSON CANDIDATE -> EVIDENCE -> DEDUPE -> SCOPE -> VALIDATION /
REVIEW -> PROMOTION IF JUSTIFIED. Reuse MEM-02 / MEM-02B discipline: corrections
and PASS results do not automatically become permanent global instructions.

### Closed CORE Refinements And External Trust Boundary

These accepted architectural semantics do not reopen closed checkpoints or
claim that every conceptual event or routing input is implemented.

- CORE-07 remains CLOSED: progress is observable structured state, including
  user-facing semantics, long-running visibility, excessive silent-period
  detection, and useful update hooks. Conceptual events include job_started,
  step_started, tool_started, tool_completed, repair_started, gate_failed,
  replan_requested, progress_update, step_completed, job_completed, job_failed,
  and blocked. Progress evidence grants no authority or completion.
- CORE-09 remains CLOSED: context size, repeated prefix/prompt reuse, cache
  reuse/validity/invalidation, provider cache capability, repeated-context cost,
  and large-context latency inform the architecture. Provider-specific cache
  mechanisms stay inside adapters; the committed cache remains bounded,
  process-local context reuse, not proof of provider-side token savings.
- CORE-10 remains CLOSED: FAST / STANDARD / DEEP / CRITICAL are provider-neutral
  effort profiles; provider-native settings stay inside adapters. Conceptual
  routing inputs include complexity, risk, data sensitivity, credential proximity,
  financial impact, external visibility, context size, expected input volume,
  expected output length, latency requirement, time/cost budgets, provider
  capability/performance history, and verification requirements. Eligibility
  restrictions precede provider selection. Model-facing time signals may be
  advisory; runtime policy enforces hard budgets/timeouts.
- CORE-11 is CLOSED / COMMITTED at `8bda7eb`: pasted text, web pages, emails, documents,
  retrieval, tool output, scraped data, and connector data are external/untrusted
  content. EXTERNAL CONTENT != SYSTEM AUTHORITY != POLICY AUTHORITY != USER
  AUTHORITY. Instruction-like content gains no authority. Use source/trust
  metadata where practical; delimiters alone are insufficient injection defence.
  Independent Re-review R2 passed; closure and commit are complete at `8bda7eb`.

### Phase 9A And Retrieval Efficiency

Where telemetry permits, distinguish request_latency, TTFT/time_to_first_token,
ITL/inter_token_latency, generation_duration, input_tokens, output_tokens,
context_tokens, provider_calls, retries, replans, tool failures, total cost,
cost per run, and cost per completed task. COST PER COMPLETED TASK remains the
primary economic metric. Diagnose start/prefill, streaming/decode, and total
generation latency separately; "model is slow" is insufficient. Low-level
inference-server optimization is not a V1 requirement.

Selective retrieval serves answer quality and runtime efficiency:
large corpus -> deterministic narrowing -> retrieval -> semantic relevance ->
rerank -> task-specific context pack -> preserve important evidence verbatim
when required. Consider relevance, evidence quality, token burden, latency,
and cost. Reuse existing memory/RAG ownership; do not create a RAG Agent.

## Completed / Committed

### Phase 1-5: Core Architecture

- CORE: provider-neutral governance, canonical agents, skills, routing, project onboarding, and knowledge structure.
- CORE: Claude and Codex hybrid routing configuration.
- CORE: business agents, skills, workflows, and connector contracts.

### Phase 6: Verified Local Runtime

Phase 6 is completed and committed at `81aa9b3`. Phase 6M remains the highest
explicit Phase 6 marker, and no Phase 6N is defined. Current combined Phase 6/7
working-tree verification is recorded in `PROJECT_STATE.md`.

- RUNTIME: canonical job model and lifecycle engine.
- RUNTIME: Phase 6B local queue and traceable retries.
- RUNTIME: Worker and provider-neutral Executor contract.
- RUNTIME: Phase 6D deterministic one-time and recurring schedules.
- RUNTIME: Phase 6E opt-in local provider execution.
- RUNTIME: Phase 6F deterministic verification and Reviewer Runtime.
- RUNTIME: Phase 6G persisted scoped human approvals.
- RUNTIME: Phase 6H staged controlled write and dry-run enforcement.
- RUNTIME: Phase 6I controlled Git change set, approval, exact staging, and commit evidence.
- RUNTIME: Phase 6J remote validation, separately approved push, and separately approved pull-request creation.
- RUNTIME: Phase 6M bounded autonomous scheduler loop, claims, leases, heartbeat, retry backoff, restart recovery, audit status, and provider usage guards.

## Completed / Closed

### Phase 7: Remote Control And Runtime Integrations

Goal: allow Agent Company to receive and expose runtime operations through safe remote interfaces while preserving existing approval and authority boundaries.

- REMOTE INTERFACE: transport-independent `RemoteCommandService` with six
  explicit commands and deny-by-default per-user permissions.
- REMOTE INTERFACE: action and project-scoped remote approval/rejection through
  the existing Approval Runtime, with durable pre-mutation audit evidence.
- REMOTE INTERFACE: authenticated Telegram commands restricted to private chats.
- REMOTE INTERFACE: bounded proactive Telegram notifications for approval
  requested/resolved, job completion/failure, and runtime errors.
- REMOTE INTERFACE: authenticated localhost `TASK_SIGNAL` webhook ingress with
  HMAC verification, replay protection, and canonical task dispatch.
- CORE: Telegram humans and webhook machine sources remain separate identity
  and authority classes; neither inbound channel implies approval.

Telegram is an implemented interface/connector, not an agent or orchestrator.
The webhook adapter is loopback-only machine ingress, not public deployment.
Gmail, Drive, Calendar, remote task submission, scheduler mutation, remote
filesystem/Git commands, merge, and deployment are not Phase 7 capabilities.
The final repository-backed Phase 7 architecture and security review passed on
2026-09-24: 142/142 targeted Phase 7 tests and 430/430 full runtime tests passed,
100 Python files compiled, and 15 schemas parsed. Phase 7 is closed. A future
different-provider full-repository audit remains recommended validation, not a
mandatory Phase 8 implementation gate.

## Completed / Committed Capability Checkpoint

### Social Media Capability

This provider-neutral checkpoint sits between Phase 7 and Phase 8. It does not
redefine or begin Phase 8.

- CORE: dedicated Social Media Agent with an explicit boundary from Marketing.
- SKILLS: content calendar, post planning, caption writing, hook generation,
  content repurposing, social competitor monitoring, performance review,
  comment analysis, and weekly social reporting.
- ROUTING: canonical `social_media` task class, `social-media` workflow, and
  `social_media_content` provider capability.
- PROVIDERS: Claude and Codex are equally eligible at neutral configured weight;
  eligibility and weights do not claim runtime availability or quality.
- APPROVALS: planning, drafts, and analysis may remain internal; publication,
  live edits or deletion, public replies, paid campaign changes, budget spend,
  and account changes remain approval-gated external actions.
- CONNECTORS: no social-platform connector, API client, credential, scheduling,
  or autonomous publication capability is implemented.

## Core Runtime Enhancements

- CORE-01 Canonical Result Contract: COMPLETED / CLOSED / COMMITTED at `3f6acb6`.
- CORE-02 Continuation Policy: COMPLETED / CLOSED / COMMITTED at `9d5ead1`.
- CORE-03 Eval Framework: COMPLETED / CLOSED / COMMITTED at `80ead22`.
- CORE-04 Tool / Skill Discovery: CLOSED / COMMITTED at `35f03f8` after
  CORE-04R5 PASS.
- CORE-05 Time / Execution Budget: CLOSED / COMMITTED at `63813b5` after
  CORE-05R3 PASS.
- CORE-06 Retry / Stop Policy: CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
- CORE-07 Progress Events: CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS.
- CORE-08 Context Discovery Before Action: CLOSED / COMMITTED at `1a1b029` after CORE-08R3 PASS.
- CORE-09 Context / Prompt Cache Policy: CLOSED / COMMITTED at `fa7e30f` after CORE-09R2 PASS.
- CORE-10 Compute / Effort Policy: CLOSED / COMMITTED at `dd72cb2` after CORE-10R3 PASS.
- CORE-11 External Content Isolation: CLOSED / COMMITTED at `8bda7eb`.

CORE-01 defines the canonical provider-agnostic Execution Result: WHAT HAPPENED.
Its final independent closure review passed with no Critical or Major findings.
CORE-02 is COMPLETED / CLOSED and committed at `9d5ead1` after CORE-02R6 PASS
with no Critical, Major, or Minor findings. CORE-03 now provides separate
provider-agnostic EvalSpec and EvalResult contracts, explicit deterministic
evaluators, content identity/versioning, typed immutable persistence, and a
minimal CLI. Eval is measurement evidence only: it grants no Reviewer,
approval, continuation, retry, Git, or deployment authority. CORE-03 is
COMPLETED / CLOSED / COMMITTED at `80ead22` after CORE-03R5 PASS with no
Critical, Major, or Minor findings. CORE-04 now provides an explicit immutable
tool registry, capability-first deterministic discovery, separate bounded
selection, and selected-only JSON definition/schema loading. Discovery and
loading grant no execution or governance authority. CORE-04 is implemented,
independently reviewed, closure-reconciled, and CLOSED / COMMITTED at `35f03f8`
after CORE-04R5 PASS with no Critical, Major, or Minor findings. CORE-05 now
provides immutable logical-job elapsed/execution-unit policy, atomic admission
and reservation, complete genesis-to-head validation of one content-addressed
append-only usage ledger, verified state/head caches, restart-safe accounting,
conservative crash recovery, and structured fail-closed exhaustion without
granting execution or governance authority. CORE-05 is CLOSED / COMMITTED at
`63813b5` after CORE-05R3 PASS. CORE-06 is CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
CORE-07 is CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS; CORE-08 is
CLOSED / COMMITTED at `1a1b029` after CORE-08R3 PASS; CORE-09 is CLOSED /
COMMITTED at `fa7e30f` after CORE-09R2 PASS. CORE-10 is CLOSED / COMMITTED at `dd72cb2` after CORE-10R3 PASS.
CORE-11 is CLOSED / COMMITTED at `8bda7eb`.
An aggregate
serialized-result byte ceiling is FUTURE HARDENING / NON-BLOCKING.

### CORE-10 Compute / Effort Policy - CLOSED / COMMITTED at `dd72cb2`

CORE-10 is CLOSED / COMMITTED at `dd72cb2` after CORE-10R3 PASS under
`runtime/compute_policy/`. Compute/effort routing considers task risk,
data sensitivity, provider eligibility, context exposure, and required
review as well as quality, cost, latency, and effort. Security and authority
constraints filter eligible choices before optimization; cheaper or higher-scoring
routes never bypass policy, approval, isolation, or required review.
FAST / STANDARD / DEEP / CRITICAL profiles use trusted canonical compute/security
inputs and filter provider eligibility before routing. Codex/Claude native effort
controls are enforced; unsupported adapters are rejected. Decisions bind exact
work to repository filesystem identity and selected context, report the applicable
fallback reason, and grant no authority. DEC-01/JEV is untouched; CORE-11 is
CLOSED / COMMITTED at `8bda7eb`. See `runtime/compute_policy/README.md` for implementation limits.
R3 final decision: PASS — READY FOR CORE-10 CLOSURE, with no findings.

### CORE-06 Accepted Scope — CLOSED / COMMITTED at `4a6e5c4`

CORE-06 defines provider-neutral Retry Policy and Stop Policy, bounded
no-progress and stuck detection, cycle detection, unit-scoped repair,
repair-scope enforcement, safe retry of only the failed unit, local retry
limits, and the Retry -> Replan boundary. It must not treat provider prose,
`retryable`, `next_actions`, an available budget, or an unfinished job as retry
authority. The implementation is under `runtime/retry/`, with policy/state
schemas and Worker/Scheduler/job integration. `REPLAN_REQUIRED` is a boundary
only for RetryRuntime; ORCH-01 now routes predeclared contracted alternatives
after the verified decision. It does not authorize generated replacement work. CORE-06 is
CLOSED / COMMITTED at `4a6e5c4` after R6 PASS. Exact-work and approval requirements
are preserved, restart/concurrency safety prevents consumed-attempt replay,
and canonical corruption fails closed. Retry remains separate from continuation
and retains the same CORE-05 logical budget without reset or refund.

## Phases 8A, 8B, 8C, And 8D Closed

### Phase 8: Always-On Runtime And Deployment

Goal: move the verified local runtime into an optional always-on execution environment.

Phase 8A architecture design is COMPLETED / CLOSED. The canonical host and
threat-model design is in `infrastructure/`. It defines the infrastructure,
host/process, persistent-state, secrets, Docker, VPS, Telegram, webhook,
deployment/merge authority, Hermes, backup/recovery, threat-model, acceptance,
and staged implementation boundaries. The current baseline remains local; no
operating-system service, running container, VPS, Hermes integration, public
endpoint, merge authority, or deployment authority has been created.

- RUNTIME: plan background runtime hosting, process lifecycle, startup/restart behavior, and recovery.
- DEPLOYMENT: define environment and secrets management for optional hosted operation.
- DEPLOYMENT: evaluate Docker and VPS deployment options.
- DEPLOYMENT: evaluate Hermes only if it provides concrete value as a runtime or host integration.
- DEPLOYMENT: design backup/recovery for operational runtime state.
- CORE: define deployment authority before any deployment implementation exists.

Hermes is optional and must not be treated as the Agent Company core. Merge and deployment authority remain absent until deliberately implemented and approved.

Proposed implementation stages are Phase 8B host configuration and persistence,
8C background process lifecycle, 8D optional Docker adaptation and packaging,
8E VPS deployment, 8F backup/recovery, 8G deployment smoke testing, and 8H final
independent security review. Phase 8B is COMPLETED / CLOSED after its final
independent re-review passed with no critical, major, or required-fix findings.
It adds
the canonical state root, strict non-secret host configuration, fixed path
resolver, dedicated-root rejection before initialization, default-deny
provider child environments, symmetric state/credential/secret separation,
and deterministic readiness failures while preserving local defaults. Phase
8C is COMPLETED / CLOSED after its final independent re-review passed with no
critical, major, or required-fix findings. It adds fixed
scheduler/Telegram/webhook-local lifecycle wrappers, atomic process metadata,
OS-backed singleton enforcement, signals, host heartbeats, read-only status,
and stale-record recovery. The bounded Phase 8C repair makes provider enablement
fail closed before discovery, makes OS signal callbacks notification-only, and
serializes startup publication with persisted stop requests. It installs no
systemd unit, Windows Service, Task Scheduler job, automatic restart supervisor
daemon, Docker/VPS/Hermes component, public webhook hosting, TLS termination,
backup automation, merge authority, or deployment authority.

Phase 8D is COMPLETED / CLOSED after its independent architecture/security
review passed with no critical, major, or required-fix findings. It adds one non-root,
provider-neutral Linux image definition; fixed Compose services for scheduler,
Telegram, and optional webhook-local; one canonical named state volume; strict
per-service host configuration; and read-only lifecycle healthchecks. It adds
no provider CLI, embedded credential, public port, automatic restart policy,
VPS, TLS, reverse proxy, Hermes component, merge authority, or deployment
authority. Compose syntax and deterministic regressions pass, but a Docker
daemon was unavailable, so the image build and live-container smoke remain
unverified. These are Phase 8E runtime-validation prerequisites and do not
reopen Phase 8D. Phase 8E is PAUSED / BLOCKED because the VPS has not yet been
created; deployment has not started. Phases 8F through 8H are NOT STARTED.

Before Phase 8E production use, build the pinned image on the target Linux
architecture; perform an SBOM/vulnerability scan and verify or update the base
digest; validate fresh-volume ownership, non-root initialization, read-only-root
and `/tmp` behavior, cross-container singleton locks, `docker stop` signal and
final-state behavior, and live health transitions; validate the derived Linux
provider image/executable, provider-specific credential mount, authentication,
and environment isolation; and run live Telegram, provider, or public-ingress
smoke tests only with separate explicit approval.

Non-blocking Phase 8C future hardening is a different-provider full-repository
audit, real subprocess singleton-race validation, native Windows signal/ACL
validation, and more race-resistant status-lock probing. Phase 8B's
race-resistant directory-handle containment item also remains non-blocking.

## Accepted V1 Roadmap — Implementation Status And Planned Scope

GOV-01 and GOV-02 below are CLOSED / COMMITTED. Remaining entries are planned
V1 scope unless explicitly identified as implemented.
Its labels define ownership and sequencing only; they grant no execution,
approval, review, write, Git, deployment, or provider authority.

Owner outcome-first UX is PLANNED: the owner specifies the outcome; Agent
Company selects the workflow, agents, skills, tools, context, and providers
within the applicable authority contract.

CORE-08 implements the bounded foundation for context discovery before action, graceful
degradation and fallback resolution, semantic skill selection, semantic
context selection/reranking, selective verbatim context retention, and Code
Intelligence / Repository Index. Fallback order is preferred connector,
alternative connector, file/CSV/upload, manual structured input, then explicit
BLOCKED. Fallback preserves evidence and authority requirements. It is
CLOSED / COMMITTED at `1a1b029` after CORE-08R3 PASS.
See `runtime/context/README.md` for integration and bounded index limitations.

Skill discovery provides provider-neutral metadata and relevance contracts with
name, description, required capabilities, inputs, outputs, prerequisites,
references, and templates. Load only skills relevant to the task. Workflows
request connector capabilities rather than hard-coded vendors.


### A. Governance

#### GOV-01 — Task & Authority Contract

GOV-01 implements the canonical Task Contract: objective, inputs, expected
outputs, allowed tools, write scope, acceptance criteria, required checks,
required evidence, and explicit stop conditions. It also owns Risk / Delegation
Levels L0-L5, blast radius, reversibility, approval requirements, and
Evidence-Gated Task Completion.

Executor or agent success is not task completion. `DONE` requires successful
execution plus satisfied acceptance criteria, required evidence, and every
required review or gate. Execution completion, eval evidence, Reviewer outcome,
human approval, and task completion remain distinct states; none substitutes
for another. Progress, candidate selection, or an executor success report alone
cannot mark the task complete.

Implementation is integrated into canonical JobRuntime admission, Worker and executor
boundaries, existing approval fingerprints, retry/continuation inheritance, and
terminal persistence. The contract and completion receipts use write-once anchors
inside the existing job state. Missing acceptance/evidence cannot become DONE.
Opaque native-tool CLI providers fail closed; no native CLI confinement is claimed.
GOV-01 is CLOSED / COMMITTED at `852ec01` after verified independent PASS and GOV-01C2 closure.
GOV-02 is CLOSED / COMMITTED at `e6dbe3f` after independent R5 PASS and verified owner closure.
Details: [Task Contract](governance/task-contract/README.md).

#### GOV-02 — Capability Governance

GOV-02 now implements Capability Certification, Decision Audit Trace,
policy/authority provenance, blast-radius gates, and reversibility gates.
Capability profiles are READ_ONLY, LOCAL_WRITE, EXTERNAL_PREPARE,
EXTERNAL_EXECUTE, and SENSITIVE_EXECUTE, integrated with delegation, blast
radius, reversibility, approval, and capability certification. These are
execution profiles, not canonical agents.

The current implementation is in `runtime/core/capability_governance.py`,
`runtime/core/capability_actions.py` and `governance/capability-governance/`,
with `schemas/capability-certification.schema.json` and five capability test
modules. Certification and decision traces extend canonical task, execution,
review, approval, Git and progress stores; separate capability-certification
and decision-trace directory labels are superseded, not outstanding targets.
Unsupported external effects fail closed.
GOV-02 is CLOSED / COMMITTED at `e6dbe3f` after independent R5 PASS and owner closure.
All prior findings are CLOSED, with 0 critical / 0 major / 0 minor.
See [closure evidence](governance/capability-governance/CLOSURE.md).
ORCH-01 is CLOSED / COMMITTED at `d3878081`; `runtime/graph/` and
`orchestrator/graph/` are CURRENT. MEM-01 is CLOSED / COMMITTED at
`5e29cdb177838adb1682ab3b36728623d714c5e3`; NEXT: MEM-02 / NOT STARTED, sequence only.

### B. Graph Orchestration

#### ORCH-01 — Graph Execution Runtime

CLOSED / COMMITTED at `d3878081` after independent R4 refresh-02 PASS and owner
closure PASS. All required validation tiers passed on frozen source; R3-M1 and
Signals 1/2/3 are CLOSED, with no unresolved acceptance blockers. See
[owner closure](orchestrator/graph/CLOSURE.md). This roadmap is status evidence only.

CURRENT: `runtime/graph/`, `orchestrator/graph/`, graph plan/binding schemas,
and graph targeted/adversarial/integration tests. Admission extends canonical
jobs, task anchors, Worker, execution intent/provenance, budget reservations,
request/package profiles and CLI. Correction/replan routes use predeclared
contracted alternatives after canonical REPLAN_REQUIRED. No new canonical
agent or independent scheduler, authority, retry, state or review owner exists.
See [invariants and classification](orchestrator/graph/ACCEPTANCE.md).

ORCH-01 is not CORE-12. A loop operates inside a node; a graph connects nodes.
The owner specifies outcomes rather than workflows; Agent Company selects
clarification, task contract, graph, agents, skills, context, tools/providers,
eval/review, and approval points. Planned scope includes Planner / Splitter,
Worker nodes, deterministic nodes,
gate nodes, human gates, dependencies, fan-out, fan-in/merge, correction,
replan, and learning edges, edge validation, isolated fan-out contexts, and
unit-level repair integration.

Deterministic nodes may perform merge, deduplication, sorting, hashing, diff,
schema validation, test execution, artifact verification, counting, or
dependency resolution.

### C. Knowledge / Memory / RAG

Knowledge is what the system knows. Memory is what happened or was learned.
State is what is happening now. These remain separate.

- MEM-01 — Knowledge / Memory Foundation: CLOSED / COMMITTED at
  `5e29cdb177838adb1682ab3b36728623d714c5e3`. CURRENT / COMMITTED contract-only
  `runtime/memory/`: provider-neutral
  `MemoryInterface`, project isolation, immutable source/capture/review provenance,
  confidence and claim-bound verification. A1-A7 and independent R03-M1 PASS
  are owner-supplied; see the closure evidence and limitations above.
- MEM-02 — Knowledge Lifecycle + Retrieval / RAG: NEXT / NOT STARTED; capture, normalize,
  deduplicate, classify, connect, store, retrieve, rerank, build context packs,
  selectively retain relevant context, act, verify, and learn from run traces.
  Anchored evidence-backed memory may link to files,
  symbols, tasks, workflows, decisions, runs, tests, evidence, agents, or
  capabilities and record provenance, verification, confidence, validity, and
  supersession.
- MEM-02B — Learning Constraint Pipeline: observation -> candidate lesson ->
  evidence -> deduplication -> scope -> validation/review -> promotion -> active
  planning constraint. A PASS does not automatically become a permanent rule.
- MEM-03 — Memory Providers: local provider first. Hindsight is only a future
  prototype provider behind `MemoryInterface`; SwarmVault and Vault Curate are
  reference patterns, not core dependencies.

### D. Agent Expansion

The current canonical agent count is 10. V1 targets 14 by later adding:

11. Finance & Pricing
12. Analytics
13. Content
14. Design

The complete V1 target is Project Manager, Software, Research, Knowledge
Manager, Reviewer, Sales, Marketing, Operations, Communications, Social Media,
Finance & Pricing, Analytics, Content, and Design. Agents 11-14 remain PLANNED
until repository evidence proves implementation.

Legal, SEO, AEO, GEO, QA, Security, Lead Finder, Trend Research, Community
Management, Repurposing, Video Generation, Remotion, Higgsfield, RAG, Document
Intelligence, JEV, Memory, SAGE, Sentinel, Chimera, Firecrawl, and DataForSEO
are not separate canonical agents. They belong to skills, workflows, tools,
shared/runtime capabilities, domain profiles, or Project Packs.

### E. Capability Expansion

- CAP-SALES: lead finding, lead research, qualification, outreach, and
  follow-up.
- CAP-SEARCH-GROWTH-01: one cross-agent Search Growth system covering SEO, AEO,
  GEO, search intent, commercial keyword strategy, technical and on-page SEO,
  internal linking, content funnel, authority building, AI-search readiness,
  answer extractability, conversion, experiments, and seasonal planning.
- CAP-REV-01: QA, Security, Knowledge, Release, External / Client-Facing
  Output Review, Citation Verification, Extraction Verification, Semantic
  Completion Verification, and Change Impact Review. Change Impact Review considers the task, acceptance criteria, diff, changed symbols,
  dependencies, architecture decisions, related memory, previous failures, and
  tests.
- Code Intelligence / Repository Index: CORE-08 implements a bounded in-memory
  file index, Python symbols/imports, syntactic call names, one-hop related and
  affected files, and relevant repository context in `runtime/context/repository.py`.
  Knowledge/memory retrieval is an explicit read-only adapter interface. Advanced
  graphs and cross-language semantic call resolution remain deferred.

#### CAP-SOC-01 - One-Person Social Media Team / Social Media Operating System

PLANNED / NOT STARTED. Extend the committed Social Media skills/routing checkpoint
into a stateful cross-agent capability, without creating another Social Media
agent or duplicating the canonical `social_media` capability routing.
The existing Social Media agent remains domain owner and coordinator.
Research owns evidence and intelligence; Content owns copy and narrative;
Design owns visual assets; Analytics owns measurement and experiment analysis;
Reviewer independently checks quality, claims, safety, and required gates.
Content, Design, and Analytics remain planned agents within the 14-agent V1
target, not currently implemented roles.

Planned content lifecycle:
IDEA -> RESEARCH -> DRAFT -> PREVIEW -> REVIEW -> REVISION -> APPROVED -> FINAL RENDER -> SCHEDULED -> PUBLISHED -> MEASURED -> REPURPOSE.
State transitions retain provenance, versions, approval scope, and publication
and measurement evidence. A lifecycle label or schedule is never execution
authority; changed content must satisfy the applicable review/approval gates.

Scope includes research/intelligence, content studio, publishing/scheduling,
community/engagement, growth experiments, cross-platform repurposing,
performance evidence -> memory/learning, and human handoff. Operational content
state stays separate from durable lessons; promotion follows MEM-02B evidence,
validation, and review. Social integrations remain connectors/tools. JEV may
later assist classification/triage but never grants execution authority.

V1 priority: lifecycle, approval/scheduling, repurposing, basic community triage,
human handoff, performance -> memory, and basic Social Media HQ representation
under Phase 9B. Advanced DM autonomy, influencer automation, advanced attribution,
complete platform coverage, and full autonomous community management remain
non-blocking. External publication, public replies, account changes, and spend
retain applicable explicit human approval requirements.

PLANNED target ownership (paths remain absent):
`skills/social-media/lifecycle/` owns reusable lifecycle methods;
`orchestrator/workflows/social-media-operations/` owns coordination;
`apps/control-room/social-media-hq/` owns the Phase 9B view over canonical state.
Existing `agents/social-media/`, `skills/social-media/`, and
`orchestrator/workflows/social-media.yaml` remain CURRENT checkpoint artifacts,
not evidence that CAP-SOC-01 is implemented.

#### CAP-CREATIVE-01 - Creative Media Production

ACCEPTED ARCHITECTURE / PLANNED / NON-BLOCKING FOR V1. Broadens the earlier
CREATIVE_MEDIA_GENERATION concept; no new agent, phase, or V1 completion blocker.
Content and Design responsibilities remain distinct from Social Media
coordination and Reviewer gates. Creative Media remains vendor neutral.

Two lanes: deterministic media (Remotion, real screen capture, Playwright/browser
capture, charts, tables, cards, subtitles, coded motion graphics, timeline
assembly, render/export) and generative media (Higgsfield, image/video models,
synthetic scenes, cinematic assets, future generative adapters).
Text/data/UI-heavy visuals prefer real capture or deterministic rendering;
synthetic/cinematic visuals may use generation. GitHub pages use browser capture,
terminals use real capture, charts/tables/subtitles use deterministic rendering.
Remotion is an optional deterministic tool/runtime capability; Playwright capture
is an optional browser/media tool; Higgsfield is an optional generative
connector/tool/adapter. None is an agent, Reviewer, policy authority, or core
provider architecture.

Accepted target workflow: owner goal -> research/reference if needed ->
script/hook -> creative brief -> storyboard/shot plan -> deterministic vs
generative asset selection -> capture/generation -> assembly -> preview ->
review -> revision -> final render -> subtitles/platform adaptation -> approval
-> publish -> analytics -> learn. Production gate: storyboard/composition ->
still preview -> review -> PASS -> full render. Applicable approval gates still
apply; review PASS never grants publication authority.

Shared skill pattern: transcript -> glossary normalization -> subtitle
segmentation -> review. Reference analysis may examine hook, pacing, timing,
editing grammar, visual structure, transcript, and transitions.
REFERENCE -> LEARN PATTERN; REFERENCE != COPY.
These target patterns are not new mandatory V1 workflows.

CAP-SOC-01 remains bounded to lifecycle, approval/scheduling, cross-platform
repurposing, basic community triage, Human Handoff, and performance -> memory,
with basic Phase 9B HQ representation. Complete creative automation, advanced
Remotion automation, autonomous DM management, advanced influencer discovery,
advanced attribution, every publishing connector, advanced experiment engine,
and a full generative-media pipeline are not V1 blockers.

Vendor/third-party performance claims must retain source, date, conditions,
and verification status. Marketing claims are not measured Agent Company
performance; adoption or comparative claims require relevant reproducible
local evidence, with uncertainty and limitations disclosed.

#### CAP-DOC-01 - Document Intelligence & Structured Summarization

ACCEPTED ARCHITECTURE / POST-V1 / LATER IMPLEMENTATION / NOT A V1 BLOCKER.
Legal summarization is Document Intelligence + Legal Domain Profile, not a
Legal Agent. Potential scope: ingestion, normalization, metadata/structured
extraction, structured summarization, citation grounding, document comparison,
long-document processing, summary-indexed retrieval, evaluation, review/escalation.

General principles may reuse existing V1 systems: define extraction fields
before generation, use structured output where appropriate, preserve provenance
and evidence/citation links, and strengthen review for high-stakes work.
Missing/evidence states include not_found, not_specified, unknown, conflicting.
MISSING EVIDENCE != PERMISSION TO INVENT.

Optional future MEM-02/RAG pattern: source -> raw document + metadata + document
summary + section summaries + retrieval index; query -> summary-level shortlist
-> document/section retrieval -> semantic rerank -> context pack.
Future long-document pattern: document -> structure/sections -> chunk ->
structured extraction -> preserve citations -> merge -> conflict check -> synthesis.
Both are POST-V1 refinements, not new V1 deliverables.

Consequential legal/financial/compliance work follows AI extraction ->
evidence/citation verification -> Reviewer -> human expert where consequential.
AI summaries do not become legal authority. Reuse GOV-01 / GOV-02 / Reviewer.

### Optional Future Target Paths - PLANNED ONLY

No paths below are implementation evidence; do not create empty future folders.
Creative tool targets: `tools/creative-media/remotion/`,
`tools/creative-media/playwright-capture/`, `tools/creative-media/higgsfield/`.
Skill targets: `skills/content/transcription-normalization/`,
`skills/content/subtitle-segmentation/`, `skills/design/motion-graphics/`,
`skills/design/storyboard/`, `skills/social-media/reference-analysis/`,
`skills/social-media/reel-production/`; `skills/document-intelligence/` with
`structured-extraction/`, `summarization/`, `citation-grounding/`,
`metadata-extraction/`, `document-comparison/`.
Workflow targets: `workflows/creative/` with `video-production/`,
`reference-analysis/`, `preview-review/`, `render-revision/`;
`workflows/document-intelligence/` with `single-document-summary/`,
`long-document-summary/`, `batch-document-review/`, `summary-indexed-retrieval/`.
These are conceptual path labels only; approved implementation must reconcile
workflow placement with the existing `orchestrator/workflows/` convention.
Future document runtime ownership: `runtime/documents/` with `ingestion/`,
`normalization/`, `chunking/`, `indexing/`.

### F. Phase 9

- Phase 9A — Observability: task success, cost per completed task, latency,
  provider calls, tool errors, retries, continuation, replans, escalation, and
  eval history; Unified Run Trace, Exact Replay, Semantic Regression,
  Trace → Eval → Lesson Candidate, and provider/model behavioural comparison.
  Lesson candidates still require MEM-02B validation and promotion. Later graph
  metrics include planned/executed/skipped nodes,
  parallel branches, repairs, replans, gate failures, human interventions,
  rollbacks, critical-path time, provider/token cost, and wall-clock time.
  Decision/JEV metrics include decision quality against declared evals,
  confidence calibration, abstention/escalation and override rates, policy
  rejection, candidate coverage, cost, and latency. Compare the bounded pilot
  against deterministic baselines before expanding its scope.
  Unified Run Trace links input/context identities, candidates, decisions,
  policy checks, execution, eval, review, and approval evidence. Exact Replay
  requires captured versions and inputs; replay cannot silently repeat external
  effects or reuse stale authority. Semantic Regression measures declared
  behavioural expectations separately from byte-for-byte replay.
- Phase 9B — Control Room: Projects, Agents, Jobs, Approvals, Providers, Costs,
  Reviews, Evals, Graph execution, Knowledge, Memory, Decisions, Lessons,
  Planning Constraints, and Context Packs. Control Room Owner Home is the
  primary natural-language goal entry: "What do you want to do?" Manual agent,
  skill, and workflow selection is not the primary UX. It remains a view/operator
  layer over canonical state, never a second source of truth. Social Media HQ
  represents CAP-SOC-01 lifecycle, calendar/approval queue, handoffs, publication
  evidence, and performance/learning links; the basic representation is V1.
- Phase 9C — Operating Layer: Morning Map, State Delta, Weekly Close / Weekly
  Compounding, Lessons Learned, Automation Opportunities, and Pre-flight Review.

### G. Decision Engine / JEV

- DEC-01 — Provider-neutral Decision Engine: deterministic rules plus worker,
  skill, context, and option selectors; classification, scoring, ranking,
  confidence, and escalation. Generation belongs to
  an execution provider, bounded decisions to the Decision Engine or possible
  JEV adapter, and exact rules to deterministic code. Decision authority stays
  separate from execution authority.
- DEC-02 — JEV Pilot: initially limited to low-risk next-worker routing, skill
  selection, context relevance/reranking, and semantic eval. Context compaction
  selection, stuck detection, and citation/extraction verification are later
  candidates only if metrics justify them. JEV is not an agent, Reviewer,
  approval/security authority, or normal generation provider.

DEC-01 planned refinements:

- Decision State Contract: record the decision objective, scoped evidence and
  provenance, eligible candidate identities/versions, constraints, scores,
  confidence, selection or abstention, rationale, and escalation outcome.
  Decision state is evidence; policy authorization is recorded separately.
- Live Candidate Menu: derive candidates from the current eligible registry
  and available evidence at decision time; reject stale or unavailable choices.
  Candidate != selected; selected != loaded; loaded != authorized.
- Decision escape hatch: abstain, request material clarification, use a valid
  deterministic fallback, or escalate to a human when candidates/confidence
  are inadequate. Never invent a candidate or broaden authority to proceed.
- Composite scoring: combine declared quality/relevance, confidence, cost,
  latency, and task-fit signals with explicit weights and provenance after
  hard eligibility/security filters. Scores do not override policy or gates.

Canonical JEV rule: **JEV judges. Policy authorizes. Executor acts.**

JEV is a bounded semantic judging component: it does not authorize actions,
serve as an agent or Reviewer, or act as a normal generation provider.

### H. Deployment

- Phase 8E — Real VPS deployment: PAUSED / NOT COMPLETE. Hostinger is preferred,
  but no VPS has been purchased, provisioned, or deployed. Procurement remains
  deferred until near V1 completion and requires separate approval. Phase 8D
  live-image and target-Linux prerequisites remain required.
- Phase 8F — Backup / Recovery: NOT STARTED.
- Phase 8G — Production smoke tests: NOT STARTED.
- Phase 8H — Final deployment security review: NOT STARTED.

All four remain required before the system can be described as
production-deployed or always-on.

### I. Phase 10 — Project / Domain Packs

Brightshore is the first production Project Pack. A pack may reference skills,
workflows, knowledge, policies, connector capability requirements, templates,
and project configuration, but never duplicates the Agent Company runtime
or canonical agents. YouTube, social content, digital products, travel, Etsy, and other
packs are later expansion and do not block V1 unless explicitly approved.

## Canonical V1 Definition

V1 consists of CORE-01 through CORE-11; GOV-01 and GOV-02; ORCH-01; the
Knowledge / Memory / RAG foundation; 14 canonical agents; essential Sales,
Search Growth, Reviewer, and the prioritized CAP-SOC-01 capability; Code Intelligence; Phase 9A through
9C; DEC-01 and the bounded DEC-02 pilot; Phase 8E through 8H deployment and
security completion; and Brightshore as the first production Project Pack.

## Target-Tree Ownership / DOC-GOV-01

`README.md` owns the CURRENT/PLANNED physical-tree summary; this roadmap owns
capability scope and target-path ownership; `PROJECT_STATE.md` owns current
status; `TODO.md` owns remaining work. Follow implementation -> validation ->
review -> closure -> commit -> physical-tree audit -> DOC-TREE reconciliation.
Only physically implemented paths become CURRENT. Keep future paths PLANNED
and absent until approved implementation supplies real content. Do not create
empty target folders, duplicate agents/capabilities, or rewrite historical
review evidence to imply current implementation.

### DOC-GOV-01 Freeze Health Checks

Verify freeze integrity; no unplanned agents; 10 current vs 14 target remains
explicit; later ideas do not interrupt checkpoints; AGENTS stays concise and
action-changing; lessons follow MEM promotion; CORE-10 stays provider neutral;
CORE-11 preserves external-content trust boundaries; Creative Media remains
capability/tool architecture and Remotion/Playwright/Higgsfield stay tools;
CAP-CREATIVE-01 stays non-blocking; CAP-SOC-01 stays bounded; CAP-DOC-01,
local inference, and fine-tuning stay POST-V1; planned folders stay absent.

## Later / Important — Not V1 Blockers

- CAP-SOC-01 advanced DM autonomy, influencer automation, advanced attribution,
  complete platform coverage, and full autonomous community management.
- CAP-CREATIVE-01 implementation and complete creative automation: non-blocking.
- CAP-DOC-01, summary-indexed retrieval, and long-document refinements: POST-V1.
- Local inference: quantization, KV-cache optimization, PagedAttention,
  vLLM optimization, continuous batching, speculative decoding, GPU tuning,
  and self-hosted inference optimization are POST-V1 / REFERENCE, not blockers.
- Fine-tuning is POST-V1 / LATER; prioritize structured prompting, schemas,
  retrieval, context selection, evals, memory, and provider routing first.

- Persistent Agent Mailbox.
- Git Worktree Isolation.
- Advanced Agent Teams / parallel execution.
- Credential / Secret Broker.
- Advanced Knowledge Graph.
- Multi-model Council / disagreement escalation.
- Additional memory providers.
- Advanced context compaction.
- Browser Semantic Action Selector.
- Typed Tool-call Semantic Compiler.
- Jevgrep.
- Beacon importer/adapter.
- Later JEV / Beacon experiments beyond the bounded DEC-02 V1 pilot.

## Deferred Or Not Implemented

- Merge, release, and deployment authority are not implemented.
- Public Telegram webhook mode and public webhook hosting are not implemented.
- Broader Gmail, Drive, and Calendar runtime integrations remain contract-only.
- Phase 8D Docker adaptation and packaging is completed, closed, and not
  deployed.
- Phase 8E is PAUSED / NOT COMPLETE and requires separate human approval.
- Phases 8F, 8G, and 8H are NOT STARTED.
- GOV-01/GOV-02 and ORCH-01 are CLOSED / COMMITTED, not pending work; their
  historical review and closure evidence remains unchanged.
- MEM-01 contracts are CURRENT / COMMITTED, CLOSED / COMMITTED at
  `5e29cdb177838adb1682ab3b36728623d714c5e3`.
- MEM-02/02B/03, agents 11-14, CAP-SOC-01 and other specifically planned
  capability expansion, advanced Code Intelligence, Phase 9, Decision
  Engine/JEV, and Phase 10 remain planned and unimplemented as described above.
- The SYNC-06 R4/R2 refinements are documentation mappings, not implemented
  features, passed tests, reopened checkpoints, or authority for new work.
