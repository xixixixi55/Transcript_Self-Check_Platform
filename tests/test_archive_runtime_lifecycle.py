"""Application-lifespan coverage for the persistent archive runtime."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
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
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository  # noqa: E402
from app.repository.archive_attempt_restart_repository import interrupt_owned_claim  # noqa: E402
from app.repository.archive_runtime_context_lease_repository import (  # noqa: E402
    interrupt_expired_queued_contexts,
    interrupt_queued_runtime_context,
    lease_queued_runtime_context,
)
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
        self.multi_part = False

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
            if stage == "winrar" and self.multi_part:
                self.progress.activity(claim.task_id, claim.owner_token, {
                    "observed_at": "2026-08-11T06:16:42+00:00",
                    "output_bytes": len(b"SYNTHETIC/TEST/RUNTIME-ARCHIVE-PART-1"),
                    "output_volume_count": 1,
                })
        self._publish_synthetic_result(claim, item["context_id"])
        return self.progress.complete(claim.task_id, claim.owner_token)

    def _publish_synthetic_result(self, claim, context_id: str) -> None:
        manifest_id = "SYNTHETIC-MANIFEST-RUNTIME"
        payloads = [b"SYNTHETIC/TEST/RUNTIME-ARCHIVE-PART-1"]
        if self.multi_part:
            payloads.append(b"SYNTHETIC/TEST/RUNTIME-ARCHIVE-PART-2")
        final_dir = self.attempts.output_root / "compressed" / context_id / manifest_id
        final_dir.mkdir(parents=True)
        parts = []
        for index, payload in enumerate(payloads, start=1):
            filename = f"SYNTHETIC-RUNTIME.part{index}.rar"
            (final_dir / filename).write_bytes(payload)
            parts.append({
                "part_id": f"SYNTHETIC-PART-RUNTIME-{index}",
                "part_number": index,
                "filename": filename,
                "size_bytes": len(payload),
                "md5": hashlib.md5(payload).hexdigest(),
                "disc_number": f"SYNTHETIC-DISC-RUNTIME-{index}",
                "disc_date": "2026-07-30",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            })
        manifest = {
            "manifest_id": manifest_id,
            "archive_base_name": "SYNTHETIC-RUNTIME",
            "volume_size_bytes": 4_000_000_000,
            "max_part_count": len(parts),
            "actual_archive_bytes": sum(len(payload) for payload in payloads),
            "validation_status": "validated",
            "parts": parts,
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
            "SYNTHETIC-RUNTIME-V1", 0, 0, 100, 100, 6,
        )),
    )
    worker = RecordingWorker(progress, attempts)
    runtime = ArchiveRuntimeCoordinator(
        scheduler,
        worker,
        attempts,
        progress,
        item_factory=lambda _claim, context_id, _cancellation_check: {
            "context_id": context_id,
        },
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
    worker.multi_part = True
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
        assert completed["output_volume_count"] == 2
        assert completed["output_bytes"] == sum(map(len, (
            b"SYNTHETIC/TEST/RUNTIME-ARCHIVE-PART-1",
            b"SYNTHETIC/TEST/RUNTIME-ARCHIVE-PART-2",
        )))
        assert services.archive_runtime.is_running
    assert not services.archive_runtime.is_running
    assert worker.calls == [queued["task_id"]]
    task = ArchiveTaskRepository(services.database).get(queued["task_id"])
    attempt = services.archive_attempts.repository.get_internal(
        task["process_binding"]["staging_asset_id"],
    )
    assert all(attempt[field] is None for field in (
        "input_snapshot_id", "input_snapshot_root_id", "input_snapshot_locator",
        "input_snapshot_fingerprint", "input_snapshot_status",
    ))
    with services.database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM archive_input_snapshots WHERE attempt_id=?",
            (attempt["attempt_id"],),
        ).fetchone()[0] == 0
    assert services.synthetic_report_dir.is_dir()  # type: ignore[attr-defined]


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
        result = client.get(
            f"/api/v1/workbench/tasks/{queued['task_id']}/result",
        ).json()["data"]
        part = result["parts"][0]
        saved_report = client.get(
            f"/api/v1/workbench/cases/{second['shell']['case_id']}",
        ).json()["data"]["draft"]["report"]
        saved = saved_report["inspection"]["result"]
        assert saved["rar_filename"] == part["filename"]
        assert saved["md5_hash"] == part["md5"]
        assert saved["file_size"] == str(part["size_bytes"])
        attachment_table = saved_report["attachments"]["extract_list"]
        assert [row["no"] for row in attachment_table["rows"]] == ["1"]
        assert [row["electronic_data"] for row in attachment_table["rows"]] == [part["filename"]]
        assert [row["md5_hash"] for row in attachment_table["rows"]] == [part["md5"]]
        assert "file_size" not in {column["key"] for column in attachment_table["columns"]}
        assert saved_report["attachments"]["disc_number"] == part["disc_number"]
        assert services.archive_runtime.loop_start_count == 1


def test_retry_returns_safe_task_and_runtime_claims_new_attempt(tmp_path: Path) -> None:
    services, worker = _services(tmp_path)
    worker.multi_part = True
    app = create_app(service_provider=lambda: services)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        worker.fail_next = True
        first = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        failed = _wait_task(client, first["task_id"], {"failed_retryable"})

        tasks = ArchiveTaskRepository(services.database)
        old_attempt_id = tasks.get(first["task_id"])["process_binding"]["staging_asset_id"]
        current_case = client.get(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}"
        ).json()["data"]
        retried = client.post(
            f"/api/v1/workbench/tasks/{first['task_id']}/retry",
            json={
                "expected_revision": failed["revision"],
                "expected_case_revision": current_case["shell"]["revision"],
            },
        )
        assert retried.status_code == 200, (
            f"{retried.text} task_revision={failed['revision']} "
            f"case_revision={current_case['shell']['revision']}"
        )
        retry_data = retried.json()["data"]
        assert set(retry_data) == {"task"}
        retry_task = retry_data["task"]
        assert retry_task["task_id"] != first["task_id"]
        for forbidden in (
            "archive_context_id", "archive_attempt_id", "context_hash", "fence_id",
            "lease_id", "lease_token", "owner_token", "deployment_instance_id",
            "source_id", "source_revision", "draft_revision", "report_fingerprint",
            "publication_id", "publication_digest", "process_binding", "staging_locator",
            "ownership_marker_token", "internal_locator", "internal_path",
        ):
            assert forbidden not in retried.text

        new_attempt_id = tasks.get(retry_task["task_id"])["process_binding"]["staging_asset_id"]
        assert new_attempt_id != old_attempt_id
        assert services.archive_attempts.repository.get_internal(new_attempt_id)["task_id"] == retry_task["task_id"]
        completed = _wait_task(client, retry_task["task_id"], {"succeeded"})
        assert completed["status"] == "succeeded"
        assert completed["worker_state"] == "released"
        assert completed["output_volume_count"] == 2
        result = client.get(
            f"/api/v1/workbench/tasks/{retry_task['task_id']}/result",
        ).json()["data"]
        assert len(result["parts"]) == 2

    assert worker.calls == [first["task_id"], retry_task["task_id"]]


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


def test_public_result_rejects_formal_part_tamper_after_completion(tmp_path: Path) -> None:
    services, _worker = _services(tmp_path)
    with _controller_patches(services), TestClient(
        create_app(service_provider=lambda: services)
    ) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        completed = _wait_task(client, queued["task_id"], {"succeeded"})
        result = client.get(f"/api/v1/workbench/tasks/{queued['task_id']}/result")
        assert result.status_code == 200
        part = result.json()["data"]["parts"][0]
        registry = ArchiveManifestRepository(services.archive_attempts.output_root)
        task = ArchiveTaskRepository(services.database).get(queued["task_id"])
        attempt_id = task["process_binding"]["staging_asset_id"]
        record = registry.find_for_attempt(attempt_id)[0]
        part_path = registry.resolve_final_dir(record) / part["filename"]
        part_path.write_bytes(b"SYNTHETIC/TEST/FORMAL-TAMPER")
        rejected = client.get(f"/api/v1/workbench/tasks/{queued['task_id']}/result")
        assert rejected.status_code == 422
        rejected_download = client.get(
            f"/api/v1/workbench/tasks/{queued['task_id']}/result/parts/{part['part_id']}"
        )
        assert rejected_download.status_code == 422
        assert completed["status"] == "succeeded"


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


def test_other_coordinator_interrupts_expired_queued_context_lease(tmp_path: Path) -> None:
    services, worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]

    first_runtime = services.archive_runtime
    context_id = first_runtime._contexts[queued["task_id"]]
    observed_at = datetime.now(timezone.utc)
    renewed_until = (observed_at + timedelta(seconds=30)).isoformat()
    assert lease_queued_runtime_context(
        services.database, task_id=queued["task_id"],
        context_id=context_id, expires_at=renewed_until,
    )
    assert not interrupt_queued_runtime_context(
        services.database, task_id=queued["task_id"],
        expires_before=observed_at,
    )
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert lease_queued_runtime_context(
        services.database, task_id=queued["task_id"],
        context_id=context_id, expires_at=expired_at,
    )
    second_runtime = ArchiveRuntimeCoordinator(
        first_runtime.scheduler, worker, services.archive_attempts, first_runtime.progress,
        item_factory=first_runtime.item_factory,
        snapshot_provider=first_runtime.snapshot_provider,
        poll_interval_seconds=0.01,
    )
    second_runtime.start()
    deadline = time.monotonic() + 2
    task = first_runtime.scheduler.tasks.get(queued["task_id"])
    while time.monotonic() < deadline and task["status"] == "queued":
        time.sleep(0.01)
        task = first_runtime.scheduler.tasks.get(queued["task_id"])
    second_runtime.stop()

    assert task["status"] == "interrupted"
    assert task["error_code"] == "ARCHIVE_RUNTIME_CONTEXT_EXPIRED"
    attempt_id = task["process_binding"]["staging_asset_id"]
    assert services.archive_attempts.repository.get_internal(attempt_id)["status"] == "interrupted"


def test_context_renewal_does_not_invalidate_queued_cancel_revision(tmp_path: Path) -> None:
    services, _worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        original_revision = queued["revision"]
        services.archive_runtime._renew_queued_contexts()
        renewed = services.archive_runtime.scheduler.tasks.get(queued["task_id"])

        assert renewed["revision"] == original_revision
        cancelled = client.post(
            f"/api/v1/workbench/tasks/{queued['task_id']}/cancel",
            json={"expected_revision": original_revision},
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["data"]["status"] == "cancelled"


def test_cancel_during_item_preparation_converges_without_ownership_failure(
    tmp_path: Path,
) -> None:
    services, _worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]

        preparing = threading.Event()
        release = threading.Event()

        def blocked_factory(_claim, _context_id, cancellation_check):
            preparing.set()
            assert release.wait(2)
            assert cancellation_check() is True
            raise RuntimeError("SYNTHETIC preparation cancellation")

        services.archive_runtime.item_factory = blocked_factory
        services.archive_runtime.start()
        assert preparing.wait(2)
        running = services.archive_runtime.scheduler.tasks.get(queued["task_id"])
        assert running["stage"] == "inventory"
        assert running["stage_label"] == "正在核对文件清单与路径"
        response = client.post(
            f"/api/v1/workbench/tasks/{queued['task_id']}/cancel",
            json={"expected_revision": running["revision"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "cancelling"
        release.set()
        cancelled = _wait_task(client, queued["task_id"], {"cancelled"})

    assert services.archive_runtime.stop() is True
    assert cancelled["error_code"] is None
    task = services.archive_runtime.scheduler.tasks.get(queued["task_id"])
    attempt_id = task["process_binding"]["staging_asset_id"]
    attempt = services.archive_attempts.repository.get_internal(attempt_id)
    assert attempt["status"] == "failed"
    assert attempt["error_code"] == "ARCHIVE_CANCELLED"


def test_stale_owner_error_cannot_fail_or_clean_new_owner_attempt(
    tmp_path: Path,
) -> None:
    services, _worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]

    tasks = services.archive_runtime.scheduler.tasks
    original_binding = tasks.get(queued["task_id"])["process_binding"]
    raised = threading.Event()

    class StaleOwnerWorker:
        def run(self, claim, _item, *, interruption_check=None):
            current = tasks.get(claim.task_id)
            tasks.update_state(claim.task_id, {
                "status": "cancelling",
                "process_binding": {
                    **current["process_binding"],
                    "staging_asset_id": "SYNTHETIC-NEW-ATTEMPT",
                },
            }, current["revision"])
            raised.set()
            raise WorkbenchPersistenceError("ARCHIVE_TASK_OWNERSHIP_LOST")

    services.archive_runtime.worker = StaleOwnerWorker()  # type: ignore[assignment]
    services.archive_runtime.start()
    assert raised.wait(2)
    current = tasks.get(queued["task_id"])
    attempt_id = original_binding["staging_asset_id"]
    attempt = services.archive_attempts.repository.get_internal(attempt_id)
    assert current["status"] == "cancelling"
    assert attempt["status"] == "accepted"

    restored = tasks.update_state(queued["task_id"], {
        "process_binding": original_binding,
    }, current["revision"])
    assert restored["status"] == "cancelling"
    assert services.archive_runtime.stop() is True


def test_failed_initial_context_lease_converges_created_task(tmp_path: Path) -> None:
    services, _worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        with patch.object(
            services.archive_runtime, "register",
            side_effect=WorkbenchPersistenceError("SQLITE_BUSY"),
        ):
            response = client.post(
                f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
                json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
            )
    assert response.status_code == 422
    history = services.archive_runtime.scheduler.tasks.get_history(ready["shell"]["case_id"])
    assert len(history) == 1 and history[0]["status"] == "interrupted"
    attempt_id = history[0]["process_binding"]["staging_asset_id"]
    assert services.archive_attempts.repository.get_internal(attempt_id)["status"] == "interrupted"


def test_ownerless_bound_task_expires_after_registration_crash(tmp_path: Path) -> None:
    services, _worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        with patch.object(services.archive_runtime, "register", return_value=None):
            queued = client.post(
                f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
                json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
            ).json()["data"]["archive_task"]
    observed = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert interrupt_expired_queued_contexts(
        services.database, observed_at=observed,
    ) == [queued["task_id"]]
    assert services.archive_runtime.scheduler.tasks.get(queued["task_id"])["status"] == "interrupted"


def test_normal_stop_interrupts_registered_unclaimed_task(tmp_path: Path) -> None:
    services, _worker = _services(tmp_path)
    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
    assert services.archive_runtime.stop() is True
    task = services.archive_runtime.scheduler.tasks.get(queued["task_id"])
    assert task["status"] == "interrupted"
    assert services.archive_attempts.repository.get_internal(
        task["process_binding"]["staging_asset_id"],
    )["status"] == "interrupted"
    assert CaseShellRepository(services.database).get(task["case_id"])["lifecycle"] == "archive_interrupted"


@pytest.mark.parametrize("start_attempt", [False, True])
def test_runtime_timeout_persists_owned_claim_as_interrupted(
    tmp_path: Path, start_attempt: bool,
) -> None:
    services, _worker = _services(tmp_path)
    started = threading.Event()
    release = threading.Event()

    class BlockingWorker:
        def run(self, claim, _item, *, interruption_check=None):
            started.set()
            if start_attempt:
                services.archive_attempts.start(claim.attempt_id)
            release.wait(5)
            return None

    app = create_app(service_provider=lambda: services, enable_archive_runtime=False)
    with _controller_patches(services), TestClient(app) as client:
        ready = _create_ready_case(client, services)
        queued = client.post(
            f"/api/v1/workbench/cases/{ready['shell']['case_id']}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]

    runtime = services.archive_runtime
    context_id = runtime._contexts[queued["task_id"]]
    runtime.worker = BlockingWorker()  # type: ignore[assignment]
    runtime.shutdown_timeout_seconds = 0.05
    runtime.start()
    assert started.wait(2)
    task = runtime.scheduler.tasks.get(queued["task_id"])
    claim = runtime._claims[next(iter(runtime._claims))]
    assert task["status"] == "running"
    assert services.archive_attempts.context_binding(context_id)["expires_at"] is None
    assert interrupt_owned_claim(
        services.database, task_id=claim.task_id, owner_token="SYNTHETIC-WRONG-OWNER",
        attempt_id=claim.attempt_id, task_revision=claim.revision,
    ) == "ownership_lost"
    assert runtime.scheduler.tasks.get(queued["task_id"])["status"] == "running"

    assert runtime.stop() is False
    interrupted = runtime.scheduler.tasks.get(queued["task_id"])
    assert interrupted["status"] == "interrupted"
    assert interrupted["percent"] != 100
    assert interrupted["worker_state"] == "waiting_reclaim"
    assert services.archive_attempts.repository.get_internal(claim.attempt_id)["status"] == "interrupted"

    release.set()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and runtime.is_running:
        time.sleep(0.01)
    runtime.stop()
    final_task = runtime.scheduler.tasks.get(queued["task_id"])
    assert final_task["status"] == "interrupted"
    assert final_task["percent"] != 100


def test_export_bundle_succeeds_after_archive_completion_when_revisions_differ(
    tmp_path: Path,
) -> None:
    """Unified export from a completed card must not be blocked by the
    independent draft revision (REVISION_CONFLICT regression).

    The card sends the shell revision; the template-context resolver must not
    require it to equal the draft revision, which legitimately diverges across
    the archive lifecycle.
    """
    from app.controllers import record_template_context_controller

    services, _worker = _services(tmp_path)
    export_dir = tmp_path / "SYNTHETIC-EXPORT"
    export_dir.mkdir()
    token = services.sources.authorization.issue_exact_directory_grant(str(export_dir))

    with _controller_patches(services), \
            patch.object(
                record_template_context_controller, "get_workbench_services",
                return_value=services,
            ), TestClient(create_app(service_provider=lambda: services)) as client:
        ready = _create_ready_case(client, services)
        case_id = ready["shell"]["case_id"]
        queued = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        ).json()["data"]["archive_task"]
        completed = _wait_task(client, queued["task_id"], {"succeeded"})
        assert completed["status"] == "succeeded"

        shell = CaseShellRepository(services.database).get(case_id)
        draft = CaseDraftRepository(services.database).get(case_id)
        assert shell["revision"] != draft["revision"]

        def fake_docx(_report, **kwargs):
            path = Path(kwargs["output_dir"]) / (kwargs.get("output_filename") or "out.docx")
            path.write_bytes(b"SYNTHETIC/DOCX")
            return path

        from app.repository.hashmyfiles_repository import HashMyFilesError
        failures = [
            (
                "HASHMYFILES_OUTPUT_MISSING", "HashMyFiles 校验结果未生成。",
                "HashMyFiles 校验结果未生成，请重试。",
            ),
            (
                "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果不完整。",
                "HashMyFiles 校验结果缺失或不完整，请重试。",
            ),
            (
                "HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验截图生成失败。",
                "HashMyFiles 校验截图生成失败，请重试。",
            ),
        ]
        for index, (error_code, internal_message, public_message) in enumerate(failures):
            if index:
                token = services.sources.authorization.issue_exact_directory_grant(str(export_dir))
            with patch(
                "app.services.unified_export_service.generate_docx",
                side_effect=fake_docx,
            ), patch(
                "app.services.unified_export_service.generate_verification_image",
                side_effect=HashMyFilesError(error_code, internal_message),
            ):
                failed_response = client.post(
                    f"/api/v1/workbench/cases/{case_id}/export-bundle",
                    json={
                        "expected_revision": shell["revision"],
                        "export_path": str(export_dir),
                        "directory_token": token,
                        "word_filename": "SYNTHETIC-EXPORT.docx",
                    },
                )
            assert failed_response.status_code == 422, failed_response.text
            assert failed_response.json()["detail"] == {
                "code": error_code, "message": public_message,
            }
            assert CaseShellRepository(services.database).get(case_id)["lifecycle"] != "exported"

        token = services.sources.authorization.issue_exact_directory_grant(str(export_dir))
        def fake_hash_image(_paths, output_dir):
            (Path(output_dir) / "hash.png").write_bytes(b"SYNTHETIC/PNG")
            return "hash.png"

        with patch(
            "app.services.unified_export_service.generate_docx",
            side_effect=fake_docx,
        ), patch(
            "app.services.unified_export_service.generate_verification_image",
            side_effect=fake_hash_image,
        ):
            response = client.post(
                f"/api/v1/workbench/cases/{case_id}/export-bundle",
                json={
                    "expected_revision": shell["revision"],
                    "export_path": str(export_dir),
                    "directory_token": token,
                    "word_filename": "SYNTHETIC-EXPORT.docx",
                },
            )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["lifecycle"] == "exported"
        assert response.json()["data"]["output"]["word_filename"] == "SYNTHETIC-EXPORT.docx"
