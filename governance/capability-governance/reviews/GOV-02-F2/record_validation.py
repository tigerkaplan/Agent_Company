"""Verify completed F2 evidence and update canonical validation, preserving R3."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from run_validation import OUT, ROOT, R3, fingerprints, preserve_r3, digest_snapshot


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


canonical = ROOT / "governance/capability-governance"
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "c5de47440973c87023bbd6652aca984262ab17f7", head
snapshot = json.loads((OUT / "regression-source.json").read_text())
assert snapshot == fingerprints(), "Source drift since final regression"
preserve_r3()
for script in ("adversarial.py", "multifile_apply.py"):
    assert (OUT / script).read_bytes() == (R3 / script).read_bytes(), "Original probe copy changed"
delta = json.loads((OUT / "f2-changed-source.json").read_text())
for name, entry in delta.items():
    assert entry["f2_sha256"] == snapshot[name], name
stages = ("targeted", "adversarial", "r3-adversarial", "r3-multifile", "affected", "focused", "full", "validation", "diff-check")
reports = {}
for kind in stages:
    report = json.loads((OUT / (kind + ".json")).read_text())
    assert report["exit_code"] == 0 and report["complete"] and report["passed"], kind
    assert report["source_sha256"] == digest_snapshot(snapshot), kind
    assert hashlib.sha256((OUT / report["log"]).read_bytes()).hexdigest() == report["log_sha256"], kind
    reports[kind] = report
for kind, count in {"targeted": 107, "adversarial": 15, "r3-adversarial": 6, "affected": 156, "focused": 840, "full": 1301}.items():
    assert reports[kind]["test_count"] == count, (kind, reports[kind])
static = json.loads((OUT / reports["validation"]["log"]).read_text())
assert static == {"python_syntax_files": 172, "schema_files": 33, "certificate_count": 17, "status": "PASS"}
observations = json.loads((OUT / "adversarial-observations.json").read_text())
assert len(observations) == 24
assert all(item.get("denied") is True or item.get("returncode") == 0 for item in observations)
multifile = json.loads((OUT / "multifile-apply-observations.json").read_text())
assert multifile["denied"] is True and multifile["provider_status"] is None
assert len(multifile["target_write_order"]) == 1
assert multifile["existing_target_contents"] == "before\n"

# Previous source manifest also pins earlier review files and unrelated dirt.
before = json.loads((R3 / "source-after.json").read_text())
changed = [name for name, old_hash in before.items()
           if not (ROOT / name).is_file() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != old_hash]
implementation = {"runtime/actions/runtime.py", "runtime/core/capability_actions.py", "runtime/storage/execution_store.py"}
evidence = {"governance/capability-governance/" + name for name in (
    "README.md", "VALIDATION.md", "validated-source.json", "targeted-regression.json", "adversarial-regression.json",
    "affected-regression.json", "focused-regression.json", "full-regression.json")}
assert set(changed) <= implementation | evidence, changed
assert implementation <= set(changed), changed

# Preserve canonical F1 evidence verbatim before replacing current aliases.
saved = {}
for name in ("README.md", "VALIDATION.md", "validated-source.json", "targeted-regression.json", "adversarial-regression.json", "affected-regression.json", "focused-regression.json", "full-regression.json"):
    target = OUT / ("pre-f2-" + name)
    if not target.exists(): shutil.copyfile(canonical / name, target)
    saved[name] = hashlib.sha256(target.read_bytes()).hexdigest()
write_json(OUT / "pre-f2-canonical-evidence.json", saved)
for kind in ("targeted", "adversarial", "affected", "focused", "full"):
    report = dict(reports[kind])
    report["log"] = (OUT / report["log"]).relative_to(ROOT).as_posix()
    report["phase"] = "GOV-02-F2"
    write_json(canonical / (kind + "-regression.json"), report)
write_json(canonical / "validated-source.json", snapshot)

rows = ["| Run | Completed result | Seconds | Complete log SHA-256 |", "| --- | --- | --- | --- |"]
for kind in stages:
    report = reports[kind]
    result = "PASS" + (", " + str(report["test_count"]) + " tests" if report["test_count"] is not None else "")
    rows.append(f"| {kind} | {result} | {report['elapsed_seconds']} | `{report['log_sha256']}` |")
text = """# GOV-02-F2 validation evidence

HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.
GOV-02-F2: PASS. R3 majors M1 / M2 / M3: FIXED in executor validation.
R1 findings 1 / 2 / 3: CLOSED in executor validation; finding 1 was preserved.
AUTHORITY / PROVENANCE / TRACE / REPLAY / COMPATIBILITY: PASS.
READY FOR FRESH INDEPENDENT R4: YES. GOV-02 remains OPEN and uncommitted;
owner closure is pending fresh independent acceptance. ORCH-01 has not begun.

