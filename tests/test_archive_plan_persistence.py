"""T013 archive plan, stable-slot, Manifest, and asset persistence tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    ArchiveAssetRepository,
    ArchivePlanRepository,
    ArchiveTaskRepository,
    CaseShellRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.workbench_errors import RevisionConflictError, WorkbenchPersistenceError  # noqa: E402

CASE_ID = "SYNTHETIC-T013-PLAN-CASE"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    db = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-T013-PLAN"),
        "SYNTHETIC-T013-PLAN",
    )
    CaseShellRepository(db).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/Plan",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    return db


def slot(slot_id: str, ordinal: int, revision: int = 1) -> dict:
    return {
        "slot_id": slot_id, "ordinal": ordinal, "plan_revision": revision,
        "lineage_key": f"SYNTHETIC-{slot_id}", "planned_input_bytes": ordinal * 100,
        "status": "active",
        "disc_mapping": {
            "slot_id": slot_id, "disc_number": f"SYNTHETIC-DISC-{ordinal}",
            "disc_date": "2026-07-30", "source": "default",
            "confirmation": "confirmed",
        },
    }


def create_plan(repository: ArchivePlanRepository):
    return repository.create({
        "plan_id": "SYNTHETIC-PLAN-1", "case_id": CASE_ID, "plan_revision": 1,
        "input_inventory_revision": 4, "mapping_revision": 2,
        "volume_slots": [slot("SYNTHETIC-SLOT-A", 1), slot("SYNTHETIC-SLOT-B", 2)],
    })


def test_replan_preserves_removed_slots_and_manifest_converges(database: WorkbenchDatabase) -> None:
    repository = ArchivePlanRepository(database)
    plan = create_plan(repository)
    replanned = repository.replan(
        plan["plan_id"],
        [slot("SYNTHETIC-SLOT-A", 1, 2), slot("SYNTHETIC-SLOT-C", 3, 2)],
        input_inventory_revision=5, mapping_revision=3, expected_revision=plan["revision"],
    )
    assert replanned["plan_revision"] == 2
    assert {
        item["slot_id"] for item in replanned["volume_slots"] if item["status"] == "removed"
    } == {"SYNTHETIC-SLOT-B"}
    verified = [
        {
            "slot_id": item["slot_id"], "ordinal": item["ordinal"],
            "disc_number": item["disc_mapping"]["disc_number"],
            "output_bytes": 123, "md5": f"SYNTHETIC-MD5-{item['ordinal']}",
        }
        for item in replanned["volume_slots"] if item["status"] == "active"
    ]
    converged = repository.converge_manifest(
        plan["plan_id"], verified, replanned["revision"]
    )
    assert converged["verified_slots"] == verified
    assert repository.get_latest_for_case(CASE_ID)["plan_id"] == plan["plan_id"]
    reopened = ArchivePlanRepository(
        WorkbenchDatabase(database.database_path, "SYNTHETIC-T013-PLAN")
    ).get(plan["plan_id"])
    assert reopened["volume_slots"] == converged["volume_slots"]
    with pytest.raises(RevisionConflictError):
        repository.replan(
            plan["plan_id"], [slot("SYNTHETIC-SLOT-A", 1, 3)],
            input_inventory_revision=6, mapping_revision=4,
            expected_revision=replanned["revision"],
        )


def test_manifest_must_cover_exact_active_slot_set(database: WorkbenchDatabase) -> None:
    repository = ArchivePlanRepository(database)
    plan = create_plan(repository)
    with pytest.raises(WorkbenchPersistenceError, match="MANIFEST_SLOT_MISMATCH"):
        repository.converge_manifest(plan["plan_id"], [], plan["revision"])


def test_archive_asset_internal_locator_never_enters_public_projection(
    database: WorkbenchDatabase,
) -> None:
    plan = create_plan(ArchivePlanRepository(database))
    task = ArchiveTaskRepository(database).create({
        "task_id": "SYNTHETIC-ASSET-TASK", "case_id": CASE_ID,
    })
    repository = ArchiveAssetRepository(database)
    asset = repository.create({
        "asset_id": "SYNTHETIC-ASSET-1", "case_id": CASE_ID,
        "task_id": task["task_id"], "plan_id": plan["plan_id"],
        "asset_kind": "rar_volume", "status": "temporary",
        "internal_locator": "C:\\SYNTHETIC\\private\\volume.part1.rar",
        "metadata": {"slot_id": "SYNTHETIC-SLOT-A"},
    })
    public = repository.get_public(asset["asset_id"])
    assert "internal_locator" not in public
    assert "metadata" not in public
    published = repository.update_status(asset["asset_id"], "published", asset["revision"])
    with database.transaction() as connection:
        connection.execute("DELETE FROM task_records WHERE task_id=?", (task["task_id"],))
        connection.execute("DELETE FROM archive_plans WHERE plan_id=?", (plan["plan_id"],))
        connection.execute("DELETE FROM case_shells WHERE case_id=?", (CASE_ID,))
    assert repository.get_internal(asset["asset_id"])["status"] == "published"
    reopened = ArchiveAssetRepository(
        WorkbenchDatabase(database.database_path, "SYNTHETIC-T013-PLAN")
    )
    assert reopened.get_internal(asset["asset_id"])["status"] == published["status"]


def test_persist_archive_plan_projects_manifest_parts_to_slots(database: WorkbenchDatabase) -> None:
    from app.services.archive_mapping_service import persist_archive_plan

    repository = ArchivePlanRepository(database)
    plan = persist_archive_plan(
        repository, plan_id="SYNTHETIC-PERSIST-PLAN-1", case_id=CASE_ID,
        manifest_parts=[
            {"filename": "case.part1.rar", "size_bytes": 100,
             "disc_number": "GP20260718-01", "disc_date": "2026-07-18"},
            {"filename": "case.part2.rar", "size_bytes": 200,
             "disc_number": "", "disc_date": ""},
        ],
    )
    slots = plan["volume_slots"]
    assert len(slots) == 2
    assert [item["lineage_key"] for item in slots] == ["case.part1.rar", "case.part2.rar"]
    # Pre-filled disc becomes a confirmed mapping; empty disc stays deferred.
    assert slots[0]["disc_mapping"]["disc_number"] == "GP20260718-01"
    assert slots[0]["status"] == "active"
    assert slots[1]["disc_mapping"] is None
    assert slots[1]["status"] == "pending"
    reopened = repository.get_latest_for_case(CASE_ID)
    assert reopened is not None
    # No-op when a plan already exists for the case.
    again = persist_archive_plan(
        repository, plan_id="SYNTHETIC-PERSIST-PLAN-2", case_id=CASE_ID,
        manifest_parts=[
            {"filename": "case.part1.rar", "size_bytes": 100,
             "disc_number": "", "disc_date": ""},
        ],
    )
    assert again["plan_id"] == "SYNTHETIC-PERSIST-PLAN-1"
