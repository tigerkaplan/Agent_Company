# Agent Company Roadmap

## Agent 11 M2 Offline Pilot Scope - 2026-10-26

`AC-AG11-M2-ACCEPT-20261026-03` owner-accepts only the exact offline,
synthetic and non-authoritative M2 pilot at
`pilots/agent11_finance_pricing/synthetic_cost_scenario.py` (SHA-256
`4855FBF9C90D01BB8A37DA5C00954BE5D1A654A6705694C74F034F90846088AA`)
and `pilots/agent11_finance_pricing/test_synthetic_cost_scenario.py` (SHA-256
`DB8DA82DADC010F6DEEA1FB1D140AEBD9071EBDB0431036A06200A7ECF55BC98`).
Independent checkpoint `AC-AG11-M2-REVIEW-20261026-02` returned
`REVIEW_PASS / CLOSURE_READY`, 30/30 scoped tests PASS and zero new findings.

This bounded acceptance preserves the completed M1 exact-division Git closure,
the unchanged M1 helper identity
`08F50215E79D81BEB256ECB1D27FD9C3671B0D83D065EB6B88774CE7FF9556B3`,
and the existing M1 narrow-sequencing authorization. It adds no governance
mechanism, roadmap phase, agent, capability, workflow, runtime integration or
production authority. The M2 files remain uncommitted, and Agent 11 remains
**APPROVED V1 / DESIGN REVIEW ACCEPTED / NOT PRODUCTION IMPLEMENTED**.

`MEM-03` remains **BLOCKED / HOLD / NOT ACCEPTED**; `BUILD-02` remains
`REVIEW_PASS / ACCEPTANCE BLOCKED`; `CONTRACT-04` installation remains
**BLOCKED**; and the frozen 14-role scope is unchanged. Any later implementation,
runtime promotion or Git lifecycle requires its own authorization and applicable
gates. `automatic=false`.

## MEM-03 Event Log Receipt Architecture Disposition - 2026-10-25

The owner records Windows Event Log as **NO_GO** for the authoritative MEM-03
bootstrap-failure durable receipt channel under
`AC-MEM03-EVENTLOG-DISPOSITION-20261025-04`. This preserves the preceding
`NO_QUALIFIED_EXISTING_CHANNEL` and `Application CANDIDATE_UNSUITABLE`
findings.

An independently pre-provisioned custom channel can separate ordinary
principal access in design: Controller publish, Reviewer read-only, Executor
excluded, and elevated configuration retained by a separate host-security
custodian. That separation does not solve the receipt contract. Windows event
publication provides buffered submission without a synchronous per-receipt
durable-commit acknowledgement. Query visibility, circular or retain-mode
configuration, export and forwarding do not by themselves prove crash-durable
commitment to the publisher.

The blocker is therefore **CONTRACT MISMATCH**, not a proven defect in current
runtime code. Repeating Event Log configuration trials without a materially
different durability mechanism is closed. Event Log remains eligible only as
secondary diagnostic evidence and is not an approved authority store, receipt
channel, implementation dependency or qualification target.

Before MEM-03 bootstrap, a separate independently administered transactional
receipt mechanism must already exist and must be qualified for exact custodian,
writer and independent verifier identities; executor exclusion; synchronous
durable acknowledgement; restart, full-capacity and partial-failure behavior;
retention, integrity, tamper evidence, archival and recovery. No replacement
service or operator is currently claimed to exist or be approved.

`MEM-03` remains **BLOCKED / HOLD / NOT ACCEPTED**. `BUILD-02` remains
`REVIEW_PASS / ACCEPTANCE BLOCKED`; `CONTRACT-04` installation remains
**BLOCKED**; the frozen 14-role boundary and accepted Agent 11-14 designs remain
unchanged. This decision grants no provisioning, implementation, test, Windows,
installation or Git authority. `automatic=false`.

## MEM-03 Approved V1 Trust Boundary - 2026-10-25

The owner-approved `AC-MEM03-TRUST-BOUNDARY-20261025-01` decision selects
**OWNER APPROVED — OPTION A**: privileged Windows administrators are trusted V1
computing-base members, and privileged-administrator compromise is outside the
local receipt-service threat model. This resolves only that threat-model branch.
It does not make administrator capability a receipt, independent verification,
approval or ordinary workflow authority, and it does not claim administrator-
resistant local immutability.

Controller, Reviewer and Executor separation remains mandatory. Any V1 local
receipt design must still establish a bounded authenticated Controller writer,
an independent read-only Reviewer, Executor exclusion, synchronous durable-
commit acknowledgement, immutable receipt identity and integrity evidence,
bounded retention and capacity failure, fail-closed restart/recovery, qualified
custody and independent acceptance evidence. The exact qualified human
host-security custodian and governed break-glass rights remain unresolved.

`MEM03-LOCAL-RECEIPT-SVC-V1` is retained only as a **CANDIDATE / NOT APPROVED /
NOT IMPLEMENTED** architecture. No service, database, pipe, key, storage root or
operator is asserted to exist or be approved. The current
`AC-MEM-03-090` / `AC-MEM-03-092` contract retains existing execution storage
and adds no independent receipt database or authority service. Selecting this
candidate later would therefore require a separately authorized contract
amendment, independent affected security review, explicit owner approval and
independently administered pre-bootstrap provisioning and qualification.

Windows Event Log remains **NO_GO**. `MEM-03` remains **BLOCKED / HOLD / NOT
ACCEPTED**; `BUILD-02` remains `REVIEW_PASS / ACCEPTANCE BLOCKED`;
`CONTRACT-04` installation remains **BLOCKED**; and the frozen 14-role boundary
and Agent 11-14 design-only implementation status remain unchanged. This record
grants no implementation, provisioning, installation, test, Windows or Git
authority. `automatic=false`.

## Agent 14 Design Accepted Design - 2026-10-25

Agent 14 is **APPROVED V1 / DESIGN REVIEW ACCEPTED / NOT IMPLEMENTED**.
The owner accepted AC-V1-AGENT14-DESIGN-005 `REVIEW_PASS`, resolving
`AG14-DESIGN-R1` through `AG14-DESIGN-R3` only for the reviewed 552-line,
35,534-byte source at
`C:/Users/DELL/Downloads/AC_V1_AGENT14_DESIGN_DRAFT_20261024.md`, SHA-256
`9BDB320EB6450D7FE2AA8C475D4BE753198C02EE0ADBDF2FA2D85A646B188138`.
The external source is evidence by exact identity; its complete text is not
copied into the repository.

The bounded V1 design operation set is `PREPARE_STATIC_VISUAL`,
`ADAPT_STATIC_VISUAL` and `INSPECT_STATIC_VISUAL`. The practical objective is
to produce real internal draft artifacts: an editable SVG source and an exact
rendered PNG/preview with immutable provenance, metadata and inspection
evidence. This objective is accepted design, not evidence that a renderer,
adapter, provider capability or artifact-production runtime exists.

Inspection and planning remain `READ_ONLY`, L1, `write_scope: null`. Artifact
production is a distinct `CONTROLLED_WRITE`, L2 operation requiring separate
human execution approval, an exact job-specific write scope, bounded mutation
evidence and independent review. Publication, external sends, live-site writes,
purchases, deployment and unapproved generation services remain prohibited.

One immutable canonical `DesignRequest` reference must be identical in job
inputs and Task Contract inputs. Its pre-approval material scope includes the
selected serializer, renderer, fonts, versions, complete CORE-04 registry and
toolchain identities/digests, output scope, sources and required checks. The
existing authorization fingerprint and every material identity must be
revalidated immediately before writing; substitution, drift, fallback and
stale or cross-attempt approval fail closed. CORE-04 discovery, selection and
loading do not grant execution authority. CORE-11 preserves untrusted external
text isolation; binary bytes are not provider inputs. The initial design's only
raster path is deterministic trusted-serializer normalization and embedding of
an exact approved first-party PNG.

Canonical `ExecutionResult` retains deterministic `blocked`, `needs_human`,
`failed` and `needs_review` boundaries, canonical blocker/error forms,
retryability, real evidence, identical `artifacts`/`output_refs` and
`next_actions.automatic=false`. Independent human visual review inspects the
actual PNG; review PASS does not grant publication authority.

Content owns copy and narrative; Marketing owns positioning, campaigns and
brand policy; Social Media owns channel context and coordination; Software owns
implementation; Research owns evidence collection; Reviewer remains
independent; and the human owner retains approval, rights-policy and publication
authority. Provider eligibility remains pending and fail-closed. No provider
manifest, capability certification, runtime eligibility, role, skill, workflow,
schema or renderer changed.

`AG14-CM-01` through `AG14-CM-07` remain implementation prerequisites. Final
SVG/PNG policy, limits, staging root, renderer, rights, accessibility, provider
qualification, whether future semantic image inspection may transmit binary
content to a separately qualified provider, and future generative-media scope
remain unapproved. The existing `CAP-CREATIVE-01` classification remains
**ACCEPTED ARCHITECTURE / PLANNED /
NON-BLOCKING FOR V1**; this record authorizes no generative-media service.
Agents 11 through 13 remain closed, the frozen 14-role roster is unchanged,
`MEM-03` remains **BLOCKED / HOLD / NOT ACCEPTED**, `BUILD-02` remains
`REVIEW_PASS / ACCEPTANCE BLOCKED`, and `CONTRACT-04` installation remains
**BLOCKED**.

## Agent 13 Content Accepted Design - 2026-10-24

Agent 13 is **APPROVED V1 / DESIGN REVIEW ACCEPTED / NOT IMPLEMENTED**.
The owner accepted AC-V1-AGENT13-DESIGN-007 `REVIEW_PASS` and approved
`AC-AG13-POLICY-001` as **APPROVED - DESIGN SCOPE ONLY**.
`AG13-DESIGN-R1` through `AG13-DESIGN-R4` are `REVIEW_RESOLVED`, and
`AG13-DESIGN-E1` is **CLOSED / EVIDENCE GAP RESOLVED**, only for the reviewed
646-line source at
`C:/Users/DELL/Downloads/AC_V1_AGENT13_DESIGN_DRAFT_20261024.md`, SHA-256
`9807DB16BFC98F86079BB0E68FC4101A57802447607A7F804D540315C695CDA7`.
The external source is evidence by exact identity; its complete text is not
copied into the repository.

The frozen V1 Content role retains the closed operation set `GENERATE_DRAFT`,
`EDIT_DRAFT` and `REPURPOSE_DRAFT`. The approved initial operational design
slice is exactly `EDIT_DRAFT` / `INTERNAL_REVIEW` / user-supplied original
content / `FIRST_PARTY_EDIT_ONLY` / `OWNER_SUPPLIED` or `UNVERIFIED` claims.
It is `READ_ONLY`, L1, `write_scope: null` and `automatic=false`. It preserves
source identity, immutable request binding, the existing Task Contract and
authorization fingerprint, CORE-11 isolation, canonical `ExecutionResult`,
budgets, approvals, evidence and independent review. It produces internal
drafts only and has no publication, sending, purchasing or consequential-write
authority.

`GENERATE_DRAFT` and `REPURPOSE_DRAFT` remain within V1 design but are
fail-closed wherever independent factual verification or third-party
copyright/reuse permission is required. `OWNER_SUPPLIED` and `UNVERIFIED`
content cannot be promoted to `VERIFIED` merely because it was supplied by a
user. Source possession, user assertion, Research output or Reviewer `PASS`
does not establish copyright permission. The policy creates no canonical
issuer, rights registry, approval action or unrestricted verifier.

Marketing retains strategy, positioning, campaigns and audience decisions;
Communications retains message-specific drafting and delivery; Social Media
retains posts, captions, hooks, calendars and channel repurposing; Research
retains evidence collection and source-quality verification; Reviewer remains independent;
and planned Agent 14 retains visual design. No proposed Agent 13 role, skill,
workflow or schema path is created. Provider qualification remains pending and
the new capability remains ineligible until separately qualified. Agent 11 and
Agent 12 remain closed, the frozen 14-role roster is unchanged, `MEM-03` remains
**BLOCKED / HOLD / NOT ACCEPTED**, `BUILD-02` remains `REVIEW_PASS /
ACCEPTANCE BLOCKED`, and `CONTRACT-04` installation remains **BLOCKED**.

## Agent 12 Analytics Accepted Design - 2026-10-24

Agent 12 is **APPROVED V1 / DESIGN REVIEW ACCEPTED / NOT IMPLEMENTED**.
AC-V1-AGENT12-DESIGN-008 returned the owner-accepted `REVIEW_PASS`, resolving
`AG12-DESIGN-R1` through `AG12-DESIGN-R4`, including `AG12-DESIGN-R4-F1` and
`AG12-DESIGN-R4-F1-A`, only for the reviewed 1,168-line source at
`C:/Users/DELL/Downloads/Pasted markdown.md`, SHA-256
`29A22A43028A5DC37949F210CAA10200DDF1141FC84E65701055E5584B1DB46D`.
The external source is evidence by exact identity; its complete text is not
copied into the repository.

The accepted future Analytics boundary is `READ_ONLY`, L1,
`write_scope: null` and `automatic=false`. It permits deterministic,
provenance-bound metric, reconciliation, period, cohort, funnel and declared
experiment analysis from approved dataset snapshots, with uncertainty and
independent verification. It provides internal findings only: it may not mutate
records or systems, publish findings, trigger actions, create experiments,
broaden data access, make domain decisions or treat correlation as causation.

Agent 11 retains finance and pricing semantics; Sales retains individual leads
and opportunities; Marketing retains positioning, audience and campaign
decisions; Social Media retains channel-level performance review; Operations
retains process ownership and reporting coordination; Communications or the
owning domain retains external wording and delivery; Reviewer remains
independent; and the human owner and authoritative source systems retain data
access and business policy. Agent 12 owns only the specified measurement layer.

The design reuses the existing Task Contract, authorization fingerprint,
approvals, budgets, evidence and `ExecutionResult`. Provider qualification and
eligibility remain pending and fail closed. No provider manifest, capability
certification or runtime eligibility changed. No proposed Agent 12 directory,
role, skill, workflow or schema path is created. The frozen 14-role roster is
unchanged; Agent 11 remains closed; `MEM-03` remains **BLOCKED / HOLD / NOT
ACCEPTED**, `BUILD-02` remains `REVIEW_PASS / ACCEPTANCE BLOCKED`, and
`CONTRACT-04` installation remains **BLOCKED**. Implementation, testing,
provider qualification, runtime acceptance, deployment and Git work require
separate authorization.

## Agent 11 Finance & Pricing Accepted Design - 2026-10-24

Agent 11 remains **APPROVED V1 / DESIGN REVIEW ACCEPTED / NOT IMPLEMENTED**.
AC-V1-AGENT11-DESIGN-009 returned the owner-accepted `REVIEW_PASS`, resolving
`AG11-DESIGN-R1` through `AG11-DESIGN-R5` only for the reviewed 888-line source
with SHA-256
`46EB8C6375FAC0A13E7A845C7793019BC4625E568B934264E02E2ECCA0BAE142` at
`C:/Users/DELL/Downloads/AC_V1_AGENT11_DESIGN_005_R2_R5_REVISION_20261024.md`.
The external source is evidence by exact identity; its complete text is not
copied into the repository.

The accepted design is a future `READ_ONLY` Finance & Pricing analysis boundary.
It may calculate, compare, explain and recommend from approved, source-bound
inputs, but it may not approve or issue prices, quotes, discounts, refunds,
credits, invoices or contracts; adopt financial policy; communicate an external
commitment; mutate business records; or initiate payments, purchases, transfers,
subscriptions or spend. Sales retains leads, opportunities, proposals and
follow-up; Marketing retains positioning, campaigns and market evidence;
Operations retains process and reporting coordination; Communications or Sales
retains external wording and delivery; and planned Analytics retains general
statistical and cross-domain analysis. Agent 11 owns only future finance and
pricing semantics within an authorized analysis.

The design reuses existing Task Contract, `ExecutionResult`, approval,
authorization-fingerprint, review and human-decision boundaries. Material
financial scope must be immutable and digest-bound before any future authorized
execution; new or changed material policy requires new bound input and approval.
Provider eligibility remains **NOT QUALIFIED**. The proposed provider eligibility
flags remain fail-closed, and this documentation record does not modify a
provider manifest, certify a provider or authorize provider execution.

