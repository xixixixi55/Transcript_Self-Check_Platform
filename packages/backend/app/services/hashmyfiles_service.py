"""Service facade for HashMyFiles verification HTML generation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from ..repository.hashmyfiles_repository import (
    HashMyFilesError,
    resolve_hashmyfiles,
    run_hashmyfiles,
)

Runner = Callable[[Path, list[Path], Path, int], str]

_DEFAULT_RUNNER: Runner = run_hashmyfiles


def generate_verification_html(
    rar_paths: list[Path],
    output_dir: Path,
    *,
    runner: Runner = _DEFAULT_RUNNER,
) -> str:
    """Generate the HashMyFiles verification HTML for ``rar_paths``.

    Returns the HTML file name written under ``output_dir``. Raises
    :class:`HashMyFilesError` when the tool is unavailable or the run fails,
    so the export fails explicitly instead of omitting the report.
    """
    if not rar_paths:
        raise HashMyFilesError("HASHMYFILES_NO_PARTS", "没有可校验的 RAR 文件。")
    executable = resolve_hashmyfiles()
    if executable is None:
        raise HashMyFilesError("HASHMYFILES_UNAVAILABLE", "HashMyFiles 工具不可用，无法生成校验 HTML。")
    output_dir.mkdir(parents=True, exist_ok=True)
    return runner(executable, rar_paths, output_dir, 120)
