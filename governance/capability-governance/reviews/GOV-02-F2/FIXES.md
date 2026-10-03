# GOV-02-F2 scope and repairs

Expected and inspected HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.
`pre-edit.json` records that the old R3 runner had finished, all its regression
and validation reports were complete, and no F2 implementation change existed.
All 43 durable R3 artifacts were read and fingerprinted before editing;
`r3-artifacts-before.json` pins their original bytes. R3 evidence is immutable
for this task. R3's earlier request-time verdict and unfinished prose are
historical artifacts; its subsequently completed machine reports are retained.

Only these three documented R3 majors are repaired. Their source is
`../GOV-02-R3/REVIEW.md`, backed by the following exact reproductions:

The [isolated F2 diff](f2-implementation.diff) contains only three production
file changes and the new test file. `capture_delta.py` reconstructs the original
R3 bytes in memory and verifies their recorded SHA-256 before generating it;
`f2-changed-source.json` pins both revisions. No implementation file is restored
or rewritten by this evidence capture.

| R3 major | Original durable reproduction | Runtime owner and repair |
| --- | --- | --- |
| M1 / R1 finding 3 | `adversarial-observations.json` and `rollback-confirmation-observations.json`: coherent retained intent job-ID plus dispatch-digest rebinding, pre-intent journal rollback, new execution ID, actual successful fresh-process redispatch in canonical and alternate roots | `FileExecutionStore.begin_decision`: every retained intent must have matching exact request identity/digest and intent/work observations in the canonical runtime's journal owner, even if its IDs appear foreign. Surviving dispatch pairs also require their independent consumption observations. |
| M2 / additional Git major | `adversarial-observations.json`: deleting the original action-policy pair immediately before `ActionDecision.consume` still creates a real Git commit and accepts success | `ActionDecision._validate_current`: recheck the exact original action-policy pair and its journal intent observation at consumption and result acceptance, along with the existing policy and canonical human approval checks. This shared owner covers commit, push and pull-request creation. |
| M3 / R1 finding 2 | `multifile-apply-observations.json`: delete the consumed effect pair after `src/new.txt` is written; the loop then writes `src/existing.txt` and reports provider success | `ControlledWriteRuntime._apply`: recheck current tool/dispatch/authority and exact consumed effect evidence before directory creation, each file replacement/deletion, each rollback mutation, and final successful return. |

R1 finding 1 remains CLOSED: imported observations remain readable but cannot
grant execution, completion, review or Git authority. Its F1 tests and the
copied R3 import attacks remain part of validation; those production gates
were not changed by F2.

`runtime/tests/test_capability_governance_f2.py` adds eight methods / 24 cases:
four actual first-execution plus fresh-process replacement probes, one journal
owner substitution probe, four Git admission-loss variants (including policy
replacement plus journal rollback), one real post-commit acceptance-loss and
restart probe, two remote-action loss probes, eight multi-file evidence-loss
variants (including effect replacement plus journal rollback), two deletion /
last-write acceptance probes, and two I/O-failure rollback probes. The existing
F1 suite covers genuinely unrelated historical job removal and explicit human
resumption remains covered by the original governance suite.

The executor also runs copies of the exact R3 adversarial and multi-file probe
scripts in this F2 directory. Their bytes match R3; their relative output paths
write F2 evidence only. They are executor reproductions of independent findings,
not a new independent review.

If evidence is lost after a partial controlled effect, F2 halts further target
and compensation writes. Already-applied bytes remain for explicit recovery;
the runtime does not return success and retained dispatch/effect consumption
does not grant redispatch. Ordinary I/O failure still rolls back when evidence
remains valid. No new approval, journal, persistence or authority owner was added.

Validation uses `run_validation.py` here. Each stage records exact command,
exit code, completed test count, log SHA-256 and a shared source fingerprint.
Successful stages are reused only when their log and source fingerprints match.
An incomplete or failed stage cannot count as passing evidence. F2 remains
executor validation; fresh independent R4 is required before owner closure.
GOV-02 remains OPEN and uncommitted. ORCH-01 is outside this task.
