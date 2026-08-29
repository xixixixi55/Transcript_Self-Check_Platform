"""读取部署拥有的归档准入资源事实。"""

from __future__ import annotations

import os
import logging
import shutil
import tempfile
import time
from pathlib import Path

import psutil

from ...repository.archive.archive_input_repository import MAX_SAFE_INTEGER
from .archive_resource_admission_service import (
    ArchiveAdmissionConfig,
    ArchiveResourceSnapshot,
)

logger = logging.getLogger(__name__)


def build_archive_admission_config() -> ArchiveAdmissionConfig:
    return ArchiveAdmissionConfig(
        version="archive-admission-v1",
        minimum_output_free_bytes=_nonnegative_int_env(
            "BIJI_ARCHIVE_MIN_OUTPUT_FREE_BYTES", 0,
        ),
        minimum_temporary_free_bytes=_nonnegative_int_env(
            "BIJI_ARCHIVE_MIN_TEMP_FREE_BYTES", 0,
        ),
        maximum_cpu_percent=_bounded_float_env(
            "BIJI_ARCHIVE_MAX_CPU_PERCENT", 95.0,
        ),
        maximum_io_busy_percent=_bounded_float_env(
            "BIJI_ARCHIVE_MAX_IO_BUSY_PERCENT", 95.0,
        ),
        maximum_input_bytes=_positive_int_env(
            "BIJI_ARCHIVE_MAX_INPUT_BYTES", MAX_SAFE_INTEGER,
        ),
        maximum_winrar_processes=_positive_int_env(
            "BIJI_ARCHIVE_MAX_WINRAR_PROCESSES", 6,
        ),
    )


def positive_float_env(name: str, default: float) -> float:
    value = float(os.environ.get(name, str(default)))
    if value <= 0:
        raise ValueError("ARCHIVE_RUNTIME_CONFIG_INVALID")
    return value


def _nonnegative_int_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < 0:
        raise ValueError("ARCHIVE_ADMISSION_CONFIG_INVALID")
    return value


def _positive_int_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value <= 0:
        raise ValueError("ARCHIVE_ADMISSION_CONFIG_INVALID")
    return value


def _bounded_float_env(name: str, default: float) -> float:
    value = float(os.environ.get(name, str(default)))
    if not 0 <= value <= 100:
        raise ValueError("ARCHIVE_ADMISSION_CONFIG_INVALID")
    return value


class ArchiveRuntimeResourceProvider:
    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)
        self._last_io_busy_ms: int | None = None
        self._last_observed_at: float | None = None
        self._io_unavailable_logged = False

    def snapshot(self) -> ArchiveResourceSnapshot:
        self.output_root.mkdir(parents=True, exist_ok=True)
        output_free = shutil.disk_usage(self.output_root).free
        temporary_free = shutil.disk_usage(tempfile.gettempdir()).free
        return ArchiveResourceSnapshot(
            output_free_bytes=output_free,
            temporary_free_bytes=temporary_free,
            cpu_percent=max(0.0, min(100.0, psutil.cpu_percent(interval=None))),
            io_busy_percent=self._io_busy_percent(),
            winrar_process_count=self._winrar_process_count(),
        )

    def _io_busy_percent(self) -> float | None:
        now = time.monotonic()
        try:
            counters = psutil.disk_io_counters()
        except (OSError, psutil.Error):
            return self._unavailable_io_metric()
        busy_value = getattr(counters, "busy_time", None)
        if busy_value is None:
            return self._unavailable_io_metric()
        busy_ms = int(busy_value)
        result = 0.0
        if self._last_io_busy_ms is not None and self._last_observed_at is not None:
            elapsed_ms = max((now - self._last_observed_at) * 1000, 1)
            result = (max(0, busy_ms - self._last_io_busy_ms) / elapsed_ms) * 100
        self._last_io_busy_ms = busy_ms
        self._last_observed_at = now
        return max(0.0, min(100.0, result))

    def _unavailable_io_metric(self) -> None:
        self._last_io_busy_ms = None
        self._last_observed_at = None
        if not self._io_unavailable_logged:
            logger.warning(
                "ARCHIVE_IO_METRIC_UNAVAILABLE: skipping optional I/O busy gate."
            )
            self._io_unavailable_logged = True
        return None

    @staticmethod
    def _winrar_process_count() -> int:
        count = 0
        for process in psutil.process_iter(("name",)):
            try:
                name = str(process.info.get("name") or "").casefold()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            if name in {"rar.exe", "winrar.exe"}:
                count += 1
        return count
