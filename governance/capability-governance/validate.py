"""Reproducible syntax/schema/reference checks, without executing providers."""
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.core.validation import JobValidator
from runtime.core.capability_governance import policy


python_files = list((ROOT / "runtime").rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
schemas = list((ROOT / "schemas").glob("*.schema.json"))
for path in schemas:
    JobValidator(path).validate_schema_references()
certification = policy()
JobValidator(ROOT / "schemas/capability-certification.schema.json").validate(certification)
print(json.dumps({"python_syntax_files": len(python_files), "schema_files": len(schemas),
                  "certificate_count": len(certification["certificates"]), "status": "PASS"}))
