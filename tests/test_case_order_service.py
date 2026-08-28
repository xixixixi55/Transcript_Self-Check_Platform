"""案件范围证据与检查人员排序的 SYNTHETIC T009 覆盖测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.case_order_service import CaseOrderService  # noqa: E402


def _service() -> CaseOrderService:
    identifiers = iter(range(1, 20))
    return CaseOrderService(lambda prefix: f"SYNTHETIC-{prefix}-{next(identifiers)}")


def test_new_case_uses_natural_evidence_order_and_creates_stable_card_ids():
    report = {"introduction": {
        "evidence_list": [
            {"evidence_number": "SYNTHETIC-10", "model": "SYNTHETIC-10"},
            {"evidence_number": "SYNTHETIC-2", "model": "SYNTHETIC-2"},
            {"evidence_number": "SYNTHETIC-1", "model": "SYNTHETIC-1"},
        ],
        "inspectors": [{"name": "SYNTHETIC-A", "unit": "SYNTHETIC-U", "badge_number": "SYNTHETIC-001"}],
    }}

    initialized = _service().initialize(report)

    assert [item["evidence_number"] for item in initialized["introduction"]["evidence_list"]] == [
        "SYNTHETIC-1", "SYNTHETIC-2", "SYNTHETIC-10",
    ]
    assert all(item["evidence_id"].startswith("SYNTHETIC-evidence-") for item in initialized["introduction"]["evidence_list"])
    assert initialized["introduction"]["inspector_snapshots"] == [{
        "snapshot_id": "SYNTHETIC-inspector-4", "name": "SYNTHETIC-A",
        "unit": "SYNTHETIC-U", "position": "", "police_number": "SYNTHETIC-001", "selected_order": 0,
    }]


def test_duplicate_or_unrecognizable_parser_numbers_keep_source_order_and_save_never_resorts():
    report = {"introduction": {"evidence_list": [
        {"evidence_number": "SYNTHETIC-10"}, {"evidence_number": "SYNTHETIC-2"},
        {"evidence_number": "SYNTHETIC-02"}, {"evidence_number": "SYNTHETIC-UNKNOWN"},
    ]}}
    service = _service()
    initialized = service.initialize(report)
    edited = {"introduction": {"evidence_list": list(reversed(initialized["introduction"]["evidence_list"]))}}

    saved = service.prepare_save(initialized, edited)

    assert [item["evidence_number"] for item in initialized["introduction"]["evidence_list"]] == [
        "SYNTHETIC-10", "SYNTHETIC-2", "SYNTHETIC-02", "SYNTHETIC-UNKNOWN",
    ]
    assert [item["evidence_number"] for item in saved["introduction"]["evidence_list"]] == [
        "SYNTHETIC-UNKNOWN", "SYNTHETIC-02", "SYNTHETIC-2", "SYNTHETIC-10",
    ]
    assert [item["evidence_id"] for item in saved["introduction"]["evidence_list"]] == [
        item["evidence_id"] for item in reversed(initialized["introduction"]["evidence_list"])
    ]
