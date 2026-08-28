"""窗口化便携启动器的核心进程生命周期。"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable
from urllib.parse import quote

try:
    from generated_integrity import EXPECTED_FILES as _EMBEDDED_EXPECTED_FILES
except ImportError:
    _EMBEDDED_EXPECTED_FILES: dict[str, str] = {}


class LauncherError(RuntimeError):
    """可安全向用户展示的便携式启动失败。"""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_program_integrity(
    paths: LauncherPaths,
    *,
    expected_files: dict[str, str] | None = None,
) -> tuple[str, ...]:
    expected = _EMBEDDED_EXPECTED_FILES if expected_files is None else expected_files
    if not expected:
        raise LauncherError("程序完整性清单不可用，请重新解压完整发布包。")
    try:
        entries = list(paths.resource_root.rglob("*"))
        if any(path.is_symlink() for path in entries):
            raise LauncherError("程序目录包含不受支持的链接，请重新解压完整发布包。")
        actual = {
            path.relative_to(paths.resource_root).as_posix()
            for path in entries
            if path.is_file() and path.relative_to(paths.resource_root).as_posix()
            not in {"文枢.exe", "PORTABLE-FILES.json"}
        }
        if set(expected) - actual:
            raise LauncherError("程序文件不完整，请重新解压完整发布包。")
        for relative, expected_hash in expected.items():
            candidate = paths.resource_root / Path(relative)
            if candidate.is_symlink() or _file_sha256(candidate) != expected_hash:
                raise LauncherError("程序文件校验失败，请重新解压完整发布包。")
        return tuple(sorted(actual - set(expected)))
    except LauncherError:
        raise
    except OSError as error:
        raise LauncherError("无法校验程序文件，请重新解压完整发布包。") from error


def record_integrity_warning(paths: LauncherPaths, unknown_files: tuple[str, ...]) -> None:
    """记录额外文件数量，不泄露文件名或绝对路径。"""
    if not unknown_files:
        return
    try:
        paths.log_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with (paths.log_root / "launcher.log").open("a", encoding="utf-8") as log:
            log.write(
                f"{timestamp} PROGRAM_INTEGRITY_UNKNOWN_FILES_IGNORED "
                f"count={len(unknown_files)}\n"
            )
    except OSError:
        return


def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        try:
            right.relative_to(left)
            return True
        except ValueError:
            return False


@dataclass(frozen=True)
class LauncherPaths:
    resource_root: Path
    app_data_root: Path
    backend_executable: Path
    log_root: Path
    lock_file: Path


def resolve_launcher_paths(
    env: dict[str, str] | None = None,
    *,
    executable: Path | None = None,
) -> LauncherPaths:
    values = dict(os.environ if env is None else env)
    running_executable = executable or Path(sys.executable).resolve()
    resource_override = values.get("BIJI_RESOURCE_ROOT", "").strip()
    resource_root = Path(resource_override).resolve() if resource_override else running_executable.parent
    app_override = values.get("BIJI_APP_DATA_ROOT", "").strip()
    local_app_data = values.get("LOCALAPPDATA", "").strip()
    if app_override:
        app_data_root = Path(app_override).resolve()
    elif local_app_data:
        app_data_root = Path(local_app_data).resolve() / "文枢"
    else:
        raise LauncherError("无法确定用户数据目录，请检查 Windows 用户环境。")
    if _paths_overlap(resource_root, app_data_root):
        raise LauncherError("程序目录与用户数据目录不能重叠。")
    return LauncherPaths(
        resource_root=resource_root,
        app_data_root=app_data_root,
        backend_executable=resource_root / "runtime" / "backend" / "backend.exe",
        log_root=app_data_root / "logs",
        lock_file=app_data_root / "launcher.lock",
    )


class SingleInstance:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: BinaryIO | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle: BinaryIO | None = None
        try:
            handle = self.path.open("a+b")
            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if handle is not None:
                handle.close()
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def select_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def build_backend_environment(paths: LauncherPaths, secret: str) -> dict[str, str]:
    values = dict(os.environ)
    for key in ("BIJI_NODE_PATH", "BIJI_OFFICECLI_ENTRY"):
        values.pop(key, None)
    values.update({
        "BIJI_PORTABLE_MODE": "1",
        "BIJI_RESOURCE_ROOT": str(paths.resource_root),
        "BIJI_APP_DATA_ROOT": str(paths.app_data_root),
        "BIJI_WORKBENCH_DATA_ROOT": str(paths.app_data_root / "data"),
        "BIJI_DESKTOP_SECRET": secret,
        "PYTHONUTF8": "1",
    })
    return values


class ProcessJob:
    """关闭时会终止所属后端进程树的 Windows Job Object。"""

    def __init__(self, handle: int) -> None:
        self.handle = handle

    def close(self) -> None:
        if not self.handle:
            return
        import ctypes

        ctypes.windll.kernel32.CloseHandle(self.handle)
        self.handle = 0


def attach_kill_on_close_job(process: subprocess.Popen) -> ProcessJob | None:
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise LauncherError("无法建立后端进程保护，请重试。")
    job = ProcessJob(handle)
    information = ExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = 0x00002000
    if not kernel32.SetInformationJobObject(
        handle, 9, ctypes.byref(information), ctypes.sizeof(information),
    ):
        job.close()
        raise LauncherError("无法配置后端进程保护，请重试。")
    process_handle = wintypes.HANDLE(getattr(process, "_handle", 0))
    if not process_handle or not kernel32.AssignProcessToJobObject(handle, process_handle):
        job.close()
        raise LauncherError("无法托管后端进程，请重试。")
    return job


def start_backend(
    paths: LauncherPaths,
    port: int,
    secret: str,
    ready_file: Path,
    *,
    popen: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> tuple[subprocess.Popen, BinaryIO]:
    if not paths.backend_executable.is_file():
        raise LauncherError("程序文件不完整：缺少后端运行文件。")
    paths.log_root.mkdir(parents=True, exist_ok=True)
    log_handle = (paths.log_root / "backend.log").open("ab")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = popen(
        [str(paths.backend_executable), "--port", str(port), "--ready-file", str(ready_file)],
        cwd=str(paths.backend_executable.parent),
        env=build_backend_environment(paths, secret),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return process, log_handle


def wait_until_ready(
    process: subprocess.Popen,
    ready_file: Path,
    secret: str,
    *,
    expected_port: int | None = None,
    timeout_seconds: float = 45.0,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LauncherError("文枢后端启动失败，请查看日志。")
        if ready_file.is_file():
            try:
                handshake = json.loads(ready_file.read_text(encoding="utf-8"))
                port = handshake.get("port")
                pid = handshake.get("pid")
                proof = handshake.get("proof", "")
                identity = f"{pid}:{port}".encode("ascii")
                expected_proof = hmac.new(
                    secret.encode("utf-8"), identity, hashlib.sha256,
                ).hexdigest()
                if (
                    handshake.get("status") == "ready"
                    and pid == process.pid and isinstance(port, int)
                    and (expected_port is None or port == expected_port)
                    and isinstance(proof, str) and hmac.compare_digest(proof, expected_proof)
                ):
                    with opener(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        if getattr(response, "status", 0) == 200:
                            return port
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        time.sleep(0.1)
    raise LauncherError("文枢启动超时，请查看日志后重试。")


def open_desktop_browser(
    port: int,
    secret: str,
    *,
    browser_open: Callable[[str], object] = webbrowser.open,
) -> None:
    url = f"http://127.0.0.1:{port}/desktop/bootstrap#token={quote(secret, safe='')}"
    if browser_open(url) is False:
        raise LauncherError("无法自动打开浏览器，请检查默认浏览器设置。")


def open_application_browser(
    port: int,
    *,
    browser_open: Callable[[str], object] = webbrowser.open,
) -> None:
    if browser_open(f"http://127.0.0.1:{port}/") is False:
        raise LauncherError("无法自动打开浏览器，请检查默认浏览器设置。")


def terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def new_secret() -> str:
    return secrets.token_urlsafe(48)


__all__ = [
    "LauncherError", "LauncherPaths", "ProcessJob", "SingleInstance",
    "attach_kill_on_close_job", "build_backend_environment",
    "new_secret", "open_application_browser", "open_desktop_browser",
    "record_integrity_warning", "resolve_launcher_paths", "select_loopback_port",
    "start_backend", "terminate_process_tree", "validate_program_integrity",
    "wait_until_ready",
]
