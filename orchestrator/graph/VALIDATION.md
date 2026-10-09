# ORCH-01-F2 executor validation

ORCH-01-F2: PASS (implementation executor validation).
R2 MAJOR 1 / 2: FIXED / FIXED.
R1 MAJOR 1 / 2 / 3: CLOSED / CLOSED / CLOSED (executor repair disposition).
GRAPH / STATE / PARALLELISM / AUTHORITY / RECOVERY: PASS.
READY FOR FRESH INDEPENDENT R3: YES.
ORCH-01 remains OPEN and uncommitted. Independent R3 acceptance and owner closure
remain pending; this executor report does not supply either.

Authoritative checkout: `E:\Software\Agent_Company`.
Expected and observed HEAD: `8e1381a278b5f3c92c5eedf7fbfb9c9aa6c7bfb8`.
The durable [R1 review](reviews/ORCH-01-R1/REVIEW.md) and
[R2 review](reviews/ORCH-01-R2/REVIEW.md) remain byte-for-byte unchanged.
R2 independently closed R1 Majors 1 and 2. Its two contention majors are the
bounded F2 repair scope; fresh R3 must independently verify their disposition.

- R1: 1300 files including its manifest; manifest SHA-256 `25891f9f6efcfdbf4089945cb7b6ffa8b5d491eb4dba989e1652d61ece67eac6`.
- R2: 2455 files including its manifest; manifest SHA-256 `1f27427f1c15b9ee93666eb8f2b9ac7e917b3d8684350c6ed3ca426dcfa8d23b`.

Review comparisons are in [reviews-before.json](fixes/ORCH-01-F2/reviews-before.json),
[reviews-after.json](fixes/ORCH-01-F2/reviews-after.json) and
[scope-integrity.json](fixes/ORCH-01-F2/scope-integrity.json).
Historical F1 validation remains under [ORCH-01-F1](fixes/ORCH-01-F1/), including
its earlier validation document retained in F2's `VALIDATION-before.txt`.

## Bounded repairs

1. Failed-source retry/replan catches the canonical claim owner's typed contention
   and leaves the persisted decision/admission boundary pending. Repeated ticks,
   restart and duplicate delivery reuse canonical retry decisions and exact child
   IDs. Claim-lock timeout cannot bypass admission or create another dispatch.
2. The existing budget store distinguishes acquisition timeout from malformed or
   exhausted budget evidence. Reservation, finalization, state and recovery return
   DEFER with `may_begin: false` during contention. Retry raises the same typed
   contention before writing a terminal decision; graph dispatch and recovery
   remain blocked until the owner becomes available. Genuine exhaustion retains
   STOP, and untrusted budget evidence retains fail-closed behavior.

Graph retry admission reserves budget before write-once attempt consumption while
holding the existing retry transaction. A deferred graph admission consumes no
attempt or execution unit and enters no executor. Ordinary retry retains its
existing consumption-before-budget crash boundary; consumed attempts never become
fresh or reexecute through this change.

Explicit graph recovery releases only an unexpired running claim with no budget
reservation, attempt consumption/admission, failure anchor, verified intent,
dispatch consumption, execution-start evidence or immutable result. It holds the
existing claim, progress, retry and budget owners through the lifecycle write.
Generic requeue remains denied. Early and late lease checks leave expired claims
with the existing expiration/retry owner. Historical claim provenance is retained;
recovery does not refund budget or retry history.

Budget admission compares the original Worker claim's owner, claimed timestamp
and lease with freshly validated context and the canonical record under the
budget lock. Queued release and same-worker reclaim cannot authorize a stale
caller. The existing JobRuntime active-claim checks recheck lease and approval
inside the budget lock without repeating full work validation there. Full
authority validation remains before budget locking and at intent/dispatch.
Graph intent admission retains the existing transition lock with a finite
180-second wait; full live authority and lease validation after waiting remains
mandatory. Other graph waits and the executor barrier keep their existing bounds.

