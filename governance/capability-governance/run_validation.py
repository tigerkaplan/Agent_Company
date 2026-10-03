"""Record complete regression evidence; never infer success from partial logs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
kind = sys.argv[1]
modules = {
 "adversarial": ["test_capability_governance_f1"],
 "affected": ["test_git", "test_remote_git", "test_review", "test_approval", "test_worker"],
 "targeted": ["test_capability_governance_f1", "test_capability_governance", "test_capability_actions", "test_actions"],
 "focused": ["test_capability_governance_f1", "test_capability_governance", "test_capability_actions", "test_task_contract", "test_task_contract_f1", "test_task_contract_f2", "test_review", "test_approval", "test_worker", "test_tool_discovery", "test_providers", "test_runtime", "test_actions", "test_progress", "test_progress_f1", "test_progress_f2", "test_execution_budget", "test_retry_policy", "test_continuation", "test_compute_policy", "test_git", "test_remote_git", "test_context_discovery", "test_external_content", "test_scheduler_loop", "test_retry_repairs"],
}
command = [sys.executable, "-B", "-m", "unittest"]
command += ["discover", "-s", "runtime/tests", "-v"] if kind == "full" else ["runtime.tests." + m for m in modules[kind]] + ["-v"]
if kind == "focused":
 command.append("-f")
log_path = ROOT / ("gov02-" + kind + "-complete.log")
started = time.monotonic()
with log_path.open("w", encoding="utf-8") as log:
 result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
raw = log_path.read_bytes()
match = re.search(rb"Ran (\d+) tests? in", raw)
report = {"command": command, "exit_code": result.returncode,
 "elapsed_seconds": round(time.monotonic()-started, 3),
 "test_count": int(match.group(1)) if match else None,
 "complete": bool(match), "passed": result.returncode == 0 and bool(match),
 "log": log_path.name, "log_sha256": hashlib.sha256(raw).hexdigest()}
(OUT / (kind + "-regression.json")).write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
print(json.dumps(report), flush=True)
sys.exit(result.returncode)
