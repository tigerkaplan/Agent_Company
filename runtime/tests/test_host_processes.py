from __future__ import annotations

import json
import io
import os
import signal
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from integrations.telegram.state import TelegramStateStore
from runtime.cli.__main__ import LocalWebhookProcess, build_parser, run
from runtime.core.jobs import JobRuntime
from runtime.host.config import HostConfig
from runtime.host.paths import StatePaths
from runtime.host.processes import (
    FileHostProcessStore,
    HostProcess,
    HostProcessController,
    HostProcessError,
    ProcessState,
    ProcessType,
    _SignalNotice,
)
from runtime.host.service import HostReadinessService


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> str:
        return self.value.isoformat().replace("+00:00", "Z")

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def host_config(**overrides: object) -> HostConfig:
    value: dict[str, object] = {
        "schema_version": 1,
        "environment_mode": "local",
        "state_root": None,
        "secret_file": None,
        "provider_execution_enabled": False,
        "provider_credential_root": None,
        "telegram_enabled": False,
        "webhook_enabled": False,
        "notifications_enabled": False,
        "scheduler_enabled": True,
        "git_enabled": False,
    }
    value.update(overrides)
    return HostConfig.from_dict(value)


class Phase8CHostProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "agent-company-state"
        self.config = host_config()
        self.paths = StatePaths.resolve(
            REPOSITORY_ROOT,
            self.config,
            cli_root=self.root,
            environment={},
        )
        HostReadinessService(self.config, self.paths, environment={}).initialize()
        self.clock = MutableClock()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def controller(
        self,
        *,
        config: HostConfig | None = None,
        environment: dict[str, str] | None = None,
    ) -> HostProcessController:
        return HostProcessController(
            config or self.config,
            self.paths,
            environment={} if environment is None else environment,
            clock=self.clock,
            token_factory=lambda: "owner-token",
            pid_factory=lambda: 4242,
            heartbeat_interval_seconds=0.05,
            stale_after_seconds=0.2,
        )

    def test_a_scheduler_starts_through_lifecycle_wrapper(self) -> None:
        observed: list[str] = []

        def runner() -> dict[str, str]:
            observed.append(
                self.controller().store.load(ProcessType.SCHEDULER).state.value
            )
            return {"status": "stopped", "reason": "max_cycles_reached"}

        result = self.controller().run(
            ProcessType.SCHEDULER, runner, request_component_stop=lambda: None
        )

        self.assertEqual(observed, ["RUNNING"])
        self.assertEqual(result["reason"], "max_cycles_reached")
        self.assertEqual(
            self.controller().store.load(ProcessType.SCHEDULER).state,
            ProcessState.STOPPED,
        )

    def test_a2_cli_scheduler_uses_host_lifecycle_wrapper(self) -> None:
        config_path = Path(self.temporary.name) / "host.json"
        value = self.config.to_safe_dict()
        value["state_root"] = str(self.root)
        config_path.write_text(json.dumps(value), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = run(
                [
                    "--host-config",
                    str(config_path),
                    "host",
                    "run",
                    "scheduler",
                    "--dry-run",
                    "--max-cycles",
                    "1",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            self.controller().store.load(ProcessType.SCHEDULER).state,
            ProcessState.STOPPED,
        )

    def test_a3_explicit_provider_is_rejected_before_discovery_when_disabled(
        self,
    ) -> None:
        config_path = Path(self.temporary.name) / "provider-disabled-host.json"
        value = self.config.to_safe_dict()
        value["state_root"] = str(self.root)
        value["provider_credential_root"] = str(
            Path(self.temporary.name) / "must-not-be-accessed"
        )
        config_path.write_text(json.dumps(value), encoding="utf-8")
        error = io.StringIO()

        with patch(
            "runtime.cli.__main__.build_provider_router"
        ) as provider_discovery, patch(
            "runtime.cli.__main__.build_scheduler_loop"
        ) as scheduler_builder, patch.object(
            HostReadinessService, "_check_provider_credentials"
        ) as credential_check, redirect_stderr(error):
            exit_code = run(
                [
                    "--host-config",
                    str(config_path),
                    "host",
                    "run",
                    "scheduler",
                    "--executor",
                    "provider",
                    "--max-cycles",
                    "1",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("disabled by canonical host configuration", error.getvalue())
        provider_discovery.assert_not_called()
        scheduler_builder.assert_not_called()
        credential_check.assert_not_called()

    def test_a4_enabled_provider_mode_runs_normal_readiness(self) -> None:
        credential_root = Path(self.temporary.name) / "provider-credentials"
        credential_root.mkdir()
        config = host_config(
            provider_execution_enabled=True,
            provider_credential_root=str(credential_root),
        )
        config_path = Path(self.temporary.name) / "provider-enabled-host.json"
        value = config.to_safe_dict()
        value["state_root"] = str(self.root)
        config_path.write_text(json.dumps(value), encoding="utf-8")
        router = Mock()
        router.availability.return_value = {"codex": Mock(available=True)}
        scheduler_loop = Mock()
        scheduler_loop.run.return_value = {"reason": "max_cycles_reached"}
        output = io.StringIO()

        with patch.dict(os.environ, {}, clear=True), patch(
            "runtime.cli.__main__.build_provider_router", return_value=router
        ) as provider_discovery, patch(
            "runtime.cli.__main__.build_scheduler_loop", return_value=scheduler_loop
        ) as scheduler_builder, redirect_stdout(output):
            exit_code = run(
                [
                    "--host-config",
                    str(config_path),
                    "host",
                    "run",
                    "scheduler",
                    "--executor",
                    "provider",
                    "--max-cycles",
                    "1",
                ]
            )

        self.assertEqual(exit_code, 0)
        provider_discovery.assert_called_once()
        scheduler_builder.assert_called_once()
        scheduler_loop.run.assert_called_once()

    def test_a5_malformed_enabled_provider_readiness_fails_closed(self) -> None:
        config = host_config(
            provider_execution_enabled=True,
            provider_credential_root=str(Path(self.temporary.name) / "missing"),
        )
        config_path = Path(self.temporary.name) / "provider-missing-host.json"
        value = config.to_safe_dict()
        value["state_root"] = str(self.root)
        config_path.write_text(json.dumps(value), encoding="utf-8")
        router = Mock()
        router.availability.return_value = {"codex": Mock(available=True)}
        scheduler_loop = Mock()
        error = io.StringIO()

        with patch.dict(os.environ, {}, clear=True), patch(
            "runtime.cli.__main__.build_provider_router", return_value=router
        ), patch(
            "runtime.cli.__main__.build_scheduler_loop", return_value=scheduler_loop
        ), redirect_stderr(error):
            exit_code = run(
                [
                    "--host-config",
                    str(config_path),
                    "host",
                    "run",
                    "scheduler",
                    "--executor",
                    "provider",
                    "--max-cycles",
                    "1",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("readiness validation failed", error.getvalue())
        scheduler_loop.run.assert_not_called()

    def test_b_telegram_entrypoint_is_a_fixed_parser_choice(self) -> None:
        args = build_parser().parse_args(["host", "run", "telegram"])
        self.assertEqual(args.process, "telegram")

    def test_c_duplicate_scheduler_start_is_rejected(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        failures: list[BaseException] = []

        def first() -> None:
            try:
                self.controller().run(
                    ProcessType.SCHEDULER,
                    lambda: (entered.set(), release.wait(2), {"reason": "done"})[-1],
                    request_component_stop=release.set,
                )
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=first)
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(HostProcessError, "singleton lock"):
            self.controller().run(
                ProcessType.SCHEDULER,
                lambda: None,
                request_component_stop=lambda: None,
            )
        release.set()
        thread.join(2)
        self.assertFalse(failures)

    def test_d_duplicate_telegram_start_is_rejected(self) -> None:
        remote_config = Path(self.temporary.name) / "remote.json"
        remote_config.write_text(
            (REPOSITORY_ROOT / "config" / "remote.example.json").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        config = host_config(scheduler_enabled=False, telegram_enabled=True)
        environment = {
            "AGENT_COMPANY_TELEGRAM_BOT_TOKEN": "test-token-not-used",
            "AGENT_COMPANY_REMOTE_CONFIG": str(remote_config),
        }
        HostReadinessService(config, self.paths, environment=environment).initialize()
        entered = threading.Event()
        release = threading.Event()
        thread = threading.Thread(
            target=lambda: self.controller(
                config=config, environment=environment
            ).run(
                ProcessType.TELEGRAM,
                lambda: (entered.set(), release.wait(2), {"reason": "done"})[-1],
                request_component_stop=release.set,
            )
        )
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaisesRegex(HostProcessError, "singleton lock"):
            self.controller(config=config, environment=environment).run(
                ProcessType.TELEGRAM,
                lambda: None,
                request_component_stop=lambda: None,
            )
        release.set()
        thread.join(2)

    def test_e_stale_active_record_is_recoverable(self) -> None:
        store = self.controller().store
        store.save(
            HostProcess(
                process_id="scheduler",
                process_type=ProcessType.SCHEDULER,
                enabled=True,
                pid=100,
                started_at="2026-09-25T11:00:00Z",
                last_heartbeat="2026-09-25T11:00:00Z",
                state=ProcessState.RUNNING,
                owner_token="dead-owner",
                owner_started_at="2026-09-25T11:00:00Z",
            )
        )
        seen: list[str | None] = []

        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: seen.append(store.load(ProcessType.SCHEDULER).last_exit_reason),
            request_component_stop=lambda: None,
        )

        self.assertEqual(seen, ["stale_record_recovered"])
        self.assertEqual(store.load(ProcessType.SCHEDULER).restart_count, 1)

    def test_f_singleton_lock_releases_after_clean_exit(self) -> None:
        controller = self.controller()
        controller.run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "done"},
            request_component_stop=lambda: None,
        )
        self.assertFalse(controller.store.singleton(ProcessType.SCHEDULER).locked())

    def test_g_failure_is_persisted_and_next_start_recovers(self) -> None:
        with self.assertRaisesRegex(HostProcessError, "simulated crash"):
            self.controller().run(
                ProcessType.SCHEDULER,
                lambda: (_ for _ in ()).throw(ValueError("simulated crash")),
                request_component_stop=lambda: None,
            )
        failed = self.controller().store.load(ProcessType.SCHEDULER)
        self.assertEqual(failed.state, ProcessState.FAILED)
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "restarted"},
            request_component_stop=lambda: None,
        )
        self.assertEqual(
            self.controller().store.load(ProcessType.SCHEDULER).state,
            ProcessState.STOPPED,
        )

    def test_g2_abrupt_exit_leaves_stale_recoverable_record(self) -> None:
        with self.assertRaises(SystemExit):
            self.controller().run(
                ProcessType.SCHEDULER,
                lambda: (_ for _ in ()).throw(SystemExit(9)),
                request_component_stop=lambda: None,
            )
        status = self.controller().status()["processes"][0]
        self.assertEqual(status["state"], "RUNNING")
        self.assertTrue(status["stale_record"])
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "recovered"},
            request_component_stop=lambda: None,
        )
        self.assertEqual(
            self.controller().store.load(ProcessType.SCHEDULER).state,
            ProcessState.STOPPED,
        )

    def test_h_persisted_stop_request_calls_component_stop(self) -> None:
        entered = threading.Event()
        stopped = threading.Event()
        thread = threading.Thread(
            target=lambda: self.controller().run(
                ProcessType.SCHEDULER,
                lambda: (entered.set(), stopped.wait(2), {"reason": "stop_requested"})[-1],
                request_component_stop=stopped.set,
            )
        )
        thread.start()
        self.assertTrue(entered.wait(1))
        self.assertTrue(self.controller().request_stop(ProcessType.SCHEDULER))
        thread.join(2)
        self.assertTrue(stopped.is_set())
        self.assertEqual(
            self.controller().store.load(ProcessType.SCHEDULER).last_exit_reason,
            "stop_requested",
        )

    def test_h2_sigterm_handler_requests_graceful_stop(self) -> None:
        installed: dict[int, object] = {}
        notice = _SignalNotice()
        with patch.object(signal, "getsignal", return_value="prior"), patch.object(
            signal,
            "signal",
            side_effect=lambda number, handler: installed.__setitem__(number, handler),
        ):
            handlers = self.controller()._install_signal_handlers(notice)
        self.assertIn(signal.SIGTERM, handlers)
        self.assertIn(signal.SIGINT, handlers)
        started = time.monotonic()
        installed[signal.SIGTERM](signal.SIGTERM, None)
        installed[signal.SIGINT](signal.SIGINT, None)
        self.assertLess(time.monotonic() - started, 0.1)
        self.assertTrue(notice.event.is_set())
        self.assertEqual(notice.reason, "sigterm")

    def test_h3_signal_notice_coordinates_stop_outside_metadata_lock(self) -> None:
        controller = self.controller()
        captured: dict[str, _SignalNotice] = {}
        stopped = threading.Event()
        observed: dict[str, object] = {}

        def install(notice: _SignalNotice) -> dict[int, object]:
            captured["notice"] = notice
            return {}

        def component_stop() -> None:
            observed["component_stop_thread"] = threading.current_thread().name
            stopped.set()

        def runner() -> dict[str, str]:
            with controller.store._thread_lock:
                started = time.monotonic()
                captured["notice"].notify("sigterm")
                captured["notice"].notify("sigint")
                observed["handler_elapsed"] = time.monotonic() - started
                observed["stopped_while_locked"] = stopped.is_set()
            self.assertTrue(stopped.wait(1))
            return {"reason": "stop_requested"}

        with patch.object(
            controller, "_install_signal_handlers", side_effect=install
        ):
            result = controller.run(
                ProcessType.SCHEDULER,
                runner,
                request_component_stop=component_stop,
            )

        self.assertEqual(result["reason"], "stop_requested")
        self.assertLess(observed["handler_elapsed"], 0.1)
        self.assertFalse(observed["stopped_while_locked"])
        self.assertEqual(captured["notice"].reason, "sigterm")
        self.assertEqual(
            observed["component_stop_thread"], "host-heartbeat-scheduler"
        )
        final = controller.store.load(ProcessType.SCHEDULER)
        self.assertEqual(final.state, ProcessState.STOPPED)
        self.assertFalse(final.stop_requested)

    def test_i_keyboard_interrupt_stops_cleanly(self) -> None:
        stopped: list[bool] = []
        result = self.controller().run(
            ProcessType.SCHEDULER,
            lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
            request_component_stop=lambda: stopped.append(True),
        )
        self.assertEqual(result["reason"], "keyboard_interrupt")
        self.assertEqual(stopped, [True])
        self.assertEqual(
            self.controller().store.load(ProcessType.SCHEDULER).state,
            ProcessState.STOPPED,
        )

    def test_i2_stop_before_start_is_consumed_without_running(self) -> None:
        controller = self.controller()
        controller.store.save(
            HostProcess(
                process_id="scheduler",
                process_type=ProcessType.SCHEDULER,
                enabled=True,
                pid=100,
                started_at="2026-09-25T11:00:00Z",
                last_heartbeat="2026-09-25T11:00:00Z",
                state=ProcessState.STOPPING,
                owner_token="dead-owner",
                owner_started_at="2026-09-25T11:00:00Z",
                stop_requested=True,
            )
        )
        runner = Mock()

        with self.assertRaisesRegex(HostProcessError, "consumed before process startup"):
            controller.run(
                ProcessType.SCHEDULER,
                runner,
                request_component_stop=lambda: None,
            )

        runner.assert_not_called()
        consumed = controller.store.load(ProcessType.SCHEDULER)
        self.assertEqual(consumed.state, ProcessState.STOPPED)
        self.assertEqual(consumed.last_exit_reason, "pending_stop_consumed")
        self.assertFalse(consumed.stop_requested)
        controller.run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "restarted"},
            request_component_stop=lambda: None,
        )

    def test_i3_stop_winning_before_start_transaction_is_not_lost(self) -> None:
        owner = self.controller()
        owner.store.save(
            HostProcess(
                process_id="scheduler",
                process_type=ProcessType.SCHEDULER,
                enabled=True,
                pid=100,
                started_at="2026-09-25T11:00:00Z",
                last_heartbeat="2026-09-25T11:00:00Z",
                state=ProcessState.RUNNING,
                owner_token="dead-owner",
                owner_started_at="2026-09-25T11:00:00Z",
            )
        )
        before_transaction = threading.Event()
        release = threading.Event()
        errors: list[BaseException] = []
        runner = Mock()
        original_publish = owner.store.publish_start

        def delayed_publish(*args: object, **kwargs: object) -> HostProcess:
            before_transaction.set()
            release.wait(2)
            return original_publish(*args, **kwargs)

        def start_owner() -> None:
            try:
                owner.run(
                    ProcessType.SCHEDULER,
                    runner,
                    request_component_stop=lambda: None,
                )
            except BaseException as error:
                errors.append(error)

        with patch.object(owner.store, "publish_start", side_effect=delayed_publish):
            thread = threading.Thread(target=start_owner)
            thread.start()
            self.assertTrue(before_transaction.wait(1))
            self.assertTrue(self.controller().request_stop(ProcessType.SCHEDULER))
            release.set()
            thread.join(2)

        self.assertFalse(thread.is_alive())
        runner.assert_not_called()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], HostProcessError)
        consumed = owner.store.load(ProcessType.SCHEDULER)
        self.assertEqual(consumed.state, ProcessState.STOPPED)
        self.assertEqual(consumed.last_exit_reason, "pending_stop_consumed")
        self.assertFalse(consumed.stop_requested)

    def test_i4_stop_after_start_publication_targets_new_owner(self) -> None:
        owner = self.controller()
        owner.store.save(
            HostProcess(
                process_id="scheduler",
                process_type=ProcessType.SCHEDULER,
                enabled=True,
                pid=100,
                started_at="2026-09-25T11:00:00Z",
                last_heartbeat="2026-09-25T11:00:00Z",
                state=ProcessState.RUNNING,
                owner_token="dead-owner",
                owner_started_at="2026-09-25T11:00:00Z",
            )
        )
        published = threading.Event()
        release = threading.Event()
        stopped = threading.Event()
        runner_entered = threading.Event()
        request_entered = threading.Event()
        request_results: list[bool] = []
        errors: list[BaseException] = []
        original_save = owner.store.save

        def gated_save(item: HostProcess) -> None:
            original_save(item)
            if item.state is ProcessState.STARTING and not published.is_set():
                published.set()
                release.wait(2)

        def start_owner() -> None:
            try:
                owner.run(
                    ProcessType.SCHEDULER,
                    lambda: (
                        runner_entered.set(),
                        stopped.wait(2),
                        {"reason": "stop_requested"},
                    )[-1],
                    request_component_stop=stopped.set,
                )
            except BaseException as error:
                errors.append(error)

        requester = self.controller()
        original_update = requester.store.update

        def observed_update(*args: object, **kwargs: object) -> HostProcess:
            request_entered.set()
            return original_update(*args, **kwargs)

        with patch.object(owner.store, "save", side_effect=gated_save), patch.object(
            requester.store, "update", side_effect=observed_update
        ):
            owner_thread = threading.Thread(target=start_owner)
            owner_thread.start()
            self.assertTrue(published.wait(1))
            request_thread = threading.Thread(
                target=lambda: request_results.append(
                    requester.request_stop(ProcessType.SCHEDULER)
                )
            )
            request_thread.start()
            self.assertTrue(request_entered.wait(1))
            release.set()
            request_thread.join(2)
            owner_thread.join(3)

        self.assertFalse(request_thread.is_alive())
        self.assertFalse(owner_thread.is_alive())
        self.assertEqual(request_results, [True])
        self.assertTrue(runner_entered.is_set())
        self.assertTrue(stopped.is_set())
        self.assertFalse(errors)
        final = owner.store.load(ProcessType.SCHEDULER)
        self.assertEqual(final.state, ProcessState.STOPPED)
        self.assertFalse(final.stop_requested)

    def test_j_scheduler_claim_state_is_untouched_by_host_restart(self) -> None:
        jobs = JobRuntime(self.paths.path("jobs"), clock=self.clock)
        payload = {
            "task": "Preserve claim",
            "task_class": "communications",
            "agent": "communications",
            "workflow": "communications",
            "capability": "business_communications",
            "risk_level": "low",
            "approval_status": "not_required",
            "review_required": False,
            "max_attempts": 1,
            "input_refs": [],
            "output_refs": [],
            "created_by": "phase8c-test",
        }
        created = jobs.create(payload)
        jobs.enqueue(created["job_id"])
        claimed = jobs.claim(claimed_by="worker-a", lease_seconds=30)
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "no_work"},
            request_component_stop=lambda: None,
        )
        self.assertEqual(jobs.show(claimed["job_id"])["claimed_by"], "worker-a")

    def test_k_telegram_offset_survives_host_lifecycle(self) -> None:
        state = TelegramStateStore(self.paths.path("telegram"))
        state.advance(41, updated_at=self.clock())
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "done"},
            request_component_stop=lambda: None,
        )
        self.assertEqual(state.load().next_update_id, 42)

    def test_l_webhook_provenance_is_untouched(self) -> None:
        path = self.paths.path("webhooks") / "retained.webhook-provenance.json"
        path.write_text('{"retained": true}\n', encoding="utf-8")
        before = path.read_bytes()
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "done"},
            request_component_stop=lambda: None,
        )
        self.assertEqual(path.read_bytes(), before)

    def test_l2_webhook_local_wrapper_closes_without_serving_after_stop(self) -> None:
        calls: list[str] = []

        class FakeServer:
            def handle_request(self) -> None:
                calls.append("handled")

            def server_close(self) -> None:
                calls.append("closed")

        process = LocalWebhookProcess(FakeServer)
        process.stop()
        result = process.run()
        self.assertEqual(result["reason"], "stop_requested")
        self.assertEqual(calls, ["closed"])

    def test_m_disabled_component_cannot_start(self) -> None:
        with self.assertRaisesRegex(HostProcessError, "disabled"):
            self.controller().run(
                ProcessType.TELEGRAM,
                lambda: None,
                request_component_stop=lambda: None,
            )

    def test_n_missing_token_blocks_telegram_start(self) -> None:
        config = host_config(scheduler_enabled=False, telegram_enabled=True)
        with self.assertRaisesRegex(HostProcessError, "readiness"):
            self.controller(config=config).run(
                ProcessType.TELEGRAM,
                lambda: None,
                request_component_stop=lambda: None,
            )

    def test_o_uninitialized_host_state_blocks_start(self) -> None:
        other_root = Path(self.temporary.name) / "other-agent-company-state"
        paths = StatePaths.resolve(
            REPOSITORY_ROOT, self.config, cli_root=other_root, environment={}
        )
        controller = HostProcessController(self.config, paths, environment={})
        with self.assertRaisesRegex(HostProcessError, "readiness"):
            controller.run(
                ProcessType.SCHEDULER,
                lambda: None,
                request_component_stop=lambda: None,
            )

    def test_p_status_is_read_only_and_q_contains_no_secrets(self) -> None:
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "done"},
            request_component_stop=lambda: None,
        )
        state_path = self.controller().store.state_path(ProcessType.SCHEDULER)
        before = state_path.read_bytes()
        status = self.controller().status()
        self.assertEqual(state_path.read_bytes(), before)
        rendered = json.dumps(status)
        self.assertNotIn("owner-token", rendered)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", rendered)

    def test_r_process_state_uses_canonical_root_and_s_is_ignored(self) -> None:
        self.controller().run(
            ProcessType.SCHEDULER,
            lambda: {"reason": "done"},
            request_component_stop=lambda: None,
        )
        self.assertEqual(
            self.controller().store.state_path(ProcessType.SCHEDULER).parent,
            self.root / "host" / "processes",
        )
        probe = "runtime/state/host/processes/scheduler.json"
        result = subprocess.run(
            ["git", "check-ignore", probe],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_t_arbitrary_process_selection_is_rejected(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["host", "run", "arbitrary.exe"])

    def test_u_crash_metadata_is_bounded(self) -> None:
        with self.assertRaises(HostProcessError):
            self.controller().run(
                ProcessType.SCHEDULER,
                lambda: (_ for _ in ()).throw(ValueError("x" * 2000)),
                request_component_stop=lambda: None,
            )
        failed = self.controller().store.load(ProcessType.SCHEDULER)
        self.assertLessEqual(len(failed.last_error), 512)

    def test_v_heartbeat_staleness_is_detected(self) -> None:
        store = self.controller().store
        store.save(
            HostProcess(
                process_id="scheduler",
                process_type=ProcessType.SCHEDULER,
                enabled=True,
                pid=123,
                started_at=self.clock(),
                last_heartbeat=self.clock(),
                state=ProcessState.RUNNING,
                owner_token="old-owner",
                owner_started_at=self.clock(),
            )
        )
        self.clock.advance(1)
        scheduler = self.controller().status()["processes"][0]
        self.assertTrue(scheduler["heartbeat_stale"])
        self.assertTrue(scheduler["stale_record"])


if __name__ == "__main__":
    unittest.main()
