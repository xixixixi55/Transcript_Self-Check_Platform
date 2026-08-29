"""跨平台归档资源采样的 SYNTHETIC/TEST 覆盖测试。"""

from __future__ import annotations

import logging
import os
import sys
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive import archive_runtime_resource_service as resource_module  # noqa: E402
from app.repository import (  # noqa: E402
    CaseShellRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.services.archive.archive_resource_admission_service import (  # noqa: E402
    ArchiveAdmissionConfig,
    ArchiveResourceAdmissionService,
    ArchiveResourceSnapshot,
)
from app.services.archive.archive_runtime_resource_service import (  # noqa: E402
    ArchiveRuntimeResourceProvider, build_archive_admission_config,
)


WindowsSdiskio = namedtuple(
    "sdiskio",
    "read_count write_count read_bytes write_bytes read_time write_time",
)


def test_default_admission_does_not_cap_archives_at_135gb(monkeypatch) -> None:
    monkeypatch.delenv("BIJI_ARCHIVE_MAX_INPUT_BYTES", raising=False)

    config = build_archive_admission_config()

    assert config.maximum_input_bytes == (2**53 - 1)
    assert config.maximum_input_bytes > 225 * 1024**3


def test_operator_can_still_apply_an_explicit_input_safety_limit(monkeypatch) -> None:
    monkeypatch.setenv("BIJI_ARCHIVE_MAX_INPUT_BYTES", "123456789")

    assert build_archive_admission_config().maximum_input_bytes == 123456789


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-WINDOWS-RESOURCE"),
        "SYNTHETIC-WINDOWS-RESOURCE",
    )
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-WINDOWS-RESOURCE-CASE",
        "case_name": "SYNTHETIC/TEST/WINDOWS-RESOURCE",
        "case_summary": "SYNTHETIC/TEST",
        "source_id": "SYNTHETIC-WINDOWS-SOURCE",
        "parse_task_id": "SYNTHETIC-WINDOWS-PARSE",
    })
    return database


def test_none_disk_io_counters_is_explicitly_unavailable_and_logged_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    provider = ArchiveRuntimeResourceProvider(tmp_path / "SYNTHETIC-OUTPUT")
    with patch.object(resource_module.psutil, "disk_io_counters", return_value=None):
        with caplog.at_level(logging.WARNING, logger=resource_module.logger.name):
            assert provider._io_busy_percent() is None
            assert provider._io_busy_percent() is None

    diagnostics = [
        record for record in caplog.records
        if "ARCHIVE_IO_METRIC_UNAVAILABLE" in record.getMessage()
    ]
    assert len(diagnostics) == 1


def test_windows_sdiskio_without_busy_time_does_not_fake_zero_percent(
    tmp_path: Path,
) -> None:
    provider = ArchiveRuntimeResourceProvider(tmp_path / "SYNTHETIC-OUTPUT")
    counters = WindowsSdiskio(1, 2, 3, 4, 5, 6)
    with patch.object(
        resource_module.psutil, "disk_io_counters", return_value=counters,
    ):
        assert provider._io_busy_percent() is None
    assert not hasattr(counters, "busy_time")
    assert provider._last_io_busy_ms is None
    assert provider._last_observed_at is None


def test_busy_time_sampling_preserves_initial_zero_delta_and_reset_behavior(
    tmp_path: Path,
) -> None:
    provider = ArchiveRuntimeResourceProvider(tmp_path / "SYNTHETIC-OUTPUT")
    counters = iter([
        type("LinuxCounters", (), {"busy_time": 100})(),
        type("LinuxCounters", (), {"busy_time": 150})(),
        type("LinuxCounters", (), {"busy_time": 10})(),
        type("LinuxCounters", (), {"busy_time": 20})(),
    ])
    observed_at = iter([10.0, 10.0, 11.0, 12.0])
    with patch.object(
        resource_module.psutil, "disk_io_counters", side_effect=lambda: next(counters),
    ), patch.object(
        resource_module.time, "monotonic", side_effect=lambda: next(observed_at),
    ):
        assert provider._io_busy_percent() == 0.0
        assert provider._io_busy_percent() == 100.0
        assert provider._io_busy_percent() == 0.0
        assert provider._io_busy_percent() == 1.0


def test_unavailable_io_gate_is_skipped_but_other_admission_gates_remain() -> None:
    admission = ArchiveResourceAdmissionService(ArchiveAdmissionConfig(
        "SYNTHETIC-RESOURCE-V1", 100, 100, 80, 20, 1_000, 2,
    ))
    snapshot = ArchiveResourceSnapshot(1_000, 1_000, 10, None, 0)
    decision = admission.evaluate(snapshot, input_bytes=100)
    assert decision.admitted

    assert not admission.evaluate(
        ArchiveResourceSnapshot(1_000, 1_000, 81, None, 0), input_bytes=100,
    ).admitted
    assert not admission.evaluate(
        ArchiveResourceSnapshot(99, 1_000, 10, None, 0), input_bytes=100,
    ).admitted
    assert not admission.evaluate(
        ArchiveResourceSnapshot(1_000, 1_000, 10, None, 2), input_bytes=100,
    ).admitted


def test_scheduler_can_claim_with_unavailable_optional_io_metric(database) -> None:
    """调度器不得因缺少可选指标而永久等待。"""
    from app.repository.archive.archive_task_repository import ArchiveTaskRepository
    from app.services.archive.archive_scheduler_service import ArchiveSchedulerService

    tasks = ArchiveTaskRepository(database)
    task = tasks.create({
        "task_id": "SYNTHETIC-WINDOWS-RESOURCE-TASK",
        "case_id": "SYNTHETIC-WINDOWS-RESOURCE-CASE",
        "created_at": "2026-07-31T01:00:00+00:00",
        "updated_at": "2026-07-31T01:00:00+00:00",
        "counters": {"input_bytes": 100},
        "process_binding": {"staging_asset_id": "SYNTHETIC-WINDOWS-ATTEMPT"},
    })
    scheduler = ArchiveSchedulerService(
        tasks,
        ArchiveResourceAdmissionService(ArchiveAdmissionConfig(
            "SYNTHETIC-WINDOWS-V1", 0, 0, 100, 0, 1_000, 1,
        )),
    )
    claim = scheduler.claim_next(ArchiveResourceSnapshot(1_000, 1_000, 0, None, 0))
    assert claim is not None
    assert claim.task_id == task["task_id"]
