"""GAP-40 foreground probes: temporary canonical owners, no live providers."""
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.cache import ContextCache
from runtime.cli import __main__ as cli
from runtime.context.contracts import DiscoveryError, Limits, RepositoryReader
from runtime.core.references import CanonicalReferenceResolver
from runtime.core.jobs import RuntimeError as JobRuntimeError
from runtime.executors.local import LocalExecutor
from runtime.memory.action_trace import ActionTraceOwners
from runtime.approvals.store import FileApprovalStore
from runtime.evals.store import FileEvalStore
from runtime.memory.contracts import EvidenceOrigin, MemoryContractError
from runtime.memory.integration import ForegroundMemoryIntegration, MemoryIntegrationError
from runtime.memory.knowledge_adapter import MemoryDiscoveryEntry
from runtime.memory.lifecycle import DecisionEvidence, Disposition, MemoryReference, prepare_candidate
from runtime.memory.validity import LifecycleView, PinnedMemory, SupersessionEvidence, prepare_evidence
from runtime.providers.context import ContextBuildError, ExecutionContextBuilder
from runtime.providers.config import ProviderConfiguration
from runtime.providers.routing import ProviderRouter
from runtime.tests.contract_fixtures import bounded_context_repository
from runtime.tests import test_memory_action_trace as trace_fixtures
from runtime.tests.test_memory_foundation import record, source
from runtime.tests.test_memory_lifecycle import RecordingMemory
from runtime.tests.test_memory_readonly_inspection import filesystem_snapshot, no_persistent_mutations
from runtime.tests.test_providers import FakeAdapter, REPOSITORY_ROOT, request
from runtime.tests.test_continuation import Reviewer
from runtime.workers.worker import Worker


class MemoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("CONSTITUTION.md", "AGENTS.md", "PROJECT_STATE.md"):
            (self.root / name).write_text("# Rules\n## Current\nCanonical fixture\n", encoding="utf-8")
        (self.root / "evidence.txt").write_bytes(b"original source")
        self.memory = RecordingMemory()
        self.entries, self.views = (), ()
        self.request = request(project_id="alpha", task="invoice review", context_refs=())
        self.scope = set()
        self.authority_calls = []
        self.service = self.integration()
        self.trace = trace_fixtures.ActionTraceTests()
        self.addCleanup(self.trace.doCleanups)

    def integration(self, *, project="alpha", root=None, owners=None, authority=True, manifest=None,
                    memory=None):
        return ForegroundMemoryIntegration(project, self.root if root is None else root,
            self.memory if memory is None else memory,
            manifest=(lambda req: (self.entries, self.views)) if manifest is None else manifest,
            owners=owners, authorize_storage=self.authorize if authority else None)

    def authorize(self, project, sink, pins):
        self.authority_calls.append((project, sink, pins))
        return sink is self.memory and all((project, pin) in self.scope for pin in pins)

    def grant(self, project, candidates):
        self.scope.update((project, PinnedMemory.from_record(c.to_memory_record())) for c in candidates)

    def candidate(self, identity, *, project="alpha", claim="invoice review evidence", origin=EvidenceOrigin.REPOSITORY,
                  decision=None):
        return prepare_candidate(project, record(project, record_id="original-" + identity, claim=claim,
            sources=(source(project, origin=origin, location="evidence.txt"),)),
            record_id=identity, decision=decision)

    def persist(self, candidate, service=None):
        service = self.service if service is None else service
        self.grant(service.project_id, (candidate,))
        report = service.store_candidates((candidate,))
        self.assertIsNone(report.failure)
        self.assertEqual(report.stored, (PinnedMemory.from_record(candidate.to_memory_record()),))
        return report.stored[0]

    def builder(self, service=None, **options):
        return ExecutionContextBuilder(self.root, knowledge_factory=(self.service if service is None else service).request_adapter,
                                       **options)

    def body(self, package):
        material = next(m for m in package.context_pack.materials if m.source == "memory")
        self.assertEqual((material.trust, material.authority), ("untrusted", "none"))
        return json.loads(material.content)

    def test_default_runtime_has_no_memory_reads_writes_or_capture(self):
        fixture = self.trace.fixture()
        created = fixture.runtime.create(fixture.payload(project_id="brightshore"))
        fixture.runtime.enqueue(created["job_id"])
        with patch.object(cli, "repository_root", return_value=self.root):
            worker = cli.build_worker("local-success", fixture.runtime, fixture.executions, None,
                                      fixture.root / "executions")
            with patch.object(self.service, "capture", side_effect=AssertionError("Implicit capture")):
                outcome = cli.run_foreground_worker(worker)
        self.assertEqual(outcome["status"], "completed")
        self.assertNotIn("memory_capture", outcome)
        package = ExecutionContextBuilder(self.root).build(self.request)
        self.assertFalse(any(m.source == "memory" for m in package.context_pack.materials))
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))

    def test_composed_builder_installs_fresh_adapter_for_each_exact_request(self):
        candidate = self.candidate("selected")
        self.persist(candidate)
        self.entries = (MemoryDiscoveryEntry.from_candidate(candidate, description="invoice review"),)
        fixture = self.trace.fixture()
        router = ProviderRouter(ProviderConfiguration(REPOSITORY_ROOT), {
            "claude": FakeAdapter("claude", available=False), "codex": FakeAdapter("codex", available=True)})
        with patch.object(cli, "repository_root", return_value=self.root), \
             patch.object(cli, "build_provider_router", return_value=router):
            worker = cli.build_worker("provider", fixture.runtime, fixture.executions, None,
                                      fixture.root / "executions", memory_integration=self.service)
        builder = worker.executor.context_builder
        self.assertIsNone(builder.knowledge)
        self.memory.reads.clear()
        for req in (self.request, self.request, replace(self.request, execution_id="next-request")):
            self.assertEqual(self.body(builder.build(req))["candidate"]["reference"]["record_id"], "selected")
        self.assertEqual(self.memory.reads, [("alpha", "selected")] * 3)
        consumed = self.service.request_adapter(self.request, self.root, Limits())
        wrong_factory = ExecutionContextBuilder(self.root, knowledge_factory=lambda *args: consumed)
        wrong_factory.build(self.request)
        with self.assertRaises(ContextBuildError): wrong_factory.build(self.request)
        self.memory.reads.clear()
        with self.assertRaises(ContextBuildError):
            wrong_factory.build(replace(self.request, execution_id="different-bound-request"))
        self.assertEqual(self.memory.reads, [])
        with self.assertRaises(ContextBuildError):
            ExecutionContextBuilder(self.root, knowledge=object(), knowledge_factory=self.service.request_adapter)
        builder.knowledge = object()
        self.memory.reads.clear()
        with self.assertRaises(ContextBuildError):
            builder.build(self.request)
        self.assertEqual(self.memory.reads, [])

    def test_foreign_request_manifest_or_project_root_fails_before_memory_io(self):
        item = self.candidate("one")
        self.persist(item)
        self.entries = (MemoryDiscoveryEntry.from_candidate(item, description="invoice review"),)
        cache = ContextCache()
        builder = self.builder(cache=cache, cache_scope="host-alpha")
        builder.build(self.request)  # Warm cache does not bypass installation checks.
        self.memory.reads.clear(); self.memory.writes.clear()
        invalid = replace(self.request)
        object.__setattr__(invalid, "attempt", 0)
        for req in (replace(self.request, project_id="beta"), replace(self.request, project_id=None), invalid):
            with self.subTest(project=req.project_id), patch.object(cache, "reuse", side_effect=AssertionError("Cache bypass")), \
                 patch.object(RepositoryReader, "read", side_effect=AssertionError("Read before isolation")), \
                 self.assertRaises(ContextBuildError):
                builder.build(req)
        foreign = self.candidate("foreign", project="beta")
        self.entries = (MemoryDiscoveryEntry.from_candidate(foreign, description="invoice review"),)
        with self.assertRaises(ContextBuildError): builder.build(self.request)
        self.entries = (MemoryDiscoveryEntry.from_candidate(item, description="invoice review"),)
        wrong_root = self.root / "other"; wrong_root.mkdir()
        with self.assertRaises(ContextBuildError):
            ExecutionContextBuilder(wrong_root, knowledge_factory=self.service.request_adapter).build(self.request)
        for manifest in (None, (self.entries,), (list(self.entries), ()), (self.entries * 33, ())):
            with self.subTest(manifest=type(manifest).__name__), self.assertRaises(ContextBuildError):
                self.builder(self.integration(manifest=lambda req: manifest)).build(self.request)
        object.__setattr__(self.entries[0], "record_digest", "0" * 64)
        # Changed metadata cannot reuse already captured binding, even with no I/O.
        adapter = self.service.request_adapter(self.request, self.root, Limits())
        object.__setattr__(self.entries[0], "record_digest", "1" * 64)
        with self.assertRaises(DiscoveryError): adapter.candidates(self.request.task, 32)
        # The root remains explicitly checked even after adapter installation.
        original_root = self.service.project_root
        self.service.project_root = wrong_root
        with self.assertRaises(DiscoveryError): adapter.load(item.reference.identity, 128 * 1024)
        self.service.project_root = original_root
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))

    def test_explicit_capture_store_readback_and_later_selected_retrieval(self):
        fixture = self.trace.fixture()
        owners = ActionTraceOwners(jobs=fixture.runtime.store, tasks=fixture.runtime.task_contract_store,
            executions=fixture.executions, progress=fixture.runtime.progress.store,
            approvals=FileApprovalStore(fixture.root / "approvals"), evaluations=FileEvalStore(fixture.root / "evals"))
        service = self.integration(project="brightshore", owners=owners)
        selected = []
        def capture(outcome):
            job = fixture.runtime.store.load(outcome.job_id)
            req, owners = self.trace.inputs(fixture, job, outcome.execution_id)
            # run_once has returned after the outcome journal emission.
            self.assertTrue(any(e.event_type == "worker_exited" for e in owners.progress.read(req.trace.identity)))
            selected.append((req, owners))
            return req
        created = fixture.runtime.create(fixture.payload(project_id="brightshore"))
        fixture.runtime.enqueue(created["job_id"])
        result = cli.run_foreground_worker(fixture.worker, memory_integration=service, memory_capture=capture)
        self.assertEqual(result["memory_capture"]["status"], "captured")
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        candidates = service.capture(selected[0][0])
        self.grant("brightshore", candidates)
        report = service.store_candidates(candidates)
        self.assertEqual(report.stored, tuple(PinnedMemory.from_record(c.to_memory_record()) for c in candidates))
        # This injected port also performs its own collision read in put_candidate.
        self.assertEqual(self.memory.reads, [("brightshore", c.reference.record_id) for c in candidates for _ in range(3)])
        self.entries = tuple(MemoryDiscoveryEntry.from_candidate(c, description="invoice review") for c in candidates)
        wanted = candidates[0].reference.identity
        class SelectObservation:
            def rank(self, query, metadata): return (wanted,)
        req = request(project_id="brightshore", task="invoice review", context_refs=())
        adapter = service.request_adapter(req, self.root, Limits())
        self.memory.reads.clear(); self.memory.writes.clear()
        self.assertTrue(adapter.candidates(req.task, 32))
        self.assertEqual(self.memory.reads, [])
        package = self.builder(service, ranker=SelectObservation()).build(req)
        self.assertEqual(self.body(package)["candidate"]["reference"]["record_id"], candidates[0].reference.record_id)
        self.assertEqual(self.memory.reads, [("brightshore", candidates[0].reference.record_id)])
        self.assertEqual(self.memory.writes, [])
        self.assertTrue(json.loads(candidates[0].original.claim)["completion_verified"])
        # Later retrieval reaches real provider dispatch and canonical completion
        # through CLI composition. Only the provider process is a local double.
        with bounded_context_repository(profile="provider-review") as context_root:
            integrated = self.integration(project="brightshore", root=context_root)
            second = self.trace.fixture()
            payload = second.payload(project_id="brightshore", task="invoice review",
                task_class="software", agent="software", workflow="software", capability="software_implementation")
            job = second.runtime.create(payload)
            second.runtime.enqueue(job["job_id"])
            codex = FakeAdapter("codex", available=True)
            router = ProviderRouter(ProviderConfiguration(REPOSITORY_ROOT), {
                "claude": FakeAdapter("claude", available=False), "codex": codex})
            with patch.object(cli, "repository_root", return_value=context_root), \
                 patch.object(cli, "build_provider_router", return_value=router):
                worker = cli.build_worker("provider", second.runtime, second.executions, None,
                    second.root / "executions", memory_integration=integrated)
            # Match the explicit bounded fixture resolver to its context root.
            worker.resolver = CanonicalReferenceResolver(context_root)
            self.memory.reads.clear(); self.memory.writes.clear()
            outcome = cli.run_foreground_worker(worker)
            self.assertEqual(outcome["status"], "completed", outcome)
            self.assertEqual(len(codex.calls), 1)
            self.assertTrue(any(e.origin == "retrieved" for e in codex.calls[0][1].context))
            self.assertEqual(set(self.memory.reads), {("brightshore", c.reference.record_id) for c in candidates})
            self.assertEqual(self.memory.writes, [])
            self.assertIn("task_completion", second.runtime.store.load(job["job_id"]))

    def test_runtime_validity_refresh_preserves_unknown_truth_and_invalidates_cache(self):
        a = self.candidate("a")
        pin = self.persist(a)
        self.entries = (MemoryDiscoveryEntry.from_candidate(a, description="invoice review"),)
        self.views = (LifecycleView(subject=pin),)
        builder = self.builder(cache=ContextCache(), cache_scope="host-alpha")
        first = self.body(builder.build(self.request))
        self.assertEqual(first["assessment"]["usability"], "valid-for-reuse")
        self.assertEqual(first["assessment"]["truth"], "unknown")
        builder.build(self.request)
        self.assertEqual(builder.last_cache_result.status, "HIT")
        (self.root / "evidence.txt").write_bytes(b"changed")
        changed = self.body(builder.build(self.request))
        self.assertEqual(builder.last_cache_result.status, "STALE")
        self.assertEqual(changed["assessment"]["usability"], "invalidated")
        with patch.object(RepositoryReader, "read", side_effect=PermissionError("denied")):
            # Only the source checker failure is relevant; required governance
            # reads still use their real reader below.
            checker = self.service.request_adapter(self.request, self.root, Limits())
            checker.candidates(self.request.task, 32)
            unknown = json.loads(checker.load(a.reference.identity, 128 * 1024).content)
        self.assertEqual(unknown["assessment"]["usability"], "unknown")
        unsupported = self.candidate("unsupported", origin=EvidenceOrigin.TOOL)
        unsupported_pin = self.persist(unsupported)
        self.entries = (MemoryDiscoveryEntry.from_candidate(unsupported, description="invoice review"),)
        self.views = (LifecycleView(subject=unsupported_pin),)
        body = self.body(builder.build(self.request))
        self.assertEqual(body["assessment"]["usability"], "unknown")
        self.assertEqual(body["assessment"]["truth"], "unknown")
        self.assertEqual(body["assessment"]["scope"], "within this supplied view only")
        with self.assertRaises(ContextBuildError):
            self.builder(max_file_bytes=64).build(self.request)
        self.memory.records.pop(("alpha", "unsupported"))
        with self.assertRaises(ContextBuildError): builder.build(self.request)

    def test_stored_supersession_closure_preserves_originals_conflicts_and_scope(self):
        a, b, c = (self.candidate(n, decision=DecisionEvidence(disposition=Disposition.REJECTED,
                    rationale="Keep contrary invoice evidence") if n == "b" else None) for n in "abc")
        pa, pb, pc = (self.persist(item) for item in (a, b, c))
        def event(old, new, identity, applicability):
            return SupersessionEvidence(reference=MemoryReference(project_id="alpha", record_id=identity),
                predecessor=old, successor=new, applicability=applicability,
                rationale="Declared replacement only", sources=(source(),))
        def append(value, dependencies=()):
            self.grant("alpha", (prepare_evidence(value),))
            report = self.service.store_event(value, dependencies=dependencies)
            self.assertIsNone(report.failure)
            return report.stored[0]
        ab = append(event(pa, pb, "ab", "invoice scope one"))
        bc = append(event(pb, pc, "bc", "different declared scope"), (pa, ab))
        self.entries = (MemoryDiscoveryEntry.from_candidate(a, description="invoice review"),)
        self.views = (LifecycleView(subject=pa, dependencies=(pb, pc, ab, bc)),)
        body = self.body(self.builder().build(self.request))
        self.assertEqual(body["original_candidate"]["record_id"], "a")
        self.assertEqual(body["assessment"]["relationship_state"], "declared-unverified")
        self.assertIn("different declared scope", json.dumps(body))
        self.assertIn("Keep contrary invoice evidence", json.dumps(body))
        ac = append(event(pa, pc, "ac", "third declared scope"), (pb, ab, bc))
        self.views = (LifecycleView(subject=pa, dependencies=(pb, pc, ab, bc, ac)),)
        self.assertEqual(self.body(self.builder().build(self.request))["assessment"]["usability"], "conflicted")
        self.views = (LifecycleView(subject=pb, dependencies=(pa, pc, ab, bc, ac)),)
        self.entries = (MemoryDiscoveryEntry.from_candidate(b, description="invoice review"),)
        merged = self.body(self.builder().build(self.request))
        self.assertEqual(merged["original_candidate"]["record_id"], "b")
        self.assertEqual(merged["assessment"]["relationship_state"], "conflicted")
        self.views = (LifecycleView(subject=pb, dependencies=(pa, ab, bc)),)
        with self.assertRaises(ContextBuildError): self.builder().build(self.request)
        cycle = event(pc, pa, "ca", "cycle")
        self.grant("alpha", (prepare_evidence(cycle),))
        before = dict(self.memory.records)
        report = self.service.store_event(cycle, dependencies=(pb, ab, bc))
        self.assertEqual(report.failure, "storage_unconfirmed")
        self.assertEqual(self.memory.records, before)
        with self.assertRaises(MemoryIntegrationError):
            self.service.store_candidates((prepare_evidence(cycle),))

    def test_capture_preserves_failed_pending_dry_run_and_verified_completion(self):
        for kind in ("failed", "pending", "dry-run", "verified", "review-fail", "review-pass"):
            with self.subTest(kind=kind):
                if kind.startswith("review-"):
                    fixture, job, execution_id = self.trace.reviewed("PASS" if kind == "review-pass" else "FAIL")
                else:
                    fixture = self.trace.fixture()
                    payload = fixture.payload(project_id="brightshore", max_attempts=1, dry_run=kind == "dry-run")
                    if kind == "pending": payload.pop("task_contract")
                    if kind == "failed": fixture.worker.executor = LocalExecutor("failure", clock=fixture.runtime.clock)
                    _, outcome = fixture.run_job(payload)
                    job = fixture.runtime.store.load(outcome.job_id); execution_id = outcome.execution_id
                req, owners = self.trace.inputs(fixture, job, execution_id)
                service = self.integration(project="brightshore", owners=owners)
                before = fixture.runtime.store.load(job["job_id"])
                with no_persistent_mutations(self, fixture.root):
                    observation, assertion = [json.loads(c.original.claim) for c in service.capture(req)]
                self.assertEqual(fixture.runtime.store.load(job["job_id"]), before)
                if kind in {"failed", "pending", "review-fail"}: self.assertFalse(observation["gov_accepted"])
                if kind in {"verified", "review-pass"}: self.assertTrue(observation["completion_verified"])
                if kind == "failed":
                    self.assertEqual(assertion["execution_result"]["error"]["code"], "local_executor_failure")
                    self.assertEqual(assertion["execution_result"]["evidence"][0]["status"], "failed")
                if kind == "dry-run": self.assertTrue(observation["dry_run"])
                if kind.startswith("review-"):
                    self.assertEqual(assertion["review_record"]["result"]["decision"], "PASS" if kind == "review-pass" else "FAIL")
                    with self.assertRaises(MemoryContractError): service.capture(replace(req, review=None))
                with self.assertRaises(MemoryContractError):
                    service.capture(replace(req, execution=replace(req.execution, sha256="0" * 64)))
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        # A capture failure after a completed worker retains its actual outcome.
        fixture = self.trace.fixture()
        job = fixture.runtime.create(fixture.payload(project_id="brightshore"))
        fixture.runtime.enqueue(job["job_id"])
        service = self.integration(project="brightshore")
        result = cli.run_foreground_worker(fixture.worker, memory_integration=service,
                                           memory_capture=lambda outcome: None)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["memory_capture"]["status"], "unavailable")

    def assert_capture_exception_preserves_outcome(self, error_type, *, during_capture=False):
        fixture = self.trace.fixture()
        created = fixture.runtime.create(fixture.payload(project_id="brightshore"))
        fixture.runtime.enqueue(created["job_id"])
        service = self.integration(project="brightshore")
        failure = error_type("Capture failed after Worker returned")
        observed = {}

        def select(outcome):
            self.assertEqual(outcome.status, "completed")
            job = fixture.runtime.store.load(outcome.job_id)
            self.assertEqual(job["status"], "completed")
            req, owners = self.trace.inputs(fixture, job, outcome.execution_id)
            self.assertTrue(any(e.event_type == "worker_exited" for e in owners.progress.read(req.trace.identity)))
            observed.update(outcome=outcome.to_dict(), job=job, state=filesystem_snapshot(fixture.root))
            if during_capture:
                return req
            raise failure

        with patch.object(fixture.worker, "run_once", wraps=fixture.worker.run_once) as run_once, \
             patch.object(service, "capture", side_effect=failure) as capture:
            if issubclass(error_type, Exception):
                result = cli.run_foreground_worker(fixture.worker, memory_integration=service, memory_capture=select)
                self.assertEqual(result, {**observed["outcome"],
                    "memory_capture": {"status": "unavailable", "candidates": []}})
            else:
                with self.assertRaises(error_type) as raised:
                    cli.run_foreground_worker(fixture.worker, memory_integration=service, memory_capture=select)
                self.assertIs(raised.exception, failure)
            run_once.assert_called_once_with()
            if during_capture:
                capture.assert_called_once()
            else:
                capture.assert_not_called()
        self.assertEqual(filesystem_snapshot(fixture.root), observed["state"])
        self.assertEqual(fixture.runtime.store.load(created["job_id"]), observed["job"])
        self.assertEqual((self.memory.reads, self.memory.writes, self.authority_calls), ([], [], []))

    def test_capture_selector_key_error_preserves_completed_worker_outcome(self):
        self.assert_capture_exception_preserves_outcome(KeyError)

    def test_capture_selector_runtime_error_preserves_completed_worker_outcome(self):
        self.assert_capture_exception_preserves_outcome(RuntimeError)

    def test_capture_service_exception_preserves_completed_worker_outcome(self):
        self.assert_capture_exception_preserves_outcome(RuntimeError, during_capture=True)

    def test_capture_process_control_exceptions_propagate(self):
        for error_type in (KeyboardInterrupt, SystemExit, GeneratorExit):
            with self.subTest(error=error_type.__name__):
                self.assert_capture_exception_preserves_outcome(error_type)

    def test_capture_handler_does_not_mask_worker_or_composition_errors(self):
        fixture = self.trace.fixture()
        service = self.integration(project="brightshore")

        def select(outcome):
            self.fail("Capture selected before Worker returned")

        for error_type in (RuntimeError, JobRuntimeError, MemoryIntegrationError):
            failure = error_type("Worker failed before capture")
            with self.subTest(error=error_type.__name__), \
                 patch.object(fixture.worker, "run_once", side_effect=failure) as run_once, \
                 self.assertRaises(error_type) as raised:
                cli.run_foreground_worker(fixture.worker, memory_integration=service, memory_capture=select)
            self.assertIs(raised.exception, failure)
            run_once.assert_called_once_with()
        with patch.object(fixture.worker, "run_once") as run_once, self.assertRaises(MemoryIntegrationError):
            cli.run_foreground_worker(fixture.worker, memory_integration=object(), memory_capture=select)
        run_once.assert_not_called()
        self.assertEqual((self.memory.reads, self.memory.writes, self.authority_calls), ([], [], []))

    def test_storage_requires_separate_scope_and_reports_partial_failure(self):
        candidates = tuple(self.candidate(n) for n in ("one", "two", "three"))
        for service in (self.integration(authority=False), self.service):
            with self.subTest(authority=service.authorize_storage), self.assertRaises(MemoryIntegrationError):
                service.store_candidates(candidates)
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        self.grant("alpha", candidates[:1])
        with self.assertRaises(MemoryIntegrationError): self.service.store_candidates(candidates)
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        self.grant("alpha", candidates)
        put = self.memory.put_candidate
        def broken(project, item):
            returned = put(project, item)
            if item.record_id == "two": raise OSError("Write happened but acknowledgement lost")
            return returned
        with patch.object(self.memory, "put_candidate", side_effect=broken):
            report = self.service.store_candidates(candidates)
        self.assertEqual(report.stored, (PinnedMemory.from_record(candidates[0].to_memory_record()),))
        self.assertEqual(report.uncertain, candidates[1].reference)
        self.assertEqual(report.unattempted, (candidates[2].reference,))
        self.assertIn(("alpha", "two"), self.memory.records)
        self.assertNotIn(("alpha", "three"), self.memory.records)
        self.assertEqual(self.authority_calls[-1][0:2], ("alpha", self.memory))
        self.assertEqual(self.authority_calls[-1][2], tuple(PinnedMemory.from_record(c.to_memory_record()) for c in candidates))
        self.memory.reads.clear(); self.memory.writes.clear()
        foreign = self.candidate("foreign", project="beta")
        for batch in ((foreign,), candidates * 11, (candidates[0], candidates[0])):
            with self.subTest(size=len(batch)), self.assertRaises(MemoryIntegrationError):
                self.service.store_candidates(batch)
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        changed = self.candidate("changed-during-authority")
        def mutate(project, sink, pins):
            object.__setattr__(changed, "normalized_claim", "different bytes")
            return True
        mutating_host = ForegroundMemoryIntegration("alpha", self.root, self.memory,
            manifest=lambda req: ((), ()), authorize_storage=mutate)
        with self.assertRaises(MemoryContractError): mutating_host.store_candidates((changed,))
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        # A stored acknowledgement with a substituted record is never confirmed.
        fresh = self.candidate("bad-readback")
        self.grant("alpha", (fresh,))
        with patch.object(self.memory, "put_candidate", return_value=candidates[0].to_memory_record()):
            unconfirmed = self.service.store_candidates((fresh,))
        self.assertEqual(unconfirmed.stored, ())
        self.assertEqual(unconfirmed.uncertain, fresh.reference)

    def test_later_human_completion_requires_explicit_recapture(self):
        fixture = self.trace.fixture()
        payload = fixture.payload(project_id="brightshore", review_required=True)
        payload["task_contract"]["approval_requirements"]["completion"] = True
        reviewer = Reviewer("PASS")
        self.addCleanup(reviewer.review_temporary.cleanup)
        fixture.worker = Worker(fixture.runtime, CanonicalReferenceResolver(REPOSITORY_ROOT),
            LocalExecutor(clock=fixture.runtime.clock), fixture.executions,
            reviewer_runtime=reviewer, clock=fixture.runtime.clock)
        _, outcome = fixture.run_job(payload)
        self.assertEqual(outcome.status, "waiting_approval")
        job = fixture.runtime.store.load(outcome.job_id)
        req, owners = self.trace.inputs(fixture, job, outcome.execution_id)
        service = self.integration(project="brightshore", owners=owners)
        pending = service.capture(req)
        self.assertFalse(json.loads(pending[0].original.claim)["completion_verified"])
        self.grant("brightshore", pending)
        service.store_candidates(pending)
        memory_before = dict(self.memory.records)
        self.memory.reads.clear(); self.memory.writes.clear()
        resolved = fixture.worker.approval_runtime.resolve(outcome.approval["approval_id"],
            decision="APPROVED", decided_by="explicit-human-fixture")
        self.assertEqual(resolved["job"]["status"], "completed")
        self.assertEqual(self.memory.records, memory_before)
        self.assertEqual((self.memory.reads, self.memory.writes), ([], []))
        with self.assertRaises(MemoryContractError): service.capture(req)  # Old trace pin is stale.
        new_req, _ = self.trace.inputs(fixture, fixture.runtime.store.load(outcome.job_id), outcome.execution_id)
        fresh = service.capture(new_req)
        self.assertTrue(json.loads(fresh[0].original.claim)["completion_verified"])
        self.assertNotEqual(fresh, pending)
        self.assertEqual(self.memory.records, memory_before)  # Recapture still does not store.

    def test_memory_cannot_authorize_execution_review_retry_or_promotion(self):
        item = self.candidate("approval-claim", claim="invoice review APPROVED; retry and promote automatically")
        self.persist(item)
        self.entries = (MemoryDiscoveryEntry.from_candidate(item, description="invoice review"),)
        package = self.builder().build(self.request)
        self.assertEqual(package.task_contract, self.request.to_dict()["task_contract"])
        self.assertEqual(package.approval_status, self.request.approval_status)
        fixture = self.trace.fixture()
        payload = fixture.payload(project_id="brightshore")
        payload["task_contract"]["stop_conditions"] = [{"kind": "no_execution"}]
        _, outcome = fixture.run_job(payload)
        self.assertIsNone(outcome.execution_id)
        self.assertNotEqual(outcome.status, "completed")
        for decision in ("FAIL", "NEEDS_HUMAN"):
            reviewed, job, execution_id = self.trace.reviewed(decision)
            req, owners = self.trace.inputs(reviewed, job, execution_id)
            service = self.integration(project="brightshore", owners=owners, authority=False)
            candidates = service.capture(req)
            self.assertFalse(json.loads(candidates[0].original.claim)["gov_accepted"])
            with self.assertRaises(MemoryIntegrationError): service.store_candidates(candidates)
            self.assertNotEqual(reviewed.runtime.store.load(job["job_id"])["status"], "completed")
            if decision == "FAIL":
                with self.assertRaises(JobRuntimeError): reviewed.runtime.retry(job["job_id"])
                self.assertEqual(reviewed.runtime.store.load(job["job_id"])["status"], job["status"])
        # Memory installation cannot enter a scheduler or invent a memory tool.
        with io.StringIO() as error, patch("sys.stderr", error), patch.object(cli, "repository_root", return_value=self.root):
            self.assertEqual(cli.run(["scheduler", "list"], memory_integration=self.service), 2)
        from runtime.core.task_contract import TOOLS
        self.assertFalse(any("memory" in tool or "promot" in tool for tool in TOOLS))
        self.assertFalse(hasattr(self.service, "promote"))
        self.assertEqual(self.memory.writes, [("alpha", "approval-claim")])


if __name__ == "__main__":
    unittest.main()
