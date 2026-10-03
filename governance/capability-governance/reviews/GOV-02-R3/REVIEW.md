# GOV-02-R3 independent review

Review in progress. The findings below are reproduced; remaining regression results are pending and this document is not an acceptance sign-off.

HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.
Reviewer role is separate from the GOV-02 implementation and F1 executor: this fresh session performed neither task. No implementation repair, commit, canonical status edit or ORCH-01 work is authorized or performed. R1/R2/F1 evidence is preserved.

Provider diversity is not established. PATH discovery resolved Codex only; Claude and Gemini did not resolve. No callable distinct-provider execution route was observed. This is an independent reviewer session using Codex, not a claim of provider-diverse acceptance. High-risk routing in `orchestrator/routing/fallback.yaml` and `escalation.yaml` still prevents a same-provider fallback from becoming acceptance authority. The actual security failures independently require FIX.

## Reproduced findings

### R3-M1: combined journal rollback and retained-record rebinding permits redispatch (MAJOR)

`runtime/storage/execution_store.py:150` derives retained work identity from mutable intent bytes. Lines 159-163 check surviving dispatch claims against the digest of those same bytes. Lines 166-168 only verify canonical provenance when either retained job identity matches the new request's job.

The independent probe performs a valid first admission and dispatch, then restores the pre-intent progress journal, coherently changes both retained intent job identity fields to a foreign ID, and updates both surviving dispatch records to the new intent digest. It leaves canonical job/claim, task authority, policy and approvals unchanged. A fresh Python process admits another execution ID for the same original job/attempt and dispatches it. Both canonical and alternate execution-store roots reproduce the bypass.

`adversarial-observations.json` records successful redispatch in both cases. `rollback-confirmation-observations.json` independently records actual LocalExecutor results: first and second executions succeeded; job/task authority fingerprints were unchanged; job and attempt were identical; no new approval receipt was supplied.

Journal-only rollback, intent deletion with retained consumption, and foreign intent substitution without dispatch rebinding all deny. The combined attack defeats their composition. It modifies evidence stores rather than replacing every trusted authority store and policy, so the documented excluded total-authority-replacement threat does not explain it away. No claim is made that a confined provider can access these state files.

Required fix: retained evidence must veto admission unless its original provenance and exact work identity are independently validated, including apparently foreign entries. Preserve support for genuinely unrelated historical work without trusting attacker-edited IDs. Add the coherent rebinding + rollback + fresh-process case for both storage roots.

### R3-M2: losing Git action-policy records after admission does not deny mutation or successful acceptance (MAJOR)

`runtime/core/capability_actions.py:61` validates/persists the action-policy pair at construction. `consume` at line 73 and `finish` at line 115 call `_validate_current`, which checks evaluated task policy and canonical approval but does not revalidate the persisted action-policy pair or its intent observation. `fail` does check that pair, but the successful path does not.

The independent probe uses real canonical completed/reviewed work and a genuine local-operator Git approval. Immediately before calling the original `ActionDecision.consume`, it deletes only the two action-policy records. The original consumption, real Git commit and successful final acceptance proceed. Probe result: `denied: false`, `commit_created: true`, no exception. This is confined to an isolated temporary repository.

Required fix: validate intact, exact action-policy provenance at consumption and acceptance, not only constructor entry. Exercise deletion, coherent replacement and observation rollback between admission and mutation, including relevant remote action paths. Do not infer completion from later effect/result records when the original decision trace is missing.

### R3-M3: multi-file controlled apply continues after effect evidence is lost (MAJOR)

`runtime/actions/runtime.py:657-659` verifies tool and effect evidence once before the apply loop. Lines 662-670 perform each create/modify/delete without another authority/effect check. A multi-file operation can therefore continue mutating after its consumed effect trace disappears.

The independent probe stages one new file and a change to the existing file. After the first actual target write, a hook deletes only the two effect-controlled_write records. The original loop then writes the existing file and returns provider status `succeeded`. Actual target write order is `src/new.txt`, then `src/existing.txt`; the second target contains `second-mutation` while the effect pair is missing. `multifile-apply-observations.json` records this result. The confirmation also verifies canonical result acceptance is denied afterward, so this finding concerns actual mutation, not successful DONE or review acceptance.

The F1 checks successfully deny loss before entering `_apply` and before its first target write. They do not enforce evidence validity between successive target mutations. Required fix: verify exact current authority, consumed dispatch and effect evidence at every actual target mutation boundary; define safe handling of already-applied changes if later validation fails. Cover multi-file create/modify/delete and evidence loss after the first effect. The hook simulates local evidence-state loss, not a demonstrated provider escape.

## Original R1 assessment

1. CLOSED on reproduced import boundaries: observations remain readable but cannot dispatch, complete, or feed independently reviewed/approved Git prerequisites.
2. OPEN: pre-apply and first-write checks are repaired, but R3-M3 permits a later target mutation after effect evidence is lost. Combined pre-apply journal/effect/dispatch/intent/authority/approval loss denies and later result acceptance also denies. R3-M2 is a separate Git action trace finding.
3. OPEN: journal-only rollback is repaired, but combined retained-intent and dispatch-record rebinding refunds the generation and enables actual fresh-process redispatch.

## Fresh validation so far

- Targeted: 99 tests PASS, exit 0.
- Independent corrected adversarial: 6 methods / 24 subcases, 3 failed assertions, exit 1, no errors. The failures reproduce R3-M1 and R3-M2.
- Initial adversarial run: 3 failures plus one reviewer probe setup error; preserved in `adversarial.log`. Corrected evidence is `adversarial-corrected.log`; no implementation changes were made.
- Actual fresh-process redispatch confirmation: two successful bypass cases, probe exit 1 as an acceptance failure.
- Multi-file apply confirmation: second target mutation and provider success with missing consumed effect records; later canonical result acceptance denies. Probe exit 1 as an acceptance failure.
- Affected integrations, focused, complete full regression, schema/static checks and diff validation: pending.

Exact commands, logs and their SHA-256 hashes are recorded in adjacent JSON files. `source-before.json` pins tracked and untracked non-R3 files, including prior review evidence. The final integrity comparison is pending.
