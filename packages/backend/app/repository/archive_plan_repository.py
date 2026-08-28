"""具有稳定槽位、重新规划和 Manifest 收敛的持久归档计划。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase, normalize_utc, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import json_text, row_json
from .workbench_serialization import validate_opaque_id

_SLOT_STATUSES = {"active", "pending", "removed", "verified"}
class ArchivePlanRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        plan_id = validate_opaque_id(plan.get("plan_id"))
        case_id = validate_opaque_id(plan.get("case_id"))
        slots = _slots(plan.get("volume_slots", []))
        now = normalize_utc(plan.get("created_at"))
        values = (
            plan_id, 1, case_id, _integer(plan.get("plan_revision", 1)),
            _integer(plan.get("input_inventory_revision", 0)),
            _integer(plan.get("mapping_revision", 0)), json_text(slots),
            json_text([]), now, normalize_utc(plan.get("updated_at")), 0,
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO archive_plans(plan_id,schema_version,case_id,plan_revision,"
                    "input_inventory_revision,mapping_revision,volume_slots_json,"
                    "verified_slots_json,created_at,updated_at,revision) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)", values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("ARCHIVE_PLAN_CREATE_FAILED") from error
        return self.get(plan_id)
    def get(self, plan_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM archive_plans WHERE plan_id=?",
                (validate_opaque_id(plan_id),),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_PLAN_NOT_FOUND")
        return _plan_dict(row)

    def get_latest_for_case(self, case_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT plan_id FROM archive_plans WHERE case_id=? "
                "ORDER BY plan_revision DESC,updated_at DESC LIMIT 1",
                (validate_opaque_id(case_id),),
            ).fetchone()
        return None if row is None else self.get(str(row[0]))
    def replan(
        self,
        plan_id: str,
        slots: list[Mapping[str, Any]],
        *,
        input_inventory_revision: int,
        mapping_revision: int,
        expected_revision: int,
    ) -> dict[str, Any]:
        current = self.get(plan_id)
        if current["revision"] != expected_revision:
            raise RevisionConflictError("archive_plan", expected_revision, current["revision"])
        next_slots = _merge_slot_history(current["volume_slots"], _slots(slots))
        return self._update(plan_id, {
            "plan_revision": current["plan_revision"] + 1,
            "input_inventory_revision": _integer(input_inventory_revision),
            "mapping_revision": _integer(mapping_revision),
            "volume_slots": next_slots,
            "verified_slots": current["verified_slots"],
        }, expected_revision)
    def converge_manifest(
        self,
        plan_id: str,
        verified_slots: list[Mapping[str, Any]],
        expected_revision: int,
    ) -> dict[str, Any]:
        current = self.get(plan_id)
        verified = _verified(verified_slots)
        active_ids = {
            slot["slot_id"] for slot in current["volume_slots"]
            if slot["status"] in {"active", "pending", "verified"}
        }
        if {slot["slot_id"] for slot in verified} != active_ids:
            raise WorkbenchPersistenceError("MANIFEST_SLOT_MISMATCH")
        slots = [
            {**slot, "status": "verified"} if slot["slot_id"] in active_ids else slot
            for slot in current["volume_slots"]
        ]
        return self._update(plan_id, {
            "plan_revision": current["plan_revision"],
            "input_inventory_revision": current["input_inventory_revision"],
            "mapping_revision": current["mapping_revision"],
            "volume_slots": slots, "verified_slots": verified,
        }, expected_revision)

    def update_mappings(
        self,
        plan_id: str,
        mappings: list[Mapping[str, Any]],
        expected_revision: int,
    ) -> dict[str, Any]:
        current = self.get(plan_id)
        if current["revision"] != expected_revision:
            raise RevisionConflictError("archive_plan", expected_revision, current["revision"])
        by_slot = {str(item.get("slot_id")): dict(item) for item in mappings}
        active_ids = {
            slot["slot_id"] for slot in current["volume_slots"]
            if slot["status"] != "removed"
        }
        if set(by_slot) != active_ids:
            raise WorkbenchPersistenceError("INVALID_DISC_MAPPING")
        slots = []
        for slot in current["volume_slots"]:
            if slot["status"] == "removed":
                slots.append(slot)
                continue
            mapping = by_slot[slot["slot_id"]]
            _mapping(slot["slot_id"], mapping)
            slots.append({
                **slot,
                "disc_mapping": mapping,
                "status": "active" if mapping["confirmation"] == "confirmed" else "pending",
            })
        _slots(slots)
        return self._update(plan_id, {
            "plan_revision": current["plan_revision"],
            "input_inventory_revision": current["input_inventory_revision"],
            "mapping_revision": current["mapping_revision"] + 1,
            "volume_slots": slots,
            "verified_slots": current["verified_slots"],
        }, expected_revision)

    def _update(
        self, plan_id: str, value: Mapping[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        now = utc_now()
        with self.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE archive_plans SET plan_revision=?,input_inventory_revision=?,"
                "mapping_revision=?,volume_slots_json=?,verified_slots_json=?,updated_at=?,"
                "revision=revision+1 WHERE plan_id=? AND revision=?",
                (
                    value["plan_revision"], value["input_inventory_revision"],
                    value["mapping_revision"], json_text(value["volume_slots"]),
                    json_text(value["verified_slots"]), now, plan_id, expected_revision,
                ),
            )
            if updated.rowcount != 1:
                actual = self.get(plan_id)["revision"]
                raise RevisionConflictError("archive_plan", expected_revision, actual)
        return self.get(plan_id)


def _slots(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_PLAN")
    result, ids, ordinals, disc_numbers = [], set(), set(), set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_PLAN")
        slot = dict(raw)
        slot_id = validate_opaque_id(slot.get("slot_id"))
        ordinal = _integer(slot.get("ordinal"))
        if slot_id in ids or ordinal in ordinals or slot.get("status") not in _SLOT_STATUSES:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_PLAN")
        if not isinstance(slot.get("lineage_key"), str) or not slot["lineage_key"]:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_PLAN")
        _integer(slot.get("plan_revision"))
        _integer(slot.get("planned_input_bytes"))
        _mapping(slot_id, slot.get("disc_mapping"))
        mapping = slot.get("disc_mapping")
        if mapping is not None and mapping.get("confirmation") == "confirmed":
            if mapping["disc_number"] in disc_numbers or not mapping["disc_number"]:
                raise WorkbenchPersistenceError("INVALID_DISC_MAPPING")
            disc_numbers.add(mapping["disc_number"])
        ids.add(slot_id)
        ordinals.add(ordinal)
        result.append(slot)
    return result


def _mapping(slot_id: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or value.get("slot_id") != slot_id:
        raise WorkbenchPersistenceError("INVALID_DISC_MAPPING")
    if value.get("source") not in {"default", "user"}:
        raise WorkbenchPersistenceError("INVALID_DISC_MAPPING")
    if value.get("confirmation") not in {"confirmed", "pending"}:
        raise WorkbenchPersistenceError("INVALID_DISC_MAPPING")
    if not isinstance(value.get("disc_number"), str) or not isinstance(value.get("disc_date"), str):
        raise WorkbenchPersistenceError("INVALID_DISC_MAPPING")


def _verified(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("INVALID_MANIFEST_SLOTS")
    result, ids = [], set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise WorkbenchPersistenceError("INVALID_MANIFEST_SLOTS")
        item = dict(raw)
        slot_id = validate_opaque_id(item.get("slot_id"))
        if slot_id in ids or not isinstance(item.get("md5"), str) or not item["md5"]:
            raise WorkbenchPersistenceError("INVALID_MANIFEST_SLOTS")
        _integer(item.get("ordinal"))
        _integer(item.get("output_bytes"))
        if not isinstance(item.get("disc_number"), str):
            raise WorkbenchPersistenceError("INVALID_MANIFEST_SLOTS")
        ids.add(slot_id)
        result.append(item)
    return result


def _merge_slot_history(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    new_ids = {slot["slot_id"] for slot in new}
    removed = [
        {**slot, "status": "removed"} for slot in old
        if slot["slot_id"] not in new_ids and slot["status"] != "removed"
    ]
    historical = [slot for slot in old if slot["status"] == "removed" and slot["slot_id"] not in new_ids]
    return [*new, *removed, *historical]


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_PLAN")
    return value


def _plan_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "plan_id": row["plan_id"], "schema_version": int(row["schema_version"]),
        "case_id": row["case_id"],
        "plan_revision": int(row["plan_revision"]),
        "input_inventory_revision": int(row["input_inventory_revision"]),
        "mapping_revision": int(row["mapping_revision"]),
        "volume_slots": row_json(row, "volume_slots_json"),
        "verified_slots": row_json(row, "verified_slots_json"),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "revision": int(row["revision"]),
    }
