# Agent Company

## Agent 11 M2 Physical DOC-TREE Reconciliation - 2026-10-26

Current verified repository: `C:/Users/DELL/Desktop/AgentCompany/Agent_Company`,
branch `master`, HEAD `f49f21510812f962e9521bec830bb821f32f9b1d` with parent
documentation commit `6175d3f07522bedcd1639ded5166d1ef797e5a10` and an empty
index. The physical DOC-TREE tracks these exact M2 pilot paths:

- `pilots/agent11_finance_pricing/synthetic_cost_scenario.py` - SHA-256
  `4855FBF9C90D01BB8A37DA5C00954BE5D1A654A6705694C74F034F90846088AA`.
- `pilots/agent11_finance_pricing/test_synthetic_cost_scenario.py` - SHA-256
  `DB8DA82DADC010F6DEEA1FB1D140AEBD9071EBDB0431036A06200A7ECF55BC98`.

`AC-AG11-M2-REVIEW-20261026-02` independently returned
`REVIEW_PASS / CLOSURE_READY`, 30/30 scoped tests PASS and zero new findings.
`AC-AG11-M2-ACCEPT-20261026-03` records **OWNER ACCEPTED** for only those exact
two files. They remain byte-identical to the reviewed identities and are tracked
at code commit `f49f21510812f962e9521bec830bb821f32f9b1d`. The committed M1
pilot paths `pilots/agent11_finance_pricing/exact_division.py` and
`pilots/agent11_finance_pricing/test_exact_division.py`, its Git closure and its
narrow-sequencing authorization remain unchanged; the M1 helper retains SHA-256
`08F50215E79D81BEB256ECB1D27FD9C3671B0D83D065EB6B88774CE7FF9556B3`.

M2 is isolated, offline, synthetic and non-authoritative. It is not production
Agent 11 implementation, runtime integration or V1 acceptance. The 12 unrelated
modified tracked files and four untracked diagnostics remain protected.
`MEM-03` remains **BLOCKED / HOLD / NOT ACCEPTED**; `BUILD-02` remains
`REVIEW_PASS / ACCEPTANCE BLOCKED`; `CONTRACT-04` installation remains
**BLOCKED**; and the frozen 14-role scope is unchanged. PROJECT_STATE owns the
acceptance status, ROADMAP owns scope, TODO owns the independent documentation
review gate, and this entry records only physical path presence. No code, tests
or Git action is authorized by this reconciliation. `automatic=false`.

## Canonical DOC-TREE Reconciliation - 2026-10-24

Current verified repository: `C:/Users/DELL/Desktop/AgentCompany/Agent_Company`,
branch `master`, HEAD `98f197821966e9d4ff777ff88b69d88b96e461dd`, upstream
`origin/master`, empty index. Read-only Git tree inspection reports 751 tracked
files. The current visible worktree contains 12 pre-existing modified tracked
files and exactly four non-ignored untracked diagnostics:

- `orchestrator/graph/test_retained_fixture_diagnostics.py`
- `orchestrator/graph/test_run_validation_measurements.py`
- `runtime/tests/fixture_diagnostics.py`
- `runtime/tests/recovery_lock_telemetry.py`

Git-ignored generated/local material is physically present (2,545 ignored paths
at preflight), but it is not promoted into the canonical versioned DOC-TREE.
The tracked top level is `.agents/`, `.claude/`, `agent-generation/`, `agents/`,
`config/`, `docs/`, `governance/`, `infrastructure/`, `integrations/`,
`orchestrator/`, `providers/`, `runtime/`, `schemas/`, `shared/`, `skills/`, plus
the tracked root files `.dockerignore`, `.env.example`, `.gitignore`,
`AGENTS.md`, `CLAUDE.md`, `compose.yaml`, `CONSTITUTION.md`, `Dockerfile`,
`INTENT.md`, `PROJECT_STATE.md`, `README.md`, `ROADMAP.md` and `TODO.md`. The
detailed Current Repository Structure below remains the canonical navigation
summary.

Physical inspection confirms exactly ten current agent directories. The four
frozen V1 role targets remain absent and planned:
`agents/finance-pricing/`, `agents/analytics/`, `agents/content/` and
`agents/design/`. The other documented future roots also remain absent:
`shared/memory/`, `skills/search-growth/`,
`skills/social-media/lifecycle/`,
`orchestrator/workflows/search-growth/`,
`orchestrator/workflows/social-media-operations/`, `observability/`,
`apps/control-room/`, `orchestrator/decision-engine/` and
`project-packs/brightshore/`. No future directory was created.

Master Context ownership remains unchanged: PROJECT_STATE owns current status,
ROADMAP owns capability/architecture scope, TODO owns remaining work, and this
README owns current/planned physical DOC-TREE navigation. The attached R2 file
is reference evidence only and is not a repository tree node or canonical
document. No source, runtime, test, configuration or governance-contract path is
changed by this reconciliation.

## GOV-01 Direct API Transport Design Acceptance And DOC-TREE - 2026-10-23

