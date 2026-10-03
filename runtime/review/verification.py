"""Deterministic verification gates that run before model review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.actions.models import ExecutionScope, ScopeContractError
from runtime.actions.store import FileMutationArtifactStore, MutationArtifactError
from runtime.execution.models import ExecutionRequest, ExecutionResult
from runtime.providers.artifacts import FileProviderArtifactStore, ProviderArtifactError
from runtime.review.models import DeterministicCheck, VerificationResult
from runtime.storage.execution_store import ExecutionStoreError, FileExecutionStore


class DeterministicVerifier:
    def __init__(
        self,
        execution_store: FileExecutionStore,
        provider_artifact_store: FileProviderArtifactStore,
        mutation_artifact_store: FileMutationArtifactStore | None = None,
    ) -> None:
        self.execution_store = execution_store
        self.provider_artifact_store = provider_artifact_store
        self.mutation_artifact_store = mutation_artifact_store

    def verify(
        self,
        job: dict[str, Any],
        request: ExecutionRequest,
        result: ExecutionResult,
    ) -> VerificationResult:
        execution_ref = {
            "ref_type": "artifact",
            "ref": f"runtime-execution:{result.execution_id}",
            "description": "Immutable normalized execution record",
        }
        checks: list[DeterministicCheck] = []
        checks.append(
            self._check(
                "execution_reviewable",
                result.status in {"succeeded", "needs_review"},
                "Normalized execution produced work eligible for review",
                "Normalized execution did not produce reviewable work",
                (execution_ref,),
            )
        )
        identity_valid = (
            request.job_id == job.get("job_id") == result.job_id
            and request.execution_id == result.execution_id
            and request.agent == job.get("agent")
            and request.skill == job.get("skill")
            and request.workflow == job.get("workflow")
            and request.capability == job.get("capability")
            and request.execution_mode
            == job.get("execution_mode", "READ_ONLY")
            == result.execution_mode
            and request.dry_run == job.get("dry_run", False) == result.dry_run
        )
        checks.append(
            self._check(
                "canonical_identity_preserved",
                identity_valid,
                "Job, request, and execution identities agree",
                "Job, request, and execution identities do not agree",
                (execution_ref,),
            )
        )
        checks.append(
            self._check(
                "review_gate_state",
                job.get("status") == "reviewing" and job.get("review_required") is True,
                "Job is in the canonical reviewing gate",
                "Job is not in the canonical reviewing gate",
                (),
            )
        )

        try:
            stored = self.execution_store.load(result.execution_id, require_authority=True)
            stored_request = stored.request
            stored_result = stored.result.to_dict()
            stored_valid = (
                isinstance(stored_request, dict)
                and isinstance(stored_result, dict)
                and stored_request.get("job_id") == result.job_id
                and stored_result.get("execution_id") == result.execution_id
                and stored_result.get("status") == result.status
                and stored_request.get("execution_mode") == request.execution_mode
                and stored_result.get("execution_mode") == result.execution_mode
                and stored_request.get("dry_run", False) == request.dry_run
                and stored_result.get("dry_run", False) == result.dry_run
                and stored_result.get("evidence") == list(result.evidence)
                and stored_result.get("artifacts") == list(result.artifacts)
                and stored_result.get("blockers") == list(result.blockers)
                and stored_result.get("next_actions") == list(result.next_actions)
                and stored_result.get("retryable") == result.retryable
            )
        except ExecutionStoreError:
            stored_valid = False
        checks.append(
            self._check(
                "execution_artifact_valid",
                stored_valid,
                "Immutable execution artifact exists and matches the result",
                "Execution artifact is missing, malformed, or inconsistent",
                (execution_ref,),
            )
        )

        job_refs = job.get("output_refs", [])
        execution_ref_present = any(
            reference.get("ref") == execution_ref["ref"]
            for reference in job_refs
            if isinstance(reference, Mapping)
        )
        checks.append(
            self._check(
                "execution_evidence_referenced",
                execution_ref_present,
                "Job state references immutable execution evidence",
                "Job state does not reference immutable execution evidence",
                (execution_ref,) if execution_ref_present else (),
            )
        )

        if result.provider is not None:
            provider_ref = {
                "ref_type": "provider_result",
                "ref": f"runtime-provider-output:{result.execution_id}",
                "description": "Bounded provider process output",
            }
            try:
                provider_artifact = self.provider_artifact_store.load(result.execution_id)
                process = provider_artifact.get("process", {})
                selection = provider_artifact.get("selection", {})
                provider_valid = (
                    isinstance(process, dict)
                    and isinstance(selection, dict)
                    and provider_artifact.get("execution_id") == result.execution_id
                    and selection.get("actual_provider") == result.provider
                    and selection.get("execution_mode") == request.execution_mode
                    and process.get("status") == "succeeded"
                    and isinstance(process.get("stdout"), str)
                    and bool(process.get("stdout", "").strip())
                    and len(process.get("stdout", "").encode("utf-8")) <= 1024 * 1024
                    and len(str(process.get("stderr", "")).encode("utf-8")) <= 64 * 1024
                )
            except ProviderArtifactError:
                provider_valid = False
            checks.append(
                self._check(
                    "provider_artifact_valid",
                    provider_valid,
                    "Bounded provider evidence exists and reports success",
                    "Provider evidence is missing, malformed, failed, or oversized",
                    (provider_ref,) if provider_valid else (),
                )
            )

        if request.execution_mode == "CONTROLLED_WRITE":
            mutation_ref = {
                "ref_type": "artifact",
                "ref": f"runtime-mutation:{result.execution_id}",
                "description": "Independent bounded mutation evidence",
            }
            mutation = None
            if self.mutation_artifact_store is not None:
                try:
                    mutation = self.mutation_artifact_store.load(result.execution_id)
                except MutationArtifactError:
                    mutation = None
            try:
                scope = ExecutionScope.from_dict(request.execution_scope or {})
            except ScopeContractError:
                scope = None
            changed = mutation.get("changed_files", []) if isinstance(mutation, dict) else []
            mutation_ref_present = any(
                reference.get("ref") == mutation_ref["ref"]
                for reference in (*result.output_refs, *job.get("output_refs", []))
                if isinstance(reference, Mapping)
            )
            fingerprints_valid = bool(changed) and all(
                isinstance(path, str)
                and mutation.get("post_fingerprints", {}).get(path)
                == mutation.get("target_post_fingerprints", {}).get(path)
                for path in changed
            ) if isinstance(mutation, dict) else False
            integrity = mutation.get("target_integrity", {}) if isinstance(mutation, dict) else {}
            dry_run_valid = (
                request.dry_run
                and isinstance(mutation, dict)
                and mutation.get("dry_run") is True
                and mutation.get("apply_status") == "preview"
                and mutation.get("mutation_kind") == "proposed"
                and mutation.get("proposed_changed_files") == changed
                and mutation.get("applied_changed_files") == []
                and isinstance(integrity, dict)
                and integrity.get("unchanged") is True
                and isinstance(integrity.get("before"), dict)
                and isinstance(integrity.get("after"), dict)
                and integrity["before"].get("fingerprint")
                == integrity["after"].get("fingerprint")
            )
            applied_valid = (
                not request.dry_run
                and isinstance(mutation, dict)
                and mutation.get("dry_run") is False
                and mutation.get("apply_status") == "applied"
                and mutation.get("mutation_kind") == "applied"
                and mutation.get("applied_changed_files") == changed
                and fingerprints_valid
            )
            mutation_valid = (
                isinstance(mutation, dict)
                and scope is not None
                and mutation.get("execution_id") == result.execution_id
                and mutation.get("job_id") == result.job_id
                and mutation.get("execution_mode") == "CONTROLLED_WRITE"
                and mutation.get("scope_fingerprint") == scope.fingerprint
                and mutation.get("scope_violations") == []
                and mutation_ref_present
                and isinstance(changed, list)
                and 0 < len(changed) <= scope.max_changed_files
                and (dry_run_valid or applied_valid)
                and mutation.get("validation", {}).get("status")
                in {"not_configured", "passed"}
            )
            checks.append(
                self._check(
                    "mutation_evidence_valid",
                    mutation_valid,
                    (
                        "Independent evidence confirms a bounded proposal and unchanged target"
                        if request.dry_run
                        else "Independent evidence confirms bounded applied mutations"
                    ),
                    (
                        "Dry-run preview evidence is missing, inconsistent, or the target changed"
                        if request.dry_run
                        else "Mutation evidence is missing, inconsistent, out of scope, or unapplied"
                    ),
                    (mutation_ref,) if mutation_valid else (),
                )
            )
            protected_clear = mutation_valid and not any(
                item.get("code") == "protected_path_violation"
                for item in mutation.get("scope_violations", [])
                if isinstance(item, dict)
            )
            checks.append(
                self._check(
                    "protected_paths_clear",
                    protected_clear,
                    "Mutation evidence contains no protected-path violation",
                    "Protected-path safety could not be established",
                    (mutation_ref,) if protected_clear else (),
                )
            )

        status = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
        return VerificationResult(status=status, checks=tuple(checks))

    @staticmethod
    def _check(
        name: str,
        passed: bool,
        pass_reason: str,
        fail_reason: str,
        evidence_refs: tuple[dict[str, Any], ...],
    ) -> DeterministicCheck:
        return DeterministicCheck(
            name=name,
            status="PASS" if passed else "FAIL",
            reason=pass_reason if passed else fail_reason,
            evidence_refs=evidence_refs if passed else (),
        )
