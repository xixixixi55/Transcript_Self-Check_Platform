"""失败开放 Shadow 边车的合成数据生产链测试。"""

import copy
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.main import app
from app.config import OUTPUT_BASE
from app.repository.archive.archive_authorization_repository import ArchiveAuthorizationStore
from app.services.archive.archive_execution_service import ArchiveExecutionOutcome
from app.services.archive.archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveRuntimeError
from app.services.archive import archive_source_runtime_service
from app.services.archive.archive_source_runtime_service import (
    ArchiveSourceRuntimeStore,
    create_preview_source,
    prepare_archive_source,
)
from app.services.pipeline_runtime_service import load_pipeline_settings
from app.services.shadow_pipeline_service import run_shadow_archive, run_shadow_export, run_shadow_parse
from app.services.shadow_runtime_service import SHADOW_RUNTIME_STORE


SYNTHETIC_REPORT = {
    "title": "电子数据检查笔录", "document_number": "SYNTHETIC-2026-001",
    "case_number": "SYNTHETIC-CASE-001",
    "introduction": {
        "case_summary": "SYNTHETIC-CASE", "inspection_time_range": "SYNTHETIC-TIME",
        "evidence_list": [{
            "id": "synthetic-material-1", "evidence_number": "SYNTHETIC-E-001",
            "device_type": "手机", "material_type": "phone",
            "material_type_status": "confirmed_by_report", "material_type_source": "report",
            "imei1": "SYNTHETIC-IMEI-1",
        }],
        "inspectors": [{"name": "SYNTHETIC-INSPECTOR", "unit": "SYNTHETIC-UNIT", "badge_number": "SYNTHETIC-BADGE"}],
    },
    "inspection": {
        "hardware_device": "SYNTHETIC-HARDWARE",
        "primary_software": {"name": "SYNTHETIC-FORENSIC", "version": "1.0", "confirmation_status": "confirmed_by_report"},
        "software_tools": [
            {"name": "WinRAR压缩管理软件", "version": "7.0"},
            {"name": "Python hashlib", "version": "3.12"},
        ],
        "result": {},
    },
    "attachments": {"disc_number": "GP20260722-01", "photo_ids": []},
}

SYNTHETIC_MANIFEST = {
    "manifest_id": "synthetic-manifest-1", "validation_status": "validated",
    "archive_base_name": "SYNTHETIC-CASE", "volume_tier_gb": 4,
    "volume_size_bytes": 4_000_000_000, "total_input_bytes": 1, "actual_archive_bytes": 123,
    "parts": [{
        "part_id": "synthetic-part-1", "part_number": 1, "filename": "SYNTHETIC-CASE.rar",
        "size_bytes": 123, "md5": "a" * 32, "disc_capacity_bytes": 4_000_000_000,
        "disc_number": "GP20260722-01", "disc_date": "2026-07-22",
    }],
}


def _context():
    item = SimpleNamespace(relative_path="data/SYNTHETIC.json", size_bytes=1, modified_time_ns=1)
    return SimpleNamespace(inventory=SimpleNamespace(files=(item,)))


@pytest.fixture(autouse=True)
def clean_shadow_store():
    SHADOW_RUNTIME_STORE.clear()
    yield
    SHADOW_RUNTIME_STORE.clear()


@pytest.fixture
def shadow_client():
    previous = app.state.pipeline_settings
    app.state.pipeline_settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    with TestClient(app) as client:
        yield client
    app.state.pipeline_settings = previous


