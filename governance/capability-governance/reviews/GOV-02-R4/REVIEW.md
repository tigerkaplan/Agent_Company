# GOV-02-R4 final independent review

GOV-02 REVIEW: **FIX**. Canonical skill decision: **FAIL**.
INDEPENDENCE: **PASS** for executor/reviewer role separation. This fresh session
performed no GOV-02, F1 or F2 implementation and made no repairs.
HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.

R1 FINDINGS 1 / 2 / 3: **CLOSED / CLOSED / CLOSED** on their original boundaries.
R3 MAJORS 1 / 2 / 3: **CLOSED / OPEN / CLOSED**. The exact R3 M2 reproduction now
denies, but adjacent Git action-provenance and consumption variants remain open.
FINDINGS: **0 critical / 2 major / 0 minor** on the reviewed scope.

1. **R4-M1 — Git consumption rollback can launder provenance and refund work.**
   A journal-only rollback after consumption makes real commit/push/fake-PR
   effects return success with `effect_performed: false`; a fresh Python process
   accepts the committed trace. A separate restart attack restores consumption
   evidence and removes the effect pair while retaining canonical failure pairs.
   The same approval then creates a real commit (count 1 -> 2); acceptance denies
   only afterward. Original authority/job/approval owners were not replaced.
2. **R4-M2 — Git commit continues after evidence loss during staging.**
   Removing the policy or consumed-effect pair immediately after real Git staging
   still allows the real commit. Later acceptance failure does not prevent that
   second mutation.

Detailed causes, boundaries, exact source locations and required repairs are in
[FINDINGS.md](FINDINGS.md); probe outcomes are in the adjacent JSON/log files.
No implementation finding was repaired during review.

AUTHORITY / CERTIFICATION / PROVENANCE / TRACE / REPLAY / COMPATIBILITY:
**FAIL / PASS / FAIL / FAIL / FAIL / PASS**.
READY FOR OWNER CLOSURE: **NO**. GOV-02 stays OPEN and uncommitted.
ORCH-01 was not begun.

## Coverage and limits

Fresh tests and source inspection verify provider-neutral certification ceilings,
revocation, profile/mode/allocation matching, exact request/result/evidence binding,
parent tools/capabilities/project/scope/gates/budget ceilings, blast/reversibility,
canonical approval actor/scope checks, monotonic GOV-01 review strengthening,
historical recovery refusal and observation non-authority. Imported execution
and review observations cannot complete, dispatch, feed approved Git prerequisites
or restore executable human-resumption authority. Controlled create/modify/delete,
compensation and final return revalidate exact evidence; lost evidence halts later
mutations and does not authorize compensation. Original job-attempt replay and
coherent retained-intent/dispatch rebinding plus journal rollback deny in fresh
processes for canonical and alternate execution roots. One explicit new canonical
human receipt still permits only its bounded work generation.

These repaired original boundaries do not repair the two Git majors above.
Certification and canonical human approvals remain necessary; their continuous
enforcement and action Decision Audit Trace/replay integrity still fail.
GOV-01 task/completion/delegation invariants pass on the inspected/tested paths;
no new approval, budget, journal or authority owner was found.

R1/R2/R3 durable evidence, current F2 validation and the actual tracked/untracked
runtime/schema/policy diff were read. `prior-evidence-audit.json` checks retained
R1/R3/F2 regression logs against their hashes and confirms all 212 F2 source
fingerprints match. R1's validation JSON is a structured check record rather than
a subprocess/log report; its absent log fields are not a claimed log failure.
The three copied R3 probes are byte-identical to their originals. Earlier green
claims do not substitute for this review's fresh runs.

Provider diversity is not established. PATH discovery resolved Codex only;
Claude/Gemini did not resolve, and available tools exposed no eligible distinct
provider execution route. This does not prove no installation exists elsewhere.
`orchestrator/routing/fallback.yaml` requires high-risk escalation when a different
provider is unavailable, and `escalation.yaml` requires reviewer role separation.
Role independence passes; the high-risk provider routing gate remains unsatisfied.
No provider-diverse acceptance is claimed. The reproduced majors independently
require FIX, regardless of that gate.

## Completed fresh validation

