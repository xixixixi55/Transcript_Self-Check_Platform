"""Service facade for HashMyFiles verification screenshot generation."""

from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Callable

from ..repository.hashmyfiles_repository import (
    HashMyFilesError,
    resolve_hashmyfiles,
    run_hashmyfiles,
)

Runner = Callable[[Path, list[Path], Path, int, str], str]

_DEFAULT_RUNNER: Runner = run_hashmyfiles
_MIN_TIMEOUT_SECONDS = 120
_MAX_TIMEOUT_SECONDS = 30 * 24 * 60 * 60
_ESTIMATED_BYTES_PER_SECOND = 100_000
_TIMEOUT_OVERHEAD_SECONDS = 120


def generate_verification_image(
    rar_paths: list[Path],
    output_dir: Path,
    *,
    hash_algorithm: str = "md5",
    runner: Runner = _DEFAULT_RUNNER,
) -> str:
    """Generate the HashMyFiles verification PNG for ``rar_paths``.

    Returns the PNG file name written under ``output_dir``. Raises
    :class:`HashMyFilesError` when the tool is unavailable or the run fails,
    so the export fails explicitly instead of omitting the report.
    """
    if not rar_paths:
        raise HashMyFilesError("HASHMYFILES_NO_PARTS", "没有可校验的 RAR 文件。")
    executable = resolve_hashmyfiles()
    if executable is None:
        raise HashMyFilesError("HASHMYFILES_UNAVAILABLE", "HashMyFiles 工具不可用，无法生成校验截图。")
    output_dir.mkdir(parents=True, exist_ok=True)
    return runner(
        executable, rar_paths, output_dir, _hash_timeout_seconds(rar_paths),
        hash_algorithm,
    )


def _hash_timeout_seconds(rar_paths: list[Path]) -> int:
    override = os.environ.get("BIJI_HASHMYFILES_TIMEOUT_SECONDS")
    if override:
        try:
            return min(_MAX_TIMEOUT_SECONDS, max(_MIN_TIMEOUT_SECONDS, int(override)))
        except ValueError:
            pass
    total_bytes = sum(path.stat().st_size for path in rar_paths)
    estimate = math.ceil(total_bytes / _ESTIMATED_BYTES_PER_SECOND)
    return min(
        _MAX_TIMEOUT_SECONDS,
        max(_MIN_TIMEOUT_SECONDS, estimate + _TIMEOUT_OVERHEAD_SECONDS),
    )
