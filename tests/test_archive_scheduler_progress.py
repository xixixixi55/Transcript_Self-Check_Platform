"""T014 调度、准入、进度和映射测试。"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    ArchivePlanRepository,
    ArchiveTaskRepository,
    CaseShellRepository,
    ResourceSnapshotRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_mapping_service import ArchiveMappingService  # noqa: E402
from app.services.archive_progress_service import ArchiveProgressService  # noqa: E402
from app.services.archive_resource_admission_service import (  # noqa: E402
    ArchiveAdmissionConfig,
    ArchiveResourceAdmissionService,
    ArchiveResourceSnapshot,
)
from app.services.archive_scheduler_service import ArchiveSchedulerService  # noqa: E402

CASE_ID = "SYNTHETIC-T014-CASE"
BASE = "2026-07-30T02:00:00+00:00"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-T014"),
        "SYNTHETIC-T014",
    )
    CaseShellRepository(database).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/T014",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    return database


def create_task(
    tasks: ArchiveTaskRepository, number: int, *, priority: int = 0,
) -> dict:
    return tasks.create({
        "task_id": f"SYNTHETIC-T014-TASK-{number}",
        "case_id": CASE_ID,
        "created_at": f"2026-07-30T02:00:{number:02d}+00:00",
        "updated_at": BASE,
        "counters": {"priority": priority, "input_bytes": 100},
        "process_binding": {
            "staging_asset_id": f"SYNTHETIC-T014-ATTEMPT-{number}",
        },
    })


def admission(maximum_input: int = 1_000) -> ArchiveResourceAdmissionService:
    return ArchiveResourceAdmissionService(ArchiveAdmissionConfig(
        version="SYNTHETIC-CONFIG-V1",
        minimum_output_free_bytes=100,
        minimum_temporary_free_bytes=100,
        maximum_cpu_percent=80,
        maximum_io_busy_percent=80,
        maximum_input_bytes=maximum_input,
        maximum_winrar_processes=6,
    ))


def snapshot(**changes) -> ArchiveResourceSnapshot:
    values = {
        "output_free_bytes": 1_000,
        "temporary_free_bytes": 1_000,
        "cpu_percent": 10,
        "io_busy_percent": 10,
        "winrar_process_count": 0,
    }
    values.update(changes)
    return ArchiveResourceSnapshot(**values)


def test_scheduler_uses_persistent_priority_queue_and_atomic_cap(database) -> None:
    tasks = ArchiveTaskRepository(database)
    for number in range(1, 8):
        create_task(tasks, number, priority=10 if number == 7 else 0)
    scheduler = ArchiveSchedulerService(tasks, admission(), max_running=6)
    claims = [scheduler.claim_next(snapshot()) for _ in range(7)]
    assert claims[0].task_id == "SYNTHETIC-T014-TASK-7"
    assert all(claim is not None for claim in claims[:6])
    assert claims[6] is None
    assert len(tasks.list_inflight()) == 6
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_CONCURRENCY_LIMIT"):
        queued = tasks.list_queued()[0]
        tasks.claim(
            queued["task_id"], owner_token="SYNTHETIC-EXTRA-WORKER",
            attempt_id="SYNTHETIC-EXTRA-ATTEMPT",
            expected_revision=queued["revision"], max_running=6,
        )


def test_concurrent_schedulers_never_exceed_database_cap(database) -> None:
    tasks = ArchiveTaskRepository(database)
    for number in range(1, 11):
        create_task(tasks, number)
    scheduler = ArchiveSchedulerService(tasks, admission(), max_running=6)
    with ThreadPoolExecutor(max_workers=10) as pool:
        claims = list(pool.map(lambda _item: scheduler.claim_next(snapshot()), range(10)))
    claimed_ids = {claim.task_id for claim in claims if claim is not None}
    assert len(claimed_ids) <= 6
    assert len(tasks.list_inflight()) == len(claimed_ids)


def test_resource_denial_keeps_task_queued_with_server_reason(database) -> None:
    tasks = ArchiveTaskRepository(database)
    task = create_task(tasks, 1)
    scheduler = ArchiveSchedulerService(tasks, admission())
    assert scheduler.claim_next(snapshot(cpu_percent=95)) is None
    waiting = tasks.get(task["task_id"])
    assert waiting["status"] == "queued"
    assert waiting["error_code"] == "ARCHIVE_CPU_BUSY"
    assert waiting["percent"] == 0


def test_scheduler_does_not_claim_task_without_local_runtime_context(database) -> None:
    tasks = ArchiveTaskRepository(database)
    first = create_task(tasks, 1)
    second = create_task(tasks, 2)
    scheduler = ArchiveSchedulerService(tasks, admission())

    claim = scheduler.claim_next(
        snapshot(), eligible_task_ids={second["task_id"]},
    )

    assert claim is not None
    assert claim.task_id == second["task_id"]
    assert tasks.get(first["task_id"])["status"] == "queued"


def test_owned_progress_fixed_milestones_activity_and_cancel(database) -> None:
    tasks = ArchiveTaskRepository(database)
    queued = create_task(tasks, 1)
    running = tasks.claim(
        queued["task_id"], owner_token="SYNTHETIC-OWNER",
        attempt_id="SYNTHETIC-T014-ATTEMPT-1",
        expected_revision=queued["revision"], max_running=6,
    )
    progress = ArchiveProgressService(
        tasks, ResourceSnapshotRepository(database, interval_seconds=15),
    )
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_TASK_OWNERSHIP_LOST"):
        progress.advance(running["task_id"], "SYNTHETIC-STALE-OWNER", "inventory")
    inventory = progress.advance(running["task_id"], "SYNTHETIC-OWNER", "inventory")
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_STAGE_GATE_REQUIRED"):
        progress.advance(inventory["task_id"], "SYNTHETIC-OWNER", "winrar")
    preflight = progress.advance(
        inventory["task_id"], "SYNTHETIC-OWNER", "preflight_verified",
    )
    winrar = progress.advance(preflight["task_id"], "SYNTHETIC-OWNER", "winrar")
    assert winrar["percent"] == 30
    unchanged = progress.activity(winrar["task_id"], "SYNTHETIC-OWNER", {
        "observed_at": "2026-07-30T02:00:05+00:00",
    })
    assert unchanged["revision"] == winrar["revision"]
    active = progress.activity(winrar["task_id"], "SYNTHETIC-OWNER", {
        "observed_at": "2026-07-30T02:00:06+00:00",
        "output_bytes": 123, "output_volume_count": 2,
    })
    assert active["percent"] == 30
    assert active["output_volume_count"] == 2
    cancelling = progress.request_cancel(active["task_id"], active["revision"])
    cancelled = progress.cancel(cancelling["task_id"], "SYNTHETIC-OWNER")
    assert cancelled["status"] == "cancelled"
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_TASK_OWNERSHIP_LOST"):
        progress.activity(cancelled["task_id"], "SYNTHETIC-OWNER", {
            "observed_at": "2026-07-30T02:01:00+00:00",
        })


def test_mapping_replan_preserves_lineage_identity_not_filename(database) -> None:
    service = ArchiveMappingService(
        ArchivePlanRepository(database),
        create_slot_id=iter(["SYNTHETIC-SLOT-A", "SYNTHETIC-SLOT-B",
                             "SYNTHETIC-SLOT-C"]).__next__,
    )
    plan = service.create(
        plan_id="SYNTHETIC-T014-PLAN", case_id=CASE_ID,
        input_inventory_revision=1, mapping_revision=1,
        planned_slots=[
            {"lineage_key": "SYNTHETIC-LINE-A", "planned_input_bytes": 10,
             "estimated_filename": "old.part1.rar", "disc_mapping": {
                 "slot_id": "SYNTHETIC-SLOT-A",
                 "disc_number": "SYNTHETIC-DISC-9",
                 "disc_date": "2026-07-30", "source": "user",
                 "confirmation": "confirmed",
             }},
            {"lineage_key": "SYNTHETIC-LINE-B", "planned_input_bytes": 20},
        ],
    )
    replanned = service.replan(
        plan["plan_id"],
        [
            {"lineage_key": "SYNTHETIC-LINE-A", "planned_input_bytes": 15,
             "estimated_filename": "renamed.part99.rar"},
            {"lineage_key": "SYNTHETIC-LINE-C", "planned_input_bytes": 25},
        ],
        input_inventory_revision=2, mapping_revision=2,
        expected_revision=plan["revision"],
    )
    active = {slot["lineage_key"]: slot for slot in replanned["volume_slots"]
              if slot["status"] != "removed"}
    assert active["SYNTHETIC-LINE-A"]["slot_id"] == "SYNTHETIC-SLOT-A"
    assert active["SYNTHETIC-LINE-A"]["disc_mapping"]["source"] == "user"
    assert active["SYNTHETIC-LINE-C"]["status"] == "pending"
