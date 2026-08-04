"""Authorize case directories without trusting client supplied paths."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class ArchiveAuthorizationError(ValueError):
    """Safe authorization diagnostics; messages never contain local paths."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class AuthorizedInputRoot:
    resolved_input_root: Path
    authorization_type: str
    authorized_root_id: str
    authorized_scope: Path | None = None


@dataclass
class _ExactDirectoryGrant:
    token_hash: str
    resolved_root: Path
    authorized_root_id: str
    expires_at: float
    used: bool = False


def _is_reparse_point(path: Path) -> bool:
    try:
        return bool(os.lstat(path).st_file_attributes & _REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def _is_unsafe_special_path(path: Path) -> bool:
    try:
        return path.is_symlink() or _is_reparse_point(path)
    except OSError:
        return True


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_special_path(raw_path: str, path: Path) -> None:
    if not raw_path.strip() or "\x00" in raw_path:
        raise ArchiveAuthorizationError("ARCHIVE_INPUT_PATH_INVALID", "归档输入目录无效。")
    if not path.is_absolute() or ".." in path.parts:
        raise ArchiveAuthorizationError("ARCHIVE_INPUT_PATH_INVALID", "归档输入目录必须是安全的绝对路径。")
    raw = raw_path.replace("/", "\\")
    if raw.startswith("\\\\") or raw.startswith("\\?\\") or raw.startswith("\\.\\"):
        raise ArchiveAuthorizationError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "不支持网络或设备路径。")


def _resolve_directory(raw_path: str | os.PathLike[str]) -> Path:
    raw = os.fspath(raw_path)
    path = Path(raw)
    _reject_special_path(raw, path)
    try:
        if not path.exists() or not path.is_dir():
            raise ArchiveAuthorizationError("ARCHIVE_INPUT_PATH_INVALID", "归档输入目录无效。")
        current = path
        while True:
            if _is_unsafe_special_path(current):
                raise ArchiveAuthorizationError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "归档输入不能包含链接或特殊路径。")
            parent = current.parent
            if parent == current:
                break
            current = parent
        resolved = path.resolve(strict=True)
    except ArchiveAuthorizationError:
        raise
    except OSError as error:
        raise ArchiveAuthorizationError("ARCHIVE_INPUT_PATH_INVALID", "归档输入目录无法访问。") from error
    if not resolved.is_dir() or resolved == Path(resolved.anchor):
        raise ArchiveAuthorizationError("ARCHIVE_INPUT_PATH_INVALID", "归档输入目录无效。")
    return resolved