The repair scope is exactly the three majors documented by R3. See
[F2 scope, reproductions and repairs](reviews/GOV-02-F2/FIXES.md) and the unchanged
[independent R3 findings](reviews/GOV-02-R3/REVIEW.md). R3's prose and request-time
verdict predate its completed runner; F2's `pre-edit.json` records the completed
R3 machine results without rewriting any of its 43 artifacts.

""" + "\n".join(rows) + """

Every stage finished with exit 0. All test suites have their completed unittest
summary and OK result; no interrupted run or isolated rerun substitutes for a
complete full regression. The full run passed all 1,301 tests in one process.
The 15-method F1/F2 adversarial run includes the 24 new F2 cases, and the copied
R3 adversarial script passed all six methods / 24 original subcases. Its copied
multi-file probe now stops after the first write and does not return provider
success. R3 originals remain byte-identical. Copies are executor reproductions.

Commands, elapsed times, exit codes, log names and SHA-256 values are in
`reviews/GOV-02-F2/*.json`. Canonical `*-regression.json` aliases point to the F2
complete logs. `validated-source.json` and F2 `regression-source.json` pin the
same final runtime/schema/policy/authority source bytes. Static validation passed
172 Python AST files, 33 schema/local-reference checks and 17 certificates.
`git diff --check` passed. The recorder rechecks HEAD, all source fingerprints,
every completed log hash, exact counts, R3 preservation and the allowed change
scope. Previous canonical F1 validation is preserved as F2 `pre-f2-*` files;
earlier R1/R2/F1 evidence and unrelated dirty implementation are preserved.

M1 now independently validates all retained intent and consumption observations
against the canonical journal owner before trusting an apparently foreign work
identity. The exact R3 attack and its fully rebound request-digest variant both
deny actual replacement execution in fresh Python processes for canonical and
alternate execution roots. Unrelated historical job removal and one-generation
explicit human resumption still pass.

M2 rechecks the exact original Git action-policy pair and journal observation at
consumption and successful acceptance. Deletion, coherent replacement, journal
rollback and combined replacement/rollback deny staging and commit. Push and PR
creation also deny before their effects. A policy loss after a real commit denies
successful acceptance and restart reconciliation without refunding consumption.

M3 rechecks canonical task/tool/dispatch/approval and consumed effect evidence
before each target mutation, rollback mutation and final return. Evidence loss
after one target write prevents the second write and later deletion. Already
applied effects remain for explicit recovery when authority/evidence is lost;
unapproved compensation is not attempted. Ordinary I/O failure with valid evidence
still rolls back. Retained dispatch cannot be reused. Imported observations
continue to grant no execution/completion/review/Git authority (R1 finding 1).

This is executor validation, not independent R4 acceptance or provider-diverse
review. Git effects use isolated temporary repositories and a local bare remote;
PR integration uses the existing fake adapter. No live provider, external forge,
deployment, publication or VPS validation is claimed. Existing GOV-01, approval,
review, execution persistence and CORE-07 journal owners remain canonical. No
parallel persistence/authority owner, automatic migration or authority widening
was introduced. No commit or ORCH-01 work was performed.

The initial diagnostic logged eight tests OK, but PowerShell stderr redirection
returned a shell status of 1; it is retained as diagnostic evidence only and is
not counted as a passing final run. The two subsequent combined subcases were
included in every final targeted/adversarial/focused/full suite.
"""
(canonical / "VALIDATION.md").write_text(text, encoding="utf-8")
write_json(OUT / "result.json", {"head": head, "GOV-02-F2": "PASS", "R3_majors": {"1": "FIXED", "2": "FIXED", "3": "FIXED"},
    "R1_findings": {"1": "CLOSED", "2": "CLOSED", "3": "CLOSED"},
    "authority": "PASS", "provenance": "PASS", "trace": "PASS", "replay": "PASS", "compatibility": "PASS",
    "tests": reports, "static": static, "ready_for_fresh_independent_R4": True, "GOV-02": "OPEN",
    "R3_artifacts_preserved": 43, "source_files": len(snapshot), "source_sha256": digest_snapshot(snapshot),
    "implementation_changed_since_R3": sorted(implementation), "no_commit": True, "ORCH-01_started": False,
    "independent_acceptance": False})
preserve_r3()
assert fingerprints() == snapshot
print(json.dumps({"GOV-02-F2": "PASS", "R3_preserved": True, "source_files": len(snapshot), "ready_for_R4": True}))
