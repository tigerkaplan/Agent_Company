# GOV-02 Capability Governance

GOV-02 is CLOSED / COMMITTED at `e6dbe3f` (`feat: add capability governance`).
Owner closure completed on 2026-10-03 at pre-commit HEAD `c5de474`; its dated
record and integrity evidence are preserved. Independent R5 acceptance
and canonical policy reconciliation PASS; all eight prior majors are CLOSED,
with 0 critical / 0 major / 0 minor. Same-provider reviewer role separation is
disclosed; no provider-diverse review is claimed.
See [owner closure](CLOSURE.md), [closure integrity evidence](CLOSURE_EVIDENCE.json),
[independent R5 review](reviews/GOV-02-R5/REVIEW.md) and [validation](VALIDATION.md).
V1 freeze remains active. NEXT: ORCH-01 / NOT STARTED; no authorization to begin.
Physical implementation, policy/schema, tests and governance/review paths are
CURRENT; see the root README for the reconciled physical tree. Planned future
paths remain absent. This documentation reconciliation makes no commit.

## Historical pre-implementation reality classification

| Requirement | Classification | Repository evidence |
| --- | --- | --- |
| Task scope, delegation, approvals, review, budget, durable state | SATISFIED | GOV-01 TaskContractStore, JobRuntime, ApprovalRuntime, CORE-01–11 |
| Capability/risk and blast/reversibility integration | PARTIAL | Task contracts constrain tools and L0–L5 but capabilities lack certification |
| Capability certification and policy provenance | MISSING | Routing descriptions and provider eligibility are not certificates |
| Exact-work Decision Audit Trace | MISSING | Execution artifacts and CORE-07 progress exist without a unified decision record |

## Invariants and acceptance evidence defined before implementation

1. Only tracked provider-neutral policy certifies capability/profile combinations.
   A certificate is a ceiling, never approval. Unknown/revoked capabilities deny.
2. Profile, L0–L5, actual execution mode, scope, risk, blast radius, reversibility
   and required human/review gates must agree before any supported tool effect.
   Unsupported external and sensitive action surfaces remain denied.
3. New task authority pins certification and canonical policy source digests in
   the existing task authority store. Missing, changed or historical provenance
   requires explicit recovery; no migration, backfill or inferred approval.
4. Delegation only narrows parent tools, capabilities, scope, profile, risk and
   gates. Review/model/JEV/advisor output cannot authorize transitions.
5. Audit records bind the full immutable request, policy evaluation, risk,
   blast/reversibility, authority source, approval requirements/observations,
   executor identity, result and evidence. Existing execution storage owns them.
6. Persist an intent before Worker dispatch. A consumed intent cannot dispatch
   again after restart/crash. Paired durable records and independent CORE-07
   observations detect partial writes, tampering and rollback within the existing
   trusted-filesystem boundary. Audit evidence never grants authority.

Acceptance tests must exercise actual JobRuntime/Worker/executor/store boundaries:
uncertified capability; profile and child-scope escalation; certificate/policy
tampering; understated blast radius and reversibility; self-approval; stale or
replayed requests/traces; exact-work substitution; interrupted paired writes;
restart/reconciliation; approval and independent-review integration.

Validation requires targeted/adversarial tests, affected GOV-01/approval/review/
tool/runtime integrations, focused regression, a complete full regression,
schema/static checks and git diff --check. Only completed checks are PASS.

## Runtime implementation and final reality classification

The confirmed gaps are implemented on active frozen-V1 paths. Existing task,
approval, review, budget, execution and CORE-07 state stores remain the owners.
All requirements above now have runtime enforcement; validation and independent
review determine acceptance rather than documentation claims.

| Profile | Certified boundary and required allocation |
| --- | --- |
| READ_ONLY | L0/L1, no write scope, no side effects, blast none |
| LOCAL_WRITE | Existing controlled local write, L2/L3, local/reversible, exact scope, human execution approval and independent review |
| EXTERNAL_PREPARE | L3, no mutation/external effect, blast none, no-side-effect |
| EXTERNAL_EXECUTE | Only existing separately approved Git push and PR actions, L4, external/irreversible, exact human action scope and independently reviewed completed work; generic task execution denied |
| SENSITIVE_EXECUTE | Only existing controlled local delete, L5, local/irreversible, exact destructive scope, human approval and independent review; generic financial/sensitive executor denied |

Seventeen canonical capability certificates are a tracked policy ceiling.
`independent_review` is READ_ONLY only. Only `software_implementation` has the
EXTERNAL_EXECUTE ceiling for existing Git actions. Certificates grant no approval.

