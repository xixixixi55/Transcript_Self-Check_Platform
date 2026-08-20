"""Native Windows entry point for the portable application."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from portable_launcher import (
    LauncherError,
    SingleInstance,
    attach_kill_on_close_job,
    new_secret,
    open_application_browser,
    open_desktop_browser,
    resolve_launcher_paths,
    start_backend,
    terminate_process_tree,
    validate_program_integrity,
    wait_until_ready,
)
from windows_tray import TrayError, run_windows_tray

MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_ICONERROR = 0x00000010


def show_message(title: str, message: str, flags: int = MB_OK) -> None:
    """Use the Windows API so the launcher has no Tk runtime dependency."""
    ctypes.windll.user32.MessageBoxW(None, message, title, flags)


def main() -> int:
    lock = None
    process = None
    process_job = None
    log_handle = None
    ready_file = None
    try:
        paths = resolve_launcher_paths(executable=Path(sys.executable).resolve())
        validate_program_integrity(paths)
        lock = SingleInstance(paths.lock_file)
        if not lock.acquire():
            show_message("文枢", "文枢已经在运行，请通过系统托盘重新打开。", MB_ICONINFORMATION)
            return 0
        ready_file = paths.log_root / "backend-ready.json"
        ready_file.unlink(missing_ok=True)
        secret = new_secret()
        process, log_handle = start_backend(paths, 0, secret, ready_file)
        process_job = attach_kill_on_close_job(process)
        port = wait_until_ready(process, ready_file, secret)
        open_desktop_browser(port, secret)

        def reopen_application() -> None:
            try:
                open_application_browser(port)
            except (LauncherError, OSError) as error:
                show_message("无法打开文枢", str(error), MB_ICONERROR)

        tray_result = run_windows_tray(
            reopen_application,
            lambda: process.poll() is None,
        )
        if tray_result == "backend_stopped":
            show_message("文枢已停止", "文枢后端意外退出，请查看日志后重新启动。", MB_ICONERROR)
            return 1
        return 0
    except (LauncherError, TrayError) as error:
        show_message("文枢启动失败", str(error), MB_ICONERROR)
        return 1
    except OSError:
        show_message("文枢启动失败", "无法访问程序或用户数据文件，请重新解压后重试。", MB_ICONERROR)
        return 1
    finally:
        if process is not None:
            terminate_process_tree(process)
        if process_job is not None:
            process_job.close()
        if log_handle is not None:
            log_handle.close()
        if ready_file is not None:
            ready_file.unlink(missing_ok=True)
        if lock is not None:
            lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
