# GOV-02 validation and closure evidence

Current state on 2026-10-03: GOV-02 CLOSED / READY TO COMMIT; uncommitted.
Independent R5 review and policy reconciliation PASS; all prior findings CLOSED;
0 critical / 0 major / 0 minor. See [R5 review](reviews/GOV-02-R5/REVIEW.md),
[owner closure](CLOSURE.md) and [closure integrity checks](CLOSURE_EVIDENCE.json).
Closure verified all 15 completed R5 stages and their exact source/log bindings:
targeted 114, adversarial 22, affected 163, focused 847 and full 1,308 PASS.
The full result is the retained uninterrupted review run, not a closure-time rerun.
Fresh lightweight syntax/schema/certificate and final integrity checks PASS.
ORCH-01 remains NOT STARTED. The F3 executor record below is historical and intact.

## Historical GOV-02-F3 validation evidence

HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.
GOV-02-F3: PASS. R4 majors 1 / 2: FIXED in executor validation.
R1 findings 1 / 2 / 3 and R3 majors 1 / 2 / 3: PASS in executor validation;
the R4-opened adjacent Git variants are repaired here.
AUTHORITY / PROVENANCE / TRACE / REPLAY / COMPATIBILITY: PASS.
READY FOR FRESH INDEPENDENT R5: YES. GOV-02 remains OPEN and uncommitted;
owner closure awaits fresh independent acceptance. ORCH-01 has not begun.

F3 repairs the two R4 Git findings using the existing canonical approval,
progress-journal, action-policy/effect persistence and Git-runtime owners. An
action is treated as spent when its retained consumption, result or failure
evidence records the attempt, even if the journal is older or incomplete.
Admission and acceptance cross-check the paired records against the independent
journal. Retained failures remain immutable and veto reuse of the same approval.
Verified external effects that genuinely predate this action can still be
reconciled as observations without granting another effect.

Before each Git mutation, the action gate rechecks the current policy, canonical
approved authority, task provenance, original action-policy pair and consumed
effect evidence. Local commit performs this check before staging and again after
staging immediately before commit. Git action approval reads opt into canonical
byte validation through the existing approval store; other approval reads retain
their prior behavior.

The new regressions cover the R4 journal rollback and retained-failure restart
reproductions, actual temporary commit/push/fake-PR effects followed by journal
rollback, and evidence deletion, replacement and non-canonical encodings during
staging. The R4 combined probe passed all three methods. The retained-failure
fresh-process probe denied reuse under the same approval and kept the commit
count at 1. Twelve staging-time variants denied commit while preserving the
unchanged target HEAD. The legacy out-of-action push recovery case also passed.
The copied R4 probes and their observations are executor evidence under
`reviews/GOV-02-F3/`; R1-R4 review artifacts were not edited.

| Run | Completed result | Seconds | Complete log SHA-256 |
| --- | --- | ---: | --- |
| targeted | PASS, 114 tests | 320.981 | `9cac381bdad779dba70a5acbace5af0516da6cba0ea0185170c67c76dbfd2a5f` |
| adversarial | PASS, 22 tests | 241.482 | `31919ab8aabf9573aea2039a26aa06e2d36252c3aca7d90176be7007d6bd4682` |
| R3 adversarial copy | PASS, 6 tests | 36.412 | `3d821e8e873a4995dfaa36a7a4e37d29253bc6e412cecc579a3ec756e8be5910` |
| R3 multi-file copy | PASS | 1.495 | `75fb91bebd05980b8e6ab0d064261451010c124f464d34a890c0925f87dcfa84` |
| R4 combined copy | PASS, 3 tests | 22.532 | `2db9f60b26539b2e35dc68b399fb927fc44892427f160c901b7c6f1f6bdfb7da` |
| R4 retained-failure replay | PASS | 5.202 | `1244aa801a04dd8ea580a40957f25e6ecb7182140251e94ca169321956ff98a1` |
| affected integrations | PASS, 163 tests | 619.573 | `dbbf6634ab9a3c5951ca1d9f4b5670e6beb6006551f412adb013ee68fd1c54cb` |
| focused | PASS, 847 tests | 1512.478 | `85cd3a88f3ae05c9c185b62e6ff02a6e69686622006041758d98b17b1d3ba0af` |
| full discovery | PASS, 1308 tests | 1770.887 | `b761fe41eb42998d712440cda5002d9b365b4565c70ca475b7ed003859c0fa79` |
| schema/reference validation | PASS | 0.540 | `26539145d47c3b3e25e69fd6d52bc70d3ace8c84ebd208cf140b94a2aff08298` |
| static validation | PASS | 0.916 | `5f11729d27b6135df3f8ce23490405b74aafee42cd1cea3975b8ff449fd62375` |
| diff check | PASS | 0.076 | `254b635731c6074e3302e4bf9f602d92a33aaa01510c6f1f644fff18bcb0808f` |

Every suite completed with exit 0 and its full unittest summary. Full discovery
passed all 1,308 tests in one uninterrupted process. Static validation parsed 173
runtime Python files and 33 schemas, checked duplicate JSON fields and local
schema references, verified all 17 certificates and found no production imports
from `runtime.tests`. The repository schema validator also passed. The runner
verified the expected HEAD, runtime/schema/policy source fingerprints and the
unchanged pre-existing R1-R4 review evidence at every completed stage. Detailed
commands, counts, logs and hashes are in `reviews/GOV-02-F3/*.json`.

Git effects used temporary repositories and a local bare remote; PR behavior used
the existing fake adapter. No live forge, provider, deployment, publication or
VPS was used or claimed. No commit was created, and ORCH-01 was not started.
