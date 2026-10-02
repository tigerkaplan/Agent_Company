# GOV-01 Task & Authority Contract

Status: GOV-01 CLOSED / READY TO COMMIT / UNCOMMITTED after verified independent PASS and GOV-01C2 closure.
Starting HEAD verified: `92d8020`. V1 freeze active. GOV-02 NOT STARTED.

## GOV-01C2 verified implementation guarantees

The 60/60 targeted tests passed during GOV-01C. The implemented contract covers
canonical Task & Authority Contract and L0-L5 delegation; child authority is
bounded by authorized parent scope, with exact contract/work binding and existing
scope/budget integration. Evidence-Gated Completion requires acceptance checks,
required evidence, review and approval, while explicit stop conditions deny work.
Governed Reviewer dispatch narrows parent authority and enforces provider policy;
canonical approval evidence is reloaded and bound to completion receipts.
Durable authority strengthening cross-checks independent CORE-07 observations to
resist rollback within the documented filesystem boundary. Restart/crash
consistency holds incomplete or inconsistent writes for explicit recovery.
Provider output cannot grant authority; opaque native CLI tooling remains blocked.
Unsupported historical records fail closed without migration or backfill.

These guarantees do not protect against coherent replacement of every relevant
trusted store. Final independent PASS, confirmed separate reviewer role, zero
findings and one complete 1227/1227 full run are verified in
[review evidence](REVIEW_EVIDENCE.json) and [validation](VALIDATION.md).
[Review history](REVIEW_HISTORY.md) preserves actual R3 FIX and historical R4 PASS.
GOV-01 is CLOSED / READY TO COMMIT; GOV-02 remains NEXT / NOT STARTED.

## Initial reality classification

| Requirement | Before GOV-01 | Existing foundation / confirmed gap |
| --- | --- | --- |
| Canonical approvals, controlled scope, review, budgets, persisted execution | SATISFIED | Existing approval/actions/review/budget/execution stores; reused unchanged as authority owners |
| Exact work binding and immutable requests | PARTIAL | Approval fingerprint, retry work digest and authorized continuation existed; canonical task policy was absent |
| Contract fields and delegation L0-L5 | MISSING | No canonical task-level authority ceiling |
| Evidence-gated DONE | PARTIAL | Execution results and deterministic evals existed; success could reach terminal completion without task acceptance and pinned evidence |
| Contract persistence and tamper/staleness enforcement | MISSING | No task-contract anchor, witness or durable completion receipt |
| Provider resistance | PARTIAL | Scope/approval/external-content protections existed; contract/tool ceilings and completion gates were absent |

## Canonical implementation

`schemas/task-contract.schema.json` and `runtime/core/task_contract.py` define the
provider-neutral contract. Every new canonical job contains objective, inputs,
expected outputs, allowed tools/capabilities, write scope, existing budget
references, acceptance criteria, required checks/evidence, stop conditions, risk,
blast radius, reversibility, delegation level, and execution/completion/review
approval requirements. Closed schemas, exact primitive validation, bounded JSON,
registered evaluator checks and unique IDs reject malformed declarations.

JobRuntime validates exact objective, inputs, capability, scope, risk and budget
binding at admission and reload. Approval fingerprints, immutable ExecutionRequest,
provider/review packages and retry identity include the contract. Retry preserves
its logical budget and contract. Continuation inherits ceilings and gates from the
persisted authorized parent; it only adapts objective/inputs to the approved step.
Review escalation is monotonic. Provider output is evidence, never authorization.

### GOV-01F1 authority repairs

Provider-backed Reviewer dispatch requires both `provider_call` and
`independent_review` in the parent contract. It derives a read-only review
contract, preserves parent budget references, stop conditions and approval gates,
narrows tools/capabilities and delegation, applies canonical provider eligibility
and compute filters, and runs the existing native-tool confinement guard before
adapter invocation. This delegation cannot approve or complete the parent job.
New conservative envelopes include `independent_review` only when review is
declared at creation. Existing explicit contracts are never expanded automatically.

Omitting a contract creates a conservative execution envelope with **empty
acceptance criteria**. This supports existing admission without inventing business
acceptance; successful execution cannot become DONE. Callers must explicitly
provide criteria mapped to deterministic checks. Old jobs without contracts or
anchors fail closed; this checkpoint does not backfill authority or migrate them.

## Runtime enforcement and persistence

JobRuntime admission, claim authority and terminal save; Worker dispatch; local,
provider and controlled-write executors; native CLI adapters; existing review and
human completion approval all enforce this policy. Direct executors check tools,
approval requirements and stop/deadline conditions before effects. Native adapters
must expose a trusted, empty native-tool surface: the current opaque CLI adapters
cannot demonstrate confinement and are blocked before process invocation.
This is an explicit operational limitation, not live provider validation.

