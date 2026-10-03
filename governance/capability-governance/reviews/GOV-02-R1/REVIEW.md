# GOV-02-R1 review evidence

Review decision: **FIX** (canonical skill outcome: **FAIL**).
INDEPENDENCE: **FAIL**. The reviewing assistant is the GOV-02 executor from the same conversation. No distinct reviewer/provider participated. Fresh source inspection and fresh test results are evidence, but do not satisfy Constitution rule 9 or the canonical review skill's executor independence requirement. This is not an independent acceptance sign-off.

Scope: HEAD `c5de47440973c87023bbd6652aca984262ab17f7`, uncommitted GOV-02 diff and additions. V1 freeze active. Only review artifacts in this directory were added. No implementation fixes, canonical rule changes, commit, push, deployment or ORCH-01 work.

## Findings

Critical: 0. Major: 3. Minor: 0.

### R1-M1 ? Observation imports can become completion and review authority (MAJOR)

`FileExecutionStore.create` records `intent_digest: null` when no intent exists (`runtime/storage/execution_store.py:302`); `verify_decision` verifies the parent authority/dispatch only when that digest is non-null (`:166`). `FileReviewStore.create` has the same observation import (`runtime/review/store.py:78`), and `load` skips parent/Reviewer dispatch verification for null intent (`:110`). Canonical completion loads those records (`runtime/core/task_contract.py:466`, `:542`) without requiring non-null decision intents.

Fresh probe 1 created a canonical job, enqueued/claimed it, imported a successful ExecutionResult without calling any executor or creating an intent, and passed canonical `record_execution_success`/completion. Actual final status: `completed`; intent digest: null; executor called: false.

Fresh probe 3 used the existing canonical Git integration fixture's imported execution and review observations. Both intent digests were null and no Reviewer dispatch took place, yet the job was completed. A separate genuine local-operator Git approval then permitted a real commit in the temporary target repository. The Git action's approval was not forged: its reviewed/completed parent premise was accepted without governed execution/review trace.

Impact: non-authoritative imports and claimed review evidence can substitute for executed/reviewed work and propagate into separately approved actions. This violates required trace completeness, Reviewer integration and observation-versus-authority separation. Existing integration fixtures exercise this gap as successful behavior.

Acceptance required: imported observations remain readable but cannot satisfy DONE, required independent review, human completion prerequisites or downstream Git reviewed-work prerequisites. Exercise the complete import -> completion -> separately approved action chain.

### R1-M2 ? Missing controlled-write consumption records do not deny target apply (MAJOR)

`ControlledWriteRuntime.execute` consumes the effect at `runtime/actions/runtime.py:85`. Before applying the staging changes, `:289` calls `require_tool`; `runtime/core/capability_governance.py:105` verifies intent/current claim but does not verify that consumed dispatch/effect pairs remain intact. `FileExecutionStore.verify_decision` checks dispatch consumption but does not require controlled-write effect consumption.

Fresh probe 2 used a real canonical claimed/approved controlled-write request. During adapter staging, it deleted only the effect-controlled_write anchor/witness files in temporary state, keeping the independent journal and authority records intact. Actual result: provider status `succeeded`; target content changed from `before\n` to `r1-staged-change`; effect pair absent. The pre-apply recheck did not fail closed.

Impact: a missing/interrupted/tampered effect trace can coexist with actual target mutation. Existing deletion coverage checks only a second `consume_effect` call; it does not check the ongoing staging -> apply path or result acceptance.

Acceptance required: actual target application and acceptance/restart verification require intact exact dispatch and effect consumption evidence; missing or conflicting evidence denies before apply and cannot be treated as a complete trace.

### R1-M3 ? Single progress-journal rollback refunds a work generation under a new ID (MAJOR)

`FileExecutionStore.begin_decision` (`runtime/storage/execution_store.py:96`) protects the generation by checking and writing only the existing CORE-07 journal. `_intent_work_id` (`:148`) hashes job, attempt and execution approval references. Admission of a new execution ID does not cross-check independently retained prior intents for that generation.

Fresh probe 4 saved the valid journal before intent admission, admitted and dispatched the request, then restored only that journal snapshot. The original paired intent and dispatch records, current canonical job/claim, task authority and approval records were retained. A new execution ID for the exact same job/attempt was admitted and dispatched successfully in a fresh Python process (`rollback_restart_probe.py`). No new human authority or approval was supplied. Original intent pair bytes stayed unchanged.

