"""Application-lifespan coverage for the persistent archive runtime."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.main import create_app  # noqa: E402
from app.repository import (  # noqa: E402
    ArchiveTaskRepository,
    ResourceSnapshotRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.archive_manifest_repository import ArchiveManifestRepository  # noqa: E402
from app.services.archive_attempt_service import ArchiveAttemptService  # noqa: E402
from app.services.archive_attempt_completion_service import record_attempt_completion  # noqa: E402
from app.services.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
from app.services.archive_progress_service import ArchiveProgressService  # noqa: E402
from app.services.archive_resource_admission_service import (  # noqa: E402
    ArchiveAdmissionConfig,
    ArchiveResourceAdmissionService,
    ArchiveResourceSnapshot,
)
from app.services.archive_runtime_coordinator_service import (  # noqa: E402
    ArchiveRuntimeCoordinator,
)
from app.services.archive_runtime_resource_service import (  # noqa: E402
    ArchiveRuntimeResourceProvider,
)
from app.services.archive_runtime_service import ArchiveManifestRecord  # noqa: E402
from app.services.archive_scheduler_service import ArchiveSchedulerService  # noqa: E402
from app.services.archive_task_api_service import ArchiveTaskApiService  # noqa: E402
from app.services.case_draft_service import CaseDraftService  # noqa: E402
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.edit_lease_service import EditLeaseService  # noqa: E402
from app.services.shared_defaults_service import SharedDefaultsService  # noqa: E402
from app.services.source_record_service import SourceRecordService  # noqa: E402
from app.services.task_record_service import TaskRecordService  # noqa: E402
from app.services.workbench_factory_service import WorkbenchServices  # noqa: E402


REPORT = {
    "title": "SYNTHETIC/TEST/Runtime",
    "document_number": "SYNTHETIC-RUNTIME-001",
    "introduction": {
        "entrust_unit": "",
        "entrust_time": "",
        "entrust_persons": [],
        "case_summary": "SYNTHETIC-RUNTIME",
        "inspection_requirement": "",
        "inspection_time_range": "",
        "evidence_list": [],
        "inspectors": [],
        "inspection_place": "SYNTHETIC",
    },
    "inspection": {
        "method": "SYNTHETIC",
        "hardware_device": "SYNTHETIC",
        "software_tools": [],
        "process_steps": [],
        "result": {
            "evidence_number": "",
            "software_name": "",
            "software_version": "",
            "data_summary": "",
            "rar_filename": "",
            "md5_hash": "",
            "file_size": "",
        },
    },
    "attachments": {
        "disc_number": "GP20260730-01",
        "photo_ids": [],
        "extract_list": {"columns": [], "rows": []},
    },
}


class RecordingWorker:
    def __init__(self, progress: ArchiveProgressService, attempts: ArchiveAttemptService) -> None:
        self.progress = progress
        self.attempts = attempts
        self.calls: list[str] = []
        self.fail_next = False

    def run(self, claim, item, *, interruption_check=None):
        self.calls.append(claim.task_id)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("SYNTHETIC worker failure")
        for stage in (
            "inventory", "preflight_verified", "winrar", "integrity",
            "integrity_verified", "md5", "manifest",
        ):
            self.progress.advance(claim.task_id, claim.owner_token, stage)
        self._publish_synthetic_result(claim, item["context_id"])
        return self.progress.complete(claim.task_id, claim.owner_token)

    def _publish_synthetic_result(self, claim, context_id: str) -> None:
        manifest_id = "SYNTHETIC-MANIFEST-RUNTIME"
        filename = "SYNTHETIC-RUNTIME.part1.rar"
        payload = b"SYNTHETIC/TEST/RUNTIME-ARCHIVE"
        final_dir = self.attempts.output_root / "compressed" / context_id / manifest_id
        final_dir.mkdir(parents=True)
        (final_dir / filename).write_bytes(payload)
        manifest = {
            "manifest_id": manifest_id,
            "archive_base_name": "SYNTHETIC-RUNTIME",
            "volume_size_bytes": 4_000_000_000,
            "max_part_count": 1,
            "actual_archive_bytes": len(payload),
            "validation_status": "validated",
            "parts": [{
                "part_id": "SYNTHETIC-PART-RUNTIME",
                "part_number": 1,
                "filename": filename,
                "size_bytes": len(payload),
                "md5": hashlib.md5(payload).hexdigest(),
                "disc_number": "SYNTHETIC-DISC-RUNTIME",
                "disc_date": "2026-07-30",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            }],
        }
        registry = ArchiveManifestRepository(self.attempts.output_root)
        record = ArchiveManifestRecord(
            manifest_id, context_id, "c" * 64, manifest, final_dir,
            time.time(), time.time() + 60,
        )
        record_attempt_completion(
            self.attempts, claim.attempt_id, registry,
            SimpleNamespace(
                source_key="a" * 64,
                input_fingerprint="b" * 64,
                context_id=context_id,
            ), "c" * 64, record, context_binding_id=context_id,
        )


def _wait_task(client: TestClient, task_id: str, terminal: set[str]) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        detail = client.get(f"/api/v1/workbench/tasks/{task_id}").json()["data"]
        if detail["status"] in terminal:
            return detail
        time.sleep(0.01)
    raise AssertionError(f"SYNTHETIC task did not reach {terminal}")


def _services(tmp_path: Path) -> tuple[WorkbenchServices, RecordingWorker]:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-RUNTIME"),
        "SYNTHETIC-RUNTIME",
    )
    allowed = tmp_path / "SYNTHETIC-ALLOWED"
    output = tmp_path / "SYNTHETIC-OUTPUT"
    report_dir = allowed / "SYNTHETIC-REPORT"
    data = report_dir / "data"
    data.mkdir(parents=True)
    output.mkdir()
    (data / "data_case_info.json").write_text(
        json.dumps({"contents": []}), encoding="utf-8",
    )
    (data / "data_device_lists.json").write_text(
        json.dumps({"contents": [{"c3": "SYNTHETIC"}]}), encoding="utf-8",
    )
    (data / "data_report_info.json").write_text(
        json.dumps({"contents": []}), encoding="utf-8",
    )
    sources = SourceRecordService(
        database, ArchiveAuthorizationService(str(allowed), str(output)),
    )
    attempts = ArchiveAttemptService(database, output)
    tasks = ArchiveTaskRepository(database)
    progress = ArchiveProgressService(
        tasks, ResourceSnapshotRepository(database, interval_seconds=1),
    )
    scheduler = ArchiveSchedulerService(
        tasks,
        ArchiveResourceAdmissionService(ArchiveAdmissionConfig(
            "SYNTHETIC-RUNTIME-V1", 0, 0, 100, 100, 135_000_000_000, 6,
        )),
    )
    worker = RecordingWorker(progress, attempts)
    runtime = ArchiveRuntimeCoordinator(
        scheduler,
        worker,
        attempts,
        progress,
        item_factory=lambda _claim, context_id: {"context_id": context_id},
        snapshot_provider=lambda: ArchiveResourceSnapshot(
            1_000_000, 1_000_000, 0, 0, 0,
        ),
        poll_interval_seconds=0.05,
        shutdown_timeout_seconds=2,
        max_workers=1,
    )
    services = WorkbenchServices(
        database,
        CaseDraftService(
            database, parser=lambda *_args: {"report": copy.deepcopy(REPORT)},
            source_service=sources,
        ),
        CaseLifecycleService(database),
        SharedDefaultsService(database),
        EditLeaseService(database),
        sources,
        TaskRecordService(database),
        archive_attempts=attempts,
        archive_progress=progress,
        archive_scheduler=scheduler,
        archive_worker=worker,  # type: ignore[arg-type]
        archive_runtime=runtime,
    )
    services.archive_api = ArchiveTaskApiService(
        database, attempts, sources, progress, runtime,
    )
    services.synthetic_report_dir = report_dir  # type: ignore[attr-defined]
    return services, worker


def _create_ready_case(client: TestClient, services: WorkbenchServices) -> dict:
    created = client.post("/api/v1/workbench/cases", json={
        "source_path": str(services.synthetic_report_dir),  # type: ignore[attr-defined]
        "case_name": "SYNTHETIC-RUNTIME",
    }).json()["data"]
    case_id = created["shell"]["case_id"]
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        detail = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        if detail["shell"]["lifecycle"] == "review_ready":
            services.sources.revalidate(detail["source"]["source_id"])
            return client.get(
                f"/api/v1/workbench/cases/{case_id}"
            ).json()["data"]
        time.sleep(0.01)
    raise AssertionError("SYNTHETIC case did not become review_ready")


def _controller_patches(services: WorkbenchServices):
    from app.controllers import workbench_controller

    return patch.object(
        workbench_controller, "get_workbench_services", return_value=services,
    )


def test_lifespan_claims_task_queued_before_startup_and_stops(tmp_path: Path) -> None:
    services, worker = _services(tmp_path)
    app_without_runtime = create_app(
        service_provider=lambda: services, enable_archive_runtime=False,
    )
    with _controller_patches(services), TestClient(app_without_runtime) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        assert queued["status"] == "queued"
        assert queued["worker_state"] == "unassigned"

    app_with_runtime = create_app(service_provider=lambda: services)
    with _controller_patches(services), TestClient(app_with_runtime) as client:
        completed = _wait_task(client, queued["task_id"], {"succeeded"})
        assert completed["stage"] == "completed"
        assert completed["percent"] == 100
        assert services.archive_runtime.is_running
    assert not services.archive_runtime.is_running
    assert worker.calls == [queued["task_id"]]


def test_http_task_is_claimed_and_one_failure_does_not_stop_runtime(
    tmp_path: Path,
) -> None:
    services, worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services)
    with _controller_patches(services), TestClient(app) as client:
        first = _create_ready_case(client, services)
        worker.fail_next = True
        failed = client.post(
            f"/api/v1/workbench/cases/{first['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": first["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        failed = _wait_task(client, failed["task_id"], {"failed_retryable"})
        assert failed["worker_state"] == "released"

        second = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{second['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": second["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        completed = _wait_task(client, queued["task_id"], {"succeeded"})
        assert completed["percent"] == 100
        assert services.archive_runtime.loop_start_count == 1


def test_public_http_task_is_claimed_with_windows_style_resource_snapshot(
    tmp_path: Path, caplog,
) -> None:
    services, worker = _services(tmp_path)
    provider = ArchiveRuntimeResourceProvider(services.archive_attempts.output_root)
    services.archive_runtime.snapshot_provider = provider.snapshot
    windows_counters = type(
        "sdiskio",
        (),
        {
            "read_count": 1,
            "write_count": 2,
            "read_bytes": 3,
            "write_bytes": 4,
            "read_time": 5,
            "write_time": 6,
        },
    )()
    with patch(
        "app.services.archive_runtime_resource_service.psutil.disk_io_counters",
        return_value=windows_counters,
    ), caplog.at_level(
        logging.WARNING,
        logger="app.services.archive_runtime_resource_service",
    ), _controller_patches(services), TestClient(
        create_app(service_provider=lambda: services)
    ) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        completed = _wait_task(client, queued["task_id"], {"succeeded"})
        assert completed["status"] == "succeeded"
        assert completed["worker_state"] == "released"

    unavailable = [
        record for record in caplog.records
        if "ARCHIVE_IO_METRIC_UNAVAILABLE" in record.getMessage()
    ]
    assert len(unavailable) == 1
    assert not any(
        "busy_time" in record.getMessage()
        or "Archive scheduler iteration failed safely" in record.getMessage()
        for record in caplog.records
    )


def test_runtime_start_is_idempotent_and_empty_queue_waits(tmp_path: Path) -> None:
    services, _worker = _services(tmp_path)
    calls = 0

    def snapshot() -> ArchiveResourceSnapshot:
        nonlocal calls
        calls += 1
        return ArchiveResourceSnapshot(1_000, 1_000, 0, 0, 0)

    services.archive_runtime.snapshot_provider = snapshot
    services.archive_runtime.start()
    services.archive_runtime.start()
    time.sleep(0.13)
    services.archive_runtime.stop()
    assert services.archive_runtime.loop_start_count == 1
    assert calls <= 4
