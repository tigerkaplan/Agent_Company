"""Bounded current-schema/runtime/policy AST and JSON canonicality checks."""
import ast,json,re
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from runtime.core.validation import JobValidator
from runtime.core.capability_governance import policy

def unique(pairs):
 result={}
 for key,value in pairs:
  assert key not in result,"duplicate JSON key: "+key
  result[key]=value
 return result

def refs(value,validator,root,path):
 if isinstance(value,dict):
  if "$ref" in value:validator._resolve_ref(value["$ref"],root,path)
  for child in value.values():refs(child,validator,root,path)
 elif isinstance(value,list):
  for child in value:refs(child,validator,root,path)

runtime=list((ROOT/"runtime").rglob("*.py"))
schemas=list((ROOT/"schemas").glob("*.schema.json"))
for path in runtime:ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
for path in schemas:
 value=json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=unique)
 assert isinstance(value,dict),path
 refs(value,JobValidator(path),value,path)
cert=policy();JobValidator(ROOT/"schemas/capability-certification.schema.json").validate(cert)
assert len(cert["certificates"])==17
catalog=re.findall(r"^  ([a-z_]+):$",(ROOT/"orchestrator/routing/capabilities.yaml").read_text(),re.M)
assert set(catalog)==set(cert["certificates"])
production=[]
for path in runtime:
 if "tests" in path.parts:continue
 tree=ast.parse(path.read_text(encoding="utf-8"))
 for node in ast.walk(tree):
  if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith("runtime.tests"):production.append(path)
  if isinstance(node,ast.Import):
   production.extend(path for alias in node.names if alias.name.startswith("runtime.tests"))
assert not production,production
print(json.dumps({"status":"PASS","runtime_python_files":len(runtime),"schema_files":len(schemas),"certificates":len(cert["certificates"]),"duplicate_json_keys":"PASS","local_schema_references":"PASS","production_test_imports":len(production)},indent=2))
