"""Typed execution models shared by the WinRAR adapter and callers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


class ArchiveExecutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


class PlanEntry(Protocol):
    relative_path: str
    absolute_path: Path
    size_bytes: int


class PlanLike(Protocol):
    plan_id: str
    archive_base_name: str
    archive_mode: str
    volume_size_bytes: int | None


@dataclass(frozen=True)
class WinRarExecutionResult:
    plan_id: str
    staging_dir: Path
    returncode: int
    timed_out: bool
    diagnostic_code: str | None = None
    safe_output: str = ""


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
StagingInitializer = Callable[[Path], None]
ProcessStartedCallback = Callable[[int], None]
