"""Reviewer contract and provider-backed strict-output implementation."""

from __future__ import annotations

import json
from typing import Any, Protocol

from runtime.execution.models import ExecutionRequest
from runtime.providers.adapters import sanitize_provider_text
from runtime.providers.routing import ProviderRouter
from runtime.review.models import (
    REVIEW_DECISIONS,
    ReviewPackage,
    ReviewerResponse,
)


class Reviewer(Protocol):
    def review(self, package: ReviewPackage) -> ReviewerResponse:
        """Evaluate one bounded review package without changing runtime state."""


class ProviderBackedReviewer:
    def __init__(self, router: ProviderRouter) -> None:
        self.router = router

    def review(self, package: ReviewPackage) -> ReviewerResponse:
        executor_provider = package.execution.get("provider")
        risk_level = str(package.job.get("risk_level") or "high")
        selection = self.router.resolve_review(executor_provider, risk_level)
        if selection.actual_provider is None:
            category = (
                "reviewer_unavailable"
                if selection.fallback_reason == "no_provider_available"
                else "independent_reviewer_unavailable"
            )
            return ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="No eligible reviewer provider is available under canonical policy",
                evidence_refs=package.verification.evidence_refs,
                reviewer="reviewer",
                review_provider=None,
                same_provider_review=False,
                model_review_performed=False,
                raw_output="",
                preferred_provider=selection.preferred_provider,
                fallback_used=selection.fallback_used,
                fallback_reason=selection.fallback_reason,
                error_category=category,
            )

        synthetic_request = ExecutionRequest(
            execution_id=f"review-execution-{package.review_id}",
            job_id=str(package.job["job_id"]),
            task=f"Review execution {package.execution['execution_id']}",
            task_class="review",
            project_id=package.job.get("project_id"),
            agent="reviewer",
            skill="review",
            workflow="review",
            capability="independent_review",
            provider=selection.actual_provider,
            risk_level=risk_level,
            input_refs=package.available_evidence_refs,
            context_refs=(),
            review_required=False,
            attempt=int(package.job["attempt"]),
            approval_status=str(package.job["approval_status"]),
        )
        provider_result = self.router.adapters[selection.actual_provider].execute(
            synthetic_request, package
        )
        same_provider = selection.actual_provider == executor_provider
        if provider_result.status == "failed":
            category_map = {
                "provider_unavailable": "reviewer_unavailable",
                "provider_timeout": "review_timeout",
                "provider_execution_failed": "review_provider_execution_failed",
                "invalid_provider_output": "invalid_review_output",
            }
            return ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="Reviewer provider did not return a usable decision",
                evidence_refs=package.verification.evidence_refs,
                reviewer="reviewer",
                review_provider=selection.actual_provider,
                same_provider_review=same_provider,
                model_review_performed=False,
                raw_output=(
                    provider_result.stdout
                    + (
                        "\n[stderr]\n" + provider_result.stderr
                        if provider_result.stderr
                        else ""
                    )
                ),
                preferred_provider=selection.preferred_provider,
                fallback_used=selection.fallback_used,
                fallback_reason=selection.fallback_reason,
                error_category=category_map.get(
                    provider_result.error_category or "", "review_runtime_error"
                ),
            )
        try:
            decision, reason, evidence_refs = self._parse_output(
                provider_result.stdout, package
            )
        except ValueError:
            return ReviewerResponse(
                decision="NEEDS_HUMAN",
                reason="Reviewer provider returned output outside the strict review contract",
                evidence_refs=package.verification.evidence_refs,
                reviewer="reviewer",
                review_provider=selection.actual_provider,
                same_provider_review=same_provider,
                model_review_performed=True,
                raw_output=provider_result.stdout,
                preferred_provider=selection.preferred_provider,
                fallback_used=selection.fallback_used,
                fallback_reason=selection.fallback_reason,
                error_category="invalid_review_output",
            )
        return ReviewerResponse(
            decision=decision,
            reason=reason,
            evidence_refs=evidence_refs,
            reviewer="reviewer",
            review_provider=selection.actual_provider,
            same_provider_review=same_provider,
            model_review_performed=True,
            raw_output=provider_result.stdout,
            preferred_provider=selection.preferred_provider,
            fallback_used=selection.fallback_used,
            fallback_reason=selection.fallback_reason,
        )

    @staticmethod
    def _parse_output(
        raw_output: str,
        package: ReviewPackage,
    ) -> tuple[str, str, tuple[dict[str, Any], ...]]:
        try:
            value = json.loads(raw_output)
        except json.JSONDecodeError as error:
            raise ValueError("Review output is not JSON") from error
        if not isinstance(value, dict) or set(value) != {
            "decision",
            "reason",
            "evidence_refs",
        }:
            raise ValueError("Review output has invalid keys")
        decision = value.get("decision")
        reason = value.get("reason")
        evidence_refs = value.get("evidence_refs")
        if decision not in REVIEW_DECISIONS:
            raise ValueError("Review decision is invalid")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError("Review reason is invalid")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise ValueError("Review evidence is required")
        available = {
            (str(reference.get("ref_type")), str(reference.get("ref"))): reference
            for reference in package.available_evidence_refs
        }
        normalized: list[dict[str, Any]] = []
        for reference in evidence_refs:
            if not isinstance(reference, dict) or set(reference) - {
                "ref_type",
                "ref",
                "description",
            }:
                raise ValueError("Review evidence reference is malformed")
            key = (str(reference.get("ref_type")), str(reference.get("ref")))
            if not all(key) or key not in available:
                raise ValueError("Review cited evidence outside the package")
            normalized.append(dict(available[key]))
        return (
            str(decision),
            sanitize_provider_text(reason).strip(),
            tuple(normalized),
        )
