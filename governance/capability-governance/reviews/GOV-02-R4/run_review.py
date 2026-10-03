"""Fresh review runs, with immutable non-R4 fingerprints and complete logs."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PREFIX = OUT.relative_to(ROOT).as_posix() + "/"

def snapshot():
    names = subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    paths = {n.replace("\\", "/") for n in names}
    # Include ignored durable prior logs, which must also remain untouched.
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "governance/capability-governance").rglob("*") if p.is_file())
    return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(paths)
            if (ROOT/n).is_file() and not n.startswith(PREFIX) and "__pycache__" not in n}

MODULES = {
    "targeted": ["test_capability_governance_f2", "test_capability_governance_f1", "test_capability_governance", "test_capability_actions", "test_actions"],
    "adversarial": ["test_capability_governance_f2", "test_capability_governance_f1"],
    "affected": ["test_git", "test_remote_git", "test_review", "test_approval", "test_worker"],
    "focused": ["test_capability_governance_f2", "test_capability_governance_f1", "test_capability_governance", "test_capability_actions", "test_task_contract", "test_task_contract_f1", "test_task_contract_f2", "test_review", "test_approval", "test_worker", "test_tool_discovery", "test_providers", "test_runtime", "test_actions", "test_progress", "test_progress_f1", "test_progress_f2", "test_execution_budget", "test_retry_policy", "test_continuation", "test_compute_policy", "test_git", "test_remote_git", "test_context_discovery", "test_external_content", "test_scheduler_loop", "test_retry_repairs"],
}
COMMANDS = {k: [sys.executable, "-B", "-m", "unittest", *("runtime.tests."+m for m in v), "-v"] for k,v in MODULES.items()}
COMMANDS.update({
    "r3-adversarial": [sys.executable, "-B", str(OUT/"adversarial.py"), "-v"],
    "r3-multifile": [sys.executable, "-B", str(OUT/"multifile_apply.py")],
    "combined": [sys.executable, "-B", str(OUT/"combined.py"), "-v"],
    "full": [sys.executable, "-B", "-m", "unittest", "discover", "-s", "runtime/tests", "-v"],
    "validation": [sys.executable, "-B", str(ROOT/"governance/capability-governance/validate.py")],
    "diff-check": ["git", "diff", "--check"],
})

def run(kind, before):
    assert snapshot() == before, "Non-R4 source/evidence drift before stage"
    log = OUT/(kind+".log")
    report_path = OUT/(kind+".json")
    assert not log.exists() and not report_path.exists(), "Never overwrite existing run evidence"
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(COMMANDS[kind], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        (OUT/"runner-state.json").write_text(json.dumps(dict(stage=kind, status="RUNNING", runner_pid=os.getpid(), child_pid=process.pid, command=COMMANDS[kind]), indent=2)+"\n")
        code = process.wait()
    raw = log.read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in", raw)
    suite = kind in MODULES or kind in ("r3-adversarial", "combined", "full")
    complete = bool(counts) and bool(re.search(rb"^(OK|FAILED \(.*\))\s*$", raw, re.M)) if suite else True
    report = dict(command=COMMANDS[kind], exit_code=code, elapsed_seconds=round(time.monotonic()-start,3), test_count=int(counts[-1]) if counts else None, complete=complete, passed=code==0 and complete, log=log.name, log_sha256=hashlib.sha256(raw).hexdigest(), source_sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest())
    report_path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(dict(stage=kind,**report)),flush=True)
    assert snapshot() == before, "Non-R4 source/evidence drift during stage"

if __name__ == "__main__":
    path = OUT/"source-before.json"
    before = json.loads(path.read_text()) if path.exists() else snapshot()
    if not path.exists(): path.write_text(json.dumps(before,indent=2)+"\n")
    for stage in sys.argv[1:] or ("targeted","adversarial","r3-adversarial","r3-multifile","affected","focused","full","validation","diff-check"):
        run(stage,before)
    after = snapshot()
    changed = [n for n in sorted(set(before)|set(after)) if before.get(n)!=after.get(n)]
    (OUT/"source-after.json").write_text(json.dumps(after,indent=2)+"\n")
    (OUT/"integrity.json").write_text(json.dumps(dict(unchanged=not changed,changed=changed,files_checked=len(before),head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()),indent=2)+"\n")
    (OUT/"runner-state.json").write_text(json.dumps(dict(status="COMPLETE",stages=sys.argv[1:] or ["targeted","adversarial","r3-adversarial","r3-multifile","affected","focused","full","validation","diff-check"]),indent=2)+"\n")
