"""Reconcile R5 policy evidence only; never invoke tests or runtime validators."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import runpy
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PREFIX = OUT.relative_to(ROOT).as_posix() + '/'
assert PREFIX == 'governance/capability-governance/reviews/GOV-02-R5/'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot():
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    paths = {name.replace('\\', '/') for name in names}
    paths.update(path.relative_to(ROOT).as_posix() for path in (ROOT/'governance/capability-governance').rglob('*') if path.is_file())
    return {name: digest(ROOT/name) for name in sorted(paths)
            if (ROOT/name).is_file() and not name.startswith(PREFIX) and '__pycache__' not in name}

def artifacts():
    return {path.relative_to(OUT).as_posix(): digest(path) for path in sorted(OUT.rglob('*'))
            if path.is_file() and '__pycache__' not in path.parts and path.name != 'artifact-manifest.json'}

def replace_exact(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)

head_before = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert head_before == 'c5de47440973c87023bbd6652aca984262ab17f7'
before = snapshot()
assert before == json.loads((OUT/'source-before.json').read_text())
artifact_before = artifacts()
original_result = json.loads((OUT/'result.json').read_text())
assert original_result['review'] == 'FIX' and original_result['runtime_acceptance_checks'] == 'PASS'
assert original_result['independence'] == 'PASS' and original_result['prior_findings'] == 'CLOSED'
assert original_result['findings'] == {'critical': 0, 'major': 0, 'minor': 0}

history = OUT/'superseded-policy-verdict'
history.mkdir(exist_ok=False)
for name in ('REVIEW.md', 'result.json', 'prior-evidence-audit.json', 'finalize_report.py', 'audit_evidence.py', 'artifact-manifest.json'):
    (history/name).write_bytes((OUT/name).read_bytes())
(history/'README.md').write_text('# Superseded R5 policy verdict\n\nThese are byte-identical snapshots taken before GOV-02-R5-POLICY-RECONCILE.\nTheir FIX / NEEDS_HUMAN / READY NO provider-gate interpretation is historical\nand superseded by ../POLICY_RECONCILIATION.md and the current ../REVIEW.md.\nTechnical results and same-provider observations remain intact.\n', encoding='utf-8')

sources = ('CONSTITUTION.md', 'AGENTS.md', 'skills/shared/review/SKILL.md')
policy = {
    'prompt_id': 'GOV-02-R5-POLICY-RECONCILE',
    'canonical_distinct_provider_requirement': 'NO',
    'canonical_distinct_model_requirement': 'NO',
    'sources': {name: {'sha256': digest(ROOT/name)} for name in sources},
    'exact_requirements': {
        'CONSTITUTION.md:41': 'Important, risky, user-facing, security-sensitive, financial, or irreversible work must be validated by a reviewer or gatekeeper that is independent from the initial executor.',
        'AGENTS.md:57': 'Critical work requires independent validation. The reviewer or gatekeeper should check the actual output, relevant source files, and tool results rather than trusting an executor summary.',
        'skills/shared/review/SKILL.md:26': '- Stay independent from the executor.',
        'CONSTITUTION.md:7': '1. The company core is provider-independent.'},
    'distinction': 'Reviewer independence concerns separation from the executor and evidence-based validation. Provider independence concerns a core and canonical policy that do not depend on a particular engine. Neither specifies a different model or provider for acceptance.',
    'earlier_interpretation': 'Superseded: lower-level routing fallback was treated as a universal canonical acceptance gate.',
    'routing_disclosure': 'The earlier report cited real different-provider fallback/escalation text. It is not deleted or claimed absent. Under the current human instruction and AGENTS.md precedence, it is not an additional universal acceptance requirement in the three requested canonical sources. Routing files and provider adapters are unchanged.',
    'provider_diversity': 'NOT ESTABLISHED; same-provider review disclosed',
    'technical_results_reused_without_rerun': True,
    'corrected_review': 'PASS',
    'ready_for_owner_closure': 'YES',
    'owner_status': 'GOV-02 remains OPEN and uncommitted until owner closure'}
for location, quote in policy['exact_requirements'].items():
    name, line = location.rsplit(':', 1)
    assert (ROOT/name).read_text(encoding='utf-8').splitlines()[int(line)-1] == quote
(OUT/'policy-reconciliation.json').write_text(json.dumps(policy, indent=2)+'\n', encoding='utf-8')

path = OUT/'finalize_report.py'
text = path.read_text()
text = replace_exact(text, "result = dict(review='FIX', runtime_acceptance_checks='PASS', canonical_decision='NEEDS_HUMAN',", "result = dict(review='PASS', runtime_acceptance_checks='PASS', canonical_decision='PASS',")
text = replace_exact(text, "provider_diversity='NOT ESTABLISHED', high_risk_provider_gate='UNSATISFIED',", "provider_diversity='NOT ESTABLISHED', canonical_distinct_provider_requirement='NO',\n    canonical_distinct_model_requirement='NO', high_risk_provider_gate='NOT A CANONICAL ACCEPTANCE REQUIREMENT',\n    policy_reconciliation='policy-reconciliation.json',")
text = replace_exact(text, "ready_for_owner_closure='NO',", "ready_for_owner_closure='YES',")
text = replace_exact(text, "routing_reason='High-risk same-provider fallback requires escalation under fallback.yaml and escalation.yaml; no eligible distinct-provider route was observed.',", "routing_reason='Canonical sources require independence from the executor, not a different model/provider. The earlier universal provider-gate interpretation is superseded by the current policy reconciliation; same-provider disclosure remains.',")
text = replace_exact(text, "required_next_action='Obtain the eligible distinct-provider acceptance review or an explicit canonical human routing decision; keep GOV-02 OPEN.',", "required_next_action='Ready for owner closure; GOV-02 remains OPEN and uncommitted until the owner records closure.',")
text = replace_exact(text, 'GOV-02 REVIEW: **FIX**. Canonical review decision: **NEEDS_HUMAN**.', 'GOV-02 REVIEW: **PASS**. Canonical review decision: **PASS**.')
text = replace_exact(text, 'Provider diversity: **NOT ESTABLISHED**; high-risk provider routing gate remains\n**UNSATISFIED**. This is a same-provider technical review, not provider-diverse\nacceptance authority.', 'CANONICAL DISTINCT-PROVIDER / DISTINCT-MODEL REQUIREMENT: **NO / NO**.\nProvider diversity: **NOT ESTABLISHED**. This same-provider review satisfies\ncanonical reviewer independence; no provider-diverse review is claimed.')
text = replace_exact(text, 'READY FOR OWNER CLOSURE: **NO**, solely because the required high-risk provider\nrouting decision remains unresolved. GOV-02 stays OPEN and uncommitted.', 'READY FOR OWNER CLOSURE: **YES**. GOV-02 stays OPEN and uncommitted until the\nowner records closure.')
start = text.index('## Independence and remaining acceptance gate')
end = text.index('Git effects used disposable temporary repositories', start)
text = text[:start] + '''## Independence and canonical policy reconciliation

The fresh reviewer session implemented none of GOV-02/F1/F2/F3. Independent role
and actual-output inspection pass. PATH discovery resolved Codex only; Claude
and Gemini did not resolve, and available tool metadata exposed no callable
eligible distinct-provider route. This does not prove no installation exists
elsewhere. No sub-agent or provider-diverse review is claimed.

[CONSTITUTION.md rule 9](../../../../CONSTITUTION.md) requires a reviewer or
gatekeeper independent from the initial executor. [AGENTS.md, Review And
Gatekeeping](../../../../AGENTS.md) requires independent validation of actual
outputs, source and tool evidence. The [shared review skill, Constraints](../../../../skills/shared/review/SKILL.md)
says "Stay independent from the executor." None of these sources requires a
different model or provider. Constitution rule 1 concerns provider-neutral core
architecture and policy, not provider diversity among execution and review roles.

The original report overapplied real lower-level fallback/escalation routing text
as a universal canonical acceptance gate. The current human instruction and
AGENTS.md precedence reconcile acceptance against the three canonical sources.
No routing file, provider adapter or canonical policy was changed. The earlier
**FIX / NEEDS_HUMAN / READY NO** verdict is superseded by **PASS / PASS / READY YES**.
Same-provider disclosure and all technical evidence remain intact. See
`POLICY_RECONCILIATION.md`, `policy-reconciliation.json` and the explicitly
historical snapshots in `superseded-policy-verdict/`.

This reconciliation reran no tests or runtime/static/schema/diff validators.
The complete R5 validation results above are the existing fresh technical review.

''' + text[end:]
path.write_text(text, encoding='utf-8')
runpy.run_path(str(path), run_name='__main__')

route_update = {
    'high_risk_provider_gate': 'NOT A CANONICAL ACCEPTANCE REQUIREMENT',
    'canonical_distinct_provider_requirement': 'NO',
    'canonical_distinct_model_requirement': 'NO',
    'policy_reconciliation': 'policy-reconciliation.json',
    'previous_gate_interpretation': 'UNSATISFIED interpretation superseded; see superseded-policy-verdict/',
    'canonical_policy': list(sources)}
audit_path = OUT/'prior-evidence-audit.json'
audit = json.loads(audit_path.read_text())
audit['provider_route'].update(route_update)
audit_path.write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
path = OUT/'audit_evidence.py'
text = replace_exact(path.read_text(), "    'high_risk_provider_gate': 'UNSATISFIED',", "    'high_risk_provider_gate': 'NOT A CANONICAL ACCEPTANCE REQUIREMENT',\n    'canonical_distinct_provider_requirement': 'NO',\n    'canonical_distinct_model_requirement': 'NO',\n    'policy_reconciliation': 'policy-reconciliation.json',\n    'previous_gate_interpretation': 'UNSATISFIED interpretation superseded; see superseded-policy-verdict/',\n    'canonical_policy': ['CONSTITUTION.md', 'AGENTS.md', 'skills/shared/review/SKILL.md'],")
path.write_text(text, encoding='utf-8')

corrected = json.loads((OUT/'result.json').read_text())
for key in ('tests', 'prior_findings', 'prior_findings_detail', 'findings', 'independence', 'authority', 'certification', 'provenance', 'trace', 'replay', 'compatibility', 'head', 'files_checked', 'limitations'):
    assert corrected[key] == original_result[key], key
after = snapshot()
head_after = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert before == after and head_before == head_after
allowed_changes = {'REVIEW.md', 'result.json', 'prior-evidence-audit.json', 'finalize_report.py', 'audit_evidence.py'}
current = artifacts()
changed = [name for name, value in artifact_before.items() if current.get(name) != value]
assert set(changed) == allowed_changes, changed
integrity = {
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'prompt_id': policy['prompt_id'], 'head_before': head_before, 'head_after': head_after,
    'non_R5_files_checked': len(before), 'non_R5_files_unchanged': before == after,
    'existing_R5_artifacts_changed': sorted(changed),
    'existing_R5_artifacts_unchanged': {name: value for name, value in artifact_before.items() if name not in allowed_changes},
    'technical_results_unchanged': True, 'tests_or_validators_rerun': False,
    'writes_only': PREFIX, 'implementation_changed': False, 'committed': False,
    'ORCH_01_started': False, 'source_policy_sha256': policy['sources']}
(OUT/'policy-reconciliation-integrity.json').write_text(json.dumps(integrity, indent=2)+'\n', encoding='utf-8')
(OUT/'artifact-manifest.json').write_text(json.dumps(artifacts(), indent=2)+'\n', encoding='utf-8')
print(json.dumps({'review': corrected['review'], 'ready_for_owner_closure': corrected['ready_for_owner_closure'],
                  'non_R5_files_unchanged': True, 'files_checked': len(before), 'tests_rerun': False}))
