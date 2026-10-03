"""Reproducible syntax/schema/reference checks, without executing providers."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.core.validation import JobValidator
from runtime.core.capability_governance import policy


def references(value, validator, root, path):
    if isinstance(value, dict):
        if "$ref" in value:
            validator._resolve_ref(value["$ref"], root, path)
        for item in value.values():
            references(item, validator, root, path)
    elif isinstance(value, list):
        for item in value:
            references(item, validator, root, path)


python_files = list((ROOT / "runtime").rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
schemas = list((ROOT / "schemas").glob("*.schema.json"))
for path in schemas:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path
    references(value, JobValidator(path), value, path)
certification = policy()
JobValidator(ROOT / "schemas/capability-certification.schema.json").validate(certification)
print(json.dumps({"python_syntax_files": len(python_files), "schema_files": len(schemas),
                  "certificate_count": len(certification["certificates"]), "status": "PASS"}))
