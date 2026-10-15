"""Build bounded reviewer context from canonical references and runtime evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.actions.store import FileMutationArtifactStore, MutationArtifactError
from runtime.core.references import CanonicalReferenceResolver
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.git.store import FileGitArtifactStore, GitStoreError
from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.providers.artifacts import FileProviderArtifactStore, ProviderArtifactError
from runtime.providers.context import ExecutionContextBuilder
from runtime.review.models import ReviewEvidence, ReviewPackage, VerificationResult
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore


class ReviewContextBuilder:
    def __init__(
        self,
        repository_root: Path,
        execution_store: FileExecutionStore,
        provider_artifact_store: FileProviderArtifactStore,
        mutation_artifact_store: FileMutationArtifactStore | None = None,
        git_artifact_store: FileGitArtifactStore | None = None,
        learning=None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.execution_store = execution_store
        self.provider_artifact_store = provider_artifact_store
        self.mutation_artifact_store = mutation_artifact_store
        self.git_artifact_store = git_artifact_store
        self.learning = learning

    def build(
        self,
        review_id: str,
        job: dict[str, Any],
        request: ExecutionRequest,
        result: ExecutionResult,
        verification: VerificationResult,
    ) -> ReviewPackage:
        reviewer_refs = CanonicalReferenceResolver(self.repository_root).resolve(
            {
                "agent": "reviewer",
                "skill": "review",
                "workflow": "review",
                "capability": "independent_review",
                "project_id": request.project_id,
            }
        )
        context_request = ExecutionRequest(
            execution_id=f"review-context-{review_id}",
            job_id=request.job_id,
            task=f"Verify execution {result.execution_id} against job intent",
            task_class="review",
            project_id=request.project_id,
            agent="reviewer",
            skill="review",
            workflow="review",
            capability="independent_review",
            provider=None,
            risk_level=request.risk_level,
            input_refs=(),
            context_refs=tuple([*reviewer_refs, *request.context_refs]),
            review_required=False,
            attempt=request.attempt,
            approval_status=request.approval_status,
        )
        context = ExecutionContextBuilder(
            self.repository_root,
            max_file_bytes=128 * 1024,
            max_total_bytes=512 * 1024,
        ).build(context_request).context

        evidence: list[ReviewEvidence] = []
        if self.learning is not None:
            from runtime.memory.learning import LearningReviewInterface, coverage_name, package_coverage_name
            if type(self.learning) is not LearningReviewInterface:
                raise ValueError("Canonical learning review port required")
            value, ref, content = self.learning.evidence(job, request)
            if (not any(c.name == coverage_name(value) and c.status == "PASS" for c in verification.checks)
                    or not any(c.name == package_coverage_name(value, content) and c.status == "PASS"
                               for c in verification.checks)):
                raise ValueError("Learning review package lacks complete deterministic coverage")
            evidence.append(ReviewEvidence(ref=ref, content=content))
        try:
            execution_record = self.execution_store.load(result.execution_id, require_authority=True)
        except ExecutionStoreError:
            execution_record = None
        if execution_record is not None:
            evidence.append(
                ReviewEvidence(
                    ref={
                        "ref_type": "artifact",
                        "ref": f"runtime-execution:{result.execution_id}",
                        "description": "Immutable normalized execution record",
                    },
                    content=bound_text(
                        sanitize_provider_text(
                            json.dumps(
                                execution_record.to_dict(),
                                indent=2,
                                sort_keys=True,
                                ensure_ascii=True,
                            )
                        ),
                        128 * 1024,
                    ),
                )
            )
        if result.provider is not None:
            try:
                provider_record = self.provider_artifact_store.load(result.execution_id)
            except ProviderArtifactError:
                provider_record = None
            if provider_record is not None:
                evidence.append(
                    ReviewEvidence(
                        ref={
                            "ref_type": "provider_result",
                            "ref": f"runtime-provider-output:{result.execution_id}",
                            "description": "Bounded provider process output",
                        },
                        content=bound_text(
                            sanitize_provider_text(
                                json.dumps(
                                    provider_record,
                                    indent=2,
                                    sort_keys=True,
                                    ensure_ascii=True,
                                )
                            ),
                            256 * 1024,
                        ),
                    )
                )
        if request.execution_mode == "CONTROLLED_WRITE" and self.mutation_artifact_store:
            try:
                mutation_record = self.mutation_artifact_store.load(result.execution_id)
            except MutationArtifactError:
                mutation_record = None
            if mutation_record is not None:
                evidence.append(
                    ReviewEvidence(
                        ref={
                            "ref_type": "artifact",
                            "ref": f"runtime-mutation:{result.execution_id}",
                            "description": "Independent bounded mutation evidence",
                        },
                        content=bound_text(
                            sanitize_provider_text(
                                json.dumps(
                                    mutation_record,
                                    indent=2,
                                    sort_keys=True,
                                    ensure_ascii=True,
                                )
                            ),
                            256 * 1024,
                        ),
                    )
                )
        if self.git_artifact_store is not None:
            evidence.extend(self._git_evidence(job))
        return ReviewPackage(
            review_id=review_id,
            job=dict(job),
            execution=result.to_dict(),
            verification=verification,
            context=context,
            evidence=tuple(evidence),
        )

    def _git_evidence(self, job: dict[str, Any]) -> list[ReviewEvidence]:
        """Load only explicitly referenced Git evidence; never grant authority."""

        evidence: list[ReviewEvidence] = []
        for reference in job.get("output_refs", []):
            if not isinstance(reference, dict):
                continue
            ref = str(reference.get("ref", ""))
            try:
                if ref.startswith("runtime-git-change-set:"):
                    identifier = ref.split(":", 1)[1]
                    record = self.git_artifact_store.load_change_set(identifier).to_dict()
                elif ref.startswith("runtime-git-commit:"):
                    identifier = ref.split(":", 1)[1]
                    record = self.git_artifact_store.load_evidence(identifier).to_dict()
                elif isinstance(
                    self.git_artifact_store, FileRemoteGitArtifactStore
                ) and ref.startswith(
                    (
                        "runtime-git-push-plan:",
                        "runtime-git-push:",
                        "runtime-pull-request-plan:",
                        "runtime-pull-request-body:",
                        "runtime-pull-request:",
                    )
                ):
                    identifier = ref.split(":", 1)[1]
                    if ref.startswith("runtime-git-push-plan:"):
                        record = self.git_artifact_store.load_push_plan(identifier).to_dict()
                    elif ref.startswith("runtime-git-push:"):
                        record = self.git_artifact_store.load_push_evidence(identifier).to_dict()
                    elif ref.startswith("runtime-pull-request-plan:"):
                        record = self.git_artifact_store.load_pull_request_plan(identifier).to_dict()
                    elif ref.startswith("runtime-pull-request-body:"):
                        record = {
                            "body": self.git_artifact_store.load_pull_request_body(
                                identifier
                            )
                        }
                    elif ref.startswith("runtime-pull-request:"):
                        record = self.git_artifact_store.load_pull_request_evidence(identifier).to_dict()
                    else:
                        continue
                else:
                    continue
            except GitStoreError:
                continue
            evidence.append(
                ReviewEvidence(
                    ref=dict(reference),
                    content=bound_text(
                        sanitize_provider_text(
                            json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True)
                        ),
                        256 * 1024,
                    ),
                )
            )
        return evidence