Existing jobs state contains `.task-contracts/<job-id>.anchor.json` and `.witness.json`.
These write-once canonical bytes bind exact work, lineage identity and original
gates. Completion uses separate anchor/witness receipts in this same store to pin
accepted time, contract, full execution/eval/review/artifact digests and evidence
store roots. Missing, partial, conflicting or changed records require recovery;
there is no automatic reauthorization. Identical interrupted terminal writes may
reuse the receipt only after current gates and deadline checks pass.

These filesystem records protect against inconsistent artifact edits, not an
attacker able to replace every canonical authority file. Existing filesystem and
human authority trust boundaries remain in force. No new approval store exists.

Historical GOV-01F1 creation anchors use an explicit version-2 envelope. The same
TaskContractStore also owns paired accepted gate records and write-once review
strengthening witnesses. A strengthened gate is persisted before the job write
under the existing transition lock. Replaying a stale job or accepted gate record,
missing either acceptance half or strengthening witness, and interrupted updates
fail closed and require explicit recovery. No separate authority store is added.

GOV-01R2 found that replaying the old job and both gate records while deleting
both strengthening witnesses bypassed F1. GOV-01F2 cross-checks those records
against independent `task_gate_observed` events in the existing CORE-07 journal.
Creation commits a canonical genesis observation. Strengthening commits its
observation in a FULL synchronous SQLite transaction before writing witnesses,
gate records or the job, under the existing lifecycle transition lock. Each
observation binds the exact gate/contract boundary digest. Every canonical job
validation reads the complete protected history, including schema, chain, head,
pending records and capacity, and requires the exact ordered genesis/strengthening
observations. These observations only veto inconsistent authority; they never
grant execution, approval, review completion, budgets or DONE.

The combined R2 replay leaves the independent observation intact and fails closed.
Missing or damaged journals, deleted witnesses, older journal snapshots conflicting
with current gate records, and interrupted writes require explicit recovery.
Reconciliation never synthesizes gate observations from job snapshots. Repeated
accepted strengthening is idempotent; concurrent writers use the existing lock.
An uncommitted SQLite transaction accepts no strengthening. Once that independent
commit succeeds, any later interruption holds the task rather than refunding its
gate. Creation anchors and task declaration identity are preserved unchanged.

F2 does not migrate pre-F1 or pre-F2 task authority. Even intact F1 records without
the independent genesis/history require explicit recovery; absence cannot mean
"never strengthened". The progress event vocabulary adds one non-authoritative
observation without changing the existing journal schema/persistence owner.
This resists replay of GOV-01 files against independent CORE evidence, not an
owner replacing all relevant canonical stores with a coherent old snapshot.
No software-only local journal can detect replacement of every trusted copy.

Version-2 completion state/receipts pin approval artifact digests and the canonical
approval store root. FileApprovalStore validates exact approved task boundaries,
local-operator decisions, scope, execution/review identities, linked evidence and
the compact projection. Restart reloads these artifacts through that existing
approval system. Missing, corrupt, rejected or replaced approval evidence
invalidates DONE; unrelated historical annotations and later Git approvals do
not become task completion authority.

Compatibility is deliberately fail closed: pre-F1 unversioned creation anchors,
records without accepted gate evidence, and version-1 completion state/receipts
require explicit recovery. F1 performs no migration, backfill or reauthorization;
historical authority cannot be reconstructed from a mutable job snapshot. Contract
schema version 1 remains the task declaration format; persistence versions are
separate. New version-2 records retain the original contract and canonical CORE
approval, review, write, budget, retry and continuation boundaries.

## Delegation, completion and stops

See [delegation](../delegation/README.md), [completion](../completion/README.md),
and [stop conditions](../stop-conditions/README.md). Git read is a distinct tool;
Git write, deployment, external action and financial authority are never granted
by a delegation label, provider output, review PASS or budget availability.

## Validation

Initial implementation results: targeted 28/28, focused 290/290, full regression
1195/1195 PASS. GOV-01 R1 subsequently found three Major issues; GOV-01F1 repairs
and validation are recorded separately in [validation evidence](VALIDATION.md).
See [validation evidence](VALIDATION.md) and PROJECT_STATE.md. Syntax, schema parsing
and git diff --check passed. No commit or GOV-02 work was performed.
Adversarial coverage includes missing acceptance/evidence, actual persisted review,
human completion approval, opaque providers, tools, stop/deadline, forged outputs,
contract mutation/anchor loss, receipt tampering/restart, and retry inheritance.
Existing fixture acceptance is explicitly declared in test-only helpers; production
never synthesizes acceptance. No commit or GOV-02 work is authorized.