@pytest.fixture
def synthetic_archive_source(tmp_path):
    """为控制器测试注册并准备真实的合成预览源。"""
    source_root = tmp_path / "synthetic-source"
    source_root.mkdir()
    (source_root / "SYNTHETIC-input.bin").write_bytes(b"SYNTHETIC")
    authorization = ArchiveAuthorizationStore(str(tmp_path), environment={})
    authorized_input = authorization.authorize_directory(
        str(source_root), output_roots=(OUTPUT_BASE,),
    )
    source_store = ArchiveSourceRuntimeStore()
    with patch.object(
        archive_source_runtime_service, "ARCHIVE_SOURCE_RUNTIME_STORE", source_store,
    ):
        source_id = create_preview_source(authorized_input)
        formal_context_id = prepare_archive_source(
            source_id, copy.deepcopy(SYNTHETIC_REPORT), output_root=OUTPUT_BASE,
        )
        try:
            yield SimpleNamespace(
                source_id=source_id,
                formal_context_id=formal_context_id,
            )
        finally:
            with ARCHIVE_RUNTIME_STORE._lock:
                ARCHIVE_RUNTIME_STORE._contexts.pop(formal_context_id, None)


def _pipeline(client, context_id):
    from app.controllers import pipeline_controller
    with patch.object(
        pipeline_controller.ARCHIVE_RUNTIME_STORE, "get_context_summary",
        return_value={"archive_context_id": context_id, "status": "idle"},
    ):
        response = client.get(f"/api/v1/records/archive/{context_id}/pipeline")
    assert response.status_code == 200
    return response.json()["data"]


def test_shadow_service_runs_parse_archive_export_without_formal_execution():
    report = copy.deepcopy(SYNTHETIC_REPORT)
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    with patch("app.services.archive.archive_execution_service.execute_archive") as execute, \
         patch("app.services.record_generator_service.generate_docx") as render, \
         patch("app.services.shadow_pipeline_service.ARCHIVE_RUNTIME_STORE.get_context_snapshot", return_value=_context()):
        parsed = run_shadow_parse(report, settings, "synthetic-context")
        archived = run_shadow_archive("synthetic-context", report, SYNTHETIC_MANIFEST, _context(), settings)
        exported = run_shadow_export("synthetic-context", report, SYNTHETIC_MANIFEST, settings)

    assert parsed["stages"]["parse"]["status"] == "matched"
    assert parsed["status"] == "partial"
    assert archived["stages"]["archive"]["status"] == "not_comparable"
    assert "ARCHIVE_ROOT_PRESERVATION_NOT_COMPARABLE" in archived["diagnostic_codes"]
    assert exported["stages"]["export"]["status"] == "matched"
    execute.assert_not_called()
    render.assert_not_called()
    rendered = json.dumps(exported, ensure_ascii=False)
    for sensitive in ("SYNTHETIC-CASE-001", "SYNTHETIC-IMEI-1", "SYNTHETIC-INSPECTOR"):
        assert sensitive not in rendered


def test_shadow_observers_are_noops_when_pipeline_mode_is_legacy():
    from app.controllers import pipeline_controller

    tasks = MagicMock()
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "legacy"})
    pipeline_controller.observe_shadow_parse(SYNTHETIC_REPORT, settings, "SYNTHETIC-context", tasks)
    pipeline_controller.observe_shadow_archive(
        "SYNTHETIC-context", SYNTHETIC_REPORT, SYNTHETIC_MANIFEST, settings, tasks,
    )
    pipeline_controller.observe_shadow_export(
        "SYNTHETIC-context", SYNTHETIC_REPORT, SYNTHETIC_MANIFEST, settings, tasks,
    )

    tasks.add_task.assert_not_called()
    assert SHADOW_RUNTIME_STORE.size() == 0


def test_shadow_chain_keeps_formal_legacy_facts_independent_from_canonical_source():
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    formal_legacy_report = copy.deepcopy(SYNTHETIC_REPORT)
    formal_legacy_report["case_number"] = "SYNTHETIC-FORMAL-LEGACY-CASE"

    with patch.object(
        ARCHIVE_RUNTIME_STORE, "get_context_snapshot", return_value=_context(),
    ):
        result = run_shadow_archive(
            "SYNTHETIC-context", formal_legacy_report, SYNTHETIC_MANIFEST, _context(), settings,
            canonical_source=SYNTHETIC_REPORT,
        )

    codes = result["stages"]["archive"]["comparison"]["diagnostic_codes"]
    assert "CASE_NUMBER_MISMATCH" in codes