No proposed `agents/finance-pricing/`, finance-pricing skill or workflow path is
created. The frozen 14-role roster is unchanged. `MEM-03` remains **BLOCKED /
HOLD / NOT ACCEPTED**, `BUILD-02` remains `REVIEW_PASS / ACCEPTANCE BLOCKED`,
and `CONTRACT-04` installation remains **BLOCKED**. Implementation, testing,
runtime acceptance, deployment and Git work require separate authorization.
`automatic=false`.

## Canonical Reconciliation Overlay - 2026-10-24

This overlay reconciles the full current roadmap with the reference-only R2
conflict register at
`C:/Users/DELL/Downloads/AC_CODEX_ROADMAP_RECONCILIATION_INPUT_20261024.md`
(SHA-256
`c31e0ff1bb7ada6fcfe6c303b8254fc92bc4116040687f9995c297a40badc9df`).
It does not replace the accepted design sources embedded below, reopen a closed
checkpoint or create implementation authority. Where dated entries conflict,
this current overlay and the later accepted decisions control current status.

### Current status and dependency boundary

| Scope | Current canonical classification |
| --- | --- |
| CORE-01 through CORE-11; GOV-01/02; ORCH-01 | CLOSED / COMMITTED. CORE-07 remains closed; the reviewed recovery-lock diagnostic is retained, the concurrency proof is INSUFFICIENT, and the broader recovery-coordination refactor is owner-DEFERRED. |
| MEM-01 / MEM-02 / MEM-02B | CLOSED / COMMITTED; MEM-02 is PUSHED. MEM-02B commit `ad055f8` and later fixture-hygiene commit `4773acb` are ancestors of current HEAD. Do not restart older ACTIVE/UNCOMMITTED steps. |
| MEM-03 | Mandatory V1; BLOCKED / HOLD / NOT ACCEPTED. Native Windows compatibility, identity, evidence-custody and protected-execution evidence remain incomplete. Design preparation for Agents 11-14 does not bypass or satisfy this gate. |
| Shared CORE BUILD-01 | CLOSED / COMMITTED at `376763d`; reviewed two-file scope only. |
| Shared CORE BUILD-02 | REVIEW_PASS / ACCEPTANCE BLOCKED. Mandatory affected regression remains 51/52; the same recovery-lock signature occurs on the committed baseline, so BUILD-02 defect attribution is UNKNOWN. The 52/52 requirement remains. |
| GOV-01 Direct API Transport V2 | DESIGN ACCEPTED / REVIEW_PASS / documentation and Git closed; implementation, provider qualification and runtime acceptance NOT STARTED. CLI adapters remain blocked. |
| CONTRACT-04 revision 2 | DESIGN ACCEPTED / PARTIALLY IMPLEMENTED; installation BLOCKED. The 180-candidate inventory is not an approved manifest, exceeds the 128-entry ceiling, and has UNRESOLVED membership and UNVERIFIED dependency closure. Alternative A is approved as design scope only. |
| D1 / D2-D8 | D1 PAUSED / unaccepted. D2-D8 are ACCEPTED / MAPPED ownership families, not implementation or new checkpoints. |
| Phase 9A / DEC-01 / DEC-02 | Phase 9A NOT STARTED and precedes DEC-01 runtime. DEC-01 design is accepted; runtime NOT STARTED. DEC-02/JEV is DEFERRED. |

No currently blocked item becomes implementation-ready through documentation.
The Shared CORE BUILD-02, MEM-03 and CONTRACT-04 admission blockers remain
distinct and fail closed.

### Frozen V1 placement and remaining scope

The physical and roadmap placement remains: current ten agents, then the
planned Agent Expansion section, then Capability Expansion and Phase 9. The
four unimplemented roles stay explicitly inside frozen V1 and are not moved to
Phase 10 or Post-V1:

11. Finance & Pricing - APPROVED V1 / PLANNED / NOT IMPLEMENTED.
12. Analytics - APPROVED V1 / PLANNED / NOT IMPLEMENTED.
13. Content - APPROVED V1 / PLANNED / NOT IMPLEMENTED.
14. Design - APPROVED V1 / PLANNED / NOT IMPLEMENTED.

Owner-approved sequencing permits separately authorized, bounded design and
contract preparation for Agents 11-14 before MEM-03 acceptance. This is
preparatory documentation only: it creates no agent, skill, workflow, runtime
contract or implementation checkpoint. Agent implementation and runtime
acceptance remain behind MEM-03 and every other applicable existing mandatory
gate. MEM-03 remains mandatory V1 on BLOCKED / HOLD / NOT ACCEPTED; preparation
does not waive, satisfy, reorder or bypass it.

The exact V1 capability IDs remain `CAP-SALES`,
`CAP-SEARCH-GROWTH-01`, `CAP-REV-01` and `CAP-SOC-01`, all planned and
unimplemented at their full accepted scopes. Phase 9A Observability, Phase 9B
Control Room and Phase 9C Operating Layer remain distinct planned V1 scopes.
Phase 8E stays PAUSED / BLOCKED; 8F, 8G and 8H remain NOT STARTED. Phase 10
still begins with the Brightshore production Project Pack. Existing
`shared/projects/brightshore/` is operational project state, not pack
acceptance.

Optional Obsidian Stage 1 local notes and Stage 2 governed integration remain
PROPOSED / UNVERIFIED and separate from MEM-03. They are not a V1 blocker, new
agent, second authority database or implementation checkpoint. Other Later /
Post-V1 classifications below remain unchanged.

## GOV-01 Direct API Transport Design Acceptance - 2026-10-23

AC-GOV01-TRANSPORT-DOC-001 records owner-approved design-level acceptance of the
complete AC-GOV01-TRANSPORT-DESIGN-FIX-001 V2 contract after the owner-reported
affected-scope independent `REVIEW_PASS`. Both reviewed findings are closed at
design level: destination/profile validation must precede credential resolution
and network activity, and deterministic verification must bind the complete
execution, attempt, retry and continuation identity before review can PASS.

