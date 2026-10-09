"""Graph topology, delegation, corruption and dispatch-boundary probes."""
from copy import deepcopy
import json
from unittest.mock import patch
import unittest

from runtime.core.jobs import RuntimeError as JobError
from runtime.core.task_contract import TaskContractError
from runtime.graph.models import GraphError, node_id
from runtime.graph.planner import GraphPlanner
from runtime.tests.test_graph import GraphHarness


class GraphAdversarialTests(GraphHarness, unittest.TestCase):
    def approved_parent(self, *, admit=True):
        node = self.node("a")
        node["payload"]["task_contract"]["approval_requirements"]["execution"] = True
        root = self.create([node], approval_status="required")
        self.graph.advance(root["job_id"])
        parent = self.approvals.store.list()[0]
        self.approvals.resolve(parent.approval_id, decision="APPROVED", decided_by="test-owner")
        if admit:
            self.graph.advance(root["job_id"])
            child = next(a for a in self.approvals.store.list() if a.job_id != root["job_id"])
            self.approvals.resolve(child.approval_id, decision="APPROVED", decided_by="test-owner")
        return root, parent

    def test_missing_parent_approval_receipt_blocks_admission(self):
        root, parent = self.approved_parent(admit=False)
        self.approvals.store._path(parent.approval_id).unlink()
        with self.assertRaises((GraphError, JobError)):
            self.graph.advance(root["job_id"])
        self.assertEqual(len(self.jobs.store.list()), 1)

    def test_tampered_parent_approval_receipt_blocks_claimed_child(self):
        root, parent = self.approved_parent()
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        path = self.approvals.store._path(parent.approval_id)
        record = json.loads(path.read_text())
        record["status"] = "REJECTED"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises((GraphError, JobError)):
            self.jobs.validate_execution_authority(claim["job_id"], worker.worker_id)
        self.assertIsNone(worker.executor.last_request)

    def test_missing_parent_receipt_after_intent_blocks_actual_local_tool(self):
        from runtime.executors.local import LocalExecutor
        root, parent = self.approved_parent()
        harness = self
        class MissingParentReceipt(LocalExecutor):
            def execute(self, request):
                harness.approvals.store._path(parent.approval_id).unlink()
                return super().execute(request)
        executor = MissingParentReceipt()
        outcome = self.execute(root, "a", executor=executor)
        self.assertIsNone(executor.last_request)
        self.assertNotEqual(outcome.status, "completed")

    def test_bad_topologies_and_unbounded_allocations_rejected(self):
        samples = [([self.node("a", depends=("missing",))], {}),
                   ([self.node("a", depends=("a",))], {}),
                   ([self.node("a", depends=("b",)), self.node("b", depends=("a",))], {}),
                   ([self.node("a"), self.node("a")], {}),
                   ([self.node("a")], {"max_parallel": 17}),
                   ([self.node("a")], {"max_parallel": True}),
                   ([self.node("a")], {"max_handoffs": 65}),
                   ([self.node(str(n)) for n in range(65)], {})]
        for nodes, overrides in samples:
            with self.subTest(overrides=overrides, count=len(nodes)), self.assertRaises(TaskContractError):
                GraphPlanner.build(nodes, **overrides)

    def test_recovery_requires_unambiguous_predeclared_endpoints(self):
        for edges in ([dict(source="a", target="missing", kind="replan")],
            [dict(source="a", target="b", kind="correction"), dict(source="a", target="c", kind="replan")],
            [dict(source="a", target="c", kind="correction"), dict(source="b", target="c", kind="replan")]):
            with self.subTest(edges=edges), self.assertRaises(TaskContractError):
                GraphPlanner.build([self.node("a"), self.node("b"), self.node("c")], edges=edges)

    def test_profile_cannot_become_new_canonical_agent(self):
        node = self.node("a", profile="explorer")
        node["payload"]["agent"] = "explorer"
        root = self.create([node])
        with self.assertRaisesRegex(JobError, "agent: expected one of"):
            self.graph.advance(root["job_id"])
        self.assertEqual(len(self.jobs.list()), 1)

    def test_parent_authority_widening_denied_before_admission(self):
        for field, value in (("allowed_tools", ["controlled_write"]),
            ("allowed_capabilities", ["financial_operations"]),
            ("delegation_level", "L2"), ("blast_radius", "external"),
            ("stop_conditions", [])):
            node = self.node("a")
            node["payload"]["task_contract"][field] = value
            with self.subTest(field=field), self.assertRaises((JobError, GraphError)):
                self.create([node])

    def test_project_input_compute_and_budget_widening_denied(self):
        variants = []
        project = self.node("a"); project["payload"]["project_id"] = "another-project"; variants.append(project)
        inputs = self.node("a"); inputs["payload"]["input_refs"] = [{"ref_type": "file", "ref": "outside.md"}]
        inputs["payload"]["task_contract"]["inputs"] = inputs["payload"]["input_refs"]; variants.append(inputs)
        compute = self.node("a"); compute["payload"]["compute_requirements"] = {"complexity": "high"}; variants.append(compute)
        budget = self.node("a"); budget["payload"]["task_contract"]["budget_references"] = {"budget_id": "forged", "logical_job_id": "other", "policy_digest": "0" * 64}; variants.append(budget)
        for node in variants:
            with self.subTest(node=node), self.assertRaises((JobError, GraphError)):
                self.create([node])

    def test_managed_binding_cannot_bypass_graph_admission(self):
        root = self.create([self.node("a"), self.node("join", depends=("a",))])
        payload = self.payload(graph_binding={"root_job_id": root["job_id"]})
        with self.assertRaisesRegex(JobError, "runtime-managed"):
            self.jobs.create(payload)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_direct_private_admission_still_requires_fan_in_proof(self):
        from runtime.graph.models import child_payload
        root = self.create([self.node("a"), self.node("join", depends=("a",))])
        child = child_payload(root, root["graph_plan"]["nodes"][-1])
        with self.assertRaisesRegex(JobError, "dependency receipt"):
            self.jobs._create_attempt(child, attempt=1, parent_job_id=None,
                                      job_id_override=node_id(root["job_id"], "join"))

    def test_tampered_topology_or_binding_fails_closed(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        initial = self.jobs.store.load(root["job_id"])
        modified = deepcopy(initial)
        modified["graph_plan"]["max_parallel"] = 16
        self.jobs.store.save(modified)
        with self.assertRaises(JobError):
            self.graph.show(root["job_id"])
        self.jobs.store.save(initial)
        child_id = node_id(root["job_id"], "a")
        child = self.jobs.store.load(child_id)
        child["graph_binding"]["node_id"] = "undeclared"
        self.jobs.store.save(child)
        with self.assertRaises(JobError):
            self.jobs.show(child_id)

    def test_removed_graph_binding_still_fails_existing_authority_anchor(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        job = self.jobs.store.load(node_id(root["job_id"], "a"))
        del job["graph_binding"]
        self.jobs.store.save(job)
        with self.assertRaises(JobError):
            self.jobs.show(job["job_id"])

    def test_branch_context_does_not_include_sibling_outputs(self):
        root = self.create([self.node("a"), self.node("b"), self.node("after", depends=("a",))])
        self.graph.advance(root["job_id"])
        a = self.execute(root, "a")
        b = self.execute(root, "b")
        self.graph.advance(root["job_id"])
        after = self.jobs.show(node_id(root["job_id"], "after"))
        refs = {ref["ref"] for ref in after["input_refs"]}
        self.assertIn("runtime-execution:" + a.execution_id, refs)
        self.assertNotIn("runtime-execution:" + b.execution_id, refs)

    def test_deterministic_node_cannot_dispatch_provider_or_generic_executor(self):
        root = self.create([self.node("a", kind="deterministic")])
        self.graph.advance(root["job_id"])
        worker = self.worker()
        claim = self.jobs.claim(job_id=node_id(root["job_id"], "a"), claimed_by=worker.worker_id)
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            outcome = worker.run_claimed(claim["job_id"])
            self.assertEqual(outcome.status, "worker_error")
            self.assertEqual(execute.call_count, 0)

    def test_gate_contracts_cannot_omit_canonical_handoffs(self):
        for node in (self.node("a", kind="human_gate"), self.node("a", kind="gate", profile="critic")):
            with self.subTest(kind=node["kind"]), self.assertRaises((JobError, GraphError)):
                self.create([node])

    def test_interrupted_admission_does_not_regenerate_authority(self):
        root = self.create([self.node("a")])
        original = self.jobs.store.create
        def interrupt(job):
            if "graph_binding" in job:
                raise OSError("simulated interruption after immutable task anchors")
            return original(job)
        with patch.object(self.jobs.store, "create", side_effect=interrupt), self.assertRaises(OSError):
            self.graph.advance(root["job_id"])
        with self.assertRaises(JobError):
            self.graph.advance(root["job_id"])
        self.assertEqual(len(self.jobs.list()), 1)

    def test_cancelled_parent_cannot_dispatch_already_queued_child(self):
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        self.jobs.transition(root["job_id"], "cancelled")
        worker = self.worker()
        with patch.object(worker.executor, "execute", wraps=worker.executor.execute) as execute:
            outcome = worker.run_once()
            self.assertIn(outcome.status, {"worker_error", "no_work"})
            self.assertEqual(execute.call_count, 0)

    def test_stop_decision_cannot_be_bypassed_by_replan(self):
        root = self.create([self.node("a"), self.node("repair")],
            edges=[dict(source="a", target="repair", kind="replan")], handoffs=1, budget=0)
        outcome = self.graph.run_ready(root["job_id"], self.factory)[0]
        self.assertEqual(outcome.status, "failed")
        view = self.graph.advance(root["job_id"])
        self.assertEqual(view["status"], "failed")
        self.assertIsNone(view["nodes"]["repair"]["job_id"])

    def test_parent_revocation_after_intent_blocks_actual_tool_dispatch(self):
        from runtime.executors.local import LocalExecutor
        root = self.create([self.node("a")])
        self.graph.advance(root["job_id"])
        harness = self
        class RevokedExecutor(LocalExecutor):
            def execute(self, request):
                harness.jobs.transition(root["job_id"], "cancelled")
                return super().execute(request)
        executor = RevokedExecutor()
        self.execute(root, "a", executor=executor)
        self.assertIsNone(executor.last_request)
        self.assertEqual(self.graph.show(root["job_id"])["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