def test_shadow_archive_expected_values_are_from_independent_plan_not_manifest():
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    tampered_manifest = copy.deepcopy(SYNTHETIC_MANIFEST)
    tampered_manifest["volume_tier_gb"] = 22
    tampered_manifest["total_input_bytes"] = 999
    tampered_manifest["parts"][0]["disc_number"] = "GP20260722-02"

    with patch.object(
        ARCHIVE_RUNTIME_STORE, "get_context_snapshot", return_value=_context(),
    ):
        result = run_shadow_archive(
            "SYNTHETIC-context", SYNTHETIC_REPORT, tampered_manifest, _context(), settings,
        )

    codes = result["stages"]["archive"]["comparison"]["diagnostic_codes"]
    assert "ARCHIVE_VOLUME_TIER_MISMATCH" in codes
    assert "ARCHIVE_INPUT_TOTAL_BYTES_MISMATCH" in codes
    assert "ARCHIVE_DISC_NUMBER_MISMATCH" in codes


def test_shadow_archive_page_counts_use_independent_part_plan_not_manifest():
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    tampered_manifest = copy.deepcopy(SYNTHETIC_MANIFEST)
    tampered_manifest["parts"] = [
        {
            "part_id": f"synthetic-part-{number}", "part_number": number,
            "filename": f"SYNTHETIC-CASE.part{number}.rar", "size_bytes": 123,
            "md5": "a" * 32, "disc_capacity_bytes": 4_000_000_000,
            "disc_number": f"GP20260722-{number:02d}", "disc_date": "2026-07-22",
        }
        for number in range(1, 6)
    ]

    with patch.object(
        ARCHIVE_RUNTIME_STORE, "get_context_snapshot", return_value=_context(),
    ):
        result = run_shadow_archive(
            "SYNTHETIC-context", SYNTHETIC_REPORT, tampered_manifest, _context(), settings,
        )

    codes = result["stages"]["archive"]["comparison"]["diagnostic_codes"]
    assert "ARCHIVE_PART_COUNT_MISMATCH" in codes
    assert "ATTACHMENT1_PAGE_COUNT_MISMATCH" in codes


def test_legacy_docx_failure_keeps_previous_shadow_stages(shadow_client):
    from app.controllers import pipeline_controller

    run_shadow_parse(
        copy.deepcopy(SYNTHETIC_REPORT),
        load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"}),
        "SYNTHETIC-context",
    )
    pipeline_controller.record_shadow_export_failure_at_controller(
        load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"}), "SYNTHETIC-context",
    )

    summary = _pipeline(shadow_client, "SYNTHETIC-context")
    assert summary["stages"]["parse"]["status"] == "matched"
    assert summary["stages"]["export"]["status"] == "failed"


def test_archive_controller_constructs_legacy_and_canonical_sources_separately(
    shadow_client, synthetic_archive_source,
):
    from app.controllers import archive_controller

    formal_legacy_report = copy.deepcopy(SYNTHETIC_REPORT)
    formal_legacy_report["case_number"] = "SYNTHETIC-FORMAL-LEGACY-CASE"
    record = MagicMock(public_manifest=SYNTHETIC_MANIFEST)
    with patch.object(
        archive_controller, "execute_archive",
        return_value=ArchiveExecutionOutcome("completed", "synthetic-manifest-1", None),
    ), patch.object(
        archive_controller.ARCHIVE_RUNTIME_STORE, "get_manifest", return_value=record,
    ), patch.object(
        archive_controller.ARCHIVE_RUNTIME_STORE, "get_context_snapshot", return_value=_context(),
    ), patch.object(
        archive_controller, "project_manifest_to_legacy_report_with_plan",
        return_value=(formal_legacy_report, None),
    ):
        response = shadow_client.post("/api/v1/records/archive", data={
            "archive_context_id": synthetic_archive_source.source_id,
            "report_json": json.dumps(SYNTHETIC_REPORT, ensure_ascii=False),
        })

    assert response.status_code == 200
    summary = SHADOW_RUNTIME_STORE.public_summary(
        context_id=synthetic_archive_source.source_id,
    )
    codes = summary["stages"]["archive"]["comparison"]["diagnostic_codes"]
    assert "CASE_NUMBER_MISMATCH" in codes


