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

    def load(self, approval_id: str) -> ApprovalRequest:
        path = self._path(approval_id)
        if not path.is_file():
            raise ApprovalStoreError(f"Approval request not found: {approval_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ApprovalStoreError(
                f"Could not read approval request {approval_id}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise ApprovalStoreError(
                f"Approval request is not an object: {approval_id}"
            )
        try:
            return ApprovalRequest.from_dict(value)
        except ApprovalContractError as error:
            raise ApprovalStoreError(
                f"Approval request is invalid: {approval_id}: {error}"
            ) from error

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
                json.dump(
                    request.to_dict(),
                    handle,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                )
                handle.write("\n")
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
