"""基于持久计划仓储的稳定归档分卷映射。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable
from uuid import uuid4

from ...repository.archive.archive_plan_repository import ArchivePlanRepository
from ...repository.workbench.workbench_errors import WorkbenchPersistenceError


class ArchiveMappingService:
    def __init__(
        self,
        plans: ArchivePlanRepository,
        *,
        create_slot_id: Callable[[], str] | None = None,
    ) -> None:
        self.plans = plans
        self.create_slot_id = create_slot_id or (lambda: str(uuid4()))

    def create(
        self,
        *,
        plan_id: str,
        case_id: str,
        input_inventory_revision: int,
        mapping_revision: int,
        planned_slots: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        slots = self._reconcile([], planned_slots, plan_revision=1)
        return self.plans.create({
            "plan_id": plan_id,
            "case_id": case_id,
            "plan_revision": 1,
            "input_inventory_revision": input_inventory_revision,
            "mapping_revision": mapping_revision,
            "volume_slots": slots,
        })

    def replan(
        self,
        plan_id: str,
        planned_slots: list[Mapping[str, Any]],
        *,
        input_inventory_revision: int,
        mapping_revision: int,
        expected_revision: int,
    ) -> dict[str, Any]:
        current = self.plans.get(plan_id)
        slots = self._reconcile(
            current["volume_slots"], planned_slots,
            plan_revision=current["plan_revision"] + 1,
        )
        return self.plans.replan(
            plan_id, slots,
            input_inventory_revision=input_inventory_revision,
            mapping_revision=mapping_revision,
            expected_revision=expected_revision,
        )

    def _reconcile(
        self,
        previous: list[dict[str, Any]],
        planned: list[Mapping[str, Any]],
        *,
        plan_revision: int,
    ) -> list[dict[str, Any]]:
        old = {
            slot["lineage_key"]: slot
            for slot in previous if slot["status"] != "removed"
        }
        result = []
        for ordinal, raw in enumerate(planned, start=1):
            lineage_key = str(raw.get("lineage_key", "")).strip()
            if not lineage_key:
                raise ValueError("INVALID_ARCHIVE_PLAN")
            prior = old.get(lineage_key)
            mapping = prior.get("disc_mapping") if prior else raw.get("disc_mapping")
            slot_id = prior["slot_id"] if prior else self.create_slot_id()
            if mapping is not None:
                mapping = {**mapping, "slot_id": slot_id}
            result.append({
                "slot_id": slot_id,
                "ordinal": ordinal,
                "lineage_key": lineage_key,
                "planned_input_bytes": _planned_bytes(
                    raw.get("planned_input_bytes", 0)
                ),
                "plan_revision": plan_revision,
                "status": (
                    "active"
                    if mapping and mapping.get("confirmation") == "confirmed"
                    else "pending"
                ),
                "disc_mapping": mapping,
            })
        return result


def _planned_bytes(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("INVALID_ARCHIVE_PLAN")
    return value


def persist_archive_plan(
    plans: ArchivePlanRepository,
    *,
    plan_id: str,
    case_id: str,
    manifest_parts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """将已执行计划及其 Manifest 分卷投影到 `archive_plans`。

    每个 Manifest 分卷成为以文件名为键的分卷槽位，使后续延迟光盘映射（REQ-030）
    指向 Manifest 来源的同一槽位。压缩可在输入任何光盘编号前运行，因此槽位初始没有映射。
    案件已有持久计划时不执行操作。
    """
    existing = plans.get_latest_for_case(case_id)
    if existing is not None:
        return existing
    slots: list[dict[str, Any]] = []
    for part in manifest_parts:
        filename = str(part.get("filename") or "").strip()
        if not filename:
            continue
        disc_number = str(part.get("disc_number") or "").strip()
        slots.append({
            "lineage_key": filename,
            "planned_input_bytes": int(part.get("size_bytes") or 0),
            "disc_mapping": (
                {
                    "disc_number": disc_number,
                    "disc_date": str(part.get("disc_date") or ""),
                    "source": "default",
                    "confirmation": "confirmed",
                }
                if disc_number else None
            ),
        })
    if not slots:
        raise WorkbenchPersistenceError("ARCHIVE_PLAN_EMPTY", "归档计划没有可映射的分卷。")
    return ArchiveMappingService(plans).create(
        plan_id=plan_id, case_id=case_id,
        input_inventory_revision=0, mapping_revision=0, planned_slots=slots,
    )


def persist_archive_plan_for_attempt(
    attempt_service: Any, attempt_id: str | None, plan: Any, manifest: Mapping[str, Any],
) -> None:
    """根据已完成尝试的 Manifest 分卷尽力投影计划。"""
    if attempt_service is None or attempt_id is None:
        return
    from ...repository.archive.archive_plan_repository import ArchivePlanRepository

    case_id = str(attempt_service.repository.get_internal(attempt_id).get("case_id") or "")
    if not case_id:
        return
    persist_archive_plan(
        ArchivePlanRepository(attempt_service.database),
        plan_id=plan.plan_id, case_id=case_id,
        manifest_parts=list(manifest.get("parts", [])),
    )