def test_shadow_archive_stops_when_archive_context_expires():
    settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"})
    with patch.object(
        ARCHIVE_RUNTIME_STORE, "get_context_snapshot",
        side_effect=ArchiveRuntimeError("ARCHIVE_CONTEXT_EXPIRED", "expired"),
    ):
        result = run_shadow_archive(
            "SYNTHETIC-context", SYNTHETIC_REPORT, SYNTHETIC_MANIFEST, _context(), settings,
        )

    assert result["stages"]["archive"]["status"] == "not_comparable"
    assert "ARCHIVE_CONTEXT_EXPIRED" in result["diagnostic_codes"]


def test_shadow_parser_failure_is_queryable_and_does_not_change_legacy_response(shadow_client, tmp_path):
    from app.controllers import pipeline_controller, record_controller
    from app.services.archive.archive_authorization_service import ArchiveAuthorizationService

    case_dir = tmp_path / "synthetic-case"
    case_dir.mkdir()
    authorization = ArchiveAuthorizationService(str(tmp_path), record_controller.OUTPUT_BASE)
    with patch.object(record_controller, "parse_report", return_value={"report": copy.deepcopy(SYNTHETIC_REPORT)}), \
         patch.object(record_controller, "ARCHIVE_AUTHORIZATION_SERVICE", authorization), \
         patch.object(pipeline_controller, "run_shadow_parse", side_effect=RuntimeError("SYNTHETIC shadow failure")):
        response = shadow_client.post("/api/v1/reports/parse", data={"report_dir": str(case_dir)})

    assert response.status_code == 200
    assert "pipeline" not in response.json()["data"]
    summary = _pipeline(shadow_client, response.json()["data"]["archive_context_id"])
    assert summary["stages"]["parse"]["status"] == "failed"
    assert "SHADOW_RUNTIME_FAILED" in summary["diagnostic_codes"]


def test_shadow_archive_failure_keeps_legacy_manifest_and_records_failure(
    shadow_client, synthetic_archive_source,
):
    from app.controllers import archive_controller, pipeline_controller

    manifest = {"manifest_id": "synthetic-manifest", "validation_status": "validated", "parts": []}
    record = MagicMock(public_manifest=manifest)
    with patch.object(archive_controller, "execute_archive", return_value=ArchiveExecutionOutcome("completed", "synthetic-manifest", None)) as execute, \
         patch.object(archive_controller.ARCHIVE_RUNTIME_STORE, "get_manifest", return_value=record), \
         patch.object(archive_controller.ARCHIVE_RUNTIME_STORE, "get_context_snapshot", return_value=MagicMock()), \
         patch.object(archive_controller, "project_manifest_to_legacy_report_with_plan", return_value=({"attachments": {"extract_list": {"rows": []}}}, None)), \
         patch.object(pipeline_controller, "run_shadow_archive", side_effect=RuntimeError("SYNTHETIC shadow archive failure")):
        response = shadow_client.post("/api/v1/records/archive", data={"archive_context_id": synthetic_archive_source.source_id, "report_json": "{}"})

    assert response.status_code == 200
    assert "pipeline" not in response.json()["data"]
    assert response.json()["data"]["manifest_id"] == "synthetic-manifest"
    summary = _pipeline(shadow_client, synthetic_archive_source.source_id)
    assert summary["stages"]["archive"]["status"] == "failed"
    execute.assert_called_once()


