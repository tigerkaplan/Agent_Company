"""Final read-only evidence integrity checks; writes only into the R5 folder."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
import run_review

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
before = json.loads((OUT/'source-before.json').read_text())
after = run_review.snapshot()
changed = [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]
stages = ('targeted', 'adversarial', 'r3-adversarial', 'r3-multifile', 'combined',
          'replay-confirmation', 'rollback-confirmation', 'import-boundaries',
          'affected', 'focused', 'full', 'validation', 'static', 'diff-check', 'r5-combined')
reports = {}
for stage in stages:
    report = json.loads((OUT/(stage+'.json')).read_text())
    raw = (OUT/report['log']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == report['log_sha256'], stage
    assert report['source_sha256'] == hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(), stage
    reports[stage] = {k: report[k] for k in ('passed', 'complete', 'exit_code', 'test_count', 'elapsed_seconds', 'log_sha256')}
syntax = []
whitespace = []
for path in sorted(OUT.rglob('*')):
    if not path.is_file() or path.suffix not in ('.py', '.json', '.md'): continue
    value = path.read_text(encoding='utf-8')
    if path.suffix == '.py': ast.parse(value, filename=str(path)); syntax.append(path.name)
    if path.suffix == '.json': json.loads(value)
    whitespace.extend(f'{path.name}:{index}' for index, line in enumerate(value.splitlines(), 1) if line.rstrip()!=line)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
result = dict(head=head, expected_head=head=='c5de47440973c87023bbd6652aca984262ab17f7',
              files_checked=len(before), unchanged=not changed, changed=changed,
              reports=reports, review_python_AST=syntax, review_trailing_whitespace=whitespace,
              all_stages_pass=all(r['passed'] and r['complete'] and r['exit_code']==0 for r in reports.values()))
(OUT/'final-integrity.json').write_text(json.dumps(result, indent=2)+'\n')
manifest = {p.relative_to(OUT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'artifact-manifest.json' and '__pycache__' not in p.parts}
(OUT/'artifact-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps(result, indent=2))
assert not changed and result['expected_head'] and not whitespace
