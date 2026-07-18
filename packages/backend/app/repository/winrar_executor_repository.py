"""Safe WinRAR process execution into an isolated staging directory."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .winrar_discovery_repository import WinRarCapability


class ArchiveExecutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


class PlanEntry(Protocol):
    relative_path: str
    absolute_path: Path


class PlanLike(Protocol):
    plan_id: str
    archive_base_name: str
    volume_size_bytes: int


@dataclass(frozen=True)
class WinRarExecutionResult:
    plan_id: str
    staging_dir: Path
    returncode: int
    timed_out: bool
    diagnostic_code: str | None = None
    safe_output: str = ""


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


class WinRarExecutor:
    """The only component that constructs and invokes the WinRAR argument array."""

    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(
        self,
        staging_root: str | os.PathLike[str],
        *,
        timeout_seconds: int = 300,
        process_runner: ProcessRunner = subprocess.run,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.timeout_seconds = timeout_seconds
        self.process_runner = process_runner

    @classmethod
    def _lock_for(cls, plan_id: str) -> threading.Lock:
        with cls._locks_guard:
            return cls._locks.setdefault(plan_id, threading.Lock())

    def execute(
        self,
        plan: PlanLike,
        inventory_files: tuple[PlanEntry, ...],
        source_root: Path,
        capability: WinRarCapability,
    ) -> WinRarExecutionResult:
        if not capability.available or not capability.executable_path:
            raise ArchiveExecutionError("WINRAR_UNAVAILABLE", "WinRAR 不可用，无法执行归档。")
        lock = self._lock_for(plan.plan_id)
        if not lock.acquire(blocking=False):
            raise ArchiveExecutionError("ARCHIVE_EXECUTION_IN_PROGRESS", "该归档正在执行，请稍后重试。")
        staging_dir: Path | None = None
        try:
            self.staging_root.mkdir(parents=True, exist_ok=True)
            staging_dir = Path(tempfile.mkdtemp(prefix="archive-", dir=self.staging_root))
            list_path = staging_dir / "source-list.txt"
            list_path.write_text(
                "\n".join(item.relative_path for item in inventory_files) + "\n",
                encoding="utf-8",
            )
            archive_path = staging_dir / f"{plan.archive_base_name}.rar"
            # a/r/ep1: create recursive RAR and retain paths relative to source_root;
            # -v...b: exact decimal byte volume size; -inul/-y: no GUI or prompts.
            args = [
                capability.executable_path,
                "a", "-r", "-ep1", "-y", "-inul",
                f"-v{plan.volume_size_bytes}b",
                str(archive_path), f"@{list_path}",
            ]
            try:
                result = self.process_runner(
                    args, cwd=str(source_root), capture_output=True,
                    text=True, timeout=self.timeout_seconds, shell=False,
                )
            except subprocess.TimeoutExpired as error:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise ArchiveExecutionError("ARCHIVE_EXECUTION_FAILED", "归档执行超时。") from error
            except (OSError, subprocess.SubprocessError) as error:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise ArchiveExecutionError("ARCHIVE_EXECUTION_FAILED", "归档执行失败。") from error
            if result.returncode != 0:
                shutil.rmtree(staging_dir, ignore_errors=True)
                return WinRarExecutionResult(
                    plan.plan_id, staging_dir, result.returncode, False,
                    "ARCHIVE_EXECUTION_FAILED", "WinRAR 返回非零退出码。",
                )
            # RAR emits `base.rar` when a volume request still fits in one
            # volume, while multi-volume output already uses `base.partN.rar`.
            # Normalize that one-volume result to the project's stable public
            # naming contract without touching historical output.
            single_volume = staging_dir / f"{plan.archive_base_name}.rar"
            first_part = staging_dir / f"{plan.archive_base_name}.part1.rar"
            if single_volume.is_file() and not first_part.exists():
                rar_outputs = [
                    path for path in staging_dir.iterdir()
                    if path.is_file() and path.suffix.casefold() == ".rar"
                ]
                if rar_outputs == [single_volume]:
                    single_volume.rename(first_part)
            list_path.unlink(missing_ok=True)
            return WinRarExecutionResult(plan.plan_id, staging_dir, 0, False)
        except ArchiveExecutionError:
            raise
        except OSError as error:
            if staging_dir:
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise ArchiveExecutionError("ARCHIVE_EXECUTION_FAILED", "归档临时目录不可用。") from error
        finally:
            lock.release()

    @staticmethod
    def cleanup(result: WinRarExecutionResult) -> None:
        shutil.rmtree(result.staging_dir, ignore_errors=True)
