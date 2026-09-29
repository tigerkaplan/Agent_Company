"""Canonical contracts for bounded local write execution."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


EXECUTION_MODES = {"READ_ONLY", "CONTROLLED_WRITE"}
WRITE_MODES = {"CREATE_OR_MODIFY", "CREATE_MODIFY_DELETE"}

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _compare_ordinal = ctypes.WinDLL("kernel32", use_last_error=True).CompareStringOrdinal
    _compare_ordinal.argtypes = (wintypes.LPCWSTR, ctypes.c_int, wintypes.LPCWSTR,
                                ctypes.c_int, wintypes.BOOL)
    _compare_ordinal.restype = ctypes.c_int


class ScopeContractError(ValueError):
    """Raised when a controlled-write scope is invalid or unsafe."""

    def __init__(self, message: str, code: str = "write_scope_invalid") -> None:
        super().__init__(message)
        self.code = code


def normalize_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ScopeContractError("Execution scope paths must be non-empty and trimmed")
    if len(value) > 512:
        raise ScopeContractError("Execution scope path exceeds the bounded length")
    candidate = value.replace("\\", "/")
    if candidate.startswith("/") or "//" in candidate or candidate.endswith("/"):
        raise ScopeContractError("Execution scope paths must be normalized relative paths")
    path = PurePosixPath(candidate)
    if candidate in {".", ".."} or any(part in {"", ".", ".."} for part in path.parts):
        raise ScopeContractError("Execution scope paths cannot contain traversal segments")
    windows_reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if not path.parts or any(
        ":" in part
        or any(ord(character) < 32 for character in part)
        or part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in windows_reserved
        for part in path.parts
    ):
        raise ScopeContractError(
            "Execution scope path uses unsupported Windows or control syntax"
        )
    normalized = path.as_posix()
    if normalized != candidate:
        raise ScopeContractError("Execution scope paths must use canonical separators")
    return normalized


def scope_path_key(value: str) -> str:
    """A conservative namespace key, never Unicode linguistic equivalence."""
    normalized = normalize_relative_path(value)
    # Windows ordinarily ignores ASCII case; POSIX namespaces need not. Do not
    # casefold/lower Unicode: distinct names (e.g. straße/strasse) must survive.
    if os.name == "nt":
        return normalized.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
    return normalized


def _scope_names_equal(left: str, right: str) -> bool:
    if left == right:
        return True
    if os.name != "nt":
        return False
    # The OS ordinal comparison preserves namespace spelling/length rather than
    # applying linguistic Unicode casefold expansions such as sharp-s -> ss.
    result = _compare_ordinal(left, -1, right, -1, True)
    if result == 0:
        raise ScopeContractError("Filesystem scope names could not be compared")
    return result == 2  # CSTR_EQUAL


def scope_path_contains(boundary: str, relative: str, *, project_root: str,
                        case_aliases_require_identity: bool = True) -> bool:
    """Compare path components without expanding filesystem authority.

    Exact spelling works even for not-yet-created paths. Alternate ordinal case
    on Windows is accepted only when the filesystem proves the boundary is the
    same object; case-sensitive directories and ambiguous future names deny.
    """
    boundary = normalize_relative_path(boundary)
    relative = normalize_relative_path(relative)
    boundary_parts, relative_parts = boundary.split("/"), relative.split("/")
    if len(relative_parts) < len(boundary_parts):
        return False
    prefix = "/".join(relative_parts[:len(boundary_parts)])
    if prefix == boundary:
        return True
    if not _scope_names_equal(prefix, boundary):
        return False
    if not case_aliases_require_identity:
        # Negative scope may conservatively reject ambiguous future aliases;
        # absence of a forbidden file must never make its case alias writable.
        return True
    try:
        return (Path(project_root) / boundary).samefile(Path(project_root) / prefix)
    except OSError:
        return False


@dataclass(frozen=True)
class ExecutionScope:
    project_root: str
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    write_mode: str
    max_changed_files: int
    max_artifact_bytes: int
    allow_tests: bool
    allow_git_reads: bool
    allow_protected_paths: bool
    dry_run: bool = False

    def __post_init__(self) -> None:
        root = Path(self.project_root)
        if not root.is_absolute():
            raise ScopeContractError("Controlled-write project_root must be absolute")
        if self.write_mode not in WRITE_MODES:
            raise ScopeContractError("Controlled-write write_mode is not canonical")
        if not 1 <= self.max_changed_files <= 100:
            raise ScopeContractError("max_changed_files must be between 1 and 100")
        if not 1024 <= self.max_artifact_bytes <= 16 * 1024 * 1024:
            raise ScopeContractError(
                "max_artifact_bytes must be between 1024 and 16777216"
            )
        if not self.allowed_paths or len(self.allowed_paths) > 64:
            raise ScopeContractError("allowed_paths must contain between 1 and 64 paths")
        if len(self.forbidden_paths) > 64:
            raise ScopeContractError("forbidden_paths cannot exceed 64 paths")
        normalized_allowed = tuple(normalize_relative_path(item) for item in self.allowed_paths)
        normalized_forbidden = tuple(
            normalize_relative_path(item) for item in self.forbidden_paths
        )
        if any(_scope_names_equal(left, right) for index, left in enumerate(normalized_allowed)
               for right in normalized_allowed[index + 1:]):
            raise ScopeContractError("allowed_paths contains duplicate paths")
        if any(_scope_names_equal(left, right) for index, left in enumerate(normalized_forbidden)
               for right in normalized_forbidden[index + 1:]):
            raise ScopeContractError("forbidden_paths contains duplicate paths")
        object.__setattr__(self, "allowed_paths", normalized_allowed)
        object.__setattr__(self, "forbidden_paths", normalized_forbidden)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionScope":
        expected = {
            "project_root",
            "allowed_paths",
            "forbidden_paths",
            "write_mode",
            "max_changed_files",
            "max_artifact_bytes",
            "allow_tests",
            "allow_git_reads",
            "allow_protected_paths",
        }
        if not isinstance(value, dict) or set(value) not in (expected, expected | {"dry_run"}):
            raise ScopeContractError("Execution scope has missing or unexpected fields")
        if not isinstance(value["project_root"], str):
            raise ScopeContractError("Execution scope project_root must be a string")
        if not isinstance(value["allowed_paths"], list) or not all(
            isinstance(item, str) for item in value["allowed_paths"]
        ):
            raise ScopeContractError("Execution scope allowed_paths must contain strings")
        if not isinstance(value["forbidden_paths"], list) or not all(
            isinstance(item, str) for item in value["forbidden_paths"]
        ):
            raise ScopeContractError("Execution scope forbidden_paths must contain strings")
        if not isinstance(value["write_mode"], str):
            raise ScopeContractError("Execution scope write_mode must be a string")
        if any(
            not isinstance(value[name], int) or isinstance(value[name], bool)
            for name in ("max_changed_files", "max_artifact_bytes")
        ):
            raise ScopeContractError("Execution scope limits must be integers")
        if any(
            not isinstance(value[name], bool)
            for name in ("allow_tests", "allow_git_reads", "allow_protected_paths")
        ):
            raise ScopeContractError("Execution scope permission flags must be booleans")
        if not isinstance(value.get("dry_run", False), bool):
            raise ScopeContractError("Execution scope dry_run must be a boolean")
        return cls(
            project_root=value["project_root"],
            allowed_paths=tuple(value["allowed_paths"]),
            forbidden_paths=tuple(value["forbidden_paths"]),
            write_mode=value["write_mode"],
            max_changed_files=value["max_changed_files"],
            max_artifact_bytes=value["max_artifact_bytes"],
            allow_tests=value["allow_tests"],
            allow_git_reads=value["allow_git_reads"],
            allow_protected_paths=value["allow_protected_paths"],
            dry_run=value.get("dry_run", False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "write_mode": self.write_mode,
            "max_changed_files": self.max_changed_files,
            "max_artifact_bytes": self.max_artifact_bytes,
            "allow_tests": self.allow_tests,
            "allow_git_reads": self.allow_git_reads,
            "allow_protected_paths": self.allow_protected_paths,
            "dry_run": self.dry_run,
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def permits(self, relative: str) -> bool:
        relative = normalize_relative_path(relative)
        allowed = any(
            scope_path_contains(item, relative, project_root=self.project_root)
            for item in self.allowed_paths
        )
        forbidden = any(
            scope_path_contains(item, relative, project_root=self.project_root,
                                case_aliases_require_identity=False)
            for item in self.forbidden_paths
        )
        return allowed and not forbidden
