"""Bind prior durable reports and copied probes to actual retained bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
result = {}
for name in ('GOV-02-R1', 'GOV-02-R2', 'GOV-02-R3', 'GOV-02-R4', 'GOV-02-F3'):
    directory = OUT.parent / name
    records = {}
    for stage in ('targeted', 'adversarial', 'adversarial-corrected', 'affected', 'focused', 'full', 'validation', 'static', 'combined', 'r4-combined', 'r4-replay', 'diff-check'):
        path = directory / (stage + '.json')
        if not path.is_file(): continue
        value = json.loads(path.read_text())
        expected = value.get('log_sha256')
        if expected is None:
            records[stage] = {'format': 'structured evidence without log binding'}
            continue
        log = directory / value.get('log', stage + '.log')
        matches = log.is_file() and hashlib.sha256(log.read_bytes()).hexdigest() == expected
        records[stage] = dict(log_matches=matches, exit_code=value.get('exit_code'),
            tests=value.get('test_count'), passed=value.get('passed'), complete=value.get('complete'))
        assert matches, str(log)
    result[name] = records
source = json.loads((OUT.parent / 'GOV-02-F3' / 'regression-source.json').read_text())
mismatches = [n for n, h in source.items() if not (ROOT/n).is_file() or hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != h]
result['F3_current_source'] = dict(files=len(source), mismatches=mismatches)
assert not mismatches
copied = ('adversarial.py', 'multifile_apply.py', 'combined.py', 'confirm_replay.py', 'confirm_rollback.py', 'import_boundaries.py', 'confirm_actions.py')
result['R4_copied_probe_hashes'] = {}
for name in copied:
    original = (OUT.parent/'GOV-02-R4'/name).read_bytes()
    assert original == (OUT/name).read_bytes(), name
    result['R4_copied_probe_hashes'][name] = hashlib.sha256(original).hexdigest()
result['provider_route'] = {'separate_reviewer_session': True,
    'implementation_or_F1_F2_F3_performed_in_this_session': False,
    'path_discovery': 'Codex only; Claude and Gemini did not resolve',
    'callable_distinct_provider_tool': False,
    'role_independence': 'PASS', 'provider_diversity': 'NOT ESTABLISHED',
    'high_risk_provider_gate': 'UNSATISFIED',
    'policy': ['orchestrator/routing/fallback.yaml', 'orchestrator/routing/escalation.yaml']}
(OUT/'prior-evidence-audit.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
