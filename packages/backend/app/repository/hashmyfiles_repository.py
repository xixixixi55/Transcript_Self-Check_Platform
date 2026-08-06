"""Run HashMyFiles.exe over a set of RAR parts and emit a verification HTML.

The executable is a local third-party tool (not tracked by the repository).
Real command-line arguments are probed once on a machine with the tool; until
then the invocation raises a controlled error so exports fail explicitly
instead of silently omitting the verification report.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class HashMyFilesError(RuntimeError):
    """Stable, path-free diagnostic for HashMyFiles failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_hashmyfiles() -> Path | None:
    """Resolve HashMyFiles.exe; env override first, then reserved default."""
    override = os.environ.get("BIJI_HASHMYFILES_PATH")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
    return None


def run_hashmyfiles(
    executable: Path,
    rar_paths: list[Path],
    output_dir: Path,
    timeout_seconds: int = 120,
) -> str:
    """Produce the verification HTML file name inside ``output_dir``.

    TODO(probe): confirm HashMyFiles.exe command-line switches and HTML output
    name on a machine that has the tool; the real arguments replace this
    placeholder before the change is gated. No filesystem paths leak in errors.
    """
    raise HashMyFilesError(
        "HASHMYFILES_ARGUMENTS_NOT_CONFIGURED",
        "HashMyFiles 校验 HTML 生成参数尚未配置，导出被阻止。",
    )


def _invoke(executable: Path, args: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [str(executable), *args],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise HashMyFilesError("HASHMYFILES_TIMEOUT", "HashMyFiles 校验超时。") from error
    except OSError as error:
        raise HashMyFilesError("HASHMYFILES_LAUNCH_FAILED", "HashMyFiles 无法启动。") from error
