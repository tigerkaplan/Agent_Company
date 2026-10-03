"""Pin canonical F1 evidence before F2 documentation/status reconciliation."""
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
CANONICAL = OUT.parents[1]
saved = {}
for name in ("README.md", "VALIDATION.md", "validated-source.json", "targeted-regression.json", "adversarial-regression.json", "affected-regression.json", "focused-regression.json", "full-regression.json"):
    source = CANONICAL / name
    target = OUT / ("pre-f2-" + name)
    if target.exists():
        assert target.read_bytes() == source.read_bytes(), "Snapshot/current evidence conflict: " + name
    else:
        shutil.copyfile(source, target)
    saved[name] = hashlib.sha256(target.read_bytes()).hexdigest()
(OUT / "pre-f2-canonical-evidence.json").write_text(json.dumps(saved, indent=2) + "\n")
print(json.dumps({"preserved": len(saved), "canonical_written": False}))