AC-GOV01-TRANSPORT-DOC-001 records owner design-level acceptance of the complete
AC-GOV01-TRANSPORT-DESIGN-FIX-001 V2 contract after the owner-reported
affected-scope independent `REVIEW_PASS`. The complete verified 612-line source,
SHA-256 `ffb09725b75c805c6dd35027be82817d4cf2811e0ed0dff7b4206bfc218ced94`,
is preserved in the existing
[ROADMAP architecture owner](ROADMAP.md#gov-01-direct-api-transport-accepted-design---2026-10-23).
Its canonical embedded copy removes only ten trailing Markdown hard-break spaces
to keep repository whitespace validation clean; provenance and the normalized
copy hash are recorded with the ROADMAP source.
[PROJECT_STATE](PROJECT_STATE.md#gov-01-direct-api-transport-design-acceptance---2026-10-23)
owns status and review provenance; [TODO](TODO.md#gov-01-direct-api-transport-remaining-decisions---2026-10-23)
owns remaining owner decisions and future work.

Both reviewed findings are closed at design level. The accepted design requires
precredential exact destination/profile enforcement with zero credential
disclosure and zero provider transmission on mismatch, plus complete canonical
execution/retry/continuation evidence binding and deterministic stale/replay
rejection before review PASS. Same-byte zero-tool validation, fail-closed
responses, one transport attempt, no automatic fallback, blocked opaque CLI
adapters and a deferred/non-mandatory separate-process oracle are preserved.

This reconciliation adds no physical runtime, provider, configuration, schema,
test, credential or evidence-store path. The existing GOV-01 current physical
paths below remain unchanged. Direct API implementation, provider qualification,
isolated canary execution and runtime acceptance are NOT STARTED. The accepted
ROADMAP text is documentation, not an implemented transport or qualification
artifact.

Only the four existing Master Context documents change, retaining their current
status/scope/work/DOC-TREE ownership. Frozen V1, 14 approved roles and all prior
valid PASS/BLOCKED states remain intact. GOV-01 remains CLOSED / COMMITTED at
`852ec01`; CONTRACT-04 remains partially implemented; Phase 9A remains NOT
STARTED and unaccepted; DEC-01 implementation remains NOT STARTED; **MEM-03
remains BLOCKED; D1 remains PAUSED.** No new mandatory checkpoint or parallel
governance system is created. The documentation diff is unstaged and uncommitted.
`authority=none`; `automatic=false`.

## CONTRACT-04 Canonical Design And DOC-TREE - 2026-10-19

The complete original CONTRACT-04 and later owner design dispositions are stored
in [ROADMAP](ROADMAP.md#contract-04-accepted-design---2026-10-19), the existing
architecture/scope owner. [PROJECT_STATE](PROJECT_STATE.md#contract-04-design-acceptance-and-source-provenance---2026-10-19)
records conversation-reported acceptance and user-relayed independent design
REVIEW_PASS with source limitations; [TODO](TODO.md#contract-04-remaining-prerequisites---2026-10-19)
owns the remaining implementation and operational prerequisites.

The physical DOC-TREE now includes the completed BUILD-01 two-file slice:
`runtime/core/validation.py` and `runtime/tests/test_schema_io.py`, committed at
`376763d37a7a7cebb106cb793317bd62207fe402`. Conversation-supplied reports state
that the Codex builder obtained 12/12 focused and 112/112 affected-regression PASS
results; the independent Codex reviewer obtained 12/12 focused PASS, accepted the
112/112 final-source evidence, and returned `REVIEW_PASS` with no remaining High
finding. No retained repository test logs or standalone review artifact were
verified. The other existing CORE
candidate paths are
`runtime/progress/store.py`,
`runtime/core/capability_governance.py`, `runtime/graph/models.py` and
`runtime/tests/test_memory_readonly_inspection.py`; presence outside the reviewed
two-file slice is existing infrastructure, not CONTRACT-04 implementation
evidence. Pinned operational inspection and Windows containment remain
unimplemented and unaccepted. The separately scoped
`observability/__init__.py`, `observability/selected_trace.py` and
`runtime/tests/test_p9a_selected_trace.py` also remain absent; `observability/`
remains PLANNED. No path, directory, manifest or approval artifact is created.

The repository-external fresh inventory artifact is not a DOC-TREE node. Its
verified SHA-256 is
`2a8c958c7d3cbb99ddeed79e3e13768868e9c2ad3f517bd59507b7dcd9859e87`;
it records 178 committed candidates plus two absent proposed observability
modules. All 180 membership decisions and dependency closure remain unresolved,
so the candidate set is not an approved manifest and does not satisfy the
1-128 profile limit. Alternative A selected-action evidence inspection is
approved as design scope only; no source path, profile, pin or installation is
created by that decision.

Only the four existing Master Context documents change, retaining their current
status/scope/work/DOC-TREE ownership. BUILD-01 is CLOSED / COMMITTED, while
CONTRACT-04 remains partially implemented and Phase 9A Selected Trace remains
NOT STARTED and unaccepted. The documentation diff is uncommitted. Frozen V1 and completed checkpoints remain
intact; **MEM-03 remains BLOCKED; D1 remains PAUSED.** Claude external review stays
PAUSED. `authority=none`; `automatic=false`.

## DEC-01 Design Acceptance And DOC-TREE - 2026-10-21

AC-DEC-01-009 records owner design-level acceptance of the complete
AC-DEC-01-004 contract plus AC-DEC-01-006 and AC-DEC-01-007 after the
owner-reported independent AC-DEC-01-008 `REVIEW_PASS`. All four original design
findings are closed; DEC-01 implementation is NOT STARTED. The complete verified
454-line baseline and both normative amendments belong in
[ROADMAP](ROADMAP.md#dec-01-accepted-design-contract---2026-10-21),
status/review provenance in
[PROJECT_STATE](PROJECT_STATE.md#dec-01-design-acceptance---2026-10-21), and
remaining technical dispositions in
[TODO](TODO.md#dec-01-design-acceptance-and-remaining-decisions---2026-10-21).

Filesystem inspection confirms `observability/`, `orchestrator/decision-engine/`
and `orchestrator/decision-engine/adapters/jev/` are absent and remain PLANNED
targets. Existing CORE/GOV/evaluation/storage/progress files are supporting
contracts, not a DEC-01 implementation. The ROADMAP preservation is canonical
documentation, not a runtime, schema or implementation artifact. No report
artifact, directory, agent, database or authority owner is added by this reconciliation.
The four existing Master Context documents retain their respective ownership.

Phase 9A remains before DEC-01. P9A-1 through P9A-6 remain assessment/proposal
labels, not six new mandatory checkpoints; Phase 9A acceptance is not claimed.
`authority=none`, `automatic=false` and `ExecutionResult` remain unchanged.
**MEM-03 remains BLOCKED; D1 remains PAUSED.** Earlier dated entries retain their
historical scope. Design acceptance is not implementation, test, Git or
deployment authorization; the documentation edits remain uncommitted.

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

MEM-02B is ACTIVE / ACCEPTANCE FIX / BOUNDED REPAIR IMPLEMENTED / CLOSURE OPEN.
See [current repair status](PROJECT_STATE.md#mem-02b-fix-69-r2---2026-10-12).
Bounded evidence and counterevidence bodies now accompany the reviewed intent;
coverage binds actual reviewer content. Credential-bearing string values are
sanitized before JSON encoding. Original source hashes still bind unsanitized
bytes, and incomplete/oversized packages fail without truncation. Reconciliation
reports historical confirmation separately from current planning eligibility.

Fresh executor source/run evidence and owner-only gate commands are retained at
`E:\Software\Agent_Company_Handoff\MEM-02B\validation\FIX-69-R2-20261012`.
Retained original REVIEW-68, R1 failures, GATES-67 and GOV-02 histories are not
rewritten or retrospectively source-bound. Independent re-review and owner
closure remain OPEN. The dated BUILD-64 evidence below remains historical.

## MEM-02B BUILD-64 - 2026-10-11

MEM-02B is ACTIVE / IMPLEMENTED / BOUNDED EXECUTOR VALIDATION PASS / MANDATORY GATES PENDING / UNCOMMITTED.
See [current state and validation boundary](PROJECT_STATE.md#mem-02b-build-64---2026-10-11).
The existing four-document Master Context and README DOC-TREE ownership remain
unchanged. Earlier dated entries retain their original checkpoint meanings.

New physical CURRENT paths are `runtime/memory/learning.py`,
`schemas/learning-disposition.schema.json`, `runtime/tests/test_memory_learning.py`,
`runtime/tests/test_learning_disposition.py`, and
`runtime/tests/test_learning_disposition_recovery.py`. Existing approval, action,
review, progress vocabulary, CLI and foreground workflow surfaces are extended
within the exact 33-path allowlist. Default learning installation is disabled.
No new backend/agent/provider, graph decision engine, MEM-03 or Obsidian is added.

Executor validation is not independent acceptance. Mandatory complete GOV-02
regression and Git-dependent checks await owner execution under the no-Git work
order. No real disposition, cleanup, commit, push or deployment occurs.

### Exact BUILD-64 edit manifest

The accepted Scope-63 allowlist contains exactly 33 unique paths. Five paths
are new (learning implementation/schema and three test modules); the other 28
extend existing owners. This table is the complete executor edit manifest.

| Path | Change |
| --- | --- |
| [runtime/memory/learning.py](runtime/memory/learning.py) | New closed proposal, scope, evidence and bounded planning contracts. |
| [runtime/memory/integration.py](runtime/memory/integration.py) | Explicit host installation of Manager planning interface; default unchanged. |
| [runtime/approvals/models.py](runtime/approvals/models.py) | Conditional learning scope; legacy serialization and fingerprints retained. |
| [runtime/approvals/store.py](runtime/approvals/store.py) | Canonical bounded .learning genesis/index/transition/reservation ownership. |
| [runtime/approvals/runtime.py](runtime/approvals/runtime.py) | Exact preparation and approval binding, transitions, diagnosis and planning checks. |
| [runtime/approvals/factory.py](runtime/approvals/factory.py) | Opt-in installed learning composition. |
| [runtime/core/capability_actions.py](runtime/core/capability_actions.py) | Single-use learning application under existing transition lock. |
| [runtime/core/capability_governance.py](runtime/core/capability_governance.py) | Pins every authoritative learning implementation, schema and composition path. |
| [runtime/progress/models.py](runtime/progress/models.py) | Nonauthoritative disposition observation vocabulary; no storage format change. |
| [schemas/progress-event.schema.json](schemas/progress-event.schema.json) | Closed observation event schemas. |
| [runtime/review/context.py](runtime/review/context.py) | Complete untrusted learning review packaging. |
| [runtime/review/verification.py](runtime/review/verification.py) | Operation-specific deterministic coverage of full output and evidence. |
| [runtime/review/factory.py](runtime/review/factory.py) | Explicit opt-in review composition. |
| [runtime/cli/__main__.py](runtime/cli/__main__.py) | Disabled-by-default learning commands; existing completion commands retained. |
| [schemas/approval.schema.json](schemas/approval.schema.json) | Conditional new action; legacy scopes forbidden. |
| [schemas/learning-disposition.schema.json](schemas/learning-disposition.schema.json) | New closed learning action schema. |
| [orchestrator/workflows/project-continuation.yaml](orchestrator/workflows/project-continuation.yaml) | Opt-in exact planning selection and revalidation requirements. |
| [runtime/tests/test_memory_learning.py](runtime/tests/test_memory_learning.py) | New deterministic local fixtures and contract/capacity/source checks. |
| [runtime/tests/test_learning_disposition.py](runtime/tests/test_learning_disposition.py) | New canonical approval/disposition/Manager integration and security tests. |
| [runtime/tests/test_learning_disposition_recovery.py](runtime/tests/test_learning_disposition_recovery.py) | New crash, partial application, replay and read-only recovery tests. |
| [runtime/tests/test_approval.py](runtime/tests/test_approval.py) | Legacy approval byte/schema compatibility test. |
| [runtime/tests/test_capability_actions.py](runtime/tests/test_capability_actions.py) | Dedicated boundary and callback/foreign owner denial test. |
| [runtime/tests/test_review.py](runtime/tests/test_review.py) | Default review installation compatibility test. |
| [runtime/tests/test_memory_integration.py](runtime/tests/test_memory_integration.py) | Foreground installation compatibility test. |
| [runtime/tests/test_memory_readonly_inspection.py](runtime/tests/test_memory_readonly_inspection.py) | Learning read limits and no-write compatibility test. |
| [PROJECT_STATE.md](PROJECT_STATE.md) | Current bounded implementation state, executor evidence and manual gate status. |
| [ROADMAP.md](ROADMAP.md) | Current implementation checkpoint without later-phase scope expansion. |
| [TODO.md](TODO.md) | Pending owner gates, independent review and closure tasks. |
| [README.md](README.md) | Physical DOC-TREE, complete edit manifest and reproducible bounded commands. |
| [runtime/approvals/README.md](runtime/approvals/README.md) | Canonical manual learning action semantics and limits. |
| [runtime/review/README.md](runtime/review/README.md) | Exact full learning evidence and operation review semantics. |
| [orchestrator/approvals/APPROVAL_POLICY.md](orchestrator/approvals/APPROVAL_POLICY.md) | Human resolution semantics; completion approval kept separate. |
| [governance/capability-governance/README.md](governance/capability-governance/README.md) | Governance action mapping, freshness and unchanged mandatory validation gates. |

### BUILD-64 tested source manifest

These SHA-256 identities cover all 50 governed source files and all eight
edited test files. They were captured during the final executor runs and are
checked again after recording results. The four Master Context documents are
status/report artifacts, outside policy source pinning; their reporting changes
do not re-attest historical work. This manifest does not include its own file
hash and does not claim a Git diff or independent acceptance.

| Governed source path | SHA-256 |
| --- | --- |
| `AGENTS.md` | `39349be67961e6ffcdefb3288c7228b419f7c14e880efbef69f86bb6ea3624ed` |
| `CONSTITUTION.md` | `25273cdad156d808e5cff2e370287e40791070eefd8dc08460bebceaca74c407` |
| `governance/capability-governance/README.md` | `524595ba7e562b645d7b7eb3da9d8b96f93ca8b6bc419f5bbbed913f6c7ffc8c` |
| `orchestrator/approvals/APPROVAL_POLICY.md` | `1169152eadb909e0eaf488d94003c8d800bba64453f063de281edf769f4a95ac` |
| `orchestrator/routing/capabilities.yaml` | `6dd8886901f64f2be1b7812e9f6fb9b6418bb4453824d4f925d5ea5bb84368cc` |
| `orchestrator/workflows/project-continuation.yaml` | `74d9bfac73b0785a90b3026aead057a53b21d44a4b0a91975a0d58986e85ce79` |
| `runtime/actions/authorization.py` | `e86131705548086db1f068f422ad6904ff4c003b70b3b4e4815bc4aae9f28710` |
| `runtime/actions/runtime.py` | `4417353d0aee9584950a6492e39b5ff2dd4390182885024f0097315df87ab604` |
| `runtime/approvals/README.md` | `bac3174dd1dd1c2b86deec9bacadb40bac082a42cf519fa925f28c15c9ac29c5` |
| `runtime/approvals/factory.py` | `357b27bd8b79c7280fbc97ce7f7f926de4d1c1051e9388c697b145f081d4c86d` |
| `runtime/approvals/models.py` | `067beb0282b8c9a0a0ac51469b5dc23d985f7c9a34822a934e6a55f447646fe6` |
| `runtime/approvals/runtime.py` | `b01bd4ad1036444e604245e3bf6198a50c9ed01a3afd452eb0a5969bf18d3888` |
| `runtime/approvals/store.py` | `d509110001b84e2a9f6ee3b7212e89b0cc3c39dd5dd20d1934b40274da10a5de` |
| `runtime/budget/runtime.py` | `d0e4bc9a1a0fa77fd6e35292d4b8187b8dec473db456e0919a22de8544f40133` |
| `runtime/cli/__main__.py` | `bacddbc38b4a40f6cb807f521c43268a986bdc6082214fe46e523a11023e5e87` |
| `runtime/core/capability_actions.py` | `63f7a2abd8a9c5232bdb8ebe30cf6900a2909b3e8cd2b6fe3f68a483b9daab7f` |
| `runtime/core/capability_governance.py` | `db289990dcdfafe74933b61abb76bb0f237de37ce99991fbd90b3e7b13a75384` |
| `runtime/core/jobs.py` | `1e7b0beffcb22e9a8ca6c8cb2d03d5e6403c87a4aeb666584db45dadb8503a6f` |
| `runtime/core/task_contract.py` | `fe5f621571a9fffe3385e41d9ef5ba5e487385c66ce2b19149be7ba6e95163fe` |
| `runtime/execution/models.py` | `e1db247fd5480ff84b588a72ad94e19278459541098716a6458c7a0056ade76d` |
| `runtime/git/remote_runtime.py` | `1f2e7a7d4cbf86f533bd5c42e04d0e7c0745fdd47dcb3f2bce2aaa90c4df4062` |
| `runtime/git/runtime.py` | `65101894ed2dfa8d147421cc0a204b970ad4d34a6d83165efd780de054d5900a` |
| `runtime/graph/executor.py` | `6a4ea8cd1a8e76d6acfe7aa8ca5b67e38abd5ad6d0a8aff37d5de8da776598e2` |
| `runtime/graph/models.py` | `fea1cdada7350efa4476a5a6a8c5b31aaf5a63ba9af30671c1c07e28752db3f8` |
| `runtime/graph/planner.py` | `7a93613872f496fcdce6fa52d21dd819318678c8bf2ce928e6202f285bbd9ce9` |
| `runtime/graph/runtime.py` | `2250be3d15fd7f09e155b1ed1a6a7a4e78d93f23c16b7b12618c2f3049ef2551` |
| `runtime/memory/integration.py` | `0934da8dfa207e65721cb1c0de709a19fdecddcc705efe352a159d464f0fc126` |
| `runtime/memory/learning.py` | `9fa06e6c3c77f2fe4d2f9d42f6224e96f06ad2197d7e6c1f4d3b7ff3edcded0f` |
| `runtime/progress/models.py` | `ae6b1a2604948d6bfa7df26e9e1a052249940f70dcc956521d5453776e43b5dd` |
| `runtime/providers/context.py` | `be264db7e3c537dde3f068cb33eab4bfbe5ae54b80ff9d4bb5e90c7514dc8b3b` |
| `runtime/providers/models.py` | `addd8656c67275786c1c9184341672a3c3cb8821b582927f9272194a0a264ae4` |
| `runtime/retry/runtime.py` | `0a7aa2624d5e4df5e522e573a8d989367a9609f4827ccc087fd29dd8ea437e0d` |
| `runtime/review/README.md` | `2947395cb38ddd2d87c80aceb2daba4449177000f2637031307231ee89547871` |
| `runtime/review/context.py` | `2447ae3aa89276d9959f8a5adc76769153c575889ced4e2d771f431eb805d8d9` |
| `runtime/review/factory.py` | `d5060d950114b2fb9e6e43e035cd282edfa75f7ff8764230e8ee99c8c4c3e479` |
| `runtime/review/reviewers.py` | `e5ea926298b3d81b8e6ca2b40b081743ea016206845c2957a55bd444faaad15c` |
| `runtime/review/runtime.py` | `d2c563244fd3c8386ad5a452fb6bd98c24ab5d06ee74703362b4e413d6b4900d` |
| `runtime/review/store.py` | `f4d5c25578d6791adddcb101f4afe7bf0126e7639545015f917e35172c442013` |
| `runtime/review/verification.py` | `082f9473bf4f41ba27cef738419557c7353faafc3ed6a241757b963cda72126f` |
| `runtime/storage/execution_store.py` | `e533c9f4184649e943c29c4b6ed1c4553fb1b630bce7fc25015adb4d6208cc88` |
| `runtime/storage/file_store.py` | `06ddec9394dba8ede6790b35db9a9c783e219160bab3e53377a5a0601423b474` |
| `runtime/workers/worker.py` | `e9cc4a7e09229de93b097033460955f0ea8ddb7a4318ab8fc5c54ae33a5b5caf` |
| `schemas/approval.schema.json` | `7376ba5bc7f8c3858f0eb93349fa70f72391b562477a9323c8df73d51d6c6fe8` |
| `schemas/capability-certification.schema.json` | `1d5db70945e6ffe2ee78a61ee5ada21d57910b21c756531f759ae5f2c7d90bf5` |
| `schemas/graph-binding.schema.json` | `41537acf2fb65711c1b76bce167a4fbe80a06ff4dc37314f35609847e681c1b3` |
| `schemas/graph-plan.schema.json` | `e3274f02b520cdf235c7e658d06afbf5f8e62010697a4caf579435289e4af008` |
| `schemas/job.schema.json` | `293b46f7dff607ddd290e91b958052eaaa6feaf2e67c3dc634df82e01aea5c4b` |
| `schemas/learning-disposition.schema.json` | `5a98810b0482ac24ba368038f75dfaf7d5f82d43b85efea1c1e5c9f8c07af312` |
| `schemas/progress-event.schema.json` | `9f08ffb299b08407e153940cce891f3f52d4af73c8c79235e613e4f794111fca` |
| `schemas/task-contract.schema.json` | `301df8ca9fcd1bbbb27e2886caea0894123697e07d753314188d3c21c6a1f7b5` |

| Edited test path | SHA-256 |
| --- | --- |
| `runtime/tests/test_approval.py` | `9b721b312895441d1e638e1d23a2b9fda7c5e554c857b1fa4019bd72eab18f91` |
| `runtime/tests/test_capability_actions.py` | `c06d850412a787554face4fdf920a922c66dc3fd93b6bc104f8a65ff339664ad` |
| `runtime/tests/test_learning_disposition.py` | `0f3c5045a9254cf8e4b221d6a133a7d3b909d4ad8cb22e2caf099668619f5c0e` |
| `runtime/tests/test_learning_disposition_recovery.py` | `3e6a153bd60971d4abc34f25a5a51fc28472be35d6a54cdd1698d07c465f54e4` |
| `runtime/tests/test_memory_integration.py` | `43f854f682cf028cf59cf62b22429c6f7012d4b317c99d9a447db8d72f17acf9` |
| `runtime/tests/test_memory_learning.py` | `1810ad61e27c56aaf0365cc09b5e25222053ee73255826e89a44c4240601a418` |
| `runtime/tests/test_memory_readonly_inspection.py` | `447e03bdf77caf62f36102f64115cdbf937d1fcdb85d39d17cf6708fc64e8430` |
| `runtime/tests/test_review.py` | `83c00f22718d81b39da417ea3b5ebc5172ae6f511cc7efa66bfaaa2498241788` |

Accepted handoff file SHA-256 values (files unchanged):

- Authority-62: `4f32df273f976f51a098801ecdb61f2ce499b244d2ad290bf17a6a33dadbbeac`.
- Scope-63: `ae436c3bf87f489301fbb1aa3f2c51a19e94e0661ba7d3bdacd9147fb4aa3b92`.

### BUILD-64 reproducible executor validation

Working directory: `F:\Software\Agent_Company`. Commands use `-B` to avoid
bytecode artifacts. Learning fixtures use isolated TemporaryDirectory stores;
their declared fixture reviewer does not independently accept this implementation.
No real learning disposition is performed.

```powershell
python -B -m unittest runtime.tests.test_memory_learning runtime.tests.test_learning_disposition runtime.tests.test_learning_disposition_recovery -v
python -B governance/capability-governance/validate.py
```

The affected integration batch excludes exactly the two Git-ignore tests named
below. They remain **UNRUN / OWNER-RUN**, rather than reported passing or silently
skipped. An audit hook denies a Git launch before execution. The focused batch
uses the same hook and has no excluded tests. These commands do not create
governance report files outside the 33-path allowlist.

Affected integration command:

```powershell
@'
import re, sys, unittest
from pathlib import Path
modules = ["test_approval","test_review","test_memory_integration","test_memory_readonly_inspection","test_task_contract","test_task_contract_f1","test_task_contract_f2","test_actions"]
excluded = set(["runtime.tests.test_approval.ApprovalCliAndIgnoreTests.test_zzz_approval_artifacts_are_git_ignored","runtime.tests.test_review.ReviewCliAndIgnoreTests.test_x_review_artifacts_are_git_ignored"])
attempts = []
def guard(event, args):
    if event not in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        return
    values = args[1] if event == "subprocess.Popen" else args[0]
    words = list(values) if isinstance(values, (list, tuple)) else re.findall(r"[A-Za-z0-9_.:/\\-]+", str(values))
    if any(Path(str(word)).name.lower() in {"git", "git.exe"} for word in words):
        attempts.append(event)
        raise RuntimeError("Git launch prohibited by BUILD-64")
sys.addaudithook(guard)
def flatten(suite):
    for entry in suite:
        if isinstance(entry, unittest.TestSuite):
            yield from flatten(entry)
        else:
            yield entry
tests = list(flatten(unittest.defaultTestLoader.loadTestsFromNames(["runtime.tests." + m for m in modules])))
omitted = [t.id() for t in tests if t.id() in excluded]
suite = unittest.TestSuite(t for t in tests if t.id() not in excluded)
print("EXCLUDED_OWNER_RUN_UNRUN=" + repr(omitted), flush=True)
result = unittest.TextTestRunner(verbosity=1).run(suite)
print("GIT_LAUNCH_ATTEMPTS=" + str(len(attempts)), flush=True)
print("RESULT tests=%s failures=%s errors=%s skipped=%s" % (result.testsRun, len(result.failures), len(result.errors), len(result.skipped)), flush=True)
sys.exit(0 if result.wasSuccessful() and not attempts else 1)

'@ | python -B -
```

Focused regression command:

```powershell
@'
import re, sys, unittest
from pathlib import Path
modules = ["test_memory_foundation","test_memory_lifecycle","test_memory_validity","test_memory_knowledge_adapter","test_context_discovery","test_context_cache","test_external_content","test_capability_governance","test_progress","test_progress_f1","test_progress_f2"]
excluded = set([])
attempts = []
def guard(event, args):
    if event not in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
        return
    values = args[1] if event == "subprocess.Popen" else args[0]
    words = list(values) if isinstance(values, (list, tuple)) else re.findall(r"[A-Za-z0-9_.:/\\-]+", str(values))
    if any(Path(str(word)).name.lower() in {"git", "git.exe"} for word in words):
        attempts.append(event)
        raise RuntimeError("Git launch prohibited by BUILD-64")
sys.addaudithook(guard)
def flatten(suite):
    for entry in suite:
        if isinstance(entry, unittest.TestSuite):
            yield from flatten(entry)
        else:
            yield entry
tests = list(flatten(unittest.defaultTestLoader.loadTestsFromNames(["runtime.tests." + m for m in modules])))
omitted = [t.id() for t in tests if t.id() in excluded]
suite = unittest.TestSuite(t for t in tests if t.id() not in excluded)
print("EXCLUDED_OWNER_RUN_UNRUN=" + repr(omitted), flush=True)
result = unittest.TextTestRunner(verbosity=1).run(suite)
print("GIT_LAUNCH_ATTEMPTS=" + str(len(attempts)), flush=True)
print("RESULT tests=%s failures=%s errors=%s skipped=%s" % (result.testsRun, len(result.failures), len(result.errors), len(result.skipped)), flush=True)
sys.exit(0 if result.wasSuccessful() and not attempts else 1)

'@ | python -B -
```

Mandatory owner-run gates remain: complete GOV-02 full regression (including
Git-dependent fixtures), the two excluded Git-ignore tests, the native complete
affected/targeted and focused gates where Git is required, and `git diff --check`.
The GOV-02 report runner is unrun here because its suites execute Git and its
retained report paths fall outside the edit allowlist. It is not replaced by the
filtered executor batches. No full-suite PASS, independent acceptance or owner
closure is claimed. Owner-run commands and evidence must bind the final source;
historical tasks/receipts cannot be migrated or re-attested.

### BUILD-64 compatibility and earlier targeted commands

Final compatibility command: PASS 5/5, 0.042 s.

```powershell
python -B -m unittest runtime.tests.test_approval.LearningLegacyApprovalBytesTests runtime.tests.test_capability_actions.LearningActionIsolationTests runtime.tests.test_review.LearningReviewInstallationTests runtime.tests.test_memory_integration.LearningForegroundInstallationTests runtime.tests.test_memory_readonly_inspection.LearningArtifactReadBoundaryTests -v
```

Earlier two-test failure: two errors/2 in 25.964 s; corrected before final runs.
The Snapshot adapter and fixture import errors are recorded in PROJECT_STATE.

```powershell
python -B -m unittest runtime.tests.test_learning_disposition.LearningDispositionTests.test_inspection_and_reconciliation_create_no_locks_or_persistent_writes runtime.tests.test_learning_disposition.LearningDispositionTests.test_completion_needs_human_cannot_substitute_for_pass_review -v
```

Corrected focused rerun: PASS 3/3, 31.590 s.

```powershell
python -B -m unittest runtime.tests.test_learning_disposition.LearningDispositionTests.test_inspection_and_reconciliation_create_no_locks_or_persistent_writes runtime.tests.test_learning_disposition.LearningDispositionTests.test_completion_needs_human_cannot_substitute_for_pass_review runtime.tests.test_learning_disposition.LearningDispositionTests.test_default_runtime_remains_uninstalled -v
```

Terminal-version request rerun after the shared-validator fix: PASS 1/1,
78.781 s. This precedes final source-coverage hardening; the final 33-test run
repeats it on final source.

```powershell
python -B -m unittest runtime.tests.test_learning_disposition.LearningDispositionTests.test_revoked_version_needs_new_version_and_fresh_approval -v
```

Initial contract command passed six tests in 15.790 s, and initial promotion
integration passed one test in 19.085 s, at earlier implementation source.

```powershell
python -B -m unittest runtime.tests.test_memory_learning -v
python -B -m unittest runtime.tests.test_learning_disposition.LearningDispositionTests.test_promote_requires_confirmation_and_does_not_change_completion -v
```

Interrupted aggregate attempts use the three-module learning command above.
None establishes an aggregate PASS. The intermediate 187-test affected and
428-test focused passes predate final hardening and are historical executor
observations; final 191/191 and 428/428 reruns supersede their use for this
implementation checkpoint without rewriting historical authority.

## Post-MEM-02 Commit Reconciliation - 2026-10-11

`AC-POST-MEM02-RECONCILE-60` records **MEM-02 CLOSED / COMMITTED / PUSHED**
from owner verification, HEAD `22c9d37b503d3eea242eb6cc35041efdaac0a4d5`.
**ACTIVE: None. NEXT: MEM-02B / NOT STARTED — Learning Constraint Pipeline.**
See the [current state and evidence attribution](PROJECT_STATE.md#post-mem-02-commit-reconciliation---2026-10-11).
The existing DOC-TREE ownership and frozen V1 scope/dependencies remain unchanged.
MEM-03, DEC-01/02 and agents 11-14 stay PLANNED / NOT STARTED. Earlier dated
closure, acceptance and pending Git actions remain historical snapshots.
No agent Git command, code edit, new file, test, review, MEM-02B implementation
or deployment occurs. The next action is a separately scoped MEM-02B
contract-definition work order. STOP before implementation.

## MEM-02 Formal Bounded Closure - 2026-10-11

`AC-MEM-02-FORMAL-CLOSURE-58` records **formal bounded closure PASS; MEM-02
CLOSED / READY_TO_COMMIT**. COMMITTED/PUSHED are not asserted. ACTIVE: None.
NEXT: MEM-02 commit, pending the owner's PowerShell Git step. See the
[canonical closure gates, owner preflight and evidence](PROJECT_STATE.md#mem-02-formal-bounded-closure---2026-10-11)
and [preserved bounded acceptance matrix](PROJECT_STATE.md#mem-02-full-foreground-integration-acceptance---2026-10-11).

Accepted hashes and retained independent technical evidence remain bound to
their scopes. Same-provider review, historical FIX/FAIL/NEEDS_HUMAN records,
source-version limits and missing historical manifests are preserved. No
cross-provider PASS or fresh combined regression is claimed. Runtime approval
ID remains NOT_APPLICABLE; no runtime completion state is resolved. Non-null
mutation `diff_ref` remains unsupported and fails closed; truth, publisher
authenticity, unsupported freshness and global completeness remain UNKNOWN.
MEM-02B promotion and MEM-03 storage/durability remain OPEN / NOT STARTED.

The four existing canonical documents retain Master Context/status/scope/work
ownership; this README retains physical DOC-TREE ownership. No separate MEM-02
closure artifact is mandated by the inspected rules. All earlier dated records
below remain historical snapshots. Unrelated changes, immutable archives and
both fixture/temp directories are preserved. No Git, code/policy edit,
implementation, new files, tests/reviews or deployment occurs.

**Next owner PowerShell Git step:** inspect status, whitespace and diff scope,
then review an exact MEM-02/documentation staging allowlist. STOP before Git work.

## MEM-02 Full Foreground Integration Acceptance - 2026-10-11

`AC-MEM-02-GAP40-ACCEPT-57` records **owner GAP-40 ACCEPT** for the current
four-file foreground integration. All supplied SHA-256 identities MATCH.
**The bounded MEM-02 acceptance package is READY; MEM-02 remains OPEN / NOT
CLOSED.** Its sole remaining formal checkpoint gate is the separate owner
closure disposition. See the [canonical acceptance, exact source identities,
retained evidence and complete requirement matrix](PROJECT_STATE.md#mem-02-full-foreground-integration-acceptance---2026-10-11).

Retained Review 42, accepted P2 and repaired M1 evidence are reused with their
original source versions and outcomes. Same-provider review is disclosed;
no cross-provider PASS or fresh combined regression coverage is claimed.
Runtime approval ID is **NOT_APPLICABLE**; this manual acceptance resolves no
runtime job/approval/completion state. Recovered navigation and pre-edit live
context smoke remain historical evidence; post-edit builder behavior is not
freshly attested. Missing historical manifests remain provenance limitations.

Linked mutation diff is **UNSUPPORTED: non-null `diff_ref` must fail closed**.
Truth, publisher authenticity, unsupported freshness and global completeness
remain UNKNOWN. Operational candidate storage requires separate scoped
authority. Candidates remain untrusted; MEM-02B promotion and MEM-03 production
durability stay separate. Earlier decisions and dated documentation below remain
intact as historical snapshots; this entry supplies the current reconciliation.
No production edits, new files, tests/reviews, Git, deployment or formal closure
occur in this documentation task.

**One next permitted action:** obtain the owner's separately scoped formal
MEM-02 closure disposition against the reconciled bounded acceptance package.
STOP.

## MEM-02 Repaired Action Trace M1 Acceptance Audit Pointer - 2026-10-11

`AC-MEM-02-TRACE-M1-ACCEPT-53` records **owner ACCEPT repaired M1 only**.
Both current Action Trace source/test hashes match the accepted identities.
Owner-supplied independent technical review: **PASS, 3/3 probes**; same-provider
review is disclosed and review/source/repair-scope provenance remains unknown
or unverified. No cross-provider PASS or full scope proof is claimed.

Linked mutation diff is **UNSUPPORTED: non-null `diff_ref` must fail closed**.
Runtime approval ID is **NOT_APPLICABLE for this ad-hoc review**; the decision
resolves no runtime approval/completion state. See the
[current scoped acceptance, hashes, evidence limitations and remaining blockers](PROJECT_STATE.md#mem-02-repaired-action-trace-m1-acceptance---2026-10-11).
Historical FIX, PASS and prior ACCEPT remain intact; earlier Action Trace hash
matches below describe the bytes observed at those prior recording steps.

**MEM-02 remains BLOCKED / OPEN / NOT CLOSED.** All other MEM-02 requirements
and MEM-02B/MEM-03 boundaries remain intact. This adds no files and grants no
code, Git, test/review, deployment or closure authority.
**One next action:** reconcile the retained exact-source acceptance/evidence
mapping for remaining blockers, including unknown Action Trace review provenance
and state-layout/live-checkout evidence, in a separately scoped documentation
task. STOP.

## MEM-02 Human Security Disposition Audit Pointer - 2026-10-11

`AC-MEM-02-ROUTING-DISPOSITION-47` records the owner's existing scoped ACCEPT
decisions for Validity M1/M2, Read-Only Inspection, Action Trace (Prompt 38)
and P2 (Prompt 45). All twelve reviewed/accepted source hashes match current
files. Same-provider technical evidence and historical NEEDS_HUMAN/BLOCKED
outcomes remain intact; no cross-provider PASS is claimed.

The manual human dispositions are recorded on the canonical audit surface.
Unbound annotations cannot resolve a runtime approval/completion boundary:
applicable canonical job, execution, review and approval bindings remain
unverified, and no pending runtime gate or approval ID is invented. See the
[scoped decisions, retained evidence and policy applicability](PROJECT_STATE.md#mem-02-scoped-human-security-dispositions---2026-10-11).
**MEM-02 remains BLOCKED / OPEN / NOT CLOSED.** All other acceptance gaps and
MEM-02B/MEM-03 exclusions remain intact. This reconciliation changes only the
three existing audit documents and grants no Git, deployment or closure authority.

## MEM-02 P2 Acceptance Audit Pointer - 2026-10-11

The owner selected **ACCEPT P2 repair only** under `AC-MEM-02-P2-ACCEPT-45`.
Both accepted hashes for `runtime/cli/__main__.py` and
`runtime/tests/test_memory_integration.py` match current files. Retained
REREVIEW-44 records **technical PASS**, 8/8 fresh probes and exact patch binding;
review used a separate session/role on the same provider. Formal routing remains
NEEDS_HUMAN because alternate-provider availability and applicable disposition
are unverified. The historical 206-file manifests remain unavailable.

See the [canonical P2 decision, source identities, retained evidence and
remaining gates](PROJECT_STATE.md#mem-02-p2-human-acceptance-and-gate-reconciliation---2026-10-11).
**MEM-02 readiness remains BLOCKED / OPEN / NOT CLOSED.** No runtime approval
ID is created. Earlier Prompt 35 acceptance, owner decisions and open
requirements remain intact. This P2 decision does not accept wider GAP-40
scope or authorize MEM-02 closure, deployment or MEM-02B work.

## MEM-02 Scoped Acceptance Audit Pointer - 2026-10-11

The owner selected **ACCEPT for Action Trace Bridge, Prompt 35 only** under
`AC-MEM-02-HUMAN-ACCEPT-38`. Both accepted source hashes match the current files.
See the [scoped decision, source identities, same-provider disclosure and open
gates](PROJECT_STATE.md#mem-02-scoped-human-acceptance---2026-10-11) on the existing
canonical audit surface. MEM-02 remains OPEN / NOT CLOSED; no runtime approval
ID exists for this review and no cross-provider PASS is claimed.

Physical scope is the existing `runtime/memory/action_trace.py` and
`runtime/tests/test_memory_action_trace.py`; this pointer adds no files or paths
and establishes no Git/commit status. Earlier DOC-TREE and decision records
remain intact; broader MEM-02 implementation and closure are not established
by this two-file acceptance.

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

CURRENT / COMMITTED at `5e29cdb177838adb1682ab3b36728623d714c5e3`:
`runtime/memory/__init__.py`, `runtime/memory/contracts.py` and
`runtime/tests/test_memory_foundation.py`. `shared/memory/` stays PLANNED / absent;
production memory storage/providers, retrieval/RAG and runtime integration remain unimplemented.

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

CURRENT / UNCOMMITTED: `runtime/memory/__init__.py`,
`runtime/memory/contracts.py` and `runtime/tests/test_memory_foundation.py`.
`shared/memory/` and production memory storage/providers stay PLANNED and absent.

## POST-ORCH-01 DOC-TREE - 2026-10-09

ORCH-01 Graph Execution Runtime: CLOSED / COMMITTED at `d38780817ca9f233051efa31b77d3a8eabe1473a`
(`feat: add graph execution runtime`). Independent R4 refresh-02 PASS and owner
closure PASS; no unresolved acceptance blockers. ACTIVE: None.
NEXT: MEM-01 Knowledge / Memory Foundation / NOT STARTED, by frozen roadmap order
only; no implementation authority follows from this reconciliation.
See [owner closure](orchestrator/graph/CLOSURE.md) and
[closure evidence](orchestrator/graph/CLOSURE_EVIDENCE.json).

## SYNC-06 R4/R2 DOC-TREE Reconciliation - 2026-10-10

README remains the canonical physical CURRENT/PLANNED tree summary. The
SYNC-06 R4/R2 reconciliation creates no new Master Context, DOC-TREE, registry,
agent, runtime, or target directory. Accepted source refinements are recorded in
the existing `ROADMAP.md`; current status remains in `PROJECT_STATE.md`, and
remaining work remains in `TODO.md`. The physical owners remain:

- `runtime/` and its existing owner READMEs for closed CORE runtime foundations;
- `governance/task-contract/` and `governance/capability-governance/` for
  CLOSED / COMMITTED GOV-01 and GOV-02;
- `runtime/graph/` and `orchestrator/graph/` for CLOSED / COMMITTED ORCH-01;
- `agents/` for the current 10 canonical agents, with 14 retained as the frozen
  V1 target rather than a claim that four additional roles already exist;
- future MEM, DEC, CAP-SOC, Phase 9/10, creative/document, provider, and
  deployment paths remain PLANNED unless separately evidenced as CURRENT.

Hostinger preference and deferred purchase create no repository, host, service,
credential, backup, or deployment path. Phase 8E remains PAUSED / BLOCKED and
Phase 8F-8H remain required and NOT STARTED. No empty target directories were
created. Dated DOC-TREE entries below retain their historical checkpoint meaning.

## Historical ORCH-01 executor validation PASS - 2026-10-03

ACTIVE: ORCH-01 / IMPLEMENTED / EXECUTOR VALIDATION PASS / UNCOMMITTED.
NEXT: ORCH-01 independent review and owner closure. GOV-01/GOV-02 remain CLOSED.
MEM-01 is NOT STARTED. See [graph runtime](runtime/graph/README.md) and
[acceptance and validation](orchestrator/graph/README.md).

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

Agent Company is a local-first, model-independent operating core for coordinating AI agents across multiple projects without losing context. It starts with Claude and Codex as execution providers, and is designed to support ChatGPT and other providers later.

The company is not any one model. Providers execute work. The company core defines the durable rules, roles, state boundaries, review expectations, and routing principles that let different engines work consistently.

## Architecture

At a high level, the system separates these concerns:

- Agents define who performs work.
- Skills define how reusable work is performed.
- Prompts define task-specific instructions.
- Workflows define execution order.
- Reviewers and gatekeepers independently validate important work.
- Operational state records current work in progress.
- Long-term knowledge records stable, reusable facts and decisions.
- Provider adapters translate canonical company rules into provider-specific bootstraps.

Canonical definitions must remain separate from generated provider files. Claude, Codex, ChatGPT, and future engines should all defer to the same company constitution and operating instructions.

## Current State

CORE-04 implementation commit `35f03f8` contains the committed Tool / Skill Discovery /
Deferred Loading implementation and closure state. CORE-05 Time / Execution
Budget is CLOSED / COMMITTED at `63813b5` after CORE-05R3 PASS.
Phases 1-7 are closed, the Social Media capability is committed, Phase 8A is
closed, and Phases 8B and 8C are completed and closed after successful
independent review. Phase 8D's independent architecture/security review passed
with no critical, major, or required-fix findings. Phase 8D is COMPLETED /
CLOSED and not deployed. Phase 8E is PAUSED / BLOCKED; deployment has not
started because the VPS has not yet been created. Phases 8F through 8H are NOT
STARTED.

CORE-01 Canonical Result Contract is COMPLETED / CLOSED and committed at
`3f6acb6`. CORE-02 Continuation Policy is COMPLETED / CLOSED and committed at
`9d5ead1` after CORE-02R6 PASS with no Critical, Major, or Minor findings.
CORE-03 Eval Framework is COMPLETED / CLOSED / COMMITTED at `80ead22` after
CORE-03R5 PASS with no Critical, Major, or Minor findings. CORE-04 Tool / Skill
Discovery is CLOSED / COMMITTED at `35f03f8` after CORE-04R5 PASS with no
Critical, Major, or Minor findings. It adds explicit immutable registration,
exact capability-first matching, deterministic bounded selection, and
selected-only definition/schema loading without granting tool or execution
authority. CORE-05 adds immutable logical-job active-time/execution-unit bounds,
atomic admission/reservation, a complete genesis-validated content-addressed
usage ledger with independently verified state/head caches, restart-safe
accounting, and structured fail-closed exhaustion without granting
approval, review, continuation, retry, write, Git, or deployment authority. It
is CLOSED / COMMITTED at `63813b5` after CORE-05R3 PASS. CORE-06 Retry / Stop
Policy is CLOSED / COMMITTED at `4a6e5c4` after CORE-06R6 PASS.
CORE-07 is CLOSED / COMMITTED at `6bcffa4` after CORE-07R3 PASS;
CORE-08 is CLOSED / COMMITTED at `1a1b029` after CORE-08R3 PASS. CORE-09 is
CLOSED / COMMITTED at `fa7e30f` after CORE-09R2 PASS. CORE-01-11 are CLOSED /
COMMITTED; CORE-10 is committed at `dd72cb2` after CORE-10R3 PASS,
and CORE-11 is CLOSED / COMMITTED at `8bda7eb`. The
aggregate serialized-result byte ceiling remains FUTURE HARDENING / NON-BLOCKING.

The runtime remains local-first. Phase 8D packages the canonical Phase 8C
foreground lifecycle into one non-root image definition and fixed Compose
services. It adds no systemd unit, Windows Service, Task Scheduler job,
automatic restart supervisor daemon, VPS, Hermes, public webhook hosting, TLS
termination, merge authority, or deployment authority.
`PROJECT_STATE.md` is the canonical current-status record and `ROADMAP.md` is
the canonical capability roadmap.

GOV-01 is CLOSED / COMMITTED at `852ec01`; GOV-02 Capability Governance is
CLOSED / COMMITTED at `e6dbe3f`. ORCH-01 is CLOSED / COMMITTED at `d3878081`
after independent R4 PASS and owner closure PASS. MEM-01 is CLOSED / COMMITTED
at `5e29cdb177838adb1682ab3b36728623d714c5e3`; MEM-02 is CLOSED /
COMMITTED / PUSHED after Prompt 58 bounded closure PASS and owner verification
of HEAD `22c9d37b503d3eea242eb6cc35041efdaac0a4d5`.
ACTIVE: None. MEM-02B is CLOSED / COMMITTED in current HEAD ancestry at
`ad055f8`, with later fixture hygiene at `4773acb`. MEM-03 is BLOCKED / NOT
ACCEPTED. DEC-01 design is accepted but runtime is NOT STARTED; DEC-02/JEV is
DEFERRED. Agents 11-14 remain APPROVED V1 / PLANNED / NOT IMPLEMENTED.

## Current Repository Structure

CURRENT physical source is the verified C: checkout and HEAD recorded in the
2026-10-24 DOC-TREE overlay above. The E: ACCEPTANCE-116 and F: MEM-02 checkout
observations remain historical evidence for their checkpoints; they no longer
identify the current physical tree. External handoff and repository-external
candidate-inventory evidence are not DOC-TREE nodes. MEM-02 remains CLOSED /
COMMITTED / PUSHED at its retained owner-verified identity. Generated contents
and ignored local configuration are counted separately and are not expanded as
canonical versioned paths.

- `agents/` — 10 canonical roles: communications, knowledge-manager, marketing,
  operations, project-manager, research, reviewer, sales, social-media, and
  software. Each keeps `ROLE.md`, `GUARDRAILS.md`, and agent-specific `MEMORY.md`.
- `skills/` — separate reusable HOW definitions in communications, marketing,
  operations, sales, shared, and social-media families.
- `orchestrator/` — `dispatcher/`, `routing/`, `workflows/`, `approvals/`,
  `dry-run/`, and `graph/` (ORCH-01 contracts, closure records and retained evidence).
- `providers/` — Claude and Codex execution-provider definitions only.
- `integrations/` — github, gmail, google-calendar, google-drive, obsidian,
  telegram, and webhooks; runtime implementations exist only where explicitly
  represented by source.
- `runtime/` — `actions/`, `approvals/`, `budget/`, `cache/`, `cli/`, `compute_policy/`, `context/`, `continuation/`,
  `core/`, `evals/`, `execution/`, `executors/`, `git/`, `graph/`, `host/`, `jobs/`, `memory/`,
  `notifications/`, `progress/`, `providers/`, `queue/`, `remote/`, `review/`, `retry/`,
  `scheduler/`, `storage/`, `tests/`, `tools/`, `webhooks/`, and `workers/`.
  `runtime/memory/` is CURRENT: `__init__.py`, `contracts.py`, `lifecycle.py`,
  `knowledge_adapter.py`, `validity.py`, `action_trace.py` and `integration.py`.
  MEM-01's recorded committed foundation is `__init__.py`, `contracts.py` and
  `runtime/tests/test_memory_foundation.py`, CLOSED / COMMITTED at
  `5e29cdb177838adb1682ab3b36728623d714c5e3`. MEM-02 is CLOSED / COMMITTED /
  PUSHED at the owner-verified HEAD above. CURRENT test support:
  `test_memory_lifecycle.py`, `test_memory_knowledge_adapter.py`,
  `test_memory_validity.py`, `test_memory_readonly_inspection.py`,
  `test_memory_action_trace.py` and `test_memory_integration.py` under
  `runtime/tests/`. Foreground composition lives in existing provider context
  and CLI files; accepted Inspection lives in existing canonical owner stores.
  No production Memory provider or accepted durability is established; MEM-03
  stays BLOCKED / NOT ACCEPTED.
  `shared/memory/` stays absent / PLANNED.
  `runtime/progress/` is the CURRENT CORE-07 implementation, CLOSED / COMMITTED
  at `6bcffa4` after CORE-07R3 PASS; it contains typed/schema-validated, bounded,
  non-authoritative events and durable, capacity-safe recovery delivery. Its
  files are `__init__.py`, `models.py`, `runtime.py`, `store.py`, and `README.md`.
  Supporting CURRENT paths are `schemas/progress-event.schema.json` and
  `runtime/tests/test_progress.py`, `runtime/tests/test_progress_f1.py`, and
  `runtime/tests/test_progress_f2.py`. Integration lives in existing
  `runtime/core/jobs.py`, `runtime/workers/worker.py`,
  `runtime/providers/executor.py`, `runtime/actions/runtime.py`, and
  `runtime/scheduler/loop.py`. Generated progress journals belong beneath the
  configured state root at `jobs/.progress/`, not a planned source directory.
  `runtime/budget/` is the committed CORE-05 implementation and
  `runtime/retry/` is the CURRENT CORE-06 implementation, CLOSED / COMMITTED
  at `4a6e5c4` after CORE-06R6 PASS. It contains `__init__.py`, `models.py`,
  `runtime.py`, `store.py`, and `README.md`. Supporting CURRENT paths include
  `runtime/execution/failures.py` and the five `runtime/tests/test_retry*.py`
  modules. `runtime/state/`
  contains its tracked boundary README plus ignored operational state; it is not
  a future source-architecture namespace.
- `governance/` — CURRENT GOV-01 task-contract, delegation, stop-conditions
  and completion documentation, plus GOV-02 `capability-governance/` policy,
  validation, closure and retained review/repair evidence.
- `infrastructure/` — `HOST_ARCHITECTURE.md`, `SECURITY_MODEL.md`, its README,
  and `docker/` with non-secret per-service configuration and operating notes.
- `Dockerfile`, `.dockerignore`, and `compose.yaml` — Phase 8D packaging for the
  existing canonical runtime; no image build or deployment is recorded.
- `shared/projects/` — operational project state; currently includes
  `brightshore/`.
- `shared/knowledge/` — indexed long-term knowledge, sources, raw material,
  operations, and synthesized wiki content.
- `schemas/` — CURRENT persisted runtime contracts, including CORE-06
  `retry-policy.schema.json`, `retry-state.schema.json`, and
  `execution-artifact.schema.json`, CORE-07 `progress-event.schema.json`,
  GOV-01 `task-contract.schema.json` and GOV-02
  `capability-certification.schema.json`, plus ORCH-01 `graph-plan.schema.json`
  and `graph-binding.schema.json`.
- `config/` — tracked non-secret examples only: `host.example.json`,
  `remote.example.json`, and `webhooks.example.json`. Ignored local files,
  tokens, real IDs, and secret values are not documentation inputs.
- `.agents/` and `.claude/` — provider-specific adapters that defer to the
  canonical agents and skills; `agent-generation/` documents adapter generation.
- `docs/history/PROJECT_STATE-2026-10-11.md` — byte-preserved historical state
  snapshot added by the bounded 2026-10-11 state-layout repair; current per-path
  commit membership is not re-attested by this task.
  Its original source is repository-root `PROJECT_STATE.md`, 133,601 bytes,
  SHA-256 `553c2ef7ed2019defcc064f82086b4ab1df41d4fa69816c975cf6b8696595da6`.
  The live `PROJECT_STATE.md` remains the current-status owner; detailed
  CORE-01–07 history is accessible through its preserved headings and archive
  links. The immutable snapshot retains the original link text, but its 16
  relative link occurrences do not resolve after relocation to `docs/history/`.
  Use the working repository links in [live PROJECT_STATE.md](PROJECT_STATE.md).
  History is not a default context input. Historical Navigation PASS and the
  pre-edit live builder smoke are retained in Prompt 57's evidence mapping;
  post-edit builder behavior is not freshly attested. Runtime limits and
  historical reviewer/source bindings remain unchanged.
- Top-level `tests/` — physically present but empty; this repair created no files
  there.

Agent = WHO. Skill = HOW. Workflow = ORDER. Provider = execution engine.
Execution Result = WHAT HAPPENED. Eval = HOW THE RESULT / BEHAVIOR MET DECLARED
EXPECTATIONS. `shared/projects/` is operational project
state, `shared/knowledge/` is long-term synthesized knowledge, agent
`MEMORY.md` files hold role-specific durable lessons, and `runtime/state/` is
runtime operational state. These stores remain separate.

CORE-08 CURRENT: `runtime/context/` contains `__init__.py`, `contracts.py`,
`discovery.py`, `external.py`, `fallback.py`, `repository.py`, `skills.py`,
`README.md`, and `EXTERNAL_CONTENT.md`.
The bounded Code Intelligence / Repository Index lives in
`runtime/context/repository.py`; no separate advanced subsystem is implemented.
Supporting CURRENT paths: `skills/catalog.json`,
`runtime/tests/test_context_discovery.py`, `runtime/providers/context.py`,
`runtime/providers/executor.py`, and `runtime/providers/models.py`.
See `runtime/context/README.md` for contracts, bounds, and implementation limits.

CORE-09 CURRENT: `runtime/cache/` contains `__init__.py`, `policy.py`, and
`README.md`; `runtime/tests/test_context_cache.py` covers cache boundaries.
Integration is in `runtime/providers/context.py`. CORE-09 adds no schema file.
The provider context builder integrates bounded, provider-neutral, process-local
context reuse. Canonical identity and exact cached-contract/serialized-byte
validation keep source, skill, policy, project, task, and scope changes from
reusing stale material. TTL, LRU, and storage bounds apply; fresh discovery
still runs on hits, and cached context grants no authority.
See `runtime/cache/README.md` for validation, isolation, and performance limits.

CORE-10 CURRENT: `runtime/compute_policy/` contains `__init__.py`, `policy.py`,
`canonical.py`, and `README.md`, with `runtime/tests/test_compute_policy.py`. Provider executor,
router, and package integration apply effort and eligibility before execution.
This importable path replaces the planned `runtime/compute-policy/` label.
See `runtime/compute_policy/README.md` for policy defaults and authority limits.

CORE-11 CURRENT: `runtime/context/external.py` and
`runtime/context/EXTERNAL_CONTENT.md` implement isolation alongside CORE-08,
CLOSED / COMMITTED at `8bda7eb`. Supporting CURRENT paths are
`runtime/context/contracts.py`, `runtime/context/discovery.py`,
`runtime/context/skills.py`, `runtime/core/references.py`,
`runtime/providers/context.py`, `runtime/providers/models.py`,
`runtime/review/models.py`, and `runtime/tests/test_external_content.py`.
The former planned `runtime/isolation/` label is superseded by this integrated
implementation and remains physically absent; it is not an outstanding target.

## GOV-01 Current Physical Paths

`runtime/core/task_contract.py`, `schemas/task-contract.schema.json`,
`runtime/tests/test_task_contract.py`, `runtime/tests/test_task_contract_f1.py`,
`runtime/tests/test_task_contract_f2.py`, and `runtime/tests/contract_fixtures.py` are
CURRENT. Governance documentation is CURRENT in `governance/task-contract/`,
`governance/delegation/`, `governance/stop-conditions/`, and `governance/completion/`.
`governance/task-contract/` contains `README.md`, `REVIEW_EVIDENCE.json`,
`REVIEW_HISTORY.md`, and `VALIDATION.md`; the other three governance paths
contain their boundary READMEs.
These describe the integrated runtime; they do not establish duplicate authority stores.

## GOV-02 Current Physical Paths

`runtime/core/capability_governance.py`, `runtime/core/capability_actions.py`,
`schemas/capability-certification.schema.json`, `runtime/tests/test_capability_governance.py`,
`runtime/tests/test_capability_governance_f1.py`, `runtime/tests/test_capability_governance_f2.py`,
`runtime/tests/test_capability_governance_f3.py` and `runtime/tests/test_capability_actions.py`
are CURRENT and committed at `e6dbe3f`.
`governance/capability-governance/` contains `README.md`, `certifications.json`,
`VALIDATION.md`, `CLOSURE.md`, `CLOSURE_EVIDENCE.json`, `validate.py`,
`run_validation.py`, regression reports, source fingerprints and validation
history. Its `reviews/` contains `GOV-02-R1/` through `GOV-02-R5/` and
`GOV-02-F1/` through `GOV-02-F3/`, including the retained
`GOV-02-R5/superseded-policy-verdict/` snapshot. Tracked evidence is committed;
ignored local validation logs remain operational artifacts.
Integration extends existing `runtime/core/task_contract.py`,
`runtime/core/jobs.py`, `runtime/workers/worker.py`, `runtime/actions/runtime.py`,
`runtime/approvals/`, `runtime/git/`, `runtime/review/`, `runtime/progress/` and
`runtime/storage/execution_store.py`, plus existing task/progress schemas.
Certification/provenance extend
the existing TaskContractStore; execution and review decision traces extend their
existing stores and CORE-07 observations. The proposed capability-certification
and decision-trace directory labels are superseded by these integrated paths;
no separate governance authority store is introduced. Capability profiles are
execution constraints, not canonical agents.

## ORCH-01 Current Physical Paths

`runtime/graph/` contains `README.md`, `__init__.py`, `executor.py`, `models.py`,
`planner.py`, and `runtime.py`. The graph plan/binding schemas and six
`runtime/tests/test_graph*.py` modules are CURRENT and committed at `d3878081`.
Integration extends existing canonical job, task, execution, Worker, retry,
budget, progress, provider and CLI owners. Graph batches support at most sixteen
active units; execution profiles do not add agents or authority stores.

`orchestrator/graph/` contains committed `ACCEPTANCE.md`, `README.md`,
`VALIDATION.md`, `run_validation.py`, `CLOSURE.md` and `CLOSURE_EVIDENCE.json`.

The same physical directory also contains two CURRENT / COMMITTED standalone
D1 diagnostics files committed at `031028b6`, retained at current HEAD
`5e29cdb177838adb1682ab3b36728623d714c5e3`. Dated pre-commit status remains
historical evidence; runner optimization and D1 closure remain unfinished:

- [run_validation_diagnostics.py](orchestrator/graph/run_validation_diagnostics.py) — explicit-evidence observation reporter.
- [test_run_validation_diagnostics.py](orchestrator/graph/test_run_validation_diagnostics.py) — standalone diagnostics tests.

Both source hashes match the owner-supplied identities. Independent current-source
PASS (58/58 tests, 37 assertions, Python 3.14.3) is owner-supplied re-attestation;
historical review hash binding remains UNAVAILABLE. See
[source/review status](PROJECT_STATE.md#d1-standalone-diagnostics-source-and-review-status---2026-10-10).
These files remain under the existing validation-tooling and physical DOC-TREE
ownership. Overlap is OBSERVED; acceptance, compatibility, coverage, execution
reuse, test skipping and measured speedup remain UNKNOWN. Runner optimization
and runtime measurements remain unfinished; runner M2 stays OPEN in archived
experimental work per owner instruction, absent from the committed runner.
D1 formal closure has not been performed; no broad validation or speedup is claimed.

Only `reviews/ORCH-01-R1/probes.py` and `reviews/ORCH-01-R2/probes.py` are
committed review test support, required by the F2/F3 regression modules.
Other `reviews/` and `fixes/` artifacts, including final F3 validation and R4
acceptance evidence, remain retained local/untracked evidence. Existing ignored
logs and generated archives are not represented as committed Git evidence.
`ACCEPTANCE.md`, `VALIDATION.md`, dated reviews and closure records retain their
original checkpoint wording; the current status above supersedes it.

## Future / Target Repository Structure

The proposed paths in the list below are PLANNED and absent from the current
physical tree. This list records structural ownership only; implementation
checkpoints create paths when real content exists.

- MEM-03: future provider additions under CURRENT `runtime/memory/`;
  `shared/memory/` stays PLANNED and absent. MEM-02B learning implementation and
  tests are CURRENT as recorded in the BUILD-64 physical-tree entry above.
- Agents 11-14: `agents/finance-pricing/`, `agents/analytics/`,
  `agents/content/`, and `agents/design/`.
- CAP-SEARCH-GROWTH-01: `skills/search-growth/` and
  `orchestrator/workflows/search-growth/`.
- CAP-SOC-01: `skills/social-media/lifecycle/` for lifecycle methods and
  `orchestrator/workflows/social-media-operations/` for stateful coordination.
  These extend existing social skills and workflow ownership without a new agent.
- Phase 9B / CAP-SOC-01: `apps/control-room/social-media-hq/` for the HQ view.
- Phase 9A: `observability/`.
- Phase 9B: `apps/control-room/`.
- DEC-01: `orchestrator/decision-engine/` remains absent / PLANNED; design accepted
  under AC-DEC-01-009 after owner-reported AC-DEC-01-008 `REVIEW_PASS`,
  implementation NOT STARTED.
- DEC-02: `orchestrator/decision-engine/adapters/jev/`.
- Phase 10: `project-packs/brightshore/` first. The existing
  `shared/projects/brightshore/` is current operational project state, not a
  production Project Pack.

The current 10 canonical agents may later be joined by Finance & Pricing,
Analytics, Content, and Design for a V1 total of 14. SEO, AEO, GEO, JEV,
Memory, SAGE, Sentinel, Chimera, Lead Finder, Firecrawl, and DataForSEO are not
canonical agents. JEV remains only a possible bounded DEC-02 adapter, never a
normal execution provider, Reviewer, approval authority, or security authority.

No planned directory in this section was created by this documentation task.

## Repository Tree Reconciliation Policy - DOC-GOV-01

README owns the physical CURRENT and PLANNED target-tree summary;
PROJECT_STATE owns current status, ROADMAP owns scope and target-path ownership,
and TODO tracks remaining work. A planned path is not implementation evidence.
Reconcile these surfaces together without replacing dated review/closure records.

After any structural checkpoint, use this sequence:

implementation -> validation -> review -> closure -> commit -> physical-tree
audit -> DOC-TREE reconciliation when the filesystem changed.

Planned empty directories are never created merely for documentation
completeness. The Current Repository Structure above describes only physical
paths; this Future / Target section is the only place where absent paths are
presented as planned structure.

## V1 Scope Freeze - ACTIVE

Architecture discovery is frozen under SYNC-05 (2026-10-01), additive to SYNC-04
and SYNC-04A. The exception gate and accepted refinements live in
[ROADMAP.md](ROADMAP.md#v1-scope-freeze---active). New ideas default to POST-V1 /
LATER / REFERENCE; only critical implementation, security, data-loss, authority,
architectural-consistency, or completion-correctness blockers may be evaluated
for V1. They do not interrupt the checkpoint sequence or grant implementation
authority. ACTIVE: None. MEM-02B is CLOSED / COMMITTED in current HEAD ancestry
at `ad055f8`; later fixture hygiene is committed at `4773acb`. No blocked
implementation is promoted into NEXT by this documentation reconciliation.
MEM-02 is CLOSED / COMMITTED / PUSHED; MEM-03 is BLOCKED / NOT ACCEPTED.
MEM-01 is CLOSED / COMMITTED at `5e29cdb177838adb1682ab3b36728623d714c5e3`.
ORCH-01 is CLOSED / COMMITTED at `d3878081`; GOV-02 remains CLOSED / COMMITTED at `e6dbe3f`.
GOV-01 remains CLOSED / COMMITTED at `852ec01`.

Current canonical agents: 10; frozen V1 target: 14. CAP-CREATIVE-01 is accepted
non-blocking capability/tool architecture; CAP-DOC-01, summary-indexed retrieval,
long-document refinements, local inference, and fine-tuning remain POST-V1.
Optional future creative/document paths are PLANNED ONLY, listed in ROADMAP's
Optional Future Target Paths section; none is a CURRENT physical-tree entry.

## Canonical V1 Target

V1 includes CORE-01 through CORE-11; GOV-01 and GOV-02; ORCH-01 Graph Execution
Runtime; the Knowledge / Memory / RAG foundation; 14 canonical agents;
essential Sales, Search Growth, Reviewer, and CAP-SOC-01 capabilities; Code Intelligence;
Phase 9 Observability, Control Room, and Operating Layer; DEC-01 plus a bounded
DEC-02 JEV pilot; Phase 8E through 8H deployment/security completion; and
Brightshore as the first production Project Pack. Persistent Agent Mailbox, Git
Worktree Isolation, advanced Agent Teams, Credential / Secret Broker, Advanced
Knowledge Graph, Multi-model Council, additional memory providers, and advanced
context compaction, and later JEV / Beacon experiments remain later/important
and do not block V1.

CAP-SOC-01 is PLANNED / NOT STARTED, owned by the existing Social Media agent.
V1 prioritizes lifecycle, approval/scheduling, repurposing, basic community
triage, human handoff, performance -> memory, and basic Phase 9B Social Media HQ.
Advanced DM autonomy, influencer automation, advanced attribution, complete
platform coverage, and full autonomous community management are non-blocking.

The accepted planned details are owned by `ROADMAP.md`, including outcome-first
owner UX, expanded
CAP-REV-01 review, Unified Run Trace / Exact Replay / Trace → Eval, Semantic
Regression / Eval → Lesson Candidate, and Owner Home: "What do you want to do?"
The bounded DEC-02 pilot covers worker routing, skill selection, context
relevance/reranking, and semantic eval. JEV judges. Policy authorizes. Executor
acts. These are planned capabilities, not current implementation.

The current runtime does not implement merge, release, deployment, public
webhook hosting, TLS termination, remote task submission, remote scheduler or
filesystem/Git commands, general connector execution, infrastructure
deployment automation, Hermes integration, VPS hosting, Control Room, or a
dedicated observability platform.

## Operating Boundary

Provider execution is explicit and approval boundaries remain authoritative.
Remote users require an exact command permission; approval decisions also
require configured action/project scope and the current canonical approval
fingerprint. Telegram commands are private-chat only. Webhooks are authenticated
machine ingress on loopback and never human approval. The local scheduler is
sequential and file-backed; it does not install an operating-system service or
create approval authority.

## Quick Start

Read these files in order:

1. `INTENT.md`
2. `CONSTITUTION.md`
3. `AGENTS.md`
4. `PROJECT_STATE.md`
5. `ROADMAP.md`
6. Any provider-specific bootstrap, such as `CLAUDE.md`
