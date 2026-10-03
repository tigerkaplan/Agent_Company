"""Reconstruct hash-verified R3 bytes in memory and capture only F2 edits."""
import difflib
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
R3 = OUT.parent / "GOV-02-R3"
before_hashes = json.loads((R3 / "source-after.json").read_text())
reverse = {
    "runtime/core/capability_actions.py": [(
        '        if self.store._decision_pair(self.identity, "action-policy") != self.value:\n'
        '            raise ExecutionStoreError("Action policy provenance changed before effect or acceptance")\n'
        '        self.store._verify_observation(self.value, "decision_intent_observed", self.identity, digest(self.value))\n', '')],
    "runtime/storage/execution_store.py": [(
        '                        source = prior["authority_source"]\n'
        '                        if (prior["request"]["execution_id"] != prior_id\n'
        '                                or source["job_id"] != prior["request"]["job_id"]\n'
        '                                or prior["request_digest"] != digest(prior["request"])\n'
        '                                or Path(source["progress_store_root"]).resolve()\n'
        '                                != runtime.progress.store.root.resolve()):\n'
        '                            raise ExecutionStoreError("Retained intent identity/provenance changed; recovery required")\n', ''), (
        '                        # Journal observations independently bind even apparently\n'
        '                        # foreign retained entries. No live historical job is\n'
        '                        # needed, but mutable paired records cannot certify each\n'
        '                        # other or redirect verification to another journal owner.\n'
        '                        decisions._verify_observation(prior, "decision_intent_observed", prior_id, digest(prior))\n'
        '                        decisions._verify_observation(prior, "decision_consumption_observed", prior_identity, digest(prior))\n', ''), (
        '                            decisions._verify_consumption(prior, stage, claim)\n',
        '                            if decisions._decision_pair(prior_id, stage) != claim:\n'
        '                                raise ExecutionStoreError("Retained consumption does not bind original intent; recovery required")\n')],
    "runtime/actions/runtime.py": [(
        '        # Every target mutation (including rollback) needs current exact evidence.\n'
        '        # Evidence loss after a partial effect stops here for explicit recovery;\n'
        '        # it cannot authorize compensating writes or refund consumed work.\n',
        '        # Revalidate after target preflight, immediately before target writes.\n'), (
        '\n        def validate_effect():\n'
        '            require_tool(request, "controlled_write")\n'
        '            require_effect(request, "controlled_write")\n'
        '\n        validate_effect()\n',
        '        require_tool(request, "controlled_write")\n'
        '        require_effect(request, "controlled_write")\n'), (
        '                data = source.read_bytes()\n                validate_effect()\n', ''), (
        '                validate_effect()\n                self._atomic_write(target, data)\n',
        '                self._atomic_write(target, source.read_bytes())\n'), (
        '                validate_effect()\n                target.unlink()\n', '                target.unlink()\n'), (
        '                original = backups[relative]\n                validate_effect()\n', '                original = backups[relative]\n'), (
        '                    validate_effect()\n                    self._atomic_write(target, original)\n',
        '                    self._atomic_write(target, original)\n'), (
        '        validate_effect()\n        return result\n', '        return result\n')],
}
lines = []
manifest = {}
for name, changes in reverse.items():
    path = ROOT / name
    current = path.read_text(encoding="utf-8")
    previous = current
    for new, old in changes:
        assert previous.count(new) == 1, (name, new)
        previous = previous.replace(new, old, 1)
    candidates = [previous.encode(), previous.replace("\n", "\r\n").encode()]
    original = next((raw for raw in candidates if hashlib.sha256(raw).hexdigest() == before_hashes[name]), None)
    assert original is not None, "Reconstructed source does not match actual R3 hash: " + name
    manifest[name] = {"r3_sha256": before_hashes[name], "f2_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    lines.extend(difflib.unified_diff(previous.splitlines(keepends=True), current.splitlines(keepends=True),
                 fromfile="R3/" + name, tofile="F2/" + name))
name = "runtime/tests/test_capability_governance_f2.py"
path = ROOT / name
manifest[name] = {"r3_sha256": None, "f2_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
lines.extend(difflib.unified_diff([], path.read_text().splitlines(keepends=True), fromfile="/dev/null", tofile="F2/" + name))
(OUT / "f2-implementation.diff").write_text("".join(lines), encoding="utf-8")
(OUT / "f2-changed-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"existing_implementation_files_changed": 3, "new_test_files": 1, "original_R3_hashes_verified": True}))
