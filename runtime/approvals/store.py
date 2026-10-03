"""Atomic single-resolution persistence for approval requests."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from runtime.approvals.models import ApprovalContractError, ApprovalRequest


class ApprovalStoreError(ValueError):
    """Raised when approval persistence cannot satisfy an operation."""


class FileApprovalStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def exists(self, approval_id: str) -> bool:
        return self._path(approval_id).is_file()

    def create(self, request: ApprovalRequest) -> None:
        path = self._path(request.approval_id)
        if path.exists():
            raise ApprovalStoreError(
                f"Approval request already exists: {request.approval_id}"
            )
        self._write(path, request)

    def resolve(self, request: ApprovalRequest) -> None:
        existing = self.load(request.approval_id)
        if existing.status != "PENDING":
            raise ApprovalStoreError(
                f"Approval is already resolved as {existing.status}"
            )
        immutable_fields = (
            "approval_id",
            "job_id",
            "execution_id",
            "review_id",
            "reason",
            "risk_level",
            "requested_action",
            "evidence_refs",
            "requested_at",
            "execution_mode",
            "execution_scope",
            "authorization_fingerprint",
            "commit_scope",
            "remote_scope",
            "dry_run",
        )
        if any(
            getattr(existing, field) != getattr(request, field)
            for field in immutable_fields
        ):
            raise ApprovalStoreError("Approval resolution changed immutable request data")
        if request.status == "PENDING":
            raise ApprovalStoreError("Approval resolution must be terminal")
        self._write(self._path(request.approval_id), request)

    def load(self, approval_id: str, *, require_canonical: bool = False) -> ApprovalRequest:
        path = self._path(approval_id)
        if not path.is_file():
            raise ApprovalStoreError(f"Approval request not found: {approval_id}")
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            raise ApprovalStoreError(
                f"Could not read approval request {approval_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ApprovalStoreError(
                f"Approval request is not an object: {approval_id}"
            )
        try:
            request = ApprovalRequest.from_dict(value)
            if request.approval_id != approval_id:
                raise ApprovalContractError("Approval artifact identity differs from its path")
            if require_canonical and raw != self._encoded(request).encode("utf-8"):
                raise ApprovalContractError("Approval artifact is not canonical")
            return request
        except ApprovalContractError as error:
            raise ApprovalStoreError(
                f"Approval request is invalid: {approval_id}: {error}"
            ) from error

    def completion_evidence(self, job, execution_id, review_id, *, pinned_refs=None, execution_only=False):
        """Verify completed-task approvals using this canonical approval owner.

        GOV-01 pins returned artifacts; it does not parse approvals or decide
        them. Post-completion Git approvals remain separate authority boundaries.
        """
        from runtime.actions.authorization import authorization_fingerprint
        from runtime.approvals.models import approval_boundary_id
        linked = {r["ref"] for r in job["output_refs"] if r["ref"].startswith("runtime-approval:")}
        fingerprint = authorization_fingerprint(job)
        compact = job.get("approval")
        # Historical annotations are not current approval authority. Select
        # exact canonical boundaries instead of treating every output ref as a
        # required artifact. The receipt freezes this selection at completion.
        candidates = {"runtime-approval:" + approval_boundary_id(job["job_id"], None, None,
            "EXECUTE_JOB", fingerprint)}
        for output in job["output_refs"]:
            if output["ref"].startswith("runtime-execution:"):
                identity = output["ref"].split(":", 1)[1]
                candidates.add("runtime-approval:" + approval_boundary_id(job["job_id"], identity, None,
                    "RESOLVE_HUMAN_CONDITION", fingerprint))
        if compact is not None:
            candidates.add(f"runtime-approval:{compact.get('approval_id')}")
        refs = sorted(candidates & linked)
        if pinned_refs is not None:
            if (type(pinned_refs) is not list or len(pinned_refs) > 64
                    or any(type(ref) is not str or not ref.startswith("runtime-approval:") for ref in pinned_refs)
                    or len(set(pinned_refs)) != len(pinned_refs) or not set(pinned_refs) <= linked):
                raise ApprovalStoreError("Pinned task approval evidence is malformed or unlinked")
            refs = pinned_refs
        records = {}
        actions = set()
        for ref in refs:
            request = self.load(ref.split(":", 1)[1])
            if request.requested_action not in {"EXECUTE_JOB", "RESOLVE_HUMAN_CONDITION", "COMPLETE_REVIEWED_JOB"}:
                if pinned_refs is not None:
                    raise ApprovalStoreError("Pinned approval cannot substitute Git authority")
                continue
            if (request.status != "APPROVED" or request.decision_actor_type != "local_operator"
                    or request.job_id != job["job_id"] or request.authorization_fingerprint != fingerprint
                    or request.risk_level != job["risk_level"]
                    or request.execution_mode != job["execution_mode"]
                    or request.execution_scope != job.get("execution_scope")
                    or request.dry_run != job.get("dry_run", False)
                    or request.approval_id != approval_boundary_id(request.job_id, request.execution_id,
                        request.review_id, request.requested_action, fingerprint)):
                raise ApprovalStoreError("Task approval evidence is unresolved, stale or outside exact authority")
            if request.requested_action == "COMPLETE_REVIEWED_JOB":
                evidence = {r["ref"] for r in request.evidence_refs}
                if (request.execution_id != execution_id or request.review_id != review_id
                        or not {f"runtime-execution:{execution_id}", f"runtime-review:{review_id}"} <= evidence):
                    raise ApprovalStoreError("Completion approval does not bind current execution/review evidence")
            if request.requested_action == "RESOLVE_HUMAN_CONDITION":
                if f"runtime-execution:{request.execution_id}" not in {r["ref"] for r in request.evidence_refs}:
                    raise ApprovalStoreError("Human-condition approval has no bound execution evidence")
            records[ref] = request.to_dict()
            actions.add(request.requested_action)
        gates = job["task_contract"]["approval_requirements"]
        if gates["execution"] and not actions & {"EXECUTE_JOB", "RESOLVE_HUMAN_CONDITION"}:
            raise ApprovalStoreError("Required execution approval artifact is missing")
        if not execution_only and gates["completion"] and "COMPLETE_REVIEWED_JOB" not in actions:
            raise ApprovalStoreError("Required completion approval artifact is missing")
        if compact is not None:
            ref = f"runtime-approval:{compact.get('approval_id')}"
            if ref not in records or ApprovalRequest.from_dict(records[ref]).compact() != compact:
                raise ApprovalStoreError("Compact task approval differs from its canonical artifact")
        if job.get("approval_status") == "approved" and compact is None:
            raise ApprovalStoreError("Approved task has no canonical approval linkage")
        return records

    def list(self, status: str | None = None) -> list[ApprovalRequest]:
        if not self.root.exists():
            return []
        requests = [
            self.load(path.name.removesuffix(".approval.json"))
            for path in self.root.glob("*.approval.json")
        ]
        if status is not None:
            requests = [request for request in requests if request.status == status]
        status_order = {"PENDING": 0, "APPROVED": 1, "REJECTED": 2}
        return sorted(
            requests,
            key=lambda request: (
                status_order[request.status],
                request.requested_at,
                request.approval_id,
            ),
        )

    def _path(self, approval_id: str) -> Path:
        if self._SAFE_ID.fullmatch(approval_id) is None:
            raise ApprovalStoreError(
                "Approval ID contains unsupported path characters"
            )
        return self.root / f"{approval_id}.approval.json"

    def _write(self, path: Path, request: ApprovalRequest) -> None:
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
                handle.write(self._encoded(request))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise ApprovalStoreError(
                f"Could not persist approval request {path.stem}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _encoded(request: ApprovalRequest) -> str:
        return json.dumps(request.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
