"""Read prior validation and bind its claims to retained source/log bytes."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
BASE=OUT.parents[1]
result={}
for name in ('GOV-02-R1','GOV-02-R3','GOV-02-F2'):
    directory=OUT.parent/name
    stages={}
    for stage in ('targeted','adversarial','adversarial-corrected','affected','focused','full','validation','diff-check'):
        path=directory/(stage+'.json')
        if not path.exists():continue
        report=json.loads(path.read_text())
        log=directory/report.get('log',stage+'.log')
        stages[stage]=dict(exit_code=report.get('exit_code'),passed=report.get('passed'),
            complete=report.get('complete'),test_count=report.get('test_count'),
            log_exists=log.is_file(),log_matches=log.is_file() and hashlib.sha256(log.read_bytes()).hexdigest()==report.get('log_sha256'))
    result[name]=stages
source=json.loads((BASE/'validated-source.json').read_text())
result['current_validated_source']=dict(files=len(source),mismatches=[n for n,h in source.items() if not (ROOT/n).is_file() or hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h])
result['copied_exact_probes']={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest()==hashlib.sha256((OUT.parent/'GOV-02-R3'/n).read_bytes()).hexdigest()
    for n in ('adversarial.py','multifile_apply.py','confirm_rollback.py')}
(OUT/'prior-evidence-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
