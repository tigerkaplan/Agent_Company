"""Atomic local persistence for review artifacts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from runtime.providers.adapters import bound_text, sanitize_provider_text
from runtime.review.models import ReviewPackage, ReviewResult


class ReviewStoreError(ValueError):
    """Raised when review artifacts cannot be persisted or loaded."""


class FileReviewStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _decisions(self):
        from runtime.storage.execution_store import FileExecutionStore
        return FileExecutionStore(self.root)

    def begin_decision(self, review_id, job, request, execution, reviewer):
        from runtime.core.capability_governance import evaluate, require_review_dispatch, dispatch_intent
        from runtime.core.task_contract import digest
        require_review_dispatch(request)
        if (job["job_id"] != request.job_id or job["task_contract"] != request.to_dict()["task_contract"]
                or execution.job_id != request.job_id or execution.execution_id != request.execution_id):
            raise ReviewStoreError("Review decision does not bind exact authorized work")
        value = {"schema_version": 1, "requested_action": "REVIEW",
                 "request_digest": digest(request.to_dict()),
                 "execution_digest": digest(execution.to_dict()),
                 "policy_evaluation": evaluate(job),
                 "authority_source": {"job_id": job["job_id"],
                                      "task_contract_digest": digest(job["task_contract"])},
                 "approval_required": job["task_contract"]["approval_requirements"],
                 "approval_received": "parent-dispatch-verified" if job["task_contract"]["approval_requirements"]["execution"] else "not-required",
                 "executor": reviewer, "parent_decision": dispatch_intent()}
        if value["parent_decision"] is not None:
            self._decisions()._observe(value["parent_decision"], "decision_review_observed", review_id, digest(value))
        return self._decisions()._decision_pair(review_id, "review-intent", value)

    def create(
        self,
        package: ReviewPackage,
        result: ReviewResult,
        raw_output: str,
        *, execution_request: dict | None = None,
    ) -> dict[str, Any]:
        path = self._path(result.review_id)
        if path.exists():
            raise ReviewStoreError(f"Review artifact already exists: {result.review_id}")
        record = {
            "schema_version": 1,
            "package": bound_text(
                sanitize_provider_text(package.render()), 768 * 1024
            ),
            "raw_output": bound_text(sanitize_provider_text(raw_output), 256 * 1024),
            "result": result.to_dict(),
        }
        from runtime.core.task_contract import digest
        record["task_contract_digest"] = digest(package.job.get("task_contract"))
        record["execution_request_digest"] = digest(execution_request)
        decisions = self._decisions()
        paths = [decisions._decision_path(result.review_id, "review-intent", s) for s in ("anchor", "witness")]
        intent = decisions._decision_pair(result.review_id, "review-intent") if any(p.exists() for p in paths) else None
        if intent is not None and intent["request_digest"] != record["execution_request_digest"]:
            raise ReviewStoreError("Review decision does not bind the exact execution request")
        trace = {
            "schema_version": 1, "record_digest": digest(record),
            "intent_digest": digest(intent) if intent is not None else None,
            "evidence": result.to_dict()["evidence_refs"]}
        if intent is not None and intent["parent_decision"] is not None:
            decisions._observe(intent["parent_decision"], "decision_result_observed", result.review_id, digest(trace))
        decisions._decision_pair(result.review_id, "review-result", trace)
        self._write(path, record)
        return {
            "ref_type": "review",
            "ref": f"runtime-review:{result.review_id}",
            "description": "Normalized review decision and bounded evidence package",
        }

    def load(self, review_id: str, *, require_authority=False, inspection=False) -> dict[str, Any]:
        if type(inspection) is not bool:
            raise ReviewStoreError("Inspection flag must be a boolean")
        if inspection:
            from runtime.progress.store import readonly_inspection
            with readonly_inspection():
                return self.load(review_id, require_authority=require_authority)
        path = self._path(review_id)
        if not path.is_file():
            raise ReviewStoreError(f"Review artifact not found: {review_id}")
        try:
            from runtime.progress.store import inspection_active, inspection_read
            value = json.loads(inspection_read(path)) if inspection_active() else json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            raise ReviewStoreError(
                f"Could not read review artifact {review_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ReviewStoreError(f"Review artifact is not an object: {review_id}")
        from runtime.core.task_contract import digest
        from runtime.storage.execution_store import ExecutionStoreError
        try:
            trace = self._decisions()._decision_pair(review_id, "review-result")
            if trace != {"schema_version": 1, "record_digest": digest(value),
                         "intent_digest": trace.get("intent_digest"),
                         "evidence": value["result"]["evidence_refs"]}:
                raise ReviewStoreError("Review result trace is stale or tampered")
            if require_authority and trace["intent_digest"] is None:
                raise ReviewStoreError("Imported review observation has no review authority")
            if trace["intent_digest"] is not None:
                intent = self._decisions()._decision_pair(review_id, "review-intent")
                if digest(intent) != trace["intent_digest"] or intent["request_digest"] != value["execution_request_digest"]:
                    raise ReviewStoreError("Review intent trace is stale or tampered")
                if require_authority and intent["parent_decision"] is None:
                    raise ReviewStoreError("Review has no canonical parent authority")
                if intent["parent_decision"] is not None:
                    decisions = self._decisions()
                    decisions._verify_intent(intent["parent_decision"])
                    from runtime.storage.execution_store import FileExecutionStore
                    parent_store = FileExecutionStore(Path(intent["parent_decision"]["authority_source"]["execution_store_root"]))
                    parent_store._verify_consumption(intent["parent_decision"], "dispatch-review", {
                        "schema_version": 1, "intent_digest": digest(intent["parent_decision"]), "purpose": "review"})
                    decisions._verify_observation(intent["parent_decision"], "decision_review_observed", review_id, digest(intent))
                    decisions._verify_observation(intent["parent_decision"], "decision_result_observed", review_id, digest(trace))
        except (ExecutionStoreError, KeyError, TypeError) as error:
            raise ReviewStoreError("Review trace unavailable; explicit recovery required") from error
        return value

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        values = [
            self.load(path.name.removesuffix(".review.json"))
            for path in self.root.glob("*.review.json")
        ]
        return sorted(
            values,
            key=lambda value: (
                value.get("result", {}).get("created_at", ""),
                value.get("result", {}).get("review_id", ""),
            ),
        )

    def _path(self, review_id: str) -> Path:
        if self._SAFE_ID.fullmatch(review_id) is None:
            raise ReviewStoreError("Review ID contains unsupported path characters")
        return self.root / f"{review_id}.review.json"

    def _write(self, path: Path, record: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(record, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise ReviewStoreError(
                f"Could not persist review artifact {path.stem}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
