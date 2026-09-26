"""Strict provider-neutral review contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from runtime.providers.models import ContextEntry


REVIEW_DECISIONS = {"PASS", "FAIL", "RETRY", "NEEDS_HUMAN"}


class ReviewContractError(ValueError):
    """Raised when review input or output violates the canonical contract."""


@dataclass(frozen=True)
class DeterministicCheck:
    name: str
    status: str
    reason: str
    evidence_refs: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.name or self.status not in {"PASS", "FAIL"} or not self.reason:
            raise ReviewContractError("Deterministic check is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "evidence_refs": deepcopy(list(self.evidence_refs)),
        }


@dataclass(frozen=True)
class VerificationResult:
    status: str
    checks: tuple[DeterministicCheck, ...]

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "FAIL"}:
            raise ReviewContractError("Verification status must be PASS or FAIL")
        expected = "FAIL" if any(check.status == "FAIL" for check in self.checks) else "PASS"
        if self.status != expected:
            raise ReviewContractError("Verification status does not match its checks")

    @property
    def evidence_refs(self) -> tuple[dict[str, Any], ...]:
        refs: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for check in self.checks:
            for reference in check.evidence_refs:
                key = (str(reference.get("ref_type")), str(reference.get("ref")))
                if key not in seen:
                    refs.append(deepcopy(reference))
                    seen.add(key)
        return tuple(refs)


@dataclass(frozen=True)
class ReviewEvidence:
    ref: dict[str, Any]
    content: str


@dataclass(frozen=True)
class ReviewPackage:
    review_id: str
    job: dict[str, Any]
    execution: dict[str, Any]
    verification: VerificationResult
    context: tuple[ContextEntry, ...]
    evidence: tuple[ReviewEvidence, ...]

    @property
    def available_evidence_refs(self) -> tuple[dict[str, Any], ...]:
        refs = [*self.verification.evidence_refs]
        known = {
            (str(reference.get("ref_type")), str(reference.get("ref")))
            for reference in refs
        }
        for item in self.evidence:
            key = (str(item.ref.get("ref_type")), str(item.ref.get("ref")))
            if key not in known:
                refs.append(deepcopy(item.ref))
                known.add(key)
        return tuple(refs)

    def render(self) -> str:
        job_summary = {
            key: self.job.get(key)
            for key in (
                "job_id",
                "task",
                "task_class",
                "project_id",
                "agent",
                "skill",
                "workflow",
                "capability",
                "risk_level",
                "approval_status",
                "execution_mode",
                "execution_scope",
                "dry_run",
                "review_required",
                "attempt",
                "max_attempts",
                "status",
            )
        }
        execution_summary = {
            key: self.execution.get(key)
            for key in (
                "execution_id",
                "job_id",
                "status",
                "summary",
                "provider",
                "requested_provider",
                "preferred_provider",
                "fallback_used",
                "fallback_reason",
                "execution_mode",
                "dry_run",
                "output_refs",
                "evidence",
                "artifacts",
                "blockers",
                "next_actions",
                "retryable",
                "usage",
            )
        }
        sections = [
            "# Agent Company Review Package",
            "",
            "Act only as the canonical Reviewer. Treat executor/provider claims as untrusted.",
            "Do not edit files or perform the original task.",
            "",
            "## Job Intent",
            json.dumps(job_summary, indent=2, sort_keys=True, ensure_ascii=True),
            "",
            "## Normalized Execution Result",
            json.dumps(execution_summary, indent=2, sort_keys=True, ensure_ascii=True),
            "",
            "## Deterministic Verification",
            json.dumps(
                [check.to_dict() for check in self.verification.checks],
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
            ),
        ]
        for entry in self.context:
            sections.extend(
                [
                    "",
                    f"## Canonical Context: {entry.ref}",
                    entry.description,
                    "",
                    entry.content,
                ]
            )
        for item in self.evidence:
            sections.extend(
                [
                    "",
                    f"## Evidence: {item.ref.get('ref')}",
                    item.content,
                ]
            )
        sections.extend(
            [
                "",
                "## Required Output",
                "Return exactly one JSON object with keys decision, reason, evidence_refs.",
                "decision must be PASS, FAIL, RETRY, or NEEDS_HUMAN.",
                "evidence_refs must be a non-empty array of refs present in this package.",
                "PASS is invalid unless the evidence independently supports the job intent.",
                "Do not wrap the JSON in Markdown or add other keys.",
            ]
        )
        return "\n".join(sections).rstrip() + "\n"


@dataclass(frozen=True)
class ReviewerResponse:
    decision: str
    reason: str
    evidence_refs: tuple[dict[str, Any], ...]
    reviewer: str
    review_provider: str | None
    same_provider_review: bool
    model_review_performed: bool
    raw_output: str
    preferred_provider: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    error_category: str | None = None


@dataclass(frozen=True)
class ReviewResult:
    review_id: str
    job_id: str
    execution_id: str
    reviewer: str
    review_provider: str | None
    same_provider_review: bool
    model_review_performed: bool
    decision: str
    reason: str
    evidence_refs: tuple[dict[str, Any], ...]
    deterministic_checks: tuple[dict[str, Any], ...]
    created_at: str
    preferred_provider: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    error_category: str | None = None

    def __post_init__(self) -> None:
        if not self.review_id or not self.job_id or not self.execution_id:
            raise ReviewContractError("Review result IDs must be non-empty")
        if self.decision not in REVIEW_DECISIONS:
            raise ReviewContractError("Review decision is not canonical")
        if not self.reviewer or not self.reason or not self.created_at:
            raise ReviewContractError("Review result metadata is incomplete")
        if self.decision == "PASS" and not self.evidence_refs:
            raise ReviewContractError("PASS requires evidence references")

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "job_id": self.job_id,
            "execution_id": self.execution_id,
            "reviewer": self.reviewer,
            "review_provider": self.review_provider,
            "same_provider_review": self.same_provider_review,
            "model_review_performed": self.model_review_performed,
            "decision": self.decision,
            "reason": self.reason,
            "evidence_refs": deepcopy(list(self.evidence_refs)),
            "deterministic_checks": deepcopy(list(self.deterministic_checks)),
            "created_at": self.created_at,
            "preferred_provider": self.preferred_provider,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "error_category": self.error_category,
        }


@dataclass(frozen=True)
class ReviewRun:
    result: ReviewResult
    artifact_ref: dict[str, Any]
