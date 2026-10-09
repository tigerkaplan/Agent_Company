"""Graph readiness/admission over canonical jobs, claims and retry decisions.

The graph owns topology only. Jobs own mutable state; Workers own execution;
RetryRuntime owns repair/stop; ApprovalRuntime and ReviewerRuntime own gates.
"""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from copy import deepcopy

from runtime.core.task_contract import digest, validate_binding
from runtime.graph.models import (ACTIVE, DETERMINISTIC_KINDS, GraphError,
                                 child_payload, node_id, parent_gate_pending, validate_root)
from runtime.storage.file_store import ClaimLockTimeout


_PROOF_TRAVERSAL = ContextVar("orch01_bounded_proof_traversal", default=None)


def persisted_decision(jobs, failed):
    """Read a verified canonical retry decision, without creating one."""
    return jobs.retry_runtime.persisted_decision(failed)


def _parent_approval(jobs, root, *, admitted=False):
    if admitted and parent_gate_pending(root):
        raise GraphError("Graph parent has an unresolved canonical approval/review gate")
    if root["approval_status"] == "approved" or (
            admitted and root["task_contract"]["approval_requirements"]["execution"]):
        from runtime.approvals.store import FileApprovalStore, ApprovalStoreError
        owner = jobs.approval_store or FileApprovalStore(jobs.store.root.parent / "approvals")
        try:
            owner.completion_evidence(root, None, None, execution_only=True)
        except ApprovalStoreError as error:
            raise GraphError("Graph parent approval evidence is unavailable or stale") from error


def _root(jobs, binding):
    root = jobs.store.load(binding["root_job_id"])
    jobs.validator.validate(root)
    jobs.task_contract_store.verify(root)
    validate_binding(root)
    validate_root(root, validate_children=False)
    _parent_approval(jobs, root, admitted=True)
    return root


def _recovery_source(jobs, root, node, binding):
    edges = [e for e in root["graph_plan"]["edges"] if e["target"] == node["node_id"]]
    source_id = binding["recovery_source_job_id"]
    if not edges:
        if source_id is not None:
            raise GraphError("Unexpected recovery source")
        return None
    if source_id is None:
        raise GraphError("Dormant recovery node cannot be admitted without a source")
    source = jobs.store.load(source_id)
    jobs.validator.validate(source)
    jobs.task_contract_store.verify(source)
    if (source.get("graph_binding", {}).get("root_job_id") != root["job_id"]
            or source.get("graph_binding", {}).get("node_id") != edges[0]["source"]
            or source["status"] != "failed"):
        raise GraphError("Recovery source is not the exact failed graph task unit")
    decision = persisted_decision(jobs, source)
    if decision is None or decision["decision"] != "REPLAN_REQUIRED":
        raise GraphError("Recovery edge requires canonical REPLAN_REQUIRED")
    return source


def _effective_names(plan, source):
    """Finite possible recovery substitutions; actual route is verified separately."""
    names = {source}
    current = source
    routes = {e["source"]: e["target"] for e in plan["edges"]}
    while current in routes and routes[current] not in names:
        current = routes[current]
        names.add(current)
    return names


def validate_graph_job(jobs, job, *, executing=False):
    """Each entry starts fresh; recursive reads share bounded traversal evidence.

    This memo exists only while this one validation call is on the stack. It
    never crosses admission, dispatch, tool effects, restart or continuation.
    Exact completed job bytes key each proof, and parent anchors/gates are read
    afresh. Duplicate ancestry is a DAG, not repeated execution or authority.
    """
    existing = _PROOF_TRAVERSAL.get()
    token = _PROOF_TRAVERSAL.set({"complete": set(), "visiting": set()}) if existing is None else None
    try:
        return _validate_graph_job(jobs, job, executing=executing)
    finally:
        if token is not None:
            _PROOF_TRAVERSAL.reset(token)


