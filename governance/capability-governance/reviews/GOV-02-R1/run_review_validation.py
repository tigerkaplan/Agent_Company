import sys, subprocess, time, re, json, hashlib
from pathlib import Path
base=Path(__file__).resolve().parent
kind=sys.argv[1]
modules=json.loads((base/'commands.json').read_text())
cmd=[sys.executable,'-B','-m','unittest']
cmd+=['discover','-s','runtime/tests','-v'] if kind=='full' else ['runtime.tests.'+m for m in modules[kind]]+['-v']
log=base/(kind+'.log');start=time.monotonic()
with log.open('w',encoding='utf-8') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
raw=log.read_bytes();match=re.search(rb'Ran (\d+) tests? in',raw)
report={'command':cmd,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,3),'tests':int(match.group(1)) if match else None,'complete':bool(match),'passed':r.returncode==0 and bool(match),'log_sha256':hashlib.sha256(raw).hexdigest()}
(base/(kind+'.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True);sys.exit(r.returncode)
