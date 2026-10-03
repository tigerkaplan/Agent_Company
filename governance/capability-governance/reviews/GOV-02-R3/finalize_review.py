"""Finalize only after every required fresh run and source comparison exists."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
def read(name):return json.loads((OUT/(name+'.json')).read_text())
runs={name:read(name) for name in ('targeted','adversarial-corrected','multifile-apply-confirmed','affected','focused','full','validation','diff-check')}
integrity=read('integrity')
for name in ('targeted','affected','focused','full'):
    assert runs[name]['test_count'] is not None, name
for name in ('targeted','affected','focused','full','validation','diff-check'):
    assert runs[name]['passed'], f'Unexpected regression failure needs explicit assessment: {name}'
assert integrity['unchanged'],integrity
for name,result in runs.items():
    assert hashlib.sha256((OUT/result['log']).read_bytes()).hexdigest()==result['log_sha256'],name
for path in OUT.glob('*.py'):ast.parse(path.read_text(),filename=str(path))
actual_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert actual_head==integrity['head']=='c5de47440973c87023bbd6652aca984262ab17f7'
final_source=read('source-after')
changes=[name for name,expected in final_source.items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected]
assert not changes,changes
observations=read('adversarial-observations')
failed_subcases=[v for v in observations if v.get('returncode')==3 or v.get('case')=='git-action-policy-loss-at-consume' and not v['denied']]
assert len(failed_subcases)==3
result={
    'prompt_id':'GOV-02-R3-INDEPENDENT','decision':'FAIL','requested_review_result':'FIX',
    'head':actual_head,'independence':'PASS',
    'independence_basis':'Fresh reviewer session; did not execute GOV-02 implementation or F1',
    'provider_diverse_review':False,'provider_routing_limit':'No distinct-provider callable execution route observed; no high-risk provider-diverse acceptance sign-off',
    'r1_findings':{'1':'CLOSED','2':'OPEN','3':'OPEN'},
    'findings':{'critical':0,'major':3,'minor':0},
    'authority':'FAIL','certification':'PASS','provenance':'FAIL','trace':'FAIL','replay':'FAIL','compatibility':'PASS',
    'tests':runs,'adversarial_methods':6,'adversarial_subcases':len(observations),'failed_adversarial_subcases':len(failed_subcases),
    'additional_multifile_probe':'FAIL; later target mutation occurs despite lost effect evidence; result acceptance denies',
    'source_integrity':integrity,'ready_for_owner_closure':False,'committed':False,'orch01_started':False,
}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
report=(OUT/'REVIEW.md').read_text()
backup=OUT/'REVIEW-in-progress.md'
if not backup.exists():backup.write_text(report)
report=report.replace('Review in progress. The findings below are reproduced; remaining regression results are pending and this document is not an acceptance sign-off.',
    'GOV-02 REVIEW: **FIX**. Canonical review decision: **FAIL**.\n\nINDEPENDENCE: **PASS** for reviewer/executor separation; provider diversity is not established.\n\nCritical / major / minor: **0 / 3 / 0**. READY FOR OWNER CLOSURE: **NO**.')
report=report.replace('## Fresh validation so far','## Complete fresh validation')
report=report.replace('- Affected integrations, focused, complete full regression, schema/static checks and diff validation: pending.','')
report=report.replace('The final integrity comparison is pending.',f"The final integrity comparison passed: {integrity['files_checked']} non-R3 files are unchanged, including implementation and prior R1/R2/F1 evidence; HEAD is unchanged.")
report+='\n| Fresh run | Tests | Exit | Seconds | Result |\n| --- | ---: | ---: | ---: | --- |\n'
for name,r in runs.items():
    report+=f"| {name} | {r['test_count'] if r['test_count'] is not None else '-'} | {r['exit_code']} | {r['elapsed_seconds']} | {'PASS' if r['passed'] else 'FAIL'} |\n"
report+='''
The corrected adversarial run completed with three acceptance failures and no probe errors. Those assertions reproduce R3-M1 and R3-M2; the rollback case fails for both execution-store roots. The separate actual-executor confirmation reproduced both rollback variants. The additional multi-file apply probe reproduces R3-M3. Prior R1/F1 test reports are background only and are not substituted for these fresh results.

## Coverage and decision

| Required area | Assessment and evidence |
| --- | --- |
| AUTHORITY | FAIL: R3-M1 reuses a consumed job/attempt with no new canonical approval or work claim. Import separation, explicit human approval and native-tool confinement cases pass. |
| CERTIFICATION | PASS on inspected and tested boundaries: unknown/revoked capabilities, profile escalation, policy source changes, unsupported external execution, and Reviewer certification ceilings deny. Certificates remain ceilings rather than approvals. |
| PROVENANCE | FAIL: combined retained-intent and dispatch rebinding is accepted without checking the retained entry's original canonical provenance. Policy/catalog provenance and ordinary tampering cases pass. |
| TRACE | FAIL: R3-M2 permits actual Git mutation and successful result acceptance with missing action-policy records. R3-M3 permits a later controlled target mutation after effect evidence disappears; later canonical result acceptance denies. Observation-import separation passes. |
| REPLAY | FAIL: R3-M1 permits actual fresh-process redispatch. Journal-only rollback, partial/missing retained intents, ordinary replay, and forged identity without dispatch rebinding deny. |
| COMPATIBILITY | PASS on exercised boundaries: historical task authority without GOV-02 provenance requires recovery without migration; observation-only reads remain non-authoritative; GOV-01 gate strengthening, CORE recovery/retry/continuation/budget/context/compute behavior pass regression. |
| Parent ceilings and blast/reversibility | PASS on supported tested paths: parent project/tool/capability/gate/stop/budget ceilings and controlled destructive-write/independent-review gates remain enforced. These do not resolve the replay and action-trace failures. |

All requested run categories completed. Static validation uses the repository validator: runtime Python AST parsing, schema JSON/local-reference checks and capability policy validation; it is not an external JSON Schema metaschema certification. R3 probe scripts also parse successfully. `git diff --check` passed. Exact full logs and SHA-256 hashes are adjacent to this report. Non-R3 source fingerprints are unchanged.

No live provider, remote service, deployment or publication validation is claimed. Git effects were confined to temporary repositories. Both reproduced attacks require access to local evidence state; no provider escape is demonstrated. Canonical authority and policy were retained, so these attacks do not replace the entire trusted system.

Next required action: fix the three majors in a separately authorized implementation task, then obtain a fresh independent review with the required high-risk provider routing. This review does not repair implementation, close GOV-02, commit, or begin ORCH-01.
'''
(OUT/'REVIEW.md').write_text(report)
print(json.dumps({'review':'FIX','independence':'PASS','major':3,'tests':{n:r['test_count'] for n,r in runs.items()},'unchanged_files':integrity['files_checked']}))
