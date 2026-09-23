"""Bounded local-first autonomous scheduler loop."""

from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable
from uuid import uuid4

from runtime.approvals.runtime import ApprovalRuntime, ApprovalRuntimeError
from runtime.core.jobs import JobRuntime, RuntimeError, utc_now
from runtime.scheduler.dispatch import CanonicalDispatchAdapter
from runtime.scheduler.schedules import ScheduleRuntime, ScheduleRuntimeError
from runtime.storage.scheduler_state_store import (
    FileSchedulerStateStore,
    SchedulerStateStoreError,
)
from runtime.workers.worker import Worker, WorkerRunOutcome


class SchedulerLoopError(ValueError):
    """Raised when autonomous scheduling cannot proceed safely."""


@dataclass(frozen=True)
class SchedulerConfig:
    poll_interval_seconds: float = 5.0
    max_jobs_per_cycle: int = 1
    max_concurrent_jobs: int = 1
    max_provider_runs_per_cycle: int = 1
    max_provider_runs_per_day: int = 25
    lease_seconds: int = 300
    heartbeat_interval_seconds: float = 60.0
    retry_backoff_seconds: tuple[int, ...] = (30, 300, 1800)

    def __post_init__(self) -> None:
        if not 0.01 <= self.poll_interval_seconds <= 300:
            raise SchedulerLoopError("Poll interval must be between 0.01 and 300 seconds")
        if not 1 <= self.max_jobs_per_cycle <= 100:
            raise SchedulerLoopError("max_jobs_per_cycle must be between 1 and 100")
        if self.max_concurrent_jobs != 1:
            raise SchedulerLoopError("Phase 6M supports exactly one concurrent job")
        if not 0 <= self.max_provider_runs_per_cycle <= self.max_jobs_per_cycle:
            raise SchedulerLoopError("Provider runs per cycle exceed the cycle boundary")
        if not 0 <= self.max_provider_runs_per_day <= 10000:
            raise SchedulerLoopError("Provider runs per day are outside the bounded range")
        if not 5 <= self.lease_seconds <= 3600:
            raise SchedulerLoopError("Lease duration must be between 5 and 3600 seconds")
        if not 0.01 <= self.heartbeat_interval_seconds < self.lease_seconds:
            raise SchedulerLoopError("Heartbeat interval must be positive and shorter than the lease")
        if (
            not self.retry_backoff_seconds
            or len(self.retry_backoff_seconds) > 10
            or any(not isinstance(value, int) or not 1 <= value <= 86400 for value in self.retry_backoff_seconds)
        ):
            raise SchedulerLoopError("Retry backoff policy is invalid")


