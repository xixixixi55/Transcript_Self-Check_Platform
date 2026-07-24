"""Authorization and cleanup guards for preview-source records."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

from ..repository.archive_authorization_repository import AuthorizedInputRoot
from .archive_runtime_service import ArchiveRuntimeError


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def validate_authorized_input(authorized_input: AuthorizedInputRoot) -> None:
    root = authorized_input.resolved_input_root
    try:
        info = os.lstat(root)
        current = root.resolve(strict=True)
    except OSError as error:
        raise ArchiveRuntimeError(
            "ARCHIVE_AUTHORIZATION_INVALID",
            "Archive input authorization is no longer valid.",
        ) from error
    if not stat.S_ISDIR(info.st_mode) or root.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    ) or not current.is_dir():
        raise ArchiveRuntimeError(
            "ARCHIVE_AUTHORIZATION_INVALID",
            "Archive input authorization is no longer valid.",
        )
    if authorized_input.authorization_type == "exact_directory_grant" and current != root:
        raise ArchiveRuntimeError("ARCHIVE_INPUT_CHANGED", "Archive input changed before preparation.")
    scope = authorized_input.authorized_scope
    if scope is not None:
        try:
            current.relative_to(scope)
        except ValueError as error:
            raise ArchiveRuntimeError(
                "ARCHIVE_AUTHORIZATION_INVALID",
                "Archive input authorization is no longer valid.",
            ) from error


def cleanup_owned_source(path: Path | None) -> None:
    if path is None:
        return
    try:
        resolved = path.resolve(strict=False)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
        resolved.relative_to(temp_root)
    except (OSError, ValueError):
        return
    if resolved.name.startswith("biji_archive_context_"):
        shutil.rmtree(resolved, ignore_errors=True)


__all__ = ["cleanup_owned_source", "validate_authorized_input"]