Impact: stale/replaced journal evidence can reopen a consumed work generation despite surviving independent records. This is a combined journal rollback + identity substitution path, distinct from the covered new-ID attack against an intact journal. The probe requires access to replace one local journal; it does not demonstrate that a confined provider can obtain that access. It does not replace every trusted authority store/policy, the limitation excluded in the implementation documentation.

Acceptance required: restoring one evidence store must not refund consumed work when independent exact-work evidence remains; restart/cross-store admission must detect the rollback and require explicit recovery.

## Coverage assessment

| Area | Assessment |
| --- | --- |
| Capability/profile certification, revocation and READ_ONLY -> SENSITIVE_EXECUTE boundaries | PASS on inspected supported boundaries; certificates are ceilings, not approvals |
| Parent/child tools, capabilities, profile, project, gates, stops and budget ceilings | PASS on inspected paths and existing adversarial cases |
| Blast-radius/reversibility and separate human-approved Git profile transitions | PASS on inspected supported action boundaries |
| Canonical approval actor/scope checks and provider/model/JEV/advice non-authority | Canonical actor/scope checks preserved; overall AUTHORITY FAIL through R1-M1 |
| Policy source provenance and historical schema-3 task authority | Current policy pinning/revocation checks work; overall PROVENANCE FAIL through accepted unproven imports |
| Decision Trace persistence/completeness | FAIL, R1-M1/R1-M2 |
| Replay/crash/replaced/deleted evidence | FAIL, R1-M2/R1-M3; ordinary intact-journal replay and partial-write tests pass |
| Historical persisted-record compatibility | PASS for explicit refusal of unsupported anchors; no migration observed. Observation imports must be fixed under R1-M1 |
| Existing authority/state owners and frozen model | No added approval/budget owner or agent-model mutation found; observation promotion undermines authority semantics |

## Fresh validation

Existing targeted/adversarial suite: 92 tests PASS, exit 0 (`targeted.json`).
New runtime attack probes: four reproduced failures (`adversarial_probes.py`, `adversarial-results.json`). Four acceptance assertions FAIL, exit 1 (`adversarial-checks.json`). The probe runner invokes actual runtime APIs against isolated temporary stores/targets; assertion checks evaluate those recorded outcomes.
Focused/affected GOV-01, Approval, Reviewer, Worker, tool/runtime, budget, retry/continuation and Git integrations: **825 tests PASS**, exit 0 (`focused.json`).
Complete full regression: **1,286 tests PASS**, exit 0 (`full.json`).
Static/schema validation **PASS**: 170 runtime Python AST files, 33 schema JSON/local-reference checks, 17 certificates. `git diff --check` **PASS**. Final source snapshot **PASS**: all 459 non-review files unchanged; HEAD unchanged. New review-file whitespace **PASS**. See `validation.json`.

`source-before.json` pins the actual tracked/untracked non-review files. Source inspection included the diff, certification/catalog schema, JobRuntime/TaskContractStore, ApprovalStore, Worker, execution store, Reviewer runtime/store/delegation, tool/effect guards, Git/remote-action paths and CORE-07 journal/transition coordination. Prior implementation PASS reports were not used as acceptance evidence.

READY FOR OWNER CLOSURE: **NO**. Fix findings in a separately authorized task and obtain a distinct independent reviewer. No fixes were made in this review.

## Complete fresh run fingerprints

| Run | Tests | Seconds | Complete log SHA-256 |
| --- | --- | --- | --- |
| targeted | 92 | 122.4 | `7eaea64457731ba6a775a55dd0117293f07606516700bd6d85cd50266c7e0aa8` |
| focused | 825 | 1020.454 | `148156bd460e6e6f8686f462d726a4e225352ad4cf3fc3f5140dc5630259be70` |
| full | 1286 | 1306.613 | `d6022a519b955a7b067791c8cf655aed2925e75baac00442d891ec16dbb61af8` |

The existing suites passing does not resolve the four reproduced acceptance failures. No live provider/remote forge/deployment validation is claimed. Git probe effects were confined to temporary repositories. The rollback reproduction starts a fresh Python process with unchanged canonical authority.
