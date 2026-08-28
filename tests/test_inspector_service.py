"""有序快照与旧版 DTO 兼容性的合成数据测试。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.inspector_repository import InspectorNotFoundError, InspectorRepository
from app.services.inspector_service import (
    InspectorService,
    apply_inspector_snapshot_compatibility,
)


def test_snapshots_follow_requested_order_and_capture_values(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    first = repository.create("甲", "单位甲", "职位甲", "001")
    second = repository.create("乙", "单位乙", "职位乙", "002")
    service = InspectorService(repository)

    snapshots = service.snapshots_from_ids([second.id, first.id])
    assert [item.selected_order for item in snapshots] == [0, 1]
    assert [item.name for item in snapshots] == ["乙", "甲"]
    repository.update(second.id, name="乙修改")
    assert snapshots[0].name == "乙"


def test_snapshot_selection_rejects_duplicates_and_missing_ids(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    record = repository.create("合成姓名", "合成单位", "合成职位", "001")
    service = InspectorService(repository)
    with pytest.raises(ValueError):
        service.snapshots_from_ids([record.id, record.id])
    with pytest.raises(InspectorNotFoundError):
        service.snapshots_from_ids(["missing-id"])


def test_snapshot_field_is_authoritative_over_legacy_projection():
    report = {
        "introduction": {
            "inspector_snapshots": [
                {"name": "快照姓名", "unit": "快照单位", "police_number": "S-001"}
            ],
            "inspectors": [
                {"name": "旧姓名", "unit": "旧单位", "badge_number": "OLD-001"}
            ],
        }
    }
    normalized = apply_inspector_snapshot_compatibility(report)
    assert normalized["introduction"]["inspector_snapshots"][0]["name"] == "快照姓名"
    assert normalized["introduction"]["inspectors"] == [
        {"name": "快照姓名", "unit": "快照单位", "position": "", "badge_number": "S-001"}
    ]
    assert report["introduction"]["inspectors"][0]["name"] == "旧姓名"


def test_legacy_inspectors_are_converted_in_order_without_library_id():
    normalized = apply_inspector_snapshot_compatibility(
        {
            "introduction": {
                "inspectors": [
                    {"name": "甲", "unit": "单位甲", "badge_number": "001"},
                    {"name": "乙", "unit": "单位乙", "badge_number": "002"},
                ]
            }
        }
    )
    assert normalized["introduction"]["inspector_snapshots"] == [
        {"name": "甲", "unit": "单位甲", "position": "", "police_number": "001"},
        {"name": "乙", "unit": "单位乙", "position": "", "police_number": "002"},
    ]
    assert all("id" not in item for item in normalized["introduction"]["inspector_snapshots"])


def test_legacy_missing_values_do_not_become_literal_none():
    normalized = apply_inspector_snapshot_compatibility(
        {"introduction": {"inspectors": [{"name": None, "unit": None, "badge_number": None}]}}
    )
    assert normalized["introduction"]["inspector_snapshots"] == [
        {"name": "", "unit": "", "position": "", "police_number": ""}
    ]
