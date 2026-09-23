"""Minimal deterministic command-line interface for local canonical jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from runtime.actions.runtime import ControlledWriteRuntime
from runtime.actions.store import FileMutationArtifactStore
from runtime.approvals.factory import build_approval_runtime
from runtime.approvals.runtime import ApprovalRuntimeError
from runtime.approvals.store import ApprovalStoreError
from runtime.core.jobs import JobRuntime, RuntimeError
from runtime.core.references import CanonicalReferenceResolver
from runtime.executors.local import LocalExecutor
from runtime.git.runtime import GitRuntime, GitRuntimeError
from runtime.git.forge import ForgeError, GitHubCliPullRequestAdapter
from runtime.git.remote_runtime import RemoteGitRuntime, RemoteGitRuntimeError
from runtime.git.remote_store import FileRemoteGitArtifactStore
from runtime.git.store import GitStoreError
from runtime.providers.artifacts import FileProviderArtifactStore
from runtime.providers.config import ProviderConfigError
from runtime.providers.context import ExecutionContextBuilder
from runtime.providers.executor import ProviderExecutor
from runtime.providers.factory import build_provider_router
from runtime.remote.config import RemoteRuntimeConfig
from runtime.remote.models import RemoteCommand, RemoteCommandError, RemoteCommandType
from runtime.remote.service import RemoteCommandService, RemoteCommandServiceError
from runtime.remote.store import FileRemoteCommandStore, RemoteStoreError
from runtime.review.factory import build_reviewer_runtime
from runtime.review.store import FileReviewStore, ReviewStoreError
from runtime.scheduler.dispatch import CanonicalDispatchAdapter
from runtime.scheduler.loop import SchedulerConfig, SchedulerLoop, SchedulerLoopError
from runtime.scheduler.schedules import ScheduleRuntime, ScheduleRuntimeError
from runtime.storage.execution_store import FileExecutionStore
from runtime.storage.scheduler_state_store import (
    FileSchedulerStateStore,
    SchedulerStateStoreError,
)
from runtime.workers.worker import Worker


def default_state_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_RUNTIME_STATE_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "jobs"


def default_execution_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_EXECUTION_STATE_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "executions"


def default_schedule_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_SCHEDULE_STATE_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "schedules"


def default_approval_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_APPROVAL_STATE_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "approvals"


def default_scheduler_runtime_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_SCHEDULER_RUNTIME_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "scheduler-runtime"


def default_git_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_GIT_STATE_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "executions" / "git"


def default_remote_root() -> Path:
    configured = os.environ.get("AGENT_COMPANY_REMOTE_STATE_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "state" / "remote"


def default_remote_config() -> Path:
    configured = os.environ.get("AGENT_COMPANY_REMOTE_CONFIG")
    if configured:
        return Path(configured)
    return repository_root() / "config" / "remote.local.json"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent Company local job runtime")
    parser.add_argument(
        "--state-root",
        type=Path,
        default=default_state_root(),
        help="Local directory for generated job JSON records",
    )
    parser.add_argument(
        "--execution-root",
        type=Path,
        default=default_execution_root(),
        help="Local directory for generated execution JSON records",
    )
    parser.add_argument(
        "--schedule-root",
        type=Path,
        default=default_schedule_root(),
        help="Local directory for generated schedule JSON records",
    )
    parser.add_argument(
        "--approval-root",
        type=Path,
        default=default_approval_root(),
        help="Local directory for generated approval JSON records",
    )
    parser.add_argument(
        "--scheduler-runtime-root",
        type=Path,
        default=default_scheduler_runtime_root(),
        help="Local directory for scheduler state and bounded audit records",
    )
    parser.add_argument(
        "--git-state-root",
        type=Path,
        default=default_git_root(),
        help="Local directory for generated Git change-set and commit evidence",
    )
    parser.add_argument(
        "--remote-state-root",
        type=Path,
        default=default_remote_root(),
        help="Local directory for generated remote command audit/replay state",
    )
    parser.add_argument(
        "--remote-config",
        type=Path,
        default=default_remote_config(),
        help="Ignored local remote identity mapping configuration",
    )
    top = parser.add_subparsers(dest="resource", required=True)
    job = top.add_parser("job", help="Manage canonical jobs")
    commands = job.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create and persist a job")
    create.add_argument(
        "--from",
        dest="input_path",
        type=Path,
        required=True,
        help="JSON file containing dispatcher-selected canonical job fields",
    )
    create.add_argument(
        "--dry-run",
        action="store_true",
        help="Persist canonical dry-run state; controlled writes remain preview-only",
    )

    enqueue = commands.add_parser("enqueue", help="Move a created job to queued")
    enqueue.add_argument("job_id")

    list_jobs = commands.add_parser("list", help="List jobs in FIFO order")
    list_jobs.add_argument("--status", help="Optional canonical status filter")

    show = commands.add_parser("show", help="Inspect one job")
    show.add_argument("job_id")

    commands.add_parser("claim", help="Claim the oldest queued job")

    transition = commands.add_parser("transition", help="Apply a canonical transition")
    transition.add_argument("job_id")
    transition.add_argument("status")

    complete = commands.add_parser("complete", help="Mark a running/reviewing job complete")
    complete.add_argument("job_id")

    fail = commands.add_parser("fail", help="Mark a running/reviewing job failed")
    fail.add_argument("job_id")
    fail.add_argument("--code", default="execution_failed")
    fail.add_argument("--message", default="Job execution failed")
    fail.add_argument("--not-retryable", action="store_true")

    retry = commands.add_parser("retry", help="Create a traceable retry for a failed job")
    retry.add_argument("job_id")

    for command_name in ("schedule", "reschedule"):
        scheduling = commands.add_parser(
            command_name,
            help=f"{command_name.title()} one job at an explicit UTC-aware time",
        )
        scheduling.add_argument("job_id")
        timing = scheduling.add_mutually_exclusive_group(required=True)
        timing.add_argument("--at", dest="run_at")
        timing.add_argument("--delay-seconds", type=int)
    cancel = commands.add_parser("cancel", help="Cancel one non-terminal job")
    cancel.add_argument("job_id")

    worker = top.add_parser("worker", help="Coordinate one local execution")
    worker_commands = worker.add_subparsers(dest="command", required=True)
    run_once = worker_commands.add_parser("run-once", help="Claim and process at most one job")
    run_once.add_argument(
        "--executor",
        choices=("local-success", "local-failure", "provider"),
        default="local-success",
        help="Executor mode; provider mode may consume configured provider usage",
    )

    provider = top.add_parser("provider", help="Inspect configured local providers")
    provider_commands = provider.add_subparsers(dest="command", required=True)
    provider_commands.add_parser("list", help="List canonically configured providers")
    provider_commands.add_parser(
        "status", help="Show observed local executable availability"
    )

    review = top.add_parser("review", help="Inspect persisted review decisions")
    review_commands = review.add_subparsers(dest="command", required=True)
    review_commands.add_parser("list", help="List normalized review decisions")
    review_show = review_commands.add_parser("show", help="Inspect one review decision")
    review_show.add_argument("review_id")

    approval = top.add_parser("approval", help="Manage scoped human approvals")
    approval_commands = approval.add_subparsers(dest="command", required=True)
    approval_list = approval_commands.add_parser(
        "list", help="List approval requests with pending requests first"
    )
    approval_list.add_argument(
        "--status", choices=("PENDING", "APPROVED", "REJECTED")
    )
    approval_show = approval_commands.add_parser(
        "show", help="Inspect bounded approval evidence"
    )
    approval_show.add_argument("approval_id")
    for decision in ("approve", "reject"):
        resolve = approval_commands.add_parser(
            decision, help=f"{decision.title()} one scoped approval request"
        )
        resolve.add_argument("approval_id")
        resolve.add_argument("--by", dest="decided_by", required=True)
        resolve.add_argument("--reason")

    scheduler = top.add_parser("scheduler", help="Manage deterministic local schedules")
    scheduler_commands = scheduler.add_subparsers(dest="command", required=True)
    schedule_create = scheduler_commands.add_parser(
        "create", help="Create and persist a schedule"
    )
    schedule_create.add_argument("--from", dest="input_path", type=Path, required=True)
    scheduler_commands.add_parser("list", help="List schedules")
    schedule_show = scheduler_commands.add_parser("show", help="Inspect one schedule")
    schedule_show.add_argument("schedule_id")
    schedule_enable = scheduler_commands.add_parser("enable", help="Enable a schedule")
    schedule_enable.add_argument("schedule_id")
    schedule_disable = scheduler_commands.add_parser("disable", help="Disable a schedule")
    schedule_disable.add_argument("schedule_id")
    scheduler_commands.add_parser("tick", help="Check and fire due schedules once")
    scheduler_commands.add_parser("status", help="Inspect scheduler and queue state")
    scheduler_commands.add_parser("stop", help="Request graceful scheduler shutdown")
    scheduler_commands.add_parser(
        "list-due", help="List due schedules and eligible queued jobs"
    )

    def add_loop_options(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--executor",
            choices=("local-success", "local-failure", "provider"),
            default="local-success",
        )
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--max-jobs-per-cycle", type=int, default=1)
        command.add_argument("--max-concurrent-jobs", type=int, default=1)
        command.add_argument("--max-provider-runs-per-cycle", type=int, default=1)
        command.add_argument("--max-provider-runs-per-day", type=int, default=25)
        command.add_argument("--lease-seconds", type=int, default=300)
        command.add_argument("--heartbeat-seconds", type=float, default=60.0)

    scheduler_run_once = scheduler_commands.add_parser(
        "run-once", help="Run one bounded scheduler cycle"
    )
    add_loop_options(scheduler_run_once)
    scheduler_run = scheduler_commands.add_parser(
        "run", help="Run bounded scheduler cycles until stopped"
    )
    add_loop_options(scheduler_run)
    scheduler_run.add_argument("--poll-seconds", type=float, default=5.0)
    scheduler_run.add_argument("--max-cycles", type=int)

    git = top.add_parser("git", help="Manage runtime-controlled Git change sets")
    git_commands = git.add_subparsers(dest="command", required=True)
    git_prepare = git_commands.add_parser(
        "prepare", help="Inspect and persist an exact reviewed Git change set"
    )
    git_prepare.add_argument("--job-id", required=True)
    git_prepare.add_argument("--execution-id", required=True)
    git_prepare.add_argument("--repository-root", type=Path, required=True)
    git_prepare.add_argument("--message", required=True)
    git_prepare.add_argument(
        "--dry-run",
        action="store_true",
        help="Persist preview evidence without approval, staging, or commit",
    )
    git_commands.add_parser("list", help="List controlled Git change sets")
    git_show = git_commands.add_parser("show", help="Inspect one Git change set")
    git_show.add_argument("change_set_id")
    git_commit = git_commands.add_parser(
        "commit", help="Stage and commit one exactly approved change set"
    )
    git_commit.add_argument("change_set_id")
    push_prepare = git_commands.add_parser(
        "push-prepare", help="Inspect and persist one exact remote push plan"
    )
    push_prepare.add_argument("--change-set-id", required=True)
    push_prepare.add_argument("--remote", default="origin")
    push_prepare.add_argument("--branch", required=True)
    push_prepare.add_argument("--dry-run", action="store_true")
    git_push = git_commands.add_parser(
        "push", help="Push one exactly approved verified commit"
    )
    git_push.add_argument("push_plan_id")
    pr_prepare = git_commands.add_parser(
        "pr-prepare", help="Inspect and persist one exact pull-request plan"
    )
    pr_prepare.add_argument("--push-evidence-id", required=True)
    pr_prepare.add_argument("--base", required=True)
    pr_prepare.add_argument("--title", required=True)
    pr_prepare.add_argument("--body-file", type=Path, required=True)
    pr_prepare.add_argument("--dry-run", action="store_true")
    pr_create = git_commands.add_parser(
        "pr-create", help="Create one exactly approved pull request"
    )
    pr_create.add_argument("pull_request_plan_id")

    remote = top.add_parser(
        "remote", help="Transport-independent Phase 7 remote command harness"
    )
    remote_commands = remote.add_subparsers(dest="command", required=True)

    def add_remote_actor(command: argparse.ArgumentParser) -> None:
        command.add_argument("--actor", required=True, help="Platform user ID")
        command.add_argument("--channel", default="local_test")
        command.add_argument("--command-id")
        command.add_argument("--idempotency-key")
        command.add_argument("--issued-at")
        command.add_argument("--received-at")

    add_remote_actor(remote_commands.add_parser("status", help="Remote status"))
    add_remote_actor(remote_commands.add_parser("jobs", help="Remote jobs list"))
    remote_show = remote_commands.add_parser("job-show", help="Remote job show")
    add_remote_actor(remote_show)
    remote_show.add_argument("job_id")
    add_remote_actor(
        remote_commands.add_parser("approvals", help="Remote pending approvals list")
    )
    for decision in ("approve", "reject"):
        remote_resolve = remote_commands.add_parser(
            decision, help=f"Remote {decision} for one exact approval"
        )
        add_remote_actor(remote_resolve)
        remote_resolve.add_argument("approval_id")
        remote_resolve.add_argument("--fingerprint", required=True)
    return parser


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read creation input: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError("Creation input must be a JSON object")
    return value


def read_bounded_text(path: Path, *, limit: int = 64 * 1024) -> str:
    try:
        if path.stat().st_size > limit:
            raise RuntimeError("Pull-request body exceeds the bounded limit")
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError(f"Could not read pull-request body: {error}") from error


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True))


def build_worker(
    executor_name: str,
    runtime: JobRuntime,
    executions: FileExecutionStore,
    approvals: Any,
    execution_root: Path,
    *,
    lease_seconds: int = 300,
) -> Worker:
    if executor_name == "provider":
        router = build_provider_router(repository_root())
        executor = ProviderExecutor(
            router=router,
            context_builder=ExecutionContextBuilder(repository_root()),
            artifact_store=FileProviderArtifactStore(
                execution_root / "provider-output"
            ),
            controlled_write_runtime=ControlledWriteRuntime(
                repository_root(),
                FileMutationArtifactStore(execution_root / "mutations"),
            ),
        )
        reviewer_runtime = build_reviewer_runtime(
            repository_root(), execution_root, router
        )
    else:
        executor_mode = "success" if executor_name == "local-success" else "failure"
        executor = LocalExecutor(executor_mode)
        reviewer_runtime = None
    return Worker(
        runtime=runtime,
        resolver=CanonicalReferenceResolver(),
        executor=executor,
        execution_store=executions,
        reviewer_runtime=reviewer_runtime,
        approval_runtime=approvals,
        lease_seconds=lease_seconds,
    )


def load_remote_config(path: Path) -> RemoteRuntimeConfig:
    if path.is_file():
        return RemoteRuntimeConfig.from_file(path)
    return RemoteRuntimeConfig.empty()


def remote_command_from_args(args: argparse.Namespace, clock: str) -> RemoteCommand:
    command_map = {
        "status": RemoteCommandType.STATUS,
        "jobs": RemoteCommandType.JOBS_LIST,
        "job-show": RemoteCommandType.JOB_SHOW,
        "approvals": RemoteCommandType.APPROVALS_LIST,
        "approve": RemoteCommandType.APPROVE,
        "reject": RemoteCommandType.REJECT,
    }
    command_type = command_map[args.command]
    target_id = args.job_id if args.command == "job-show" else None
    approval_id = args.approval_id if args.command in {"approve", "reject"} else None
    fingerprint = args.fingerprint if args.command in {"approve", "reject"} else None
    issued_at = args.issued_at or clock
    received_at = args.received_at or clock
    base = [
        args.channel,
        args.actor,
        command_type.value,
        target_id,
        approval_id,
        fingerprint,
        issued_at,
    ]
    stable = json.dumps(base, separators=(",", ":"), ensure_ascii=True)
    default_id = f"remote-{hashlib.sha256(stable.encode('utf-8')).hexdigest()[:32]}"
    return RemoteCommand(
        command_id=args.command_id or default_id,
        channel=args.channel,
        actor=args.actor,
        command_type=command_type,
        target_id=target_id,
        approval_id=approval_id,
        authorization_fingerprint=fingerprint,
        issued_at=issued_at,
        received_at=received_at,
        idempotency_key=args.idempotency_key or default_id,
        metadata={},
    )


def scheduled_time(runtime: JobRuntime, args: argparse.Namespace) -> str:
    if args.run_at is not None:
        return args.run_at
    if args.delay_seconds is None or args.delay_seconds < 0:
        raise RuntimeError("Delay seconds must be zero or greater")
    return runtime._format_timestamp(
        runtime._parse_timestamp(runtime.clock(), "runtime clock")
        + timedelta(seconds=args.delay_seconds)
    )


def run(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    try:
        runtime = JobRuntime(args.state_root)
        executions = FileExecutionStore(args.execution_root)
        reviews = FileReviewStore(args.execution_root / "reviews")
        approvals = build_approval_runtime(
            runtime,
            args.approval_root,
            execution_store=executions,
            review_store=reviews,
        )
        if args.resource == "remote":
            config = load_remote_config(args.remote_config)
            identity = config.identify(
                channel=args.channel,
                platform_user_id=args.actor,
            )
            command = remote_command_from_args(args, runtime.clock())
            service = RemoteCommandService(
                jobs=runtime,
                approvals=approvals,
                store=FileRemoteCommandStore(
                    args.remote_state_root,
                    max_records=config.max_audit_records,
                ),
                config=config,
                clock=runtime.clock,
            )
            result = service.handle(command, identity).to_dict()
        elif args.resource == "git":
            git_store = FileRemoteGitArtifactStore(args.git_state_root)
            git_runtime = GitRuntime(
                repository_root(),
                runtime,
                executions,
                reviews,
                FileMutationArtifactStore(args.execution_root / "mutations"),
                approvals,
                git_store,
            )
            if args.command == "prepare":
                result = git_runtime.prepare(
                    job_id=args.job_id,
                    execution_id=args.execution_id,
                    repository_root=args.repository_root,
                    commit_message=args.message,
                    dry_run=args.dry_run,
                )
            elif args.command == "list":
                result = git_runtime.list()
            elif args.command == "show":
                result = git_runtime.show(args.change_set_id)
            elif args.command == "commit":
                result = git_runtime.commit(args.change_set_id)
            elif args.command in {"push-prepare", "push", "pr-prepare", "pr-create"}:
                adapter = (
                    GitHubCliPullRequestAdapter()
                    if args.command in {"pr-prepare", "pr-create"}
                    else None
                )
                remote_runtime = RemoteGitRuntime(
                    git_runtime,
                    approvals,
                    git_store,
                    pull_request_adapter=adapter,
                )
                if args.command == "push-prepare":
                    result = remote_runtime.prepare_push(
                        change_set_id=args.change_set_id,
                        remote_name=args.remote,
                        remote_branch=args.branch,
                        dry_run=args.dry_run,
                    )
                elif args.command == "push":
                    result = remote_runtime.push(args.push_plan_id)
                elif args.command == "pr-prepare":
                    result = remote_runtime.prepare_pull_request(
                        push_evidence_id=args.push_evidence_id,
                        base_branch=args.base,
                        title=args.title,
                        body=read_bounded_text(args.body_file),
                        dry_run=args.dry_run,
                    )
                else:
                    result = remote_runtime.create_pull_request(
                        args.pull_request_plan_id
                    )
            else:
                raise GitRuntimeError(
                    "git_command_invalid", f"Unsupported Git command: {args.command}"
                )
        elif args.resource == "approval":
            if args.command == "list":
                result = approvals.list(args.status)
            elif args.command == "show":
                result = approvals.show(args.approval_id)
            elif args.command in {"approve", "reject"}:
                result = approvals.resolve(
                    args.approval_id,
                    decision=(
                        "APPROVED" if args.command == "approve" else "REJECTED"
                    ),
                    decided_by=args.decided_by,
                    reason=args.reason,
                )
            else:
                raise ApprovalRuntimeError(
                    f"Unsupported approval command: {args.command}"
                )
        elif args.resource == "review":
            if args.command == "list":
                result = [record["result"] for record in reviews.list()]
            elif args.command == "show":
                result = reviews.load(args.review_id)["result"]
            else:
                raise ReviewStoreError(f"Unsupported review command: {args.command}")
        elif args.resource == "provider":
            router = build_provider_router(repository_root())
            if args.command == "list":
                result = [
                    {
                        "provider_id": provider_id,
                        "adapter": router.configuration.cli_config(provider_id).adapter,
                        "execution_modes": list(
                            router.configuration.cli_config(
                                provider_id
                            ).supported_execution_modes
                        ),
                    }
                    for provider_id in router.configuration.provider_ids
                ]
            elif args.command == "status":
                availability = router.availability()
                result = [
                    {
                        "provider_id": provider_id,
                        "available": availability[provider_id].available,
                        "reason": availability[provider_id].reason,
                    }
                    for provider_id in router.configuration.provider_ids
                ]
            else:
                raise ProviderConfigError(
                    f"Unsupported provider command: {args.command}"
                )
        elif args.resource == "scheduler":
            schedules = ScheduleRuntime(args.schedule_root)
            if args.command == "create":
                result = schedules.create(read_json_object(args.input_path))
            elif args.command == "list":
                result = schedules.list()
            elif args.command == "show":
                result = schedules.show(args.schedule_id)
            elif args.command == "enable":
                result = schedules.enable(args.schedule_id)
            elif args.command == "disable":
                result = schedules.disable(args.schedule_id)
            elif args.command == "tick":
                result = schedules.tick(
                    CanonicalDispatchAdapter(
                        runtime,
                        approval_runtime=approvals,
                    )
                )
            elif args.command == "stop":
                state_store = FileSchedulerStateStore(args.scheduler_runtime_root)
                result = {
                    "stop_requested": state_store.request_stop(runtime.clock())
                }
            elif args.command in {"status", "list-due", "run-once", "run"}:
                executor_name = (
                    args.executor
                    if args.command in {"run-once", "run"}
                    else "local-success"
                )
                lease_seconds = (
                    args.lease_seconds
                    if args.command in {"run-once", "run"}
                    else 300
                )
                worker = build_worker(
                    executor_name,
                    runtime,
                    executions,
                    approvals,
                    args.execution_root,
                    lease_seconds=lease_seconds,
                )
                loop = SchedulerLoop(
                    schedules,
                    CanonicalDispatchAdapter(
                        runtime,
                        approval_runtime=approvals,
                    ),
                    runtime,
                    worker,
                    approvals,
                    FileSchedulerStateStore(args.scheduler_runtime_root),
                    config=(
                        SchedulerConfig(
                            poll_interval_seconds=(
                                args.poll_seconds if args.command == "run" else 5.0
                            ),
                            max_jobs_per_cycle=(
                                args.max_jobs_per_cycle
                                if args.command in {"run-once", "run"}
                                else 1
                            ),
                            max_concurrent_jobs=(
                                args.max_concurrent_jobs
                                if args.command in {"run-once", "run"}
                                else 1
                            ),
                            max_provider_runs_per_cycle=(
                                args.max_provider_runs_per_cycle
                                if args.command in {"run-once", "run"}
                                else 1
                            ),
                            max_provider_runs_per_day=(
                                args.max_provider_runs_per_day
                                if args.command in {"run-once", "run"}
                                else 25
                            ),
                            lease_seconds=lease_seconds,
                            heartbeat_interval_seconds=(
                                args.heartbeat_seconds
                                if args.command in {"run-once", "run"}
                                else 60.0
                            ),
                        )
                    ),
                    counts_as_provider_run=executor_name == "provider",
                )
                if args.command == "status":
                    result = loop.inspect()
                elif args.command == "list-due":
                    snapshot = loop.inspect()
                    result = {
                        "checked_at": snapshot["checked_at"],
                        "eligible_jobs": snapshot["eligible_jobs"],
                        "due_schedules": snapshot["due_schedules"],
                        "waiting_approvals": snapshot["waiting_approvals"],
                        "next_due_at": snapshot["next_due_at"],
                    }
                elif args.command == "run-once":
                    result = loop.run_once(dry_run=args.dry_run)
                else:
                    result = loop.run(
                        max_cycles=args.max_cycles,
                        dry_run=args.dry_run,
                    )
            else:
                raise ScheduleRuntimeError(f"Unsupported scheduler command: {args.command}")
        elif args.resource == "worker":
            worker = build_worker(
                args.executor,
                runtime,
                executions,
                approvals,
                args.execution_root,
            )
            result = worker.run_once().to_dict()
        elif args.command == "create":
            payload = read_json_object(args.input_path)
            if args.dry_run:
                payload["dry_run"] = True
                if payload.get("execution_mode") == "CONTROLLED_WRITE":
                    scope = payload.get("execution_scope")
                    if not isinstance(scope, dict):
                        raise RuntimeError(
                            "CONTROLLED_WRITE dry-run requires an execution scope"
                        )
                    payload["execution_scope"] = {**scope, "dry_run": True}
            result = runtime.create(payload)
        elif args.command == "enqueue":
            result = runtime.enqueue(args.job_id)
        elif args.command == "list":
            result = runtime.list(status=args.status)
        elif args.command == "show":
            result = runtime.show(args.job_id)
        elif args.command == "claim":
            result = runtime.claim()
        elif args.command == "transition":
            if args.status == "waiting_approval":
                approval_run = approvals.request_execution(
                    args.job_id,
                    reason="Job requires explicit approval before execution",
                )
                result = approval_run.job
            else:
                result = runtime.transition(args.job_id, args.status)
        elif args.command == "complete":
            result = runtime.complete(args.job_id)
        elif args.command == "fail":
            result = runtime.fail(
                args.job_id,
                code=args.code,
                message=args.message,
                retryable=not args.not_retryable,
            )
        elif args.command == "retry":
            result = runtime.retry(args.job_id)
        elif args.command == "schedule":
            result = runtime.schedule(args.job_id, scheduled_time(runtime, args))
        elif args.command == "reschedule":
            result = runtime.reschedule(args.job_id, scheduled_time(runtime, args))
        elif args.command == "cancel":
            result = runtime.transition(args.job_id, "cancelled")
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except (
        RuntimeError,
        ScheduleRuntimeError,
        ProviderConfigError,
        ReviewStoreError,
        ApprovalRuntimeError,
        ApprovalStoreError,
        GitRuntimeError,
        GitStoreError,
        RemoteGitRuntimeError,
        ForgeError,
        SchedulerLoopError,
        SchedulerStateStoreError,
        RemoteCommandError,
        RemoteCommandServiceError,
        RemoteStoreError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
