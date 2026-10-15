"""MEM-02B bounded proposals and planning inputs. Evidence never grants authority.

Only an explicitly installed canonical ApprovalRuntime can confirm dispositions.
These contracts neither change MemoryRecord trust nor grant execution authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from runtime.context.contracts import Limits, RepositoryReader
from runtime.core.task_contract import digest
from runtime.memory.contracts import MemoryContractError, validate_memory_key
from runtime.memory.validity import PinnedMemory
from runtime.progress.store import readonly_inspection, inspection_read

ACTION = "SET_LEARNING_DISPOSITION"
OPERATIONS = frozenset({"PROMOTE", "REVOKE", "SUPERSEDE"})
MAX_LINEAGES = MAX_TRANSITIONS = MAX_ITEMS = 32
MAX_RECORD_BYTES = 128 * 1024
MAX_READ_BYTES = 1024 * 1024
_BUDGET = ContextVar("learning_artifact_reads", default=None)


class LearningError(MemoryContractError):
    """Missing, ambiguous or stale learning evidence; affected planning is held."""


def encoded(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise LearningError("Learning record is not canonical JSON") from error
    if len(raw) > MAX_RECORD_BYTES:
        raise LearningError("Learning record capacity exceeded")
    return raw


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise LearningError("Duplicate learning field")
        value[key] = item
    return value


@contextmanager
def learning_inspection():
    """Nested inspections share the strict learning read budget and no-write IO."""
    token = _BUDGET.set({"read": 0, "paths": {}}) if _BUDGET.get() is None else None
    try:
        with readonly_inspection():
            yield
            if token is not None:
                # readonly_inspection rechecks retained filesystem observations
                # on exit. Include those learning-artifact rereads in this cap.
                state = _BUDGET.get()
                state["read"] += sum(state["paths"].values())
                if state["read"] > MAX_READ_BYTES:
                    raise LearningError("Learning final readback capacity exceeded")
    finally:
        if token is not None:
            _BUDGET.reset(token)


def charge(raw, *, path=None):
    state = _BUDGET.get()
    if len(raw) > MAX_RECORD_BYTES:
        raise LearningError("Learning artifact exceeds 128 KiB")
    if state is not None:
        state["read"] += len(raw)
        if state["read"] > MAX_READ_BYTES:
            raise LearningError("Learning artifact read capacity exceeded")
        if path is not None:
            state["paths"][str(Path(path).resolve())] = len(raw)


def read_record(path):
    raw = inspection_read(path, limit=MAX_RECORD_BYTES)
    charge(raw, path=path)
    try:
        value = json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise LearningError("Malformed learning record") from error
    if raw != encoded(value):
        raise LearningError("Noncanonical learning record")
    return value


def fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise LearningError("Unknown or missing learning fields")


def text(value, limit=200):
    if type(value) is not str or not value.strip() or len(value.encode("utf-8")) > limit:
        raise LearningError("Invalid bounded learning text")
    return value


def sha(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise LearningError("Invalid learning digest")


def number(value, minimum=1, maximum=32):
    if type(value) is not int or not minimum <= value <= maximum:
        raise LearningError("Invalid learning revision/capacity")


def collection(value):
    if type(value) is not list or len(value) > MAX_ITEMS:
        raise LearningError("Learning collection capacity exceeded")


def instant(value):
    text(value)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result
    except ValueError as error:
        raise LearningError("Timezone-aware learning validity required") from error


def planning_scope(value):
    fields(value, "tasks workflows agents capabilities conditions exclusions valid_until")
    for name in ("tasks", "workflows", "agents", "capabilities", "conditions", "exclusions"):
        collection(value[name])
        if len(set(map(str, value[name]))) != len(value[name]):
            raise LearningError("Duplicate planning selector")
        for item in value[name]:
            text(item, 4096 if name in {"conditions", "exclusions"} else 200)
            if any(c in item for c in "*?["):
                raise LearningError("Wildcard learning selectors forbidden")
    if not all(value[n] for n in ("tasks", "workflows", "agents", "capabilities")):
        raise LearningError("Explicit bounded planning selectors required")
    instant(value["valid_until"])


def proposal(value):
    fields(value, "proposal_id version constraint_id constraint applicability evidence counterevidence rejections checks deduplication conflicts")
    validate_memory_key(value["constraint_id"], value["proposal_id"])
    number(value["version"], maximum=2**31-1)
    text(value["constraint"], 16000)
    planning_scope(value["applicability"])
    for name in ("evidence", "counterevidence"):
        collection(value[name])
        identities = []
        for item in value[name]:
            fields(item, "record_id record_digest sources")
            validate_memory_key("learning", item["record_id"])
            sha(item["record_digest"])
            collection(item["sources"])
            if not item["sources"]:
                raise LearningError("Evidence requires local source pins")
            for source in item["sources"]:
                fields(source, "path sha256")
                text(source["path"], 512); sha(source["sha256"])
            identities.append(item["record_id"])
        if len(set(identities)) != len(identities):
            raise LearningError("Duplicate evidence identity")
    if not value["evidence"]:
        raise LearningError("Exact disposition evidence required")
    for name in ("rejections", "conflicts"):
        collection(value[name])
        for item in value[name]:
            text(item, 4096)
    collection(value["checks"])
    if not value["checks"]:
        raise LearningError("Required validation checks absent")
    for check in value["checks"]:
        fields(check, "rule version status")
        text(check["rule"]); text(check["version"])
        if check["status"] != "PASS":
            raise LearningError("Disposition validation must pass")
    fields(value["deduplication"], "outcome related")
    if value["deduplication"]["outcome"] not in {"unique", "duplicate"}:
        raise LearningError("Explicit deduplication outcome required")
    collection(value["deduplication"]["related"])
    for item in value["deduplication"]["related"]:
        sha(item)


def genesis(value):
    fields(value, "schema_version project_id project_root owners logical_job_id")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise LearningError("Invalid learning genesis version")
    validate_memory_key(value["project_id"], "learning")
    fields(value["owners"], "job_root approval_root execution_root review_root task_root progress_root memory_source")
    for path in [value["project_root"], *[v for k, v in value["owners"].items() if k != "memory_source"]]:
        text(path, 2000)
        if not Path(path).is_absolute() or str(Path(path).resolve()) != path:
            raise LearningError("Canonical absolute owner roots required")
    text(value["owners"]["memory_source"])
    text(value["logical_job_id"])


def empty_index(value):
    return {"schema_version": 1, "genesis_digest": digest(value),
            "revision": 0, "heads": {}, "history": []}


def intent(value):
    fields(value, "schema_version operation proposal genesis initialize expected_revision expected_index_digest predecessor")
    if (value["schema_version"] != 1 or type(value["schema_version"]) is not int
            or type(value["operation"]) is not str or value["operation"] not in OPERATIONS):
        raise LearningError("Unsupported learning operation/version")
    proposal(value["proposal"]); genesis(value["genesis"])
    if type(value["initialize"]) is not bool:
        raise LearningError("Explicit initialization allocation required")
    number(value["expected_revision"], minimum=0)
    sha(value["expected_index_digest"])
    prior = value["predecessor"]
    if value["operation"] == "PROMOTE":
        if prior is not None:
            raise LearningError("Promotion cannot silently replace a predecessor")
    else:
        fields(prior, "constraint_id version revision transition_digest application_digest")
        text(prior["constraint_id"]); number(prior["version"], maximum=2**31-1)
        number(prior["revision"]); sha(prior["transition_digest"]); sha(prior["application_digest"])
    if value["initialize"] and (value["operation"] != "PROMOTE" or value["expected_revision"] != 0
                                or value["expected_index_digest"] != digest(empty_index(value["genesis"]))):
        raise LearningError("Initialization must authorize exact explicit genesis")
    if not value["initialize"] and value["expected_revision"] == 0:
        raise LearningError("Missing state is never implicit genesis")


@dataclass(frozen=True, slots=True)
class LearningIntent:
    canonical: str

    @classmethod
    def from_dict(cls, value):
        intent(value)
        return cls(encoded(value).decode("utf-8"))

    def to_dict(self):
        value = json.loads(self.canonical, object_pairs_hook=_object)
        intent(value)
        if encoded(value).decode("utf-8") != self.canonical:
            raise LearningError("Learning intent changed")
        return value


@dataclass(frozen=True, slots=True)
class LearningScope:
    canonical: str

    @classmethod
    def from_dict(cls, value):
        fields(value, "schema_version action intent preparation review governance")
        if value["schema_version"] != 1 or type(value["schema_version"]) is not int or value["action"] != ACTION:
            raise LearningError("Invalid learning action scope")
        intent(value["intent"])
        p = value["preparation"]
        fields(p, "job_id attempt execution_id contract_digest execution_digest completion_digest output_path output_digest")
        for name in ("job_id", "execution_id", "output_path"):
            text(p[name], 2000 if name == "output_path" else 200)
        number(p["attempt"], maximum=2**31-1)
        for name in ("contract_digest", "execution_digest", "completion_digest", "output_digest"):
            sha(p[name])
        fields(value["review"], "review_id digest reviewer")
        text(value["review"]["review_id"]); text(value["review"]["reviewer"]); sha(value["review"]["digest"])
        if type(value["governance"]) is not dict or not value["governance"]:
            raise LearningError("Current governance bindings required")
        from runtime.core.validation import JobValidator
        JobValidator(Path(__file__).resolve().parents[2] / "schemas/learning-disposition.schema.json").validate(value)
        return cls(encoded(value).decode("utf-8"))

    def to_dict(self):
        value = json.loads(self.canonical, object_pairs_hook=_object)
        if type(self) is not LearningScope or self.from_dict(value).canonical != self.canonical:
            raise LearningError("Noncanonical learning scope")
        return value


def learning_fingerprint(value):
    canonical = LearningScope.from_dict(value).to_dict()
    return digest({"action": ACTION, "learning_scope": canonical})


def coverage_name(value):
    return "learning_coverage_" + digest(LearningIntent.from_dict(value).to_dict())


def review_content(value, bodies):
    """Complete bounded external evidence; sanitization never changes its source pins."""
    from runtime.providers.adapters import sanitize_provider_text
    value = LearningIntent.from_dict(value).to_dict()
    fields(bodies, "evidence counterevidence")
    envelope = {"schema_version": 1, "intent": value, **bodies}
    # Enforce the complete raw-body bound before redaction. Sanitizing encoded
    # JSON can miss credentials after escaped newlines or damage JSON quotes.
    encoded(envelope)
    def sanitize(item):
        if isinstance(item, str):
            # Source bodies and lifecycle claims can contain JSON encoded more
            # than once. Inspect every decoded string before re-encoding it.
            try:
                nested = json.loads(item, object_pairs_hook=_object)
            except LearningError:
                raise
            except ValueError as error:
                if item.lstrip().startswith(('{', '[', '"')):
                    raise LearningError("Malformed serialized learning review body") from error
                nested = None
            if isinstance(nested, (dict, list, str)):
                return json.dumps(sanitize(nested), sort_keys=True, ensure_ascii=True,
                                  separators=(",", ":"))
            return sanitize_provider_text(item)
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                # Preserve the sanitizer's assignment-key rules even after
                # parsing a JSON source or serialized lifecycle claim.
                probe = json.dumps({key: "learning-redaction-probe"}, ensure_ascii=True)
                result[key] = ("[REDACTED]" if sanitize_provider_text(probe) != probe
                               else sanitize(child))
            return result
        if isinstance(item, (list, tuple)):
            return [sanitize(child) for child in item]
        return item
    try:
        return encoded(sanitize(envelope)).decode("utf-8")
    except RecursionError as error:
        raise LearningError("Learning review body exceeds JSON nesting capacity") from error


def package_coverage_name(value, content):
    """Bind the exact reviewer-visible bodies as well as the immutable intent."""
    value = LearningIntent.from_dict(value).to_dict()
    if type(content) is not str or len(content.encode("utf-8")) > MAX_RECORD_BYTES:
        raise LearningError("Learning review package exceeds its content bound")
    return "learning_package_coverage_" + digest({"intent_digest": digest(value),
        "content_digest": hashlib.sha256(content.encode("utf-8")).hexdigest()})


def packaged_review_evidence(ref, content):
    """Existing ReviewPackage external-content envelope, including persisted redaction."""
    from runtime.providers.adapters import sanitize_provider_text
    return sanitize_provider_text(json.dumps({"trust": "untrusted", "origin": "tool",
        "authority": "none", "ref": ref, "content": content}, sort_keys=True, ensure_ascii=True))


class LearningInstallation:
    """Trusted foreground composition for one existing project, source and owners.

    No callback may approve or redirect canonical disposition authority.
    """
    def __init__(self, project_id, project_root, memory, memory_source, logical_job_id,
                 *, limits=Limits()):
        from runtime.memory.lifecycle import _memory_interface
        validate_memory_key(project_id, "learning")
        _memory_interface(memory)
        text(memory_source); text(logical_job_id)
        if type(limits) is not Limits or limits.file_bytes > MAX_RECORD_BYTES or limits.scan_bytes > MAX_READ_BYTES:
            # Default CORE-08 scan ceiling is stricter only after narrowing here.
            if limits != Limits():
                raise LearningError("Installed learning limits exceed Scope-63")
            limits = Limits(scan_bytes=MAX_READ_BYTES)
        self.project_id = project_id
        self.project_path = Path(project_root).absolute()
        self.project_root = self.project_path.resolve(strict=True)
        if not self.project_root.is_dir():
            raise LearningError("Existing learning project required")
        identity = self.project_root.stat()
        self.root_identity = (identity.st_dev, identity.st_ino)
        self.memory, self.memory_source = memory, memory_source
        self.logical_job_id, self.limits = logical_job_id, limits
        self._binding = (project_id, self.project_root, memory, memory_source, logical_job_id, limits)

    def validate(self):
        if (type(self) is not LearningInstallation or self._binding !=
                (self.project_id, self.project_root, self.memory, self.memory_source, self.logical_job_id, self.limits)):
            raise LearningError("Learning installation changed")
        identity = self.project_root.stat()
        if (self.project_path.resolve(strict=True) != self.project_root
                or (identity.st_dev, identity.st_ino) != self.root_identity):
            raise LearningError("Learning project root changed")
        self.limits.__post_init__()

    def check_evidence(self, value, *, now):
        with learning_inspection():
            self.validate(); proposal(value)
            if any(c != {"rule": "local-source-pin", "version": "1", "status": "PASS"} for c in value["checks"]):
                raise LearningError("Unsupported learning validation rule/version")
            if instant(now) > instant(value["applicability"]["valid_until"]):
                raise LearningError("Learning proposal validity expired")
            if value["conflicts"]:
                raise LearningError("Unresolved applicability conflicts")
            reader = RepositoryReader(self.project_root, self.limits)
            bodies = {"evidence": [], "counterevidence": []}
            for kind in bodies:
                for item in value[kind]:
                    record = self.memory.get(self.project_id, item["record_id"])
                    if record is None or PinnedMemory.from_record(record).record_digest != item["record_digest"]:
                        raise LearningError("Learning memory evidence missing or changed")
                    snapshot = __import__('dataclasses').asdict(record)
                    charge(encoded(snapshot))
                    required = {(s.location, s.source_digest) for s in record.sources}
                    supplied = {(s["path"], s["sha256"]) for s in item["sources"]}
                    if len(supplied) != len(item["sources"]) or supplied != required:
                        raise LearningError("Learning source pins do not cover the complete memory evidence")
                    sources = []
                    for source in item["sources"]:
                        path = reader.path(source["path"])
                        raw = inspection_read(path, limit=self.limits.file_bytes)
                        reader.bytes_read += len(raw)
                        if reader.bytes_read > self.limits.scan_bytes:
                            raise LearningError("Learning source scan capacity exceeded")
                        charge(raw, path=path)
                        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                            raise LearningError("Learning source evidence missing or changed")
                        try:
                            content = raw.decode("utf-8")
                        except UnicodeError as error:
                            raise LearningError("Learning source body is not UTF-8") from error
                        sources.append({**source, "content": content})
                    bodies[kind].append({"pin": deepcopy(item), "record": snapshot, "sources": sources})
            self.validate()
            return bodies

    def read_output(self, path):
        """GOV-01 file outputs use absolute pins; CORE-08 still confines reads."""
        self.validate()
        selected = Path(path)
        if not selected.is_absolute() or str(selected.resolve()) != str(selected):
            raise LearningError("Learning preparation output requires a canonical absolute path")
        try:
            relative = selected.relative_to(self.project_root).as_posix()
        except ValueError as error:
            raise LearningError("Learning output escapes installed project") from error
        reader = RepositoryReader(self.project_root, self.limits)
        raw = reader.read(relative).encode("utf-8")
        charge(raw)
        return raw


class LearningReviewInterface:
    """Explicit opt-in review of one complete declared learning output.

    The preparation Task Contract must pin this file through ordinary GOV-01
    output verification. This port grants no approval and performs no writes.
    """
    def __init__(self, installation, output_path):
        if type(installation) is not LearningInstallation:
            raise LearningError("Canonical review learning installation required")
        self.installation, self.output_path = installation, str(Path(output_path))
        self._binding = (installation, self.output_path)

    def evidence(self, job, request):
        with learning_inspection():
            if type(self) is not LearningReviewInterface or self._binding != (self.installation, self.output_path):
                raise LearningError("Review learning installation changed")
            self.installation.validate()
            if job.get("project_id") != self.installation.project_id or request.project_id != self.installation.project_id:
                raise LearningError("Foreign learning preparation review")
            c = job["task_contract"]
            raw = self.installation.read_output(self.output_path)
            value = LearningIntent.from_dict(json.loads(raw, object_pairs_hook=_object)).to_dict()
            if (not any(r["ref_type"] == "file" and r["ref"] == self.output_path for r in c["expected_outputs"])
                    or not any(e["path"] == self.output_path and e["sha256"] == hashlib.sha256(raw).hexdigest()
                               for e in c["required_evidence"])
                    or value["genesis"]["project_id"] != self.installation.project_id
                    or value["genesis"]["project_root"] != str(self.installation.project_root)):
                raise LearningError("Unpinned or foreign learning review output")
            bodies = self.installation.check_evidence(value["proposal"], now=datetime.now(timezone.utc).isoformat())
            return value, {"ref_type": "file", "ref": self.output_path}, review_content(value, bodies)


def overlap(left, right):
    # Conservative: different conditions/exclusions cannot prove disjointness.
    return all(set(left[n]) & set(right[n]) for n in ("tasks", "workflows", "agents", "capabilities"))


def transition_heads(i, before):
    """One shared transition validator for request, resolution and application."""
    number(before["revision"], minimum=0)
    revision = before["revision"] + 1
    if revision > MAX_TRANSITIONS:
        raise LearningError("Disposition transition capacity exhausted")
    heads = deepcopy(before["heads"])
    p, prior = i["proposal"], i["predecessor"]
    if prior is not None:
        actual = heads.get(prior["constraint_id"])
        if actual is None or actual["state"] != "PROMOTED" or any(actual[k] != v for k, v in prior.items()):
            raise LearningError("Disposition predecessor is stale or not promoted")
        heads[prior["constraint_id"]] = {**actual, "state": "REVOKED" if i["operation"] == "REVOKE" else "SUPERSEDED"}
    if i["operation"] != "REVOKE":
        existing = before["heads"].get(p["constraint_id"])
        if existing is not None and (p["version"] <= existing["version"]
                or (existing["state"] == "PROMOTED" and (i["operation"] != "SUPERSEDE"
                    or prior["constraint_id"] != p["constraint_id"]))):
            raise LearningError("Terminal version cannot reactivate; competing successor denied")
        heads[p["constraint_id"]] = {"constraint_id": p["constraint_id"], "version": p["version"],
            "state": "PROMOTED", "revision": revision}
    if len(heads) > MAX_LINEAGES:
        raise LearningError("Constraint lineage capacity exhausted")
    return heads


@dataclass(frozen=True, slots=True)
class PlanningRequest:
    project_id: str
    project_root: str
    task: str
    workflow: str
    agent: str
    capability: str
    conditions: tuple[str, ...] = ()

    def to_dict(self):
        from dataclasses import asdict
        value = asdict(self)
        if type(self) is not PlanningRequest or type(self.conditions) is not tuple or len(self.conditions) > MAX_ITEMS:
            raise LearningError("Canonical bounded planning request required")
        for name in ("project_id", "task", "workflow", "agent", "capability"):
            text(value[name])
        text(self.project_root, 2000)
        for condition in self.conditions:
            text(condition, 4096)
        value["conditions"] = list(self.conditions)
        return value


@dataclass(frozen=True, slots=True)
class PlanningProjection:
    canonical: str

    def to_dict(self):
        value = json.loads(self.canonical, object_pairs_hook=_object)
        fields(value, "request genesis_digest index_digest revision constraints")
        encoded(value)
        return deepcopy(value)


class ForegroundLearningInterface:
    """Manager must revalidate immediately before plan acceptance and every reuse."""
    def __init__(self, approval_runtime):
        from runtime.approvals.runtime import ApprovalRuntime
        if type(approval_runtime) is not ApprovalRuntime or approval_runtime.learning is None:
            raise LearningError("Explicit canonical learning owner required")
        self.owner = approval_runtime

    def select(self, request):
        if type(request) is not PlanningRequest:
            raise LearningError("Exact planning request required")
        request.to_dict()
        install = self.owner.learning
        if request.project_id != install.project_id or request.project_root != str(install.project_root):
            raise LearningError("Foreign planning project/root")
        state = self.owner.inspect_learning()
        selected = []
        for item in state["eligible"]:
            scope = item["proposal"]["applicability"]
            if (all(getattr(request, n) in scope[selector] for n, selector in
                    (("task", "tasks"), ("workflow", "workflows"), ("agent", "agents"), ("capability", "capabilities")))
                    and set(scope["conditions"]) <= set(request.conditions)
                    and not set(scope["exclusions"]) & set(request.conditions)):
                selected.append(item)
        return PlanningProjection(encoded({"request": request.to_dict(),
            "genesis_digest": state["index"]["genesis_digest"], "index_digest": digest(state["index"]),
            "revision": state["index"]["revision"], "constraints": selected}).decode("utf-8"))

    def revalidate(self, request, projection):
        if type(projection) is not PlanningProjection or self.select(request) != projection:
            raise LearningError("Planning projection changed; Manager reassessment required")
        return projection