def _validate_graph_job(jobs, job, *, executing=False):
    if "graph_plan" in job:
        validate_root(job, validate_children=not jobs.store.exists(job["job_id"]))
        _parent_approval(jobs, job)
        if executing:
            raise GraphError("Graph root is a coordination envelope, not executable work")
        return
    binding = job.get("graph_binding")
    if binding is None:
        return
    root = _root(jobs, binding)
    if binding["plan_digest"] != digest(root["graph_plan"]):
        raise GraphError("Graph binding differs from immutable parent topology")
    nodes = {n["node_id"]: n for n in root["graph_plan"]["nodes"]}
    node = nodes.get(binding["node_id"])
    if node is None:
        raise GraphError("Undeclared graph node")
    if job.get("continuation_plan") is not None:
        raise GraphError("Graph units cannot silently create linear continuation children")
    if job.get("parent_job_id") is None and job["job_id"] != node_id(root["job_id"], node["node_id"]):
        raise GraphError("Graph node does not have its deterministic canonical identity")
    source = _recovery_source(jobs, root, node, binding)
    if len(binding["dependency_jobs"]) != len(node["depends_on"]):
        raise GraphError("Graph dependency receipt count mismatch")
    dependencies = []
    for name, job_id in zip(node["depends_on"], binding["dependency_jobs"]):
        dependency = jobs.store.load(job_id)
        receipt = dependency.get("graph_binding", {})
        if (receipt.get("root_job_id") != root["job_id"] or dependency["status"] != "completed"
                or receipt.get("node_id") not in _effective_names(root["graph_plan"], name)):
            raise GraphError("Graph fan-in requires exact accepted dependency work")
        # Verify task completion, persisted execution/eval, review and human proof
        # through the existing job owner, not a graph-local success flag.
        traversal = _PROOF_TRAVERSAL.get()
        proof = (str(jobs.store.root.resolve()), job_id, digest(dependency))
        if proof in traversal["visiting"]:
            raise GraphError("Cyclic persisted completion proof")
        if proof not in traversal["complete"]:
            if len(traversal["complete"]) + len(traversal["visiting"]) >= 64 * 32:
                raise GraphError("Graph proof traversal exceeds its bounded allocation")
            traversal["visiting"].add(proof)
            try:
                jobs._validate(dependency)
            finally:
                traversal["visiting"].remove(proof)
            traversal["complete"].add(proof)
        # A correction is usable only if every intervening source actually failed
        # and the persisted target bound that source's canonical replan decision.
        current_name = receipt["node_id"]
        seen = set()
        current_job = dependency
        while current_name != name:
            if current_name in seen:
                raise GraphError("Cyclic dependency recovery receipt")
            seen.add(current_name)
            recovered = _recovery_source(jobs, root, nodes[current_name], current_job["graph_binding"])
            if recovered is None:
                raise GraphError("Dependency substitution lacks the declared failed source")
            current_job = recovered
            current_name = recovered["graph_binding"]["node_id"]
        dependencies.append(dependency)
    expected = child_payload(root, node, dependencies, source)
    # Retry lineage retains this exact original admission; only retry mechanics
    # and lifecycle-owned fields differ. Strengthened review is allowed by GOV-01.
    for field, value in expected.items():
        if field in {"created_by", "output_refs", "approval_status"}:
            continue
        if field == "review_required" and job[field] is True and value is False:
            continue
        if job.get(field) != value:
            raise GraphError("Graph node changed its declared work: " + field)
    from runtime.core.capability_governance import require_child
    require_child(root, job)
    if not jobs.store.exists(job["job_id"]):
        if root["status"] in {"failed", "cancelled"}:
            raise GraphError("Graph parent stopped node admission")
        validate_binding(root, now=jobs.clock(), executing=True)
        records = jobs.store.list()
        siblings = [r for r in records if r.get("graph_binding", {}).get("root_job_id") == root["job_id"]]
        if sum(r["status"] in ACTIVE for r in siblings) >= root["graph_plan"]["max_parallel"]:
            raise GraphError("Graph admission exceeds the canonical parallel bound")
        if source is not None and job.get("parent_job_id") is None:
            handoffs = sum(r.get("parent_job_id") is None and
                           r["graph_binding"]["recovery_source_job_id"] is not None for r in siblings)
            if handoffs >= root["graph_plan"]["max_handoffs"]:
                raise GraphError("Graph admission exceeds the declared recovery bound")
    if executing:
        if root["status"] in {"failed", "cancelled"}:
            raise GraphError("Graph parent revoked execution")
        validate_binding(root, now=jobs.clock(), executing=True)


