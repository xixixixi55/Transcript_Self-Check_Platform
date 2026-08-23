"""T014 Worker ownership, activity, terminal race, and restart tests."""

from __future__ import annotations

import json
import os
import subprocess
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
    OwnedProcessIdleTimeout,
    monitor_owned_process,
)
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import (  # noqa: E402
    ArchiveExecutionError, WinRarExecutor,
)
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.repository.archive_attempt_recovery_repository import (  # noqa: E402
    _verified_output_metrics,
)
from app.repository.archive_manifest_index_repository import (  # noqa: E402
    ArchiveManifestRepositoryError,
)
from app.repository.runtime_paths import get_runtime_paths  # noqa: E402
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


def test_verified_output_metrics_use_all_manifest_parts() -> None:
    intent = {
        "public_manifest_json": json.dumps({
            "parts": [
                {"size_bytes": 4_000_000_000},
                {"size_bytes": 107_749_764},
            ],
        }),
    }

    assert _verified_output_metrics(intent) == (4_107_749_764, 2)


@pytest.mark.parametrize("parts", [[], [None], [{"size_bytes": 0}]])
def test_verified_output_metrics_reject_invalid_parts(parts) -> None:
    with pytest.raises(
        WorkbenchPersistenceError,
        match="ARCHIVE_COMPLETION_EVIDENCE_INVALID",
    ):
        _verified_output_metrics({
            "public_manifest_json": json.dumps({"parts": parts}),
        })


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
    assert attempts.failed == [(
        "SYNTHETIC-WORKER-ATTEMPT-1", "ARCHIVE_CANCELLED",
    )]
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_TASK_OWNERSHIP_LOST"):
        progress.advance(owned.task_id, owned.owner_token, "integrity")


def test_cancel_between_claim_and_worker_start_is_not_ownership_loss(
    setup, monkeypatch,
) -> None:
    _, tasks, progress, tmp_path = setup
    queue(tasks)
    owned = claim(tasks)
    attempts = FakeAttemptService()
    current = tasks.get(owned.task_id)
    cancelling = progress.request_cancel(
        current["task_id"], current["revision"],
    )

    monkeypatch.setattr(
        "app.services.archive_worker_service.execute_archive",
        lambda *_args, **_kwargs: pytest.fail(
            "cancelled preparation must not start archive execution"
        ),
    )
    result = ArchiveWorkerService(tasks, progress).run(
        owned, work_item(tmp_path, attempts),
    )

    assert cancelling["revision"] != owned.revision
    assert result["status"] == "cancelled"
    assert result["error_code"] is None
    assert attempts.failed == [(
        "SYNTHETIC-WORKER-ATTEMPT-1", "ARCHIVE_CANCELLED",
    )]


def test_replaced_owner_token_is_still_ownership_loss(setup, monkeypatch) -> None:
    _, tasks, progress, tmp_path = setup
    queue(tasks)
    owned = claim(tasks)
    attempts = FakeAttemptService()
    current = tasks.get(owned.task_id)
    tasks.update_state(owned.task_id, {
        "process_binding": {
            **current["process_binding"],
            "process_tree_id": "SYNTHETIC-REPLACEMENT-OWNER",
        },
    }, current["revision"])
    monkeypatch.setattr(
        "app.services.archive_worker_service.execute_archive",
        lambda *_args, **_kwargs: pytest.fail("stale owner must not execute"),
    )

    with pytest.raises(
        WorkbenchPersistenceError, match="ARCHIVE_TASK_OWNERSHIP_LOST",
    ):
        ArchiveWorkerService(tasks, progress).run(
            owned, work_item(tmp_path, attempts),
        )

    assert attempts.repository.status == "accepted"


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


