"""Finalize only complete, byte-bound review evidence; never touch implementation."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
spec=importlib.util.spec_from_file_location('r4_runner',OUT/'run_review.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
before=json.loads((OUT/'source-before.json').read_text())
source_digest=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest()
stages=['targeted','adversarial','r3-adversarial','r3-multifile','affected','focused','full',
    'validation','diff-check','combined','action-confirmation','replay-confirmation',
    'rollback-confirmation','import-boundaries-corrected','static-review']
reports={};missing=[]
for name in stages:
    path=OUT/(name+'.json')
    if not path.exists():missing.append(name);continue
    record=json.loads(path.read_text());raw=(OUT/record['log']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==record['log_sha256'],name+' log changed'
    assert record['source_sha256']==source_digest,name+' source binding mismatch'
    assert record['complete'],name+' incomplete'
    counts=re.findall(rb'Ran (\d+) tests? in',raw)
    if record['test_count'] is not None:
        assert counts and int(counts[-1])==record['test_count']
    if record['passed']:
        assert record['exit_code']==0
        if record['test_count'] is not None:assert re.search(rb'^OK\s*$',raw,re.M)
    reports[name]=record
after=runner.snapshot()
changed=[n for n in sorted(set(before)|set(after)) if before.get(n)!=after.get(n)]
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head=='c5de47440973c87023bbd6652aca984262ab17f7'
assert not changed,'Non-R4 file changed: '+repr(changed)
audit=dict(head=head,non_R4_files_checked=len(before),outside_R4_changed=changed,
    source_sha256=source_digest,missing_stages=missing,
    completed_stages={n:dict(passed=r['passed'],complete=r['complete'],test_count=r['test_count'],log_sha256=r['log_sha256']) for n,r in reports.items()})
(OUT/'resume-log-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
if '--audit' in sys.argv:
    print(json.dumps(audit,indent=2));sys.exit(0)
assert not missing,'Cannot finalize with unfinished validation: '+repr(missing)
assert 'FAILED (failures=4)' in (OUT/'combined.log').read_text()
assert 'errors=' not in (OUT/'combined.log').read_text().split('FAILED (')[-1]
for path in OUT.glob('*.py'):ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
whitespace=[]
for path in OUT.iterdir():
    if path.suffix not in {'.py','.md','.json'}:continue
    for index,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if line.rstrip()!=line:whitespace.append([path.name,index])
assert not whitespace,whitespace
findings=[
    dict(id='R4-M1',severity='major',title='Git consumption rollback can launder provenance and refund consumed work',
        source='runtime/core/capability_actions.py:75',acceptance_source='runtime/core/capability_actions.py:133',
        evidence=['combined-observations.json','action-confirmation-observations.json','replay-confirmation-observations.json']),
    dict(id='R4-M2',severity='major',title='Git commit proceeds after evidence loss during staging',
        source='runtime/git/runtime.py:280',evidence=['combined-observations.json']),
]
value=dict(prompt='GOV-02-R4-INDEPENDENT / GOV-02-R4-RESUME',head=head,
    review='FIX',canonical_skill_decision='FAIL',independence='PASS',
    independence_basis='Fresh reviewer session performed no GOV-02/F1/F2 execution or implementation repair',
    provider='Codex',provider_diversity='NOT ESTABLISHED',high_risk_provider_routing_gate='NOT SATISFIED',
    r1_findings={'1':'CLOSED','2':'CLOSED','3':'CLOSED'},
    r3_majors={'1':'CLOSED','2':'OPEN','3':'CLOSED'},
    r3_major_2_basis='Original attack denied; adjacent Git mutation/consumption/provenance variants remain open',
    finding_counts=dict(critical=0,major=2,minor=0),findings=findings,
    authority='FAIL',certification='PASS',provenance='FAIL',trace='FAIL',replay='FAIL',compatibility='PASS',
    parent_scope_ceilings='PASS',blast_radius_reversibility='PASS',canonical_approval_actor_scope='PASS',
    gov01_invariants='PASS on inspected and regression-tested task/completion/delegation boundaries',
    tests=reports,adversarial_acceptance='FAIL',ready_for_owner_closure='NO',
    integrity=audit,review_only=True,implementation_modified=False,repository_commit_performed=False,
    orch01_started=False,completed_at_utc=datetime.now(timezone.utc).isoformat())
(OUT/'result.json').write_text(json.dumps(value,indent=2)+'\n')
rows=[]
for name,report in reports.items():
    status='PASS' if report['passed'] else 'FAIL'
    count=str(report['test_count']) if report['test_count'] is not None else 'probe/check'
    rows.append(f"| {name} | {status} | {count} | {report['exit_code']} | {report['elapsed_seconds']} | `{report['log_sha256']}` |")
text='''# GOV-02-R4 final independent review

GOV-02 REVIEW: **FIX**. Canonical skill decision: **FAIL**.
INDEPENDENCE: **PASS** for executor/reviewer role separation. This fresh session
performed no GOV-02, F1 or F2 implementation and made no repairs.
HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.

R1 FINDINGS 1 / 2 / 3: **CLOSED / CLOSED / CLOSED** on their original boundaries.
R3 MAJORS 1 / 2 / 3: **CLOSED / OPEN / CLOSED**. The exact R3 M2 reproduction now
denies, but adjacent Git action-provenance and consumption variants remain open.
FINDINGS: **0 critical / 2 major / 0 minor** on the reviewed scope.

1. **R4-M1 — Git consumption rollback can launder provenance and refund work.**
   A journal-only rollback after consumption makes real commit/push/fake-PR
   effects return success with `effect_performed: false`; a fresh Python process
   accepts the committed trace. A separate restart attack restores consumption
   evidence and removes the effect pair while retaining canonical failure pairs.
   The same approval then creates a real commit (count 1 -> 2); acceptance denies
   only afterward. Original authority/job/approval owners were not replaced.
2. **R4-M2 — Git commit continues after evidence loss during staging.**
   Removing the policy or consumed-effect pair immediately after real Git staging
   still allows the real commit. Later acceptance failure does not prevent that
   second mutation.

Detailed causes, boundaries, exact source locations and required repairs are in
[FINDINGS.md](FINDINGS.md); probe outcomes are in the adjacent JSON/log files.
No implementation finding was repaired during review.

AUTHORITY / CERTIFICATION / PROVENANCE / TRACE / REPLAY / COMPATIBILITY:
**FAIL / PASS / FAIL / FAIL / FAIL / PASS**.
READY FOR OWNER CLOSURE: **NO**. GOV-02 stays OPEN and uncommitted.
ORCH-01 was not begun.

## Coverage and limits

Fresh tests and source inspection verify provider-neutral certification ceilings,
revocation, profile/mode/allocation matching, exact request/result/evidence binding,
parent tools/capabilities/project/scope/gates/budget ceilings, blast/reversibility,
canonical approval actor/scope checks, monotonic GOV-01 review strengthening,
historical recovery refusal and observation non-authority. Imported execution
and review observations cannot complete, dispatch, feed approved Git prerequisites
or restore executable human-resumption authority. Controlled create/modify/delete,
compensation and final return revalidate exact evidence; lost evidence halts later
mutations and does not authorize compensation. Original job-attempt replay and
coherent retained-intent/dispatch rebinding plus journal rollback deny in fresh
processes for canonical and alternate execution roots. One explicit new canonical
human receipt still permits only its bounded work generation.

These repaired original boundaries do not repair the two Git majors above.
Certification and canonical human approvals remain necessary; their continuous
enforcement and action Decision Audit Trace/replay integrity still fail.
GOV-01 task/completion/delegation invariants pass on the inspected/tested paths;
no new approval, budget, journal or authority owner was found.

R1/R2/R3 durable evidence, current F2 validation and the actual tracked/untracked
runtime/schema/policy diff were read. `prior-evidence-audit.json` checks retained
R1/R3/F2 regression logs against their hashes and confirms all 212 F2 source
fingerprints match. R1's validation JSON is a structured check record rather than
a subprocess/log report; its absent log fields are not a claimed log failure.
The three copied R3 probes are byte-identical to their originals. Earlier green
claims do not substitute for this review's fresh runs.

Provider diversity is not established. PATH discovery resolved Codex only;
Claude/Gemini did not resolve, and available tools exposed no eligible distinct
provider execution route. This does not prove no installation exists elsewhere.
`orchestrator/routing/fallback.yaml` requires high-risk escalation when a different
provider is unavailable, and `escalation.yaml` requires reviewer role separation.
Role independence passes; the high-risk provider routing gate remains unsatisfied.
No provider-diverse acceptance is claimed. The reproduced majors independently
require FIX, regardless of that gate.

## Completed fresh validation

| Run | Result | Tests | Exit | Seconds | Complete log SHA-256 |
| --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(rows)+'''

Targeted, affected, focused and full are completed aggregate runs. No interrupted
suite or isolated rerun substitutes for their results. Adversarial acceptance
is **FAIL**, despite the green F1/F2 and original R3 suites: three new combined
methods have four failed assertions and no probe errors, and the action/replay
confirmation scripts reproduce the two majors. The initial import-boundary
reviewer setup error and its script/log/report are retained and excluded from
PASS; the corrected two-method suite passes. See FINDINGS.md for the correction.

Static/schema validation uses the repository's existing AST/JSON/local-reference
and certificate validators (172 runtime Python files, 33 schemas, 17 certificates),
plus duplicate JSON, catalog coverage, reviewer AST and production-import checks.
No external metaschema validation package was installed or claimed.
Git effects are isolated in temporary repositories and a local bare remote;
PR integration uses the existing fake adapter. No live provider, forge, deployment,
publication, VPS or provider escape was tested or claimed.

## Resume and integrity evidence

The resume preserved all completed tests and the original running validator.
Affected had already passed; focused, full and final validation finished in that
same sequential runner. Process inspection via CIM was denied; `Get-Process`
and the retained PTY session independently confirmed the original live processes.
The first resume-log audit shell command had a quoting error; the final Python
auditor independently validates every completed report/log binding.

'''+f"All **{len(before)} non-R4 files** pinned before review remain byte-identical.\n"+'''
This includes prior review evidence and pre-existing dirty implementation/docs.
HEAD remains exactly the expected commit. `resume-audit.json`, `source-before.json`,
`source-after.json`, `integrity.json` and `resume-log-audit.json` provide exact
fingerprint evidence. `git diff --check` passes if its row above is PASS; existing
LF/CRLF warnings are informational. New reviewer Python/Markdown/JSON files pass
AST and trailing-whitespace checks. All review edits are confined to
`governance/capability-governance/reviews/GOV-02-R4/`.

No implementation file, prior review artifact, canonical project status, repository
history or ORCH-01 file was edited. Fixes and a subsequent acceptance review are
separate work; this review grants no execution, repair, closure or commit approval.
'''
(OUT/'REVIEW.md').write_text(text,encoding='utf-8')
(OUT/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
(OUT/'integrity.json').write_text(json.dumps(dict(unchanged=True,changed=[],files_checked=len(before),head=head,all_review_edits_confined_to=str(OUT.relative_to(ROOT))),indent=2)+'\n')
print(json.dumps(dict(review='FIX',independence='PASS',finding_counts=value['finding_counts'],
    full=reports['full'],integrity=value['integrity']['outside_R4_changed'],ready_for_owner_closure='NO'),indent=2))