class SchedulerLoop:
    """Emit due occurrences, claim eligible jobs, and delegate each to Worker."""

    def __init__(
        self,
        schedules: ScheduleRuntime,
        dispatcher: CanonicalDispatchAdapter,
        jobs: JobRuntime,
        worker: Worker,
        approvals: ApprovalRuntime,
        state_store: FileSchedulerStateStore,
        *,
        config: SchedulerConfig | None = None,
        counts_as_provider_run: bool = False,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.schedules = schedules
        self.dispatcher = dispatcher
        self.jobs = jobs
        self.worker = worker
        self.approvals = approvals
        self.state_store = state_store
        self.config = config or SchedulerConfig()
        self.counts_as_provider_run = counts_as_provider_run
        self.clock = clock
        self.id_factory = id_factory or (lambda: uuid4().hex)
        self.scheduler_id = f"scheduler-{self.id_factory()}"
        self._stop = threading.Event()

    def inspect(self) -> dict[str, Any]:
        now_text = self.clock()
        jobs = self.jobs.list()
        queued = [job for job in jobs if job["status"] == "queued"]
        eligible_ids = {job["job_id"] for job in self.jobs.eligible(now=now_text)}
        future = [job for job in queued if job["job_id"] not in eligible_ids]
        waiting = [job for job in jobs if job["status"] == "waiting_approval"]
        retry_queue = [job for job in jobs if job.get("schedule_reason") == "retry_backoff"]
        expired = [
            job
            for job in jobs
            if job["status"] == "running"
            and self.jobs._parse_timestamp(job["lease_until"], "lease_until")
            <= self.jobs._parse_timestamp(now_text, "scheduler clock")
        ]
        due_schedules = self.schedules.due(now=now_text)
        candidates = [
            str(item["next_run_at"])
            for item in [*future, *self.schedules.list()]
            if item.get("next_run_at")
        ]
        state = self.state_store.load()
        return {
            "checked_at": now_text,
            "scheduler": state,
            "running": bool(state and state.get("status") == "running"),
            "current_worker": state.get("worker_id") if state else None,
            "active_job": state.get("active_job_id") if state else None,
            "eligible_jobs": sorted(eligible_ids),
            "future_jobs": [job["job_id"] for job in future],
            "due_schedules": [schedule["schedule_id"] for schedule in due_schedules],
            "waiting_approvals": [job["job_id"] for job in waiting],
            "retry_queue": [job["job_id"] for job in retry_queue],
            "expired_claims": [job["job_id"] for job in expired],
            "next_due_at": min(candidates) if candidates else None,
        }

    def run_once(self, *, dry_run: bool = False) -> dict[str, Any]:
        if dry_run:
            return {"status": "dry_run", **self.inspect(), "outcomes": []}
        self._start()
        try:
            result = self._cycle()
        finally:
            self._finish("run_once_complete")
        return result

    def run(
        self, *, max_cycles: int | None = None, dry_run: bool = False
    ) -> dict[str, Any]:
        if max_cycles is not None and max_cycles < 1:
            raise SchedulerLoopError("max_cycles must be positive")
        if dry_run:
            cycles: list[dict[str, Any]] = []
            reason = "stop_requested"
            try:
                while not self._stop.is_set():
                    cycles.append(
                        {"status": "dry_run", **self.inspect(), "outcomes": []}
                    )
                    if max_cycles is not None and len(cycles) >= max_cycles:
                        reason = "max_cycles_reached"
                        break
                    self._stop.wait(self.config.poll_interval_seconds)
            except KeyboardInterrupt:
                reason = "interrupted"
                self._stop.set()
            return {
                "status": "stopped",
                "reason": reason,
                "dry_run": True,
                "cycles": cycles,
            }
        self._start()
        cycles: list[dict[str, Any]] = []
        reason = "stop_requested"
        try:
            while not self._stop.is_set():
                persisted = self.state_store.load() or {}
                if persisted.get("stop_requested"):
                    break
                cycles.append(self._cycle())
                if max_cycles is not None and len(cycles) >= max_cycles:
                    reason = "max_cycles_reached"
                    break
                self._stop.wait(self.config.poll_interval_seconds)
        except KeyboardInterrupt:
            reason = "interrupted"
            self._stop.set()
        finally:
            self._finish(reason)
        return {"status": "stopped", "reason": reason, "cycles": cycles}

    def stop(self) -> None:
        self._stop.set()
        self.state_store.request_stop(self.clock())

    def _cycle(self) -> dict[str, Any]:
        checked_at = self.clock()
        outcomes: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        try:
            schedule_result = self.schedules.tick(
                self.dispatcher,
                coalesce_missed=True,
            )
        except Exception:
            schedule_result = {
                "status": "failure",
                "errors": [{"code": "schedule_tick_error", "message": "Schedule tick failed"}],
            }
            errors.extend(schedule_result["errors"])
        recovered = self._recover_expired(errors)
        recovered_retries = self._recover_failed_retries(errors)
        provider_runs = 0
        processed = 0
        while processed < self.config.max_jobs_per_cycle and not self._stop.is_set():
            if self.counts_as_provider_run and (
                provider_runs >= self.config.max_provider_runs_per_cycle
                or not self._provider_daily_available()
            ):
                self._audit("provider_guard_blocked")
                break
            try:
                claimed = self.jobs.claim(
                    claimed_by=self.worker.worker_id,
                    lease_seconds=self.config.lease_seconds,
                )
            except RuntimeError as error:
                errors.append({"code": "claim_error", "message": str(error)})
                break
            if claimed is None:
                break
            processed += 1
            if self.counts_as_provider_run:
                provider_runs += 1
                self._record_provider_run()
            self._set_active_job(claimed["job_id"])
            self._audit("job_claimed", job_id=claimed["job_id"])
            self._audit("job_started", job_id=claimed["job_id"])
            outcome = self._run_with_heartbeat(claimed["job_id"])
            outcomes.append(outcome.to_dict())
            self._set_active_job(None)
            self._audit_outcome(outcome)
            try:
                self._schedule_retry(outcome)
            except (RuntimeError, ApprovalRuntimeError) as error:
                errors.append({"code": "retry_error", "message": str(error)})
        state = self.state_store.load() or self._new_state()
        state["cycle_count"] = int(state.get("cycle_count", 0)) + 1
        state["last_cycle_at"] = checked_at
        state["last_updated_at"] = self.clock()
        state["last_error"] = errors[-1] if errors else None
        self.state_store.save(state)
        return {
            "status": "ok" if not errors else "partial_failure",
            "checked_at": checked_at,
            "schedule_result": schedule_result,
            "recovered_claims": recovered,
            "recovered_retries": recovered_retries,
            "processed_count": processed,
            "provider_runs": provider_runs,
            "outcomes": outcomes,
            "errors": errors,
        }

    def _recover_expired(self, errors: list[dict[str, str]]) -> list[dict[str, Any]]:
        try:
            recovered = self.jobs.recover_expired_claims(
                backoff_seconds=self.config.retry_backoff_seconds
            )
        except RuntimeError as error:
            errors.append({"code": "claim_recovery_error", "message": str(error)})
            return []
        for item in recovered:
            failed = item["failed_job"]
            self._audit("claim_expired", job_id=failed["job_id"])
            retry_job = item.get("retry_job")
            if retry_job is not None:
                retry_job = self._ensure_retry_approval(retry_job)
                item["retry_job"] = retry_job
                self._audit("job_retried", job_id=retry_job["job_id"])
        return recovered

    def _recover_failed_retries(
        self, errors: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        try:
            jobs = self.jobs.list()
            retry_sources = {
                job["parent_job_id"]
                for job in jobs
                if job.get("parent_job_id") is not None
            }
            for failed in jobs:
                if (
                    failed["status"] != "failed"
                    or failed["job_id"] in retry_sources
                    or failed.get("error", {}).get("retryable") is not True
                    or failed["attempt"] >= failed["max_attempts"]
                ):
                    continue
                delay = self._backoff(failed["attempt"])
                run_at = self.jobs._format_timestamp(
                    self.jobs._parse_timestamp(self.clock(), "scheduler clock")
                    + timedelta(seconds=delay)
                )
                retry_job = self.jobs.retry(
                    failed["job_id"], next_run_at=run_at, enqueue=True
                )
                retry_job = self._ensure_retry_approval(retry_job)
                recovered.append(retry_job)
                self._audit("job_retry_recovered", job_id=retry_job["job_id"])
        except (RuntimeError, ApprovalRuntimeError, SchedulerLoopError) as error:
            errors.append({"code": "retry_recovery_error", "message": str(error)})
        return recovered

    def _schedule_retry(self, outcome: WorkerRunOutcome) -> None:
        if outcome.job_id is None:
            return
        original = self.jobs.show(outcome.job_id)
        retry_job = self.jobs.show(outcome.retry_job_id) if outcome.retry_job_id else None
        if retry_job is None and original["status"] == "failed":
            error = original.get("error", {})
            if error.get("retryable") is not True or original["attempt"] >= original["max_attempts"]:
                return
            delay = self._backoff(original["attempt"])
            run_at = self.jobs._format_timestamp(
                self.jobs._parse_timestamp(self.clock(), "scheduler clock")
                + timedelta(seconds=delay)
            )
            retry_job = self.jobs.retry(
                original["job_id"], next_run_at=run_at, enqueue=True
            )
        elif retry_job is not None and retry_job["status"] == "queued":
            delay = self._backoff(original["attempt"])
            run_at = self.jobs._format_timestamp(
                self.jobs._parse_timestamp(self.clock(), "scheduler clock")
                + timedelta(seconds=delay)
            )
            retry_job = self.jobs.reschedule(retry_job["job_id"], run_at)
        if retry_job is not None:
            retry_job = self._ensure_retry_approval(retry_job)
            self._audit("job_retried", job_id=retry_job["job_id"])

    def _ensure_retry_approval(self, retry_job: dict[str, Any]) -> dict[str, Any]:
        if retry_job["approval_status"] == "not_required":
            return retry_job
        if retry_job["status"] in {"created", "waiting_approval"}:
            run = self.approvals.request_execution(
                retry_job["job_id"],
                reason="Autonomous retry requires fresh execution approval",
            )
            if run.job is None:
                raise SchedulerLoopError("Retry approval did not return canonical job state")
            return run.job
        return retry_job

    def _run_with_heartbeat(self, job_id: str) -> WorkerRunOutcome:
        finished = threading.Event()

        def maintain() -> None:
            while not finished.wait(self.config.heartbeat_interval_seconds):
                try:
                    self.worker.heartbeat(job_id)
                    self._audit("job_heartbeat", job_id=job_id)
                except RuntimeError:
                    return

        heartbeat = threading.Thread(target=maintain, daemon=True)
        heartbeat.start()
        try:
            return self.worker.run_claimed(job_id)
        except Exception:
            return WorkerRunOutcome(
                status="worker_error",
                job_id=job_id,
                error={
                    "code": "scheduler_worker_error",
                    "message": "Worker raised an unexpected exception",
                },
            )
        finally:
            finished.set()
            heartbeat.join(timeout=self.config.heartbeat_interval_seconds + 0.1)

    def _provider_daily_available(self) -> bool:
        state = self.state_store.load() or self._new_state()
        today = self.clock()[:10]
        count = state.get("provider_runs_today", 0) if state.get("provider_runs_date") == today else 0
        return count < self.config.max_provider_runs_per_day

    def _record_provider_run(self) -> None:
        state = self.state_store.load() or self._new_state()
        today = self.clock()[:10]
        if state.get("provider_runs_date") != today:
            state["provider_runs_date"] = today
            state["provider_runs_today"] = 0
        state["provider_runs_today"] = int(state.get("provider_runs_today", 0)) + 1
        state["last_updated_at"] = self.clock()
        self.state_store.save(state)

    def _backoff(self, failed_attempt: int) -> int:
        return self.config.retry_backoff_seconds[
            min(failed_attempt - 1, len(self.config.retry_backoff_seconds) - 1)
        ]

    def _start(self) -> None:
        try:
            self.state_store.acquire_run_lock()
        except SchedulerStateStoreError as error:
            raise SchedulerLoopError(str(error)) from error
        try:
            prior = self.state_store.load()
            now = self.clock()
            state = self._new_state()
            state.update(
                {
                    "status": "running",
                    "started_at": now,
                    "last_updated_at": now,
                    "stop_requested": False,
                    "provider_runs_date": (
                        prior.get("provider_runs_date") if prior else now[:10]
                    ),
                    "provider_runs_today": (
                        int(prior.get("provider_runs_today", 0)) if prior else 0
                    ),
                    "cycle_count": int(prior.get("cycle_count", 0)) if prior else 0,
                    "last_cycle_at": prior.get("last_cycle_at") if prior else None,
                }
            )
            self.state_store.save(state)
            self._audit("scheduler_started")
            if prior and prior.get("status") in {"running", "stopping"}:
                self._audit("scheduler_restart_recovered")
        except Exception:
            self.state_store.release_run_lock()
            raise

    def _finish(self, reason: str) -> None:
        try:
            state = self.state_store.load() or self._new_state()
            now = self.clock()
            state.update(
                {
                    "status": "stopped",
                    "active_job_id": None,
                    "stopped_at": now,
                    "last_updated_at": now,
                    "stop_requested": False,
                    "stop_reason": reason,
                }
            )
            self.state_store.save(state)
            self._audit("scheduler_stopped", detail={"reason": reason})
        finally:
            try:
                self.state_store.release_run_lock()
            except SchedulerStateStoreError as error:
                raise SchedulerLoopError(str(error)) from error

    def _new_state(self) -> dict[str, Any]:
        now = self.clock()
        return {
            "schema_version": 1,
            "scheduler_id": self.scheduler_id,
            "status": "stopped",
            "started_at": None,
            "stopped_at": None,
            "last_cycle_at": None,
            "last_updated_at": now,
            "worker_id": self.worker.worker_id,
            "active_job_id": None,
            "cycle_count": 0,
            "provider_runs_date": now[:10],
            "provider_runs_today": 0,
            "stop_requested": False,
            "stop_reason": None,
            "last_error": None,
        }

    def _set_active_job(self, job_id: str | None) -> None:
        state = self.state_store.load() or self._new_state()
        state["active_job_id"] = job_id
        state["last_updated_at"] = self.clock()
        self.state_store.save(state)

    def _audit_outcome(self, outcome: WorkerRunOutcome) -> None:
        if outcome.job_id is None:
            return
        event = {
            "completed": "job_completed",
            "failed": "job_failed",
            "waiting_approval": "job_blocked",
            "worker_error": "job_failed",
        }.get(outcome.status, "job_finished")
        self._audit(event, job_id=outcome.job_id, detail={"status": outcome.status})

    def _audit(
        self,
        event_type: str,
        *,
        job_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        event_number = len(self.state_store.list_events()) + 1
        event_id = f"event-{event_number:06d}-{self.id_factory()}"
        event = {
            "schema_version": 1,
            "event_id": event_id,
            "event_type": event_type,
            "recorded_at": self.clock(),
            "scheduler_id": self.scheduler_id,
            "job_id": job_id,
            "detail": deepcopy(detail) if detail else None,
        }
        try:
            self.state_store.append_event(event)
        except SchedulerStateStoreError as error:
            raise SchedulerLoopError(str(error)) from error
