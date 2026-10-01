"""Construct the production local reviewer runtime from Phase 6E components."""

from __future__ import annotations

from pathlib import Path
from runtime.compute_policy import ComputePolicy

from runtime.actions.store import FileMutationArtifactStore
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.routing import ProviderRouter
from runtime.review.context import ReviewContextBuilder
from runtime.review.reviewers import ProviderBackedReviewer
from runtime.review.runtime import ReviewerRuntime
from runtime.review.store import FileReviewStore
from runtime.review.verification import DeterministicVerifier
from runtime.storage.execution_store import FileExecutionStore


def build_reviewer_runtime(
    repository_root: Path,
    execution_root: Path,
    router: ProviderRouter,
    compute_policy: ComputePolicy | None = None,
) -> ReviewerRuntime:
    execution_store = FileExecutionStore(execution_root)
    provider_store = FileProviderArtifactStore(execution_root / "provider-output")
    mutation_store = FileMutationArtifactStore(execution_root / "mutations")
    return ReviewerRuntime(
        verifier=DeterministicVerifier(execution_store, provider_store, mutation_store),
        context_builder=ReviewContextBuilder(
            repository_root,
            execution_store,
            provider_store,
            mutation_store,
            FileRemoteGitArtifactStore(execution_root / "git"),
        ),
        reviewer=ProviderBackedReviewer(router),
        store=FileReviewStore(execution_root / "reviews"),
        compute_policy=compute_policy,
        repository_root=repository_root,
    )
