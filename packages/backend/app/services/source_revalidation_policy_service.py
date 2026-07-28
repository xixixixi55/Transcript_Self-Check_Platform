"""Safe classification for source verification failures."""

from __future__ import annotations

import errno


def is_temporary_source_failure(error: Exception) -> bool:
    if isinstance(error, FileNotFoundError):
        return False
    if isinstance(error, (PermissionError, TimeoutError, BlockingIOError, OSError)):
        return True
    return getattr(error, "code", None) in {
        "SOURCE_ACCESS_DENIED", "ARCHIVE_INPUT_ACCESS_DENIED", errno.EACCES,
    }