`TaskContractStore` pins policy/certificate/source provenance to task authority.
`Worker` persists an exact canonical request decision before executor dispatch.
Every actual executor/provider/tool dispatch requires that durable parent evidence,
including read-only calls. Controlled writes consume their effect claim before
staging and revalidate policy before applying target changes. Existing Git runtimes
bind separately approved commit/push/PR transitions and audit success or failure.

Execution intent records contain requested_action, full request digest, policy
and risk evaluation, blast/reversibility, authority store locations and boundary
digest, approval requirements and actual canonical approval records, and executor.
Result records bind the intent, normalized result and artifact evidence. Review
records bind parent dispatch, exact package/request/result and review evidence.
Paired write-once records live alongside their existing execution/review/Git
artifacts; independent existing CORE-07 observations detect deletion, substitution,
partial persistence and replay. Model advice never becomes a policy decision.

Review delegation binds the parent's job/project, retains all authority ceilings,
and admits only exact parent inputs, declared output evidence and observations of
that execution. Review dispatch cannot replay the parent, consume write authority,
or allocate another project. Continuation may narrow; it cannot widen. A separate
canonical human Git action approval is the sole implemented bounded transition.

## Compatibility and recovery

Task declarations stay schema version 1 with optional explicit profile. New
creation anchors are version 3 and gate records version 2. Historical anchors
without GOV-02 provenance require explicit recovery; no automatic migration,
backfill, reclassification, certificate issuance or approval inference occurs.
Execution/review artifact envelopes keep their existing version; GOV-02 decision
sidecars are required for contract-bearing evidence. Historical observations can
remain readable where their existing schema permits, but never authorize effects
or bypass canonical completion/approval/review verification.

Consumption observes the journal before writing paired records. A crash after
that observation burns the dispatch/effect claim; missing pairs require recovery
and cannot refund authority. Verified existing Git effects may be reconciled as
evidence using existing behavior, with no new external operation. Existing recorded
result pairs cannot be silently rebuilt or substituted after loss.

The trusted-filesystem boundary is unchanged: these checks detect missing,
partial, stale or tampered records against independent canonical evidence; they do
not claim protection against an attacker replacing every trusted authority store
and policy simultaneously. Native CLI tools remain blocked where enforceable tool
confinement is unavailable. No live provider, VPS, deployment or publication test
is claimed. The frozen 14-agent/provider-neutral model is unchanged.

## Reproducible validation and review boundary

Run `python -B governance/capability-governance/run_validation.py targeted`,
`focused`, or `full`. Each records actual subprocess exit, completed test count,
elapsed time and SHA-256 of its log. `validation-history.json` preserves earlier
interrupted attempts; they are not passing regression evidence.
Run `python -B governance/capability-governance/validate.py` for Python AST,
repository schema JSON/local-reference validation and certificate validation.
This is the repository's existing validator, not a claim of external metaschema
validation. Run `git diff --check` separately.

Independent R5 review accepted the exact implementation and evidence; its
canonical policy reconciliation establishes independence PASS without requiring
a distinct provider or model. Owner closure is recorded in [CLOSURE.md](CLOSURE.md).
GOV-02 is committed at `e6dbe3f`; ORCH-01 has not begun. Dated F1/F2 sections below
retain their historical pre-acceptance state.

## Acceptance test mapping

| Required adversarial behavior | Actual tests |
| --- | --- |
| Uncertified capability/profile and profile escalation | `test_uncertified_capability_is_rejected_at_admission`, `test_profile_escalation_and_understated_effects_rejected`, `test_primary_reviewer_capability_cannot_certify_write_profile` |
| Child task/scope escalation and Reviewer replay | `test_child_capability_tools_and_gate_escalation_denied`, `test_review_child_identity_and_evidence_scope_cannot_widen`, `test_primary_review_task_cannot_replay_itself_through_review_dispatch` |
| Provenance/certification tampering and revocation | `test_certificate_revocation_and_tampering_fail_on_restart`, `test_deleted_parent_authority_after_intent_denies_dispatch`, action policy pair tampering and uncertified remote profile tests |
| Blast/reversibility bypass and actual supported effects | `test_read_profile_blast_and_reversibility_bypass_rejected`, controlled create/modify/delete/dry-run tests, separately approved local commit and remote push tests |
| Self-approval and model authority | Canonical local-operator approval tests, GOV-01 Reviewer/JEV advisory tests, direct uncertified execution and confined provider tests |
| Stale/replayed trace and exact-work substitution | Intent/result pair tamper tests, exact request substitution, expired deadline, consumed dispatch/effect deletion, missing result and path injection tests |
| Restart/crash/partial persistence | Paired intent/consumption interrupted-write tests; existing GOV-01 F2 subprocess crash probes and CORE-07 recovery suites; existing Git/remote recovery suites |
| Persisted compatibility | Historical anchor/provenance rejection, historical observation-only evidence, unchanged canonical completion and approval evidence verification |

