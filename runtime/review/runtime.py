"""Coordinate deterministic verification, reviewer execution, and persistence."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable
from uuid import uuid4

from runtime.core.jobs import utc_now
from runtime.compute_policy import ComputePolicy
from runtime.compute_policy.canonical import bind_project_context, canonical_inputs
from runtime.compute_policy.policy import ComputeError
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.review.context import ReviewContextBuilder
from runtime.review.models import (
    REVIEW_DECISIONS,
    ReviewResult,
    ReviewRun,
    ReviewerResponse,
)
from runtime.review.reviewers import Reviewer
from runtime.review.store import FileReviewStore
from runtime.review.verification import DeterministicVerifier


class ReviewRuntimeError(ValueError):
    """Raised when the review gate cannot persist a normalized decision."""


def new_review_id() -> str:
    return f"review-{uuid4().hex}"


class ReviewerRuntime:
    def __init__(
        self,
        verifier: DeterministicVerifier,
        context_builder: ReviewContextBuilder,
        reviewer: Reviewer,
        store: FileReviewStore,
        *,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] = new_review_id,
        compute_policy: ComputePolicy | None = None,
        repository_root=None,
    ) -> None:
        self.verifier = verifier
        self.context_builder = context_builder
        self.reviewer = reviewer
        self.store = store
        self.clock = clock
        self.id_factory = id_factory
        self.compute_policy = compute_policy
        self.repository_root = repository_root

    def run(
        self,
        job: dict[str, Any],
        request: ExecutionRequest,
        execution_result: ExecutionResult,
        *, compute_budget_decision=None,
    ) -> ReviewRun:
        review_id = self.id_factory()
        verification = self.verifier.verify(job, request, execution_result)
        try:
            package = self.context_builder.build(
                review_id, job, request, execution_result, verification
            )
            if self.compute_policy is not None:
                if job.get('execution_budget') is not None and compute_budget_decision is None:
                    raise ComputeError('Reviewer compute budget snapshot unavailable')
                inputs = canonical_inputs(request, job, compute_budget_decision)
                inputs = bind_project_context(inputs, self.repository_root, package.render())
                decision = self.compute_policy.decide(request, inputs)
                package = replace(package, eligible_providers=decision.eligible_providers,
                                  compute_decision=decision)
        except Exception as error:
            raise ReviewRuntimeError(
                "Review context could not be built from persisted execution evidence"
            ) from error

        if verification.status == "FAIL":
            response = ReviewerResponse(
                decision="FAIL",
                reason="Deterministic verification conclusively rejected the execution",
                evidence_refs=verification.evidence_refs,
                reviewer="deterministic-verifier",
                review_provider=None,
                same_provider_review=False,
                model_review_performed=False,
                raw_output="",
                error_category="deterministic_verification_failure",
            )
        else:
            try:
                response = self.reviewer.review(package)
            except Exception:
                response = ReviewerResponse(
                    decision="NEEDS_HUMAN",
                    reason="Reviewer runtime raised an internal error",
                    evidence_refs=verification.evidence_refs,
                    reviewer="reviewer",
                    review_provider=None,
                    same_provider_review=False,
                    model_review_performed=False,
                    raw_output="",
                    error_category="review_runtime_error",
                )
        if not isinstance(response, ReviewerResponse):
            response = ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="Reviewer returned an invalid response object",
                evidence_refs=verification.evidence_refs,
                reviewer="reviewer",
                review_provider=None,
                same_provider_review=False,
                model_review_performed=False,
                raw_output="",
                error_category="invalid_review_output",
            )
        if response.decision not in REVIEW_DECISIONS:
            response = ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="Reviewer returned an unsupported decision",
                evidence_refs=verification.evidence_refs,
                reviewer=response.reviewer or "reviewer",
                review_provider=response.review_provider,
                same_provider_review=response.same_provider_review,
                model_review_performed=response.model_review_performed,
                raw_output=response.raw_output,
                preferred_provider=response.preferred_provider,
                fallback_used=response.fallback_used,
                fallback_reason=response.fallback_reason,
                error_category="invalid_review_output",
            )
        available_evidence = {
            (str(reference.get("ref_type")), str(reference.get("ref"))): reference
            for reference in package.available_evidence_refs
        }
        response_evidence_valid = all(
            (
                str(reference.get("ref_type")),
                str(reference.get("ref")),
            )
            in available_evidence
            for reference in response.evidence_refs
            if isinstance(reference, dict)
        ) and all(isinstance(reference, dict) for reference in response.evidence_refs)
        if (
            not isinstance(response.reason, str)
            or not response.reason.strip()
            or len(response.reason) > 2000
            or not response_evidence_valid
        ):
            response = ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="Reviewer response failed runtime validation",
                evidence_refs=verification.evidence_refs,
                reviewer=response.reviewer or "reviewer",
                review_provider=response.review_provider,
                same_provider_review=response.same_provider_review,
                model_review_performed=response.model_review_performed,
                raw_output=response.raw_output,
                preferred_provider=response.preferred_provider,
                fallback_used=response.fallback_used,
                fallback_reason=response.fallback_reason,
                error_category="invalid_review_output",
            )
        else:
            canonical_evidence = tuple(
                dict(
                    available_evidence[
                        (
                            str(reference.get("ref_type")),
                            str(reference.get("ref")),
                        )
                    ]
                )
                for reference in response.evidence_refs
            )
            response = replace(
                response,
                reason=bound_text(sanitize_provider_text(response.reason), 2000).strip(),
                evidence_refs=canonical_evidence,
            )
        if response.decision == "PASS" and (
            not response.evidence_refs or verification.status != "PASS"
        ):
            response = ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="Reviewer PASS lacked independently verified evidence",
                evidence_refs=verification.evidence_refs,
                reviewer=response.reviewer,
                review_provider=response.review_provider,
                same_provider_review=response.same_provider_review,
                model_review_performed=response.model_review_performed,
                raw_output=response.raw_output,
                preferred_provider=response.preferred_provider,
                fallback_used=response.fallback_used,
                fallback_reason=response.fallback_reason,
                error_category="missing_evidence",
            )
        result = ReviewResult(
            review_id=review_id,
            job_id=request.job_id,
            execution_id=execution_result.execution_id,
            reviewer=response.reviewer,
            review_provider=response.review_provider,
            same_provider_review=response.same_provider_review,
            model_review_performed=response.model_review_performed,
            decision=response.decision,
            reason=response.reason,
            evidence_refs=response.evidence_refs,
            deterministic_checks=tuple(
                check.to_dict() for check in verification.checks
            ),
            created_at=self.clock(),
            preferred_provider=response.preferred_provider,
            fallback_used=response.fallback_used,
            fallback_reason=response.fallback_reason,
            error_category=response.error_category,
        )
        try:
            artifact_ref = self.store.create(package, result, response.raw_output)
        except Exception as error:
            raise ReviewRuntimeError("Review artifact could not be persisted") from error
        return ReviewRun(result=result, artifact_ref=artifact_ref)
