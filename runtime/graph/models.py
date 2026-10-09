"""Immutable graph topology and exact child work, never permission grants."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from runtime.core.task_contract import TaskContractError, contract_validator, digest, encoded, validate
from runtime.core.validation import JobValidator


class GraphError(TaskContractError):
    """Graph work or persisted admission cannot be validated."""


DETERMINISTIC_KINDS = frozenset({"deterministic", "merge", "fan_out", "fan_in"})
ACTIVE = frozenset({"created", "queued", "running", "reviewing", "waiting_approval"})
TERMINAL = frozenset({"completed", "failed", "cancelled"})
INHERITED = ("task_class", "project_id", "agent", "skill", "workflow", "capability",
             "provider", "risk_level", "review_required", "execution_mode",
             "execution_scope", "dry_run", "compute_requirements", "max_attempts")


@lru_cache(maxsize=1)
def validator():
    return JobValidator(Path(__file__).resolve().parents[2] / "schemas/graph-plan.schema.json")



# Only immutable structural proofs live here; no jobs or authority decisions.
_PLAN_SCOPE = ContextVar("orch01_preflight_plan_structure", default=None)


@contextmanager
def preflight_plan_scope(store_root, root_job_id):
    memo = {"owner": (str(Path(store_root).resolve()), root_job_id)}
    token = _PLAN_SCOPE.set(memo)
    try:
        yield
    finally:
        memo.clear()
        _PLAN_SCOPE.reset(token)


def _schema_identity():
    """Read transitive schema bytes afresh before any structural proof reuse."""
    main = validator().schema_path
    allowed = main.parent.resolve()
    pending, seen, identities = [main], set(), []
    loaded = {main.resolve(): validator().schema,
              contract_validator().schema_path.resolve(): contract_validator().schema}
    while pending:
        path = pending.pop().resolve()
        try:
            path.relative_to(allowed)
        except ValueError as error:
            raise GraphError("Graph schema reference escapes its canonical directory") from error
        if path in seen:
            continue
        seen.add(path)
        if len(seen) > 256:
            raise GraphError("Graph schema identity exceeds bounded structural scope")
        try:
            raw = path.read_bytes()
            document = json.loads(raw)
        except (OSError, ValueError, RecursionError) as error:
            raise GraphError("Graph schema identity is missing or malformed") from error
        if path in loaded and document != loaded[path]:
            raise GraphError("Graph schema differs from the loaded canonical validator")
        identities.append((str(path), hashlib.sha256(raw).digest()))
        def references(value):
            if isinstance(value, dict):
                ref = value.get("$ref")
                if isinstance(ref, str) and ref.partition("#")[0]:
                    pending.append(path.parent / ref.partition("#")[0])
                for child in value.values():
                    references(child)
            elif isinstance(value, list):
                for child in value:
                    references(child)
        references(document)
    return tuple(sorted(identities))


def _structural_key(value):
    memo = _PLAN_SCOPE.get()
    if memo is None:
        return None
    return memo["owner"], encoded(value, max_bytes=256 * 1024), _schema_identity()


def _plan_schema(value, check):
    memo = _PLAN_SCOPE.get()
    key = _structural_key(value)
    if key is not None and memo.get("schema") == key:
        return
    check()
    if key is not None:
        memo["schema"] = key


def reuse_root_plan_schema(owner, value, schema, root, schema_path):
    """Narrow hook for the immutable plan field, never the parent envelope."""
    memo = _PLAN_SCOPE.get()
    if (memo is None or root.get("job_id") != memo["owner"][1]
            or schema != {"$ref": "graph-plan.schema.json"}
            or owner.schema_path.resolve() != validator().schema_path.parent.resolve() / "job.schema.json"):
        return False
    _plan_schema(value, lambda: owner._validate(value, schema, "$.graph_plan", root, schema_path))
    return True


def plan(value):
    key = _structural_key(value)
    memo = _PLAN_SCOPE.get()
    if key is not None and memo.get("semantic") == key:
        return json.loads(memo["normalized"])
    result = _plan(value)
    if key is not None:
        memo["semantic"] = key
        memo["normalized"] = encoded(result, max_bytes=256 * 1024)
    return result


def _plan(value):
    # Bounded canonical serialization occurs before semantic traversal/copy.
    encoded(value, max_bytes=256 * 1024)
    try:
        _plan_schema(value, lambda: validator().validate(value))
    except (ValueError, RecursionError, TypeError) as error:
        raise GraphError("Invalid bounded graph schema") from error
    nodes = {n["node_id"]: n for n in value["nodes"]}
    if len(nodes) != len(value["nodes"]):
        raise GraphError("Duplicate graph node identity")
    for node in nodes.values():
        if not set(node["depends_on"]) <= nodes.keys() or node["node_id"] in node["depends_on"]:
            raise GraphError("Missing dependency or self dependency")
        if node["kind"] in DETERMINISTIC_KINDS:
            if node["profile"] != "deterministic" or "operation" not in node:
                raise GraphError("Deterministic nodes require a deterministic operation/profile")
        elif "operation" in node:
            raise GraphError("Provider/profile node cannot specify deterministic operation")
        if node["kind"] in {"planner", "splitter"} and node["profile"] != node["kind"]:
            raise GraphError("Planner/splitter profile mismatch")
        if node["kind"] == "gate" and node["profile"] != "critic":
            raise GraphError("Review gates require the critic profile")
        validate(node["payload"]["task_contract"])
    remaining, ordered = set(nodes), []
    while remaining:
        ready = sorted(n for n in remaining if set(nodes[n]["depends_on"]) <= set(ordered))
        if not ready:
            raise GraphError("Normal dependency cycle")
        ordered.extend(ready)
        remaining.difference_update(ready)
    sources, targets = set(), set()
    for edge in value["edges"]:
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise GraphError("Missing correction/replan endpoint")
        if edge["source"] in sources or edge["target"] in targets:
            raise GraphError("Ambiguous recovery route")
        if nodes[edge["target"]]["depends_on"]:
            raise GraphError("Recovery entry must be a separate task unit without normal dependencies")
        sources.add(edge["source"]); targets.add(edge["target"])
    # Canonical ordering makes reconstruction and ready selection stable.
    result = deepcopy(value)
    result["nodes"] = [deepcopy(nodes[n]) for n in ordered]
    result["edges"] = sorted(result["edges"], key=lambda e: (e["source"], e["target"], e["kind"]))
    return result


def node_id(root_id, node_name):
    return "job-graph-" + digest([root_id, node_name])[:32]


def execution_gate(job):
    """Effective canonical requirement, including a stronger approval handoff."""
    return (job["task_contract"]["approval_requirements"]["execution"]
            or job["approval_status"] != "not_required"
            or job.get("approval", {}).get("requested_action") in {"EXECUTE_JOB", "RESOLVE_HUMAN_CONDITION"})


def parent_gate_pending(job):
    return (execution_gate(job) and job["approval_status"] != "approved"
            or job["status"] in {"waiting_approval", "reviewing"})


def child_payload(root, node, dependencies=(), recovery_source=None):
    """Resolve explicit child acceptance against the unchanged parent's ceiling."""
    payload = {k: deepcopy(root[k]) for k in INHERITED if k in root}
    payload.update(deepcopy(node["payload"]))
    c = payload["task_contract"]
    # Null is the explicit graph-template placeholder for the parent-owned budget.
    if c["budget_references"] not in (None, root.get("execution_budget")):
        raise GraphError("Graph template attempts to replace the parent budget")
    payload["execution_budget"] = deepcopy(root["execution_budget"])
    c["budget_references"] = deepcopy(root["execution_budget"])
    inputs = deepcopy(payload.get("input_refs", root["input_refs"]))
    if any(ref not in root["input_refs"] for ref in inputs):
        raise GraphError("Node input scope exceeds parent inputs")
    if c["objective"] != payload["task"] or c["inputs"] != inputs:
        raise GraphError("Explicit node contract does not match its exact task/inputs")
    if "compute_requirements" in node["payload"] and payload["compute_requirements"] != root.get("compute_requirements", {}):
        raise GraphError("Node cannot reinterpret parent's compute requirements")
    if node["kind"] == "human_gate" and not c["approval_requirements"]["execution"]:
        raise GraphError("Human gate lacks an explicit execution approval requirement")
    if node["kind"] == "gate" and not c["approval_requirements"]["review"]:
        raise GraphError("Review gate lacks the canonical review requirement")
    if node["kind"] in DETERMINISTIC_KINDS and payload["execution_mode"] != "READ_ONLY":
        raise GraphError("Deterministic graph operations are read-only")
    if node["kind"] in DETERMINISTIC_KINDS:
        c["allowed_tools"] = [tool for tool in c["allowed_tools"] if tool == "local_executor"]
    # Templates never override stronger verified owner decisions. New exact work
    # inherits requirements, never the source's approval/review receipt.
    for authority in (root, *((recovery_source,) if recovery_source else ())):
        gates = authority["task_contract"]["approval_requirements"]
        for gate, required in gates.items():
            c["approval_requirements"][gate] |= required
        c["approval_requirements"]["execution"] |= execution_gate(authority)
        c["approval_requirements"]["review"] |= authority["review_required"]
    if recovery_source is not None:
        if any(ref not in recovery_source["input_refs"] for ref in inputs):
            raise GraphError("Recovery target input scope exceeds its failed source")
        for stop in recovery_source["task_contract"]["stop_conditions"]:
            if stop not in c["stop_conditions"]:
                c["stop_conditions"].append(deepcopy(stop))
    for dependency in (*dependencies, *((recovery_source,) if recovery_source else ())):
        for ref in dependency["output_refs"]:
            if ref not in inputs:
                inputs.append(deepcopy(ref))
    payload["input_refs"] = inputs
    c["inputs"] = deepcopy(inputs)
    payload["approval_status"] = "required" if c["approval_requirements"]["execution"] else "not_required"
    payload["review_required"] = payload.get("review_required", False) or c["approval_requirements"]["review"]
    payload["output_refs"] = []
    payload["created_by"] = "graph:" + root["job_id"] + ":" + node["node_id"]
    payload["graph_binding"] = {
        "root_job_id": root["job_id"], "plan_digest": digest(root["graph_plan"]),
        "node_id": node["node_id"],
        "profile": node["profile"],
        "dependency_jobs": [d["job_id"] for d in dependencies],
        "recovery_source_job_id": recovery_source["job_id"] if recovery_source else None,
    }
    from runtime.core.capability_governance import require_child
    require_child(root, payload)
    if recovery_source is not None:
        require_child(recovery_source, payload)
    return payload


def validate_root(root, *, validate_children=True):
    if "graph_binding" in root or root.get("continuation_plan") is not None:
        raise GraphError("Graph roots cannot be nested or linear continuation steps")
    value = plan(root["graph_plan"])
    if value != root["graph_plan"]:
        raise GraphError("Graph plan must use canonical dependency order")
    if root.get("execution_budget") is None:
        raise GraphError("Graph requires a shared canonical execution budget")
    if validate_children:
        for node in value["nodes"]:
            child_payload(root, node)
    return value
