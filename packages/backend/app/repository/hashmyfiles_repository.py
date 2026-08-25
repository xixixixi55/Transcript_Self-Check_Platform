"""Run the real HashMyFiles.exe window and capture its three-column result."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .hashmyfiles_capture_script import CAPTURE_SCRIPT
from .hashmyfiles_result_repository import validate_hashmyfiles_rows
from .runtime_paths import get_runtime_paths

_CAPTURE_SCRIPT = CAPTURE_SCRIPT
_HASH_IMAGE_FILENAME = "hash-verification.png"
_LEGACY_HASH_HTML_FILENAME = "hash-verification.html"
HASHMYFILES_DISPLAY_VERSION = "2.51"
_HASH_POLICIES = {
    "md5": {"column": 1, "length": 32, "display_width": 312},
    "sha1": {"column": 2, "length": 40, "display_width": 384},
    "sha256": {"column": 4, "length": 64, "display_width": 600},
}
_WINDOW_NON_HASH_WIDTH = 475
_CAPTURE_GRACE_SECONDS = 30
_PROCESS_EXIT_GRACE_SECONDS = 15
_DEFAULT_TOOL_PATH = get_runtime_paths().hashmyfiles_executable
_FAILURE_MESSAGES = {
    "HASHMYFILES_LAUNCH_FAILED": "HashMyFiles 无法启动。",
    "HASHMYFILES_TIMEOUT": "HashMyFiles 校验未在规定时间内完成。",
    "HASHMYFILES_WINDOW_UNRESPONSIVE": "HashMyFiles 窗口持续无响应。",
    "HASHMYFILES_RUN_FAILED": "HashMyFiles 校验执行失败。",
    "HASHMYFILES_SCREENSHOT_FAILED": "HashMyFiles 校验已完成，但截图生成失败。",
}


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
    hash_algorithm: str = "md5",
) -> str:
    """Produce a validated native-window PNG inside ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / _HASH_IMAGE_FILENAME
    legacy_html_path = output_dir / _LEGACY_HASH_HTML_FILENAME
    with tempfile.TemporaryDirectory(
        prefix=".biji-hashmyfiles-", dir=output_dir,
    ) as temp_dir:
        candidate_image_path = Path(temp_dir) / _HASH_IMAGE_FILENAME
        _capture_hashmyfiles_window(
            executable, rar_paths, candidate_image_path, timeout_seconds,
            hash_algorithm,
        )
        _validate_png(candidate_image_path)
        try:
            os.replace(candidate_image_path, image_path)
        except OSError as error:
            raise HashMyFilesError(
                "HASHMYFILES_SCREENSHOT_FAILED",
                "HashMyFiles 校验截图发布失败。",
            ) from error
    legacy_html_path.unlink(missing_ok=True)
    return _HASH_IMAGE_FILENAME


def _validate_png(image_path: Path) -> None:
    try:
        with image_path.open("rb") as image_file:
            signature = image_file.read(8)
            has_payload = bool(image_file.read(1))
    except OSError as error:
        raise HashMyFilesError(
            "HASHMYFILES_SCREENSHOT_MISSING", "HashMyFiles 校验截图未生成。",
        ) from error
    if signature != b"\x89PNG\r\n\x1a\n" or not has_payload:
        raise HashMyFilesError(
            "HASHMYFILES_SCREENSHOT_INVALID", "HashMyFiles 校验截图无效。",
        )


def _capture_hashmyfiles_window(
    executable: Path,
    rar_paths: list[Path],
    output_path: Path,
    timeout_seconds: int,
    hash_algorithm: str,
) -> None:
    policy = _HASH_POLICIES.get(hash_algorithm)
    if policy is None:
        raise HashMyFilesError(
            "HASHMYFILES_ALGORITHM_INVALID", "HashMyFiles 哈希算法无效。",
        )
    hash_arguments = [
        "/MD5", "1" if hash_algorithm == "md5" else "0",
        "/SHA1", "1" if hash_algorithm == "sha1" else "0",
        "/CRC32", "0",
        "/SHA256", "1" if hash_algorithm == "sha256" else "0",
        "/SHA512", "0", "/SHA384", "0",
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="biji-hash-capture-") as temp_dir:
            temp_path = Path(temp_dir)
            payload_path = temp_path / "capture.json"
            script_path = temp_path / "render.ps1"
            result_path = temp_path / "result.json"
            payload_path.write_text(json.dumps({
                "executable": str(executable),
                "files": [str(path) for path in rar_paths],
                "expected_count": len(rar_paths),
                "timeout_seconds": timeout_seconds,
                "capture_grace_seconds": _CAPTURE_GRACE_SECONDS,
                "hash_arguments": hash_arguments,
                "hash_column_index": policy["column"],
                "hash_digest_length": policy["length"],
                "hash_column_width": policy["display_width"],
                "window_width": _WINDOW_NON_HASH_WIDTH + policy["display_width"],
            }, ensure_ascii=False), encoding="utf-8")
            script_path.write_text(CAPTURE_SCRIPT, encoding="utf-8-sig")
            result = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", str(script_path),
                    str(payload_path), str(output_path), str(result_path),
                ],
                capture_output=True,
                timeout=timeout_seconds + _CAPTURE_GRACE_SECONDS + _PROCESS_EXIT_GRACE_SECONDS,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            capture_result = _read_capture_result(result_path)
            if result.returncode != 0:
                code = str((capture_result or {}).get("error_code") or "")
                if code not in _FAILURE_MESSAGES:
                    code = "HASHMYFILES_RUN_FAILED"
                raise HashMyFilesError(code, _FAILURE_MESSAGES[code])
            if not capture_result or capture_result.get("status") != "succeeded":
                raise HashMyFilesError(
                    "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果无法读取。",
                )
            if capture_result.get("item_count") != len(rar_paths):
                raise HashMyFilesError(
                    "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果不完整。",
                )
            try:
                validate_hashmyfiles_rows(
                    capture_result.get("rows"), rar_paths, int(policy["length"]),
                )
            except (OSError, KeyError, TypeError, ValueError) as error:
                raise HashMyFilesError(
                    "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果不完整。",
                ) from error
    except subprocess.TimeoutExpired as error:
        raise HashMyFilesError(
            "HASHMYFILES_TIMEOUT", _FAILURE_MESSAGES["HASHMYFILES_TIMEOUT"],
        ) from error
    except OSError as error:
        raise HashMyFilesError(
            "HASHMYFILES_RUN_FAILED", _FAILURE_MESSAGES["HASHMYFILES_RUN_FAILED"],
        ) from error


def _read_capture_result(result_path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(result_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
