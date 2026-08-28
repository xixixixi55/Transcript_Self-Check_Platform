"""持久化案件字段来源的 SYNTHETIC T009 覆盖测试。"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.field_provenance_service import FieldProvenanceService  # noqa: E402


EVIDENCE_COMPLETENESS_FIELD_PATH = "introduction.evidence_list.completeness"


def _report(model: str = ""):
    return {
        "document_number": "SYNTHETIC-DOC", "introduction": {
            "evidence_list": [{"evidence_id": "SYNTHETIC-EVIDENCE-1", "evidence_number": "SYNTHETIC-1", "model": model}],
            "inspector_snapshots": [{"snapshot_id": "SYNTHETIC-SNAPSHOT-1", "name": "SYNTHETIC-A", "unit": "SYNTHETIC-U", "police_number": "SYNTHETIC-001", "selected_order": 0}],
        },
        "attachments": {"photo_groups": [{"material_id": "SYNTHETIC-MATERIAL-1", "material_number": "SYNTHETIC-1", "display_text": "SYNTHETIC", "ordered_image_ids": ["SYNTHETIC-IMG-1", "SYNTHETIC-IMG-2"], "source_order": 0}]},
    }


def test_initializes_evidence_inspector_and_photo_group_state_then_marks_edit_as_user():
    service = FieldProvenanceService()
    initial_report = _report()
    initial_states = service.initialize(initial_report)
    edited_report = _report("SYNTHETIC-USER-MODEL")
    submitted = copy.deepcopy(initial_states)
    submitted["evidence.SYNTHETIC-EVIDENCE-1.model"]["confirmation"] = "pending"

    states = service.reconcile(initial_report, initial_states, edited_report, submitted)

    assert initial_states["evidence.SYNTHETIC-EVIDENCE-1.model"]["source"] == "system_default"
    assert initial_states["evidence.SYNTHETIC-EVIDENCE-1.model"]["confirmation"] == "pending"
    assert states["evidence.SYNTHETIC-EVIDENCE-1.model"] | {"last_changed_at": ""} == {
        "field_path": "evidence.SYNTHETIC-EVIDENCE-1.model", "subject_id": "SYNTHETIC-EVIDENCE-1",
        "source": "user", "confirmation": "pending", "revision": 1, "last_changed_at": "",
    }
    assert states["inspectors.SYNTHETIC-SNAPSHOT-1.name"]["source"] == "report"
    assert states["photo_groups.SYNTHETIC-MATERIAL-1"]["subject_id"] == "SYNTHETIC-MATERIAL-1"


def test_preserves_submitted_evidence_completeness_confirmation():
    service = FieldProvenanceService()
    report = _report()
    initial_states = service.initialize(report)
    submitted = copy.deepcopy(initial_states)
    submitted[EVIDENCE_COMPLETENESS_FIELD_PATH] = {
        "field_path": EVIDENCE_COMPLETENESS_FIELD_PATH,
        "source": "user",
        "confirmation": "confirmed",
        "revision": 1,
        "last_changed_at": "2026-08-21T00:00:00Z",
    }

    states = service.reconcile(report, initial_states, report, submitted)

    assert states[EVIDENCE_COMPLETENESS_FIELD_PATH] == submitted[EVIDENCE_COMPLETENESS_FIELD_PATH]
