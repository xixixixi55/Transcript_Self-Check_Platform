"""Safe WinRAR process execution into an isolated staging directory."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from .winrar_execution_models_repository import (
    ArchiveExecutionError, PlanEntry, PlanLike, ProcessRunner,
    ProcessStartedCallback, StagingInitializer, WinRarExecutionResult,
)
from .winrar_discovery_repository import WinRarCapability
from .winrar_timeout_policy import (  # noqa: E402
    _kill_process_tree_impl,
    compute_timeout as _compute_timeout,
    timeout_bounds as _timeout_bounds,
)
from .winrar_process_monitor import (
    OwnedProcessCancelled, OwnedProcessOwnershipLost,
    OwnedProcessIdleTimeout, OwnedProcessTerminationFailed, monitor_owned_process,
    terminate_process_tree,
)

def _terminate_process(process: subprocess.Popen[str], pid: int) -> bool:
    return terminate_process_tree(process, pid, _kill_process_tree_impl)

class WinRarExecutor:
    """The only component that constructs and invokes the WinRAR argument array."""
    _active_plans: set[str] = set()
    _active_guard = threading.Lock()

    def __init__(self, staging_root: str | os.PathLike[str], *,
                 timeout_seconds: int | None = None,
                 process_runner: ProcessRunner | None = None,
                 staging_initializer: StagingInitializer | None = None,
                 process_started_callback: ProcessStartedCallback | None = None,
                 activity_callback: Callable[[Path], None] | None = None,
                 cancellation_check: Callable[[], bool] | None = None) -> None:
        self.staging_root = Path(staging_root)
        self._explicit_timeout = timeout_seconds
        self._process_runner = process_runner
        self._staging_initializer = staging_initializer
        self._process_started_callback = process_started_callback
        self._activity_callback = activity_callback
        self._cancellation_check = cancellation_check
    @staticmethod
    def compute_timeout(input_bytes: int) -> int:
        return _compute_timeout(input_bytes)
    @staticmethod
    def timeout_bounds() -> tuple[int, int, int]:
        return _timeout_bounds()

    @classmethod
    def _claim_plan(cls, plan_id: str) -> None:
        """Atomically check-and-insert *plan_id*; raise if already active."""
        with cls._active_guard:
            if plan_id in cls._active_plans:
                raise ArchiveExecutionError(
                    "ARCHIVE_EXECUTION_IN_PROGRESS", "该归档正在执行，请稍后重试。")
            cls._active_plans.add(plan_id)

    @classmethod
    def _release_plan(cls, plan_id: str) -> None:
        with cls._active_guard:
            cls._active_plans.discard(plan_id)

    def _timeout_for(self, total_input_bytes: int) -> int:
        if self._explicit_timeout is not None:
            if self._explicit_timeout <= 0:
                raise ArchiveExecutionError(
                    "ARCHIVE_EXECUTION_FAILED", "归档超时配置无效。")
            return min(self._explicit_timeout, _timeout_bounds()[2])
        return _compute_timeout(total_input_bytes)

    def execute(self, plan: PlanLike, inventory_files: tuple[PlanEntry, ...],
                source_root: Path, capability: WinRarCapability,
                ) -> WinRarExecutionResult:
        if not capability.available or not capability.executable_path:
            raise ArchiveExecutionError("WINRAR_UNAVAILABLE", "WinRAR 不可用，无法执行归档。")
        self._claim_plan(plan.plan_id)
        staging_dir: Path | None = None
        process: subprocess.Popen[str] | None = None
        try:
            self.staging_root.mkdir(parents=True, exist_ok=True)
            staging_dir = Path(tempfile.mkdtemp(prefix="archive-", dir=self.staging_root))
            if self._staging_initializer is not None:
                try:
                    self._staging_initializer(staging_dir)
                except Exception as error:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise ArchiveExecutionError(
                        "ARCHIVE_EXECUTION_FAILED", "归档临时资源登记失败。",
                    ) from error
            archive_path = staging_dir / f"{plan.archive_base_name}.rar"
            total_bytes = sum(item.size_bytes for item in inventory_files)
            timeout = self._timeout_for(total_bytes)
            args = [capability.executable_path, "a", "-r", "-y", "-inul",
                    f"-v{plan.volume_size_bytes}b", str(archive_path), source_root.name]

            if self._process_runner is not None:
                try:
                    result = self._process_runner(
                        args, cwd=str(source_root.parent), capture_output=True,
                        text=True, timeout=timeout, shell=False)
                except subprocess.TimeoutExpired as error:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise ArchiveExecutionError(
                        "ARCHIVE_EXECUTION_TIMEOUT",
                        f"归档执行超时（{timeout}秒）。") from error
                except (OSError, subprocess.SubprocessError) as error:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    raise ArchiveExecutionError(
                        "ARCHIVE_EXECUTION_FAILED", "归档执行失败。") from error
                if result.returncode != 0:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    return WinRarExecutionResult(
                        plan.plan_id, staging_dir, result.returncode, False,
                        "ARCHIVE_EXECUTION_FAILED", "WinRAR 返回非零退出码。")
                return self._finalize_result(plan, staging_dir)
            # Production path — Popen with verified termination
            try:
                process = subprocess.Popen(
                    args, cwd=str(source_root.parent),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, shell=False)
                win_pid = process.pid  # saved for tree kill even if parent exits
                if self._process_started_callback is not None:
                    try:
                        self._process_started_callback(win_pid)
                    except Exception as error:
                        _terminate_process(process, win_pid)
                        if staging_dir.exists():
                            shutil.rmtree(staging_dir, ignore_errors=True)
                        raise ArchiveExecutionError(
                            "ARCHIVE_EXECUTION_FAILED", "归档进程登记失败。",
                        ) from error
                if self._activity_callback is None and self._cancellation_check is None:
                    process.communicate(timeout=timeout)
                else:
                    try:
                        monitor_owned_process(
                            process, pid=win_pid, args=args, timeout=timeout,
                            staging_dir=staging_dir, terminate=_terminate_process,
                            activity_callback=self._activity_callback,
                            cancellation_check=self._cancellation_check,
                        )
                    except OwnedProcessCancelled as error:
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise ArchiveExecutionError(
                            "ARCHIVE_EXECUTION_CANCELLED",
                            "The archive task was cancelled.",
                        ) from error
                    except OwnedProcessOwnershipLost as error:
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise ArchiveExecutionError(
                            "ARCHIVE_TASK_OWNERSHIP_LOST",
                            "Archive task ownership was lost.",
                        ) from error
                    except OwnedProcessTerminationFailed as error:
                        raise ArchiveExecutionError(
                            "ARCHIVE_EXECUTION_FAILED",
                            "The owned archive process could not be stopped safely.",
                        ) from error
            except OwnedProcessIdleTimeout as error:
                if not _terminate_process(process, win_pid):
                    raise ArchiveExecutionError(
                        "ARCHIVE_EXECUTION_FAILED", "归档进程无法终止，请检查系统进程后重试。")
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                raise ArchiveExecutionError(
                    "ARCHIVE_EXECUTION_TIMEOUT",
                    f"RAR 输出连续 {int(error.timeout)} 秒无增长，归档执行已停止。")
            except subprocess.TimeoutExpired:
                if not _terminate_process(process, win_pid):
                    raise ArchiveExecutionError(
                        "ARCHIVE_EXECUTION_FAILED", "归档进程无法终止，请检查系统进程后重试。")
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                raise ArchiveExecutionError(
                    "ARCHIVE_EXECUTION_TIMEOUT",
                    f"归档执行超时（{timeout}秒，输入 {total_bytes} 字节）。")
            except OSError as error:
                terminated = process is not None and _terminate_process(process, process.pid)
                if not terminated:
                    raise ArchiveExecutionError(
                        "ARCHIVE_EXECUTION_FAILED", "归档进程异常且无法终止，请检查系统进程后重试。")
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                raise ArchiveExecutionError(
                    "ARCHIVE_EXECUTION_FAILED", "归档执行失败。") from error

            if process.returncode != 0:
                shutil.rmtree(staging_dir, ignore_errors=True)
                return WinRarExecutionResult(
                    plan.plan_id, staging_dir, process.returncode, False,
                    "ARCHIVE_EXECUTION_FAILED", "WinRAR 返回非零退出码。")
            return self._finalize_result(plan, staging_dir)
        except ArchiveExecutionError:
            raise
        except OSError as error:
            if staging_dir and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise ArchiveExecutionError(
                "ARCHIVE_EXECUTION_FAILED", "归档临时目录不可用。") from error
        finally:
            self._release_plan(plan.plan_id)

    @staticmethod
    def _finalize_result(plan: PlanLike, staging_dir: Path) -> WinRarExecutionResult:
        # A single physical volume uses `base.rar`; multi-volume output keeps
        # WinRAR's `base.partN.rar` names.
        single_volume = staging_dir / f"{plan.archive_base_name}.rar"
        first_part = staging_dir / f"{plan.archive_base_name}.part1.rar"
        rar_outputs = [
            path for path in staging_dir.iterdir()
            if path.is_file() and path.suffix.casefold() == ".rar"
        ]
        if rar_outputs == [first_part] and not single_volume.exists():
            first_part.rename(single_volume)
        return WinRarExecutionResult(plan.plan_id, staging_dir, 0, False)

    @staticmethod
    def cleanup(result: WinRarExecutionResult) -> None:
        shutil.rmtree(result.staging_dir, ignore_errors=True)
