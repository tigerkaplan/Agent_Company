"""Canonical schedule operations and deterministic manual tick behavior."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from runtime.core.jobs import utc_now
from runtime.core.validation import JobValidationError, JobValidator
from runtime.scheduler.dispatch import DispatchError
from runtime.storage.schedule_store import FileScheduleStore, ScheduleStoreError


class ScheduleRuntimeError(ValueError):
    """Raised when a schedule operation cannot be completed safely."""


class Dispatcher(Protocol):
    def dispatch(
        self,
        schedule: dict[str, Any],
        occurrence_key: str,
    ) -> dict[str, Any]:
        """Create or recover one canonical job for a scheduled occurrence."""


def new_schedule_id() -> str:
    return f"schedule-{uuid4().hex}"


def default_schedule_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "schedule.schema.json"


class ScheduleRuntime:
    """Persist schedules and fire due occurrences exactly once in local state."""

    _MANAGED_FIELDS = {
        "schema_version",
        "schedule_id",
        "created_at",
        "last_updated_at",
        "last_run_at",
        "last_occurrence_key",
        "last_error",
    }
    _FORBIDDEN_METADATA_KEY_PARTS = (
        "apikey",
        "credential",
        "password",
        "privatekey",
        "secret",
        "token",
    )
    _RESERVED_METADATA_KEYS = {
        "agent",
        "approvalstatus",
        "capability",
        "knowledgebase",
        "projectstate",
        "provider",
        "reviewrequired",
        "risklevel",
        "skill",
        "workflow",
    }
    _RECURRENCE_DELTAS = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
    }

    def __init__(
        self,
        state_root: Path,
        *,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] = new_schedule_id,
        validator: JobValidator | None = None,
    ) -> None:
        self.store = FileScheduleStore(state_root)
        self.clock = clock
        self.id_factory = id_factory
        self.validator = validator or JobValidator(default_schedule_schema_path())

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ScheduleRuntimeError("Schedule creation input must be a JSON object")
        managed = sorted(set(payload) & self._MANAGED_FIELDS)
        if managed:
            raise ScheduleRuntimeError(
                f"Schedule input contains runtime-managed fields: {', '.join(managed)}"
            )
        schedule = deepcopy(payload)
        schedule.setdefault("enabled", True)
        schedule.setdefault("input_refs", [])
        schedule.setdefault("metadata", {})
        timestamp = self.clock()
        schedule.update(
            {
                "schema_version": 1,
                "schedule_id": self._unused_schedule_id(),
                "created_at": timestamp,
                "last_updated_at": timestamp,
            }
        )
        self._validate(schedule)
        try:
            self.store.create(schedule)
        except ScheduleStoreError as error:
            raise ScheduleRuntimeError(str(error)) from error
        return deepcopy(schedule)

    def list(self) -> list[dict[str, Any]]:
        try:
            schedules = self.store.list()
        except ScheduleStoreError as error:
            raise ScheduleRuntimeError(str(error)) from error
        for schedule in schedules:
            self._validate(schedule)
        return schedules

    def show(self, schedule_id: str) -> dict[str, Any]:
        return deepcopy(self._load(schedule_id))

    def enable(self, schedule_id: str) -> dict[str, Any]:
        schedule = self._load(schedule_id)
        if schedule["schedule_type"] == "one_time" and "last_occurrence_key" in schedule:
            raise ScheduleRuntimeError("Completed one-time schedule cannot be re-enabled")
        updated = deepcopy(schedule)
        updated["enabled"] = True
        updated["last_updated_at"] = self.clock()
        return self._save(updated)

    def disable(self, schedule_id: str) -> dict[str, Any]:
        schedule = self._load(schedule_id)
        updated = deepcopy(schedule)
        updated["enabled"] = False
        updated["last_updated_at"] = self.clock()
        return self._save(updated)

    def due(self, *, now: str | None = None) -> list[dict[str, Any]]:
        now_value = self._parse_datetime(now or self.clock(), "scheduler clock")
        return sorted(
            (
                schedule
                for schedule in self.list()
                if schedule["enabled"]
                and self._parse_datetime(schedule["next_run_at"], "next_run_at")
                <= now_value
            ),
            key=lambda schedule: (schedule["next_run_at"], schedule["schedule_id"]),
        )

    def tick(
        self,
        dispatcher: Dispatcher,
        *,
        coalesce_missed: bool = False,
    ) -> dict[str, Any]:
        now_text = self.clock()
        now = self._parse_datetime(now_text, "scheduler clock")
        due = self.due(now=now_text)
        fired: list[dict[str, str]] = []
        errors: list[dict[str, str]] = []
        for schedule in due:
            occurrence_key = self._occurrence_key(schedule)
            if schedule.get("last_occurrence_key") == occurrence_key:
                self._mark_fired(
                    schedule,
                    occurrence_key,
                    now_text,
                    coalesce_missed=coalesce_missed,
                )
                continue
            try:
                job = dispatcher.dispatch(schedule, occurrence_key)
                self._mark_fired(
                    schedule,
                    occurrence_key,
                    now_text,
                    coalesce_missed=coalesce_missed,
                )
                fired.append(
                    {
                        "schedule_id": schedule["schedule_id"],
                        "occurrence_key": occurrence_key,
                        "job_id": job["job_id"],
                    }
                )
            except (DispatchError, ScheduleRuntimeError) as error:
                self._record_error(schedule, "dispatch_error", str(error), now_text)
                errors.append(
                    {
                        "schedule_id": schedule["schedule_id"],
                        "occurrence_key": occurrence_key,
                        "code": "dispatch_error",
                        "message": str(error),
                    }
                )
            except Exception:
                message = "Unexpected scheduler dispatch failure; details were not persisted"
                self._record_error(schedule, "unexpected_dispatch_error", message, now_text)
                errors.append(
                    {
                        "schedule_id": schedule["schedule_id"],
                        "occurrence_key": occurrence_key,
                        "code": "unexpected_dispatch_error",
                        "message": message,
                    }
                )
        return {
            "status": "ok" if not errors else "partial_failure",
            "checked_at": now_text,
            "due_count": len(due),
            "fired": fired,
            "errors": errors,
        }

    def _mark_fired(
        self,
        schedule: dict[str, Any],
        occurrence_key: str,
        now_text: str,
        *,
        coalesce_missed: bool = False,
    ) -> dict[str, Any]:
        updated = deepcopy(schedule)
        updated["last_run_at"] = now_text
        updated["last_occurrence_key"] = occurrence_key
        updated["last_updated_at"] = now_text
        updated.pop("last_error", None)
        if updated["schedule_type"] == "one_time":
            updated["enabled"] = False
        else:
            occurrence = self._parse_datetime(updated["next_run_at"], "next_run_at")
            next_occurrence = occurrence + self._RECURRENCE_DELTAS[updated["recurrence"]]
            if coalesce_missed:
                now = self._parse_datetime(now_text, "scheduler clock")
                while next_occurrence <= now:
                    next_occurrence += self._RECURRENCE_DELTAS[updated["recurrence"]]
            updated["next_run_at"] = self._format_datetime(next_occurrence)
        return self._save(updated)

    def _record_error(
        self,
        schedule: dict[str, Any],
        code: str,
        message: str,
        now_text: str,
    ) -> dict[str, Any]:
        updated = deepcopy(schedule)
        updated["last_updated_at"] = now_text
        updated["last_error"] = {
            "code": code,
            "message": message,
            "recorded_at": now_text,
        }
        return self._save(updated)

    def _load(self, schedule_id: str) -> dict[str, Any]:
        try:
            schedule = self.store.load(schedule_id)
        except ScheduleStoreError as error:
            raise ScheduleRuntimeError(str(error)) from error
        self._validate(schedule)
        return schedule

    def _save(self, schedule: dict[str, Any]) -> dict[str, Any]:
        self._validate(schedule)
        try:
            self.store.save(schedule)
        except ScheduleStoreError as error:
            raise ScheduleRuntimeError(str(error)) from error
        return deepcopy(schedule)

    def _validate(self, schedule: dict[str, Any]) -> None:
        try:
            self.validator.validate(schedule)
        except JobValidationError as error:
            raise ScheduleRuntimeError(f"Invalid canonical schedule: {error}") from error
        self._parse_datetime(schedule["next_run_at"], "next_run_at")
        if self._contains_forbidden_metadata(schedule.get("metadata", {})):
            raise ScheduleRuntimeError(
                "Schedule metadata contains a forbidden secret, routing, approval, or state field"
            )

    def _unused_schedule_id(self) -> str:
        for _ in range(10):
            candidate = self.id_factory()
            if not self.store.exists(candidate):
                return candidate
        raise ScheduleRuntimeError("Could not generate a unique schedule ID")

    @staticmethod
    def _occurrence_key(schedule: dict[str, Any]) -> str:
        return f"{schedule['schedule_id']}@{schedule['next_run_at']}"

    @staticmethod
    def _parse_datetime(value: str, label: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise ScheduleRuntimeError(f"{label} must be an ISO 8601 date-time") from error
        if parsed.tzinfo is None:
            raise ScheduleRuntimeError(f"{label} must include an explicit timezone")
        return parsed

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @classmethod
    def _contains_forbidden_metadata(cls, value: Any) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                normalised = "".join(
                    character
                    for character in str(key).lower()
                    if character.isalnum()
                )
                if (
                    normalised in cls._RESERVED_METADATA_KEYS
                    or any(
                        part in normalised
                        for part in cls._FORBIDDEN_METADATA_KEY_PARTS
                    )
                ):
                    return True
                if cls._contains_forbidden_metadata(item):
                    return True
        elif isinstance(value, list):
            return any(cls._contains_forbidden_metadata(item) for item in value)
        return False