Test helpers now explicitly establish canonical persisted test authority for
standalone provider/reviewer units. They are under `runtime/tests/` only and are
not imported by production. Tests no longer treat an `approved` string as proof.

Canonical dispatch admission also requires JobRuntime's valid active claim and,
for budgeted work, the exact existing CORE-05 active reservation. Task provenance
and budget capacity alone cannot replace either. Loss of that claim or reservation
before the actual tool call denies dispatch. Verified GOV-01 review-gate
strengthening is preserved: the original request stays pinned and the current gate
must pass the existing paired-record and independent-journal checks; weakening or
changing any other task/scope/policy boundary still fails closed.

Completed results and limitations are recorded in [VALIDATION.md](VALIDATION.md).

Intent consumption is bound to the canonical job attempt and verified execution-approval
generation. Existing CORE-07 transition coordination makes competing IDs/stores
admit at most one intent. A partial intent write, lost sidecar or process restart
cannot regain the consumed work by inventing another ID. The original execution
and review evidence must also retain that exact observed work-consumption digest.
Canonical policy-enforcement source bytes are pinned at loading and verified
before evaluation; changed or malformed loaded provenance requires restart, and
previous task/decision source fingerprints still fail closed after restart.

A work generation binds job ID, attempt and verified canonical execution-approval
receipt references. Existing EXECUTE_JOB or RESOLVE_HUMAN_CONDITION approval
transitions can authorize one new generation; replaying the same receipt cannot.
Completion/action receipts, provider/advisor signals, another execution/store ID,
or remaining budget cannot generate that transition. This preserves canonical
human resumption and restart behavior without widening the task/profile/scope.

## GOV-02-F1: R1 repair boundaries

Imported execution/review artifacts remain readable observations. Canonical
completion (including restart verification), required review verification,
human-boundary restoration and Git reviewed-work checks explicitly require the
persisted exact-work intent and canonical authority/dispatch trace. A null intent
cannot satisfy those prerequisites, even with a separate genuine Git approval.
Historical observations are not silently promoted or migrated.

Controlled-write application revalidates current task/tool authority, consumed
dispatch and consumed effect pairs plus their CORE-07 observations inside the
apply boundary, after target preflight and before target writes. Successful
controlled-write result acceptance also requires the consumed effect trace.
Missing, conflicting or non-canonical records require recovery; staging success
cannot substitute for these records.

Intent admission cross-checks retained exact-work intent pairs under the existing
CORE-07 transition lock. The existing canonical execution-store owner retains
an identical intent pair when a caller uses an alternate execution-artifact
root. These records only veto replay; they do not grant authority or refund
budget. Rolling back the journal alone cannot admit the same job/attempt and
execution-approval generation under another execution ID or artifact root.
Partial or missing retained intent pairs fail closed when dispatch/effect records
remain. Changed retained work identities must still pass canonical provenance
and durable-observation verification. A genuine new canonical execution-authority
receipt remains subject to the existing one-generation admission rules.

Adversarial coverage is in `runtime/tests/test_capability_governance_f1.py`.
At F1, GOV-02 remained OPEN and uncommitted pending fresh independent R2 and owner closure.
ORCH-01 has not begun.

## GOV-02-F2: R3 repair boundaries

The unchanged [R3 review](reviews/GOV-02-R3/REVIEW.md) documents three concrete
majors. F2 repairs those boundaries using the existing owners:

- Intent admission verifies every retained intent's exact identity and independent
  intent/work observations against the canonical journal owner, including entries
  whose identities appear foreign. Surviving dispatch consumption also requires
  its independent observation. Coherent intent/dispatch rebinding plus journal
  rollback cannot refund the original generation or admit a new execution ID.
- Git action consumption and acceptance both revalidate the original exact
  action-policy pair and its intent observation. The shared gate covers existing
  separately approved commit, push and pull-request transitions.
- Controlled apply verifies current authority, dispatch and consumed effect
  evidence before each target mutation and compensation, and before successful
  return. Loss after a partial effect stops further writes for explicit recovery.
  Ordinary I/O failures roll back only while that evidence remains valid.

R1 finding 1's observation/import authority restrictions are preserved. The new
eight-method / 24-case regression suite is
`runtime/tests/test_capability_governance_f2.py`. Exact reproductions, combined
rollback/restart/tamper variants, source fingerprints and complete validation
reports are under [GOV-02-F2](reviews/GOV-02-F2/FIXES.md). Reproduce or resume the
complete sequence with
`python -B governance/capability-governance/reviews/GOV-02-F2/run_validation.py`.
The runner preserves successful stage evidence and refuses source drift or
unassessed incomplete logs. This is executor validation; it does not close GOV-02.
