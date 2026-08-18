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
    open_desktop_browser,
    resolve_launcher_paths,
    start_backend,
    terminate_process_tree,
    validate_program_integrity,
    wait_until_ready,
)

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
            show_message("文枢", "文枢已经在运行，请使用已打开的浏览器窗口。", MB_ICONINFORMATION)
            return 0
        ready_file = paths.log_root / "backend-ready.json"
        ready_file.unlink(missing_ok=True)
        secret = new_secret()
        process, log_handle = start_backend(paths, 0, secret, ready_file)
        process_job = attach_kill_on_close_job(process)
        port = wait_until_ready(process, ready_file, secret)
        open_desktop_browser(port, secret)
        show_message(
            "文枢正在运行",
            "文枢已在浏览器中打开。\n\n使用期间请保留本窗口；点击“确定”将退出文枢。",
            MB_ICONINFORMATION,
        )
        return 0
    except LauncherError as error:
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