def validate_executor(jobs, job, executor):
    binding = job.get("graph_binding")
    if not binding:
        return
    root = _root(jobs, binding)
    node = next(n for n in root["graph_plan"]["nodes"] if n["node_id"] == binding["node_id"])
    if node["kind"] in DETERMINISTIC_KINDS:
        from runtime.graph.executor import DeterministicGraphExecutor
        if type(executor) is not DeterministicGraphExecutor or executor.jobs is not jobs:
            raise GraphError("Deterministic graph node requires the canonical deterministic executor")


class GraphRuntime:
    def __init__(self, jobs, approvals):
        if approvals.job_runtime is not jobs:
            raise GraphError("Graph approvals must use the canonical job owner")
        self.jobs = jobs
        self.approvals = approvals

    def create(self, payload, graph_plan):
        from runtime.graph.models import plan
        value = deepcopy(payload)
        value["graph_plan"] = plan(graph_plan)
        return self.jobs.create(value)

    def _view(self, root, records):
        definition = root["graph_plan"]
        nodes = {n["node_id"]: n for n in definition["nodes"]}
        edges = {e["source"]: e["target"] for e in definition["edges"]}
        targets = set(edges.values())
        conditional = set(targets)
        for node in definition["nodes"]:
            if any(name in conditional for name in node["depends_on"]):
                conditional.add(node["node_id"])
        normal = set(nodes) - conditional
        latest, initial = {}, {}
        for job in records:
            binding = job.get("graph_binding", {})
            if binding.get("root_job_id") != root["job_id"]:
                continue
            name = binding["node_id"]
            if job.get("parent_job_id") is None:
                if name in initial:
                    raise GraphError("Duplicate persisted graph admission")
                initial[name] = job
            if name not in latest or job["attempt"] > latest[name]["attempt"]:
                latest[name] = job
        active = normal | set(initial)
        for node in definition["nodes"]:
            if node["node_id"] not in targets and all(name in active for name in node["depends_on"]):
                active.add(node["node_id"])
        handoffs = sum(j["graph_binding"]["recovery_source_job_id"] is not None for j in initial.values())
        ready, recovery_sources, failed, decisions = [], {}, [], {}
        loop = False

        def effective(name, seen=()):
            nonlocal loop
            if name in seen:
                loop = True
                return None
            job = latest.get(name)
            if job is None:
                return None
            if job["status"] == "completed":
                return job
            if job["status"] != "failed":
                return None
            if name not in decisions:
                decisions[name] = persisted_decision(self.jobs, job)
            decision = decisions[name]
            if decision is not None and decision["decision"] == "REPLAN_REQUIRED" and name in edges:
                target = edges[name]
                admitted = initial.get(target)
                if admitted is not None:
                    if admitted["graph_binding"]["recovery_source_job_id"] != job["job_id"]:
                        loop = True
                        return None
                    return effective(target, (*seen, name))
                if handoffs >= definition["max_handoffs"]:
                    failed.append(name)
                else:
                    recovery_sources[target] = job
                return None
            if decision is not None:
                failed.append(name)
            return None

        effective_jobs = {name: effective(name) for name in sorted(active)}
        for name, job in latest.items():
            if job["status"] == "cancelled":
                failed.append(name)
        for name in sorted(active | set(recovery_sources)):
            if name in latest:
                continue
            if name in targets and name not in recovery_sources:
                continue
            dependency_jobs = [effective_jobs.get(d) for d in nodes[name]["depends_on"]]
            if all(d is not None for d in dependency_jobs):
                ready.append((nodes[name], dependency_jobs, recovery_sources.get(name)))
        busy = sum(job["status"] in ACTIVE for job in latest.values())
        if busy > definition["max_parallel"] or handoffs > definition["max_handoffs"]:
            raise GraphError("Persisted graph exceeds its immutable admission bounds")
        if root["status"] in {"failed", "cancelled"} or root["approval_status"] == "denied":
            status, reason = "cancelled", "parent_stopped"
        elif loop or not normal:
            status, reason = "failed", "replan_cycle"
        elif failed:
            status, reason = "failed", "branch_stopped_or_handoff_bound"
        elif parent_gate_pending(root):
            status, reason = "waiting_approval", "parent_approval_required"
        elif all(effective_jobs.get(name) is not None for name in active):
            status, reason = "completed", "accepted_nodes"
        elif any(j["status"] == "waiting_approval" for j in latest.values()):
            status, reason = "waiting_approval", "node_approval_required"
        elif any(j["status"] == "reviewing" for j in latest.values()):
            status, reason = "reviewing", "canonical_review_required"
        else:
            status, reason = "running", "bounded_work"
        if status in {"failed", "cancelled", "completed"} or reason == "parent_approval_required":
            ready = []
        return {"root_job_id": root["job_id"], "plan_digest": digest(definition),
                "status": status, "reason": reason, "busy": busy, "handoffs": handoffs,
                "nodes": {name: {"status": latest[name]["status"] if name in latest else
                                   ("pending" if name in active else "dormant"),
                                   "job_id": latest[name]["job_id"] if name in latest else None}
                          for name in sorted(nodes)},
                "ready": ready, "latest": latest}

    def show(self, root_job_id):
        root = self.jobs.show(root_job_id)
        if "graph_plan" not in root:
            raise GraphError("Job is not a graph root")
        view = self._view(root, self.jobs.list())
        return {k: deepcopy(v) for k, v in view.items() if k not in {"ready", "latest"}}

    def _request_or_queue(self, job):
        from runtime.core.jobs import ClaimContention, RuntimeError as JobError
        from runtime.approvals.runtime import ApprovalRuntimeError
        try:
            return self._finish_created(job)
        except (JobError, ApprovalRuntimeError) as error:
            # Another canonical writer may have completed this same lifecycle
            # handoff after our read. Accept only a revalidated later state.
            current = self.jobs.show(job["job_id"])
            if isinstance(error, ClaimContention) or isinstance(error.__cause__, ClaimContention):
                return current
            if current["status"] != job["status"] and current["status"] != "created":
                return current
            raise

    def _finish_created(self, job):
        if job["status"] == "created":
            if job["approval_status"] == "required":
                return self.approvals.request_execution(job["job_id"], reason="Exact graph node requires human execution approval").job
            return self.jobs.enqueue(job["job_id"])
        if job["status"] == "waiting_approval" and job["approval_status"] == "required":
            return self.approvals.request_execution(job["job_id"], reason="Resume exact graph approval boundary").job
        return job

    def advance(self, root_job_id):
        """One bounded coordination tick; providers are never called here."""
        from runtime.core.jobs import BudgetContention, ClaimContention
        try:
            self.jobs.reconcile_progress()
        except ClaimContention:
            return self.show(root_job_id)
        root = self.jobs.show(root_job_id)
        if "graph_plan" not in root:
            raise GraphError("Job is not a graph root")
        if root["status"] in {"failed", "cancelled"}:
            return self.show(root_job_id)
        if parent_gate_pending(root):
            if root["status"] == "created":
                self.approvals.request_execution(root_job_id, reason="Graph parent ceiling requires human approval")
            return self.show(root_job_id)
        view = self._view(root, self.jobs.list())
        # Canonical retry owns every local retry and stop/replan decision.
        if view["status"] not in {"failed", "cancelled", "completed"}:
            for job in view["latest"].values():
                if job["status"] == "failed" and persisted_decision(self.jobs, job) is None:
                    try:
                        self.jobs.retry_or_stop(job["job_id"])
                    except (ClaimContention, BudgetContention):
                        return self.show(root_job_id)
            view = self._view(root, self.jobs.list())
            for job in view["latest"].values():
                if job["status"] in {"created", "waiting_approval"}:
                    self._request_or_queue(job)
        # Node admission and capacity checks share the canonical cross-process
        # claim transaction. No graph lock or separate scheduler is introduced.
        try:
            with self.jobs.store.claim_transaction(timeout_seconds=30.0):
                root = self.jobs.show(root_job_id)
                view = self._view(root, self.jobs.list())
                capacity = max(0, root["graph_plan"]["max_parallel"] - view["busy"])
                for node, dependencies, source in view["ready"][:capacity]:
                    payload = child_payload(root, node, dependencies, source)
                    job_id = node_id(root_job_id, node["node_id"])
                    self.jobs._create_attempt(payload, attempt=1, parent_job_id=None, job_id_override=job_id)
        except ClaimLockTimeout:
            # No lock means no admission. The next tick revalidates the same
            # deterministic identities through the canonical claim owner.
            return self.show(root_job_id)
        # Approval/lifecycle transitions use their own canonical owners/locks.
        view = self._view(self.jobs.show(root_job_id), self.jobs.list())
        if view["status"] not in {"failed", "cancelled", "completed"}:
            for job in view["latest"].values():
                if job["status"] in {"created", "waiting_approval"}:
                    self._request_or_queue(job)
        return self.show(root_job_id)

    def run_ready(self, root_job_id, worker_factory):
        """Execute the currently admitted batch through bounded canonical Workers.

        Factory receives an isolated node and job copy. It must return a distinct
        Worker per task with the same canonical job and execution-store owners.
        Calling this method again delivers existing state, not duplicate work.
        """
        self.advance(root_job_id)
        root = self.jobs.show(root_job_id)
        view = self._view(root, self.jobs.list())
        if view["status"] in {"failed", "cancelled", "completed"} or parent_gate_pending(root):
            return []
        nodes = {n["node_id"]: n for n in root["graph_plan"]["nodes"]}
        work = []
        worker_ids = set()
        execution_store = self.jobs.execution_store
        if execution_store is None:
            raise GraphError("Graph batch requires a configured canonical execution store")
        for name, job in sorted(view["latest"].items()):
            if job["status"] != "queued":
                continue
            worker = worker_factory(deepcopy(nodes[name]), deepcopy(job))
            if worker.runtime is not self.jobs or worker.worker_id in worker_ids:
                raise GraphError("Parallel graph work requires distinct canonical Workers")
            if execution_store is not worker.execution_store:
                raise GraphError("Graph Worker must use the canonical execution store")
            validate_executor(self.jobs, job, worker.executor)
            worker_ids.add(worker.worker_id)
            work.append((job, worker))

        # Reserve existing canonical leases before competing with worker intent
        # and budget validation. Providers still run in parallel; every Worker
        # reloads its exact live claim before use. This list grants no authority.
        from runtime.core.jobs import ClaimContention
        claimed = []
        for pair in work:
            job, worker = pair
            try:
                claim = self.jobs.claim(claimed_by=worker.worker_id,
                                        lease_seconds=worker.lease_seconds, job_id=job["job_id"],
                                        lock_timeout_seconds=30.0)
            except ClaimContention:
                # Bounded contention leaves this exact job queued; never run a
                # stale copy or retry a reserved/consumed execution identity.
                continue
            if claim is not None:
                claimed.append((claim["job_id"], worker))

        def execute(pair):
            job_id, worker = pair
            return worker.run_claimed(job_id)

        with ThreadPoolExecutor(max_workers=root["graph_plan"]["max_parallel"]) as pool:
            return list(pool.map(execute, claimed))

    def recover(self, root_job_id, worker):
        """Explicit restart recovery via existing execution/retry/lease owners."""
        from runtime.core.jobs import BudgetContention, ClaimContention
        if worker.runtime is not self.jobs:
            raise GraphError("Recovery requires the canonical Worker")
        try:
            self.jobs.reconcile_progress()
            budgets = worker.recover_budget_state()
            if any(decision.status == "ERROR" for decision in budgets):
                root = self.jobs.show(root_job_id)
                if worker.budget_runtime.state(root["execution_budget"]).status == "ERROR":
                    for job in self.jobs.list(status="running"):
                        if job.get("graph_binding", {}).get("root_job_id") != root_job_id:
                            continue
                        if worker.execution_store.find_for_job(job["job_id"]) is None:
                            # Preserve the explicit integrity denial for unstarted
                            # claims. Pending immutable results retain F3's hold;
                            # neither path releases a claim or creates completion.
                            raise GraphError("Unstarted graph recovery cannot trust budget accounting")
            if any(decision.status in {"DEFER", "ERROR"} for decision in budgets):
                # Persisted results and continuation wait for their existing
                # budget owner. Available-looking capacity grants no recovery.
                return self.show(root_job_id)
            results = worker.recover_persisted_results()
            if any(outcome.budget is not None and outcome.budget["status"] in {"DEFER", "ERROR"}
                   for outcome in results):
                # Finalization can discover an accounting fault after the first
                # recovery check. Keep downstream recovery behind that same gate.
                return self.show(root_job_id)
            self.jobs.recover_unstarted_graph_claims(root_job_id)
            worker.continuation_runtime.recover()
            from runtime.scheduler.loop import SchedulerConfig
            self.jobs.recover_expired_claims(backoff_seconds=SchedulerConfig().retry_backoff_seconds)
            return self.advance(root_job_id)
        except (BudgetContention, ClaimContention):
            return self.show(root_job_id)
