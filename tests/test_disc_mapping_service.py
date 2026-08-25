"""定向测试：盘号后填映射（序列生成 + plan 持久化）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    ArchivePlanRepository,
    CaseShellRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.workbench_errors import RevisionConflictError  # noqa: E402
from app.services.disc_mapping_service import (  # noqa: E402
    DiscMappingError,
    active_slots,
    apply_disc_mapping,
    build_disc_mappings,
    first_mapped_disc_number,
)

CASE_ID = "SYNTHETIC-DISC-MAPPING-CASE"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    db = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DISC-MAPPING"),
        "SYNTHETIC-DISC-MAPPING",
    )
    CaseShellRepository(db).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/DiscMapping",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    return db


def slot(slot_id: str, ordinal: int) -> dict:
    return {
        "slot_id": slot_id, "ordinal": ordinal, "plan_revision": 1,
        "lineage_key": f"SYNTHETIC-{slot_id}", "planned_input_bytes": ordinal * 100,
        "status": "active", "disc_mapping": None,
    }


def test_build_disc_mappings_generates_sequence_in_ordinal_order() -> None:
    slots = [slot("SLOT-A", 1), slot("SLOT-B", 2), slot("SLOT-C", 3)]
    mappings = build_disc_mappings("GP2026071802-01", slots)
    assert [item["disc_number"] for item in mappings] == [
        "GP2026071802-01", "GP2026071802-02", "GP2026071802-03",
    ]
    assert mappings[0]["disc_date"] == "2026-07-18"
    assert all(item["source"] == "user" and item["confirmation"] == "confirmed" for item in mappings)
    assert [item["slot_id"] for item in mappings] == ["SLOT-A", "SLOT-B", "SLOT-C"]


def test_build_disc_mappings_rejects_invalid_number() -> None:
    with pytest.raises(DiscMappingError) as error:
        build_disc_mappings("NOT-A-DISC", [slot("SLOT-A", 1)])
    assert error.value.code == "FIRST_DISC_NUMBER_INVALID"


@pytest.mark.parametrize(
    ("value", "archive_mode"),
    [
        ("GP20260718-01", "standard_split"),
        ("YP20260413-01", "oversized_single_volume"),
    ],
)
def test_mapping_accepts_legacy_number_without_user_identifier(
    value: str, archive_mode: str,
) -> None:
    mappings = build_disc_mappings(value, [slot("SLOT-A", 1)], archive_mode)
    assert mappings[0]["disc_number"] == value


def test_hard_drive_mapping_uses_one_user_number_and_rejects_disc_prefix() -> None:
    slots = [slot("SLOT-HARD-DRIVE", 1)]
    mappings = build_disc_mappings(
        "YP2026041302-01", slots, "oversized_single_volume",
    )
    assert [item["disc_number"] for item in mappings] == ["YP2026041302-01"]

    with pytest.raises(DiscMappingError) as error:
        build_disc_mappings(
            "GP2026041302-01", slots, "oversized_single_volume",
        )
    assert error.value.code == "HARD_DRIVE_NUMBER_INVALID"


def test_hard_drive_mapping_rejects_multiple_archive_parts() -> None:
    with pytest.raises(DiscMappingError) as error:
        build_disc_mappings(
            "YP2026041302-01", [slot("SLOT-A", 1), slot("SLOT-B", 2)],
            "oversized_single_volume",
        )
    assert error.value.code == "ARCHIVE_PLAN_INVALID"


def test_apply_disc_mapping_persists_to_plan(database: WorkbenchDatabase) -> None:
    repository = ArchivePlanRepository(database)
    plan = repository.create({
        "plan_id": "SYNTHETIC-DISC-PLAN-1", "case_id": CASE_ID, "plan_revision": 1,
        "input_inventory_revision": 4, "mapping_revision": 1,
        "volume_slots": [slot("SYNTHETIC-SLOT-A", 1), slot("SYNTHETIC-SLOT-B", 2)],
    })
    result = apply_disc_mapping(
        database, CASE_ID, plan["revision"], plan["revision"], "GP2026071802-01",
    )
    assert result["parts"] == [
        {"part_number": 1, "disc_number": "GP2026071802-01", "disc_date": "2026-07-18"},
        {"part_number": 2, "disc_number": "GP2026071802-02", "disc_date": "2026-07-18"},
    ]
    reopened = repository.get(plan["plan_id"])
    assert reopened["mapping_revision"] == plan["mapping_revision"] + 1
    assert all(
        item["disc_mapping"]["confirmation"] == "confirmed"
        for item in active_slots(reopened)
    )
    # expected_revision is the caller's case-level guard and is returned verbatim;
    # the plan write is CAS-guarded by the plan row's own revision.
    assert result["expected_revision"] == plan["revision"]
    assert result["lifecycle"] == "archive_verified"
    assert result["archive_medium"] == "optical_disc"
    assert first_mapped_disc_number(database, CASE_ID) == "GP2026071802-01"


def test_apply_hard_drive_mapping_persists_one_yp_number(database: WorkbenchDatabase) -> None:
    repository = ArchivePlanRepository(database)
    plan = repository.create({
        "plan_id": "SYNTHETIC-HARD-DRIVE-PLAN", "case_id": CASE_ID,
        "plan_revision": 1, "input_inventory_revision": 4, "mapping_revision": 0,
        "volume_slots": [slot("SYNTHETIC-HARD-DRIVE-SLOT", 1)],
    })

    result = apply_disc_mapping(
        database, CASE_ID, plan["revision"], plan["revision"],
        "YP2026041302-01", "oversized_single_volume",
    )

    assert result["archive_medium"] == "hard_drive"
    assert result["parts"] == [{
        "part_number": 1,
        "disc_number": "YP2026041302-01",
        "disc_date": "2026-04-13",
    }]
    reopened = repository.get(plan["plan_id"])
    assert active_slots(reopened)[0]["disc_mapping"]["disc_number"] == "YP2026041302-01"


def test_apply_disc_mapping_uses_plan_revision_for_cas(database: WorkbenchDatabase) -> None:
    """A stale case-level revision must not block the deferred mapping (REQ-030)."""
    repository = ArchivePlanRepository(database)
    plan = repository.create({
        "plan_id": "SYNTHETIC-DISC-PLAN-2", "case_id": CASE_ID, "plan_revision": 1,
        "input_inventory_revision": 4, "mapping_revision": 1,
        "volume_slots": [slot("SYNTHETIC-SLOT-A", 1)],
    })
    result = apply_disc_mapping(
        database, CASE_ID, plan["revision"] - 1,
        plan["revision"], "GP2026071802-01",
    )
    assert result["expected_revision"] == plan["revision"] - 1
    reopened = repository.get(plan["plan_id"])
    assert active_slots(reopened)[0]["disc_mapping"]["disc_number"] == "GP2026071802-01"


def test_first_mapped_disc_number_requires_every_active_slot_confirmed(database: WorkbenchDatabase) -> None:
    ArchivePlanRepository(database).create({
        "plan_id": "SYNTHETIC-DISC-PLAN-INCOMPLETE", "case_id": CASE_ID,
        "plan_revision": 1, "input_inventory_revision": 4, "mapping_revision": 1,
        "volume_slots": [
            {
                **slot("SYNTHETIC-SLOT-A", 1),
                "disc_mapping": {
                    "slot_id": "SYNTHETIC-SLOT-A",
                    "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                    "source": "user", "confirmation": "confirmed",
                },
            },
            {
                **slot("SYNTHETIC-SLOT-B", 2),
                "disc_mapping": {
                    "slot_id": "SYNTHETIC-SLOT-B",
                    "disc_number": "GP20260718-02", "disc_date": "2026-07-18",
                    "source": "user", "confirmation": "pending",
                },
            },
        ],
    })

    assert first_mapped_disc_number(database, CASE_ID) is None


def test_apply_disc_mapping_rejects_stale_plan_row_revision(database: WorkbenchDatabase) -> None:
    repository = ArchivePlanRepository(database)
    plan = repository.create({
        "plan_id": "SYNTHETIC-DISC-PLAN-CAS", "case_id": CASE_ID,
        "plan_revision": 1, "input_inventory_revision": 4, "mapping_revision": 1,
        "volume_slots": [slot("SYNTHETIC-SLOT-A", 1)],
    })
    first = apply_disc_mapping(
        database, CASE_ID, 8, plan["revision"], "GP2026071802-01",
    )
    assert first["plan_row_revision"] == plan["revision"] + 1

    with pytest.raises(RevisionConflictError):
        apply_disc_mapping(
            database, CASE_ID, 8, plan["revision"], "GP2026071802-02",
        )
