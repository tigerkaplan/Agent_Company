# R5 source inspection record

This record describes inspected mechanisms, not a test or acceptance verdict.
The review pins exact source bytes and tracked diff under this directory.

| Boundary | Actual inspected implementation |
| --- | --- |
| Certification and provenance | `runtime/core/capability_governance.py`: strict certificate primitives, duplicate policy keys, policy size ceiling, current source hashes and certified profile matching. `TaskContractStore` pins evaluation in schema-3 creation anchors and schema-2 gate records. Certificates only constrain canonical task/action authority. |
| Exact work and replay | `FileExecutionStore.begin_decision`: current canonical claim, exact Worker-built request, canonical approval receipts, transition lock, retained intent/consumption cross-checks including foreign entries and alternate roots. Independent original intent/work observations veto rebinding and rollback. |
| Claim and CORE-05 budget | `_verify_live_dispatch`: exact running claim, attempt, approval status and active reservation. Intent provenance and available capacity cannot supply either. |
| Imported observations and DONE | `load(require_authority=True)` is required at canonical completion, deterministic verification, human resumption restoration and Git reviewed-work prerequisites. Null-intent observations stay readable without granting execution or review authority. Completion still requires declared acceptance, deterministic checks, pinned deliverables, review and canonical approvals. |
| Reviewer and delegation | Certified review consumption, parent request/evidence binding, READ_ONLY child identity, project/input/tool/capability/profile ceilings, inherited stop conditions and budget references. Monotonic review strengthening remains guarded by GOV-01 paired records and journal. |
| Controlled write | `require_tool` and `require_effect` before every create/modify/delete, directory creation, compensation and final successful return. Evidence loss after one write stops later writes and cannot authorize compensating mutations. |
| Git admission and authority | `ActionDecision` requires exact canonical local-operator approval, completed/reviewed parent, separate action profile and intact original policy observation. Current evaluation, approval bytes and task provenance are rechecked. |
| R4-M1 repair | `_retained_state` checks effect/result/failure pairs and independent observations together. Retained terminal or consumed records veto consumption; failures are immutable and a missing consumption observation cannot classify attempted work as unspent. Genuine prior external effects can be recorded as observations without issuing a new effect. |
| R4-M2 repair | Local Git calls `before_mutation` before real staging and again immediately before commit. Remote push and PR call it after consumption before their effect. Required original policy, current authority and exact consumed effect evidence are mandatory. Late result rejection is separately enforced. |
| Malformed approval | Git action reads opt into canonical byte validation, rejecting duplicate fields, omitted/defaulted shape and noncanonical encodings. Approval models retain schema/type/actor/scope enforcement. Other approval reads retain existing compatibility semantics. |
| Historical compatibility | Historical task anchors missing current provenance require explicit recovery; no migration or approval backfill. Supported observation envelopes retain readable paths but cannot satisfy governed authority. Existing out-of-action Git reconciliation retains observation-only semantics. |
| Test changes | Test-only fixtures explicitly establish canonical persisted authority rather than relying on an approved string. Production does not import them. Changed negative assertions continue checking denied work and unchanged target state. Concurrency now asserts that only one executor receives the shared job attempt. |

The inspected tracked diff includes all modified runtime files, test fixtures and
adjacent regression changes. New governance/action modules and the F1/F2/F3 tests
were read directly. Original R1-R4 reports and reproductions were inspected;
hashes verify copied probes are byte-identical. Current F3 validation was read
as executor evidence, not adopted as independent passing evidence.

The checks operate inside the documented trusted-filesystem boundary. Probes
replace/lose selected evidence while retaining independent canonical owners;
they do not demonstrate that a confined provider can reach those files or
protect against replacement of every trusted authority owner and policy.