class ArchiveAuthorizationStore:
    """In-memory root/grant registry for the current desktop process."""

    def __init__(
        self,
        upload_base: str | os.PathLike[str],
        *,
        environment: Mapping[str, str] | None = None,
        grant_ttl_seconds: int = 5 * 60,
        clock=time.time,
    ) -> None:
        self._environment = os.environ if environment is None else environment
        self._grant_ttl_seconds = grant_ttl_seconds
        self._clock = clock
        self._configuration_warnings: list[str] = []
        self._configured_roots = self._load_configured_roots(upload_base)
        self._grants: dict[str, _ExactDirectoryGrant] = {}

    def _load_configured_roots(self, upload_base: str | os.PathLike[str]) -> tuple[Path, ...]:
        raw_roots = [os.fspath(upload_base)]
        raw_roots.extend(self._environment.get("BIJI_ALLOWED_INPUT_ROOTS", "").split(";"))
        roots: list[Path] = []
        for raw_root in raw_roots:
            if not raw_root.strip():
                continue
            try:
                root = _resolve_directory(raw_root)
            except ArchiveAuthorizationError:
                self._configuration_warnings.append("ARCHIVE_CONFIGURED_ROOT_INVALID")
                warnings.warn("ARCHIVE_CONFIGURED_ROOT_INVALID", RuntimeWarning, stacklevel=2)
                continue
            if not any(str(root).casefold() == str(existing).casefold() for existing in roots):
                roots.append(root)
        return tuple(roots)

    @property
    def configured_roots(self) -> tuple[Path, ...]:
        return self._configured_roots

    @property
    def configuration_warnings(self) -> tuple[str, ...]:
        """Safe startup diagnostics; no configured path is included."""
        return tuple(self._configuration_warnings)

    @staticmethod
    def _root_id(root: Path) -> str:
        return hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]

    def validate_output_separation(
        self,
        input_root: Path,
        output_roots: tuple[str | os.PathLike[str], ...],
    ) -> None:
        for raw_output in output_roots:
            try:
                output = Path(raw_output).resolve(strict=False)
            except OSError as error:
                raise ArchiveAuthorizationError(
                    "ARCHIVE_INPUT_OUTPUT_OVERLAP", "归档输入与系统输出区域冲突。",
                ) from error
            if _is_within(input_root, output) or _is_within(output, input_root):
                raise ArchiveAuthorizationError(
                    "ARCHIVE_INPUT_OUTPUT_OVERLAP", "归档输入与系统输出区域冲突。",
                )

    def authorize_directory(
        self,
        selected_path: str | os.PathLike[str],
        *,
        grant_token: str | None = None,
        output_roots: tuple[str | os.PathLike[str], ...] = (),
        source_authorization_enabled: bool = True,
    ) -> AuthorizedInputRoot:
        resolved = _resolve_directory(selected_path)
        self.validate_output_separation(resolved, output_roots)
        if not source_authorization_enabled:
            return AuthorizedInputRoot(
                resolved,
                "unrestricted_local_directory",
                self._root_id(resolved.parent),
                resolved.parent,
            )
        if grant_token:
            return self._consume_grant(grant_token, resolved)
        for root in self._configured_roots:
            if resolved != root and _is_within(resolved, root):
                return AuthorizedInputRoot(resolved, "configured_root", self._root_id(root), root)
        raise ArchiveAuthorizationError(
            "ARCHIVE_INPUT_ROOT_NOT_ALLOWED", "归档输入目录未获授权，请重新选择案件目录。",
        )

    def issue_exact_directory_grant(self, selected_path: str | os.PathLike[str]) -> str:
        """Issue a one-use token for a future trusted local directory picker."""
        resolved = _resolve_directory(selected_path)
        token = secrets.token_urlsafe(32)
        self._grants[hashlib.sha256(token.encode("ascii")).hexdigest()] = _ExactDirectoryGrant(
            hashlib.sha256(token.encode("ascii")).hexdigest(),
            resolved,
            secrets.token_hex(16),
            self._clock() + self._grant_ttl_seconds,
        )
        return token

    def _consume_grant(self, token: str, resolved: Path) -> AuthorizedInputRoot:
        try:
            token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        except UnicodeEncodeError as error:
            raise ArchiveAuthorizationError("ARCHIVE_AUTHORIZATION_INVALID", "目录授权无效。") from error
        grant = self._grants.get(token_hash)
        if grant is None or grant.used:
            raise ArchiveAuthorizationError("ARCHIVE_AUTHORIZATION_INVALID", "目录授权无效。")
        if grant.expires_at <= self._clock():
            grant.used = True
            raise ArchiveAuthorizationError("ARCHIVE_AUTHORIZATION_EXPIRED", "目录授权已过期，请重新选择目录。")
        if grant.resolved_root != resolved:
            raise ArchiveAuthorizationError("ARCHIVE_AUTHORIZATION_INVALID", "目录授权与所选目录不匹配。")
        grant.used = True
        return AuthorizedInputRoot(resolved, "exact_directory_grant", grant.authorized_root_id, grant.resolved_root)

    def authorize_server_source(
        self,
        source_root: str | os.PathLike[str],
        cleanup_root: str | os.PathLike[str],
        *,
        output_roots: tuple[str | os.PathLike[str], ...] = (),
    ) -> AuthorizedInputRoot:
        """Authorize an archive extracted by this server, never a client path."""
        source = _resolve_directory(source_root)
        cleanup = _resolve_directory(cleanup_root)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
        if (
            not cleanup.name.startswith("biji_archive_context_")
            or not _is_within(cleanup, temp_root)
            or not _is_within(source, cleanup)
        ):
            raise ArchiveAuthorizationError("ARCHIVE_AUTHORIZATION_INVALID", "归档输入授权无效。")
        self.validate_output_separation(source, output_roots)
        return AuthorizedInputRoot(source, "configured_root", "server_uploaded_archive", cleanup)
