"""Finalize the completed R5 review without changing canonical project state."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
audit = json.loads((OUT/'final-integrity.json').read_text())
assert audit['all_stages_pass'] and audit['unchanged'] and audit['expected_head']
observations = json.loads((OUT/'r5-combined-observations.json').read_text())
assert len(observations) == 9
domains = {name: 'PASS' for name in ('authority', 'certification', 'provenance', 'trace', 'replay', 'compatibility')}
prior = {name: 'CLOSED' for name in ('R1-M1', 'R1-M2', 'R1-M3', 'R3-M1', 'R3-M2', 'R3-M3', 'R4-M1', 'R4-M2')}
result = dict(review='FIX', runtime_acceptance_checks='PASS', canonical_decision='NEEDS_HUMAN',
    independence='PASS', independence_scope='Fresh session and executor/reviewer role separation; same provider',
    provider_diversity='NOT ESTABLISHED', high_risk_provider_gate='UNSATISFIED',
    prior_findings='CLOSED', prior_findings_detail=prior,
    findings={'critical': 0, 'major': 0, 'minor': 0},
    **domains, tests=audit['reports'], ready_for_owner_closure='NO',
    head=audit['head'], files_checked=audit['files_checked'], non_R5_files_unchanged=True,
    review_writes_only='governance/capability-governance/reviews/GOV-02-R5/',
    implementation_repairs=False, repository_commit=False, ORCH_01_started=False,
    routing_reason='High-risk same-provider fallback requires escalation under fallback.yaml and escalation.yaml; no eligible distinct-provider route was observed.',
    required_next_action='Obtain the eligible distinct-provider acceptance review or an explicit canonical human routing decision; keep GOV-02 OPEN.',
    limitations=['Temporary Git repositories and local bare remotes only', 'Existing fake PR adapter only',
                 'No live provider, forge, deployment, publication, VPS or provider escape validation',
                 'Trusted filesystem boundary unchanged; no protection against replacing every authority owner and policy is claimed'])
(OUT/'result.json').write_text(json.dumps(result, indent=2)+'\n')
table = '\n'.join(f"| {name} | PASS | {r['test_count'] if r['test_count'] is not None else 'probe/check'} | {r['exit_code']} | {r['elapsed_seconds']} | `{r['log_sha256']}` |"
                  for name, r in audit['reports'].items())
report = f'''# GOV-02-R5 completed fresh review

GOV-02 REVIEW: **FIX**. Canonical review decision: **NEEDS_HUMAN**.
Runtime acceptance checks: **PASS**. No runtime repair finding was reproduced.
INDEPENDENCE: **PASS** for fresh-session and executor/reviewer role separation.
Provider diversity: **NOT ESTABLISHED**; high-risk provider routing gate remains
**UNSATISFIED**. This is a same-provider technical review, not provider-diverse
acceptance authority.

PRIOR FINDINGS: **CLOSED** on all reproduced original and adjacent boundaries.
R1 majors 1 / 2 / 3: **CLOSED / CLOSED / CLOSED**.
R3 majors 1 / 2 / 3: **CLOSED / CLOSED / CLOSED**.
R4 majors 1 / 2: **CLOSED / CLOSED**.
FINDINGS: **0 critical / 0 major / 0 minor** on the reviewed technical scope.
AUTHORITY / CERTIFICATION / PROVENANCE / TRACE / REPLAY / COMPATIBILITY:
**PASS / PASS / PASS / PASS / PASS / PASS**.
READY FOR OWNER CLOSURE: **NO**, solely because the required high-risk provider
routing decision remains unresolved. GOV-02 stays OPEN and uncommitted.
ORCH-01 was not begun.

HEAD before and after review: `{audit['head']}`.
The reviewer performed no GOV-02, F1, F2 or F3 implementation and made no repair.
All durable review writes are confined to this directory. All **{audit['files_checked']}
non-R5 files** pinned before review remain byte-identical, including implementation,
canonical docs, pre-existing dirty changes and prior R1-R4/F1-F3 evidence.

## Prior finding closure and new probes

R1 observation imports remain readable but cannot dispatch, complete, feed
independent review/Git prerequisites or restore human-resumption authority.
Original pre-apply consumption loss denies target application and acceptance.
Job-attempt journal rollback, new identity and alternate store restart cannot
refund work. The original R3 coherent foreign-intent/dispatch rebinding probe
also denies in fresh processes for both roots with canonical job/authority bytes
unchanged. Controlled multi-file create/modify/delete stops after the first
effect if required evidence disappears; no later mutation or unauthorized
compensation occurs.

Both R4 Git majors are closed on fresh real-effect probes. Removing policy or
effect records after real staging leaves HEAD unchanged and prevents commit.
Journal rollback after staging also prevents commit. Rollback after an authorized
remote effect denies acceptance and restart reconciliation; it does not write a
successful trace with `effect_performed: false`. The original retained-failure
restart attack preserves its failure pair, receives no new human approval and
keeps commit count **1 -> 1**. It cannot reuse the consumed Git generation.

The new independent R5 probe covers **3 methods / 9 subcases**:

- Two duplicate approval variants, with identical or conflicting actor values,
  deny before staging/commit and preserve target HEAD.
- Local commit and remote push retain complete or partial failure evidence while
  effect pairs disappear and the journal rolls back. Fresh processes deny before
  add/commit/push, preserve the surviving failure anchor and leave targets and
  canonical job/task/approval owners unchanged.
- After real staging, journal rollback combines with effect loss alone, policy
  witness loss or approval loss. Commit and automatic compensation do not run;
  fresh-process retries deny and target HEAD stays unchanged. Approval loss is
  the intentional authority mutation in that subcase.

The dedicated F3 regressions also cover real commit/push/fake-PR effects followed
by rollback, intact result evidence despite missing consumption, twelve staging
loss/change/encoding cases, first-effect checks and genuine out-of-action push
reconciliation that remains an observation without new effect authority.

Actual source/diff inspection and fresh runs cover exact-work binding, certified
profiles/revocation, source provenance, parent project/tool/capability/profile/
scope/gate/budget ceilings, blast radius and reversibility, model/advice
non-authority, canonical approval integrity, trace/replay, historical refusal
without migration, and GOV-01/CORE claim, review, budget, progress, retry,
continuation, context and recovery invariants. See `SOURCE_INSPECTION.md`.

## Completed fresh validation

| Run | Result | Tests | Exit | Seconds | Complete log SHA-256 |
| --- | --- | --- | --- | --- | --- |
{table}

Every stage completed with exit 0. Targeted, adversarial, affected, focused and
full runs each contain a complete unittest summary. Full discovery passed
**1,308 tests in one uninterrupted process**. No interrupted aggregate or isolated
rerun substitutes for these results. All reports bind their commands, counts,
complete logs and common source fingerprint. The original R3/R4 probes are
byte-identical copies; their fresh outcomes are preserved alongside the new R5
observations. Prior green reports were not adopted as R5 results.

Schema/static checks parsed **173 runtime Python files**, validated **33 schemas**
and local references, checked duplicate JSON fields and all **17 certificates**,
matched certificate/catalog coverage and found **0 production test imports**.
These use repository validators; no external metaschema package was installed
or claimed. `git diff --check` passed. All reviewer Python files parse and reviewer
Python/Markdown/JSON files have no trailing whitespace. Exact source preservation,
HEAD, report/log bindings and artifact hashes are in `final-integrity.json`,
`source-before.json`, `source-after.json` and `artifact-manifest.json`.

## Independence and remaining acceptance gate

The fresh reviewer session implemented none of GOV-02/F1/F2/F3. Independent role
and actual-output inspection pass. PATH discovery resolved Codex only; Claude
and Gemini did not resolve, and available tool metadata exposed no callable
eligible distinct-provider route. This does not prove no installation exists
elsewhere. No sub-agent or provider-diverse review is claimed.

The applied canonical [review skill](../../../../skills/shared/review/SKILL.md)
states: "Do not use `PASS` when required checks are missing or unresolved risks
remain." Its Codex adapter requires applying the routing policies when provider
independence is unavailable. `orchestrator/routing/fallback.yaml` prescribes
`high_risk_action: escalate` for unavailable different-provider review;
`escalation.yaml` has `no_independent_provider_for_high_risk_review: escalate`.
Those requirements are not silently waived. They explain **FIX / NEEDS_HUMAN /
READY NO**, despite all technical checks passing and all prior runtime findings
being closed. Obtain the eligible distinct-provider acceptance review or an
explicit canonical human routing decision before owner closure.

Git effects used disposable temporary repositories and local bare remotes. PR
effects used the existing fake adapter. No live provider, forge, deployment,
publication, VPS or provider escape was tested or claimed. The documented
trusted-filesystem boundary is preserved; the probes do not replace every
trusted authority owner and policy. No reviewed-repository commit, implementation
fix, canonical status edit or ORCH-01 work was performed.
'''
(OUT/'REVIEW.md').write_text(report)
print(json.dumps({k: result[k] for k in ('review', 'runtime_acceptance_checks', 'canonical_decision', 'independence', 'prior_findings', 'findings', 'ready_for_owner_closure')}))
