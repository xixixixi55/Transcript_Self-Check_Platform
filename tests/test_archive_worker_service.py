"""T014 Worker ownership, activity, terminal race, and restart tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    ArchiveTaskRepository,
    CaseShellRepository,
    ResourceSnapshotRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.winrar_process_monitor import (  # noqa: E402
    OwnedProcessCancelled,
    monitor_owned_process,
)
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import (  # noqa: E402
    ArchiveExecutionError, WinRarExecutor,
)
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_progress_service import ArchiveProgressService  # noqa: E402
from app.services.archive_manifest_access_service import ArchiveGateError  # noqa: E402
from app.services.export_gate_service import ExportGateIssue  # noqa: E402
from app.services.archive_resource_admission_service import (  # noqa: E402
    ArchiveAdmissionConfig,
    ArchiveResourceAdmissionService,
    ArchiveResourceSnapshot,
)
from app.services.archive_scheduler_service import ArchiveSchedulerService  # noqa: E402
from app.services.archive_worker_service import (  # noqa: E402
    ArchiveWorkItem,
    ArchiveWorkerService,
)
from app.services.workbench_factory_service import build_workbench_services  # noqa: E402

CASE_ID = "SYNTHETIC-T014-WORKER-CASE"


@pytest.fixture()
def setup(tmp_path: Path):
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-T014-WORKER"),
        "SYNTHETIC-T014-WORKER",
    )
    CaseShellRepository(database).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/Worker",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    tasks = ArchiveTaskRepository(database)
    progress = ArchiveProgressService(
        tasks, ResourceSnapshotRepository(database, interval_seconds=15),
    )
    return database, tasks, progress, tmp_path


def queue(tasks, number: int = 1):
    return tasks.create({
        "task_id": f"SYNTHETIC-WORKER-TASK-{number}",
        "case_id": CASE_ID,
        "counters": {"input_bytes": 10},
        "process_binding": {
            "staging_asset_id": f"SYNTHETIC-WORKER-ATTEMPT-{number}",
        },
    })


def claim(tasks):
    admission = ArchiveResourceAdmissionService(ArchiveAdmissionConfig(
        "SYNTHETIC-V1", 0, 0, 100, 100, 1_000, 6,
    ))
    scheduler = ArchiveSchedulerService(tasks, admission)
    return scheduler.claim_next(ArchiveResourceSnapshot(100, 100, 0, 0, 0))


class FakeAttemptRepository:
    def __init__(self, status: str = "accepted") -> None:
        self.status = status

    def get_internal(self, _attempt_id: str):
        return {"status": self.status}


class FakeAttemptService:
    def __init__(self, status: str = "accepted") -> None:
        self.repository = FakeAttemptRepository(status)
        self.failed = []
        self.recovered = 0

    def start(self, _attempt_id: str) -> None:
        self.repository.status = "running"

    def fail(self, attempt_id: str, code: str) -> None:
        self.failed.append((attempt_id, code))
        self.repository.status = "failed"

    def recover_after_restart(self) -> list[str]:
        self.recovered += 1
        return []


def work_item(tmp_path: Path, attempts: FakeAttemptService):
    return ArchiveWorkItem(
        "SYNTHETIC-FORMAL-CONTEXT",
        {"introduction": {"case_summary": "SYNTHETIC-ARCHIVE"}},
        str(tmp_path / "output"),
        attempts,  # type: ignore[arg-type]
    )


def test_worker_drives_exact_gates_and_activity(setup, monkeypatch) -> None:
    _, tasks, progress, tmp_path = setup
    queue(tasks)
    owned = claim(tasks)
    attempts = FakeAttemptService()

    def execute(_context, _report, **kwargs):
        root = tmp_path / "owned-staging"
        root.mkdir()
        for stage in (
            "inventory", "preflight_verified", "winrar", "integrity",
            "integrity_verified", "md5", "manifest",
        ):
            kwargs["stage_observer"](stage)
            if stage == "winrar":
                (root / "SYNTHETIC-ARCHIVE.part1.rar").write_bytes(b"SYNTHETIC")
                kwargs["activity_observer"](root)
                assert kwargs["cancellation_check"]() is False
        return SimpleNamespace(reused=False, manifest_id="SYNTHETIC-MANIFEST")

    monkeypatch.setattr("app.services.archive_worker_service.execute_archive", execute)
    result = ArchiveWorkerService(tasks, progress).run(
        owned, work_item(tmp_path, attempts),
    )
    assert result["status"] == "succeeded"
    assert result["stage"] == "completed"
    assert result["percent"] == 100
    assert result["output_volume_count"] == 1
    assert result["output_bytes"] == len(b"SYNTHETIC")


def test_cancel_wins_before_completion_and_stale_worker_cannot_write(
    setup, monkeypatch,
) -> None:
    _, tasks, progress, tmp_path = setup
    queue(tasks)
    owned = claim(tasks)
    attempts = FakeAttemptService()

    def execute(_context, _report, **kwargs):
        for stage in ("inventory", "preflight_verified", "winrar"):
            kwargs["stage_observer"](stage)
        current = tasks.get(owned.task_id)
        progress.request_cancel(current["task_id"], current["revision"])
        assert kwargs["cancellation_check"]() is True
        raise RuntimeError("SYNTHETIC cancellation race")

    monkeypatch.setattr("app.services.archive_worker_service.execute_archive", execute)
    result = ArchiveWorkerService(tasks, progress).run(
        owned, work_item(tmp_path, attempts),
    )
    assert result["status"] == "cancelled"
    assert result["percent"] == 30
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_TASK_OWNERSHIP_LOST"):
        progress.advance(owned.task_id, owned.owner_token, "integrity")


def test_worker_failure_preserves_last_real_milestone(setup, monkeypatch) -> None:
    _, tasks, progress, tmp_path = setup
    queue(tasks)
    owned = claim(tasks)
    attempts = FakeAttemptService()

    def execute(_context, _report, **kwargs):
        for stage in ("inventory", "preflight_verified", "winrar"):
            kwargs["stage_observer"](stage)
        raise ArchiveGateError((ExportGateIssue(
            "ARCHIVE_EXECUTION_FAILED", "archive",
            "Synthetic archive execution failed.",
        ),))

    monkeypatch.setattr("app.services.archive_worker_service.execute_archive", execute)
    result = ArchiveWorkerService(tasks, progress).run(
        owned, work_item(tmp_path, attempts),
    )
    assert result["status"] == "failed_retryable"
    assert result["stage"] == "winrar"
    assert result["percent"] == 30
    assert result["error_summary"] == "Synthetic archive execution failed."
    assert attempts.failed == [(
        "SYNTHETIC-WORKER-ATTEMPT-1", "ARCHIVE_EXECUTION_FAILED",
    )]


def test_restart_waits_and_retry_uses_new_task_and_attempt(setup) -> None:
    _, tasks, progress, tmp_path = setup
    old = queue(tasks)
    old_claim = claim(tasks)
    attempts = FakeAttemptService(status="running")
    recovered = ArchiveWorkerService(tasks, progress).recover_after_restart(
        attempts,  # type: ignore[arg-type]
    )
    assert attempts.recovered == 1
    assert recovered[0]["status"] == "interrupted"
    assert recovered[0]["worker_state"] == "waiting_reclaim"
    assert recovered[0]["task_id"] == old["task_id"]
    new = queue(tasks, 2)
    new_claim = claim(tasks)
    assert new_claim.task_id == new["task_id"]
    assert new_claim.attempt_id == "SYNTHETIC-WORKER-ATTEMPT-2"
    assert new_claim.owner_token != old_claim.owner_token
    assert tasks.get(old["task_id"])["status"] == "interrupted"


def test_composition_root_keeps_archive_recovery_with_archive_worker(setup) -> None:
    database, tasks, _, _ = setup
    queued = queue(tasks)
    tasks.claim(
        queued["task_id"], owner_token="SYNTHETIC-RESTART-OWNER",
        attempt_id="SYNTHETIC-MISSING-OLD-ATTEMPT",
        expected_revision=queued["revision"], max_running=6,
    )
    config = ArchiveAdmissionConfig(
        "SYNTHETIC-DEPLOYMENT-V1", 0, 0, 100, 100, 1_000, 6,
    )
    services = build_workbench_services(database, config)
    assert services.archive_scheduler is not None
    assert services.archive_worker is not None
    services.tasks.recover_after_restart(include_archive=False)
    recovered = services.archive_worker.recover_after_restart(
        services.archive_attempts,
    )
    assert recovered[0]["status"] == "interrupted"
    assert recovered[0]["worker_state"] == "waiting_reclaim"


class WaitingProcess:
    def poll(self):
        return None

    def wait(self, timeout=None):
        raise AssertionError("cancel must be checked before waiting")

    def communicate(self):
        raise AssertionError("cancelled process must not communicate")


def test_process_cancel_targets_only_owned_pid(tmp_path: Path) -> None:
    process = WaitingProcess()
    calls = []
    with pytest.raises(OwnedProcessCancelled):
        monitor_owned_process(
            process, pid=4242, args=["WinRAR.exe"], timeout=5,
            staging_dir=tmp_path,
            terminate=lambda candidate, pid: calls.append((candidate, pid)) or True,
            activity_callback=None, cancellation_check=lambda: True,
        )
    assert calls == [(process, 4242)]


def test_executor_cancel_cleans_only_its_owned_staging(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    input_path = source / "SYNTHETIC.bin"
    input_path.write_bytes(b"SYNTHETIC")
    process = WaitingProcess()
    process.pid = 4242
    process.dead = False
    process.poll = lambda: 0 if process.dead else None
    process.wait = lambda timeout=None: setattr(process, "dead", True) or 0
    executor = WinRarExecutor(
        tmp_path / "staging", cancellation_check=lambda: True,
    )
    plan = SimpleNamespace(
        plan_id="SYNTHETIC-CANCEL-PLAN",
        archive_base_name="SYNTHETIC-ARCHIVE",
        volume_size_bytes=1_000,
    )
    entry = SimpleNamespace(
        relative_path="SYNTHETIC.bin", absolute_path=input_path,
    )
    capability = WinRarCapability(
        True, "configured", "WinRAR.exe", "7.23", True,
    )
    with mock.patch(
        "app.repository.winrar_executor_repository.subprocess.Popen",
        return_value=process,
    ), mock.patch(
        "app.repository.winrar_executor_repository._kill_process_tree_impl",
        return_value=True,
    ) as tree_kill:
        with pytest.raises(ArchiveExecutionError) as captured:
            executor.execute(plan, (entry,), source, capability)
    assert captured.value.code == "ARCHIVE_EXECUTION_CANCELLED"
    tree_kill.assert_called_once_with(4242)
    assert list((tmp_path / "staging").glob("archive-*")) == []