Immutable successful results survive budget-finalization contention with their
original execution IDs. Both graph and direct Worker recovery hold lifecycle
completion, fan-in and authorized continuation until canonical accounting can
finish. Recovery then accepts the same results with zero executor reentry.

R1 parent/source gate propagation, configured reviewer ownership, exact approvals,
source ceilings, consumed-dispatch denial and terminal evidence remain intact.
No shadow lock, scheduler, retry, budget, persistence or authority owner was added.
Budget capacity, progress and recovery evidence never grant execution authority.
GOV-01/GOV-02 status is unchanged. Deterministic reviewer fixtures exercise the
real owner pipeline and do not claim independent acceptance.

## Complete frozen-source validation

All 17 unchanged R2 executable recipes passed together; see
[probe-result.json](fixes/ORCH-01-F2/r2-reproductions/probe-result.json) and
[probes.log](fixes/ORCH-01-F2/r2-reproductions/probes.log). Raw content-addressed
state and observations accompany this complete reproduction run.

| Category | Tests | Seconds | Result | Report / complete log |
| --- | ---: | ---: | --- | --- |
| targeted | 59 | 2545.116 | PASS | [targeted.json](fixes/ORCH-01-F2/targeted.json) / [targeted.log](fixes/ORCH-01-F2/targeted.log) |
| adversarial | 19 | 64.043 | PASS | [adversarial.json](fixes/ORCH-01-F2/adversarial.json) / [adversarial.log](fixes/ORCH-01-F2/adversarial.log) |
| graph-integration | 14 | 194.455 | PASS | [graph-integration.json](fixes/ORCH-01-F2/graph-integration.json) / [graph-integration.log](fixes/ORCH-01-F2/graph-integration.log) |
| affected | 717 | 4513.436 | PASS | [affected.json](fixes/ORCH-01-F2/affected.json) / [affected.log](fixes/ORCH-01-F2/affected.log) |
| focused | 798 | 2928.940 | PASS | [focused.json](fixes/ORCH-01-F2/focused.json) / [focused.log](fixes/ORCH-01-F2/focused.log) |
| full | 1401 | 3479.721 | PASS | [full.json](fixes/ORCH-01-F2/full.json) / [full.log](fixes/ORCH-01-F2/full.log) |

Targeted coverage includes exact R2 failures, repeated retry/replan ticks,
contention held across restart, local retry attempt preservation, same-worker
claim renewal, late lease expiry, review/completion gates, pending finalization
before fan-in, and ordinary authorized continuation after accounting resumes.
Genuine exhaustion stays STOP without refunds. Both existing sixteen-worker F1
tests keep their strict unique execution/result counts, original 45-second
executor barrier, accepted completion and zero executor reentry. The F1 result
helper accepts typed budget contention only when a successful immutable result
already exists; missing results or pre-admission DEFER cannot pass that helper.

Affected integrations include budget, retry, continuation, graph, GOV-01/GOV-02,
task-contract and review owners. Focused and full are fresh complete aggregates.
The full result comes from one uninterrupted unittest discovery process with
exit code 0. No isolated rerun replaces a failed aggregate.
Windows suspend-event verification for the full process's start/end window is
recorded in [full-uninterrupted.json](fixes/ORCH-01-F2/full-uninterrupted.json).

Source digest `38e7645b973474277d01a4179fde03058e000e1efb5244fa10d1a52e54b3f597` is identical before and after the final sequence;
see [source-before.json](fixes/ORCH-01-F2/source-before.json) and
[source-after.json](fixes/ORCH-01-F2/source-after.json). The snapshot excludes F2
executor evidence and this validation document. Finalization verifies logs,
unchanged source and preserved reviews, then binds the artifacts in
[result.json](fixes/ORCH-01-F2/result.json) and
[artifact-manifest.json](fixes/ORCH-01-F2/artifact-manifest.json).

