"""F3 sequential complete validation with resumable, hash-bound stage reports."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def fingerprints():
    paths = set((ROOT / "runtime").rglob("*.py")) | set((ROOT / "schemas").glob("*.json"))
    paths.update(ROOT / name for name in (
        "CONSTITUTION.md", "AGENTS.md", "INTENT.md", "orchestrator/routing/capabilities.yaml",
        "orchestrator/routing/fallback.yaml", "orchestrator/routing/escalation.yaml",
        "governance/capability-governance/certifications.json"))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def preserve_prior():
    expected = json.loads((OUT / "pre-edit.json").read_text())
    allowed = {"runtime/core/capability_actions.py", "runtime/git/runtime.py",
               "runtime/git/remote_runtime.py", "runtime/approvals/store.py",
               "governance/capability-governance/VALIDATION.md"}
    mismatches = [name for name, sha in expected.items()
                  if name not in allowed and (not (ROOT/name).is_file()
                  or hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha)]
    assert not mismatches, "Prior evidence/unrelated source changed: " + str(mismatches)


modules = {
    "targeted": ["test_capability_governance_f3", "test_capability_governance_f2", "test_capability_governance_f1", "test_capability_governance", "test_capability_actions", "test_actions"],
    "adversarial": ["test_capability_governance_f3", "test_capability_governance_f2", "test_capability_governance_f1"],
    "affected": ["test_capability_governance_f3", "test_git", "test_remote_git", "test_review", "test_approval", "test_worker"],
    "focused": ["test_capability_governance_f3", "test_capability_governance_f2", "test_capability_governance_f1", "test_capability_governance", "test_capability_actions", "test_task_contract", "test_task_contract_f1", "test_task_contract_f2", "test_review", "test_approval", "test_worker", "test_tool_discovery", "test_providers", "test_runtime", "test_actions", "test_progress", "test_progress_f1", "test_progress_f2", "test_execution_budget", "test_retry_policy", "test_continuation", "test_compute_policy", "test_git", "test_remote_git", "test_context_discovery", "test_external_content", "test_scheduler_loop", "test_retry_repairs"],
}
commands = {kind: [sys.executable, "-B", "-m", "unittest", *("runtime.tests." + m for m in items), "-v"]
            for kind, items in modules.items()}
commands.update({
    "r3-adversarial": [sys.executable, "-B", str(OUT / "adversarial.py"), "-v"],
    "r3-multifile": [sys.executable, "-B", str(OUT / "multifile_apply.py")],
    "r4-combined": [sys.executable, "-B", str(OUT / "combined.py"), "-v"],
    "r4-replay": [sys.executable, "-B", str(OUT / "confirm_replay.py")],
    "full": [sys.executable, "-B", "-m", "unittest", "discover", "-s", "runtime/tests", "-v"],
    "validation": [sys.executable, "-B", str(ROOT / "governance/capability-governance/validate.py")],
    "static": [sys.executable, "-B", str(OUT / "static_validation.py")],
    "diff-check": ["git", "diff", "--check"],
})


def run(kind, snapshot):
    preserve_prior()
    assert fingerprints() == snapshot, "Regression source changed"
    report_path = OUT / (kind + ".json")
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get("passed"):
            assert previous["source_sha256"] == digest_snapshot(snapshot)
            assert hashlib.sha256((OUT / previous["log"]).read_bytes()).hexdigest() == previous["log_sha256"]
            print("Already complete: " + kind, flush=True)
            return
        raise RuntimeError("Preserve unsuccessful evidence under another name before rerunning " + kind)
    log_path = OUT / (kind + ".log")
    if log_path.exists():
        raise RuntimeError("Existing incomplete log must be assessed/preserved before rerunning " + kind)
    command = commands[kind]
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        (OUT / "runner-state.json").write_text(json.dumps({"stage": kind, "status": "RUNNING", "runner_pid": __import__("os").getpid(), "child_pid": process.pid, "command": command}, indent=2) + "\n")
        code = process.wait()
    raw = log_path.read_bytes()
    matches = re.findall(rb"Ran (\d+) tests? in", raw)
    suite = kind in modules or kind in ("full", "r3-adversarial", "r4-combined")
    complete = bool(matches) and bool(re.search(rb"^OK\s*$", raw, re.M)) if suite else True
    report = {"command": command, "exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 3),
        "test_count": int(matches[-1]) if matches else None, "complete": complete,
        "passed": code == 0 and complete, "log": log_path.name,
        "log_sha256": hashlib.sha256(raw).hexdigest(), "source_sha256": digest_snapshot(snapshot)}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"stage": kind, **report}), flush=True)
    assert fingerprints() == snapshot, "Source changed during stage"
    preserve_prior()
    if not report["passed"]:
        raise RuntimeError("Failed/incomplete stage: " + kind)


def digest_snapshot(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


if __name__ == "__main__":
    snapshot_path = OUT / "regression-source.json"
    snapshot = json.loads(snapshot_path.read_text()) if snapshot_path.exists() else fingerprints()
    if not snapshot_path.exists(): snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    for kind in sys.argv[1:] or ("targeted", "adversarial", "r3-adversarial", "r3-multifile", "affected", "focused", "full", "validation", "static", "diff-check"):
        run(kind, snapshot)
    preserve_prior()
    (OUT / "runner-state.json").write_text(json.dumps({"status": "COMPLETE", "stages": sys.argv[1:] or list(commands)}, indent=2) + "\n")
