"""Read every durable R3 artifact and pin it before F2 changes."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
R3=OUT.parent/'GOV-02-R3'
artifacts={}
for path in sorted(R3.rglob('*')):
    if not path.is_file():continue
    raw=path.read_bytes()
    entry={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    text=raw.decode('utf-8')
    if path.suffix=='.json':
        value=json.loads(text)
        entry['json_type']=type(value).__name__
        if isinstance(value,dict):
            for key in ('exit_code','test_count','passed','unchanged','head','review','validation_complete'):
                if key in value:entry[key]=value[key]
    elif path.suffix=='.py':
        tree=ast.parse(text)
        entry['functions']=[node.name for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    elif path.suffix=='.log':
        entry['completed_tests']=re.findall(r'Ran (\d+) tests? in',text)
        entry['outcomes']=re.findall(r'^(OK|FAILED[^\n]*)$',text,re.M)
    elif path.suffix=='.md':entry['headings']=re.findall(r'^#+ .*$',text,re.M)
    elif path.suffix=='.diff':entry['paths']=re.findall(r'^diff --git (.*)$',text,re.M)
    artifacts[path.relative_to(R3).as_posix()]=entry
(OUT/'r3-artifacts-before.json').write_text(json.dumps(artifacts,indent=2)+'\n')
previous=json.loads((R3/'source-after.json').read_text())
changed=[name for name,h in previous.items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
reports={name:json.loads((R3/(name+'.json')).read_text()) for name in ('targeted','adversarial-corrected','affected','focused','full','validation','diff-check','integrity')}
for name,value in reports.items():
    if 'log' in value:assert hashlib.sha256((R3/value['log']).read_bytes()).hexdigest()==value['log_sha256'],name
result={'r3_artifacts_read':len(artifacts),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'changed_since_r3':changed,'r3_validation':{name:{k:v[k] for k in ('exit_code','test_count','passed','unchanged') if k in v} for name,v in reports.items()},
        'r3_runner_finished':True,'existing_f2_implementation_changes':bool(changed)}
(OUT/'pre-edit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
