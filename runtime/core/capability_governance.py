"""GOV-02 deterministic certification ceilings; never an approval owner."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import json
import hashlib
import re
from pathlib import Path

from runtime.core.task_contract import TaskContractError, digest

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "governance/capability-governance/certifications.json"
PROFILES = ("READ_ONLY", "LOCAL_WRITE", "EXTERNAL_PREPARE", "EXTERNAL_EXECUTE", "SENSITIVE_EXECUTE")
_DISPATCH = ContextVar("gov02_exact_dispatch", default=None)
_IMPLEMENTATION_DIGEST = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
_SOURCE_FILES = (
    "CONSTITUTION.md", "AGENTS.md", "schemas/task-contract.schema.json",
    "schemas/capability-certification.schema.json", "runtime/core/capability_governance.py",
    "runtime/core/capability_actions.py", "orchestrator/routing/capabilities.yaml",
    "runtime/core/task_contract.py", "runtime/core/jobs.py", "runtime/approvals/store.py",
    "runtime/approvals/runtime.py", "runtime/review/context.py", "runtime/review/verification.py",
    "runtime/actions/runtime.py", "runtime/storage/execution_store.py",
    "runtime/review/reviewers.py", "runtime/review/runtime.py", "runtime/review/store.py",
    "runtime/workers/worker.py", "runtime/git/runtime.py", "runtime/git/remote_runtime.py",
)


def _source_hash(name):
    try:
        return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    except OSError:
        return None


# Evidence of loaded policy sources, not an approval/cache policy owner.
_SOURCE_IMPLEMENTATION_DIGESTS = {name: _source_hash(name) for name in _SOURCE_FILES}


@contextmanager
def certified_dispatch(store, request, *, purpose="execute"):
    """A context carries verified canonical evidence, never self-issued approval."""
    intent = store._decision_pair(request.execution_id, "intent")
    store._verify_intent(intent)
    if intent["request_digest"] != digest(request.to_dict()):
        raise TaskContractError("Dispatch differs from persisted certified decision")
    if purpose not in {"execute", "review"}:
        raise TaskContractError("Unknown certified dispatch purpose")
    if purpose == "execute":
        store._verify_live_dispatch(intent)
    # A durable consumed dispatch cannot be entered again after a crash/restart.
    claim = {"schema_version": 1, "intent_digest": digest(intent), "purpose": purpose}
    _consume(store, intent, "dispatch-" + purpose, claim)
    token = _DISPATCH.set((store, request.to_dict(), purpose))
    try:
        yield
    finally:
        _DISPATCH.reset(token)


def consume_effect(request, tool):
    require_dispatch(request)
    value = _DISPATCH.get()
    if value is None:
        raise TaskContractError("Effect requires certified dispatch evidence")
    store, parent, purpose = value
    if request.to_dict() != parent or purpose != "execute":
        raise TaskContractError("Delegated review cannot consume parent effect authority")
    intent = store._decision_pair(request.execution_id, "intent")
    _consume(store, intent, "effect-" + tool, {
        "schema_version": 1, "request_digest": digest(parent), "tool": tool})


def require_effect(request, tool):
    """Consumed evidence remains mandatory at the actual mutation boundary."""
    require_dispatch(request)
    store, parent, purpose = _DISPATCH.get()
    if purpose != "execute" or parent != request.to_dict():
        raise TaskContractError("Effect evidence is outside exact parent execution")
    store.verify_effect(store._decision_pair(request.execution_id, "intent"), tool)


def _consume(store, intent, stage, claim):
    from runtime.progress.store import ProgressStore
    from runtime.storage.execution_store import ExecutionStoreError
    source = intent["authority_source"]
    identity = "consumed-" + digest({"execution_id": intent["request"]["execution_id"], "stage": stage})
    history = ProgressStore(Path(source["progress_store_root"])).read(source["logical_job_id"])
    if any(e.event_type == "decision_consumption_observed" and e.execution_id == identity for e in history):
        raise ExecutionStoreError("Certified dispatch/effect already consumed; replay denied")
    store._observe(intent, "decision_consumption_observed", identity, digest(claim))
    store._decision_pair(intent["request"]["execution_id"], stage, claim)


def dispatch_intent():
    value = _DISPATCH.get()
    if value is None:
        return None
    store, parent, purpose = value
    return store._decision_pair(parent["execution_id"], "intent")


def require_review_dispatch(request):
    value = _DISPATCH.get()
    if value is None:
        raise TaskContractError("Review requires persisted certified parent dispatch")
    store, parent, purpose = value
    if purpose != "review" or parent != request.to_dict():
        raise TaskContractError("Review is outside its exact certified parent execution")
    intent = store._decision_pair(parent["execution_id"], "intent")
    store._verify_intent(intent)
    store._verify_consumption(intent, "dispatch-review", {
        "schema_version": 1, "intent_digest": digest(intent), "purpose": "review"})


def require_dispatch(request):
    value = _DISPATCH.get()
    if value is None:
        raise TaskContractError("Execution requires persisted certified dispatch")
    store, parent, purpose = value
    intent = store._decision_pair(parent["execution_id"], "intent")
    store._verify_intent(intent)
    store._verify_consumption(intent, "dispatch-" + purpose, {
        "schema_version": 1, "intent_digest": digest(intent), "purpose": purpose})
    child = request.to_dict()
    if purpose == "execute":
        store._verify_live_dispatch(store._decision_pair(parent["execution_id"], "intent"))
    if purpose == "review" and (child == parent or child["capability"] != "independent_review" or child["execution_mode"] != "READ_ONLY"):
        raise TaskContractError("Reviewer cannot replay parent execution authority")
    if child != parent:
        if purpose != "review" or child["capability"] != "independent_review" or child["execution_mode"] != "READ_ONLY":
            raise TaskContractError("Dispatch exact-work substitution rejected")
        if (child["job_id"] != parent["job_id"] or child["project_id"] != parent["project_id"]
                or (child["agent"], child["skill"], child["workflow"]) != ("reviewer", "review", "review")
                or child["context_refs"]
                or child["task_contract"]["allowed_tools"] != ["provider_call"]
                or child["task_contract"]["allowed_capabilities"] != ["independent_review"]):
            raise TaskContractError("Reviewer task identity/scope exceeds certified parent")
        allowed = {(r.get("ref_type"), r.get("ref")) for r in parent["input_refs"]}
        # These are observations of this exact execution, never new task scope.
        allowed.update({("artifact", "runtime-execution:" + parent["execution_id"]),
                        ("provider_result", "runtime-provider-output:" + parent["execution_id"]),
                        ("artifact", "runtime-mutation:" + parent["execution_id"])})
        persisted = store._decision_pair(parent["execution_id"], "intent")
        allowed.update((r.get("ref_type"), r.get("ref"))
                       for r in persisted["authority_source"]["review_evidence_refs"])
        if any((r.get("ref_type"), r.get("ref")) not in allowed for r in child["input_refs"]):
            raise TaskContractError("Reviewer read scope exceeds exact parent evidence")
        require_child(parent, child)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TaskContractError("Duplicate certification policy field")
        result[key] = value
    return result


def policy():
    """Reload trusted policy every time; cached/model supplied policy cannot grant."""
    try:
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != _IMPLEMENTATION_DIGEST:
            raise TaskContractError("Governance implementation changed; process restart required")
        if (type(_SOURCE_IMPLEMENTATION_DIGESTS) is not dict
                or set(_SOURCE_IMPLEMENTATION_DIGESTS) != set(_SOURCE_FILES)
                or any(type(v) is not str or re.fullmatch(r"[a-f0-9]{64}", v) is None
                       for v in _SOURCE_IMPLEMENTATION_DIGESTS.values())):
            raise TaskContractError("Loaded policy provenance malformed; process restart required")
        actual_sources = {name: _source_hash(name) for name in _SOURCE_FILES}
        if actual_sources != _SOURCE_IMPLEMENTATION_DIGESTS:
            raise TaskContractError("Canonical policy implementation changed; process restart required")
        raw = POLICY.read_bytes()
        if len(raw) > 128 * 1024:
            raise TaskContractError("Certification policy exceeds bounds")
        value = json.loads(raw, object_pairs_hook=_object)
        from runtime.core.validation import JobValidator
        JobValidator(ROOT / "schemas/capability-certification.schema.json").validate(value)
        if (type(value) is not dict or set(value) != {"schema_version", "policy_id", "certificates"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["policy_id"] != "GOV-02-frozen-V1"
                or type(value["certificates"]) is not dict or not value["certificates"]):
            raise TaskContractError("Malformed certification policy")
        for capability, cert in value["certificates"].items():
            if (type(capability) is not str or not capability or len(capability) > 200
                    or type(cert) is not dict
                    or set(cert) != {"certificate_id", "profiles", "status", "evidence"}
                    or cert["certificate_id"] != "GOV-02:" + capability
                    or cert["status"] not in {"certified", "revoked"}
                    or type(cert["profiles"]) is not list or not cert["profiles"]
                    or any(type(p) is not str or p not in PROFILES for p in cert["profiles"])
                    or len(set(cert["profiles"])) != len(cert["profiles"])
                    or cert["evidence"] != "governance/capability-governance/README.md"):
                raise TaskContractError("Malformed capability certificate")
        return value
    except TaskContractError:
        raise
    except (OSError, ValueError, TypeError, RecursionError) as error:
        raise TaskContractError("Capability certification unavailable") from error


def profile(contract):
    explicit = contract.get("capability_profile")
    if explicit is not None:
        if type(explicit) is not str or explicit not in PROFILES:
            raise TaskContractError("Unknown capability profile")
        return explicit
    # Conservative classification of NEW declarations; historical anchors are
    # separately rejected. Delegation labels never certify external execution.
    if contract["write_scope"] is not None:
        return "SENSITIVE_EXECUTE" if contract["write_scope"].get("write_mode") == "CREATE_MODIFY_DELETE" else "LOCAL_WRITE"
    return "EXTERNAL_PREPARE" if contract["delegation_level"] == "L3" else "READ_ONLY"


def evaluate(job):
    c = job["task_contract"]
    selected = profile(c)
    catalog = policy()
    certificates = {}
    for capability in c["allowed_capabilities"]:
        cert = catalog["certificates"].get(capability)
        # Review is always a narrowed read-only delegation.
        needed = "READ_ONLY" if capability == "independent_review" and capability != job["capability"] else selected
        if cert is None or cert["status"] != "certified" or needed not in cert["profiles"]:
            raise TaskContractError("Uncertified capability/profile: " + capability)
        certificates[capability] = deepcopy(cert)
    level = int(c["delegation_level"][1])
    gates = c["approval_requirements"]
    write = job.get("execution_mode", "READ_ONLY") == "CONTROLLED_WRITE"
    if selected in {"READ_ONLY", "EXTERNAL_PREPARE"}:
        if write or c["write_scope"] is not None or c["blast_radius"] != "none" or c["reversibility"] != "no_side_effect":
            raise TaskContractError("Preparation/read profile cannot allocate side effects")
        if selected == "READ_ONLY" and level > 1 or selected == "EXTERNAL_PREPARE" and level != 3:
            raise TaskContractError("Profile exceeds delegation allocation")
    elif selected == "LOCAL_WRITE":
        if (not write or level < 2 or level > 3 or c["blast_radius"] != "local"
                or c["reversibility"] != "reversible"
                or c["write_scope"].get("write_mode") == "CREATE_MODIFY_DELETE"):
            raise TaskContractError("Local write profile understates authority/blast/reversibility")
    elif selected == "EXTERNAL_EXECUTE":
        # Frozen V1 has no general external action executor.
        raise TaskContractError("External execution has no certified action boundary")
    elif selected == "SENSITIVE_EXECUTE":
        if (not write or level != 5 or c["blast_radius"] != "local"
                or c["reversibility"] != "irreversible"
                or c["write_scope"].get("write_mode") != "CREATE_MODIFY_DELETE"):
            raise TaskContractError("Sensitive execution requires the controlled destructive-write boundary")
    if write and (not gates["execution"] or not gates["review"]):
        raise TaskContractError("Effectful profiles require human approval and independent review")
    sources = deepcopy(_SOURCE_IMPLEMENTATION_DIGESTS)
    return {"schema_version": 1, "policy_id": catalog["policy_id"],
            "policy_digest": digest(catalog), "policy_sources": sources,
            "profile": selected, "certificates": certificates,
            "contract_digest": digest(c), "risk": c["risk"],
            "blast_radius": c["blast_radius"], "reversibility": c["reversibility"],
            "approval_required": deepcopy(gates)}


def require_child(parent, child):
    """No widening transition is implemented; all delegation must narrow."""
    p, c = parent["task_contract"], child["task_contract"]
    evaluate(parent); evaluate(child)
    if child.get("project_id") != parent.get("project_id"):
        raise TaskContractError("Child project scope exceeds authorized parent")
    if (not set(c["allowed_tools"]) <= set(p["allowed_tools"])
            or not set(c["allowed_capabilities"]) <= set(p["allowed_capabilities"])
            or int(c["delegation_level"][1]) > int(p["delegation_level"][1])
            or PROFILES.index(profile(c)) > PROFILES.index(profile(p))
            or any(p["approval_requirements"][g] and not c["approval_requirements"][g]
                   for g in p["approval_requirements"])
            or c["budget_references"] != p["budget_references"]
            or any(s not in c["stop_conditions"] for s in p["stop_conditions"])):
        raise TaskContractError("Child capability authority exceeds authorized parent")
    # Canonical continuation inherits exact scope; Reviewer may remove it.
    if c["write_scope"] is not None and c["write_scope"] != p["write_scope"]:
        raise TaskContractError("Child write scope exceeds authorized parent")
    if (c["blast_radius"] not in ("none", p["blast_radius"])
            or c["reversibility"] not in ("no_side_effect", p["reversibility"])
            or c["risk"] != p["risk"]):
        raise TaskContractError("Child risk/blast/reversibility differs from parent allocation")


def decision(request, *, executor, authority_source, approvals=None):
    data = request.to_dict()
    evaluation = evaluate(data)
    return {"schema_version": 1, "requested_action": "EXECUTE",
            "request_digest": digest(data), "request": data,
            "policy_evaluation": evaluation, "authority_source": authority_source,
            "approval_required": evaluation["approval_required"],
            "approval_received": deepcopy(approvals or {}), "executor": executor}
