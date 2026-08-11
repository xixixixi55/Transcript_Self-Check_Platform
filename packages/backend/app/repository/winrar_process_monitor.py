"""Cooperative monitoring for one task-owned WinRAR process."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from .workbench_constants import ARCHIVE_ACTIVITY_PERSIST_INTERVAL_SECONDS

ARCHIVE_OUTPUT_IDLE_TIMEOUT_SECONDS = 600


class OwnedProcessCancelled(RuntimeError):
    pass


class OwnedProcessOwnershipLost(RuntimeError):
    pass


class OwnedProcessTerminationFailed(RuntimeError):
    pass


class OwnedProcessIdleTimeout(subprocess.TimeoutExpired):
    pass


def _rar_output_size(staging_dir: Path) -> int:
    total = 0
    try:
        paths = staging_dir.glob("*.rar")
    except OSError:
        return 0
    for path in paths:
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


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
    idle_timeout_seconds: int = ARCHIVE_OUTPUT_IDLE_TIMEOUT_SECONDS,
    output_size_probe: Callable[[Path], int] = _rar_output_size,
) -> None:
    deadline = time.monotonic() + timeout
    last_output_size = output_size_probe(staging_dir)
    last_output_change = time.monotonic() if last_output_size > 0 else None
    next_activity_at = 0.0
    while process.poll() is None:
        if cancellation_check and cancellation_check():
            if not terminate(process, pid):
                raise OwnedProcessTerminationFailed()
            raise OwnedProcessCancelled()
        now = time.monotonic()
        output_size = output_size_probe(staging_dir)
        if output_size > last_output_size:
            last_output_change = now
        last_output_size = output_size
        idle_deadline = (
            last_output_change + idle_timeout_seconds
            if last_output_change is not None else None
        )
        if now >= deadline and (idle_deadline is None or deadline <= idle_deadline):
            raise subprocess.TimeoutExpired(args, timeout)
        if idle_deadline is not None and now >= idle_deadline:
            raise OwnedProcessIdleTimeout(args, idle_timeout_seconds)
        if activity_callback is not None and now >= next_activity_at:
            try:
                activity_callback(staging_dir)
            except Exception as error:
                if not terminate(process, pid):
                    raise OwnedProcessTerminationFailed() from error
                raise OwnedProcessOwnershipLost() from error
            next_activity_at = now + activity_interval_seconds
        remaining = deadline - now
        if idle_deadline is not None:
            remaining = min(remaining, idle_deadline - now)
        try:
            process.wait(timeout=min(1.0, remaining))
        except subprocess.TimeoutExpired:
            continue
    process.communicate()
