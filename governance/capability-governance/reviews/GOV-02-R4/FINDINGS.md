# GOV-02-R4 independently reproduced findings

HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`. Review only; GOV-02 remains OPEN.
Critical: 0. Major: 2. Minor: 0 on the reviewed scope.
The complete final test and integrity record belongs in `REVIEW.md` / `result.json`.

## R4-M1: Git consumption rollback is accepted and can refund consumed work (MAJOR)

`runtime/core/capability_actions.py:133` derives whether work was consumed solely
from the current journal. When that observation disappears, `finish` skips
`_verify_consumption` and writes `effect_performed: false`, even when the retained
action-effect pair and the verified Git effect demonstrate consumption.

`combined.py` restores only a pre-consumption journal snapshot after actual Git
staging or after a local-bare-remote push. Commit and push both return success;
their action-result pairs say `effect_performed: false`. Newly constructed
runtimes accept those results. `confirm_actions.py` independently confirms real
commit acceptance in a fresh Python process and the equivalent fake-PR behavior.
The original job/task/approval bytes remain identical; consumption pairs survive.
The subprocess accepts evidence without making another commit (count 2 -> 2).
This is provenance laundering, not a claim of an additional mutation in that
particular acceptance probe.

`confirm_replay.py` demonstrates actual refund of a consumed Git generation.
First, consume the genuine approval and simulate failure of staging. Canonical
`action-failure` pairs persist `effect_may_be_partial: true`, and target HEAD stays
unchanged. Restore the post-policy/pre-consumption journal and remove just the
action-effect pairs, retaining the original policy and immutable failure pairs,
task/job/approval owners, pending change set and unchanged target repository.
A fresh Python process uses the SAME approval, stages and commits successfully
(commit count 1 -> 2). Final acceptance fails on the retained failure trace only
AFTER the new effect. No new human approval was supplied. The surviving failure
pair is byte-identical. Consumption admission ignored its veto evidence.

Evidence: `combined-observations.json`, `action-confirmation-observations.json`,
`replay-confirmation-observations.json`, their complete logs and hash-bound reports.

Required repair: canonical action admission and acceptance must cross-check all
retained consumption/result/failure evidence with the independent observations.
Missing observation cannot mean unconsumed when surviving records prove burned
work. Recovery of an existing effect must not accept a broken original trace,
and admission must veto before another effect. Preserve legitimate recovery of
effects genuinely performed outside this action without granting new authority.

## R4-M2: Git commits after evidence loss between staging and commit (MAJOR)

`runtime/git/runtime.py:266` consumes authority once, then `:269` stages and `:280`
commits without another policy/approval/consumption check. In `combined.py`, a
hook calls the REAL Git add, then deletes only the action-policy pair or only the
action-effect pair. The original runtime proceeds to a REAL commit. Final
acceptance denies, but target HEAD has already changed after evidence loss.

Evidence: two subcases of `test_git_loss_after_staging_denies_subsequent_commit`;
`combined-observations.json` records `commit_created: true`, `success: false`,
the exact Git commands and the later exception. Four assertions fail across the
three combined test methods; there are no probe errors in that suite.

Required repair: revalidate exact current policy, canonical human action authority
and consumed effect evidence immediately before each supported Git mutation,
including the commit after staging. Late result rejection cannot replace a
pre-mutation gate. Lost authority must not authorize automatic compensation.

## Original finding closure

R1 1 / 2 / 3: CLOSED on their original execution/review/controlled-write/job-attempt
boundaries. R3 1 / 3: CLOSED. The exact original R3 2 attack is now denied, but
R3 2 remains OPEN for acceptance because adjacent action-provenance and
consumption rollback variants above still mutate/accept broken traces.

Exact copied R3 probes are byte-identical and now pass. R4 findings do not claim
that a confined provider can reach these trusted local state files; they exercise
evidence loss/rollback within the documented filesystem boundary, without replacing
all authority owners/policy. Git effects use disposable repositories and a local
bare remote; PR effects use the existing fake adapter. The reviewed repository
is never committed, reset, repaired or advanced to ORCH-01.

## Reviewer probe setup correction

The first import-boundary run had one reviewer setup error: a needs-human result
lacked its required human blocker. It also discovered 28 imported GOV-01 test
methods in addition to the two new methods. Its script is preserved as
`import_boundaries_initial.py`, with `import-boundaries.log` / `.json` unchanged.
The corrected script imports the fixture module and constructs a schema-valid
human blocker. Its two-method complete run passes in
`import-boundaries-corrected.log` / `.json`. Only review code changed; no executor
code was repaired. The initial error is not an implementation finding or PASS.