def test_worker_reports_untrusted_archive_directory_actionably(setup, monkeypatch) -> None:
    _, tasks, progress, tmp_path = setup
    queue(tasks)
    owned = claim(tasks)
    attempts = FakeAttemptService()

    monkeypatch.setattr(
        "app.services.archive_worker_service.execute_archive",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ArchiveManifestRepositoryError("ARCHIVE_INDEX_UNTRUSTED")
        ),
    )

    result = ArchiveWorkerService(tasks, progress).run(
        owned, work_item(tmp_path, attempts),
    )

    assert result["status"] == "failed_retryable"
    assert result["error_code"] == "ARCHIVE_INDEX_UNTRUSTED"
    assert "新空白目录" in result["error_summary"]
    assert "现有文件不会被修改" in result["error_summary"]
    assert attempts.failed == [(
        "SYNTHETIC-WORKER-ATTEMPT-1", "ARCHIVE_INDEX_UNTRUSTED",
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
    queued = tasks.update_state(queued["task_id"], {
        "process_binding": {
            "staging_asset_id": "SYNTHETIC-MISSING-OLD-ATTEMPT",
        },
    }, queued["revision"])
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
    assert get_runtime_paths().output_root.resolve(strict=False) in (
        services.lifecycle.artifacts.archive_output_roots
    )
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


class PollingProcess:
    def poll(self):
        return None

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired(["WinRAR.exe"], timeout)

    def communicate(self):
        return ("", "")


def test_monitor_allows_output_growth_until_hard_deadline(tmp_path: Path) -> None:
    output_sizes = iter([1, 1, 2, 3, 4])
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 0.0, 0.5, 1.5, 2.5],
    ):
        with pytest.raises(subprocess.TimeoutExpired) as failure:
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=2,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=2,
                output_size_probe=lambda _root: next(output_sizes),
            )
    assert not isinstance(failure.value, OwnedProcessIdleTimeout)


def test_monitor_times_out_after_rar_output_stalls(tmp_path: Path) -> None:
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 0.0, 1.0, 2.0],
    ):
        with pytest.raises(OwnedProcessIdleTimeout) as failure:
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=60,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=2, output_size_probe=lambda _root: 1,
            )
    assert failure.value.timeout == 2


def test_monitor_does_not_treat_output_shrink_as_growth(tmp_path: Path) -> None:
    output_sizes = iter([10, 5, 5])
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 0.0, 1.0, 2.0],
    ):
        with pytest.raises(OwnedProcessIdleTimeout):
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=60,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=2,
                output_size_probe=lambda _root: next(output_sizes),
            )


def test_monitor_waits_for_hard_deadline_before_first_rar_output(
    tmp_path: Path,
) -> None:
    output_sizes = iter([0, 0, 0])
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 0.5, 2.0],
    ):
        with pytest.raises(subprocess.TimeoutExpired) as failure:
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=2,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=1,
                output_size_probe=lambda _root: next(output_sizes),
            )
    assert not isinstance(failure.value, OwnedProcessIdleTimeout)


def test_monitor_hard_deadline_wins_when_deadlines_are_equal(
    tmp_path: Path,
) -> None:
    output_sizes = iter([1, 1])
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 0.0, 2.0],
    ):
        with pytest.raises(subprocess.TimeoutExpired) as failure:
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=2,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=2,
                output_size_probe=lambda _root: next(output_sizes),
            )
    assert not isinstance(failure.value, OwnedProcessIdleTimeout)


def test_environment_hard_deadline_wins_when_poll_crosses_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIJI_ARCHIVE_TIMEOUT_SECONDS", "1")
    hard_timeout = WinRarExecutor.compute_timeout(10_000_000_000)
    output_sizes = iter([1, 1])
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 0.0, 3.0],
    ):
        with pytest.raises(subprocess.TimeoutExpired) as failure:
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=hard_timeout,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=2,
                output_size_probe=lambda _root: next(output_sizes),
            )
    assert hard_timeout == 1
    assert not isinstance(failure.value, OwnedProcessIdleTimeout)


