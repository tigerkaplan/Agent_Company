"""Selected, read-only action evidence -> untrusted MEM-02 candidates.

Configured owners are trusted local code, not caller-supplied paths. Digests
identify retained evidence, not signatures or entailment. A verified GOV receipt
is recorded separately from executor/model success. No candidate is a lesson,
planning constraint, provider write, or promotion (MEM-02B/MEM-03 own those).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace

from runtime.approvals.store import FileApprovalStore
from runtime.actions.store import FileMutationArtifactStore
from runtime.core.task_contract import (
    TaskContractStore, digest, encoded, inspection_load, verify_completion,
)
from runtime.core.validation import JobValidator
from runtime.evals.store import FileEvalStore
from runtime.memory.contracts import (
    ClaimStatus, EvidenceOrigin, MemoryContractError, MemoryRecord,
    SourceEvidence, validate_memory_key,
)
from runtime.memory.lifecycle import LifecycleCandidate, MemoryLink, prepare_candidate
from runtime.progress.runtime import ProgressRuntime
from runtime.progress.store import ProgressStore, inspection_read, readonly_inspection
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.review.store import FileReviewStore
from runtime.storage.execution_store import FileExecutionStore
from runtime.storage.file_store import FileJobStore


class ActionTraceError(MemoryContractError):
    """Unavailable, unsupported, substituted or unbounded selected evidence."""


def _require(condition, message):
    if not condition:
        raise ActionTraceError(message)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceReference:
    """Opaque canonical reference and SHA-256 of canonical owner-returned JSON."""
    ref: str
    sha256: str

    def __post_init__(self):
        _require(type(self) is EvidenceReference, "Noncanonical evidence reference")
        _require(type(self.ref) is str and self.ref.count(":") == 1,
                 "Explicit canonical evidence reference required")
        kind, identity = self.ref.split(":")
        validate_memory_key("reference", identity)
        _require(kind in {"runtime-execution", "runtime-eval", "runtime-review",
                          "runtime-provider-output", "runtime-mutation", "runtime-trace"},
                 "Unsupported evidence reference")
        _require(type(self.sha256) is str and len(self.sha256) == 64
                 and all(c in "0123456789abcdef" for c in self.sha256),
                 "Canonical evidence digest required")

    @property
    def identity(self):
        return self.ref.split(":", 1)[1]


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionTraceRequest:
    project_id: str
    job_id: str
    attempt: int
    execution: EvidenceReference
    trace: EvidenceReference
    evaluation: EvidenceReference | None = None
    review: EvidenceReference | None = None
    outputs: tuple[EvidenceReference, ...] = ()

    def __post_init__(self):
        _require(type(self) is ActionTraceRequest, "Noncanonical action request")
        validate_memory_key(self.project_id, self.job_id)
        _require(type(self.attempt) is int and 1 <= self.attempt <= 100,
                 "Explicit bounded attempt required")
        for value, kind in ((self.execution, "runtime-execution"),
                            (self.trace, "runtime-trace"),
                            (self.evaluation, "runtime-eval"), (self.review, "runtime-review")):
            if value is None:
                _require(kind in {"runtime-eval", "runtime-review"}, "Required evidence missing")
                continue
            _require(type(value) is EvidenceReference, "Noncanonical evidence reference")
            value.__post_init__()
            _require(value.ref.startswith(kind + ":"), "Evidence reference kind mismatch")
        _require(type(self.outputs) is tuple and len(self.outputs) <= 16,
                 "Output reference limit exceeded")
        for value in self.outputs:
            _require(type(value) is EvidenceReference, "Noncanonical output reference")
            value.__post_init__()
            _require(value.ref.split(":")[0] in {"runtime-provider-output", "runtime-mutation"},
                     "Unsupported output inspection path")
        _require(len({v.ref for v in self.outputs}) == len(self.outputs), "Duplicate output reference")


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionTraceOwners:
    jobs: FileJobStore
    tasks: TaskContractStore
    executions: FileExecutionStore
    progress: ProgressStore
    approvals: FileApprovalStore
    evaluations: FileEvalStore
    reviews: FileReviewStore | None = None
    provider_outputs: FileProviderArtifactStore | None = None
    mutation_outputs: FileMutationArtifactStore | None = None

    def validate(self):
        _require(type(self) is ActionTraceOwners, "Configured canonical owners required")
        for owner, cls in ((self.jobs, FileJobStore), (self.tasks, TaskContractStore),
                           (self.executions, FileExecutionStore), (self.progress, ProgressStore),
                           (self.approvals, FileApprovalStore), (self.evaluations, FileEvalStore)):
            _require(type(owner) is cls, "Unsupported canonical inspection owner")
        for owner, cls in ((self.reviews, FileReviewStore),
                           (self.provider_outputs, FileProviderArtifactStore),
                           (self.mutation_outputs, FileMutationArtifactStore)):
            _require(owner is None or type(owner) is cls, "Unsupported output/review owner")
        _require(type(self.tasks.progress) is ProgressRuntime
                 and type(self.tasks.progress.store) is ProgressStore
                 and self.tasks.progress.store.root.resolve() == self.progress.root.resolve(),
                 "Task journal differs from configured owner")
        _require(self.evaluations.root.resolve() == (self.jobs.root.parent / "evals").resolve(),
                 "Completion evaluation owner differs from canonical owner")


def _pin(reference, value):
    _require(digest(value) == reference.sha256, "Selected evidence digest mismatch: " + reference.ref)
    return value


def _root(value, owner):
    _require(type(value) is str and owner is not None
             and Path(value).absolute() == owner.root.absolute(), "Evidence owner substitution")


def _intent_owners(intent, owners, request):
    """Veto evidence-directed owner redirection before canonical nested reads."""
    source = intent["authority_source"]
    for key, owner in (("job_store_root", owners.jobs), ("task_store_root", owners.tasks),
                       ("execution_store_root", owners.executions),
                       ("progress_store_root", owners.progress), ("approval_store_root", owners.approvals)):
        _root(source[key], owner)
    _require(source["job_id"] == request.job_id
             and source["logical_job_id"] == request.trace.identity, "Intent job/trace substitution")
    data = intent["request"]
    _require(data["job_id"] == request.job_id and data["project_id"] == request.project_id
             and type(data["attempt"]) is int and data["attempt"] == request.attempt
             and data["execution_id"] == request.execution.identity, "Intent exact-work substitution")
    _require(not data.get("graph_binding") and not data.get("graph_plan"),
             "Graph inspection requires outside owners")


def _completion_owners(proof, owners):
    for key, owner in (("execution_store_root", owners.executions),
                       ("approval_store_root", owners.approvals), ("review_store_root", owners.reviews),
                       ("provider_store_root", owners.provider_outputs),
                       ("mutation_store_root", owners.mutation_outputs)):
        if proof[key] is not None:
            _root(proof[key], owner)
    if proof["review_ref"] is not None:
        _require(proof["review_store_root"] is not None, "Review completion owner missing")


def build_action_candidates(request: ActionTraceRequest, owners: ActionTraceOwners, *,
                            max_candidate_bytes: int = 128 * 1024
                            ) -> tuple[LifecycleCandidate, ...]:
    """Return two deterministic candidates; raise before returning partial evidence.

    trace pins the complete ordered journal returned for the explicit logical ID.
    Only the selected job's events enter the candidate; other jobs are not read.
    All selected output material is retained, never silently truncated. Oversized
    evidence fails closed. An incomplete/failed action can be observed but cannot
    assert GOV acceptance. A supplied completion proof must fully verify.
    Mutation records with non-null diff_ref are rejected: linked mutation diff
    inspection is unsupported, so their counterevidence cannot be omitted.
    """
    _require(type(request) is ActionTraceRequest and type(owners) is ActionTraceOwners,
             "Explicit request and configured owners required")
    request.__post_init__()
    owners.validate()
    _require(type(max_candidate_bytes) is int and 1 <= max_candidate_bytes <= 128 * 1024,
             "Invalid candidate byte limit")
    try:
        with readonly_inspection():
            candidates = _build(request, owners, max_candidate_bytes)
        # The outer context rechecks evidence bytes before anything is returned.
        return candidates
    except ActionTraceError:
        raise
    except (ValueError, OSError, KeyError, TypeError, AttributeError, RecursionError) as error:
        raise ActionTraceError("Selected action evidence unavailable or inconsistent") from error


def _build(request, owners, limit):
    # This is the same selected job snapshot path used by canonical intent
    # inspection; JobRuntime.show would also reconcile operational state.
    job = json.loads(inspection_read(owners.jobs._path(request.job_id)))
    JobValidator().validate(job)
    _require(job["job_id"] == request.job_id and job["project_id"] == request.project_id
             and type(job["attempt"]) is int and job["attempt"] == request.attempt,
             "Job project/attempt binding mismatch")
    _require("graph_binding" not in job and "graph_plan" not in job,
             "Graph inspection requires outside owners")
    _require(ProgressRuntime.logical_id(job) == request.trace.identity, "Logical trace mismatch")
    owners.tasks.verify(job, inspection=True)

    intent = owners.executions._decision_pair(request.execution.identity, "intent")
    _intent_owners(intent, owners, request)
    record = owners.executions.load(request.execution.identity, require_authority=True, inspection=True)
    execution = _pin(request.execution, record.to_dict())
    _require(record.request == intent["request"], "Execution intent substitution")
    journal = [event.to_dict() for event in owners.progress.read(request.trace.identity, inspection=True)]
    _pin(request.trace, journal)
    selected_events = [event for event in journal if event["job_id"] == request.job_id]
    _require(bool(selected_events), "Selected job has no trace evidence")
    job_refs = {r["ref"] for r in job["output_refs"]}
    material = {request.execution.ref: execution, request.trace.ref: journal,
                "runtime-job:" + request.job_id: job}

    for kind, selected in (("runtime-review:", request.review), ("runtime-eval:", request.evaluation)):
        linked = {ref for ref in job_refs if ref.startswith(kind)}
        _require(not linked or linked == {selected.ref if selected else None},
                 "Linked review/evaluation evidence must be explicitly selected")

    evaluation = None
    if request.evaluation is not None:
        evaluation = inspection_load(owners.evaluations, request.evaluation.identity).to_dict()
        _pin(request.evaluation, evaluation)
        _require(evaluation["job_id"] == request.job_id
                 and evaluation["execution_id"] == request.execution.identity
                 and evaluation["identity"]["execution_digest"] == digest(record.result.to_dict()),
                 "Evaluation exact execution mismatch")
        material[request.evaluation.ref] = evaluation
    review = None
    if request.review is not None:
        _require(owners.reviews is not None, "Review inspection owner missing")
        decisions = owners.reviews._decisions()
        review_intent = decisions._decision_pair(request.review.identity, "review-intent")
        _require(review_intent["parent_decision"] is not None, "Review parent evidence missing")
        _intent_owners(review_intent["parent_decision"], owners, request)
        review = owners.reviews.load(request.review.identity, require_authority=True, inspection=True)
        _pin(request.review, review)
        result = review["result"]
        _require(result["review_id"] == request.review.identity
                 and result["job_id"] == request.job_id and result["execution_id"] == request.execution.identity
                 and review["execution_request_digest"] == digest(record.request)
                 and review["task_contract_digest"] == digest(job["task_contract"])
                 and review_intent["execution_digest"] == digest(record.result.to_dict()),
                 "Review exact-work mismatch")
        material[request.review.ref] = review

    execution_refs = {ref["ref"] for ref in record.result.to_dict()["output_refs"]}
    supported_outputs = {ref for ref in job_refs | execution_refs
                         if ref.startswith(("runtime-provider-output:", "runtime-mutation:"))}
    _require({ref.ref for ref in request.outputs} == supported_outputs,
             "Explicit output references must cover selected job output evidence")
    outputs = {}
    for reference in sorted(request.outputs, key=lambda r: r.ref):
        _require(reference.identity == request.execution.identity
                 and reference.ref in execution_refs,
                 "Output execution/link substitution")
        owner = owners.provider_outputs if reference.ref.startswith("runtime-provider-output:") else owners.mutation_outputs
        _require(owner is not None, "Output inspection owner missing")
        value = _pin(reference, inspection_load(owner, reference.identity))
        _require(value.get("execution_id") == reference.identity, "Output identity mismatch")
        if reference.ref.startswith("runtime-mutation:"):
            _require(value.get("job_id") == request.job_id, "Mutation job substitution")
            _require(value.get("diff_ref") is None, "Mutation diff inspection is unsupported")
        outputs[reference.ref] = value
        material[reference.ref] = value

    proof = job.get("task_completion")
    completion_verified = False
    if proof is not None:
        _completion_owners(proof, owners)
        _require(request.execution.ref in job_refs and job["status"] == "completed"
                 and proof["execution_id"] == request.execution.identity
                 and proof["execution_digest"] == request.execution.sha256,
                 "Completion execution substitution")
        _require(request.evaluation is not None and proof["eval_id"] == request.evaluation.identity
                 and proof["eval_digest"] == request.evaluation.sha256, "Completion evaluation missing/substituted")
        _require(proof["review_ref"] == (request.review.ref if request.review else None)
                 and proof["review_digest"] == (request.review.sha256 if request.review else None),
                 "Completion review missing/substituted")
        _require(all(ref in outputs and digest(outputs[ref]) == pin
                     for ref, pin in proof["artifact_digests"].items()), "Completion output missing/substituted")
        verify_completion(SimpleNamespace(store=owners.jobs, task_contract_store=owners.tasks),
                          job, inspection=True)
        completion_verified = True
        material["runtime-completion:" + request.job_id] = proof
    else:
        _require(job["status"] != "completed", "Completed job has no completion receipt")

    sources = tuple(SourceEvidence(project_id=request.project_id, source_id=ref,
        source_version="sha256:" + digest(value), source_digest=digest(value),
        location=ref, origin=EvidenceOrigin.TOOL) for ref, value in sorted(material.items()))
    common = {"project_id": request.project_id, "job_id": request.job_id,
              "execution_id": request.execution.identity, "attempt": request.attempt,
              "dry_run": record.result.dry_run, "completion_verified": completion_verified,
              "gov_accepted": completion_verified, "trust": "untrusted", "authority": "none"}
    observations = {"kind": "action-trace-observed-records", "version": 1, **common,
        "meaning": "Retained canonical records; no assertion of real-world effects or durable learning",
        "job_status": job["status"], "job_error": job.get("error"),
        "execution_status": record.result.status,
        "task_completion": proof, "evaluation": evaluation,
        "trace_events": selected_events}
    assertions = {"kind": "action-trace-reported-assertions", "version": 1, **common,
        "meaning": "Executor/model assertions and output content; not independently established facts",
        "execution_result": record.result.to_dict(), "review_record": review, "outputs": outputs}
    links = tuple(MemoryLink(project_id=request.project_id, kind="evidence", target=source.location,
                             version=source.source_version) for source in sources)
    result = []
    for body in (observations, assertions):
        claim = encoded(body, max_bytes=limit).decode("utf-8")
        # Bind the identity to all retained provenance as well as prose. A new
        # journal/evaluation version must not reuse a candidate key whose
        # assertion text happens to be unchanged.
        identity = "action-" + digest({"claim": claim, "sources": {
            source.source_id: source.source_digest for source in sources}})
        original = MemoryRecord(project_id=request.project_id, record_id=identity,
            claim=claim, status=ClaimStatus.REPORTED, sources=sources)
        candidate = prepare_candidate(request.project_id, original, record_id=identity + ".candidate", links=links)
        _require(len(candidate.to_memory_record().claim.encode("utf-8")) <= limit,
                 "Serialized candidate limit exceeded")
        result.append(candidate)
    return tuple(result)
