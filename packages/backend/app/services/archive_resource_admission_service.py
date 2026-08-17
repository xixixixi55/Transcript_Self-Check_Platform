"""Versioned, deployment-owned resource admission for archive work."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchiveAdmissionConfig:
    version: str
    minimum_output_free_bytes: int
    minimum_temporary_free_bytes: int
    maximum_cpu_percent: float
    maximum_io_busy_percent: float
    maximum_winrar_processes: int

    def __post_init__(self) -> None:
        values = (
            self.minimum_output_free_bytes,
            self.minimum_temporary_free_bytes,
        )
        if (
            not self.version
            or any(value < 0 for value in values)
            or self.maximum_winrar_processes <= 0
        ):
            raise ValueError("ARCHIVE_ADMISSION_CONFIG_INVALID")
        if not 0 <= self.maximum_cpu_percent <= 100:
            raise ValueError("ARCHIVE_ADMISSION_CONFIG_INVALID")
        if not 0 <= self.maximum_io_busy_percent <= 100:
            raise ValueError("ARCHIVE_ADMISSION_CONFIG_INVALID")


@dataclass(frozen=True)
class ArchiveResourceSnapshot:
    output_free_bytes: int
    temporary_free_bytes: int
    cpu_percent: float
    io_busy_percent: float | None
    winrar_process_count: int

    def __post_init__(self) -> None:
        if (
            min(
                self.output_free_bytes,
                self.temporary_free_bytes,
                self.winrar_process_count,
            ) < 0
            or not 0 <= self.cpu_percent <= 100
            or (
                self.io_busy_percent is not None
                and not 0 <= self.io_busy_percent <= 100
            )
        ):
            raise ValueError("ARCHIVE_RESOURCE_SNAPSHOT_INVALID")


@dataclass(frozen=True)
class ArchiveAdmissionDecision:
    admitted: bool
    reason: str | None
    config_version: str


class ArchiveResourceAdmissionService:
    """Evaluate supplied server facts; clients cannot override the policy."""

    def __init__(self, config: ArchiveAdmissionConfig) -> None:
        self.config = config

    def evaluate(
        self, snapshot: ArchiveResourceSnapshot, *, input_bytes: int,
    ) -> ArchiveAdmissionDecision:
        if isinstance(input_bytes, bool) or not isinstance(input_bytes, int) or input_bytes < 0:
            return self._deny("ARCHIVE_INPUT_INVALID")
        checks = (
            (
                snapshot.output_free_bytes
                < self.config.minimum_output_free_bytes,
                "ARCHIVE_OUTPUT_SPACE_LOW",
            ),
            (
                snapshot.temporary_free_bytes
                < self.config.minimum_temporary_free_bytes,
                "ARCHIVE_TEMP_SPACE_LOW",
            ),
            (
                snapshot.cpu_percent > self.config.maximum_cpu_percent,
                "ARCHIVE_CPU_BUSY",
            ),
        )
        for denied, reason in checks:
            if denied:
                return self._deny(reason)
        if (
            snapshot.io_busy_percent is not None
            and snapshot.io_busy_percent > self.config.maximum_io_busy_percent
        ):
            return self._deny("ARCHIVE_IO_BUSY")
        if snapshot.winrar_process_count >= self.config.maximum_winrar_processes:
            return self._deny("ARCHIVE_WINRAR_LIMIT")
        return ArchiveAdmissionDecision(True, None, self.config.version)

    def _deny(self, reason: str) -> ArchiveAdmissionDecision:
        return ArchiveAdmissionDecision(False, reason, self.config.version)
