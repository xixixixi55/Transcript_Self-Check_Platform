"""Cooperative monitoring for one task-owned WinRAR process."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from .workbench_constants import ARCHIVE_ACTIVITY_PERSIST_INTERVAL_SECONDS


class OwnedProcessCancelled(RuntimeError):
    pass


class OwnedProcessOwnershipLost(RuntimeError):
    pass


class OwnedProcessTerminationFailed(RuntimeError):
    pass


def terminate_process_tree(
    process: subprocess.Popen[str],
    pid: int,
    tree_killer: Callable[[int], bool],
) -> bool:
    if os.name == "nt":
        if tree_killer(pid):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            if process.poll() is not None:
                return True
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return process.poll() is not None
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    return process.poll() is not None


def monitor_owned_process(
    process: subprocess.Popen[str],
    *,
    pid: int,
    args: list[str],
    timeout: int,
    staging_dir: Path,
    terminate: Callable[[subprocess.Popen[str], int], bool],
    activity_callback: Callable[[Path], None] | None,
    cancellation_check: Callable[[], bool] | None,
    activity_interval_seconds: int = ARCHIVE_ACTIVITY_PERSIST_INTERVAL_SECONDS,
) -> None:
    deadline = time.monotonic() + timeout
    next_activity_at = 0.0
    while process.poll() is None:
        if cancellation_check and cancellation_check():
            if not terminate(process, pid):
                raise OwnedProcessTerminationFailed()
            raise OwnedProcessCancelled()
        now = time.monotonic()
        if activity_callback is not None and now >= next_activity_at:
            try:
                activity_callback(staging_dir)
            except Exception as error:
                if not terminate(process, pid):
                    raise OwnedProcessTerminationFailed() from error
                raise OwnedProcessOwnershipLost() from error
            next_activity_at = now + activity_interval_seconds
        remaining = deadline - now
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, timeout)
        try:
            process.wait(timeout=min(1.0, remaining))
        except subprocess.TimeoutExpired:
            continue
    process.communicate()
