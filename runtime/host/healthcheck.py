"""Read-only service-local healthcheck for Phase 8D containers."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from runtime.host.config import HostConfig, HostConfigError
from runtime.host.paths import StatePathError, StatePaths
from runtime.host.processes import HostProcessController, HostProcessError, ProcessType


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read one host process health state")
    parser.add_argument("process", choices=tuple(item.value for item in ProcessType))
    args = parser.parse_args(arguments)
    process_type = ProcessType(args.process)

    try:
        configured = os.environ.get("AGENT_COMPANY_HOST_CONFIG")
        config = (
            HostConfig.from_file(Path(configured))
            if configured
            else HostConfig.local_default()
        )
        paths = StatePaths.resolve(repository_root(), config, environment=os.environ)
        status = HostProcessController(
            config,
            paths,
            environment=dict(os.environ),
        ).status()
        process = next(
            item
            for item in status["processes"]
            if item["process_type"] == process_type.value
        )
    except (
        HostConfigError,
        HostProcessError,
        StatePathError,
        KeyError,
        OSError,
        StopIteration,
        TypeError,
        ValueError,
    ):
        print(
            json.dumps(
                {"healthy": False, "process": process_type.value, "reason": "unavailable"},
                sort_keys=True,
            )
        )
        return 1

    healthy = bool(
        process["enabled"]
        and process["state"] == "RUNNING"
        and process["singleton_lock_held"]
        and not process["heartbeat_stale"]
        and not process["stale_record"]
    )
    print(
        json.dumps(
            {
                "healthy": healthy,
                "process": process_type.value,
                "state": process["state"],
                "singleton_lock_held": process["singleton_lock_held"],
                "heartbeat_stale": process["heartbeat_stale"],
                "stale_record": process["stale_record"],
            },
            sort_keys=True,
        )
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(run())