def test_shadow_export_failure_does_not_create_second_docx(
    shadow_client, tmp_path, synthetic_archive_source,
):
    from app.controllers import pipeline_controller, record_controller

    docx = tmp_path / "synthetic-output.docx"
    docx.write_bytes(b"synthetic-docx")
    report = copy.deepcopy(SYNTHETIC_REPORT)
    with patch.object(record_controller, "get_valid_manifest", return_value=SYNTHETIC_MANIFEST), \
         patch.object(record_controller, "project_manifest_to_legacy_report_with_plan", return_value=(report, None)), \
         patch.object(record_controller, "generate_docx", return_value=str(docx)) as generate, \
         patch.object(pipeline_controller, "run_shadow_export", side_effect=RuntimeError("SYNTHETIC shadow export failure")):
        response = shadow_client.post("/api/v1/records/export", data={
            "report_json": json.dumps(report, ensure_ascii=False),
            "archive_context_id": synthetic_archive_source.source_id, "manifest_id": "synthetic-manifest-1",
        })

    assert response.status_code == 200
    assert response.content == b"synthetic-docx"
    generate.assert_called_once()
    summary = _pipeline(shadow_client, synthetic_archive_source.formal_context_id)
    assert summary["stages"]["export"]["status"] == "failed"
    assert "SHADOW_RUNTIME_FAILED" in summary["diagnostic_codes"]


def test_legacy_docx_failure_is_not_reported_as_shadow_matched(
    shadow_client, synthetic_archive_source,
):
    from app.controllers import record_controller

    report = copy.deepcopy(SYNTHETIC_REPORT)
    with patch.object(record_controller, "get_valid_manifest", return_value=SYNTHETIC_MANIFEST), \
         patch.object(record_controller, "project_manifest_to_legacy_report_with_plan", return_value=(report, None)), \
         patch.object(record_controller, "generate_docx", side_effect=RuntimeError("SYNTHETIC docx failure")):
        response = shadow_client.post("/api/v1/records/export", data={
            "report_json": json.dumps(report, ensure_ascii=False),
            "archive_context_id": synthetic_archive_source.source_id, "manifest_id": "synthetic-manifest-1",
        })

    assert response.status_code == 500
    summary = _pipeline(shadow_client, synthetic_archive_source.source_id)
    assert summary["stages"]["export"]["status"] == "failed"
    assert "LEGACY_DOCX_RENDER_FAILED" in summary["diagnostic_codes"]


def test_canonical_controller_mode_is_explicitly_rejected_without_legacy_fallback():
    previous = app.state.pipeline_settings
    app.state.pipeline_settings = load_pipeline_settings({"BIJI_PIPELINE_MODE": "canonical"})
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/reports/parse", data={})
    finally:
        app.state.pipeline_settings = previous

    assert response.status_code == 501
    assert response.json()["detail"]["code"] == "CANONICAL_NOT_ENABLED"


def test_shadow_diagnostics_query_rejects_invalid_archive_context_and_hides_run_id(shadow_client):
    from app.controllers import pipeline_controller
    from app.services.archive.archive_runtime_service import ArchiveRuntimeError

    handle = run_shadow_parse(
        copy.deepcopy(SYNTHETIC_REPORT),
        load_pipeline_settings({"BIJI_PIPELINE_MODE": "shadow"}),
        "SYNTHETIC-invalid-context",
    )
    assert handle["status"] == "partial"
    with patch.object(
        pipeline_controller.ARCHIVE_RUNTIME_STORE, "get_context_summary",
        side_effect=ArchiveRuntimeError("ARCHIVE_CONTEXT_EXPIRED", "expired"),
    ):
        response = shadow_client.get("/api/v1/records/archive/SYNTHETIC-invalid-context/pipeline")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARCHIVE_CONTEXT_EXPIRED"
    assert "run_id" not in json.dumps(response.json(), ensure_ascii=False)
