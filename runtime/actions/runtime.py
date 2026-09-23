"""Execute provider writes in staging, validate them, then apply bounded changes."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.actions.authorization import authorization_fingerprint
from runtime.actions.models import ExecutionScope, ScopeContractError
from runtime.actions.store import FileMutationArtifactStore
from runtime.execution.models import ExecutionRequest
from runtime.providers.models import ProviderExecutionResult


@dataclass(frozen=True)
class ControlledWriteOutcome:
    provider_result: ProviderExecutionResult
    artifact_ref: dict[str, Any]


class ControlledWriteRuntime:
    """Keep provider writes off the target until independently validated."""

    _HARD_PROTECTED_PARTS = {
        ".git",
        ".ssh",
        ".aws",
        ".codex",
        ".claude",
        ".config",
        "secrets",
        "credentials",
    }
    _SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
    _AGENT_COMPANY_PROTECTED = (
        "CONSTITUTION.md",
        "AGENTS.md",
        "orchestrator/approvals",
        "orchestrator/routing",
        "providers",
        "runtime/state",
    )

    def __init__(
        self,
        repository_root: Path,
        store: FileMutationArtifactStore,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.store = store

    def execute(
        self,
        request: ExecutionRequest,
        context: Any,
        adapter: Any,
    ) -> ControlledWriteOutcome:
        try:
            scope = ExecutionScope.from_dict(request.execution_scope or {})
        except ScopeContractError as error:
            return self._rejected(request, None, error.code, str(error), ())
        if scope.dry_run != request.dry_run:
            return self._rejected(
                request,
                scope,
                "write_scope_invalid",
                "Controlled-write scope dry_run does not match the execution request",
                (),
            )

        if (
            request.approval_status != "approved"
            or not request.authorization_fingerprint
            or request.authorization_fingerprint != authorization_fingerprint(request.to_dict())
        ):
            return self._rejected(
                request,
                scope,
                "write_not_authorized",
                "Controlled write is not bound to the current approved job scope",
                (),
            )

        try:
            target_root = Path(scope.project_root).resolve(strict=True)
        except OSError:
            return self._rejected(
                request,
                scope,
                "write_scope_invalid",
                "Controlled-write project root does not exist",
                (),
            )
        if not target_root.is_dir():
            return self._rejected(
                request,
                scope,
                "write_scope_invalid",
                "Controlled-write project root is not a directory",
                (),
            )
        project_violation = self._project_target_violation(request, target_root)
        if project_violation is not None:
            return self._rejected(
                request,
                scope,
                "write_scope_invalid",
                project_violation,
                (),
            )
        if (
            target_root == self.repository_root
            and scope.allow_protected_paths
            and (
                request.capability != "software_implementation"
                or request.risk_level != "approval_required"
            )
        ):
            return self._rejected(
                request,
                scope,
                "protected_path_violation",
                "Agent Company control surfaces require approved software implementation",
                (),
            )

        initial_violations = self._scope_violations(scope, target_root)
        if initial_violations:
            first = initial_violations[0]
            return self._rejected(
                request,
                scope,
                str(first["code"]),
                str(first["message"]),
                tuple(initial_violations),
            )

        target_integrity_before: dict[str, Any] | None = None
        if request.dry_run:
            try:
                target_integrity_before = self._target_integrity_snapshot(target_root)
            except (OSError, ScopeContractError) as error:
                return self._rejected(
                    request,
                    scope,
                    "target_integrity_unverified",
                    f"Dry-run target integrity could not be established: {error}",
                    (),
                )

        with tempfile.TemporaryDirectory(prefix="agent-company-write-") as temporary:
            temporary_root = Path(temporary).resolve()
            workspace = temporary_root / "workspace"
            baseline = temporary_root / "baseline"
            workspace.mkdir()
            try:
                self._stage(scope, target_root, workspace)
                shutil.copytree(workspace, baseline)
                before = self._snapshot(baseline)
            except ScopeContractError as error:
                return self._rejected(request, scope, error.code, str(error), ())

            provider_result = adapter.execute(
                request, context, working_directory=workspace
            )
            after, link_violations = self._snapshot_with_violations(workspace)
            baseline_after, baseline_violations = self._snapshot_with_violations(baseline)
            created, modified, deleted = self._changes(before, after)
            changed = tuple(sorted((*created, *modified, *deleted), key=str.casefold))
            violations = [*link_violations, *baseline_violations]
            if baseline_after != before:
                violations.append(
                    {
                        "code": "mutation_scope_violation",
                        "path": None,
                        "message": "Runtime-owned mutation baseline changed during execution",
                    }
                )
            violations.extend(self._mutation_violations(scope, changed, deleted))
            diff = (
                self._diff(workspace, baseline, created, modified, deleted)
                if baseline_after == before and not baseline_violations
                else ""
            )

            changed_bytes = sum(after[path][1] for path in (*created, *modified))
            changed_bytes += sum(before[path][1] for path in deleted)
            if changed_bytes > scope.max_artifact_bytes:
                violations.append(
                    {
                        "code": "mutation_scope_violation",
                        "path": None,
                        "message": "Changed content exceeds max_artifact_bytes",
                    }
                )

            apply_status = "not_applied"
            failure_code: str | None = None
            failure_message: str | None = None
            target_post: dict[str, str | None] = {}
            target_integrity_after: dict[str, Any] | None = None
            if request.dry_run:
                try:
                    target_integrity_after = self._target_integrity_snapshot(target_root)
                except (OSError, ScopeContractError):
                    violations.append(
                        {
                            "code": "target_integrity_unverified",
                            "path": None,
                            "message": "Dry-run target integrity could not be verified after execution",
                        }
                    )
                if (
                    target_integrity_before is not None
                    and target_integrity_after is not None
                    and target_integrity_before["fingerprint"]
                    != target_integrity_after["fingerprint"]
                ):
                    violations.append(
                        {
                            "code": "target_integrity_violation",
                            "path": None,
                            "message": "Target project changed during dry-run execution",
                        }
                    )
            if provider_result.status != "succeeded":
                failure_code = provider_result.error_category or "controlled_execution_failed"
                failure_message = provider_result.error_message or "Provider execution failed"
            elif violations:
                failure_code = str(violations[0]["code"])
                failure_message = str(violations[0]["message"])
            elif not changed:
                failure_code = "mutation_evidence_missing"
                failure_message = "Controlled-write execution produced no file mutation"
            elif request.dry_run:
                apply_status = "preview"
            else:
                try:
                    target_post = self._apply(
                        scope,
                        target_root,
                        workspace,
                        before,
                        created,
                        modified,
                        deleted,
                    )
                    apply_status = "applied"
                except ScopeContractError as error:
                    failure_code = error.code
                    failure_message = str(error)
                    violations.append(
                        {"code": error.code, "path": None, "message": str(error)}
                    )
                except OSError:
                    failure_code = "controlled_execution_failed"
                    failure_message = "Validated mutation could not be applied atomically"
                    apply_status = "rolled_back"

            evidence = self._evidence(
                request,
                scope,
                created,
                modified,
                deleted,
                before,
                after,
                target_post,
                target_integrity_before,
                target_integrity_after,
                getattr(adapter, "provider_id", None),
                provider_result.requested_sandbox_mode,
                provider_result.effective_sandbox_mode,
                violations,
                apply_status,
            )
            artifact_ref = self.store.create(
                request.execution_id,
                evidence,
                diff,
                max_diff_bytes=scope.max_artifact_bytes,
            )
            if failure_code is not None:
                provider_result = ProviderExecutionResult(
                    status="failed",
                    stdout=provider_result.stdout,
                    stderr=provider_result.stderr,
                    exit_code=provider_result.exit_code,
                    error_category=failure_code,
                    error_message=failure_message,
                    requested_sandbox_mode=provider_result.requested_sandbox_mode,
                    effective_sandbox_mode=provider_result.effective_sandbox_mode,
                )
            return ControlledWriteOutcome(provider_result, artifact_ref)

    def _rejected(
        self,
        request: ExecutionRequest,
        scope: ExecutionScope | None,
        code: str,
        message: str,
        violations: tuple[dict[str, Any], ...],
    ) -> ControlledWriteOutcome:
        evidence = {
            "schema_version": 1,
            "execution_id": request.execution_id,
            "job_id": request.job_id,
            "execution_mode": "CONTROLLED_WRITE",
            "dry_run": request.dry_run,
            "authorization_required": True,
            "authorized_project_root": scope.project_root if scope else None,
            "allowed_paths": list(scope.allowed_paths) if scope else [],
            "provider_eligibility": {
                "requested_provider": request.provider,
                "executing_provider": None,
                "status": "not_executed",
            },
            "requested_sandbox_mode": None,
            "effective_sandbox_mode": None,
            "scope_fingerprint": scope.fingerprint if scope else None,
            "created_files": [],
            "modified_files": [],
            "deleted_files": [],
            "changed_files": [],
            "proposed_created_files": [],
            "proposed_modified_files": [],
            "proposed_deleted_files": [],
            "proposed_changed_files": [],
            "applied_changed_files": [],
            "mutation_kind": "none",
            "scope_violations": list(violations),
            "pre_fingerprints": {},
            "post_fingerprints": {},
            "target_post_fingerprints": {},
            "apply_status": "not_applied",
            "target_integrity": {
                "before": None,
                "after": None,
                "unchanged": None,
            },
            "validation": {"status": "not_configured", "commands": []},
        }
        ref = self.store.create(
            request.execution_id,
            evidence,
            "",
            max_diff_bytes=scope.max_artifact_bytes if scope else 1024,
        )
        return ControlledWriteOutcome(
            ProviderExecutionResult(
                status="failed",
                stdout="",
                stderr="",
                exit_code=None,
                error_category=code,
                error_message=message,
            ),
            ref,
        )

    def _scope_violations(
        self, scope: ExecutionScope, target_root: Path
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        for relative in scope.allowed_paths:
            try:
                self._target_path(target_root, relative)
            except ScopeContractError as error:
                violations.append(
                    {"code": error.code, "path": relative, "message": str(error)}
                )
                continue
            protection = self._protection(relative, target_root)
            if protection == "hard" or (
                protection == "agent_company" and not scope.allow_protected_paths
            ):
                violations.append(
                    {
                        "code": "protected_path_violation",
                        "path": relative,
                        "message": "Execution scope includes a protected path",
                    }
                )
        return violations

    def _project_target_violation(
        self, request: ExecutionRequest, target_root: Path
    ) -> str | None:
        if request.project_id is None:
            return None
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", request.project_id) is None:
            return "Controlled-write project_id is not a safe canonical identifier"
        metadata = (
            self.repository_root
            / "shared"
            / "projects"
            / request.project_id
            / "metadata.yaml"
        )
        if not metadata.is_file():
            return "Controlled-write project has no canonical root metadata"
        root_value = None
        try:
            for line in metadata.read_text(encoding="utf-8").splitlines():
                match = re.fullmatch(r"root_path:\s*(\S.*)", line)
                if match:
                    root_value = match.group(1).strip().strip("\"'")
                    break
        except OSError:
            return "Controlled-write project root metadata could not be read"
        if not root_value:
            return "Controlled-write project metadata has no root_path"
        try:
            canonical_root = Path(root_value).resolve(strict=True)
        except OSError:
            return "Controlled-write canonical project root does not exist"
        if canonical_root != target_root:
            return "Controlled-write scope does not match canonical project root"
        return None

    def _stage(self, scope: ExecutionScope, target_root: Path, workspace: Path) -> None:
        for relative in scope.allowed_paths:
            source = self._target_path(target_root, relative)
            destination = workspace / Path(relative)
            if not source.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                continue
            self._copy_entry(source, destination, target_root, scope)

    def _copy_entry(
        self,
        source: Path,
        destination: Path,
        target_root: Path,
        scope: ExecutionScope,
    ) -> None:
        relative = source.relative_to(target_root).as_posix()
        protection = self._protection(relative, target_root)
        if protection == "hard" or (
            protection == "agent_company" and not scope.allow_protected_paths
        ):
            return
        if self._is_link(source):
            raise ScopeContractError(
                f"Authorized path traverses a symlink or junction: {relative}",
                "path_escape_attempt",
            )
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return
        if not source.is_dir():
            raise ScopeContractError(f"Unsupported filesystem entry: {relative}")
        destination.mkdir(parents=True, exist_ok=True)
        with os.scandir(source) as entries:
            for entry in entries:
                self._copy_entry(
                    Path(entry.path), destination / entry.name, target_root, scope
                )

    def _snapshot(self, root: Path) -> dict[str, tuple[str, int]]:
        snapshot, violations = self._snapshot_with_violations(root)
        if violations:
            raise ScopeContractError(
                str(violations[0]["message"]), str(violations[0]["code"])
            )
        return snapshot

    def _snapshot_with_violations(
        self, root: Path
    ) -> tuple[dict[str, tuple[str, int]], list[dict[str, Any]]]:
        snapshot: dict[str, tuple[str, int]] = {}
        violations: list[dict[str, Any]] = []

        def visit(directory: Path) -> None:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    if entry.is_symlink() or self._is_link(path):
                        violations.append(
                            {
                                "code": "path_escape_attempt",
                                "path": relative,
                                "message": "Mutation workspace contains a symlink or junction",
                            }
                        )
                    elif entry.is_dir(follow_symlinks=False):
                        visit(path)
                    elif entry.is_file(follow_symlinks=False):
                        snapshot[relative] = self._fingerprint(path)
                    else:
                        violations.append(
                            {
                                "code": "mutation_scope_violation",
                                "path": relative,
                                "message": "Mutation workspace contains an unsupported entry",
                            }
                        )

        visit(root)
        return snapshot, violations

    @staticmethod
    def _changes(
        before: dict[str, tuple[str, int]], after: dict[str, tuple[str, int]]
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        created = tuple(sorted(set(after) - set(before), key=str.casefold))
        deleted = tuple(sorted(set(before) - set(after), key=str.casefold))
        modified = tuple(
            sorted(
                (path for path in set(before) & set(after) if before[path] != after[path]),
                key=str.casefold,
            )
        )
        return created, modified, deleted

    def _mutation_violations(
        self,
        scope: ExecutionScope,
        changed: tuple[str, ...],
        deleted: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        violations: list[dict[str, Any]] = []
        if len(changed) > scope.max_changed_files:
            violations.append(
                {
                    "code": "mutation_scope_violation",
                    "path": None,
                    "message": "Mutation exceeds max_changed_files",
                }
            )
        for relative in changed:
            if not scope.permits(relative):
                violations.append(
                    {
                        "code": "mutation_scope_violation",
                        "path": relative,
                        "message": "Mutation is outside allowed_paths or inside forbidden_paths",
                    }
                )
            protection = self._protection(relative, Path(scope.project_root).resolve())
            if protection == "hard" or (
                protection == "agent_company" and not scope.allow_protected_paths
            ):
                violations.append(
                    {
                        "code": "protected_path_violation",
                        "path": relative,
                        "message": "Mutation targets a protected path",
                    }
                )
        if deleted and scope.write_mode != "CREATE_MODIFY_DELETE":
            violations.append(
                {
                    "code": "mutation_scope_violation",
                    "path": deleted[0],
                    "message": "Deletion is not allowed by write_mode",
                }
            )
        return violations

    def _apply(
        self,
        scope: ExecutionScope,
        target_root: Path,
        workspace: Path,
        before: dict[str, tuple[str, int]],
        created: tuple[str, ...],
        modified: tuple[str, ...],
        deleted: tuple[str, ...],
    ) -> dict[str, str | None]:
        changed = (*created, *modified, *deleted)
        backups: dict[str, bytes | None] = {}
        for relative in changed:
            target = self._target_path(target_root, relative)
            if self._is_link(target) or any(
                self._is_link(parent)
                for parent in target.parents
                if parent != target_root and target_root in parent.parents
            ):
                raise ScopeContractError(
                    f"Target path traverses a symlink or junction: {relative}",
                    "path_escape_attempt",
                )
            if relative in created:
                if target.exists():
                    raise ScopeContractError(
                        "Target changed after staging; refusing stale mutation",
                        "validation_failed",
                    )
                backups[relative] = None
            else:
                if not target.is_file() or self._fingerprint(target) != before[relative]:
                    raise ScopeContractError(
                        "Target changed after staging; refusing stale mutation",
                        "validation_failed",
                    )
                backups[relative] = target.read_bytes()

        applied: list[str] = []
        try:
            for relative in (*created, *modified):
                target = self._target_path(target_root, relative)
                source = workspace / Path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_write(target, source.read_bytes())
                applied.append(relative)
            for relative in deleted:
                target = self._target_path(target_root, relative)
                target.unlink()
                applied.append(relative)
        except OSError:
            for relative in reversed(applied):
                target = self._target_path(target_root, relative)
                original = backups[relative]
                if original is None:
                    if target.exists() and target.is_file():
                        target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    self._atomic_write(target, original)
            raise

        result: dict[str, str | None] = {}
        for relative in changed:
            target = self._target_path(target_root, relative)
            result[relative] = self._fingerprint(target)[0] if target.is_file() else None
        return result

    def _diff(
        self,
        workspace: Path,
        baseline: Path,
        created: tuple[str, ...],
        modified: tuple[str, ...],
        deleted: tuple[str, ...],
    ) -> str:
        sections: list[str] = []
        for relative in (*created, *modified, *deleted):
            before_path = baseline / Path(relative)
            after_path = workspace / Path(relative)
            before = b"" if relative in created else before_path.read_bytes()
            after = b"" if relative in deleted else after_path.read_bytes()
            try:
                before_lines = before.decode("utf-8").splitlines(keepends=True)
                after_lines = after.decode("utf-8").splitlines(keepends=True)
            except UnicodeDecodeError:
                sections.append(f"Binary files differ: {relative}\n")
                continue
            sections.extend(
                difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
            )
        return "".join(sections)

    @staticmethod
    def _evidence(
        request: ExecutionRequest,
        scope: ExecutionScope,
        created: tuple[str, ...],
        modified: tuple[str, ...],
        deleted: tuple[str, ...],
        before: dict[str, tuple[str, int]],
        after: dict[str, tuple[str, int]],
        target_post: dict[str, str | None],
        target_integrity_before: dict[str, Any] | None,
        target_integrity_after: dict[str, Any] | None,
        executing_provider: str | None,
        requested_sandbox_mode: str | None,
        effective_sandbox_mode: str | None,
        violations: list[dict[str, Any]],
        apply_status: str,
    ) -> dict[str, Any]:
        changed = tuple(sorted((*created, *modified, *deleted), key=str.casefold))
        return {
            "schema_version": 1,
            "execution_id": request.execution_id,
            "job_id": request.job_id,
            "execution_mode": "CONTROLLED_WRITE",
            "dry_run": request.dry_run,
            "authorization_required": True,
            "authorized_project_root": scope.project_root,
            "allowed_paths": list(scope.allowed_paths),
            "provider_eligibility": {
                "requested_provider": request.provider,
                "executing_provider": executing_provider,
                "status": "selected_by_canonical_router",
            },
            "requested_sandbox_mode": requested_sandbox_mode,
            "effective_sandbox_mode": effective_sandbox_mode,
            "scope_fingerprint": scope.fingerprint,
            "created_files": list(created),
            "modified_files": list(modified),
            "deleted_files": list(deleted),
            "changed_files": list(changed),
            "proposed_created_files": list(created),
            "proposed_modified_files": list(modified),
            "proposed_deleted_files": list(deleted),
            "proposed_changed_files": list(changed),
            "applied_changed_files": list(changed) if apply_status == "applied" else [],
            "mutation_kind": (
                "proposed"
                if apply_status == "preview"
                else "applied"
                if apply_status == "applied"
                else "none"
            ),
            "scope_violations": violations,
            "pre_fingerprints": {
                path: before[path][0] if path in before else None for path in changed
            },
            "post_fingerprints": {
                path: after[path][0] if path in after else None for path in changed
            },
            "target_post_fingerprints": target_post,
            "apply_status": apply_status,
            "target_integrity": {
                "before": target_integrity_before,
                "after": target_integrity_after,
                "unchanged": (
                    target_integrity_before is not None
                    and target_integrity_after is not None
                    and target_integrity_before["fingerprint"]
                    == target_integrity_after["fingerprint"]
                )
                if request.dry_run
                else None,
            },
            "validation": {"status": "not_configured", "commands": []},
        }

    def _target_integrity_snapshot(self, root: Path) -> dict[str, Any]:
        digest = hashlib.sha256()
        file_count = 0
        directory_count = 0
        link_count = 0
        total_bytes = 0

        def record(kind: str, relative: str, value: str = "") -> None:
            digest.update(f"{kind}\0{relative}\0{value}\n".encode("utf-8"))

        def visit(directory: Path) -> None:
            nonlocal file_count, directory_count, link_count, total_bytes
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda item: item.name.casefold())
            for entry in ordered:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if entry.is_symlink() or self._is_link(path):
                    link_count += 1
                    try:
                        destination = os.readlink(path)
                    except OSError:
                        destination = "junction"
                    record("link", relative, destination)
                elif entry.is_dir(follow_symlinks=False):
                    directory_count += 1
                    record("directory", relative)
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
                    file_digest, size = self._fingerprint(path)
                    total_bytes += size
                    record("file", relative, f"{file_digest}:{size}")
                else:
                    raise ScopeContractError(
                        f"Unsupported target filesystem entry: {relative}",
                        "target_integrity_unverified",
                    )

        visit(root)
        return {
            "fingerprint": digest.hexdigest(),
            "file_count": file_count,
            "directory_count": directory_count,
            "link_count": link_count,
            "total_bytes": total_bytes,
        }

    def _protection(self, relative: str, target_root: Path) -> str | None:
        folded = relative.casefold()
        parts = tuple(part.casefold() for part in Path(relative).parts)
        name = parts[-1] if parts else ""
        if (
            any(part in self._HARD_PROTECTED_PARTS for part in parts)
            or name == ".env"
            or name.startswith(".env.")
            or Path(name).suffix.casefold() in self._SECRET_SUFFIXES
            or folded == "runtime/state"
            or folded.startswith("runtime/state/")
        ):
            return "hard"
        if target_root == self.repository_root and any(
            folded == item.casefold() or folded.startswith(item.casefold() + "/")
            for item in self._AGENT_COMPANY_PROTECTED
        ):
            return "agent_company"
        return None

    @staticmethod
    def _fingerprint(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    @staticmethod
    def _is_link(path: Path) -> bool:
        if not path.exists() and not path.is_symlink():
            return False
        is_junction = getattr(os.path, "isjunction", lambda _: False)
        return path.is_symlink() or bool(is_junction(path))

    @staticmethod
    def _target_path(root: Path, relative: str) -> Path:
        candidate = root / Path(relative)
        try:
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(root)
        except (OSError, ValueError) as error:
            raise ScopeContractError(
                f"Authorized path escapes project root: {relative}",
                "path_escape_attempt",
            ) from error
        return candidate

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
