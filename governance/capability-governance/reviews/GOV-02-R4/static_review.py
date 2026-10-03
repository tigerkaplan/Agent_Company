"""Supplementary review AST/JSON/capability coverage checks; no writes outside R4."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from runtime.core.validation import JobValidator
from runtime.core.capability_governance import policy

def unique(pairs):
    result={}
    for key,value in pairs:
        assert key not in result, 'Duplicate JSON field: '+key
        result[key]=value
    return result

schemas=list((ROOT/'schemas').glob('*.schema.json'))
for path in schemas: json.loads(path.read_text(),object_pairs_hook=unique)
catalog=policy()
JobValidator(ROOT/'schemas/capability-certification.schema.json').validate(catalog)
capabilities=re.findall(r'^  ([a-z_]+):$',(ROOT/'orchestrator/routing/capabilities.yaml').read_text(),re.M)
assert set(catalog['certificates'])==set(capabilities),'Certification catalog mismatch'
assert catalog['certificates']['independent_review']['profiles']==['READ_ONLY']
assert [k for k,v in catalog['certificates'].items() if 'EXTERNAL_EXECUTE' in v['profiles']]==['software_implementation']
assert len(catalog['certificates'])==17
runtime=list((ROOT/'runtime').rglob('*.py'))
review=list(OUT.glob('*.py'))
for path in runtime+review:ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
production=[]
for path in runtime:
    if 'tests' in path.parts:continue
    tree=ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('runtime.tests'):
            production.append(str(path.relative_to(ROOT)))
        if isinstance(node,ast.Import):
            for alias in node.names:
                if alias.name.startswith('runtime.tests'):production.append(str(path.relative_to(ROOT)))
assert not production,'Test authority helper in production'
source=json.loads((ROOT/'governance/capability-governance/validated-source.json').read_text())
mismatches=[n for n,h in source.items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h]
assert not mismatches,'Validated source drift'
print(json.dumps(dict(status='PASS',runtime_python_files=len(runtime),review_python_files=len(review),
    schema_json_duplicate_checks=len(schemas),capability_count=len(capabilities),
    certificate_count=len(catalog['certificates']),production_test_imports=production,
    executor_validated_files=len(source),executor_source_mismatches=mismatches,
    schema_validation_scope='Repository validator and local references; no external metaschema package installed'),indent=2))
