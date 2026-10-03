"""Fresh R3 evidence runner; all durable outputs stay in R3."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def snapshot():
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(set(names))
            if (ROOT/n).is_file() and not n.startswith('governance/capability-governance/reviews/GOV-02-R3/')}

def record(name, command):
    start = time.monotonic()
    log = OUT/(name+'.log')
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    raw = log.read_bytes()
    match = re.search(rb'Ran (\d+) tests? in', raw)
    value = dict(command=command, exit_code=result.returncode,
                 elapsed_seconds=round(time.monotonic()-start, 3),
                 test_count=int(match.group(1)) if match else None,
                 passed=result.returncode == 0, log=log.name,
                 log_sha256=hashlib.sha256(raw).hexdigest())
    (OUT/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(dict(stage=name, **value)), flush=True)
    return value

if __name__ == '__main__':
    before = snapshot()
    (OUT/'source-before.json').write_text(json.dumps(before, indent=2)+'\n')
    modules = {
        'targeted': ['test_capability_governance_f1', 'test_capability_governance', 'test_capability_actions', 'test_actions'],
        'adversarial': [],
        'affected': ['test_git', 'test_remote_git', 'test_review', 'test_approval', 'test_worker'],
        'focused': ['test_capability_governance_f1', 'test_capability_governance', 'test_capability_actions', 'test_task_contract', 'test_task_contract_f1', 'test_task_contract_f2', 'test_review', 'test_approval', 'test_worker', 'test_tool_discovery', 'test_providers', 'test_runtime', 'test_actions', 'test_progress', 'test_progress_f1', 'test_progress_f2', 'test_execution_budget', 'test_retry_policy', 'test_continuation', 'test_compute_policy', 'test_git', 'test_remote_git', 'test_context_discovery', 'test_external_content', 'test_scheduler_loop', 'test_retry_repairs'],
    }
    for name, selected in modules.items():
        if name == 'adversarial':
            command = [sys.executable, '-B', str(OUT/'adversarial.py'), '-v']
        else:
            command = [sys.executable, '-B', '-m', 'unittest', *['runtime.tests.'+m for m in selected], '-v']
        record(name, command)
    record('full', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'runtime/tests', '-v'])
    record('validation', [sys.executable, '-B', str(ROOT/'governance/capability-governance/validate.py')])
    record('diff-check', ['git', 'diff', '--check'])
    after = snapshot()
    changed = sorted(n for n in set(before)|set(after) if before.get(n) != after.get(n))
    (OUT/'source-after.json').write_text(json.dumps(after, indent=2)+'\n')
    (OUT/'integrity.json').write_text(json.dumps(dict(unchanged=not changed, changed=changed,
        files_checked=len(before), head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()), indent=2)+'\n')
    print(json.dumps(dict(stage='integrity', changed=changed)), flush=True)
