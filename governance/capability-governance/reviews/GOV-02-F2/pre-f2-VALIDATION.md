# GOV-02-F1 validation evidence

HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.
GOV-02-F1: PASS. Findings 1, 2 and 3: FIXED.
AUTHORITY / PROVENANCE / TRACE / REPLAY / COMPATIBILITY: PASS.
GOV-02 remains OPEN and uncommitted. ORCH-01 has not begun.
READY FOR FRESH INDEPENDENT R2: YES. Independent review has not been performed.

GOV-02-R1 found three major gaps despite its passing original regression.
Its unchanged review artifacts remain in `reviews/GOV-02-R1/`; that review was
not independent acceptance. This F1 task repairs only those reproduced findings.

| Run | Actual result | Seconds | SHA-256 of complete log |
| --- | --- | --- | --- |
| targeted | PASS, 99 tests | 103.532 | `0b59ff4045bdd965199eec3c36b5c3251c6dd89105d26276c851a6690188abe2` |
| adversarial | PASS, 7 tests | 32.202 | `b7e0e929bf04c907e5c09bf931aadc794c01e69beb67f25ade9b0524427bf46e` |
| affected | PASS, 156 tests | 357.023 | `36a39252f913f7e1b03af1b86f84a4864e8f5bc2c93971aed689ddc76879b64a` |
| focused | PASS, 832 tests | 990.657 | `02158638215a64049ede65a7f23468d86f3a06061dfe4af96520aec29a0972fa` |
| full | PASS, 1293 tests | 1249.995 | `440fae51df19e65a46d8768eda772d6d65e02f661ba9789bda9ec3ab0eae1595` |

Each run completed with exit 0. Machine command/results are the canonical
`*-regression.json` reports, also copied to `reviews/GOV-02-F1/*.json`.
Complete logs are local ignored artifacts; the reports retain their names and
fingerprints. The complete full regression ran after targeted, adversarial,
affected integrations and focused regression passed. Two recovery/review
fixtures were migrated after the first three final stages; their covered tests,
runtime, schemas and policy remained byte-identical. Both source snapshots are
preserved (`before-retry-fixture-source.json`, `regression-source.json`) and the
recorder verifies that exact two-file test-only difference. Focused/full runs
use the final fixtures and source snapshot.

Static/schema validation PASS: 171 runtime Python AST files, 33 schema JSON/local-reference checks, 17 certificates.
`git diff --check`: PASS. Final source/HEAD verification: PASS, 208 files.
`validated-source.json` and `reviews/GOV-02-F1/regression-source.json` pin the
actual regression source. `reviews/GOV-02-F1/result.json` records final status.
Reproduce final checks with `python -B governance/capability-governance/reviews/GOV-02-F1/record_validation.py`.

## Findings and adversarial evidence

1. Imported observations remain readable, but null/unproven intents cannot
   satisfy completion, required review verification, human-boundary restoration
   or Git reviewed-work prerequisites. The imported execution/review plus real
   separately approved Git variants leave the temporary repository HEAD unchanged.
2. Final controlled-write apply revalidates task/tool authority and exact consumed
   dispatch/effect pairs after target preflight and before target mutation.
   Deleted, replaced, tampered and non-canonical pairs, including combined pair
   damage and deletion after the outer check, deny apply and leave target bytes
   unchanged. Successful result/restart acceptance also requires the effect pair.
3. Existing canonical execution persistence and CORE-07 transition coordination
   cross-check retained intent/dispatch/effect evidence before intent admission.
   Alternate artifact roots retain the same intent in the canonical execution
   owner. Journal rollback plus a new ID, alternate root, one/both lost intent
   files or tampered retained identity is denied in fresh Python processes.
   Existing explicit human execution resumption still permits only one generation.

Seven adversarial test methods in `runtime/tests/test_capability_governance_f1.py`
exercise these attacks and combined variants. GOV-01, certification, historical
observation readability, unsupported-authority refusal and existing fail-closed
regressions pass. No authority, approval or budget owner was added.

## Earlier diagnostics and limits

Earlier targeted diagnostics exposed obsolete observation-based Git/verifier
fixtures and assertion text; the fixtures now use canonical dispatch evidence.
An earlier affected run completed 156 tests with four approval-fixture errors;
its report and log are preserved under `reviews/GOV-02-F1/affected-before-fixture-repair.*`.
Those positive completion/recovery fixtures were migrated to canonical execution
and Reviewer dispatch, without weakening production authority checks. An 83-test
repair probe reported OK before the final complete validation sequence.
A focused run was interrupted after four GOV-01 subtest failures exposed an
unrelated removed-job provenance veto; the check now revalidates retained
provenance for the candidate job. Same-work vetoes remain fail closed. Its
incomplete log/report are preserved as `focused-interrupted.*` and are not
passing evidence. The added independent-job regression preserves that behavior.
A targeted restart during this owner-scope refinement is retained separately as
`targeted-interrupted.*`; it is also incomplete and not passing evidence.
A second focused run was interrupted at an obsolete imported-result retry
recovery fixture. Its incomplete report/log are preserved as
`focused-retry-fixture-interrupted.*`; the repaired single-case probe passed.
A standalone continuation Reviewer fixture also needed its canonical review
context. Its interrupted evidence is retained as `focused-review-fixture-interrupted.*`
and its single-case repair probe passed. Only those two fixtures changed after
the already passing targeted, adversarial and affected stages; focused/full
were then rerun. Their production and covered-test bytes remained unchanged.
Pre-F1 canonical evidence is preserved as `reviews/GOV-02-F1/pre-f1-*`.

No live provider, external forge, publication, deployment or VPS validation is
claimed. Git effects use temporary local repositories and a local bare remote.
Tests and this F1 report are executor validation, not independent R2 acceptance.
Wholesale replacement of all trusted canonical authority/evidence stores is
outside the supported threat boundary; individual evidence loss/tampering and
single-journal rollback are fail closed. No commit or ORCH-01 work was performed.