| Run | Result | Tests | Exit | Seconds | Complete log SHA-256 |
| --- | --- | --- | --- | --- | --- |
| targeted | PASS | 107 | 0 | 175.69 | `2bbc42485d9405f26048dccc56ee3d1d2482f9bdc28dc9f5052d6cddcdd2086d` |
| adversarial | PASS | 15 | 0 | 96.805 | `09f5addb6148b542b8d10f581920478cceb5745927cade43d3d87da4aea26bf7` |
| r3-adversarial | PASS | 6 | 0 | 33.649 | `a96e27c73359fd7bcc8bb3a7a21d249b0387ac4ac0fb80e9cce9bf075b7ac081` |
| r3-multifile | PASS | probe/check | 0 | 1.681 | `75fb91bebd05980b8e6ab0d064261451010c124f464d34a890c0925f87dcfa84` |
| affected | PASS | 156 | 0 | 392.747 | `d3faa3caafab20b569133b8f66294d264b8c078b1507fac6fe13e27949bbf2ab` |
| focused | PASS | 840 | 0 | 1106.151 | `a363ccbb03c8d295fa0d464a58daa989517f3d6bf037211f61b0b48d6c654036` |
| full | PASS | 1301 | 0 | 1357.646 | `bd59e9317d9817dbe79956cc4336333150c97fd22458c3c5f8898c57d60e40c4` |
| validation | PASS | probe/check | 0 | 0.816 | `8a88e133cbc4083df3d1d1e5a2823fdcd689c94662d16193742b0aa030c3e0d6` |
| diff-check | PASS | probe/check | 0 | 0.079 | `254b635731c6074e3302e4bf9f602d92a33aaa01510c6f1f644fff18bcb0808f` |
| combined | FAIL | 3 | 1 | 23.745 | `1400241a01d8a384cbd23e35277e4da10aea50758801eca6ab3a75c96c461e16` |
| action-confirmation | FAIL | probe/check | 1 | 20.055 | `a3096224b91ef82db45fdedf547b2d7261bfb98e0616375149e57029b1fc1732` |
| replay-confirmation | FAIL | probe/check | 1 | 6.897 | `2e3fe6d66751cd659b5dc6f9ef9358f4ec809536cbab0d57b34c0d394bec8d6a` |
| rollback-confirmation | PASS | probe/check | 0 | 3.231 | `0d6aed82ec2d5d7d533ab1c156d2f981e2e9c8a74b4ca75f7e45bd4e0741a1d4` |
| import-boundaries-corrected | PASS | 2 | 0 | 2.045 | `a552da63c88998d26a35c508c41f239501a6172bd531d9aca029255ceb3edc0d` |
| static-review | PASS | probe/check | 0 | 1.271 | `a9512ebff3d30e930813908b7251ceb620b534b5d182b26823cc20bc83586b3f` |

Targeted, affected, focused and full are completed aggregate runs. No interrupted
suite or isolated rerun substitutes for their results. Adversarial acceptance
is **FAIL**, despite the green F1/F2 and original R3 suites: three new combined
methods have four failed assertions and no probe errors, and the action/replay
confirmation scripts reproduce the two majors. The initial import-boundary
reviewer setup error and its script/log/report are retained and excluded from
PASS; the corrected two-method suite passes. See FINDINGS.md for the correction.

Static/schema validation uses the repository's existing AST/JSON/local-reference
and certificate validators (172 runtime Python files, 33 schemas, 17 certificates),
plus duplicate JSON, catalog coverage, reviewer AST and production-import checks.
No external metaschema validation package was installed or claimed.
Git effects are isolated in temporary repositories and a local bare remote;
PR integration uses the existing fake adapter. No live provider, forge, deployment,
publication, VPS or provider escape was tested or claimed.

## Resume and integrity evidence

The resume preserved all completed tests and the original running validator.
Affected had already passed; focused, full and final validation finished in that
same sequential runner. Process inspection via CIM was denied; `Get-Process`
and the retained PTY session independently confirmed the original live processes.
The first resume-log audit shell command had a quoting error; the final Python
auditor independently validates every completed report/log binding.

All **596 non-R4 files** pinned before review remain byte-identical.

This includes prior review evidence and pre-existing dirty implementation/docs.
HEAD remains exactly the expected commit. `resume-audit.json`, `source-before.json`,
`source-after.json`, `integrity.json` and `resume-log-audit.json` provide exact
fingerprint evidence. `git diff --check` passes if its row above is PASS; existing
LF/CRLF warnings are informational. New reviewer Python/Markdown/JSON files pass
AST and trailing-whitespace checks. All review edits are confined to
`governance/capability-governance/reviews/GOV-02-R4/`.

No implementation file, prior review artifact, canonical project status, repository
history or ORCH-01 file was edited. Fixes and a subsequent acceptance review are
separate work; this review grants no execution, repair, closure or commit approval.
