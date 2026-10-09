"""Deterministic admission, reservation, accounting, and recovery for budgets."""

from __future__ import annotations

import math
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from runtime.budget.models import (
    BudgetBinding,
    BudgetContractError,
    BudgetDecision,
    BudgetPolicy,
    parse_timestamp,
)
from runtime.budget.store import BudgetLockTimeout, ExecutionBudgetStoreError, FileExecutionBudgetStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionBudgetRuntime:
    """Apply one immutable logical-job budget without granting execution authority."""

    def __init__(
        self,
        store: FileExecutionBudgetStore,
        *,
        wall_clock: Callable[[], str] = utc_now,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.store = store
        self.wall_clock = wall_clock
        self.monotonic_clock = monotonic_clock
        self._monotonic_starts: dict[tuple[str, str], float] = {}

    def reserve_execution(
        self,
        binding_value: Any,
        *,
        execution_id: str,
        job_id: str,
        job_runtime: Any | None = None,
        claim_identity: tuple[str, str, str] | None = None,
    ) -> BudgetDecision:
        try:
            binding = BudgetBinding.from_dict(binding_value)
            parallel = self._graph_parallel_context(job_runtime, binding, job_id)
            if parallel is not None and claim_identity is not None and parallel[2] != claim_identity:
                return BudgetDecision("DEFER", "claim changed before budget admission",
                                      {"measured_at": self.wall_clock(), "may_begin": False})
            with self.store.transaction(timeout_seconds=30.0 if parallel is not None else 5.0):
                # A recovery may release an unstarted claim while this caller
                # waits. Recheck its exact lease before reserving any capacity.
                if parallel is not None:
                    current = job_runtime.store.load(job_id)
                    current_claim = tuple(current.get(field) for field in
                                          ("claimed_by", "claimed_at", "lease_until"))
                    if current["status"] != "running" or current_claim != parallel[2]:
                        return BudgetDecision("DEFER", "claim changed while waiting for budget ownership",
                                              {"measured_at": self.wall_clock(), "may_begin": False})
                    # Authority was validated before locking. This fresh raw
                    # canonical record must still carry that exact live claim;
                    # repeating full work validation here serializes siblings.
                    job_runtime._require_active_claim(current, parallel[2][0])
                policy = self.store.load_policy(binding)
                state = self.store.load_state(binding)
                now = self.wall_clock()
                prior_clock_fault = state["clock_rollback_detected"]
                if self._observe_clock(state, now):
                    if not prior_clock_fault:
                        self.store.save_state(binding, state)
                    return BudgetDecision(
                        "ERROR",
                        "trusted wall clock moved backwards; budget is fail-closed",
                        self._snapshot(policy, state, now),
                    )
                existing = next(
                    (
                        item
                        for item in state["reservations"]
                        if item["execution_id"] == execution_id
                    ),
                    None,
                )
                if existing is not None:
                    if existing["job_id"] != job_id:
                        raise ExecutionBudgetStoreError(
                            "Execution reservation identity is bound to another job"
                        )
                    return BudgetDecision(
                        "ERROR",
                        "execution reservation identity has already been consumed",
                        self._snapshot(policy, state, now),
                        deepcopy(existing),
                    )
                live_usage = deepcopy(state)
                if parallel is not None:
                    live_usage["consumed_elapsed_ms"] += sum(
                        self._wall_elapsed_ms(item["last_accounted_at"], now)
                        for item in state["reservations"] if item["state"] == "active")
                exhausted = self._exhausted(policy, live_usage)
                if exhausted:
                    return BudgetDecision(
                        "DENY_EXHAUSTED",
                        "one or more configured budget dimensions are exhausted",
                        self._snapshot(policy, state, now),
                    )
                active = [item for item in state["reservations"] if item["state"] == "active"]
                if active and (parallel is None or len(active) >= parallel[0]
                        or any(item["job_id"] not in parallel[1] or item["job_id"] == job_id for item in active)):
                    return BudgetDecision(
                        "ERROR",
                        "an earlier execution reservation still requires recovery",
                        self._snapshot(policy, state, now),
                    )
                reservation = {
                    "execution_id": execution_id,
                    "job_id": job_id,
                    "reserved_at": now,
                    "last_accounted_at": now,
                    "elapsed_ms": 0,
                    "state": "active",
                }
                state["reservations"].append(reservation)
                state["consumed_execution_units"] += 1
                self.store.save_state(binding, state)
                self._monotonic_starts[(binding.budget_id, execution_id)] = (
                    self.monotonic_clock()
                )
                return BudgetDecision(
                    "ALLOW",
                    "execution capacity reserved",
                    self._snapshot(policy, state, now),
                    deepcopy(reservation),
                )
        except BudgetLockTimeout as error:
            return self._contention(error)
        except (BudgetContractError, ExecutionBudgetStoreError, ValueError) as error:
            return BudgetDecision(
                "ERROR",
                str(error),
                {"measured_at": self.wall_clock(), "may_begin": False},
            )

    def _graph_parallel_context(self, jobs, binding, job_id):
        """Allow simultaneous windows only for verified, actively claimed siblings.

        This is canonical budget accounting, not execution approval. Ordinary
        callers retain the serial recovery rule. Validation precedes the budget
        lock so graph/retry validation cannot invert owner lock order.
        """
        if jobs is None:
            return None
        from runtime.core.jobs import JobRuntime
        if type(jobs) is not JobRuntime or jobs.budget_store.root.resolve() != self.store.root.resolve():
            raise BudgetContractError("Graph budget requires the canonical job owner")
        job = jobs.show(job_id)
        if job.get("graph_binding") is None:
            raise BudgetContractError("Parallel budget request is not graph work")
        if job.get("execution_budget") != binding.to_dict():
            raise BudgetContractError("Graph budget differs from its task allocation")
        from runtime.graph.models import preflight_plan_scope
        with preflight_plan_scope(jobs.store.root, job["graph_binding"]["root_job_id"]):
            job = jobs.validate_execution_authority(job_id, job.get("claimed_by"))
            root = jobs.show(job["graph_binding"]["root_job_id"])
            permitted = set()
            for candidate in jobs.store.list():
                if (candidate.get("graph_binding", {}).get("root_job_id") == root["job_id"]
                        and candidate["status"] == "running"):
                    candidate = jobs.validate_claim(candidate["job_id"], candidate.get("claimed_by"))
                    if candidate.get("execution_budget") != binding.to_dict():
                        raise BudgetContractError("Graph sibling budget allocation differs")
                    permitted.add(candidate["job_id"])
            claim = tuple(job[field] for field in ("claimed_by", "claimed_at", "lease_until"))
            return root["graph_plan"]["max_parallel"], permitted, claim

    def finalize_execution(
        self,
        binding_value: Any,
        *,
        execution_id: str,
    ) -> BudgetDecision:
        try:
            binding = BudgetBinding.from_dict(binding_value)
            with self.store.transaction():
                policy = self.store.load_policy(binding)
                state = self.store.load_state(binding)
                now = self.wall_clock()
                rollback = self._observe_clock(state, now)
                reservation = next(
                    (
                        item
                        for item in state["reservations"]
                        if item["execution_id"] == execution_id
                    ),
                    None,
                )
                if reservation is None:
                    raise ExecutionBudgetStoreError(
                        "Execution finalization has no canonical reservation"
                    )
                if reservation["state"] == "active":
                    started = self._monotonic_starts.pop(
                        (binding.budget_id, execution_id), None
                    )
                    if started is None:
                        elapsed_ms = self._wall_elapsed_ms(
                            reservation["last_accounted_at"], now
                        )
                        final_state = "reconciled"
                    else:
                        elapsed_ms = max(
                            0,
                            math.ceil(
                                (self.monotonic_clock() - started) * 1000 - 1e-6
                            ),
                        )
                        final_state = "finalized"
                    reservation["elapsed_ms"] += elapsed_ms
                    reservation["last_accounted_at"] = (
                        now if not rollback else state["last_observed_at"]
                    )
                    reservation["state"] = final_state
                    reservation["finalized_at"] = (
                        now if not rollback else state["last_observed_at"]
                    )
                    state["consumed_elapsed_ms"] += elapsed_ms
                    self.store.save_state(binding, state)
                status = "ERROR" if state["clock_rollback_detected"] else "ALLOW"
                reason = (
                    "trusted wall clock moved backwards; future admission is fail-closed"
                    if status == "ERROR"
                    else "execution usage finalized"
                )
                return BudgetDecision(
                    status,
                    reason,
                    self._snapshot(policy, state, now),
                    deepcopy(reservation),
                )
        except BudgetLockTimeout as error:
            return self._contention(error)
        except (BudgetContractError, ExecutionBudgetStoreError, ValueError) as error:
            return BudgetDecision(
                "ERROR",
                str(error),
                {"measured_at": self.wall_clock(), "may_begin": False},
            )

    def recover(self, binding_value: Any) -> BudgetDecision:
        """Conservatively finalize possibly executed active reservations after restart."""
        try:
            binding = BudgetBinding.from_dict(binding_value)
            with self.store.transaction():
                policy = self.store.load_policy(binding)
                state = self.store.load_state(binding)
                now = self.wall_clock()
                prior_clock_fault = state["clock_rollback_detected"]
                rollback = self._observe_clock(state, now)
                reconciled = False
                for index in range(len(state["reservations"])):
                    reservation = state["reservations"][index]
                    if reservation["state"] != "active":
                        continue
                    elapsed_ms = self._wall_elapsed_ms(
                        reservation["last_accounted_at"], now
                    )
                    reservation["elapsed_ms"] += elapsed_ms
                    reservation["last_accounted_at"] = (
                        now if not rollback else state["last_observed_at"]
                    )
                    reservation["state"] = "reconciled"
                    reservation["finalized_at"] = (
                        now if not rollback else state["last_observed_at"]
                    )
                    state["consumed_elapsed_ms"] += elapsed_ms
                    # The canonical ledger accepts one reservation transition
                    # per event. Commit each recovery transition under this same
                    # lock, then reload its store-owned sequence before the next.
                    self.store.save_state(binding, state)
                    state = self.store.load_state(binding)
                    reconciled = True
                    self._monotonic_starts.pop(
                        (binding.budget_id, reservation["execution_id"]), None
                    )
                if not reconciled and rollback and not prior_clock_fault:
                    self.store.save_state(binding, state)
                status = "ERROR" if state["clock_rollback_detected"] else "ALLOW"
                reason = (
                    "trusted wall clock moved backwards; budget is fail-closed"
                    if status == "ERROR"
                    else "active reservations reconciled conservatively"
                )
                return BudgetDecision(status, reason, self._snapshot(policy, state, now))
        except BudgetLockTimeout as error:
            return self._contention(error)
        except (BudgetContractError, ExecutionBudgetStoreError, ValueError) as error:
            return BudgetDecision(
                "ERROR",
                str(error),
                {"measured_at": self.wall_clock(), "may_begin": False},
            )

    def state(self, binding_value: Any) -> BudgetDecision:
        try:
            binding = BudgetBinding.from_dict(binding_value)
            with self.store.transaction():
                policy = self.store.load_policy(binding)
                state = self.store.load_state(binding)
                now = self.wall_clock()
                prior_clock_fault = state["clock_rollback_detected"]
                rollback = self._observe_clock(state, now)
                if rollback and not prior_clock_fault:
                    self.store.save_state(binding, state)
                return BudgetDecision(
                    "ERROR" if state["clock_rollback_detected"] else "ALLOW",
                    "canonical budget state",
                    self._snapshot(policy, state, now),
                )
        except BudgetLockTimeout as error:
            return self._contention(error)
        except (BudgetContractError, ExecutionBudgetStoreError, ValueError) as error:
            return BudgetDecision(
                "ERROR",
                str(error),
                {"measured_at": self.wall_clock(), "may_begin": False},
            )

    def _contention(self, error):
        return BudgetDecision("DEFER", str(error),
                              {"measured_at": self.wall_clock(), "may_begin": False})

    @staticmethod
    def _observe_clock(state: dict[str, Any], now: str) -> bool:
        observed = parse_timestamp(state["last_observed_at"], "last_observed_at")
        current = parse_timestamp(now, "budget clock")
        if current < observed:
            state["clock_rollback_detected"] = True
            return True
        state["last_observed_at"] = now
        return bool(state["clock_rollback_detected"])

    @staticmethod
    def _wall_elapsed_ms(start: str, end: str) -> int:
        delta = parse_timestamp(end, "budget clock") - parse_timestamp(
            start, "last_accounted_at"
        )
        return max(0, math.ceil(delta.total_seconds() * 1000))

    @staticmethod
    def _exhausted(policy: BudgetPolicy, state: dict[str, Any]) -> list[str]:
        exhausted: list[str] = []
        if (
            policy.max_elapsed_ms is not None
            and state["consumed_elapsed_ms"] >= policy.max_elapsed_ms
        ):
            exhausted.append("elapsed_ms")
        if (
            policy.max_execution_units is not None
            and state["consumed_execution_units"] >= policy.max_execution_units
        ):
            exhausted.append("execution_units")
        return exhausted

    def _snapshot(
        self,
        policy: BudgetPolicy,
        state: dict[str, Any],
        measured_at: str,
    ) -> dict[str, Any]:
        dimensions: dict[str, Any] = {}
        for name, limit, consumed in (
            ("elapsed_ms", policy.max_elapsed_ms, state["consumed_elapsed_ms"]),
            (
                "execution_units",
                policy.max_execution_units,
                state["consumed_execution_units"],
            ),
        ):
            dimensions[name] = {
                "configured": limit is not None,
                "limit": limit,
                "consumed": consumed,
                "remaining": None if limit is None else max(limit - consumed, 0),
                "exhausted": limit is not None and consumed >= limit,
            }
        exhausted = [
            name for name, value in dimensions.items() if value["exhausted"]
        ]
        active = [
            item["execution_id"]
            for item in state["reservations"]
            if item["state"] == "active"
        ]
        return {
            "budget_id": policy.budget_id,
            "logical_job_id": policy.logical_job_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.digest,
            "measured_at": measured_at,
            "dimensions": dimensions,
            "exhausted_dimensions": exhausted,
            "active_reservation_ids": active,
            "clock_rollback_detected": state["clock_rollback_detected"],
            "may_begin": not exhausted
            and not active
            and not state["clock_rollback_detected"],
        }
