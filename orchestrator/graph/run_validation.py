"""Complete ORCH-01 regression evidence; existing unittest runner, no new gates."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
GROUPS = {
    "targeted": ["test_graph", "test_graph_adversarial", "test_graph_integration"],
    "affected": ["test_execution_budget", "test_worker", "test_review", "test_approval",
                 "test_providers", "test_scheduler_loop", "test_runtime", "test_actions",
                 "test_git", "test_remote_git"],
    "focused": ["test_capability_governance", "test_capability_governance_f1",
                "test_capability_governance_f2", "test_capability_governance_f3", "test_capability_actions",
                "test_task_contract", "test_task_contract_f1", "test_task_contract_f2",
                "test_execution_results", "test_continuation", "test_execution_budget",
                "test_retry_policy", "test_retry_repairs", "test_retry_f2a", "test_retry_f3", "test_retry_f4",
                "test_progress", "test_progress_f1", "test_progress_f2", "test_context_discovery",
                "test_context_cache", "test_compute_policy", "test_external_content",
                "test_graph", "test_graph_adversarial", "test_graph_integration"],
}


def main(kind):
    command = [sys.executable, "-B", "-m", "unittest"]
    command += (["discover", "-s", "runtime/tests", "-v"] if kind == "full" else
                ["runtime.tests." + m for m in GROUPS[kind]] + ["-v"])
    started = time.monotonic()
    log_path = OUT / (kind + "-complete.log")
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    raw = log_path.read_bytes()
    summary = re.search(rb"Ran (\d+) tests? in", raw)
    report = {"command": command, "exit_code": result.returncode,
              "elapsed_seconds": round(time.monotonic() - started, 3),
              "test_count": int(summary.group(1)) if summary else None,
              "complete": bool(summary), "passed": result.returncode == 0 and bool(summary),
              "log": log_path.name, "log_sha256": hashlib.sha256(raw).hexdigest()}
    (OUT / (kind + "-regression.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
