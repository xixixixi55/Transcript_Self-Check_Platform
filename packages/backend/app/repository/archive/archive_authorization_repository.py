"""在不信任客户端所提供路径的情况下授权案件目录。"""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class ArchiveAuthorizationError(ValueError):
    """安全授权诊断；消息绝不包含本地路径。"""

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
    """本机输入路径安全检查和导出目录授权注册表。"""

    def __init__(
        self,
        *,
        grant_ttl_seconds: int = 5 * 60,
        clock=time.time,
    ) -> None:
        self._grant_ttl_seconds = grant_ttl_seconds
        self._clock = clock
        self._grants: dict[str, _ExactDirectoryGrant] = {}

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
        output_roots: tuple[str | os.PathLike[str], ...] = (),
    ) -> AuthorizedInputRoot:
        resolved = _resolve_directory(selected_path)
        self.validate_output_separation(resolved, output_roots)
        return AuthorizedInputRoot(
            resolved,
            "unrestricted_local_directory",
            self._root_id(resolved.parent),
            resolved.parent,
        )

    def issue_exact_directory_grant(self, selected_path: str | os.PathLike[str]) -> str:
        """为受控导出目录签发一次性令牌。"""
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
        """授权由此服务器解压的归档，而非客户端路径。"""
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