The [complete accepted design](#gov-01-direct-api-transport-accepted-design---2026-10-23)
is retained under the existing GOV-01 architecture owner. It preserves same-byte
in-process verify-and-send, exact zero-tool validation, fail-closed response
handling, one transport attempt, no automatic fallback, blocked opaque CLI
adapters and a deferred/non-mandatory separate-process oracle.

AC-GOV01-OWNER-DISPOSITION-003 adds an owner-approved design-policy overlay only.
Gemini Developer API is the first qualification candidate, while
`gemini-3.5-flash-lite` remains **UNVERIFIED**. Any later authorized initial
operation is limited to synthetic, non-sensitive data, text-only, non-streaming
and tool-free requests, zero paid expenditure, one transmission attempt, and no
automatic retry, fallback or provider substitution. Qualification eligibility is
conditional on independent evidence that the exact project is Free Tier and has
no active billing linkage. Paid expenditure is capped at $0, and uncertainty
about project identity, billing, eligibility or charging fails closed. Documented
limited provider-side processing and retention are accepted only for synthetic,
non-sensitive qualification data; no zero-retention guarantee is assumed or
claimed. Exact request/response evidence must remain local, repository-external,
access-restricted and bound to canonical execution identities; 30 days is an
initial design retention target, not an implemented control. Provider/profile
qualification, exact destination and API version, model availability,
account/project qualification, no-active-billing verification, enforceable
zero-charge evidence, TLS implementation, credential integration, evidence access
and manual disposal, and privacy enforcement remain unfulfilled technical
requirements and require separate authorization. The complete accepted V2 source
below is unchanged.

This is design acceptance only. Direct API implementation, provider
qualification, credential integration, isolated canary execution and runtime
acceptance are NOT STARTED and require separate authorization and evidence.
Account inspection also requires separate authorization. GOV-01 remains
CLOSED / COMMITTED at `852ec01`; frozen V1, 14 approved roles and all existing
scope, approval, evidence, retry, continuation and review owners are unchanged.
CONTRACT-04 remains partially implemented; Phase 9A remains NOT STARTED and
unaccepted; DEC-01 implementation remains NOT STARTED; **MEM-03 remains BLOCKED;
D1 remains PAUSED.** No new checkpoint, process, service, database, role or
authority store is created. `authority=none`; `automatic=false`.

## DEC-01 Design Acceptance - 2026-10-21

AC-DEC-01-009 records owner-approved design-level acceptance of AC-DEC-01-004
plus AC-DEC-01-006 and AC-DEC-01-007 after the owner-reported independent
AC-DEC-01-008 `REVIEW_PASS`. The
[accepted design contract](#dec-01-accepted-design-contract---2026-10-21)
closes all four original design findings, not implementation or Phase 9A.
DEC-01 implementation remains NOT STARTED; the frozen sequence is unchanged.
Phase 9A remains before DEC-01. P9A-1 through P9A-6 are assessment/proposal
labels, not six additional mandatory checkpoints. **MEM-03 remains BLOCKED;
D1 remains PAUSED.** Existing dated records below retain their historical scope.
Remaining technical dispositions are explicit in the contract entry and TODO.
`authority=none`; `automatic=false`.

## MEM-02B Formal Acceptance - 2026-10-15

AC-MEM-02B-CLOSURE-PREP-116 records explicit owner formal acceptance of the
bounded MEM-02B implementation, FIX-80 credential correction and FIX-101 cleanup.
Status: **FORMALLY ACCEPTED / RECONCILIATION RECORDED / CLOSED / UNCOMMITTED**.
Bounded closure recorded under owner-authorized AC-MEM-02B-CLOSURE-119 after
REVIEW-118 CLOSURE_READY. Closure evidence: `E:\Software\Agent_Company_Handoff\MEM-02B\CLOSURE-119-20261015\CLOSURE-119.md`.
Closure grants no staging, commit, push or next-checkpoint authority.
The separate-session REVIEW-113 product finding and owner routing disposition
ROUTING-115 support acceptance. Same-provider review is OpenAI / Codex;
alternate-provider availability remains UNKNOWN. Historical REVIEW-113 BLOCKED
and REVIEW-114 NEEDS_HUMAN verdicts remain unchanged.

All six retained Package 107 owner gates PASS: targeted 100/100, affected 158/158,
focused 845 observations/835 distinct IDs, Full 1729/1719, schema/static
202 Python/36 schemas/17 certificates, and Diff exit 0 with 20 permitted warnings.
Package manifest SHA-256: `ca90aed32075b2e78b4c14fb87076dc6f1ebf587b5c66652770c3ec4bbe2e1a7`.
Owner ledger SHA-256: `a017435b19ee9f99ba801d1e85e2317612ba8691e753913f3978608dd796e192`.
Evidence: `E:\Software\Agent_Company_Handoff\MEM-02B\ACCEPTANCE-116-20261015\ACCEPTANCE-116.md`.
No tests were rerun for acceptance recording or this documentation reconciliation.

Historical 1725-test Full failure, FIX-101 repetition-8 timeout, credential and
cleanup reproduction failures, all warning/duplicate evidence and diagnostic
limitations remain retained. ROOT_CAUSE_UNKNOWN; DESIGN-99 remains DEFERRED.
Same-provider blind spots, absence of fresh REVIEW-113 runtime probes, worker
shutdown waits and trusted-filesystem/durability limits remain disclosed.
Acceptance does not authorize a learning disposition, automatic promotion,
execution, retry, Git action, deployment or later-phase implementation.
Earlier dated entries below retain historical meaning. The accepted source is
the working tree on master at baseline HEAD
`92460248344906e5388fbe02e06b6e793187bcb5`; it is not committed at that HEAD.
Only these four documentation files differ from the accepted 757-pin snapshot;
the old sealed run evidence remains unchanged and the other 753 pins were
verified unchanged for CLOSURE-119. Gates remain bound to their historical source.

## MEM-02B FIX-69-R2 - 2026-10-12

MEM-02B remains ACTIVE / ACCEPTANCE FIX / CLOSURE OPEN. Bounded review-body,
coverage, planning-hold and credential-redaction repairs use the accepted 33-path
scope. See [current repair and evidence boundary](PROJECT_STATE.md#mem-02b-fix-69-r2---2026-10-12).
Fresh source-bound executor results do not replace independent REVIEW-68, owner
Git-dependent gates or closure. Prior dated entries remain historical; no later
phase or automatic action is authorized.

## MEM-02B BUILD-64 - 2026-10-11

MEM-02B is ACTIVE / IMPLEMENTED / BOUNDED EXECUTOR VALIDATION PASS / MANDATORY GATES PENDING / UNCOMMITTED
under owner-approved Authority-62, Scope-63 and BUILD-64. Exact 33-path scope and
bounded capacities apply. See [current evidence and stop boundary](PROJECT_STATE.md#mem-02b-build-64---2026-10-11).
Independent review, complete GOV-02 gates and owner closure remain pending.
Existing completion/execution/storage/graph contracts, V1 freeze and dependencies
remain unchanged. MEM-03, Obsidian, DEC-01/02 and agents 11-14 remain planned.
No automatic next action, independent review or Git lifecycle follows BUILD-64.

## Post-MEM-02 Commit Reconciliation - 2026-10-11

`AC-POST-MEM02-RECONCILE-60` records owner-verified **MEM-02 CLOSED /
COMMITTED / PUSHED**, HEAD `22c9d37b503d3eea242eb6cc35041efdaac0a4d5`.
**ACTIVE: None. NEXT: MEM-02B / NOT STARTED — Learning Constraint Pipeline.**
This follows the existing frozen sequence; it grants no implementation authority.
MEM-03, DEC-01/02 and Finance & Pricing, Analytics, Content and Design remain
PLANNED / NOT STARTED. No scope, checkpoint or dependency is added or reordered.
See the [current post-commit record](PROJECT_STATE.md#post-mem-02-commit-reconciliation---2026-10-11).
Earlier dated closure/evidence entries, including their pending commit actions,
retain historical meaning. No Git, code, tests, reviews or implementation occur.
One next action: obtain a separately scoped MEM-02B contract-definition work order.
STOP before implementation.

## MEM-02 Formal Bounded Closure - 2026-10-11

`AC-MEM-02-FORMAL-CLOSURE-58`: **formal bounded closure PASS; MEM-02 CLOSED /
READY_TO_COMMIT**. COMMITTED/PUSHED are not asserted. ACTIVE: None. NEXT:
MEM-02 commit, pending the owner's PowerShell Git step. No next implementation
is authorized; MEM-02B validated promotion and MEM-03 production storage/
durability remain OPEN / NOT STARTED.

See the [canonical closure record, gates, owner Git evidence and limitations](PROJECT_STATE.md#mem-02-formal-bounded-closure---2026-10-11)
and preserved [full bounded acceptance matrix](PROJECT_STATE.md#mem-02-full-foreground-integration-acceptance---2026-10-11).
Accepted lifecycle, retrieval/context, bounded validity/supersession and
foreground action verification/trace candidates satisfy the approved scope.
Non-null mutation `diff_ref` remains unsupported and fails closed; truth,
publisher authenticity, unsupported freshness and global completeness remain
UNKNOWN. Same-provider review is disclosed; no cross-provider PASS, fresh
combined regression, production durability or lesson promotion is claimed.
Earlier dated checkpoint statuses and decisions retain their historical meaning.
This updates existing scope/status ownership without adding a checkpoint,
Master Context, DOC-TREE owner or closure-artifact convention.

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
- MEM-02 Knowledge Lifecycle + Retrieval / RAG: CLOSED / COMMITTED / PUSHED;
  formal bounded closure PASS; owner-verified HEAD
  `22c9d37b503d3eea242eb6cc35041efdaac0a4d5`.
- MEM-02B Learning Constraint Pipeline: CLOSED / COMMITTED in current HEAD
  ancestry at `ad055f8`; later fixture hygiene is committed at `4773acb`.
  Formal ACCEPTANCE-116, retained owner gates PASS and separate-session
  review/routing evidence remain preserved.
- MEM-03 Memory Providers: BLOCKED / NOT ACCEPTED; its planned provider scope
  remains frozen but native Windows admission and compatibility evidence are
  incomplete.
- Shared CORE BUILD-01: CLOSED / COMMITTED at `376763d` for its reviewed
  two-file slice.
- Shared CORE BUILD-02: REVIEW_PASS / ACCEPTANCE BLOCKED at 51/52 mandatory
  affected regressions; same recovery-lock signature on baseline, attribution
  UNKNOWN, 52/52 still required.
- CONTRACT-04: DESIGN ACCEPTED / PARTIALLY IMPLEMENTED; installation BLOCKED.
- Direct API Transport V2 and DEC-01: design accepted; runtime implementation
  and qualification NOT STARTED.
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

One ACTIVE and one NEXT checkpoint slot remains a governance constraint.
ACTIVE = None. The older MEM-02B commit action is superseded by the current
committed lineage. No blocked implementation is promoted into NEXT by this
reconciliation; a later action still requires its own owner authorization.
MEM-02 is CLOSED / COMMITTED / PUSHED; MEM-02B is CLOSED / COMMITTED; MEM-03
remains mandatory V1 on BLOCKED / HOLD / NOT ACCEPTED. Owner-selected M1 NARROW
SEQUENCING permits separately authorized offline, synthetic-data,
non-authoritative code development without advancing the ACTIVE/NEXT sequence.
Every slice requires an exact-file work order, bounded scope, deterministic
tests, independent review and preserved evidence. Production data, secrets,
network or provider calls, protected native execution, authority-bearing
persistence and unauthorized external effects are prohibited. Separate
acceptance is required before runtime integration or promotion; an offline pilot
PASS never implies V1 acceptance. The completed two-file Agent 11 exact-division
pilot remains closed at `29802269c2a4cab4d0f8f13d980ec85e31708737`, with the
owner-reported 19/19 deterministic test result and independent `REVIEW_PASS`,
without implementing Agent 11 or changing any mandatory gate.
MEM-01 is CLOSED / COMMITTED at `5e29cdb177838adb1682ab3b36728623d714c5e3`.
GOV-01 remains CLOSED / COMMITTED at `852ec01`; GOV-02 is CLOSED / COMMITTED
at `e6dbe3f`; ORCH-01 is CLOSED / COMMITTED at `d3878081`.
CORE-11 is CLOSED / COMMITTED at `8bda7eb` after Independent Re-review R2 PASS. Lifecycle remains IMPLEMENT -> INDEPENDENT
REVIEW -> BOUNDED FIX if required -> RE-REVIEW -> CLOSURE -> COMMIT -> NEXT.
Core Runtime Foundation = COMPLETE. GOV-01 is CLOSED / COMMITTED at `852ec01`;
no later implementation is authorized by BUILD-64.

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

##### GOV-01 Direct API Transport Accepted Design - 2026-10-23

The following is the complete accepted 612-line V2 source from
`C:/Users/DELL/Downloads/AC_GOV01_DIRECT_API_TRANSPORT_DESIGN_CANDIDATE_V2.md`,
SHA-256 `ffb09725b75c805c6dd35027be82817d4cf2811e0ed0dff7b4206bfc218ced94`.
It is retained as the accepted design baseline. The surrounding status record,
not the source's pre-review candidate label, records the later owner acceptance
and owner-reported independent `REVIEW_PASS`. No implementation authority follows.

The repository copy preserves all 612 source lines but removes the five metadata
lines' Markdown hard-break pairs (ten trailing ASCII spaces) so
`git diff --check` can remain clean. The normalized embedded bytes are 30,893
bytes with SHA-256
`5ec574202278060804f927db2fae494d424dbedb7d5f10cb86a305597836d506`.
No words, ordering or design requirements change. The unchanged Downloads source
and its expected SHA-256 above remain the acceptance identity.

<!-- AC-GOV01-DIRECT-API-TRANSPORT-V2-SOURCE-BEGIN -->
# GOV-01 Direct API Transport - Bounded Design Candidate v2

Design ID: `AC-GOV01-TRANSPORT-DESIGN-FIX-001`
Revises: `AC-GOV01-TRANSPORT-DESIGN-001`
Status: **DESIGN_FIX READY - IMPLEMENTATION NOT AUTHORIZED**
Mode: Design revision only
Source preserved unchanged: `C:\Users\DELL\Downloads\AC_GOV01_DIRECT_API_TRANSPORT_DESIGN_CANDIDATE_SOURCE.md`
Source SHA-256: `cadb43528697513e66ad89181991a23e3a6d1cb514e48d27bb273cfe72cbe004`

## Decision

**DESIGN: CANDIDATE**

Recommendation: **ADAPT** the existing provider architecture with a bounded,
byte-level direct API transport. Keep every unqualified CLI adapter blocked.

The v2 design preserves same-byte in-process verify-and-send, strict zero-tool
validation, fail-closed response handling, one transport attempt, no automatic
fallback, and the existing GOV-01 authority boundary. It adds two mandatory
corrections:

1. the trusted canonical transport owns and validates the complete destination
   before credential resolution or network activity; and
2. the prepared request and transport receipt bind the complete canonical
   execution, attempt, retry, and continuation identity and are independently
   revalidated before review can PASS.

A separate-process oracle is not a mandatory V1 component. It remains a
deferred hardening option if the owner later expands the threat model to distrust
the canonical runtime process or requires proof of bytes received by the remote
provider.

## Two-finding change summary

### Finding 1 - HIGH: destination and credential enforcement

**RESOLVED in this design.**

The trusted canonical transport, not the adapter, task, model, environment, or
caller, resolves the effective destination from an independently qualified
provider profile. Before the credential resolver is called, it must validate the
exact scheme, canonical host, explicit effective port, path, query policy, API
version placement and value, HTTP method, TLS policy, redirect policy, and proxy
policy. A supplied destination may only be accepted if every normalized field is
identical to the qualified profile.

Any missing value, ambiguity, unsupported port, endpoint override, redirect,
proxy use, destination drift, API-version conflict, or TLS-policy mismatch fails
closed before credential access and before network transmission. The failure
must record `credential_resolution_attempted=false` and
`network_attempted=false`. The successful receipt binds the validated
destination, TLS policy, and qualification-profile digest.

### Finding 2 - MEDIUM: complete evidence binding

**RESOLVED in this design.**

The immutable prepared-request envelope and provider artifact/transport receipt
must contain and bind `job_id`, `execution_id`, canonical `ExecutionRequest`
digest, Task Contract digest, rendered package digest, requested and actual
provider, qualification-profile digest, canonical job attempt, transport
attempt, and applicable retry and continuation identities. Existing retry and
continuation owners remain authoritative; the transport only records their
canonical projections and digests.

Before review can PASS, deterministic verification must independently recompute
and compare the identity against the canonical `ExecutionRequest`, Task Contract,
rendered package, `ExecutionResult`, execution decision trace, provider artifact,
and transport receipt. Missing, conflicting, stale, substituted, duplicated, or
replayed identity evidence is a deterministic failure, never an advisory log.

## Preflight and preserved baseline

The complete original candidate was verified at the source path and hash stated
above before this revision was prepared. It contains 229 lines and 16,339 bytes.
The source remains unchanged.

The original candidate recorded this repository baseline:

- Repository: `C:\Users\DELL\Desktop\AgentCompany\Agent_Company`
- Branch: `master`
- HEAD: `f8d726e2cdc96f138df8d7447839bc3b10855957`
- Upstream: `origin/master`, reported `+0/-0`
- Worktree: already dirty with 12 modified tracked files and 4 untracked
  diagnostic/test files; those files remain outside this design revision.

No Git operation was performed for this bounded fix. No repository file,
configuration, test, installation, credential, provider, model, or roadmap state
was changed. No provider, CLI, network, or live qualification probe was invoked.

The canonical GOV-01 contract remains CLOSED / COMMITTED. Provider output cannot
grant authority. Native adapters must expose a trusted empty native-tool surface,
and opaque CLI adapters remain blocked before process invocation. Filesystem
sandboxing remains insufficient evidence of an empty model-accessible tool
surface.

## Existing components suitable for reuse

| Component | Reuse |
| --- | --- |
| `TaskContract` | Retain `provider_call` authorization and the exact `native_tools == frozenset()` fail-closed guard. |
| `ProviderAdapter` | Retain the provider-neutral interface; formally add confinement and qualification metadata. |
| `ProviderRouter` | Retain pre-execution eligibility and availability selection, but forbid automatic fallback for the initial direct API path. |
| `ProviderExecutor` | Retain the pre-call confinement guard, execution-package construction, and provider-artifact creation. |
| `Worker` | Retain authority validation, retry/budget reservation, certified dispatch, identity checks, result recording, and continuation routing. |
| `ExecutionRequest` | Remain the canonical execution and attempt identity presented to the transport. |
| `ExecutionResult` | Keep schema version 1 and reference richer provider evidence through the existing artifact reference. |
| `FileProviderArtifactStore` | Extend the existing record schema rather than introduce a new storage mechanism. |
| `ExecutionStore` and capability governance | Retain intent/result binding, consumption evidence, replay prevention, and durable decision traces. |
| Retry runtime/store | Remain authoritative for retry eligibility, authorization, reservation, admission, and consumed-attempt evidence. |
| Continuation runtime/store | Remain authoritative for plan, logical-job, sequence, step, and prior-execution identities. |
| `DeterministicVerifier` | Extend verification to the exact serialized request, destination, response, and complete identity chain. |
| `ReviewerRuntime` | Retain fail-closed `FAIL`/`NEEDS_HUMAN` behavior and existing review/approval routing. |
| Compute budget and approval owners | Reuse for API spend, external transmission, and human approval. |

Current implementation gaps remain unchanged:

- the provider factory constructs only local CLI adapters;
- `ProviderAdapter` does not formally declare its native-tool surface or
  qualification profile;
- `ProviderExecutionResult` remains CLI/process-oriented;
- provider artifacts store process stdout/stderr rather than final request and
  transport evidence; and
- deterministic review does not currently validate the outbound request,
  destination, or full receipt identity.

These are identified design deltas, not implemented capabilities.

## Minimum architecture delta

### 1. Qualified direct API adapter

Add one `direct_api` adapter kind while leaving current CLI adapters unchanged
and blocked.

The adapter must expose:

- `native_tools = frozenset()` with the exact existing type requirement;
- provider and model identity;
- a qualification-profile identifier and digest;
- supported execution mode, initially `READ_ONLY` only;
- a provider-specific deterministic request encoder;
- a provider-specific effective-tool-inventory extractor; and
- a provider-specific response decoder and response-type allowlist.

The adapter must not own credentials, destination overrides, redirects, proxy
configuration, retries, or network transmission. Vendor request and response
field semantics remain inside the adapter/profile boundary. Worker, Router,
ProviderExecutor, ExecutionResult, and ReviewerRuntime remain provider-neutral.

### 2. Independently qualified provider profile

Each permitted provider/model/API-version combination requires one immutable,
independently reviewed qualification profile. Its canonical bytes and digest are
the authority for transport validation. The profile must contain at least:

- provider and profile identifiers;
- model and API version;
- HTTP method;
- scheme, necessarily `https` for V1;
- canonical ASCII host;
- explicit effective port;
- exact path and query policy;
- exact API-version location and value, including path, header, or qualified
  query component as applicable;
- allowed non-secret headers and forbidden header names;
- approved TLS verification policy;
- redirect policy, necessarily disabled;
- proxy policy, necessarily direct/no-proxy for V1;
- request-field allowlist and explicit tool-disable representation;
- response-type allowlist;
- maximum request and response sizes;
- activation and, if applicable, expiry/supersession identity; and
- qualification evidence references.

The profile cannot be selected or altered by task text, model output, inherited
environment, user configuration, arbitrary adapter input, or a per-request
endpoint option. Unknown, inactive, expired, conflicting, or ambiguously encoded
profiles fail closed.

### 3. Immutable prepared request and identity envelope

Introduce one bounded immutable `PreparedProviderRequest` with two distinct
parts: an internal identity/transport envelope and the final outbound body bytes.

The envelope must contain:

- `job_id`;
- `execution_id`;
- canonical `ExecutionRequest` SHA-256;
- canonical Task Contract SHA-256;
- rendered execution-package SHA-256;
- requested provider;
- actual provider;
- model and API version;
- qualification-profile identifier and SHA-256;
- canonical job attempt from `ExecutionRequest.attempt`;
- transport attempt, fixed at `1`;
- decision-intent digest and dispatch-consumption/claim digest supplied by the
  existing execution-governance owner;
- retry identity, either canonical `null` or a complete projection of existing
  retry evidence; and
- continuation identity, either canonical `null` or the complete existing
  continuation tuple.

When retry identity applies, the projection must include the existing canonical
values needed to distinguish the retry from original work: source job, retry job,
logical job, retry sequence/job attempt, authorization digest, repair-scope
digest, and reservation/admission or consumed-attempt evidence digest as
applicable. The transport must not derive, repair, or authorize any of them.

When continuation identity applies, it must include:

- `continuation_plan_digest`;
- `continuation_logical_job_id`;
- `continuation_sequence`;
- `continuation_step_id`; and
- `continuation_execution_ref` when required by the canonical request.

Continuation values must be wholly absent or canonically complete according to
the existing `ExecutionRequest` contract. Retry identity does not authorize
continuation, and continuation identity does not authorize a retry.

The outbound portion must contain:

- allowlisted non-secret headers;
- final UTF-8 request-body bytes;
- request-body SHA-256 and byte length; and
- the provider-specific derived effective tool inventory.

The body is serialized once. Validation and transmission receive the same
immutable byte sequence. Nothing may reconstruct, reserialize, compress,
transform, or replace it after validation.

### 4. Mandatory pre-credential destination gate

The canonical transport must execute the following order without reordering or
bypass:

1. Load the active qualified profile by its trusted identifier.
2. Verify the profile digest and qualification state.
3. Resolve the effective destination exclusively from the profile. If an adapter
   supplied destination is present, normalize and compare every field exactly.
4. Validate method, `https` scheme, canonical host, effective port, exact path,
   query policy, and API-version placement/value.
5. Validate the approved TLS policy, hostname verification requirement,
   certificate-verification requirement, redirect-disabled state, direct/no-proxy
   state, and disabled environment inheritance.
6. Validate complete execution identity and exact request bytes, including the
   empty effective tool inventory.
7. Freeze the validated destination/request tuple and create its precredential
   digest.
8. Only then call the approved credential resolver using the qualified profile
   identity, never a task-supplied host or endpoint.
9. Inject the credential into the in-memory allowlisted authorization header.
10. Send the already-validated body bytes once to the already-validated
    destination.

The canonical transport must reject:

- any non-HTTPS scheme;
- host aliasing or host drift after canonicalization;
- implicit or explicit port drift;
- an unsupported port;
- path normalization that changes the qualified path;
- unexpected query components;
- conflicting, missing, duplicated, or unsupported API versions;
- user-, task-, model-, environment-, or adapter-controlled endpoint overrides;
- redirects or any 3xx destination substitution;
- explicit or environment-derived HTTP/SOCKS proxies;
- custom transport hooks or middleware that can change destination or body;
- disabled certificate or hostname verification;
- unapproved CA bundles, TLS settings, or connection adapters; and
- any mismatch between the selected provider and the destination profile.

For every precredential mismatch:

- the credential resolver must not be called;
- no authorization header or token value may be materialized or disclosed;
- no DNS lookup, socket connection, TLS handshake, or provider transmission may
  occur;
- the execution returns a non-retryable fail-closed result; and
- bounded local failure evidence records the mismatch class plus
  `credential_resolution_attempted=false`, `network_attempted=false`, and
  `transport_attempt=0`, without secrets.

Credential acquisition failure after a successful destination gate still causes
zero network transmission. A redirect response, if one is received from the
qualified destination, is a terminal rejected response and is never followed.

### 5. Same-byte zero-tool verification and transmission

The trusted in-process transport is a canonical runtime enforcement component,
not an adapter assertion. It must:

1. parse the final request bytes with duplicate-key rejection;
2. apply the exact provider/model/API-version field allowlist;
3. derive the effective model-accessible tool inventory from those bytes;
4. require the inventory to be exactly empty;
5. confirm the body digest and identity envelope immediately before credential
   resolution;
6. pass the same immutable bytes to the network client without reserialization;
7. permit exactly one network transmission attempt; and
8. create a bounded receipt before the provider result can be accepted.

Required request conditions remain:

- `tools` is exactly empty where the qualified API supports the field;
- `tool_choice` is exactly `none` where supported;
- if either field is unsupported, its omission is explicitly defined in the
  independently reviewed profile and is never inferred from silence;
- hosted-tool, function-call, web-search, file-search, computer-use,
  code-interpreter, MCP, and equivalent capability fields are forbidden;
- unknown capability-bearing fields are rejected;
- stateful assistant, thread, session, conversation, or stored-agent identifiers
  are rejected for V1;
- streaming is disabled for V1;
- automatic retries, response hooks, middleware mutation, redirects,
  environment proxies, and automatic provider fallback are disabled; and
- no tool dispatcher is reachable from the adapter or response path.

The canonical job attempt and the transport attempt are different identities.
An authorized job retry may produce a new canonical execution and a new single
transport attempt; the transport itself never retries. An ambiguous network
outcome is non-retryable and requires human disposition.

### 6. Fail-closed response validation

Before accepting success, the adapter must reject:

- tool, function, MCP, hosted-tool, or computer-use calls;
- `required_action` or equivalent continuation states;
- provider requests to submit tool results;
- unknown response item types;
- unsupported binary or multimodal payloads;
- malformed, oversized, or non-UTF-8 responses;
- response identity inconsistent with the prepared request; and
- any response reached through redirect, retry, fallback, or destination drift.

V1 permits only bounded text output plus explicitly qualified usage and finish
metadata. A rejected response cannot be dispatched as a tool request, treated as
continuation authority, retried automatically, or sent to another provider.

### 7. Complete provider artifact and transport receipt

Extend the existing provider artifact schema rather than create another storage
mechanism. The write-once artifact must retain:

#### Canonical identity

- `job_id` and `execution_id`;
- canonical `ExecutionRequest` digest;
- Task Contract digest;
- rendered package digest;
- requested and actual provider;
- qualification-profile identifier and digest;
- canonical job attempt and transport attempt;
- decision-intent and dispatch-consumption/claim digests;
- canonical retry identity or explicit `null`; and
- canonical continuation identity or explicit `null`.

#### Validated destination and credential boundary

- method, scheme, canonical host, effective port, path, query policy, and API
  version location/value;
- TLS-policy identifier/digest and verification outcome;
- `redirects_allowed=false`;
- `proxy_mode=none`;
- `environment_transport_config_used=false`;
- precredential validation digest;
- `credential_resolution_attempted` as a boolean;
- `network_attempted` as a boolean; and
- no credential value, authorization-header value, or reversible credential
  fingerprint.

#### Request and response evidence

- exact request bytes encoded losslessly;
- request-body SHA-256 and byte length;
- allowlisted non-secret header inventory;
- derived tool inventory, necessarily `[]`;
- tool-choice validation result;
- attempt count, necessarily `1` for a transmitted request;
- `fallback_used=false`;
- exact bounded response bytes and digest;
- response status and observed response-type inventory;
- status, timestamps, and usage; and
- a receipt digest over the canonical identity, destination, request, and
  response evidence.

The receipt is evidence, never authority. It cannot authorize a retry,
continuation, fallback, review PASS, external action, or completion.

`ExecutionResult` remains structurally unchanged. Its existing provider-artifact
reference binds the result to this evidence path. Existing execution decision
traces and completion receipts remain responsible for their established result,
artifact, review, and approval digests.

### 8. Deterministic identity and replay verification

Before semantic provider review can PASS, `DeterministicVerifier` must load the
canonical sources independently and recompute all comparisons. It must not trust
the adapter's boolean claims, receipt summaries, or executor narrative.

It must verify:

1. the `ExecutionRequest` digest from canonical persisted request bytes;
2. `job_id`, `execution_id`, job attempt, execution mode, provider selection,
   and artifact reference against `ExecutionRequest` and `ExecutionResult`;
3. the Task Contract digest against the canonical Task Contract boundary and
   retained authority evidence;
4. the rendered package digest against the canonical package rebuilt from the
   request and retained context, or an existing canonical persisted package;
5. requested/actual provider and `fallback_used=false` against Router selection
   and `ExecutionResult`;
6. qualification-profile digest and active-at-send status against the retained
   qualified profile snapshot;
7. destination, API version, TLS, redirect, and proxy fields against that
   profile;
8. request bytes, body digest, empty effective tool inventory, and tool-choice
   representation by independently parsing the retained bytes;
9. canonical job attempt separately from fixed transport attempt;
10. applicable retry identity against existing retry authorization,
    reservation/admission, consumed-attempt, and source-failure evidence;
11. applicable continuation identity against existing continuation plan,
    logical-job, sequence, step, and latest-execution evidence;
12. decision-intent, dispatch claim/consumption, result trace, and artifact
    ownership through the existing execution store;
13. response bytes, digest, status, provider identity, and response types; and
14. uniqueness: the receipt, request digest, execution identity, and consumed
    dispatch evidence have not been substituted or reused for another execution.

Missing, malformed, conflicting, stale-at-send, superseded-before-send,
duplicated, or replayed evidence fails deterministic verification. A historical
profile that was valid and pinned at send time does not become invalid merely
because a later profile exists; the verifier checks the execution-time profile
snapshot and lifecycle evidence.

A deterministic identity failure yields `FAIL` or `NEEDS_HUMAN` under existing
ReviewerRuntime policy and can never become PASS through provider output. It
does not reopen the consumed attempt, synthesize retry authority, advance a
continuation, or authorize automatic resend.

## Normative enforcement points

The two corrections are enforcement requirements, not logging requirements.

| Enforcement point | Required gate | Fail-closed outcome |
| --- | --- | --- |
| Before credential resolver | Exact profile, destination, API version, TLS, proxy, request bytes, tool inventory, and identity must validate. | Resolver not called; zero credential disclosure; zero network activity; non-retryable blocked/failed result. |
| Immediately before send | Frozen destination, immutable body digest, provider/profile identity, and transport attempt must still match. | Credential discarded in memory; zero transmission; no alternate provider or endpoint. |
| Network client | Direct qualified HTTPS connection, approved TLS verification, no proxy, no redirect, no retry, same bytes. | Terminal failure; no resend or fallback. |
| Response admission | Status, size, encoding, identity, and response-type allowlist must pass. | Response rejected; no tool dispatch, continuation, or retry authority. |
| Deterministic review | Canonical request, Task Contract, package, result, profile, receipt, retry/continuation owners, and decision trace must agree. | Deterministic FAIL/NEEDS_HUMAN; review cannot PASS. |

## Independent verification decision

| Option | Decision | Reason |
| --- | --- | --- |
| Adapter declares `native_tools = frozenset()` | **REJECT** | An assertion is not evidence of the effective request. |
| Validate an object before later serialization | **REJECT** | Serialization or middleware can change the transmitted request after validation. |
| Validate final bytes and complete identity, then send those same bytes through the canonical transport | **CANDIDATE** | Independent verification can reparse the retained bytes and recompute destination, tool, and identity bindings without trusting adapter prose. |
| Separate process that repeats adapter checks without exclusive egress | **REJECT** | Process separation alone does not strengthen the request boundary. |
| Separate process with exclusive egress, authenticated IPC, independent pinning, and its own receipt | **CANDIDATE, DEFERRED** | Stronger against a compromised runtime but not required by the current documented trust boundary. |

The bounded in-process design proves the exact application bytes handed to the
canonical transport and the qualified destination to which that transport was
configured to send them. It does not cryptographically prove which bytes the
remote provider ultimately received.

Proof of provider-received bytes would require a provider-signed request-hash
receipt or an independently controlled TLS terminator/egress oracle that is the
only network path. A future isolated acceptance canary should use an independently
controlled recording endpoint or transport stub to compare received bytes and
destination evidence with the retained request. Neither an oracle nor a canary
is authorized by this design revision.

## Security and privacy trade-offs

### Benefits

- Removes the opaque CLI native-tool surface and inherited CLI/MCP/user-config
  risk.
- Makes destination, API version, request bytes, and effective tool inventory
  independently inspectable.
- Ensures a destination mismatch cannot disclose credentials or reach a
  provider.
- Eliminates model-generated tool dispatch.
- Preserves existing authority, identity, retry, continuation, evidence, review,
  and approval ownership.

### Remaining risks

- The canonical runtime and in-process transport remain inside the trusted
  computing base.
- The receipt proves bytes handed to the transport, not bytes received by the
  remote provider.
- Provider API or response-schema drift can invalidate a qualified profile.
- DNS, Windows trust-store, CA, TLS-library, and dependency changes remain part
  of the qualified transport environment.
- API credentials and their approved local source remain sensitive.
- Exact request evidence may contain confidential task context.
- External transmission creates privacy, residency, contractual, and usage-cost
  exposure.
- Parser, canonicalization, or profile-definition defects could produce false
  acceptance until independently reviewed and tested.
- No implementation, automated test, isolated canary, or provider qualification
  evidence exists from this design revision.

A digest alone is insufficient for later independent semantic inspection.
Therefore exact request retention remains mandatory unless an approved encrypted
retention mechanism provides equivalent access. The existing local provider
artifact store is mechanically sufficient; retention period, access control,
data classification, and plaintext acceptability remain owner decisions.

Credentials must be injected only after the mandatory destination gate through
an owner-approved credential source keyed by qualified profile identity. They
must remain absent from `ExecutionRequest`, rendered context, request artifact,
transport receipt, logs, errors, and review evidence. No new secret store is
mandated by this design.

## Roadmap and V1 assessment

- **GOV-01:** hard dependency and unchanged. CLI adapters remain fail-closed.
- **Shared CORE:** reuse authority, execution identity, budget, evidence, replay,
  retry, continuation, and review owners; no new authority ledger.
- **BUILD-02:** preserve `REVIEW_PASS / ACCEPTANCE BLOCKED`. This transport does
  not rely on unaccepted `readonly_inspection` lifecycle work.
- **CONTRACT-04:** remains partially implemented. Pinned installation and
  Windows-containment obligations are not claimed by this design.
- **Phase 9A:** remains NOT STARTED and unaccepted. It may later consume receipts
  but is not required to create or validate them.
- **ExecutionResult, Worker, and ReviewerRuntime:** retained; provider evidence
  production and deterministic verification are adapted within existing owners.
- **Frozen V1 and 14 roles:** unchanged. No role, service, database, security
  service, process, or mandatory checkpoint is added.
- **MEM-03 and DEC-01 implementation:** unchanged and not dependencies.

Mandatory for any accepted direct API V1 transport:

- precredential destination/profile enforcement;
- approved HTTPS/TLS verification with redirects and proxies disabled;
- final-byte request verification;
- independently qualified provider/model/API-version profile;
- empty derived native-tool inventory;
- fail-closed response parsing;
- one transport attempt and no automatic fallback;
- complete execution/retry/continuation evidence binding;
- deterministic replay/staleness rejection; and
- independent implementation review and owner acceptance.

Optional or deferred:

- separate-process egress oracle;
- encrypted evidence archive;
- streaming;
- multi-provider fallback;
- provider-signed receipts; and
- Phase 9A telemetry integration.

The direct transport itself is not authorized or automatically mandatory. If
provider-backed execution or provider-backed review is required while CLI
confinement remains blocked, this is the minimum viable architectural route.
Otherwise, defer it and keep provider execution blocked.

## Future acceptance evidence

Any later implementation acceptance must include, at minimum:

- independent source review of the destination gate and credential-call order;
- deterministic proof that every destination/profile mismatch makes zero calls
  to the credential resolver and network client;
- adversarial destination cases covering scheme, host, port, path, API version,
  redirect, proxy, TLS, environment override, and adapter override;
- same-byte tests proving the verified bytes are the bytes passed to the network
  client;
- zero-tool request tests for supported, unsupported, duplicate, unknown, and
  aliased capability fields;
- response tests covering every forbidden tool/action response type;
- identity tests for missing, conflicting, stale, substituted, duplicate, and
  replayed receipts;
- retry tests proving one HTTP attempt and preservation of canonical retry
  ownership;
- continuation tests proving provider output and receipts cannot advance or
  authorize continuation;
- a separately authorized isolated recording canary, if the owner requires
  observed wire-receipt equivalence; and
- independent affected-scope review plus explicit owner acceptance.

These are future acceptance requirements, not authorization to implement or run
them now.

## Unresolved owner decisions

1. Whether the threat model trusts independently reviewed canonical runtime code
   or requires isolation from a compromised runtime process.
2. The first provider endpoint, canonical destination, model, API version, and
   approved Windows HTTPS/TLS trust policy to qualify.
3. Exact-request retention classification, duration, and permitted readers.
4. Approved credential source and external-transmission policy.
5. Per-request and aggregate API cost limits.
6. Whether V1 is text-only and non-streaming as recommended.
7. Whether pre-send provider substitution is ever allowed; the minimum design
   requires none and forbids automatic fallback.

## One next permitted action

Submit this complete v2 artifact to a separate, affected-scope independent design
review limited to the two corrected findings: precredential destination/profile
enforcement and complete deterministic evidence binding. No implementation,
test, credential, provider call, live probe, roadmap change, or acceptance action
is implied.
<!-- AC-GOV01-DIRECT-API-TRANSPORT-V2-SOURCE-END -->

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
- MEM-02 — Knowledge Lifecycle + Retrieval / RAG: CLOSED / COMMITTED / PUSHED;
  formal bounded closure PASS under Prompt 58. Accepted scope: capture, normalize,
  deduplicate, classify, connect, store, retrieve, rerank, build context packs,
  selectively retain relevant context, act, verify, and learn from run traces.
  Anchored evidence-backed memory may link to files,
  symbols, tasks, workflows, decisions, runs, tests, evidence, agents, or
  capabilities and record provenance, verification, confidence, validity, and
  supersession. This is bounded source reuse and explicit supplied-view linkage,
  supported foreground action verification and untrusted trace candidates;
  truth/authenticity/unsupported freshness remain UNKNOWN, non-null mutation
  `diff_ref` remains unsupported and fails closed. Commit/push and HEAD
  `22c9d37b503d3eea242eb6cc35041efdaac0a4d5` are owner-verified.
- MEM-02B — Learning Constraint Pipeline: CLOSED / COMMITTED in current HEAD
  ancestry at `ad055f8`, with later fixture hygiene at `4773acb`; retained
  validation, independent review, owner acceptance, closure and Git identity
  remain distinct.
  observation -> candidate lesson ->
  evidence -> deduplication -> scope -> validation/review -> promotion -> active
  planning constraint. A PASS does not automatically become a permanent rule.
- MEM-03 — Memory Providers: BLOCKED / NOT ACCEPTED. The planned local-provider
  scope remains behind `MemoryInterface`; native Windows compatibility,
  identity, evidence custody and protected-execution acceptance remain
  incomplete. Hindsight is only a future prototype provider; SwarmVault and
  Vault Curate are reference patterns, not core dependencies.

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

#### CONTRACT-04 Accepted Design - 2026-10-19

**DESIGN ACCEPTED (conversation-reported); BUILD-01 CLOSED / COMMITTED; CONTRACT-04
PARTIALLY IMPLEMENTED.** The reviewed two-file Shared CORE slice is committed at
`376763d37a7a7cebb106cb793317bd62207fe402`. Phase 9A Selected Trace remains NOT
STARTED and is not accepted.
This existing architecture/scope owner stores the complete original contract
below, together with the later owner dispositions. Status and review provenance
belong in [PROJECT_STATE](PROJECT_STATE.md#contract-04-design-acceptance-and-source-provenance---2026-10-19);
[TODO](TODO.md#contract-04-remaining-prerequisites---2026-10-19) retains remaining work.
No new document, directory, Master Context, runtime approval or authority owner
is created.

The supplied `AC-P9A-CONTRACT04_DOCUMENTATION_HANDOFF_20261019.md` has SHA-256
`72610cde7fb53eaecd267905df3785941b9ec59331ed73fe6c1bf69ae39a5e65`.
Its section A contains the full original 250-line contract, originally named
`01_CONSOLIDATED_CONTRACT.md` in the conversation source packet. Its raw SHA-256 is
`264aa8cc7e86a79ac96b7c2fdbd5c6bc8647b31a134ebc18f0d453158a625c0f`;
the separately supplied `AC-P9A-CONTRACT04_CONSOLIDATED_CONTRACT.md` matches that
identity, and its complete bytes are preserved between the source markers below.
Local source links and line references inside that historical text are retained
verbatim; they are not freshly verified current navigation or instructions to act.

##### Later owner dispositions and remaining admission boundary

Handoff section B relays owner acceptance in conversation; section C relays a
separate OpenAI/Codex design `REVIEW_PASS`. These are recorded with their source
limitations, not promoted into authenticated original approval/review artifacts.
The reported review concerns the original contract; the later numeric decisions
are owner design targets, not independently validated compatibility guarantees.

| Parameter | Later owner-accepted design target |
| --- | --- |
| `W_MAX` | 16,777,216 operation-wide work units |
| `D_MAX` | 128 active validation frames |
| `P_MAX` | 131,072 raw bytes |
| `S_MAX` | 131,072 raw bytes |

These four dispositions supersede the original contract's numeric OPEN entries.
Preserve 131,072 raw bytes per schema, 33,554,432 aggregate read bytes including
final rereads, complete profiles of 1-128 entries, and the 512 UTF-8-byte path
ceiling. Existing stricter owner limits remain effective. No new profile fields,
runtime defaults or assurance that maximum-sized combinations fit are introduced.

Windows 11 x64 on local fixed NTFS is a conditionally accepted first qualification
target only. Exact OS build, volume, principal, safe root, component-handle
access/sharing/reparse semantics, ACL enforcement and containment evidence remain
unverified. No Windows mechanism or installed filesystem security is accepted.

The later fresh candidate inventory was generated from immutable Git commit
`98f197821966e9d4ff777ff88b69d88b96e461dd` without executing repository code.
The repository-external artifact
`C:/Users/DELL/AppData/Local/Temp/AgentCompany/CONTRACT-04/AC-CONTRACT04-FRESH-INVENTORY-FIX-001-20261024T063030Z/candidate-inventory.v2.json`
is 182,009 bytes with SHA-256
`2a8c958c7d3cbb99ddeed79e3e13768868e9c2ad3f517bd59507b7dcd9859e87`.
It contains 178 committed candidates plus two absent historically proposed
observability modules: 180 total, all membership dispositions UNRESOLVED.
Dependency closure and dynamic file-access discovery remain UNVERIFIED, and
180 does not satisfy the approved 1-128 profile-entry limit. The artifact is
candidate discovery evidence only, not an installation manifest, trusted
profile, detached trust anchor or installed-file pin set. It supersedes the
older unsupplied 114-candidate count for current planning without reconstructing
that historical inventory.

The current owner instruction affirms **Alternative A - selected-action evidence
inspection** as the CONTRACT-04 design-scope boundary, using
`runtime.memory.action_trace.build_action_candidates(request, owners)` as the
design reference. `observability/selected_trace.py` remains PLANNED / NOT
IMPLEMENTED. Exact profile location, Windows principal/SID, permissions,
bootstrap delivery, dynamic dependencies, final membership, installed-file pins
and independent trust qualification remain unresolved. This approval grants no
installation, pruning, execution or Phase 9A acceptance.

Trusted composition must supply complete installation membership, exact installed
raw-byte pins and an external trusted profile identity; no artifact-selected
subset or self-certifying profile is allowed. Historical 63-existing/65-candidate
figures and the later user-reported 114 candidates (112 existing plus two proposed
trace modules) are discovery context only. This handoff supplies neither the
114-file list nor its hashes; neither count is an approved manifest.

Shared CORE retains schema policy/provenance and CORE-07 retains accounting/final
checks, without an early Progress import. Concrete trusted bootstrap entry and
context propagation remain unestablished. Restart/reconstruction requires explicit
owner authorization outside inspection; the concrete reconstruction/restart/recovery
owner and procedure remain unestablished. Inspection never repairs caches,
rewrites historical evidence, re-attests approvals or restores authority.

The six-file CORE candidate scope and separate three-file Phase 9A slice in the
original contract remain exact boundaries, not continuing permission to edit.
BUILD-01 completed only `runtime/core/validation.py` and
`runtime/tests/test_schema_io.py`. Conversation-supplied reports state that the
Codex builder obtained 12/12 focused and 112/112 affected-regression PASS results;
the independent Codex reviewer obtained 12/12 focused PASS, accepted the 112/112
final-source evidence, and returned `REVIEW_PASS` with no remaining High finding.
No retained repository test logs or standalone review artifact were verified.
The slice was committed at
`376763d37a7a7cebb106cb793317bd62207fe402`. Pinned operational inspection,
trusted installation composition and Windows containment remain unimplemented
and unaccepted. A separately authorized remaining CORE work order, its required
evidence, independent review and owner acceptance must precede reliance by the
three-file Phase 9A slice. Recorded ACTIVE/NEXT slots and the frozen roadmap are
not replaced.

The reported design REVIEW_PASS supersedes only the original text's pending
design-review status and request to commission that design review; do not repeat
it. All other unresolved implementation and operational prerequisites remain
open as recorded in TODO. BUILD-01 review and closure do not constitute review or
acceptance of the remaining contract. Phase 9A Selected Trace remains NOT STARTED and is not accepted;
MEM-03 remains BLOCKED; D1 and Claude external review remain PAUSED.
`authority=none`; `automatic=false`.

##### Original consolidated contract - complete preserved source

The following is the original source, including its historical OPEN/pending-review
wording. Interpret it with the later dispositions and limitations immediately
above; its historical next-action statements do not authorize work.

<!-- CONTRACT-04 ORIGINAL SOURCE BEGIN -->
**CONSOLIDATED_CONTRACT_READY — design only; `automatic=false`.**

The owner’s conditional design baseline is incorporated below. This contract is ready for independent review. It grants no implementation authority and makes no runtime-acceptance claim.

Verified checkout: `master`, HEAD `7118c8ff080e8038a6aff99eae9267efdd359ca5`; index empty; nine tracked modifications and four untracked diagnostic files unchanged. All three source reports were read; their hashes remained unchanged: [FIX 1 revision]\(C:/Users/DELL/Downloads/AC-P9A-CONTRACT04_SOURCE_PACK/AC-P9A-CONTRACT04_FIX1_REVISION.md), [historical assessment]\(C:/Users/DELL/Downloads/AC-P9A-CONTRACT04_SOURCE_PACK/AC-P9A-CONTRACT04_HISTORICAL_CORE_ASSESSMENT.txt), [recovered FIX 2/3 evidence]\(C:/Users/DELL/Downloads/AC-P9A-CONTRACT04_SOURCE_PACK/AC-P9A-CONTRACT04_RECOVERED_FIX23_EVIDENCE.md).

**1. Contract purpose, authority and ownership**

This contract combines bounded schema acquisition and inspection accounting (**FIX 1**), exact identity and installation pins (**FIX 2**), and disclosure restrictions (**FIX 3**).

`JobValidator` remains the validation implementation. Shared CORE owns schema acquisition and parsed-byte provenance. CORE-07 retains inspection accounting, final readback and journal restrictions. CORE-08 supplies canonical path rules. GOV and ORCH retain their existing authority, provenance and structural-proof responsibilities.

No new validator, database, authority ledger, agent or canonical owner is introduced. Inspection grants no execution, approval, retry, recovery, mutation or communication authority.

The stronger pinned-inspection policy is explicitly selected through trusted composition. Existing consumer APIs remain intact. Shared validator construction must not eagerly import Progress or create a circular initialization dependency.

**2. Fixed ceilings and open numeric parameters**

| Parameter                                                    | Contract value              |
| ------------------------------------------------------------ | --------------------------- |
| Initial or external schema document                          | **131,072 bytes**           |
| Aggregate inspection payload reads, including final rereads  | **33,554,432 bytes**        |
| Validation-profile entries                                   | **1–128**                   |
| Installation-relative `FilePin.path`                         | **512 UTF-8 bytes maximum** |
| Existing stricter owner limits                               | Preserved                   |
| Operation-wide traversal-work limit, `W_MAX`                 | **OPEN**                    |
| Validation-depth limit, `D_MAX`                              | **OPEN**                    |
| Profile acquisition byte limit, `P_MAX`                      | **OPEN**                    |
| Installation source/configuration acquisition limit, `S_MAX` | **OPEN**                    |

The previously proposed 128 KiB profile/source limits remain proposals. They are not silently adopted as defaults.

Open limits require finite, positive, owner-disposed values before pinned operational admission. They belong to the trusted operation policy; they do not add fields to the closed profile defined below. Maximum-sized combinations need not fit simultaneously.

**3. Exact semantic identity**

`D(value)` is the existing `runtime.core.task_contract.digest(value)`: SHA-256 over its existing canonical JSON encoding—sorted keys, compact separators, ASCII escaping, `allow_nan=False`, UTF-8 encoding and existing helper limits. No replacement serializer or normalization is introduced. [Canonical implementation (line 42)]\(C:/Users/DELL/Desktop/AgentCompany/Agent_Company/runtime/core/task_contract.py:42)

`owner_binding = D(B)`, where `B` contains exactly:

```
{
  schema_version: 1,
  project_id: ID,
  installation_root: Root,
  project_root: Root,
  owners: {
    jobs: Root,
    tasks: Root,
    executions: Root,
    progress: Root,
    approvals: Root,
    evaluations: Root,
    reviews: Root|null,
    provider_outputs: Root|null,
    mutation_outputs: Root|null
  }
}
```

`ID` is the trusted configured project identifier, validated through the existing canonical owner rules. Each owner root comes from that exact `ActionTraceOwners` attribute’s configured `.root`. Only the three optional owners may be null; their fields remain present.

For every `Root`:

- Reject symlinks, junctions and non-directory roots, including unsafe components concealed by resolution.
- Resolve using `Path(root).resolve(strict=True)`.
- On Windows, apply `ntpath.normcase(str(resolved))`, then replace backslashes with `/`.
- On POSIX, use `resolved.as_posix()` without case folding.
- Apply no additional Unicode normalization or trailing-separator transformation. Reject unsupported path flavours.

Trusted composition independently supplies the Agent Company installation root. Project or artifact data cannot substitute for it. Owner, project and installation bindings must agree at entry and exit.

Existing semantic evidence pins remain `D(complete owner-returned JSON)`. The successful view ID remains `D(complete successful output with only id omitted)`. Raw-byte digests do not replace these semantic identities.

Caller-supplied containers are copied and recursively frozen before use.

**4. Closed validation profile and complete pin coverage**

The profile retains the recovered FIX 2 identity:

```
{
  contract: "AC-P9A-CONTRACT-20261018-04",
  revision: 2,
  files: List(FilePin,128)
}
```

Each `FilePin` contains exactly:

```
{path: Path, sha256: Hex}
```

`path` must:

- Be installation-relative, use `/` separators and fit 512 UTF-8 bytes.
- Pass `RepositoryReader(installation_root)` validation and equal `canonical_ref(path)`.
- Reject traversal, aliases, absolute paths, links and nonregular files.
- Be unique both as a canonical path and as `RepositoryReader.identity(path)`.

Entries are ordered by Unicode scalar-value order of the complete canonical path.

`sha256` is lowercase SHA-256 of the complete raw file bytes, including any BOM and original line endings. Decoded/re-encoded text and parsed JSON are not substitutes.

Trusted composition supplies the complete dependency set. It must cover:

- The installed trace implementation and all validation-code dependencies.
- Every initial schema and transitive external schema document.
- GOV-02’s installed source set and certification policy.
- The shared validator, inspection reader and containment implementation.
- Every additional installation payload read by the supported operation.

Requests and retained artifacts cannot reduce this set. Missing pins, undeclared installation reads, duplicates, aliases, incorrect ordering or more than 128 entries cause failure. No truncation or silent subset is permitted.

The historical inventory of **63 existing files / 65 candidates** is discovery evidence, not a complete approved manifest.

A file-backed profile requires an externally supplied trusted raw-byte identity. Its bounded acquisition is charged before parsing; it cannot authenticate itself through a self-referential pin.

**5. Operation lifecycle and byte accounting**

Create one operation context before the first attributable payload acquisition, constructor read or cold-import application read. Trusted bootstrap establishes the root bindings, policy and profile trust source. Unsupported containment or incomplete required policy denies entry before evidence inspection.

Nested inspections join the same operation. They cannot replace its profile, reset counters or enlarge limits. Concurrent work belonging to the operation must share its reservations and observations; it cannot fall through to ordinary unpinned reads.

One ledger covers all attributable application payload reads:

- Evidence and journal bytes.
- Profile acquisition and installation-pin verification.
- Initial and external schemas.
- GOV-02 implementation/source rehashes and certification reads.
- ORCH schema fingerprints.
- Nested construction and all required rereads.

Reserve capacity before each physical read. Outstanding reservations count against the remaining aggregate allowance. Reconcile reservations with actual returned bytes; uncertain partial I/O retains its reservation and fails the operation.

No read request may exceed its applicable acquisition limit or remaining aggregate capacity. The current `ceiling + 1` overshoot pattern cannot satisfy this contract.

Verified file extent, bounded acquisition and stable-handle checks must establish completeness. If completeness cannot be established within the limits, fail closed.

Reusing an immutable verified buffer incurs no fictional second physical-read charge. It cannot replace a fresh reread required by a canonical owner. Every actual reread is charged. Metadata checks and failed opens are recorded separately from payload-byte totals.

Final complete-byte readback uses the same 32 MiB budget. A journal smaller than 32 MiB is not guaranteed to fit a complete inspection.

**6. Schema acquisition and cached-validator provenance**

Every initial and external schema document must be acquired as complete bounded raw bytes. During pinned inspection, verify its canonical installation identity and trusted raw pin **before parsing**. Then decode UTF-8 and apply existing JSON interpretation.

Preserve fragment decoding, canonical schema-directory restrictions, required-field behavior and legitimate recursive schemas. Introduce no network resolution, captured-code loading or substitute validator.

New validator construction records its initial document identity and raw-byte digest. Retained external-document caches require equivalent provenance.

At pinned use, require agreement among:

1. The trusted installation pin.
2. A fresh stable byte observation.
3. The validator’s recorded provenance.

Use operation-local parsed data derived from verified bytes. Detect altered cached schema/path state. Parsed-object equality alone cannot establish raw-byte provenance.

Stale or provenance-less validators fail closed. Explicit reconstruction or process restart occurs outside inspection; global caches are never silently refreshed. Previously unacquired external documents may be acquired locally under the active policy.

**7. Traversal accounting and termination**

Byte acquisition and traversal work are separate limits.

The operation maintains one shared work counter and active-validation stack. The accounting events are:

- Entry into a schema/instance evaluation.
- A branch attempt.
- A reference resolution.
- A node visit during schema-reference discovery or instance traversal.

Each event consumes one work unit; overlapping event categories are charged separately. Failed branches retain their charges. Nested validators and reference traversal cannot reset the counter.

Before processing the next event or descending another validation frame, enforce `W_MAX` and `D_MAX`. Neither a host recursion limit nor a caught `RecursionError` substitutes for this policy.

Track active evaluations by verified schema-document identity, schema location, instance location and evaluation phase. Re-entering the same active combination without progress is a termination failure. It must not become a schema nonmatch or permit partial success.

Recursion that advances into a distinct child instance remains eligible within the declared limits. Reference discovery deduplicates documents and does not reject a schema merely because its document-reference graph contains a cycle.

Work exhaustion, depth exhaustion and non-progressing recursion are sticky integrity failures. The numeric values remain **OPEN**.

**8. Stable reads and containment**

Apply canonical path validation before resolution can conceal links. Require regular files, stable opened-object identity, agreement between named and opened objects, verified extent, raw-byte digests and before/after observations.

Pinned acquisition must maintain containment under the trusted root through concurrent directory replacement. `resolve()` and `stat()` alone are insufficient. Recheck observed content, relevant absence and bindings before releasing success.

The target-specific handle acquisition, access, sharing and reparse-point rules remain admission prerequisites. No Windows mechanism is selected or claimed validated by this consolidation. Unsupported platforms/filesystems fail closed without a weaker fallback.

These checks do not establish a simultaneous transaction across stores, detection of every change-and-restoration, protection against coherent replacement of the entire trusted installation, or power-loss durability.

**9. Failure, disclosure and recovery**

Acquisition, containment, pin, provenance, decoding, traversal and stability failures remain distinct internally from ordinary schema mismatches. Branch logic—including `if`, `oneOf`, `anyOf`, `not` and `contains`—cannot swallow them.

Any integrity failure permanently marks the operation failed. Catching or translating its exception cannot permit successful outer completion. No success is released before final checks finish. Context exit clears transient state.

The FIX 3 disclosure rule is retained:

> The successful response may expose validated installation-relative paths only in `profile.files[].path`. These paths are permitted provenance metadata. Physical installation, project and owner roots remain concealed; only their `owner_binding` digest is returned. No other source paths, source bodies, summaries, stdout/stderr, commands, raw provider reasoning or environment dumps are exposed. Failure responses contain no paths or exception text.

Profile paths remain inert data. They never direct imports, execution, fetching or artifact-selected filesystem access.

Inspection performs no migration, reconciliation, journal recovery, cache repair, persistent lock creation or write. Changed installations, stale loaded implementations, interrupted canonical state and unavailable evidence hold the operation.

Existing owners retain separately authorized reconstruction, restart and recovery. Historical receipts, approvals and evidence are not rewritten or automatically re-attested.

**10. Compatibility and exact scope**

Preserve execution-result aliases, typed-load compatibility, GOV provenance/authority checks, completion semantics, CORE-07 journal restrictions and ORCH structural-proof freshness. Accounting graph schema reads does not enable graph-bound inspection.

CORE-03’s proposed decision-subject interface remains separate. No evaluation adapter or fabricated `ExecutionResult` is introduced.

The CORE candidate scope remains exactly:

| File                                               | Responsibility                                                                                 |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `runtime/core/validation.py`                       | Bounded schema acquisition, policy access, provenance, traversal and integrity propagation.    |
| `runtime/progress/store.py`                        | Shared reservations, stable reads, final readback and failed-operation state.                  |
| `runtime/core/capability_governance.py`            | Account import-time and verification-time source/certification reads without weakening checks. |
| `runtime/graph/models.py`                          | Account transitive fingerprint reads while preserving proof freshness and graph restrictions.  |
| `runtime/tests/test_schema_io.py`                  | Proposed direct contract coverage.                                                             |
| `runtime/tests/test_memory_readonly_inspection.py` | Composed-owner accounting, compatibility and no-write coverage.                                |

Other consumers remain unchanged. Any demonstrated need for another edit requires an explicit allowlist amendment.

The original Phase 9A slice remains separately scoped:

```
observability/__init__.py
observability/selected_trace.py
runtime/tests/test_p9a_selected_trace.py
```

**11. Exact unresolved admission prerequisites**

| Stage                               | Still required                                                                                                                                                                                                                                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Before implementation authorization | Independent design review; explicit `W_MAX`, `D_MAX`, `P_MAX`, `S_MAX`; complete manifest-membership disposition and trusted pin source; supported target/containment contract; bootstrap/context propagation rules; reconstruction/restart/recovery disposition; exact work order and sequencing authority. |
| Before pinned operational admission | Concrete installed pins; demonstrated complete closure within 128 entries; target-specific containment evidence; instrumented byte/work accounting; compatibility and failure evidence; independent implementation review and owner acceptance under the existing lifecycle.                                 |

Future acceptance evidence must cover schema and aggregate boundaries, final rereads, profile identity/completeness, cold/warm validators, legitimate recursion, non-progressing recursion, work/depth exhaustion, swallowed-error resistance, concurrency isolation, supported-target replacement attacks and unchanged recovery/no-write behavior. None of that evidence is claimed here.

Design may proceed while MEM-03 remains BLOCKED. Any later implementation follows the existing canonical sequence: separately authorized CORE dependency work must supply its required acceptance evidence before the three-file slice relies on it. This creates no new global checkpoint and does not replace recorded ACTIVE/NEXT slots. [Canonical boundary (line 1292)]\(C:/Users/DELL/Desktop/AgentCompany/Agent_Company/ROADMAP.md:1292)

**One next action:** separately commission an independent, read-only review of this consolidated contract and its explicitly open admission prerequisites.

Frozen V1, closed Phase 8B/8C and DEC-01 design acceptance remain preserved. MEM-03 remains BLOCKED; D1 and Claude external review remain PAUSED. No implementation, tests, file edits or Git writes occurred. **Stopped before independent review.**

<!-- CONTRACT-04 ORIGINAL SOURCE END -->

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

#### DEC-01 Accepted Design Contract - 2026-10-21

Acceptance authority: the owner's design-level decision recorded in chat under
AC-DEC-01-009. Accepted baseline: the complete external
`AC-DEC-01-004_CONTRACT_REVISION.txt`, SHA-256
`696db224e437da994f8530a0f6d3b10ca8b8d25eea9ac8fde76744730fc5cbee`,
with the AC-DEC-01-006 conflict-order and AC-DEC-01-007 uncertainty-order
amendments supplied in chat. The verified source contains 454 lines. Its complete
verbatim text is preserved below in the existing architecture/scope owner; the
amendments control where they differ from that baseline. This creates no runtime
path, implementation or authority record.

The owner reports independent AC-DEC-01-008 `REVIEW_PASS`: findings 1, 3 and 4
remain PASS; conflict ordering, ESCALATE identity and uncertainty ordering are
resolved; all four original findings are closed at design level. AC-DEC-01-006,
AC-DEC-01-007 and AC-DEC-01-008 remain conversation-supplied evidence; no
standalone repository artifacts for them were verified, and the review was not
repeated. Design closure is separate from technical interface disposition,
implementation, runtime validation, Phase 9A acceptance and DEC-01 product
closure.

##### Complete retained AC-DEC-01-004 baseline

The following block is the verified 454-line source text, preserved verbatim.
Its original review-pending and historical-checkout statements describe the
baseline at authorship time; AC-DEC-01-006, AC-DEC-01-007, AC-DEC-01-008 and the
owner's AC-DEC-01-009 decision below provide the later dispositions.

<!-- AC-DEC-01-004-VERBATIM-BEGIN -->
```text
**CONTRACT_REVISION_READY — AC-DEC-01-004**

This is the complete proposed revision for independent review. It addresses the four AC-DEC-01-003 findings at contract level; their closure remains for the independent Reviewer. It grants no implementation, execution or Phase 9A acceptance.

**1. Verified foundation and scope.** The authoritative checkout is `E:\Software\Agent_Company`, branch `master`, HEAD `4773acb4fd64cec0d8d84f600377d44142f00120`. Local `origin/master` matches. The index is empty. Starting and ending Git status show the same nine tracked modifications and four untracked diagnostic files. Git reported missing commit-graph files; no repair was attempted.

The canonical Master Context remains [PROJECT_STATE.md](E:/Software/Agent_Company/PROJECT_STATE.md:221), [ROADMAP.md](E:/Software/Agent_Company/ROADMAP.md:488), [TODO.md](E:/Software/Agent_Company/TODO.md:582) and [README.md](E:/Software/Agent_Company/README.md:965). No separate context owner or repository artifact is introduced.

The first slice produces one advisory Skill Selection decision. Every outcome has `authority="none"` and `automatic=false`. Selection does not authorize loading, execution, approval, retry, graph mutation or communication. Independently authorized loading must still use [SkillCatalog.load](E:/Software/Agent_Company/runtime/context/skills.py:97).

Existing execution storage owns retention; CORE-08 owns catalog identities and instruction validation; GOV owns authority; CORE-03 owns evaluation; CORE-07 retains its existing observation and recovery boundaries. There is no new agent, orchestrator, database or authority ledger. `ExecutionResult` remains unchanged. DEC-02/JEV remains deferred. MEM-03 remains **BLOCKED** and D1 remains **PAUSED** under the current instruction.

All new schema and interface details below are proposals for acceptance, not claims of current runtime support.

**2. Closed types and bounds.** The following notation defines the complete nested vocabulary. Every object is closed: all listed fields are required, and additional fields are rejected. Nullable fields must be present as JSON `null`; omission is invalid. Discriminated variants contain exactly their variant’s fields.

| Type | Definition |
|---|---|
| `Hex` | Exactly 64 lowercase hexadecimal characters. |
| `ID` | ASCII `[A-Za-z0-9][A-Za-z0-9._:-]{0,199}`. |
| `Name` | Existing catalog name: `[a-z][a-z0-9-]{0,79}`. |
| `Text(n)` | Nonblank Unicode scalar string, at most `n` UTF-8 bytes. No unpaired surrogates; no control characters except tab, CR and LF. |
| `UInt(n)` | JSON integer from `0` through `n`, inclusive. Booleans are not integers. |
| `Time` | Valid UTC timestamp, exactly `YYYY-MM-DDTHH:MM:SS.ffffffZ`. |
| `Path` | Repository-relative reference, at most 512 UTF-8 bytes, validated through existing `RepositoryReader` path/identity rules. |
| `Pointer` | RFC 6901 JSON Pointer, at most 512 UTF-8 bytes and 16 segments; empty string means the root. |
| `List(T,n)` | Ordered array of zero through `n` values of type `T`, unless a positive minimum is specified. |
| `Ref(T)` | `{type:T, sha256:Hex}`; `T` fixes the digest domain and expected object type. |
| `RawRef` | `{type:"raw_sha256", sha256:Hex, bytes:UInt(2097152)}`. Context-specific smaller limits still apply. |
| `InstructionDigest` | `{type:"instruction_lf_utf8_sha256", sha256:Hex}`. Its distinct hashing rule is defined below. |
| `EvidenceRef` | `{slot:ID, pointer:Pointer|null, start_line:UInt(131072)|null, end_line:UInt(131072)|null}`. References one retained input slot. Use either a pointer, a valid inclusive line span starting at 1, or neither for the whole input. |
| `Scope` | `{project_id:ID, project_root:Text(1024), task_id:ID, job_id:ID|null, logical_job_id:ID|null}`. Root identity is locally resolved; optional job identities must already exist. |
| `Owner` | One of `human`, `CORE08`, `GOV`, `CORE03`, `CORE07`, `execution`, `review`, `approval`, `local_files`, `external`. An ownership label grants no authority. |
| `ExistingRef` | `{owner:Owner, identity:ID, raw:RawRef}`. Resolves a snapshot of an actual existing canonical artifact, validated by its owner. |
| `Question` | `{id:ID, request:Text(512), answer_slot:ID, source_owner:Owner}`. An inert request for a particular missing fact or material. |

A source reference is:

`Source = {owner:Owner, identity:Text(512), version:Text(200)}`.

Its identity is provenance data, never an executable path, URL-fetch instruction or authority assertion.

Every retained structured artifact uses this envelope:

`{schema_version:1, type:T, id:Ref(T), authority:"none", body:Body(T)}`.

The permitted artifact types are `decision`, `input_manifest`, `selector_config`, `build_manifest`, `eligibility_policy`, `security_policy`, `task_snapshot`, `receipt`, `link`, `failure`, `decision_eval_spec` and `decision_eval_result`. Derived digest domains additionally include `skill_metadata`, `menu`, `ranking` and `selection_result`.

The shared structural ceilings are depth 16 and 65,536 JSON nodes per artifact. No floating-point values are accepted in these new artifacts. Each individual field’s tighter bound applies.

| Capacity | Ceiling |
|---|---:|
| Registered candidates considered | 256 |
| Selected candidates | 1 |
| Query | 16,000 UTF-8 bytes |
| Decision envelope | 512 KiB |
| Input slots | 48 |
| Individual raw input | 128 KiB |
| Serialized input manifest | 128 KiB |
| Input bundle, including manifest and unique raw blobs | 2 MiB |
| Selector/configuration/policy/build/task artifact | 128 KiB each |
| Receipt | 32 KiB |
| Individual link or failure artifact | 16 KiB |
| Decision evaluation spec/result | 512 KiB each |

Existing readers may impose smaller limits. No ceiling promises that every maximum-sized combination fits. Exceeding any effective limit produces a capacity error before release; there is no truncation, eviction or partial-success result.

**3. Canonical serialization and identity.** Let `C(value)` be UTF-8 bytes of canonical JSON with sorted object keys, compact separators, ASCII escaping, lowercase hexadecimal Unicode escapes, no BOM and no trailing newline. Arrays preserve their specified order. There is no Unicode normalization or newline normalization. This matches the relevant [CORE-03 canonical serialization pattern](E:/Software/Agent_Company/runtime/evals/models.py:132), restricted here to integers and Unicode scalar strings.

Parsing rejects duplicate keys, unknown fields, unsupported versions, malformed Unicode, non-finite numbers and wrong primitive types before model construction. Models copy caller values and recursively freeze objects and arrays; a frozen outer container around mutable nested values is insufficient.

Define:

- `B(bytes) = SHA-256(bytes)`.
- `P(T,body) = {schema_version:1, type:T, authority:"none", body:body}`.
- `H(T,body) = SHA-256(ASCII("ac-dec-01/v1/") || ASCII(T) || 0x00 || C(P(T,body)))`.

The envelope’s `id` is `{type:T, sha256:H(T,body)}`. The `id` field is excluded from its own projection. The exact serialized envelope identity is separately `B(C(envelope))`.

Consequently:

- A decision’s semantic identity covers its entire body, including `as_of`, input-manifest identity, constraints, configuration, candidates and outcome.
- Retention time belongs only in its receipt.
- Changing any semantic input requires a new decision identity.
- Formatting variants are rejected on retained structured-artifact reads: stored bytes must equal `C(parsed_envelope)`.
- Existing GOV and CORE artifact hashes retain their existing algorithms. They are not silently reinterpreted as `H`.

`InstructionDigest` deliberately preserves the current catalog rule:

`SHA-256(UTF8(decoded_instruction_text.replace("\r\n", "\n")))`.

It is **not** a raw-file-byte hash. Raw input hashes never apply that transformation. This distinction preserves [current instruction validation](E:/Software/Agent_Company/runtime/context/skills.py:109).

Catalog metadata digests use `H("skill_metadata", metadata_projection)`. The projection contains exactly the eleven `SkillMetadata` fields, including explicit `version=1`, with its six tuple collections represented as arrays. Their original order is retained. Catalog format version is not a substitute for content identity.

Collections use these orders:

- Candidates: ascending catalog name.
- Menu: ascending eligible catalog name.
- Ranking: descending overlap, then ascending catalog name.
- Set-valued ID/name lists: unique, ascending ASCII order.
- Requirement rules: ascending `(skill, kind, label)`.
- Input entries: ascending slot; receipt blob references: ascending raw digest.
- Checks: the fixed order specified in section 6.
- Evidence references: unique, ordered by `(slot, pointer, start_line, end_line)`, with null before non-null.
- Build files: unique canonical path order.

No sorting rule changes retained raw bytes.

**4. Exact input bundle and configuration.** An input manifest body is:

`{entries:List(InputEntry,48), total_raw_bytes:UInt(2097152), derivations:List(Derivation,48)}`.

`InputEntry` contains exactly:

`{slot:ID, role:Role, blob:RawRef, media:"text/plain"|"application/json", origin:Origin, trust:"canonical"|"untrusted", authority:"none", source:Source, observed_at:Time, expires_at:Time|null}`.

`Role` is `query`, `catalog`, `task`, `eligibility_policy`, `selector_config`, `selector_build`, `baseline_build`, `security_policy` or `evidence`.

`Origin` is `repository`, `human_request`, or one of CORE-11’s existing external origins: `pasted`, `web`, `email`, `upload`, `retrieved`, `scraped`, `connector`, `tool`.

Exactly one entry exists for each of the first eight roles; remaining entries have role `evidence`. Slot names are unique. Every blob’s byte count and raw digest must match. `total_raw_bytes` counts unique blobs; the bundle ceiling additionally includes the manifest envelope.

Trust and origin come from the local capture boundary. External body claims cannot establish them. External origins always remain untrusted. A canonical label is permitted only where an existing local owner establishes that classification.

`Derivation` is:

`{slot:ID, transform_id:ID, transform_version:ID, original_retained:false}`.

It marks a newly supplied, transformed input. The derived bytes receive a new raw identity. The original is neither retained nor claimed replayable through that entry.

The query blob is nonblank UTF-8 text, at most 16,000 bytes. Its decoded value must exactly equal the decision objective’s query.

The task snapshot body is:

`{scope:Scope, query_slot:ID, allowed_capabilities:List(ID,64), permitted_skills:List(Name,256), constraint_ids:List(ID,64), canonical_task:ExistingRef|null, evidence:List(EvidenceRef,16), conflicts:List(Conflict,16)}`.

Its capabilities and constraints are explicit captured inputs, not inferred from token overlap. When `canonical_task` exists, the GOV owner validates its binding and ceilings. When absent, this is an advisory request without an invented canonical job or execution authority.

`Conflict` is:

`{code:"policy_conflict"|"scope_conflict"|"owner_disposition_required", owner:Owner, evidence:List(EvidenceRef,16)}`.

It requires at least one evidence reference. Only the corresponding trusted local owner can establish a conflict; untrusted text cannot promote itself into one.

The selector configuration body is fixed:

`{algorithm:"core08-token-overlap-v1", max_selected:1, tokenizer:"python-lower-ascii-alnum-set", rank_fields:["identity","description"], positive_only:true, tie_break:"identity_ascending"}`.

A build manifest body is:

`{implementation_id:ID, version:ID, files:List(BuildFile,128), python_implementation:ID, python_version:ID, unicode_version:ID}`.

At least one build file is required. `BuildFile` is `{path:Path, raw_sha256:Hex}`. These identify trusted installed code; they do not authorize loading captured source. Runtime and Unicode versions matter because the existing algorithm uses Python `str.lower()`.

**5. Decision Evidence schema.** The decision envelope body contains exactly:

| Field | Type and invariant |
|---|---|
| `decision_kind` | Constant `skill_selection`. |
| `scope` | `Scope`, matching the task snapshot. |
| `objective` | `{query:Text(16000), function:"skill_selection", constraint_ids:List(ID,64)}`; constraints match the task snapshot. |
| `as_of` | `Time`, frozen before evaluation of freshness predicates. |
| `inputs` | `Ref(input_manifest)`. |
| `selector` | `{build:Ref(build_manifest), config:Ref(selector_config)}`. |
| `eligibility_policy` | `Ref(eligibility_policy)`. |
| `security_policy` | `Ref(security_policy)`. |
| `candidate_universe` | `{catalog:RawRef, mode:"entire_catalog", coverage:"registered_catalog_only", unregistered_requested:List(Name,256)}`. |
| `candidates` | `List(Candidate,256)`, exactly the validated catalog entries. |
| `menu` | `List(Name,256)`, exactly candidates whose seven checks all pass. |
| `ranking` | `Ranking`. |
| `outcome` | One closed variant defined in section 7. |
| `uncertainty` | `List(Unknown,1792)`, exactly the unknown candidate/check pairs. |
| `confidence` | JSON `null`. |
| `baseline` | `Baseline`. |
| `replay` | `{mode:"captured_inputs_only", build:Ref(build_manifest), inputs:Ref(input_manifest), config:Ref(selector_config), as_of:Time}`; bindings equal the enclosing decision. |
| `prior_decision_ref` | `Ref(decision)|null`; immutable lineage only, never retry instructions. |

`Candidate` is:

`{skill:Name, instruction_identity:Text(512), metadata:Ref(skill_metadata), declared_instruction_digest:InstructionDigest, checks:List(Check,7)}`.

The instruction identity comes from `RepositoryReader.identity`, not path-name heuristics. The metadata reference resolves to the complete metadata projection from the retained catalog. No unselected instruction body is read.

`Check` is:

`{code:CheckCode, status:"pass"|"fail"|"unknown", reason:CheckReason, evidence:List(EvidenceRef,16)}`.

`CheckCode` is the seven-value vocabulary in section 6. `CheckReason` is one of `verified`, `none_declared`, `not_permitted`, `predicate_false`, `missing_material`, `missing_fact`, `unmapped_requirement`, `untrusted_fact`, `expired`, `not_yet_valid` or `freshness_unavailable`. Pass/fail observations require evidence; unknown observations identify the missing or insufficient evidence.

`Ranking` is:

`{positive:List(RankRow,256), zero_overlap:List(Name,256)}`.

`RankRow` is `{skill:Name, overlap:UInt(16000)}`, with overlap strictly positive. The positive rows and zero-overlap names partition the menu exactly. Excluded candidates cannot appear in either collection.

`Unknown` is:

`{skill:Name, check:CheckCode, reason:CheckReason, material:boolean, rule_ids:List(ID,64)}`.

`Baseline` is:

`{algorithm:"core08-token-overlap-v1", build:Ref(build_manifest), inputs:Ref(input_manifest), config:Ref(selector_config), menu:Ref(menu), output:Ranking, agreement:boolean}`.

The menu reference is computed from `{names:menu}` using domain `menu`; ranking identity uses domain `ranking`. Baseline bindings must match the selector’s exact query, menu and configuration. `agreement` must equal structural equality of the two ranking outputs. The first slice requires agreement; a mismatch is an error.

**6. Eligibility and freshness.** The eligibility-policy body is:

`{version:1, scope_rule:"explicit_skill_allowlist", rules:List(RequirementRule,512), freshness:List(FreshnessRule,48)}`.

Every rule has a unique `id:ID`. Requirement rules are closed variants:

- Input: `{id, kind:"input", skill:Name, label:Text(1024), slot:ID, question:Question|null}`.
- Prerequisite: `{id, kind:"prerequisite", skill:Name, label:Text(1024), slot:ID, pointer:Pointer, equals:boolean|ID, question:Question|null}`.

There is at most one mapping for each `(skill, kind, label)`. Labels match declared catalog strings exactly. Free-text prerequisites are never interpreted as executable rules. An unmapped declaration is unknown.

`FreshnessRule` is `{slot:ID, max_age_seconds:UInt(86400)}`, with a minimum of 1. Every manifest slot requires exactly one rule. Actual values must be explicitly accepted and captured; there is no implicit default.

The fixed check order and predicates are:

| Check | Pass condition |
|---|---|
| `registration` | Existing `SkillCatalog` validates the registered name, metadata and unique instruction identity from the captured catalog. |
| `capabilities` | Every declared required capability belongs to the task’s validated allowed capabilities and applicable GOV ceiling. |
| `inputs` | Every distinct declared input has an exact rule mapping to a present, security-valid retained input. |
| `prerequisites` | Every declared prerequisite has a mapped field in an owner-validated structured source, with type-strict equality to its expected value. |
| `scope` | Skill is explicitly present in `permitted_skills` and satisfies existing task/project restrictions. Empty permission list permits no skills. |
| `security` | Candidate metadata, references and required material satisfy the pinned security policy and existing repository path restrictions. |
| `freshness` | All evidence used by the other checks satisfies the freshness rules and its source owner’s validity rules at `as_of`. |

For freshness, require `observed_at ≤ as_of` and age no greater than the configured maximum. If `expires_at` exists, require `as_of < expires_at`. Capture time cannot replace an underlying source’s validity period. Unknown source validity is unknown evidence. An explicit source-owner rule may recognize immutable, content-addressed evidence without expiry.

A known false prerequisite or denied capability/scope is a fail. Missing, unmapped, untrusted or expired necessary evidence is unknown. Neither enters the verified menu. Empty prerequisite metadata produces `none_declared`, evidenced by the catalog; it does not prove undisclosed operational prerequisites absent.

Malformed catalogs, duplicate names, instruction-identity collisions or invalid path references are global validation errors, matching existing catalog behavior.

The freshness claim is limited to the captured evidence and `as_of`. Instruction bodies remain unverified until independently authorized loading. Current consideration must recheck applicable catalog/task/policy identities and freshness; historical reads do not establish current suitability.

**7. Ranking and total outcome procedure.** Eligibility is completed before actual ranking. Only the verified menu is ranked.

Preserve the existing [CORE-08 algorithm](E:/Software/Agent_Company/runtime/context/contracts.py:109) exactly:

- Tokens are the set returned by `[a-z0-9]+` matches after Python `str.lower()`.
- Candidate text is its catalog name, one ASCII space, then its description.
- Score is the cardinality of the query/candidate token-set intersection.
- Keep positive scores, sorted by descending score then ascending name.
- Duplicate, foreign, missing or incorrectly ordered ranker output is an error.

The `RelevanceRanker` interface returns identities, not scores. The adapter computes counts using the same pinned rule and verifies the returned ordering. It never infers confidence or probability from position.

Materiality is deterministic. An unknown candidate is potentially material only when it has no failed checks, has positive counterfactual overlap, and would precede the best verified positive candidate—or no verified positive candidate exists. Counterfactual counts diagnose missing evidence; they do not admit or rank the candidate in the actual menu.

A mapped question is resolvable only if it names the exact missing slot/fact and the owner permitted to supply it. An answer becomes a new captured input and new decision; it cannot silently resume this decision.

Apply this precedence:

1. **Error:** invalid, unsafe, unsupported, oversized or inconsistent input/output. Return a failure artifact; do not manufacture a decision outcome.
2. **ESCALATE:** a validated task conflict requires an existing owner’s disposition.
3. **CLARIFY:** at least one material unknown has a resolvable mapped question. Choose the first by `(skill, check order, rule ID)`.
4. **ABSTAIN:** material unknowns remain without a resolvable question.
5. **SELECT:** choose exactly the first positive ranked candidate.
6. **ABSTAIN:** otherwise report no registered/permitted candidate or no positive overlap.

Closed outcome variants are:

- `{kind:"SELECT", skill:Name, automatic:false}`.
- `{kind:"ABSTAIN", reason:"no_candidates"|"no_positive_overlap"|"insufficient_evidence", automatic:false}`.
- `{kind:"CLARIFY", skill:Name, check:CheckCode, question:Question, automatic:false}`.
- `{kind:"ESCALATE", conflict:Conflict, automatic:false}`.

Every variant forbids the other variants’ fields. `SELECT` requires menu membership, first ranking position and a positive available score. A fallback is a separate decision with new identity and retained failure provenance; it never broadens authority.

**8. Retention, commitment and recovery.** Proposed additive operations remain with the existing execution-evidence owner:

| Operation | Contract |
|---|---|
| `retain_advisory` | Validate and retain a complete draft and input bundle; return committed evidence only after verified publication. |
| `read_advisory` | Read committed historical evidence; never repair, refresh or execute it. |
| `consider_current` | Apply live owner/freshness checks to committed evidence; return advisory data or a hold. |
| `reconcile_advisory` | Explicitly authorized writer operation for an interrupted publication; never invoked by a read or automatically on restart. |

Artifacts occupy a distinct advisory namespace beneath the configured executions root, outside GOV’s `.decisions` namespace. Physical path creation requires later implementation authorization.

One cross-process lock covers all advisory publication, deduplication and recovery operations for that executions root. Reuse the existing [file-store lock mechanism](E:/Software/Agent_Company/runtime/storage/file_store.py:67). Do not nest it with canonical task/approval/GOV transition locks. Obtain owner-validated snapshots before publication; later current-use checks independently detect changed bindings.

The owner’s configured byte/object quotas include provisional and orphaned content. All writers use the same lock. Capacity checks cannot rely solely on available disk space, and no automatic deletion or eviction is permitted.

Publication order is:

1. Validate the entire draft and decoded input bundle in memory.
2. Under the advisory lock, check existing commitment and capacity.
3. Publish each input blob through a same-filesystem temporary file, flush, synchronize and atomically rename. Existing identical bytes deduplicate; differing bytes at the same digest fail.
4. Publish the canonical input-manifest envelope identically.
5. Publish the canonical decision envelope identically.
6. Read back and validate the complete set.
7. Construct, validate and atomically publish the final receipt.
8. Read back the receipt and its complete referenced set before returning success.

The receipt body is:

`{decision:Ref(decision), record_bytes:RawRef, manifest:Ref(input_manifest), manifest_bytes:RawRef, input_blobs:List(RawRef,48), committed_at:Time, writer_id:ID, mode:"fresh"|"recovered", security_policy:Ref(security_policy)}`.

Its envelope identity follows section 3. Its `committed_at` records this publication attempt’s actual commit time. It is not selection time or a reconstructed historical timestamp.

**The commit point is atomic publication of the final receipt.** Inputs and a record without that receipt remain provisional. A receipt is usable only when every referenced artifact exists and matches semantic identity, exact bytes, schema, security policy and completeness.

For concurrent identical decisions, the second writer returns the existing validated commitment and receipt. It does not replace the receipt or refresh its time. Any same-identity/different-content disagreement is an integrity conflict.

| Boundary | Required behavior |
|---|---|
| Crash before receipt publication | No committed decision; dependent use holds. |
| Crash during receipt temporary write | Temporary content is ignored; no commit. |
| Receipt published, response lost | A later validated read may deliver the existing commitment; it does not rerun selection. |
| Missing/corrupt artifact after commitment | Reject the chain; no reconstruction from current files. |
| Record/input set complete but receipt absent | Read reports uncommitted evidence. An explicit recovery writer may publish a new `mode="recovered"` receipt after complete verification. |
| Partial/conflicting retained bytes | Hold. Recovery cannot overwrite them or claim the original transaction completed. |
| Restart | Verify commitments; report provisional content. No automatic repair, redispatch or authority reuse. |
| Stale evidence | Preserve historical evidence; deny current reuse. |
| Full/unavailable medium or synchronization failure | Return capture failure; never claim retention success. |

Recovery does not refresh `as_of`. A recovered historical decision must independently pass current-consideration checks before present use.

This contract targets process-crash consistency on a validated local filesystem. Required file synchronization and atomic publication must be demonstrated on the target platform before runtime acceptance. Power-loss durability, network filesystems and coherent replacement of all retained artifacts are not claimed.

No new CORE-07 event is introduced in the first slice. Existing GOV consumption events are never repurposed. Additional independent observation/rollback detection would require explicit semantics and capacity acceptance under existing owners. Hashes and receipts alone do not authenticate a completely replaced store.

**9. Security across every artifact.** The security-policy body is:

`{implementation_id:ID, version:ID, source_files:List(BuildFile,16), allowed_media:["text/plain","application/json"], reject_sensitive_keys:true, reject_credential_shapes:true, reject_hidden_reasoning:true, max_depth:16, max_nodes:65536}`.

At least one implementation source file is required. The trusted host verifies its installed implementation and pinned digests; a supplied policy cannot disable checks.

Apply security validation to raw decoded inputs, manifests, configuration, decision records, receipts, links, evaluations and failures—before persistence and again on reads:

- Bound bytes before decoding or parsing.
- Accept only declared UTF-8 text or JSON. Reject binary, archives and opaque encoded payloads in this slice.
- Recursively inspect structured keys and string values using the pinned [canonical sensitive-content checks](E:/Software/Agent_Company/runtime/core/sanitization.py:9).
- Reject credential shapes, sensitive fields, environment dumps, hidden-reasoning fields and prohibited source channels. Do not capture scratchpads or raw provider reasoning.
- Preserve locally established origin/trust/authority metadata through retention and replay, following [CORE-11](E:/Software/Agent_Company/runtime/context/EXTERNAL_CONTENT.md:17).
- Never execute or dereference instructions embedded in data.
- Never copy rejected content, raw exceptions, commands or unsafe paths into failure evidence.

Credential detection is the declared canonical detector contract, not proof that arbitrary unmarked confidential prose can always be recognized. Closed capture channels and minimal retained fields remain necessary.

Sanitization is outside selection and retention. If separately authorized sanitization supplies replacement bytes, capture them as a new derived input identity. Never hash sanitized bytes while claiming the original bytes were retained. Discarded original content is unavailable for replay.

A failure body is closed:

`{scope:Scope|null, phase:"ingress"|"eligibility"|"ranking"|"retention"|"read"|"replay"|"evaluation"|"link"|"recovery", code:"validation"|"security"|"capacity"|"integrity"|"unavailable"|"unsupported"|"stale"|"conflict", related_decision:Ref(decision)|null, field:ID|null, automatic:false}`.

Only independently validated safe identifiers may be populated. If the evidence medium is unavailable, return the same bounded failure transiently and explicitly report that durable capture failed.

**10. GOV links and authority separation.** A link body is:

`{decision:Ref(decision), scope:Scope, relation:"task_request"|"gov_intent"|"gov_consumption"|"execution"|"evaluation"|"review"|"approval", target:ExistingRef|Ref(decision_eval_result)}`.

Relation and target owner/type must agree. The relevant existing owner validates the target’s actual identity, exact bytes and scope before the execution-evidence owner writes an immutable link.

Links are individually atomic, security-validated and read back. Missing later artifacts are represented by the absence of a link, not invented IDs. A malformed existing link is an error, not “not applicable.”

An execution-bearing link must bind the actual exact request and canonical execution evidence. A decision never substitutes for them. Existing [GOV consumption](E:/Software/Agent_Company/runtime/core/capability_governance.py:100) and [completion verification](E:/Software/Agent_Company/runtime/core/task_contract.py:511) remain unchanged.

If GOV consumption exists but an advisory link is missing, consumption remains spent. Repairing evidence does not refund an attempt, recreate approval or dispatch again. Changing a pinned executable skill requires the existing exact-work authorization flow.

**11. Non-acting replay and CORE-03 evaluation.** Replay receives a committed decision/input bundle and an explicitly selected, trusted local replay build. It receives no provider, connector, dispatcher, approval, mutation or recovery interfaces.

Replay must:

1. Verify receipt, exact bytes, all semantic identities and source provenance.
2. Use captured query, catalog, constraints, rules, versions and `as_of`.
3. Require the installed allowlisted build/runtime to match the captured manifest.
4. Recompute eligibility, menu, ranking, baseline and outcome.
5. Reproduce the decision’s semantic identity.

Missing builds or inputs are errors. Replay cannot fetch packages, dynamically import captured source, substitute current files or call live owners to update historical facts. Captured code/configuration is data, not executable authority. Historical replay validity is separate from current suitability.

The CORE-03 extension is an additive decision-subject entry point. Existing execution-bound specs, results, mandatory execution checks and GOV completion consumers continue accepting only their existing subject types. No fabricated `ExecutionResult`, job or execution identity is supplied.

A decision-evaluation spec body contains exactly:

`{subject:Ref(decision), inputs:Ref(input_manifest), menu:Ref(menu), selector_build:Ref(build_manifest), selector_config:Ref(selector_config), baseline:Ref(ranking), case_set:RawRef, case_id:ID, case_version:ID, expected:Expected, evaluator_id:"canonical-decision-deterministic", evaluator_version:"1", checks:List(EvalCheck,8)}`.

`Expected` is either:

- `{kind:"acceptable_selection", skills:List(Name,256)}`, requiring at least one skill; or
- `{kind:"non_selection", outcome:"ABSTAIN"|"CLARIFY"|"ESCALATE"}`.

`EvalCheck` is `{id:ID, type:EvalCheckType, severity:"critical"|"major"|"minor"}`.

Exactly eight unique checks are required in this order:

`record_validity`, `eligibility`, `menu_membership`, `outcome_consistency`, `evidence_coverage`, `baseline_reproducibility`, `authority_separation`, `acceptable_outcome`.

The result body is:

`{spec:Ref(decision_eval_spec), subject:Ref(decision), status:"pass"|"fail"|"error", checks:List(EvalCheckResult,8), score:null}`.

Each check result is:

`{id:ID, type:EvalCheckType, severity:"critical"|"major"|"minor", status:"pass"|"fail"|"error", code:"satisfied"|"expectation_mismatch"|"evidence_unavailable"|"invalid_evidence"|"unsupported", evidence:List(Ref(decision)|Ref(decision_eval_spec)|RawRef,16)}`.

Check identities and severities must match the spec. Aggregation gives `error` precedence over `fail`, then `pass`. Missing required evidence yields error; checks are never silently skipped. Only the explicit deterministic evaluator registry is available.

CORE-03 retains ownership and its isolation, identity and persistence patterns. Additional case bytes must be securely retained before an evaluation is released. Baseline agreement measures reproducibility; `acceptable_outcome` separately measures declared decision quality. Neither grants approval or completion.

**12. Phase 9A dependency assessment.** The six identifiers remain assessment labels from DEC-01-002. This revision creates no six-checkpoint workflow and closes none of them.

| Label | Existing owner and obligation | Dependency for the first slice |
|---|---|---|
| **P9A-1 — Capture** | Execution-evidence owner; traceable evidence and honest completeness reporting already apply. The specific advisory bundle/receipt interface is proposed. | Required before releasing retained advisory evidence or claiming exact replay. This design supplies the contract; implementation and acceptance remain unproven. |
| **P9A-2 — Unified trace** | Phase 9A coordinates identities across existing owners. Unified trace is [canonical planned scope](E:/Software/Agent_Company/ROADMAP.md:1117). | Requires advisory identity and explicit later-link semantics. Downstream execution/review/approval records become applicable when they exist. Full telemetry is not a new prerequisite for writing selector code. |
| **P9A-3 — Replay** | Phase 9A owns captured-version replay; existing policy prohibits effects and stale-authority reuse. | The captured-input-only boundary must be validated before replay is offered or claimed. A functioning selector is not needed to approve its interface. |
| **P9A-4 — Evaluation** | CORE-03 owns evaluation. Current APIs remain [execution-bound](E:/Software/Agent_Company/runtime/evals/models.py:286). | CORE-03 acceptance of the additive subject contract is needed before integration or decision-quality claims. It is not a new approval owner. |
| **P9A-5 — Integrity/recovery** | Execution storage and CORE-07 supply existing patterns and limitations. The advisory publication protocol is proposed. | Required before downstream release. Additional journal events are unnecessary for this proposed first slice and cannot be introduced implicitly. |
| **P9A-6 — Acceptance** | Human owner and independent Reviewer retain existing acceptance responsibilities. | Actual dependencies require independent validation and owner disposition. This is not a new global checkpoint or Phase 9A closure claim. |

The existing roadmap position of Phase 9A before DEC-01 remains intact. A later work order must identify the accepted substrate evidence it relies on and preserve the frozen sequence. This report neither advances that sequence nor authorizes early implementation.

Population calibration, override trends, dashboards and detailed economic measurements remain later measurements. Unsupported timing/cost stays unavailable.

**13. Acceptance criteria and static finding resolution.** These are requirements for future separately authorized validation, not tests executed here.

| Criterion | Required observable result |
|---|---|
| Identity | Identical semantic inputs reproduce identity; changing any semantic field changes it. `id` and retention time cannot create self-reference. |
| Serialization | Duplicate keys, wrong types, unknown fields, missing nullable keys and noncanonical retained bytes reject. |
| Digest domains | CRLF/LF instruction equivalence follows catalog normalization while raw-byte identities remain distinct. |
| Immutability | Mutating caller input or any nested model value cannot change retained semantic content. |
| Eligibility | Unknown, stale, unmapped, denied and untrusted requirements never enter the verified menu. |
| Ranking | Exact CORE-08 counts and ties reproduce; only the first verified positive candidate can be selected. |
| Outcomes | Error/conflict/material-clarification precedence holds even when a positive candidate exists. |
| Commitment | No outcome becomes usable before a complete matching receipt; all publication interruption boundaries hold correctly. |
| Concurrency/recovery | Identical writers deduplicate; conflicts reject; recovery records its actual new commit time and never rewrites history. |
| Security | Prohibited content in any retained component rejects before persistence; failures do not leak it. |
| Replay | No providers, connectors, dispatch, dynamic source loading, effects or authority reuse occur. Missing versions fail explicitly. |
| Evaluation/GOV | Acceptable-outcome evaluation remains separate from baseline agreement; execution/approval/completion behavior and consumed claims remain intact. |

| DEC-01-003 finding | Revision coverage | Current status |
|---|---|---|
| 1. Identity and closed schema | Sections 2–5: closed types, bounds, projections, byte identity, digest domains and ordering. | Addressed in design; independent closure pending. |
| 2. Deterministic selection | Sections 6–7: executable predicates, freshness, materiality, precedence and first-ranked selection. | Addressed in design; independent closure pending. |
| 3. Commitment and recovery | Section 8: writer/lock ownership, final-receipt commit point, deduplication and explicit recovery. | Addressed in design; independent closure pending. |
| 4. Retained-input security | Sections 4 and 9–11: all-artifact validation, provenance, derived-input identity and non-acting replay. | Addressed in design; independent closure pending. |

**14. Remaining owner decisions and risks.** Owner acceptance remains required for the proposed schema/limits, actual freshness values and requirement mappings, the conservative material-unknown policy, execution-storage interface and target-filesystem guarantees, and CORE-03’s additive subject interface. The pilot needs a versioned case set, acceptable outcomes and expansion thresholds.

Runtime compatibility, crash behavior, detector coverage and replay confinement remain unvalidated. Complete store replacement is outside the stated integrity boundary. Token overlap can be reproducible while selecting poorly; case-based quality evaluation must assess that separately.

No implementation, imports, tests, benchmarks, file edits, Git writes, installation or deployment occurred. This contract exists in the conversation; no standalone repository artifact or canonical promotion is claimed.

**One next action:** submit this complete AC-DEC-01-004 revision to a separate independent Reviewer to assess the four findings and Phase 9A dependency treatment. `automatic=false`.

Stopped before independent re-review.
```
<!-- AC-DEC-01-004-VERBATIM-END -->

Accepted first-slice direction:

- Produce one provider-neutral advisory Skill Selection decision. Every outcome
  has `authority=none` and `automatic=false`; `confidence=null`. Selection grants
  no loading, execution, approval, retry, mutation or communication authority.
  Subsequent authorized loading still uses `SkillCatalog.load`.
- Preserve existing ownership: execution evidence owns retention; CORE-08 owns
  catalog identities and instruction validation; GOV owns authority; CORE-03 owns
  evaluation; CORE-07 keeps its observation/recovery boundaries. Add no agent,
  orchestrator, database, authority ledger or authority owner. Preserve
  `ExecutionResult` and existing GOV completion/approval consumers. DEC-02/JEV
  remains deferred beyond this deterministic first slice.
- Use the baseline's closed, versioned, bounded nested schema: reject extra or
  missing fields, duplicate keys, wrong primitive types and unsupported versions;
  required nullable fields remain present. Copy and recursively freeze values.
  Existing reader limits still apply. The design ceilings include 256 candidates,
  one selection, a 16,000-byte query, a 512 KiB decision, 48 input slots,
  128 KiB individual inputs and a 2 MiB bundle; they are not proof that all
  maximum-sized combinations fit or that runtime limits have been accepted.
- Preserve the exact semantic/byte digest distinction. `C` is UTF-8 canonical
  JSON with sorted keys, compact separators, ASCII escaping, no BOM or final
  newline, and no Unicode/newline normalization. `P(T,body)` contains exactly
  `schema_version:1`, `type:T`, `authority:"none"` and `body`. Semantic identity is
  `SHA-256(ASCII("ac-dec-01/v1/") || ASCII(T) || 0x00 || C(P(T,body)))`, excluding
  its own `id`. Raw identity is SHA-256 of exact bytes; instruction digests retain
  CORE-08's decoded UTF-8 text rule with CRLF replaced by LF. Existing GOV/CORE
  digests keep their algorithms. Retention time belongs in the receipt.
- Retain the exact query, catalog, task/constraints, policies, configuration and
  selector/baseline build identities with locally established source metadata.
  The decision binds `as_of`, input-manifest identity, configuration, candidates
  and outcome. A transformed input gets a new identity and cannot claim replay
  of discarded original bytes. Instruction-body checks remain deferred until
  independently authorized loading; captured metadata is not that validation.
- Complete registration, capabilities, inputs, prerequisites, scope, security
  and freshness checks before ranking. Unknown required evidence excludes a
  candidate. Prerequisites use explicit mappings and type-strict equality;
  freshness uses captured, explicitly accepted values at frozen `as_of`, source
  validity and expiry. No free-text prerequisite becomes executable policy.
- Rank only the verified menu using the exact CORE-08 rule: Python `str.lower()`,
  `[a-z0-9]+` token sets, query intersection with name plus one space plus
  description, positive counts descending then name ascending. Verify ranker
  identities/order and baseline agreement; agreement is reproducibility, not
  selection quality. Counterfactual overlap only determines material unknowns.
- Preserve outcome precedence: Error, ESCALATE, material CLARIFY, material
  insufficient-evidence ABSTAIN, SELECT of exactly the first verified positive
  candidate, then no-candidate/no-positive-overlap ABSTAIN. Questions and fallback
  inputs produce a new decision rather than silently resuming the old one.

The accepted AC-DEC-01-006 correction is part of that contract:

- Section 4: the captured conflicts array order is immutable semantic input
  through copying, freezing, serialization, identity derivation, retention and
  replay. No sorting, deduplication or reordering is permitted. Validation
  preserves original indices.
- Section 5: ESCALATE carries the complete selected conflict, including ordered
  evidence references. The decision identity binds the ordered captured task
  snapshot and outcome. Identical captured inputs, builds, configuration and
  `as_of` reproduce the same ESCALATE payload and identity. Existing
  evidence-reference ordering requirements remain applicable.
- Section 7: when ESCALATE applies, select the first validated conflict by its
  original captured array index, not validation order. Error precedence remains
  unchanged; this does not permit skipping invalid input to manufacture advice.

The accepted AC-DEC-01-007 normative correction is also part of that contract:

> The decision body's uncertainty array MUST contain exactly one `Unknown` per
> unknown `(skill, check)` pair and MUST reject duplicate `(skill, check)` pairs.
> It MUST sort by ascending ASCII skill identity. For equal skills, it MUST use
> the fixed order `registration`, `capabilities`, `inputs`, `prerequisites`,
> `scope`, `security`, `freshness`. It MUST keep unique `rule_ids` in ascending
> ASCII order.
>
> The authoring path MUST establish canonical ordering before constructing the
> envelope. The exact ordered array participates in canonical serialization
> `C(P("decision", body))` and semantic identity `H("decision", body)`.
>
> Parsing and retained reads MUST reject duplicate pairs and noncanonical
> ordering. Readers MUST NOT reorder, deduplicate, repair or re-identify retained
> input.
>
> Replay MUST recompute the canonical array, compare every field structurally,
> including `reason`, `material` and `rule_ids`, and reproduce the decision
> semantic identity. Any mismatch MUST produce an error. No successful or partial
> replay is permitted.

Accepted persistence, security and evaluation direction:

- Add advisory retention/read/current-consideration/explicit-recovery interfaces
  under the execution-evidence owner, outside GOV's `.decisions` namespace. One
  cross-process advisory lock serializes writers and recovery without nesting
  canonical transition locks. Quotas count provisional/orphaned content; no
  automatic deletion or eviction follows.
- Publish validated input blobs, manifest and decision through synchronized
  atomic files, read back the set, then atomically publish the final receipt as
  the commit point and verify it before release. Identical writers return the
  existing commitment without replacing its time. Incomplete/conflicting chains
  hold. Reads never repair; explicitly authorized recovery may publish a new
  recovered receipt with its actual new time, without refreshing `as_of` or
  reconstructing historical bytes. Process-crash consistency requires later
  target-filesystem validation; power-loss/network-filesystem durability and
  coherent whole-store replacement detection are not claimed.
- Validate every retained input/artifact, receipt, link, evaluation and failure
  before persistence and on reads. Preserve CORE-11 origin/trust/authority
  bindings; external content stays untrusted. Apply pinned canonical sensitive
  key/credential checks, closed capture channels and safe bounded failures.
  Hash identity does not establish authenticity or universal secret detection.
- Replay uses committed captured inputs, versions and `as_of`, plus an explicitly
  selected trusted installed build matching the manifest. It receives no provider,
  connector, dispatch, approval, mutation or recovery interface, dynamically loads
  no captured source, substitutes no current files and refreshes no historical
  fact through live owners. Missing required versions or evidence is an error.
- CORE-03's decision-subject schema/entry point is an additive interface proposal,
  not support in current execution-bound APIs. Preserve execution checks and
  identity/persistence patterns; supply no fabricated job, execution identity or
  `ExecutionResult`. The eight proposed checks keep acceptable-outcome quality
  separate from baseline reproducibility. Immutable GOV links cannot refund
  consumed claims, recreate approval or redispatch.

Phase 9A remains before DEC-01 under the existing frozen roadmap. The following
labels describe dependencies of claims, not six new mandatory checkpoints or a
new pre-implementation workflow; existing owner duties remain binding:

| Label | Existing duty and proposed first-slice dependency |
|---|---|
| P9A-1 Capture | Execution evidence owns traceability; the advisory bundle/receipt interface remains proposed and must be accepted/validated before retained-replayable evidence is claimed. |
| P9A-2 Unified trace | Existing owners retain their records; exact advisory identities and later-link semantics are needed, with later execution/review/approval links applicable when their records exist. Full telemetry is not an added prerequisite for writing selector code. |
| P9A-3 Replay | Captured-version replay must prevent effects and authority reuse; the proposed captured-input boundary requires validation before replay is offered or claimed. |
| P9A-4 Evaluation | CORE-03 retains evaluation ownership; additive decision-subject acceptance is needed before integration or decision-quality claims. |
| P9A-5 Integrity/recovery | Existing storage and CORE-07 duties remain; the advisory publication/recovery protocol needs validation before downstream release. No implicit CORE-07 events are added. |
| P9A-6 Acceptance | Existing human owner and independent Reviewer retain their roles; validate actual dependencies and obtain owner disposition without claiming Phase 9A closure or creating a new global checkpoint. |

Remaining technical owner decisions are OPEN: final schema/limit and interface
dispositions; actual freshness values, source-validity rules and requirement
mappings; the conservative material-unknown policy; execution-storage API, quotas
and target-filesystem guarantees; CORE-03's additive subject interface; and the
pilot's versioned cases, acceptable outcomes and expansion thresholds. Runtime
compatibility, crash behavior, detector coverage and replay confinement remain
unvalidated. Full calibration, override trends, dashboards and detailed economics
remain later measurements; unavailable timing/cost must not be invented.

Design approval resolves none of those runtime acceptance obligations and
authorizes no implementation or roadmap advancement. **MEM-03 remains BLOCKED;
D1 remains PAUSED.** No staging, commit, push, installation or deployment is
authorized by this record. `automatic=false`.

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
- MEM-02 is CLOSED / COMMITTED / PUSHED at the owner-verified HEAD above.
- MEM-02B is formally accepted within the bounded Authority-62 / Scope-63 scope,
  with six owner PASS gates, separate-session REVIEW-113, ROUTING-115 and explicit
  ACCEPTANCE-116. CLOSURE-119 records bounded closure; MEM-02B is COMMITTED at `ad055f8`, with
  later fixture hygiene committed at `4773acb`. MEM-03, agents 11-14,
  CAP-SOC-01 and other specifically planned
  capability expansion, advanced Code Intelligence, Phase 9, Decision
  Engine/JEV, and Phase 10 remain planned and unimplemented as described above.
- The SYNC-06 R4/R2 refinements are documentation mappings, not implemented
  features, passed tests, reopened checkpoints, or authority for new work.
