"""Run HashMyFiles.exe over a set of RAR parts and emit a verification HTML.

The executable is a local third-party tool (not tracked by the repository).
Command-line switches were probed against HashMyFiles v2.51 on Windows
(2026-08-06): ``/files`` accepts multiple paths, ``/shtml`` writes a
horizontal HTML list and the process auto-exits after saving with returncode
0. Failures raise a controlled error so exports fail explicitly instead of
silently omitting the verification report.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_HASH_HTML_FILENAME = "hash-verification.html"
_HASH_TYPES_ARGS = [
    "/MD5", "1", "/SHA1", "0", "/CRC32", "0",
    "/SHA256", "0", "/SHA512", "0", "/SHA384", "0",
]
# Bundled default shipped with the repository: packages/backend -> root/hashmyfiles.
_DEFAULT_TOOL_PATH = Path(__file__).resolve().parents[4] / "hashmyfiles" / "HashMyFiles.exe"


class HashMyFilesError(RuntimeError):
    """Stable, path-free diagnostic for HashMyFiles failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_hashmyfiles() -> Path | None:
    """Resolve HashMyFiles.exe; env override first, then the bundled default."""
    override = os.environ.get("BIJI_HASHMYFILES_PATH")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
    if _DEFAULT_TOOL_PATH.is_file():
        return _DEFAULT_TOOL_PATH
    return None


def run_hashmyfiles(
    executable: Path,
    rar_paths: list[Path],
    output_dir: Path,
    timeout_seconds: int = 120,
) -> str:
    """Produce the verification HTML file name inside ``output_dir``.

    Only MD5 is enabled so hashing stays fast; HashMyFiles still writes every
    hash column header but leaves the disabled ones empty. The returned name
    is stable across re-exports so repeated exports overwrite the report.
    Errors never leak filesystem paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / _HASH_HTML_FILENAME
    args = [
        "/files", *[str(path) for path in rar_paths],
        *_HASH_TYPES_ARGS, "/shtml", str(html_path),
    ]
    result = _invoke(executable, args, timeout_seconds)
    if result.returncode != 0:
        raise HashMyFilesError("HASHMYFILES_RUN_FAILED", "HashMyFiles 校验生成失败。")
    if not html_path.is_file():
        raise HashMyFilesError(
            "HASHMYFILES_OUTPUT_MISSING", "HashMyFiles 校验 HTML 未生成。",
        )
    return _HASH_HTML_FILENAME


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
