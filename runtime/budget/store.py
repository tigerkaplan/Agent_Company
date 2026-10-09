"""Atomic immutable policy and restart-safe usage persistence for budgets."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from runtime.budget.models import (
    BudgetBinding,
    BudgetContractError,
    BudgetPolicy,
    BudgetUsageAnchor,
    BudgetUsageClaim,
    MAX_EXECUTION_UNITS,
    MAX_STATE_SEQUENCE,
    budget_state_digest,
    parse_timestamp,
    reservation_history_digest,
)
from runtime.core.validation import JobValidationError, JobValidator


class ExecutionBudgetStoreError(ValueError):
    """Raised when canonical budget persistence cannot be trusted."""


class BudgetLockTimeout(ExecutionBudgetStoreError):
    """No budget transaction was entered; capacity and evidence are unknown."""


class FileExecutionBudgetStore:
    """Persist immutable policies and atomically updated logical-job usage."""

    _SAFE_ID = re.compile(r"budget-[a-f0-9]{32}\Z")
    _CLAIM_NAME = re.compile(r"([0-9]{20})\.json\Z")
    _EVENT_NAME = re.compile(r"([0-9]{20})-([a-f0-9]{64})\.json\Z")
    _MAX_USAGE_EVENTS = 2 * MAX_EXECUTION_UNITS + 2

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        schemas = Path(__file__).resolve().parents[2] / "schemas"
        self.policy_validator = JobValidator(schemas / "execution-budget.schema.json")
        self.state_validator = JobValidator(schemas / "budget-state.schema.json")
        self.usage_anchor_validator = JobValidator(
            schemas / "budget-usage-anchor.schema.json"
        )
        self.usage_claim_validator = JobValidator(
            schemas / "budget-usage-claim.schema.json"
        )

    def exists(self, budget_id: str) -> bool:
        return self._policy_path(budget_id).exists() or self._manifest_path(
            budget_id
        ).exists() or self._usage_head_path(budget_id).exists() or self._usage_claims_dir(
            budget_id
        ).exists()

    def create(self, policy: BudgetPolicy) -> BudgetBinding:
        with self.transaction():
            record = policy.to_dict()
            self._validate_policy(record, policy.budget_id)
            path = self._policy_path(policy.budget_id)
            manifest_path = self._manifest_path(policy.budget_id)
            state_path = self._state_path(policy.budget_id)
            if manifest_path.exists() or path.exists() or state_path.exists():
                raise ExecutionBudgetStoreError(
                    f"Execution budget already exists: {policy.budget_id}"
                )
            state = self._initial_state(policy)
            self._validate_state(state, policy)
            # Creation evidence is first: interruption can only cause a fail-closed
            # incomplete authority anchor, never a later policy rebind.
            self._write(manifest_path, record)
            self._write(path, record)
            anchor = BudgetUsageAnchor.create(
                policy, state, previous_anchor_digest=None
            )
            claim = BudgetUsageClaim.create(
                policy, anchor, previous_claim_digest=None
            )
            self._write_once(
                self._usage_event_path(policy.budget_id, 0, anchor.digest),
                anchor.to_dict(),
            )
            self._write_once(
                self._usage_claim_path(policy.budget_id, 0), claim.to_dict()
            )
            self._write(self._usage_head_path(policy.budget_id), anchor.to_dict())
            self._write(state_path, state)
            return policy.binding

    def load_policy(self, binding: BudgetBinding) -> BudgetPolicy:
        path = self._policy_path(binding.budget_id)
        manifest_path = self._manifest_path(binding.budget_id)
        if not manifest_path.is_file() or not path.is_file():
            raise ExecutionBudgetStoreError(
                "Execution budget policy authority is incomplete; execution is denied"
            )
        manifest = self._read(manifest_path, "budget policy creation evidence")
        value = self._read(path, "budget policy")
        if manifest != value:
            raise ExecutionBudgetStoreError(
                "Execution budget policy differs from immutable creation evidence"
            )
        policy = self._validate_policy(value, binding.budget_id)
        if policy.binding != binding:
            raise ExecutionBudgetStoreError(
                "Execution budget binding does not match immutable policy"
            )
        return policy

    def load_state(self, binding: BudgetBinding) -> dict[str, Any]:
        policy = self.load_policy(binding)
        path = self._state_path(binding.budget_id)
        if not path.is_file():
            raise ExecutionBudgetStoreError(
                "Execution budget usage state is missing; execution is denied"
            )
        value = self._read(path, "budget state")
        self._validate_state(value, policy)
        self._load_usage_anchor(policy, value)
        return deepcopy(value)

    def save_state(self, binding: BudgetBinding, state: dict[str, Any]) -> None:
        policy = self.load_policy(binding)
        path = self._state_path(binding.budget_id)
        if not path.is_file():
            raise ExecutionBudgetStoreError(
                "Execution budget usage state is missing; execution is denied"
            )
        current = self._read(path, "budget state")
        self._validate_state(current, policy)
        current_anchor, current_claim = self._load_usage_anchor(policy, current)
        candidate = deepcopy(state)
        self._validate_state(candidate, policy)
        if candidate == current:
            return
        self._validate_state_transition(current, candidate)
        if current["state_sequence"] >= MAX_STATE_SEQUENCE:
            raise ExecutionBudgetStoreError(
                "Execution budget state sequence is exhausted"
            )
        candidate["state_sequence"] = current["state_sequence"] + 1
        self._validate_state(candidate, policy)
        next_anchor = BudgetUsageAnchor.create(
            policy,
            candidate,
            previous_anchor_digest=current_anchor.digest,
        )
        next_claim = BudgetUsageClaim.create(
            policy,
            next_anchor,
            previous_claim_digest=current_claim.digest,
        )
        # Evidence is committed before the mutable head and state. Any interrupted
        # suffix is therefore detectable and fails closed instead of refunding use.
        if current_anchor.state_sequence == 0:
            self._write_once(
                self._usage_started_path(binding.budget_id), policy.to_dict()
            )
        self._write_once(
            self._usage_event_path(
                binding.budget_id, candidate["state_sequence"], next_anchor.digest
            ),
            next_anchor.to_dict(),
        )
        self._write_once(
            self._usage_claim_path(binding.budget_id, candidate["state_sequence"]),
            next_claim.to_dict(),
        )
        self._write(self._usage_head_path(binding.budget_id), next_anchor.to_dict())
        self._write(path, candidate)

    @contextmanager
    def transaction(self, *, timeout_seconds: float = 5.0):
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ExecutionBudgetStoreError(
                "Could not initialize the canonical budget lock"
            ) from error
        lock_path = self.root / ".budget.lock"
        deadline = time.monotonic() + timeout_seconds
        try:
            with lock_path.open("xb") as initializer:
                initializer.write(b"0")
                initializer.flush()
                os.fsync(initializer.fileno())
        except FileExistsError:
            pass
        except OSError as error:
            raise ExecutionBudgetStoreError(
                "Could not initialize the canonical budget lock"
            ) from error
        try:
            handle = lock_path.open("r+b")
        except OSError as error:
            raise ExecutionBudgetStoreError(
                "Could not open the canonical budget lock"
            ) from error
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
                    raise BudgetLockTimeout(
                        "Timed out waiting for the canonical budget lock"
                    ) from error
                time.sleep(0.01)
        try:
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
                raise ExecutionBudgetStoreError(
                    "Could not release the canonical budget lock"
                ) from error
            finally:
                handle.close()

    def _validate_policy(self, value: Any, budget_id: str) -> BudgetPolicy:
        try:
            self.policy_validator.validate(value)
            policy = BudgetPolicy.from_dict(value)
        except (JobValidationError, BudgetContractError, TypeError) as error:
            raise ExecutionBudgetStoreError(
                f"Invalid execution budget policy: {error}"
            ) from error
        if policy.budget_id != budget_id:
            raise ExecutionBudgetStoreError("Execution budget policy identity mismatch")
        return policy

    def _validate_state(self, value: Any, policy: BudgetPolicy) -> None:
        try:
            self.state_validator.validate(value)
        except (JobValidationError, TypeError) as error:
            raise ExecutionBudgetStoreError(
                f"Invalid execution budget state: {error}"
            ) from error
        if (
            value.get("budget_id") != policy.budget_id
            or value.get("logical_job_id") != policy.logical_job_id
            or value.get("policy_digest") != policy.digest
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget state is bound to a different immutable policy"
            )
        reservations = value.get("reservations", [])
        if value.get("consumed_execution_units") != len(reservations):
            raise ExecutionBudgetStoreError(
                "Execution budget unit counter does not match its reservations"
            )
        ids: set[str] = set()
        elapsed = 0
        last_observed = parse_timestamp(value.get("last_observed_at"), "last_observed_at")
        for reservation in reservations:
            execution_id = reservation["execution_id"]
            if execution_id in ids:
                raise ExecutionBudgetStoreError(
                    "Execution budget contains duplicate reservation identities"
                )
            ids.add(execution_id)
            elapsed += reservation["elapsed_ms"]
            reserved_at = parse_timestamp(reservation["reserved_at"], "reserved_at")
            last_accounted = parse_timestamp(
                reservation["last_accounted_at"], "last_accounted_at"
            )
            if last_accounted < reserved_at:
                raise ExecutionBudgetStoreError(
                    "Execution budget reservation time moved backwards"
                )
            if last_accounted > last_observed:
                raise ExecutionBudgetStoreError(
                    "Execution budget reservation exceeds its trusted observation time"
                )
            if reservation["state"] != "active":
                finalized = parse_timestamp(
                    reservation["finalized_at"], "finalized_at"
                )
                if finalized < reserved_at:
                    raise ExecutionBudgetStoreError(
                        "Execution budget finalization predates its reservation"
                    )
        if value.get("consumed_elapsed_ms") != elapsed:
            raise ExecutionBudgetStoreError(
                "Execution budget elapsed counter does not match its reservations"
            )
        if elapsed > 2**63 - 1:
            raise ExecutionBudgetStoreError("Execution budget elapsed counter overflow")

    def _validate_usage_anchor(
        self, value: Any, policy: BudgetPolicy
    ) -> BudgetUsageAnchor:
        try:
            self.usage_anchor_validator.validate(value)
            anchor = BudgetUsageAnchor.from_dict(value)
        except (JobValidationError, BudgetContractError, TypeError) as error:
            raise ExecutionBudgetStoreError(
                f"Invalid execution budget usage evidence: {error}"
            ) from error
        if (
            anchor.budget_id != policy.budget_id
            or anchor.logical_job_id != policy.logical_job_id
            or anchor.policy_digest != policy.digest
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget usage evidence is bound to another policy"
            )
        return anchor

    def _validate_usage_claim(
        self, value: Any, policy: BudgetPolicy
    ) -> BudgetUsageClaim:
        try:
            self.usage_claim_validator.validate(value)
            claim = BudgetUsageClaim.from_dict(value)
        except (JobValidationError, BudgetContractError, TypeError) as error:
            raise ExecutionBudgetStoreError(
                f"Invalid execution budget usage claim: {error}"
            ) from error
        if (
            claim.budget_id != policy.budget_id
            or claim.logical_job_id != policy.logical_job_id
            or claim.policy_digest != policy.digest
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget usage claim is bound to another policy"
            )
        return claim

    def _load_usage_anchor(
        self, policy: BudgetPolicy, state: dict[str, Any]
    ) -> tuple[BudgetUsageAnchor, BudgetUsageClaim]:
        head_path = self._usage_head_path(policy.budget_id)
        if not head_path.is_file():
            raise ExecutionBudgetStoreError(
                "Execution budget usage evidence is missing; execution is denied"
            )
        head_value = self._read(head_path, "budget usage high-water evidence")
        head = self._validate_usage_anchor(head_value, policy)
        anchor, claim = self._load_usage_ledger(policy)
        if anchor != head:
            raise ExecutionBudgetStoreError(
                "Execution budget high-water evidence differs from the canonical ledger"
            )
        if anchor.state_sequence != state.get("state_sequence"):
            raise ExecutionBudgetStoreError(
                "Execution budget state sequence does not match usage evidence"
            )
        if (
            anchor.consumed_execution_units
            != state.get("consumed_execution_units")
            or anchor.consumed_elapsed_ms != state.get("consumed_elapsed_ms")
            or anchor.reservation_count != len(state.get("reservations", []))
            or anchor.reservation_history_digest
            != reservation_history_digest(state.get("reservations", []))
            or anchor.state_digest != budget_state_digest(state)
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget state rolled back or diverged from usage evidence"
            )
        return anchor, claim

    def _load_usage_ledger(
        self, policy: BudgetPolicy
    ) -> tuple[BudgetUsageAnchor, BudgetUsageClaim]:
        claim_paths = self._ledger_inventory(
            self._usage_claims_dir(policy.budget_id), self._CLAIM_NAME, "claim"
        )
        event_paths = self._ledger_inventory(
            self._usage_events_dir(policy.budget_id), self._EVENT_NAME, "event"
        )
        if not claim_paths or set(claim_paths) != set(event_paths):
            raise ExecutionBudgetStoreError(
                "Execution budget usage ledger is incomplete or has a sequence gap"
            )
        sequences = sorted(claim_paths)
        if sequences != list(range(len(sequences))):
            raise ExecutionBudgetStoreError(
                "Execution budget usage ledger does not form one contiguous history"
            )

        previous_anchor: BudgetUsageAnchor | None = None
        previous_claim: BudgetUsageClaim | None = None
        current_anchor: BudgetUsageAnchor | None = None
        current_claim: BudgetUsageClaim | None = None
        for sequence in sequences:
            claim_path = claim_paths[sequence]
            event_candidates = event_paths[sequence]
            if not isinstance(event_candidates, list) or len(event_candidates) != 1:
                raise ExecutionBudgetStoreError(
                    "Execution budget usage ledger contains a branch or duplicate sequence"
                )
            event_path, filename_digest = event_candidates[0]
            claim = self._validate_usage_claim(
                self._read(claim_path, "budget usage claim"), policy
            )
            anchor = self._validate_usage_anchor(
                self._read(event_path, "budget usage event"), policy
            )
            if (
                claim.state_sequence != sequence
                or anchor.state_sequence != sequence
                or claim.event_digest != anchor.digest
                or filename_digest != anchor.digest
            ):
                raise ExecutionBudgetStoreError(
                    "Execution budget usage ledger identity does not match its content"
                )
            if sequence == 0:
                expected_state = self._initial_state(policy)
                expected_anchor = BudgetUsageAnchor.create(
                    policy, expected_state, previous_anchor_digest=None
                )
                expected_claim = BudgetUsageClaim.create(
                    policy, expected_anchor, previous_claim_digest=None
                )
                if anchor != expected_anchor or claim != expected_claim:
                    raise ExecutionBudgetStoreError(
                        "Execution budget usage ledger is not bound to canonical genesis"
                    )
            else:
                assert previous_anchor is not None and previous_claim is not None
                if (
                    anchor.previous_anchor_digest != previous_anchor.digest
                    or claim.previous_claim_digest != previous_claim.digest
                    or anchor.consumed_execution_units
                    < previous_anchor.consumed_execution_units
                    or anchor.consumed_elapsed_ms
                    < previous_anchor.consumed_elapsed_ms
                    or anchor.reservation_count < previous_anchor.reservation_count
                ):
                    raise ExecutionBudgetStoreError(
                        "Execution budget usage ledger chain is invalid or non-monotonic"
                    )
            previous_anchor = current_anchor = anchor
            previous_claim = current_claim = claim

        assert current_anchor is not None and current_claim is not None
        started_path = self._usage_started_path(policy.budget_id)
        if current_anchor.state_sequence == 0:
            if started_path.exists():
                raise ExecutionBudgetStoreError(
                    "Execution budget usage history was removed after initialization"
                )
        elif (
            not started_path.is_file()
            or self._read(started_path, "budget usage initialization evidence")
            != policy.to_dict()
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget usage initialization evidence is missing or invalid"
            )
        return current_anchor, current_claim

    def _ledger_inventory(
        self, directory: Path, pattern: re.Pattern[str], kind: str
    ) -> dict[int, Any]:
        if not directory.is_dir() or directory.is_symlink():
            raise ExecutionBudgetStoreError(
                "Execution budget usage ledger is missing; execution is denied"
            )
        inventory: dict[int, Any] = {}
        count = 0
        try:
            entries = directory.iterdir()
            for path in entries:
                count += 1
                if count > self._MAX_USAGE_EVENTS:
                    raise ExecutionBudgetStoreError(
                        "Execution budget usage ledger exceeds canonical bounds"
                    )
                match = pattern.fullmatch(path.name)
                if match is None or not path.is_file() or path.is_symlink():
                    raise ExecutionBudgetStoreError(
                        "Execution budget usage ledger contains an unexpected entry"
                    )
                sequence = int(match.group(1))
                if sequence >= self._MAX_USAGE_EVENTS:
                    raise ExecutionBudgetStoreError(
                        "Execution budget usage ledger sequence exceeds canonical bounds"
                    )
                if kind == "claim":
                    if sequence in inventory:
                        raise ExecutionBudgetStoreError(
                            "Execution budget usage ledger contains a duplicate claim"
                        )
                    inventory[sequence] = path
                else:
                    inventory.setdefault(sequence, []).append((path, match.group(2)))
        except OSError as error:
            raise ExecutionBudgetStoreError(
                "Could not enumerate canonical execution budget usage evidence"
            ) from error
        return inventory

    @staticmethod
    def _initial_state(policy: BudgetPolicy) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "budget_id": policy.budget_id,
            "logical_job_id": policy.logical_job_id,
            "policy_digest": policy.digest,
            "state_sequence": 0,
            "consumed_elapsed_ms": 0,
            "consumed_execution_units": 0,
            "last_observed_at": policy.created_at,
            "clock_rollback_detected": False,
            "reservations": [],
        }

    @staticmethod
    def _validate_state_transition(
        current: dict[str, Any], candidate: dict[str, Any]
    ) -> None:
        if candidate.get("state_sequence") != current.get("state_sequence"):
            raise ExecutionBudgetStoreError(
                "Execution budget state sequence is managed by the canonical store"
            )
        current_observed = parse_timestamp(
            current.get("last_observed_at"), "last_observed_at"
        )
        candidate_observed = parse_timestamp(
            candidate.get("last_observed_at"), "last_observed_at"
        )
        if candidate_observed < current_observed:
            raise ExecutionBudgetStoreError(
                "Execution budget observation time cannot decrease"
            )
        if current.get("clock_rollback_detected") and not candidate.get(
            "clock_rollback_detected"
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget clock fault cannot be cleared"
            )

        old_reservations = current["reservations"]
        new_reservations = candidate["reservations"]
        if len(new_reservations) == len(old_reservations) + 1:
            if new_reservations[:-1] != old_reservations:
                raise ExecutionBudgetStoreError(
                    "Execution budget reservation history cannot be rewritten"
                )
            added = new_reservations[-1]
            if (
                added["state"] != "active"
                or added["elapsed_ms"] != 0
                or added["reserved_at"] != candidate["last_observed_at"]
                or added["last_accounted_at"] != candidate["last_observed_at"]
                or candidate["consumed_execution_units"]
                != current["consumed_execution_units"] + 1
                or candidate["consumed_elapsed_ms"]
                != current["consumed_elapsed_ms"]
            ):
                raise ExecutionBudgetStoreError(
                    "Execution budget reservation advancement is invalid"
                )
            return

        if len(new_reservations) != len(old_reservations):
            raise ExecutionBudgetStoreError(
                "Execution budget reservation history cannot shrink or skip"
            )
        if (
            candidate["consumed_execution_units"]
            != current["consumed_execution_units"]
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget unit usage cannot change without a reservation"
            )
        changed = [
            index
            for index, (before, after) in enumerate(
                zip(old_reservations, new_reservations, strict=True)
            )
            if before != after
        ]
        if not changed:
            if candidate["consumed_elapsed_ms"] != current["consumed_elapsed_ms"]:
                raise ExecutionBudgetStoreError(
                    "Execution budget elapsed usage lacks reservation evidence"
                )
            return
        if len(changed) != 1:
            raise ExecutionBudgetStoreError(
                "Execution budget may finalize only one active reservation"
            )
        before = old_reservations[changed[0]]
        after = new_reservations[changed[0]]
        immutable_fields = ("execution_id", "job_id", "reserved_at")
        if any(before[field] != after[field] for field in immutable_fields):
            raise ExecutionBudgetStoreError(
                "Execution budget reservation identity cannot change"
            )
        if (
            before["state"] != "active"
            or after["state"] not in {"finalized", "reconciled"}
            or after["elapsed_ms"] < before["elapsed_ms"]
            or parse_timestamp(after["last_accounted_at"], "last_accounted_at")
            < parse_timestamp(before["last_accounted_at"], "last_accounted_at")
            or after["finalized_at"] != after["last_accounted_at"]
            or candidate["consumed_elapsed_ms"] - current["consumed_elapsed_ms"]
            != after["elapsed_ms"] - before["elapsed_ms"]
        ):
            raise ExecutionBudgetStoreError(
                "Execution budget finalization advancement is invalid"
            )

    def _policy_path(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / f"{budget_id}.policy.json"

    def _manifest_path(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / ".creation-evidence" / f"{budget_id}.policy-created.json"

    def _state_path(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / f"{budget_id}.state.json"

    def _usage_started_path(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / ".creation-evidence" / f"{budget_id}.usage-started.json"

    def _usage_head_path(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / ".usage-evidence" / f"{budget_id}.head.json"

    def _usage_events_dir(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / ".usage-evidence" / budget_id / "events"

    def _usage_claims_dir(self, budget_id: str) -> Path:
        self._validate_id(budget_id)
        return self.root / ".usage-evidence" / budget_id / "claims"

    def _usage_claim_path(self, budget_id: str, sequence: int) -> Path:
        self._validate_sequence(sequence)
        return self._usage_claims_dir(budget_id) / f"{sequence:020d}.json"

    def _usage_event_path(
        self, budget_id: str, sequence: int, event_digest: str
    ) -> Path:
        self._validate_id(budget_id)
        self._validate_sequence(sequence)
        if not isinstance(event_digest, str) or re.fullmatch(
            r"[a-f0-9]{64}", event_digest
        ) is None:
            raise ExecutionBudgetStoreError(
                "Budget usage event digest is outside canonical bounds"
            )
        return self._usage_events_dir(budget_id) / (
            f"{sequence:020d}-{event_digest}.json"
        )

    @staticmethod
    def _validate_sequence(sequence: int) -> None:
        if not isinstance(sequence, int) or isinstance(sequence, bool) or not (
            0 <= sequence <= MAX_STATE_SEQUENCE
        ):
            raise ExecutionBudgetStoreError(
                "Budget usage sequence is outside canonical bounds"
            )

    def _validate_id(self, budget_id: str) -> None:
        if not isinstance(budget_id, str) or self._SAFE_ID.fullmatch(budget_id) is None:
            raise ExecutionBudgetStoreError(
                "Budget ID contains unsupported path characters"
            )

    @staticmethod
    def _read(path: Path, label: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            raise ExecutionBudgetStoreError(f"Could not read {label}: {error}") from error

    def _write(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
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
                temporary_path = Path(handle.name)
                json.dump(
                    value,
                    handle,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                    allow_nan=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise ExecutionBudgetStoreError(
                f"Could not persist execution budget {path.stem}: invalid canonical data"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _write_once(path: Path, value: dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    value,
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
            raise ExecutionBudgetStoreError(
                "Execution budget usage evidence is write-once"
            ) from error
        except (OSError, OverflowError, TypeError, ValueError) as error:
            raise ExecutionBudgetStoreError(
                "Could not persist immutable execution budget usage evidence"
            ) from error
