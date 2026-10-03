"""GOV-02 audit of existing, separately approved Git action transitions."""
from pathlib import Path
import hashlib

from runtime.core.capability_governance import evaluate, policy, _consume
from runtime.core.task_contract import TaskContractError, digest
from runtime.storage.execution_store import FileExecutionStore, ExecutionStoreError

_IMPLEMENTATION_DIGEST = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class ActionDecision:
    """Existing ApprovalRuntime owns authority; this class only constrains it."""
    ACTIONS = {
        "COMMIT_CHANGE_SET": ("LOCAL_WRITE", "local", "reversible", "commit_scope"),
        "PUSH_GIT_COMMIT": ("EXTERNAL_EXECUTE", "external", "irreversible", "remote_scope"),
        "CREATE_PULL_REQUEST": ("EXTERNAL_EXECUTE", "external", "irreversible", "remote_scope"),
    }

    def __init__(self, jobs, approvals, artifacts, approval, scope, executor):
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != _IMPLEMENTATION_DIGEST:
            raise TaskContractError("Action governance implementation changed; restart required")
        action = approval["requested_action"]
        if action not in self.ACTIONS:
            raise TaskContractError("Uncertified action transition")
        profile, blast, reversibility, scope_field = self.ACTIONS[action]
        canonical = approvals.load(approval["approval_id"], require_canonical=True).to_dict()
        if (canonical != approval or approval["status"] != "APPROVED"
                or approval["decision_actor_type"] != "local_operator"
                or approval[scope_field] != scope):
            raise TaskContractError("Action transition requires exact canonical human approval")
        job = jobs.show(approval["job_id"])
        if job["status"] != "completed" or not job["review_required"]:
            raise TaskContractError("Action transition requires independently reviewed completed work")
        base = evaluate(job)
        cert = policy()["certificates"].get(job["capability"])
        if cert is None or cert["status"] != "certified" or profile not in cert["profiles"]:
            raise TaskContractError("Uncertified capability/action profile")
        self.store = FileExecutionStore(artifacts.root)
        self.jobs, self.approvals = jobs, approvals
        self.identity = approval["approval_id"]
        self._attempted = False
        self.value = {
            "schema_version": 1, "requested_action": action,
            "request": {"execution_id": self.identity, "job_id": job["job_id"],
                        "action": action, "scope": scope},
            "request_digest": digest(scope),
            "policy_evaluation": {"parent": base, "profile": profile,
                                  "delegation_level": "L2" if profile == "LOCAL_WRITE" else "L4",
                                  "risk": "approval_required", "blast_radius": blast,
                                  "reversibility": reversibility, "certificate": cert},
            "authority_source": {"job_id": job["job_id"],
                "logical_job_id": jobs.progress.logical_id(job),
                "progress_store_root": str(jobs.progress.store.root.resolve()),
                "task_boundary_digest": digest(jobs.task_contract_store.boundary(job)),
                "task_store_root": str(jobs.task_contract_store.root.resolve()),
                "approval_store_root": str(approvals.root.resolve()),
                "transition": "separate-canonical-human-action-approval"},
            "approval_required": {"execution": True, "review": True},
            "approval_received": canonical, "executor": executor,
        }
        paths = [self.store._decision_path(self.identity, "action-policy", s) for s in ("anchor", "witness")]
        if any(p.exists() for p in paths):
            if self.store._decision_pair(self.identity, "action-policy") != self.value:
                raise ExecutionStoreError("Action certification/provenance is stale or tampered")
            self.store._verify_observation(self.value, "decision_intent_observed", self.identity, digest(self.value))
        else:
            history = jobs.progress.store.read(jobs.progress.logical_id(job))
            consumed_identity = "consumed-" + digest({"execution_id": self.identity, "stage": "action-effect"})
            failure_identity = "action-failure-" + digest(self.identity)
            if (any(e.execution_id in {self.identity, consumed_identity, failure_identity}
                    and e.event_type in {"decision_intent_observed", "decision_consumption_observed", "decision_result_observed"}
                    for e in history)
                    or any(self.store._decision_path(self.identity, stage, suffix).exists()
                           for stage in ("action-effect", "action-result", "action-failure")
                           for suffix in ("anchor", "witness"))):
                raise ExecutionStoreError("Missing action provenance; explicit recovery required")
            self.store._observe(self.value, "decision_intent_observed", self.identity, digest(self.value))
            self.store._decision_pair(self.identity, "action-policy", self.value)

    def consume(self):
        with self.jobs.progress.transition_lock():
            self._validate_current()
            consumed, terminal = self._retained_state()
            if consumed or terminal:
                raise ExecutionStoreError("Action work already attempted; no replay authority")
            self._attempted = True
            _consume(self.store, self.value, "action-effect", self._claim())

    def before_mutation(self):
        """Recheck original authority and consumed evidence at every Git effect."""
        self._validate_current()
        consumed, terminal = self._retained_state()
        if not consumed or terminal:
            raise ExecutionStoreError("Git mutation requires intact uncompleted action consumption")

    def _validate_current(self):
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != _IMPLEMENTATION_DIGEST:
            raise TaskContractError("Action governance implementation changed; restart required")
        if self.store._decision_pair(self.identity, "action-policy") != self.value:
            raise ExecutionStoreError("Action policy provenance changed before effect or acceptance")
        self.store._verify_observation(self.value, "decision_intent_observed", self.identity, digest(self.value))
        job = self.jobs.show(self.value["authority_source"]["job_id"])
        self.jobs.task_contract_store.verify(job)
        if (job["status"] != "completed" or not job["review_required"]
                or digest(self.jobs.task_contract_store.boundary(job)) != self.value["authority_source"]["task_boundary_digest"]
                or evaluate(job) != self.value["policy_evaluation"]["parent"]
                or self.approvals.load(self.identity, require_canonical=True).to_dict() != self.value["approval_received"]):
            raise TaskContractError("Action policy/authority changed before effect or evidence acceptance")

    def _claim(self):
        return {"schema_version": 1, "action_digest": digest(self.value)}

    def _history(self):
        from runtime.progress.store import ProgressStore
        source = self.value["authority_source"]
        return ProgressStore(Path(source["progress_store_root"])).read(source["logical_job_id"])

    def _retained_state(self):
        """Pairs and the canonical journal must agree; absence never refunds work."""
        history = self._history()
        consumed_identity = "consumed-" + digest({"execution_id": self.identity, "stage": "action-effect"})
        records = {}
        for stage, kind, identity in (
                ("action-effect", "decision_consumption_observed", consumed_identity),
                ("action-result", "decision_result_observed", self.identity),
                ("action-failure", "decision_result_observed", "action-failure-" + digest(self.identity))):
            if (any(self.store._decision_path(self.identity, stage, suffix).exists()
                    for suffix in ("anchor", "witness"))
                    or any(e.event_type == kind and e.execution_id == identity for e in history)):
                record = self.store._decision_pair(self.identity, stage)
                self.store._verify_observation(self.value, kind, identity, digest(record))
                records[stage] = record
        consumed = "action-effect" in records
        if consumed:
            self.store._verify_consumption(self.value, "action-effect", self._claim())
        if "action-failure" in records:
            failure = records["action-failure"]
            result = failure.get("result", {})
            import re
            if (type(result) is not dict or type(result.get("effect_may_be_partial")) is not bool
                    or type(result.get("error_code")) is not str
                    or re.fullmatch(r"[a-z_]{1,100}", result["error_code"]) is None
                    or failure != {"schema_version": 1, "policy_digest": digest(self.value),
                        "result": {"status": "FAILED", "error_code": result["error_code"],
                                   "effect_may_be_partial": consumed},
                        "evidence": {"approved_scope_digest": self.value["request_digest"]}}):
                raise ExecutionStoreError("Retained failure/consumption trace is inconsistent; recovery required")
        if "action-result" in records:
            result = records["action-result"]
            if (type(result.get("effect_performed")) is not bool
                    or result != {"schema_version": 1, "policy_digest": digest(self.value),
                        "result_digest": digest(result.get("evidence")), "effect_performed": consumed,
                        "evidence": result.get("evidence")}):
                raise ExecutionStoreError("Retained result/consumption trace is inconsistent; recovery required")
        return consumed, bool(records.keys() & {"action-result", "action-failure"})

    def fail(self, code):
        """Persist an observed failure without refunding effect authority."""
        import re
        if type(code) is not str or re.fullmatch(r"[a-z_]{1,100}", code) is None:
            code = "action_contract_failure"
        if self.store._decision_pair(self.identity, "action-policy") != self.value:
            raise ExecutionStoreError("Failure policy provenance is unavailable")
        history = self._history()
        consumed_identity = "consumed-" + digest({"execution_id": self.identity, "stage": "action-effect"})
        consumed = (self._attempted
                    or any(e.event_type == "decision_consumption_observed" and e.execution_id == consumed_identity for e in history)
                    or any(self.store._decision_path(self.identity, "action-effect", s).exists() for s in ("anchor", "witness")))
        value = {"schema_version": 1, "policy_digest": digest(self.value),
                 "result": {"status": "FAILED", "error_code": code,
                            "effect_may_be_partial": consumed},
                 "evidence": {"approved_scope_digest": self.value["request_digest"]}}
        identity = "action-failure-" + digest(self.identity)
        paths = [self.store._decision_path(self.identity, "action-failure", s) for s in ("anchor", "witness")]
        if any(p.exists() for p in paths):
            if self.store._decision_pair(self.identity, "action-failure") != value:
                raise ExecutionStoreError("Action failure evidence cannot be rewritten")
            self.store._verify_observation(self.value, "decision_result_observed", identity, digest(value))
        else:
            if any(e.event_type == "decision_result_observed" and e.execution_id == identity for e in history):
                raise ExecutionStoreError("Missing action failure trace; recovery required")
            self.store._observe(self.value, "decision_result_observed", identity, digest(value))
            self.store._decision_pair(self.identity, "action-failure", value)

    def finish(self, result):
        self._validate_current()
        # Recovering verified existing effects is evidence, never replay authority.
        consumed, _ = self._retained_state()
        if self._attempted and not consumed:
            raise ExecutionStoreError("Attempted action consumption disappeared; recovery required")
        history = self._history()
        value = {"schema_version": 1, "policy_digest": digest(self.value),
                 "result_digest": digest(result), "effect_performed": consumed,
                 "evidence": result}
        paths = [self.store._decision_path(self.identity, "action-result", s) for s in ("anchor", "witness")]
        if any(p.exists() for p in paths):
            if self.store._decision_pair(self.identity, "action-result") != value:
                raise ExecutionStoreError("Action result/evidence trace is stale or tampered")
            self.store._verify_observation(self.value, "decision_result_observed", self.identity, digest(value))
        else:
            if any(e.event_type == "decision_result_observed" and e.execution_id == self.identity for e in history):
                raise ExecutionStoreError("Missing action result trace; explicit recovery required")
            self.store._observe(self.value, "decision_result_observed", self.identity, digest(value))
            self.store._decision_pair(self.identity, "action-result", value)
        return result
