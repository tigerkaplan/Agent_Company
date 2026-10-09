"""Atomic local JSON-file persistence for canonical jobs."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class JobStoreError(ValueError):
    """Raised when local job persistence cannot satisfy an operation."""


class ClaimLockTimeout(JobStoreError):
    """The bounded canonical claim lock could not be acquired; no mutation."""


class FileJobStore:
    """Store one canonical job per JSON file with a bounded claim lock."""

    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def exists(self, job_id: str) -> bool:
        return self._path(job_id).is_file()

    def create(self, job: dict[str, Any]) -> None:
        path = self._path(job["job_id"])
        if path.exists():
            raise JobStoreError(f"Job already exists: {job['job_id']}")
        self._write(path, job)

    def save(self, job: dict[str, Any]) -> None:
        path = self._path(job["job_id"])
        if not path.is_file():
            raise JobStoreError(f"Job not found: {job['job_id']}")
        self._write(path, job)

    def load(self, job_id: str) -> dict[str, Any]:
        path = self._path(job_id)
        if not path.is_file():
            raise JobStoreError(f"Job not found: {job_id}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, ValueError, RecursionError) as error:
            raise JobStoreError(f"Could not read job {job_id}: {error}") from error
        if not isinstance(value, dict):
            raise JobStoreError(f"Job record is not an object: {job_id}")
        return value

    def list(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        jobs = [self._load_path(path) for path in self.root.glob("*.json")]
        return sorted(jobs, key=lambda job: (job["created_at"], job["job_id"]))

    @contextmanager
    def claim_transaction(self, *, timeout_seconds: float = 5.0):
        """Serialize short claim/recovery mutations across local processes."""

        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / ".claim.lock"
        deadline = time.monotonic() + timeout_seconds
        handle = None
        while handle is None:
            candidate = None
            try:
                try:
                    candidate = lock_path.open("x+b", buffering=0)
                except FileExistsError:
                    candidate = lock_path.open("r+b", buffering=0)
                handle = candidate
            except OSError as error:
                if candidate is not None:
                    candidate.close()
                if time.monotonic() >= deadline:
                    raise ClaimLockTimeout(
                        "Timed out opening the canonical claim lock"
                    ) from error
                time.sleep(0.01)
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError) as error:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise ClaimLockTimeout(
                        "Timed out waiting for the canonical claim lock"
                    ) from error
                time.sleep(0.01)
        try:
            # Windows permits a byte lock beyond EOF. A delayed creator must
            # not flush buffered initialization underneath another owner.
            # Initialize only after owning the same cross-process byte lock.
            if os.fstat(handle.fileno()).st_size == 0:
                handle.seek(0)
                handle.write(b"0")
            yield
        finally:
            try:
                handle.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError as error:
                raise JobStoreError(f"Could not release canonical claim lock: {error}") from error
            finally:
                handle.close()

    def _path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or self._SAFE_ID.fullmatch(job_id) is None:
            raise JobStoreError("Job ID contains unsupported path characters")
        return self.root / f"{job_id}.json"

    def _load_path(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, ValueError, RecursionError) as error:
            raise JobStoreError(f"Could not read job file {path.name}: {error}") from error
        if not isinstance(value, dict):
            raise JobStoreError(f"Job file is not an object: {path.name}")
        return value

    def _write(self, path: Path, job: dict[str, Any]) -> None:
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
                json.dump(job, handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except OSError as error:
            raise JobStoreError(f"Could not persist job {job['job_id']}: {error}") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
