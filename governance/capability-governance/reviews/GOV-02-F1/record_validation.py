"""Record F1 evidence only after complete passing runs and exact source checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "governance/capability-governance"
OUT = Path(__file__).resolve().parent
manifest = json.loads((OUT / "regression-source.json").read_text())
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == manifest["head"] == "c5de47440973c87023bbd6652aca984262ab17f7"
for name, fingerprint in manifest["source_files"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == fingerprint, name
reports = {}
for kind in ("targeted", "adversarial", "affected", "focused", "full"):
    report_path = BASE / (kind + "-regression.json")
    threshold = (OUT / "regression-source.json").stat().st_mtime
    if kind in {"targeted", "adversarial", "affected"} and "unchanged_stage_source_snapshot" in manifest:
        before = json.loads((OUT / manifest["unchanged_stage_source_snapshot"]).read_text())
        assert before["head"] == manifest["head"]
        assert [n for n in manifest["source_files"] if before["source_files"].get(n) != manifest["source_files"][n]] == ["runtime/tests/test_continuation.py", "runtime/tests/test_retry_policy.py"]
        threshold = manifest["unchanged_stage_source_timestamp"]
    assert report_path.stat().st_mtime >= threshold, kind
    raw = report_path.read_bytes()
    report = json.loads(raw)
    assert report["complete"] and report["passed"] and report["exit_code"] == 0, kind
    assert hashlib.sha256((ROOT / report["log"]).read_bytes()).hexdigest() == report["log_sha256"], kind
    if kind in {"targeted", "adversarial", "affected"}:
        assert "runtime.tests.test_retry_policy" not in report["command"]
        assert "runtime.tests.test_continuation" not in report["command"]
    reports[kind] = report
    (OUT / (kind + ".json")).write_bytes(raw)
static = subprocess.run([sys.executable, "-B", str(BASE / "validate.py")], cwd=ROOT, capture_output=True, text=True)
assert static.returncode == 0, static.stderr
validation = json.loads(static.stdout)
whitespace = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True)
assert whitespace.returncode == 0, whitespace.stdout + whitespace.stderr
result = {"prompt_id": "GOV-02-F1", "status": "PASS", "head": head,
          "findings": {"1": "FIXED", "2": "FIXED", "3": "FIXED"},
          "authority": "PASS", "provenance": "PASS", "trace": "PASS", "replay": "PASS",
          "compatibility": "PASS", "tests": reports, "static_schema": validation,
          "diff_check": "PASS", "source_manifest": "regression-source.json",
          "source_files_verified": len(manifest["source_files"]), "ready_for_fresh_independent_r2": True,
          "gov02_state": "OPEN", "committed": False, "orch01_started": False,
          "independent_review_performed": False}
(OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
(BASE / "validated-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
rows = "\n".join("| " + k + " | PASS, " + str(r["test_count"]) + " tests | " + str(r["elapsed_seconds"]) + " | `" + r["log_sha256"] + "` |" for k, r in reports.items())
text = """# GOV-02-F1 validation evidence

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
""" + rows + """

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

Static/schema validation PASS: """ + str(validation["python_syntax_files"]) + " runtime Python AST files, " + str(validation["schema_files"]) + " schema JSON/local-reference checks, " + str(validation["certificate_count"]) + " certificates." + """
`git diff --check`: PASS. Final source/HEAD verification: PASS, """ + str(len(manifest["source_files"])) + """ files.
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
"""
(BASE / "VALIDATION.md").write_text(text)
print(json.dumps({"status": "PASS", "tests": {k:r["test_count"] for k,r in reports.items()}, "source_files_verified": len(manifest["source_files"])}))