Schema references, Python syntax, capability certification/routing and whitespace
are checked by [validation.json](fixes/ORCH-01-F2/validation.json), including
`git diff --check`; its output is retained in
[diff-check.txt](fixes/ORCH-01-F2/diff-check.txt). Scope comparison with R2 permits
only eight repair implementation paths, the narrow F1 result-helper update,
the new F2 regression module, this document and F2 executor evidence.

## Retained diagnostic failures and interruptions

Earlier diagnostics are retained separately and grant no acceptance. The initial
repair-probe PowerShell log reflects a shell stderr wrapper issue. A later probe
aggregate ran across a source edit and failed fingerprint checks; it is rejected.
The expired-claim R2 failure led to early and late canonical lease checks. Runs
interrupted to add finalization/continuation variants are explicitly incomplete.
The initial finalization probe reproduced permanent graph failure and led to
holding lifecycle and downstream work pending budget accounting.

`failed-affected-ordinary-retry-boundary/` retains a complete affected-suite
failure that exposed reordered ordinary retry consumption. Its repair restored
the existing crash boundary, followed by fresh complete categories. The old
full run under `interrupted-full-before-claim-generation-repair/` is incomplete
and rejected: a same-worker reclaim diagnostic exposed stale admission. Its
before/after source comparison and review verification completed successfully;
that does not make its interrupted full test run complete. The first generation
probe used an incorrect lease field name and its errors remain retained.

`failed-r2-system-suspend/` retains a complete failed 17-probe aggregate. Windows
recorded lid-triggered suspend and nearly six hours asleep during competing
restart dispatch; expired claims could not complete that fixture. A temporary
validation-process idle-sleep request now runs only during tests and is released
on exit. It changes no power policy, clocks or leases and respects explicit sleep
and lid closure ([Windows API documentation](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate)).
An earlier reproduction stage also encountered battery-triggered sleep, retained
in `failed-targeted-intent-wait/r2-battery-suspend-events.json`; its complete
recipe outcomes remain recorded with that earlier aggregate.
After the user confirmed keeping the machine plugged in and awake, the required
full test process was separately checked for absence of suspend events.

`failed-r2-parallel-budget-admission/` retains the next complete 17-probe failure:
only ten workers reached the unchanged barrier while redundant full validation
held the budget lock. The correction reuses the canonical active-claim checks
without that duplicate full validation. The four-probe diagnostic then passed,
including stale claim, same-worker renewal, late expiry and the original barrier.
All final reproduction and regression categories above were restarted afterward;
the isolated diagnostic is not aggregate acceptance.

`failed-targeted-intent-wait/` retains a complete green 17-recipe reproduction
and a complete failed targeted aggregate (58 of 59 passed). A no-barrier worker
exhausted the original 120-second intent wait while siblings published canonical
result/lifecycle evidence. Its budget was finalized without a result; that
outcome is not accepted as pending-result recovery. The bounded wait is now
180 seconds with the same fresh authority/lease check and unchanged 45-second
executor barrier. The diagnostic covers no-barrier restart/duplicate delivery,
expired intent waits, finite contention and authorized continuation accounting.
The final complete categories above supersede this failed aggregate.

`interrupted-affected-lid-suspend/` retains a later incomplete affected aggregate
with 330 completed passes and no final unittest summary. Windows recorded another
lid-triggered suspension; the runner then raised FileNotFoundError while writing
its report. HEAD and source/review hashes remained unchanged. The entire affected
aggregate was restarted and its complete passing result is listed above.

`failed-focused-retry-synchronization/` retains a complete 798-test focused
aggregate with two failures and two errors in repetitions 3, 4, 5 and 9 of the
existing direct-delivery stress test. Its unchanged ten-second executor-entry
and completion waits timed out. No implementation, test assertions or wait bounds
were changed in response. The unchanged ten-repetition diagnostic then passed
in 66.414 seconds; it grants no aggregate acceptance. The entire focused suite
was rerun, followed by complete full discovery; their results are listed above.

No commit, MEM-01 work, next phase or owner closure was performed. Fresh independent
R3 remains required.
