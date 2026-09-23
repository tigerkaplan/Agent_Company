"""Narrow forge adapters for pull-request inspection and creation only."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from runtime.providers.adapters import bound_text, sanitize_provider_text


class ForgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PullRequestState:
    number: int
    url: str
    repository_slug: str
    head_branch: str
    base_branch: str
    head_commit: str
    title: str


class PullRequestAdapter(Protocol):
    def inspect(
        self, repository_slug: str, head_branch: str, base_branch: str
    ) -> PullRequestState | None: ...

    def create(
        self,
        repository_slug: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PullRequestState: ...


class GitHubCliPullRequestAdapter:
    """Fixed-command GitHub CLI bridge with no merge/update/delete methods."""

    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        executable = which("gh")
        if executable is None or Path(executable).name.casefold() not in {"gh", "gh.exe"}:
            raise ForgeError("forge_unavailable", "Allowlisted GitHub CLI executable was not found")
        self.executable = str(Path(executable).resolve())
        self.runner = runner

    def inspect(
        self, repository_slug: str, head_branch: str, base_branch: str
    ) -> PullRequestState | None:
        result = self._run(
            [
                "pr",
                "list",
                "--repo",
                repository_slug,
                "--head",
                head_branch,
                "--base",
                base_branch,
                "--state",
                "open",
                "--limit",
                "2",
                "--json",
                "number,url,headRefName,baseRefName,headRefOid,title",
            ]
        )
        values = self._json(result)
        if not isinstance(values, list) or len(values) > 1:
            raise ForgeError("pull_request_state_ambiguous", "Expected zero or one open pull request")
        if not values:
            return None
        return self._state(repository_slug, values[0])

    def create(
        self,
        repository_slug: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> PullRequestState:
        result = self._run(
            [
                "pr",
                "create",
                "--repo",
                repository_slug,
                "--head",
                head_branch,
                "--base",
                base_branch,
                "--title",
                title,
                "--body-file",
                "-",
            ],
            input_text=body,
        )
        url = result.stdout.strip()
        if not url.startswith("https://github.com/"):
            raise ForgeError("pull_request_create_failed", "GitHub CLI returned an invalid pull-request URL")
        view = self._run(
            [
                "pr",
                "view",
                url,
                "--repo",
                repository_slug,
                "--json",
                "number,url,headRefName,baseRefName,headRefOid,title",
            ]
        )
        value = self._json(view)
        if not isinstance(value, dict):
            raise ForgeError("pull_request_evidence_invalid", "GitHub CLI returned invalid pull-request evidence")
        return self._state(repository_slug, value)

    def _run(
        self, arguments: list[str], *, input_text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["GH_PROMPT_DISABLED"] = "1"
        try:
            result = self.runner(
                [self.executable, *arguments],
                input=input_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                shell=False,
                env=env,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ForgeError("forge_process_failed", str(error)) from error
        if result.returncode != 0:
            message = bound_text(sanitize_provider_text(result.stderr or result.stdout), 2000)
            raise ForgeError("forge_command_failed", message or "GitHub CLI command failed")
        return result

    @staticmethod
    def _json(result: subprocess.CompletedProcess[str]) -> Any:
        if len(result.stdout.encode("utf-8")) > 128 * 1024:
            raise ForgeError("forge_response_invalid", "GitHub CLI response exceeds the bounded limit")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ForgeError("forge_response_invalid", "GitHub CLI returned invalid JSON") from error

    @staticmethod
    def _state(repository_slug: str, value: dict[str, Any]) -> PullRequestState:
        try:
            state = PullRequestState(
                number=int(value["number"]),
                url=str(value["url"]),
                repository_slug=repository_slug,
                head_branch=str(value["headRefName"]),
                base_branch=str(value["baseRefName"]),
                head_commit=str(value["headRefOid"]),
                title=str(value["title"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ForgeError("pull_request_evidence_invalid", "Pull-request metadata is incomplete") from error
        expected_url = f"https://github.com/{repository_slug}/pull/{state.number}"
        if state.number < 1 or state.url != expected_url:
            raise ForgeError("pull_request_evidence_invalid", "Pull-request metadata is invalid")
        return state
