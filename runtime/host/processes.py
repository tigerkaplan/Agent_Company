"""Supervisor-neutral host process lifecycle for Phase 8C."""

from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from runtime.core.jobs import utc_now
from runtime.host.config import HostConfig
from runtime.host.paths import StatePaths
from runtime.host.service import HostReadinessService


class HostProcessError(ValueError):
    """Raised when a host process cannot start or persist lifecycle state."""


class ProcessType(str, Enum):
    SCHEDULER = "scheduler"
    TELEGRAM = "telegram"
    WEBHOOK_LOCAL = "webhook-local"


class ProcessState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


_ACTIVE_STATES = {ProcessState.STARTING, ProcessState.RUNNING, ProcessState.STOPPING}
_MAX_ERROR_LENGTH = 512
_MAX_EXIT_REASON_LENGTH = 128
_MAX_RESTART_COUNT = 1_000_000


def _bounded(value: object | None, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class HostProcess:
    process_id: str
    process_type: ProcessType
    enabled: bool
    pid: int | None = None
    started_at: str | None = None
    last_heartbeat: str | None = None
    state: ProcessState = ProcessState.STOPPED
    restart_count: int = 0
    last_exit_code: int | None = None
    last_error: str | None = None
    last_failure_at: str | None = None
    last_exit_reason: str | None = None
    owner_token: str | None = None
    owner_started_at: str | None = None
    stop_requested: bool = False
    schema_version: int = 1

    @classmethod
    def empty(cls, process_type: ProcessType, *, enabled: bool) -> "HostProcess":
        return cls(
            process_id=process_type.value,
            process_type=process_type,
            enabled=enabled,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HostProcess":
        try:
            process_type = ProcessType(value["process_type"])
            state = ProcessState(value["state"])
        except (KeyError, TypeError, ValueError) as error:
            raise HostProcessError("Host process state is invalid") from error
        if value.get("schema_version") != 1 or value.get("process_id") != process_type.value:
            raise HostProcessError("Host process state identity is invalid")
        enabled = value.get("enabled")
        restart_count = value.get("restart_count")
        pid = value.get("pid")
        exit_code = value.get("last_exit_code")
        if not isinstance(enabled, bool):
            raise HostProcessError("Host process enabled state is invalid")
        if (
            isinstance(restart_count, bool)
            or not isinstance(restart_count, int)
            or not 0 <= restart_count <= _MAX_RESTART_COUNT
        ):
            raise HostProcessError("Host process restart count is invalid")
        if pid is not None and (isinstance(pid, bool) or not isinstance(pid, int) or pid < 1):
            raise HostProcessError("Host process PID is invalid")
        if exit_code is not None and (
            isinstance(exit_code, bool) or not isinstance(exit_code, int)
        ):
            raise HostProcessError("Host process exit code is invalid")
        for field in (
            "started_at",
            "last_heartbeat",
            "last_error",
            "last_failure_at",
            "last_exit_reason",
            "owner_token",
            "owner_started_at",
        ):
            if value.get(field) is not None and not isinstance(value[field], str):
                raise HostProcessError(f"Host process {field} is invalid")
        stop_requested = value.get("stop_requested", False)
        if not isinstance(stop_requested, bool):
            raise HostProcessError("Host process stop request is invalid")
        return cls(
            process_id=process_type.value,
            process_type=process_type,
            enabled=enabled,
            pid=pid,
            started_at=value.get("started_at"),
            last_heartbeat=value.get("last_heartbeat"),
            state=state,
            restart_count=restart_count,
            last_exit_code=exit_code,
            last_error=_bounded(value.get("last_error"), _MAX_ERROR_LENGTH),
            last_failure_at=value.get("last_failure_at"),
            last_exit_reason=_bounded(
                value.get("last_exit_reason"), _MAX_EXIT_REASON_LENGTH
            ),
            owner_token=value.get("owner_token"),
            owner_started_at=value.get("owner_started_at"),
            stop_requested=stop_requested,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "process_id": self.process_id,
            "process_type": self.process_type.value,
            "enabled": self.enabled,
            "pid": self.pid,
            "started_at": self.started_at,
            "last_heartbeat": self.last_heartbeat,
            "state": self.state.value,
            "restart_count": self.restart_count,
            "last_exit_code": self.last_exit_code,
            "last_error": _bounded(self.last_error, _MAX_ERROR_LENGTH),
            "last_failure_at": self.last_failure_at,
            "last_exit_reason": _bounded(
                self.last_exit_reason, _MAX_EXIT_REASON_LENGTH
            ),
            "owner_token": self.owner_token,
            "owner_started_at": self.owner_started_at,
            "stop_requested": self.stop_requested,
        }


def _lock_file(handle: Any) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle: Any) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _lock_file_blocking(handle: Any) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


class HostProcessLock:
    """OS-backed singleton lock; stale locks are released by the kernel."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle: Any | None = None

    def acquire(self, owner: dict[str, Any]) -> None:
        if self._handle is not None:
            raise HostProcessError("Host process singleton lock is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            handle.write(b" ")
            handle.flush()
        acquired = False
        try:
            _lock_file(handle)
            acquired = True
            handle.seek(0)
            handle.truncate()
            handle.write(
                json.dumps(owner, sort_keys=True, ensure_ascii=True).encode("utf-8")
            )
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        except (OSError, BlockingIOError) as error:
            if acquired:
                _unlock_file(handle)
            handle.close()
            message = (
                "Could not persist host process lock ownership"
                if acquired
                else "Another host process already holds the singleton lock"
            )
            raise HostProcessError(message) from error
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            _unlock_file(handle)
        except OSError as error:
            raise HostProcessError("Could not release host process singleton lock") from error
        finally:
            handle.close()
            self._handle = None

    def locked(self) -> bool:
        if not self.path.is_file():
            return False
        try:
            handle = self.path.open("r+b")
        except OSError:
            return True
        try:
            _lock_file(handle)
        except (OSError, BlockingIOError):
            return True
        try:
            _unlock_file(handle)
        finally:
            handle.close()
        return False


class FileHostProcessStore:
    def __init__(self, root: Path, lock_root: Path) -> None:
        self.root = Path(root)
        self.lock_root = Path(lock_root)
        self._thread_lock = threading.Lock()

    def state_path(self, process_type: ProcessType) -> Path:
        return self.root / f"{process_type.value}.json"

    def singleton(self, process_type: ProcessType) -> HostProcessLock:
        return HostProcessLock(
            self.lock_root / f"host-process-{process_type.value}.lock"
        )

    def load(self, process_type: ProcessType) -> HostProcess | None:
        path = self.state_path(process_type)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise HostProcessError("Could not read host process state") from error
        if not isinstance(value, dict):
            raise HostProcessError("Host process state is not a JSON object")
        return HostProcess.from_dict(value)

    def save(self, process: HostProcess) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.state_path(process.process_type)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.root,
                prefix=f".{process.process_id}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary = Path(handle.name)
                json.dump(process.to_dict(), handle, indent=2, sort_keys=True, ensure_ascii=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as error:
            raise HostProcessError("Could not persist host process state") from error
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def update(
        self,
        process_type: ProcessType,
        transform: Callable[[HostProcess], HostProcess],
    ) -> HostProcess:
        with self._thread_lock, self._state_transaction(process_type):
            current = self.load(process_type)
            if current is None:
                raise HostProcessError("Host process state does not exist")
            updated = transform(current)
            self.save(updated)
            return updated

    def publish_start(
        self,
        process_type: ProcessType,
        transform: Callable[[HostProcess | None], HostProcess],
    ) -> HostProcess:
        """Inspect prior state and publish one startup decision atomically."""
        with self._thread_lock, self._state_transaction(process_type):
            updated = transform(self.load(process_type))
            self.save(updated)
            return updated

    @contextmanager
    def _state_transaction(self, process_type: ProcessType) -> Iterator[None]:
        self.lock_root.mkdir(parents=True, exist_ok=True)
        path = self.lock_root / f"host-process-{process_type.value}-state.lock"
        handle = path.open("a+b")
        if path.stat().st_size == 0:
            handle.write(b" ")
            handle.flush()
        acquired = False
        try:
            _lock_file_blocking(handle)
            acquired = True
        except OSError as error:
            handle.close()
            raise HostProcessError("Could not lock host process metadata") from error
        try:
            yield
        finally:
            try:
                if acquired:
                    _unlock_file(handle)
            finally:
                handle.close()


class HostProcessController:
    """Own lifecycle only; component runners retain all business authority."""

    def __init__(
        self,
        config: HostConfig,
        paths: StatePaths,
        *,
        environment: dict[str, str] | None = None,
        clock: Callable[[], str] = utc_now,
        token_factory: Callable[[], str] | None = None,
        pid_factory: Callable[[], int] = os.getpid,
        heartbeat_interval_seconds: float = 10.0,
        stale_after_seconds: float = 45.0,
    ) -> None:
        if not 0.05 <= heartbeat_interval_seconds <= 300:
            raise HostProcessError("Host heartbeat interval is outside 0.05-300 seconds")
        if not heartbeat_interval_seconds < stale_after_seconds <= 3600:
            raise HostProcessError("Host heartbeat stale threshold is invalid")
        self.config = config
        self.paths = paths
        self.environment = dict(os.environ) if environment is None else environment
        self.clock = clock
        self.token_factory = token_factory or (lambda: uuid4().hex)
        self.pid_factory = pid_factory
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.stale_after_seconds = stale_after_seconds
        self.store = FileHostProcessStore(paths.path("processes"), paths.path("locks"))

    def enabled(self, process_type: ProcessType) -> bool:
        return {
            ProcessType.SCHEDULER: self.config.scheduler_enabled,
            ProcessType.TELEGRAM: self.config.telegram_enabled,
            ProcessType.WEBHOOK_LOCAL: self.config.webhook_enabled,
        }[process_type]

    def run(
        self,
        process_type: ProcessType,
        runner: Callable[[], Any],
        *,
        request_component_stop: Callable[[], None],
    ) -> Any:
        if not isinstance(process_type, ProcessType):
            raise HostProcessError("Host process type is not supported")
        if not self.enabled(process_type):
            raise HostProcessError(f"Host process is disabled: {process_type.value}")
        readiness = HostReadinessService(
            self.config, self.paths, environment=self.environment
        ).check()
        if readiness["status"] == "FAIL":
            raise HostProcessError("Host readiness validation failed")

        now = self.clock()
        owner_token = self.token_factory()
        pid = self.pid_factory()
        singleton = self.store.singleton(process_type)
        singleton.acquire(
            {
                "schema_version": 1,
                "process_type": process_type.value,
                "pid": pid,
                "owner_token": owner_token,
                "owner_started_at": now,
            }
        )
        try:
            def publish(prior: HostProcess | None) -> HostProcess:
                if prior is not None and prior.stop_requested:
                    return HostProcess.from_dict(
                        {
                            **prior.to_dict(),
                            "enabled": True,
                            "pid": None,
                            "last_heartbeat": now,
                            "state": ProcessState.STOPPED.value,
                            "last_exit_code": None,
                            "last_exit_reason": "pending_stop_consumed",
                            "owner_token": None,
                            "owner_started_at": None,
                            "stop_requested": False,
                        }
                    )
                restart_count = min(
                    (prior.restart_count + 1) if prior and prior.started_at else 0,
                    _MAX_RESTART_COUNT,
                )
                stale_recovery = bool(prior and prior.state in _ACTIVE_STATES)
                return HostProcess(
                    process_id=process_type.value,
                    process_type=process_type,
                    enabled=True,
                    pid=pid,
                    started_at=now,
                    last_heartbeat=now,
                    state=ProcessState.STARTING,
                    restart_count=restart_count,
                    last_exit_code=prior.last_exit_code if prior else None,
                    last_error=(
                        "Recovered stale active process record" if stale_recovery else None
                    ),
                    last_failure_at=prior.last_failure_at if prior else None,
                    last_exit_reason=(
                        "stale_record_recovered" if stale_recovery else None
                    ),
                    owner_token=owner_token,
                    owner_started_at=now,
                )

            starting = self.store.publish_start(process_type, publish)
            if starting.state is not ProcessState.STARTING:
                raise HostProcessError(
                    "Pending host stop request was consumed before process startup"
                )

            def activate(current: HostProcess) -> HostProcess:
                if current.owner_token != owner_token:
                    raise HostProcessError("Host process ownership changed unexpectedly")
                if current.stop_requested:
                    return current
                return HostProcess.from_dict(
                    {**current.to_dict(), "state": ProcessState.RUNNING.value}
                )

            active = self.store.update(process_type, activate)
        except Exception:
            singleton.release()
            raise

        finished = threading.Event()
        stop_called = threading.Event()
        stop_guard = threading.Lock()
        signal_notice = _SignalNotice()

        def request_stop(reason: str) -> None:
            with stop_guard:
                if stop_called.is_set():
                    return
                stop_called.set()
            self._replace(
                process_type,
                owner_token,
                state=ProcessState.STOPPING,
                stop_requested=True,
                last_exit_reason=reason,
            )
            request_component_stop()

        def heartbeat() -> None:
            while True:
                signal_notice.event.wait(self.heartbeat_interval_seconds)
                if finished.is_set():
                    return
                if signal_notice.event.is_set():
                    try:
                        request_stop(signal_notice.reason or "signal")
                    except HostProcessError:
                        return
                    return
                try:
                    current = self.store.load(process_type)
                except HostProcessError:
                    return
                if current is None or current.owner_token != owner_token:
                    return
                if current.stop_requested:
                    try:
                        request_stop("stop_requested")
                    except HostProcessError:
                        return
                else:
                    try:
                        self._replace(
                            process_type,
                            owner_token,
                            last_heartbeat=self.clock(),
                        )
                    except HostProcessError:
                        return

        heartbeat_thread = threading.Thread(
            target=heartbeat,
            name=f"host-heartbeat-{process_type.value}",
            daemon=True,
        )
        handlers = self._install_signal_handlers(signal_notice)
        heartbeat_thread.start()
        try:
            if active.stop_requested:
                request_stop("stop_requested")
            result = runner()
            reason = "completed"
            if isinstance(result, dict):
                if result.get("interrupted") is True:
                    reason = "keyboard_interrupt"
                elif isinstance(result.get("reason"), str):
                    reason = result["reason"]
            finished.set()
            self._replace(
                process_type,
                owner_token,
                state=ProcessState.STOPPED,
                pid=None,
                last_heartbeat=self.clock(),
                last_exit_code=0,
                last_error=None,
                last_exit_reason=reason,
                stop_requested=False,
                owner_token=None,
            )
            return result
        except KeyboardInterrupt:
            request_stop("keyboard_interrupt")
            finished.set()
            self._replace(
                process_type,
                owner_token,
                state=ProcessState.STOPPED,
                pid=None,
                last_heartbeat=self.clock(),
                last_exit_code=0,
                last_error=None,
                last_exit_reason="keyboard_interrupt",
                stop_requested=False,
                owner_token=None,
            )
            return {"status": "stopped", "reason": "keyboard_interrupt"}
        except Exception as error:
            failed_at = self.clock()
            finished.set()
            self._replace(
                process_type,
                owner_token,
                state=ProcessState.FAILED,
                pid=None,
                last_heartbeat=failed_at,
                last_exit_code=1,
                last_error=_bounded(error, _MAX_ERROR_LENGTH),
                last_failure_at=failed_at,
                last_exit_reason="runner_failed",
                stop_requested=False,
                owner_token=None,
            )
            raise HostProcessError(
                f"Host process failed: {_bounded(error, _MAX_ERROR_LENGTH)}"
            ) from error
        finally:
            finished.set()
            signal_notice.event.set()
            heartbeat_thread.join(timeout=self.heartbeat_interval_seconds + 0.5)
            self._restore_signal_handlers(handlers)
            singleton.release()

    def request_stop(self, process_type: ProcessType) -> bool:
        if self.store.load(process_type) is None:
            return False
        requested = False

        def transform(item: HostProcess) -> HostProcess:
            nonlocal requested
            if item.state not in _ACTIVE_STATES:
                return item
            requested = True
            return HostProcess.from_dict(
                {
                    **item.to_dict(),
                    "state": ProcessState.STOPPING.value,
                    "stop_requested": True,
                    "last_exit_reason": "stop_requested",
                }
            )

        self.store.update(
            process_type,
            transform,
        )
        return requested

    def status(self) -> dict[str, Any]:
        now = _parse_time(self.clock())
        processes: list[dict[str, Any]] = []
        for process_type in ProcessType:
            current = self.store.load(process_type) or HostProcess.empty(
                process_type, enabled=self.enabled(process_type)
            )
            lock_held = self.store.singleton(process_type).locked()
            heartbeat = _parse_time(current.last_heartbeat)
            heartbeat_stale = bool(
                current.state in _ACTIVE_STATES
                and (
                    heartbeat is None
                    or now is None
                    or (now - heartbeat).total_seconds() > self.stale_after_seconds
                )
            )
            stale_record = current.state in _ACTIVE_STATES and (
                not lock_held or heartbeat_stale
            )
            value = current.to_dict()
            value.pop("owner_token", None)
            value.update(
                {
                    "enabled": self.enabled(process_type),
                    "singleton_lock_held": lock_held,
                    "heartbeat_stale": heartbeat_stale,
                    "stale_record": stale_record,
                }
            )
            processes.append(value)
        return {
            "status": "PASS",
            "operation": "host_process_status",
            "checked_at": self.clock(),
            "processes": processes,
        }

    def _replace(
        self,
        process_type: ProcessType,
        expected_owner_token: str,
        **changes: Any,
    ) -> None:
        def transform(current: HostProcess) -> HostProcess:
            if current.owner_token != expected_owner_token:
                raise HostProcessError("Host process ownership changed unexpectedly")
            return HostProcess.from_dict({**current.to_dict(), **changes})

        self.store.update(process_type, transform)

    @staticmethod
    def _install_signal_handlers(
        notice: "_SignalNotice",
    ) -> dict[int, Any]:
        if threading.current_thread() is not threading.main_thread():
            return {}
        installed: dict[int, Any] = {}
        for candidate, reason in (
            (getattr(signal, "SIGTERM", None), "sigterm"),
            (getattr(signal, "SIGINT", None), "sigint"),
        ):
            if candidate is None:
                continue
            installed[candidate] = signal.getsignal(candidate)
            signal.signal(
                candidate,
                lambda _signum, _frame, text=reason: notice.notify(text),
            )
        return installed

    @staticmethod
    def _restore_signal_handlers(handlers: dict[int, Any]) -> None:
        for number, handler in handlers.items():
            signal.signal(number, handler)


class _SignalNotice:
    """In-memory signal notification with no persistence or component work."""

    def __init__(self) -> None:
        self.event = threading.Event()
        self.reason: str | None = None

    def notify(self, reason: str) -> None:
        if not self.event.is_set():
            self.reason = reason
        self.event.set()