def test_monitor_starts_idle_clock_when_first_rar_output_appears(
    tmp_path: Path,
) -> None:
    output_sizes = iter([0, 5, 5, 5])
    process = PollingProcess()
    with mock.patch(
        "app.repository.winrar_process_monitor.time.monotonic",
        side_effect=[0.0, 1.0, 2.9, 3.0],
    ):
        with pytest.raises(OwnedProcessIdleTimeout):
            monitor_owned_process(
                process, pid=4242, args=["WinRAR.exe"], timeout=60,
                staging_dir=tmp_path, terminate=lambda *_: True,
                activity_callback=None, cancellation_check=None,
                idle_timeout_seconds=2,
                output_size_probe=lambda _root: next(output_sizes),
            )


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
        size_bytes=input_path.stat().st_size,
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


def test_executor_idle_timeout_terminates_and_cleans_owned_staging(
    tmp_path: Path,
) -> None:
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
        tmp_path / "staging", activity_callback=lambda _root: None,
    )
    plan = SimpleNamespace(
        plan_id="SYNTHETIC-IDLE-PLAN",
        archive_base_name="SYNTHETIC-ARCHIVE",
        volume_size_bytes=1_000,
    )
    entry = SimpleNamespace(
        relative_path="SYNTHETIC.bin", absolute_path=input_path,
        size_bytes=input_path.stat().st_size,
    )
    capability = WinRarCapability(
        True, "configured", "WinRAR.exe", "7.23", True,
    )
    with mock.patch(
        "app.repository.winrar_executor_repository.subprocess.Popen",
        return_value=process,
    ), mock.patch(
        "app.repository.winrar_executor_repository.monitor_owned_process",
        side_effect=OwnedProcessIdleTimeout(["WinRAR.exe"], 600),
    ), mock.patch(
        "app.repository.winrar_executor_repository._kill_process_tree_impl",
        return_value=True,
    ) as tree_kill:
        with pytest.raises(ArchiveExecutionError) as captured:
            executor.execute(plan, (entry,), source, capability)
    assert captured.value.code == "ARCHIVE_EXECUTION_TIMEOUT"
    assert "600" in captured.value.safe_message
    tree_kill.assert_called_once_with(4242)
    assert list((tmp_path / "staging").glob("archive-*")) == []


def test_executor_idle_timeout_keeps_staging_when_termination_fails(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    input_path = source / "SYNTHETIC.bin"
    input_path.write_bytes(b"SYNTHETIC")
    process = WaitingProcess()
    process.pid = 4242
    executor = WinRarExecutor(
        tmp_path / "staging",
        staging_initializer=lambda root: (root / "partial.rar").write_bytes(b"x"),
        activity_callback=lambda _root: None,
    )
    plan = SimpleNamespace(
        plan_id="SYNTHETIC-IDLE-TERMINATION-FAILURE",
        archive_base_name="SYNTHETIC-ARCHIVE",
        volume_size_bytes=1_000,
    )
    entry = SimpleNamespace(
        relative_path="SYNTHETIC.bin", absolute_path=input_path,
        size_bytes=input_path.stat().st_size,
    )
    capability = WinRarCapability(
        True, "configured", "WinRAR.exe", "7.23", True,
    )
    with mock.patch(
        "app.repository.winrar_executor_repository.subprocess.Popen",
        return_value=process,
    ), mock.patch(
        "app.repository.winrar_executor_repository.monitor_owned_process",
        side_effect=OwnedProcessIdleTimeout(["WinRAR.exe"], 600),
    ), mock.patch(
        "app.repository.winrar_executor_repository._terminate_process",
        return_value=False,
    ) as terminate:
        with pytest.raises(ArchiveExecutionError) as captured:
            executor.execute(plan, (entry,), source, capability)
    assert captured.value.code == "ARCHIVE_EXECUTION_FAILED"
    terminate.assert_called_once_with(process, 4242)
    staging_dirs = list((tmp_path / "staging").glob("archive-*"))
    assert len(staging_dirs) == 1
    assert (staging_dirs[0] / "partial.rar").read_bytes() == b"x"
