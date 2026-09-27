"""Immutable authoritative continuation-plan persistence."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from runtime.continuation.models import (
    ContinuationContractError,
    continuation_plan_digest,
)
from runtime.core.validation import JobValidationError, JobValidator


class AuthorizedPlanStoreError(ValueError):
    """Raised when canonical continuation-plan authority cannot be proven."""


class FileAuthorizedPlanStore:
    """Create one immutable plan snapshot for each logical continuation root."""

    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.validator = JobValidator(
            Path(__file__).resolve().parents[2]
            / "schemas"
            / "continuation-plan-authorization.schema.json"
        )

    def exists(self, logical_job_id: str) -> bool:
        return self._path(logical_job_id).is_file() or self._manifest_path(
            logical_job_id
        ).is_file()

    def create(
        self,
        logical_job_id: str,
        plan: dict[str, Any],
        *,
        authorized_at: str,
    ) -> dict[str, Any]:
        path = self._path(logical_job_id)
        manifest_path = self._manifest_path(logical_job_id)
        record = self.canonical_record(
            logical_job_id, plan, authorized_at=authorized_at
        )
        if manifest_path.exists():
            if not path.is_file():
                raise AuthorizedPlanStoreError(
                    "Authorized continuation plan authority state is lost; "
                    f"recovery hold is required: {logical_job_id}"
                )
            raise AuthorizedPlanStoreError(
                f"Authorized continuation plan already exists: {logical_job_id}"
            )
        if path.exists():
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan creation evidence is missing; "
                f"recovery hold is required: {logical_job_id}"
            )
        # Creation evidence is deliberately persisted first. If the second
        # write is interrupted, the durable manifest makes the missing anchor
        # a recovery hold rather than permitting a later rebind.
        self._write(manifest_path, record)
        self._write(path, record)
        return deepcopy(record)

    def canonical_record(
        self,
        logical_job_id: str,
        plan: dict[str, Any],
        *,
        authorized_at: str,
    ) -> dict[str, Any]:
        """Build and validate authority before its one permitted persistence."""
        try:
            digest = continuation_plan_digest(plan)
        except ContinuationContractError as error:
            raise AuthorizedPlanStoreError(str(error)) from error
        record: dict[str, Any] = {
            "schema_version": 1,
            "logical_job_id": logical_job_id,
            "plan_id": plan.get("plan_id"),
            "plan_digest": digest,
            "plan": deepcopy(plan),
            "authorized_at": authorized_at,
        }
        self._validate(record, logical_job_id)
        return deepcopy(record)

    def load(self, logical_job_id: str) -> dict[str, Any]:
        path = self._path(logical_job_id)
        manifest_path = self._manifest_path(logical_job_id)
        if not manifest_path.is_file():
            if path.exists():
                raise AuthorizedPlanStoreError(
                    "Authorized continuation plan creation evidence is missing; "
                    f"recovery hold is required: {logical_job_id}"
                )
            raise AuthorizedPlanStoreError(
                f"Authorized continuation plan not found: {logical_job_id}"
            )
        if not path.is_file():
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan authority state is lost; "
                f"recovery hold is required: {logical_job_id}"
            )
        manifest = self._read(manifest_path, logical_job_id, "creation evidence")
        value = self._read(path, logical_job_id, "plan")
        self._validate(manifest, logical_job_id)
        self._validate(value, logical_job_id)
        if value != manifest:
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan does not match durable creation evidence"
            )
        return deepcopy(value)

    def _path(self, logical_job_id: str) -> Path:
        if (
            not isinstance(logical_job_id, str)
            or self._SAFE_ID.fullmatch(logical_job_id) is None
        ):
            raise AuthorizedPlanStoreError(
                "Logical job ID contains unsupported path characters"
            )
        return self.root / f"{logical_job_id}.authorized-plan.json"

    def _manifest_path(self, logical_job_id: str) -> Path:
        self._path(logical_job_id)
        return (
            self.root
            / ".creation-evidence"
            / f"{logical_job_id}.authorized-plan-created.json"
        )

    def _validate(self, value: Any, logical_job_id: str) -> None:
        try:
            self.validator.validate(value)
        except (JobValidationError, TypeError) as error:
            raise AuthorizedPlanStoreError(
                f"Invalid authorized continuation plan record: {error}"
            ) from error
        if value.get("logical_job_id") != logical_job_id:
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan logical identity does not match"
            )
        plan = value.get("plan")
        if plan.get("plan_id") != value.get("plan_id"):
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan ID does not match its snapshot"
            )
        step_ids = [step["step_id"] for step in plan["steps"]]
        if len(step_ids) != len(set(step_ids)):
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan step IDs must be unique"
            )
        try:
            expected_digest = continuation_plan_digest(plan)
        except ContinuationContractError as error:
            raise AuthorizedPlanStoreError(str(error)) from error
        if value.get("plan_digest") != expected_digest:
            raise AuthorizedPlanStoreError(
                "Authorized continuation plan digest does not match its snapshot"
            )

    @staticmethod
    def _read(path: Path, logical_job_id: str, label: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AuthorizedPlanStoreError(
                f"Could not read authorized continuation {label} "
                f"{logical_job_id}: {error}"
            ) from error

    def _write(self, path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open(
                mode="x",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                json.dump(
                    record,
                    handle,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError as error:
            raise AuthorizedPlanStoreError(
                f"Authorized continuation plan already exists: {record['logical_job_id']}"
            ) from error
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise AuthorizedPlanStoreError(
                "Could not persist immutable authorized continuation plan"
            ) from error
