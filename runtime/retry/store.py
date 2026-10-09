"""Atomic, restart-safe persistence for retry policy and bounded decision state."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from runtime.core.validation import JobValidationError, JobValidator
from runtime.retry.models import (
    MAX_HISTORY,
    RetryBinding,
    RetryContractError,
    RetryPolicy,
    history_entry_digest,
    state_digest,
)


class RetryStoreError(ValueError):
    """Raised when retry authority or history cannot be trusted."""


_TRANSACTIONS = threading.local()


class FileRetryStore:
    _SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
    _EVENT_NAME = re.compile(
        r"(?P<sequence>[0-9]{4})-(?P<digest>[a-f0-9]{64})\.retry-decision\.json\Z"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        schema_root = Path(__file__).resolve().parents[2] / "schemas"
        self.policy_validator = JobValidator(schema_root / "retry-policy.schema.json")
        self.state_validator = JobValidator(schema_root / "retry-state.schema.json")

    def exists(self, policy_id: str) -> bool:
        return self._policy_path(policy_id).is_file() or self._manifest_path(policy_id).is_file()

    def create(self, policy: RetryPolicy) -> RetryBinding:
        value = policy.to_dict()
        binding = policy.binding
        policy_path = self._policy_path(binding.policy_id)
        manifest_path = self._manifest_path(binding.policy_id)
        state_path = self._state_path(binding.policy_id)
        if policy_path.exists() or manifest_path.exists() or state_path.exists():
            raise RetryStoreError(f"Retry policy already exists: {binding.policy_id}")
        self._validate_policy(value, binding)
        state = {
            "schema_version": 1,
            "policy_id": binding.policy_id,
            "logical_job_id": binding.logical_job_id,
            "policy_digest": binding.policy_digest,
            "revision": 0,
            "history": [],
            "updated_at": policy.created_at,
        }
        state["state_digest"] = state_digest(state)
        self._validate_state(state, binding, history_limit=policy.history_limit)
        # Creation evidence first makes an interrupted create a durable recovery hold.
        self._write_new(manifest_path, value)
        self._write_new(policy_path, value)
        self._accept_revision(binding, None, None)
        self._write_new(state_path, state)
        return binding

    def load_policy(self, binding_value: Any) -> RetryPolicy:
        try:
            binding = RetryBinding.from_dict(binding_value)
        except RetryContractError as error:
            raise RetryStoreError(str(error)) from error
        manifest_path = self._manifest_path(binding.policy_id)
        policy_path = self._policy_path(binding.policy_id)
        if not manifest_path.is_file() or not policy_path.is_file():
            raise RetryStoreError("Retry policy authority is missing; recovery hold is required")
        manifest = self._read(manifest_path, "retry policy creation evidence")
        value = self._read(policy_path, "retry policy")
        if manifest != value:
            raise RetryStoreError("Retry policy differs from durable creation evidence")
        self._validate_policy(value, binding)
        try:
            return RetryPolicy.from_dict(value)
        except RetryContractError as error:
            raise RetryStoreError(str(error)) from error

    def load_state(self, binding_value: Any, *, history_limit: int) -> dict[str, Any]:
        try:
            binding = RetryBinding.from_dict(binding_value)
        except RetryContractError as error:
            raise RetryStoreError(str(error)) from error
        path = self._state_path(binding.policy_id)
        if not path.is_file():
            raise RetryStoreError("Retry state is missing; recovery hold is required")
        state = self._read(path, "retry state")
        self._validate_state(state, binding, history_limit=history_limit)
        history = state["history"]
        event_paths = self._event_inventory(binding.policy_id)
        claims = self._claim_inventory(binding.policy_id)
        revisions = self._revision_inventory(binding.policy_id)
        accepted = self._sequence_inventory(binding.policy_id, ".accepted-revisions", genesis=True)
        acceptance_creation = self._sequence_inventory(binding.policy_id, ".acceptance-creation", genesis=True)
        if (set(claims) != set(event_paths) or set(revisions) != set(claims)
                or len(event_paths) != len(history)
                or set(accepted) != set(range(len(history) + 1))
                or set(acceptance_creation) != set(accepted)):
            raise RetryStoreError("Retry decision history is incomplete or contains extra events")
        self._verify_acceptance(binding, None, None)
        previous = None
        terminal = None
        for index, entry in enumerate(history, start=1):
            expected = self._event_path(binding.policy_id, index, history_entry_digest(entry))
            if event_paths.get(index) != expected or self._read(expected, "retry decision event") != entry:
                raise RetryStoreError("Retry decision event does not match canonical state")
            claim = self._decision_claim(binding, entry, previous)
            if not self._same_json(self._read(claims[index], "retry decision claim"), claim):
                raise RetryStoreError("Retry history diverged from write-once decision chain")
            if not self._same_json(self._read(revisions[index], "retry revision witness"), claim):
                raise RetryStoreError("Retry history rolled back from independent revision evidence")
            self._verify_acceptance(binding, entry, claim)
            if entry["decision"] in {"STOP", "REPLAN_REQUIRED"} and terminal is None:
                terminal = {**claim, "decision": entry["decision"]}
            previous = history_entry_digest(claim)
        if not self._same_json(self.load_anchor("terminal", binding.policy_id), terminal):
            raise RetryStoreError("Terminal retry decision was removed or diverged from immutable evidence")
        started = self.root / ".history-started" / f"{binding.policy_id}.json"
        head = self.root / ".history-head" / f"{binding.policy_id}.json"
        if history:
            if self._read(started, "retry first-use evidence") != binding.to_dict():
                raise RetryStoreError("Retry first-use evidence is invalid")
            if not self._same_json(self._read(head, "retry high-water evidence"), claim):
                raise RetryStoreError("Retry history rolled back from high-water evidence")
        elif started.exists() or head.exists():
            raise RetryStoreError("Retry history was reset after first use")
        return deepcopy(state)

    def append(self, binding_value: Any, entry: dict[str, Any], *, history_limit: int, updated_at: str) -> dict[str, Any]:
        binding = RetryBinding.from_dict(binding_value)
        state = self.load_state(binding.to_dict(), history_limit=history_limit)
        if len(state["history"]) >= history_limit or len(state["history"]) >= MAX_HISTORY:
            raise RetryStoreError("Retry decision history limit is exhausted")
        sequence = len(state["history"]) + 1
        if entry.get("sequence") != sequence:
            raise RetryStoreError("Retry decision sequence is not contiguous")
        event_path = self._event_path(binding.policy_id, sequence, history_entry_digest(entry))
        previous = None
        if sequence > 1:
            previous = history_entry_digest(self._read(self._claim_path(binding.policy_id, sequence - 1), "retry decision claim"))
        claim = self._decision_claim(binding, entry, previous)
        if entry["decision"] in {"STOP", "REPLAN_REQUIRED"}:
            self.anchor("terminal", binding.policy_id, {**claim, "decision": entry["decision"]})
        # Separate write-once acceptance ledger is the monotonic revision anchor,
        # not the replaceable head/state or the event/claim/witness suffix.
        self._accept_revision(binding, entry, claim)
        if sequence == 1:
            self._write_new(self.root / ".history-started" / f"{binding.policy_id}.json", binding.to_dict())
        # Evidence precedes caches. An interrupted suffix is a hold, never a refund.
        # This independent append-only witness survives event/claim and cache replay.
        self._write_new(self._revision_path(binding.policy_id, sequence), claim)
        self._write_new(event_path, entry)
        self._write_new(self._claim_path(binding.policy_id, sequence), claim)
        self._write_replace(self.root / ".history-head" / f"{binding.policy_id}.json", claim)
        state["history"].append(deepcopy(entry))
        state["revision"] = sequence
        state["updated_at"] = updated_at
        state["state_digest"] = state_digest(state)
        self._validate_state(state, binding, history_limit=history_limit)
        self._write_replace(self._state_path(binding.policy_id), state)
        return deepcopy(state)

    def anchor(self, kind: str, job_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Persist bounded write-once runtime evidence with independent creation evidence.

        The caller holds transaction(). Missing halves never get reconstructed.
        """
        current = self.load_anchor(kind, job_id)
        if current is not None:
            if not self._same_json(current, value):
                raise RetryStoreError(f"Retry {kind} evidence cannot be changed or reused")
            return current
        record, manifest = self._anchor_paths(kind, job_id)
        self._write_new(manifest, value)
        self._write_new(record, value)
        return deepcopy(value)

    def load_anchor(self, kind: str, job_id: str) -> dict[str, Any] | None:
        record, manifest = self._anchor_paths(kind, job_id)
        if not record.exists() and not manifest.exists():
            return None
        if not record.is_file() or not manifest.is_file():
            raise RetryStoreError(f"Retry {kind} evidence is missing; recovery hold is required")
        value = self._read(record, f"retry {kind} evidence")
        if not isinstance(value, dict) or not self._same_json(value, self._read(manifest, f"retry {kind} creation evidence")):
            raise RetryStoreError(f"Retry {kind} evidence diverged from creation evidence")
        return deepcopy(value)

    def _anchor_paths(self, kind: str, job_id: str) -> tuple[Path, Path]:
        if kind not in {"admission", "failure", "execution", "materialized", "attempt-admission",
                        "runtime-failure", "consumed-attempt", "terminal"}:
            raise RetryStoreError("Unknown retry evidence kind")
        self._safe(job_id)
        return (self.root / f".{kind}" / f"{job_id}.json",
                self.root / ".anchor-creation" / kind / f"{job_id}.json")

    def reject_prior_execution_evidence(self, job_id: str) -> None:
        """Missing local indexes cannot hide any surviving retry execution evidence.

        A canonical failed attempt and Worker-observed failure provenance are
        independent evidence, not unused authority. Execution-scoped admission
        and provenance inventories are inspected on both sides of each durable
        pair; even one surviving half requires a hold, never reconstruction.
        """
        self._safe(job_id)
        if self.load_anchor("failure", job_id) is not None:
            raise RetryStoreError("Retry has canonical failed-attempt evidence but no consumption index; recovery hold is required")
        directories = (
            self.root / directory
            for kind in ("admission", "runtime-failure")
            for directory in (f".{kind}", f".anchor-creation/{kind}")
        )
        for directory in directories:
            if not directory.exists():
                continue
            if directory.is_symlink() or not directory.is_dir():
                raise RetryStoreError("Retry execution evidence inventory is unsafe")
            try:
                for path in directory.iterdir():
                    if path.suffix != ".json" or path.is_symlink() or not path.is_file():
                        raise RetryStoreError("Retry execution evidence inventory contains an unsafe entry")
                    self._safe(path.stem)
                    value = self._read(path, "retry execution evidence")
                    if not isinstance(value, dict) or not isinstance(value.get("job_id"), str):
                        raise RetryStoreError("Retry execution evidence identity is malformed")
                    if value["job_id"] == job_id:
                        raise RetryStoreError("Retry has prior canonical execution evidence but no consumption index; recovery hold is required")
            except OSError as error:
                raise RetryStoreError("Could not verify retry execution evidence inventory") from error

    def _acceptance_paths(self, policy_id: str, sequence: int) -> tuple[Path, Path]:
        self._safe(policy_id)
        if type(sequence) is not int or not 0 <= sequence <= MAX_HISTORY:
            raise RetryStoreError("Retry accepted revision is out of bounds")
        return tuple(self.root / directory / policy_id / f"{sequence:04d}.json"
                     for directory in (".accepted-revisions", ".acceptance-creation"))

    @staticmethod
    def _acceptance(binding: RetryBinding, entry: Any, claim: Any) -> dict[str, Any]:
        if entry is None:
            return {"schema_version": 1, **binding.to_dict(), "sequence": 0,
                    "event_digest": None, "previous_claim_digest": None, "decision": None}
        return {**claim, "decision": entry["decision"]}

    def _accept_revision(self, binding: RetryBinding, entry: Any, claim: Any) -> None:
        value = self._acceptance(binding, entry, claim)
        record, creation = self._acceptance_paths(binding.policy_id, value["sequence"])
        self._write_new(creation, value)
        self._write_new(record, value)

    def _verify_acceptance(self, binding: RetryBinding, entry: Any, claim: Any) -> None:
        value = self._acceptance(binding, entry, claim)
        for path in self._acceptance_paths(binding.policy_id, value["sequence"]):
            if not self._same_json(self._read(path, "accepted retry revision"), value):
                raise RetryStoreError("Retry history differs from immutable accepted revision")

    @staticmethod
    def _decision_claim(binding: RetryBinding, entry: dict[str, Any], previous: str | None) -> dict[str, Any]:
        return {"schema_version": 1, **binding.to_dict(), "sequence": entry["sequence"],
                "event_digest": history_entry_digest(entry), "previous_claim_digest": previous}

    def _claim_path(self, policy_id: str, sequence: int) -> Path:
        self._safe(policy_id)
        if type(sequence) is not int or not 1 <= sequence <= MAX_HISTORY:
            raise RetryStoreError("Retry claim sequence is out of bounds")
        return self.root / ".decision-claims" / policy_id / f"{sequence:04d}.json"

    def _claim_inventory(self, policy_id: str) -> dict[int, Path]:
        return self._sequence_inventory(policy_id, ".decision-claims")

    def _revision_path(self, policy_id: str, sequence: int) -> Path:
        # Reuse the same bounded identifier/sequence contract as decision claims.
        self._claim_path(policy_id, sequence)
        return self.root / ".history-revisions" / policy_id / f"{sequence:04d}.json"

    def _revision_inventory(self, policy_id: str) -> dict[int, Path]:
        return self._sequence_inventory(policy_id, ".history-revisions")

    def _sequence_inventory(self, policy_id: str, directory: str, *, genesis: bool = False) -> dict[int, Path]:
        self._safe(policy_id)
        root = self.root / directory / policy_id
        if not root.exists():
            return {}
        if root.is_symlink() or not root.is_dir():
            raise RetryStoreError("Retry decision claim directory is unsafe")
        inventory = {}
        for count, path in enumerate(root.iterdir(), start=1):
            if (count > MAX_HISTORY + int(genesis) or not re.fullmatch(r"[0-9]{4}\.json", path.name)
                    or not path.is_file() or path.is_symlink()
                    or not int(not genesis) <= int(path.stem) <= MAX_HISTORY):
                raise RetryStoreError("Retry decision claims contain an unexpected or unbounded entry")
            inventory[int(path.stem)] = path
        return inventory

    @staticmethod
    def _same_json(left: Any, right: Any) -> bool:
        # Python equality treats True as 1; canonical evidence must not.
        try:
            return history_entry_digest(left) == history_entry_digest(right)
        except RetryContractError as error:
            raise RetryStoreError("Retry evidence is not canonical JSON") from error

    @contextmanager
    def transaction(self, *, timeout_seconds: float = 5.0) -> Iterator[None]:
        # Graph provenance may read this same history inside a canonical writer,
        # including through another store instance. Reuse only this thread's
        # already held OS transaction for this process and canonical directory.
        key = (os.getpid(), self.root.resolve())
        held = getattr(_TRANSACTIONS, "held", None)
        if held is None:
            held = _TRANSACTIONS.held = set()
        if key in held:
            yield
            return
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / ".retry.lock"
        deadline = time.monotonic() + timeout_seconds
        handle = None
        while handle is None:
            candidate = None
            try:
                try:
                    candidate = lock_path.open("x+b")
                    candidate.write(b"0")
                    candidate.flush()
                except FileExistsError:
                    candidate = lock_path.open("r+b")
                    if os.fstat(candidate.fileno()).st_size == 0:
                        candidate.write(b"0")
                        candidate.flush()
                handle = candidate
            except OSError as error:
                if candidate is not None:
                    candidate.close()
                if time.monotonic() >= deadline:
                    raise RetryStoreError("Timed out opening retry-state lock") from error
                time.sleep(0.01)
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError) as error:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise RetryStoreError("Timed out waiting for retry-state lock") from error
                time.sleep(0.01)
        held.add(key)
        try:
            yield
        finally:
            held.remove(key)
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def _validate_policy(self, value: Any, binding: RetryBinding) -> None:
        try:
            self.policy_validator.validate(value)
            policy = RetryPolicy.from_dict(value)
        except (JobValidationError, RetryContractError, TypeError) as error:
            raise RetryStoreError(f"Invalid retry policy: {error}") from error
        if policy.binding != binding:
            raise RetryStoreError("Retry policy binding does not match persisted authority")

    def _validate_state(self, value: Any, binding: RetryBinding, *, history_limit: int) -> None:
        try:
            self.state_validator.validate(value)
        except (JobValidationError, TypeError) as error:
            raise RetryStoreError(f"Invalid retry state: {error}") from error
        if any(value.get(name) != expected for name, expected in (
            ("policy_id", binding.policy_id),
            ("logical_job_id", binding.logical_job_id),
            ("policy_digest", binding.policy_digest),
        )):
            raise RetryStoreError("Retry state binding does not match policy")
        history = value.get("history")
        if len(history) > history_limit or value.get("revision") != len(history):
            raise RetryStoreError("Retry history bounds or revision are inconsistent")
        if [entry.get("sequence") for entry in history] != list(range(1, len(history) + 1)):
            raise RetryStoreError("Retry decision history is not contiguous")
        if len({entry.get("source_job_id") for entry in history}) != len(history):
            raise RetryStoreError("A failed attempt has multiple retry decisions")
        if value.get("state_digest") != state_digest(value):
            raise RetryStoreError("Retry state digest does not match content")

    def _policy_path(self, policy_id: str) -> Path:
        self._safe(policy_id)
        return self.root / f"{policy_id}.json"

    def _manifest_path(self, policy_id: str) -> Path:
        self._safe(policy_id)
        return self.root / ".creation-evidence" / f"{policy_id}.created.json"

    def _state_path(self, policy_id: str) -> Path:
        self._safe(policy_id)
        return self.root / ".state" / f"{policy_id}.state.json"

    def _event_root(self, policy_id: str) -> Path:
        self._safe(policy_id)
        return self.root / ".events" / policy_id

    def _event_path(self, policy_id: str, sequence: int, digest: str) -> Path:
        self._safe(policy_id)
        if not isinstance(sequence, int) or isinstance(sequence, bool) or not 1 <= sequence <= MAX_HISTORY:
            raise RetryStoreError("Retry event sequence is out of bounds")
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise RetryStoreError("Retry event digest is malformed")
        return self._event_root(policy_id) / f"{sequence:04d}-{digest}.retry-decision.json"

    def _event_inventory(self, policy_id: str) -> dict[int, Path]:
        root = self._event_root(policy_id)
        if not root.exists():
            return {}
        if not root.is_dir() or root.is_symlink():
            raise RetryStoreError("Retry decision history directory is unsafe")
        inventory: dict[int, Path] = {}
        try:
            for count, path in enumerate(root.iterdir(), start=1):
                if count > MAX_HISTORY:
                    raise RetryStoreError("Retry decision history exceeds canonical bounds")
                match = self._EVENT_NAME.fullmatch(path.name)
                if match is None or not path.is_file() or path.is_symlink():
                    raise RetryStoreError("Retry decision history contains an unexpected entry")
                sequence = int(match.group("sequence"))
                if sequence in inventory:
                    raise RetryStoreError("Retry decision history contains a duplicate sequence")
                inventory[sequence] = path
        except OSError as error:
            raise RetryStoreError(f"Could not inspect retry decision history: {error}") from error
        return inventory

    def _safe(self, value: Any) -> None:
        if not isinstance(value, str) or self._SAFE_ID.fullmatch(value) is None:
            raise RetryStoreError("Retry identifier contains unsupported path characters")

    @staticmethod
    def _read(path: Path, label: str) -> Any:
        try:
            if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
                raise RetryStoreError(f"Unsafe or unbounded {label}")
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            raise RetryStoreError(f"Could not read {label}: {error}") from error

    def _write_new(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except (FileExistsError, OSError, TypeError, ValueError) as error:
            raise RetryStoreError(f"Could not create retry record {path.name}: {error}") from error

    def _write_replace(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.stem}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as error:
            raise RetryStoreError(f"Could not persist retry state: {error}") from error
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
