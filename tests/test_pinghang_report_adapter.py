"""平航报告适配器的 SYNTHETIC/TEST 回归。"""

import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.report.pinghang_jsonp_repository import (  # noqa: E402
    PinghangPayloadError,
    parse_pinghang_payload,
)
from app.repository.report.report_adapter_registry import (  # noqa: E402
    ReportAdapterDetectionError,
    detect_report_adapter,
)
from app.repository.report.report_format_adapter import ReportFormat  # noqa: E402
from app.repository.report.report_parse_input_repository import (  # noqa: E402
    build_report_parse_input_snapshot,
)
from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.services.archive.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
from app.services.case.case_draft_service import CaseDraftService  # noqa: E402
from app.services.case.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.report.report_parser_service import parse_report  # noqa: E402
from app.services.source.source_record_service import SourceRecordService  # noqa: E402


class _PassthroughEnvironment:
    def apply_to_report(self, report):
        return report


def _jsonp(index: int, payload: object) -> str:
    body = json.dumps(payload, ensure_ascii=False)
    return f";static.report.records.data_{index}_1 = {body};"


def _table(rows: list[tuple[str, str]], *, info_type: str = "Table") -> dict:
    return {
        "Info": {"type": info_type},
        "Data": [
            {"Val0": ["Text", label], "Val1": ["Text", value]}
            for label, value in rows
        ],
    }


def _device(rows: list[tuple[str, str]]) -> dict:
    return {
        "Info": {"type": "DeviceInfo"},
        "Data": [
            {"Val1": [label], "Val2": [value]}
            for label, value in rows
        ],
    }


def _nav_name(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _write_pinghang_fixture(
    root: Path, *, duplicate_device_node: bool = False,
    duplicate_case_node: bool = False,
) -> Path:
    view_data = root / "报告" / "data" / "ViewData"
    view_data.mkdir(parents=True)
    (root / "SYNTHETIC-平航手机多路取证报告.html").write_text(
        "<title>平航手机多路取证报告 SYNTHETIC/TEST</title>", encoding="utf-8",
    )
    navigation = [
        {"id": 10, "pid": 0, "name": _nav_name("案件信息"), "dataIndex": "11", "viewType": "Table", "rangeCount": 1},
        {"id": 1, "pid": 0, "name": _nav_name("SYNTHETIC-设备-B"), "dataIndex": "7", "viewType": "DeviceInfo", "rangeCount": 1},
        {"id": 2, "pid": 0, "name": _nav_name("SYNTHETIC-设备-A"), "dataIndex": "4", "viewType": "DeviceInfo", "rangeCount": 1},
    ]
    if duplicate_device_node:
        navigation.append(
            {"id": 3, "pid": 0, "name": _nav_name("SYNTHETIC-重复设备"), "dataIndex": "7", "viewType": "DeviceInfo", "rangeCount": 1}
        )
    if duplicate_case_node:
        navigation.append(
            {"id": 12, "pid": 0, "name": _nav_name("案件信息"), "dataIndex": "13", "viewType": "Table", "rangeCount": 1}
        )
    nav_objects = ",\n".join(
        "{" + ",".join(
            f"{key}:'{value}'" if isinstance(value, str) else f"{key}:{value}"
            for key, value in node.items()
        ) + "}"
        for node in navigation
    )
    (root / "报告" / "data" / "navigation_data.js").write_text(
        f";window.static.report.zNodes = [{nav_objects}];", encoding="utf-8",
    )
    (view_data / "11_1.json").write_text(_jsonp(11, _table([
        ("案件名称", "SYNTHETIC-案件"),
        ("案件编号", "SYNTHETIC-CASE-001"),
        ("案件描述", "SYNTHETIC-案情摘要"),
        ("创建时间", "2026-01-02 03:04:05"),
    ])), encoding="utf-8")
    (view_data / "0_1.json").write_text(_jsonp(0, _table([
        ("数据取证软件版本", "SYNTHETIC-PH 1.2.3"),
        ("报告导出软件版本", "SYNTHETIC-EXPORT 4.5.6"),
        ("报告完成日期", "2026-01-02 05:06:07"),
    ])), encoding="utf-8")
    (view_data / "7_1.json").write_text(_jsonp(7, _device([
        ("检材名称", "SYNTHETIC-设备-B"),
        ("检材编号", "SYNTHETIC-EVIDENCE-20"),
        ("数据类型", "Android设备"),
        ("设备品牌", "SYNTHETIC-BRAND-B"),
        ("设备型号", "SYNTHETIC-MODEL-B"),
        ("IMEI", "111111111111111"),
        ("序列码", "SYNTHETIC-SERIAL-B"),
        ("取证开始时间", "2026-01-02 03:10:00"),
        ("取证结束时间", "2026-01-02 03:20:00"),
    ])), encoding="utf-8")
    (view_data / "4_1.json").write_text(_jsonp(4, _device([
        ("检材名称", "SYNTHETIC-设备-A"),
        ("检材编号", "SYNTHETIC-EVIDENCE-10"),
        ("数据类型", "Android设备"),
        ("设备品牌", "SYNTHETIC-BRAND-A"),
        ("设备型号", "SYNTHETIC-MODEL-A"),
        ("IMEI", "222222222222222"),
        ("IMEI2", "333333333333333"),
        ("序列码", "SYNTHETIC-SERIAL-A"),
    ])), encoding="utf-8")
    return root


def test_registry_and_snapshot_parse_pinghang_semantically(tmp_path):
    source = _write_pinghang_fixture(tmp_path)

    match = detect_report_adapter(source)
    snapshot = build_report_parse_input_snapshot(str(source))

    assert match.adapter_id == "pinghang-mobile-multipath-v1"
    assert match.report_format == ReportFormat.PINGHANG
    assert snapshot.adapter_id == match.adapter_id
    assert snapshot.adapter_version == match.adapter_version
    assert snapshot.structure_fingerprint == match.structure_fingerprint
    assert snapshot.case_info["case_summary"] == "SYNTHETIC-案情摘要"
    assert [row["evidence_number"] for row in snapshot.device_rows] == [
        "SYNTHETIC-EVIDENCE-20", "SYNTHETIC-EVIDENCE-10",
    ]
    assert snapshot.device_base_info["SYNTHETIC-EVIDENCE-10"]["imei2"] == (
        "333333333333333"
    )
    assert any(item.relative_path == "报告/data/navigation_data.js" for item in snapshot.dependencies)


def test_pinghang_adapter_version_and_content_participate_in_input_fingerprint(tmp_path):
    source = _write_pinghang_fixture(tmp_path)
    before = build_report_parse_input_snapshot(str(source))
    case_page = source / "报告" / "data" / "ViewData" / "11_1.json"
    case_page.write_text(
        case_page.read_text(encoding="utf-8").replace(
            "SYNTHETIC-案件", "SYNTHETIC-案件-已变更",
        ),
        encoding="utf-8",
    )
    changed_content = build_report_parse_input_snapshot(str(source))
    with patch(
        "app.repository.report.report_parse_input_repository.PINGHANG_ADAPTER_VERSION",
        "1.0.1-TEST",
    ):
        changed_adapter = build_report_parse_input_snapshot(str(source))

    assert changed_content.structure_fingerprint == before.structure_fingerprint
    assert changed_content.dependency_fingerprint != before.dependency_fingerprint
    assert changed_adapter.adapter_version == "1.0.1-TEST"
    assert changed_adapter.dependency_fingerprint != changed_content.dependency_fingerprint


def test_parse_report_keeps_ambiguous_android_material_unconfirmed(tmp_path):
    source = _write_pinghang_fixture(tmp_path)

    result = parse_report(str(source), str(tmp_path / "output"), compress=False)

    report = result["report"]
    assert report["introduction"]["case_summary"] == "SYNTHETIC-案情摘要"
    assert [item["evidence_number"] for item in report["introduction"]["evidence_list"]] == [
        "SYNTHETIC-EVIDENCE-20", "SYNTHETIC-EVIDENCE-10",
    ]
    assert all(
        item["material_type_status"] == "unconfirmed"
        for item in report["introduction"]["evidence_list"]
    )
    assert report["inspection"]["primary_software"]["confirmation_status"] == "unconfirmed"
    assert report["inspection"]["primary_software"]["provenance"][0] == {
        "source_type": "report",
        "source_file": "0_1.json",
        "json_path": "Rows",
        "adapter": "pinghang-mobile-multipath-v1",
        "confidence": 1.0,
    }
    assert report["attachments"]["photo_ids"] == []
    assert "报告/data/navigation_data.js" in result["parsed_files"]
    assert "3点10分" not in report["introduction"]["inspection_time_range"]


def test_pinghang_payload_decoder_rejects_executable_suffix():
    with pytest.raises(PinghangPayloadError):
        parse_pinghang_payload(
            ";static.report.records.data_4_1 = {\"Data\": []};alert('SYNTHETIC');",
            expected_index="4",
            expected_page=1,
        )

    with pytest.raises(PinghangPayloadError, match="PINGHANG_PAYLOAD_ASSIGNMENT_INVALID"):
        parse_pinghang_payload(
            ";static.other.records.data_4_1 = {\"Data\": []};",
            expected_index="4",
            expected_page=1,
        )


def test_pinghang_payload_decoder_accepts_bom_nul_and_trailing_commas():
    payload = parse_pinghang_payload(
        '\ufeff;\x00static.report.records.data_9_1 = {"Info":{"type":"Table",},'
        '"Data":[{"value":"SYNTHETIC,}"},],};\x00',
        expected_index="9",
        expected_page=1,
    )

    assert payload["Data"][0]["value"] == "SYNTHETIC,}"


def test_pinghang_payload_decoder_rejects_size_and_depth_limits():
    with pytest.raises(PinghangPayloadError, match="PINGHANG_PAYLOAD_SIZE_INVALID"):
        parse_pinghang_payload(
            ";static.report.records.data_4_1 = {\"value\":\""
            + ("S" * (2 * 1024 * 1024))
            + "\"};",
            expected_index="4",
            expected_page=1,
        )
    nested = "[]"
    for _ in range(70):
        nested = "[" + nested + "]"
    with pytest.raises(PinghangPayloadError, match="PINGHANG_PAYLOAD_STRUCTURE_INVALID"):
        parse_pinghang_payload(
            f";static.report.records.data_4_1 = {{\"value\":{nested}}};",
            expected_index="4",
            expected_page=1,
        )


@pytest.mark.parametrize("expression", [
    '{"Data": function(){return [];}}',
    '{"Data": new Array()}',
])
def test_pinghang_payload_decoder_rejects_expressions(expression):
    with pytest.raises(PinghangPayloadError):
        parse_pinghang_payload(
            f";static.report.records.data_4_1 = {expression};",
            expected_index="4",
            expected_page=1,
        )


def test_pinghang_duplicate_device_data_index_fails_closed(tmp_path):
    source = _write_pinghang_fixture(tmp_path, duplicate_device_node=True)

    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
        detect_report_adapter(source)


def test_pinghang_duplicate_evidence_number_and_conflicting_case_fail_closed(tmp_path):
    duplicate = _write_pinghang_fixture(tmp_path / "SYNTHETIC-DUPLICATE")
    device_path = duplicate / "报告" / "data" / "ViewData" / "4_1.json"
    device_path.write_text(
        device_path.read_text(encoding="utf-8").replace(
            "SYNTHETIC-EVIDENCE-10", "SYNTHETIC-EVIDENCE-20",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ReportAdapterDetectionError) as duplicate_error:
        detect_report_adapter(duplicate)
    assert str(duplicate_error.value) == "REPORT_ADAPTER_STRUCTURE_INVALID"
    assert str(duplicate) not in str(duplicate_error.value)

    conflict = _write_pinghang_fixture(
        tmp_path / "SYNTHETIC-CONFLICT", duplicate_case_node=True,
    )
    extra_case = conflict / "报告" / "data" / "ViewData" / "13_1.json"
    extra_case.write_text(_jsonp(13, _table([
        ("案件名称", "SYNTHETIC-冲突案件"),
        ("案件编号", "SYNTHETIC-CONFLICT-001"),
    ])), encoding="utf-8")
    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
        detect_report_adapter(conflict)


def test_pinghang_path_like_data_index_fails_closed(tmp_path):
    traversal = _write_pinghang_fixture(tmp_path / "SYNTHETIC-TRAVERSAL")
    navigation = traversal / "报告" / "data" / "navigation_data.js"
    navigation.write_text(
        navigation.read_text(encoding="utf-8").replace(
            "dataIndex:'7'", "dataIndex:'../7'",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
        detect_report_adapter(traversal)



def test_pinghang_large_viewdata_uses_only_navigation_selected_core_pages(tmp_path):
    source = _write_pinghang_fixture(tmp_path / "SYNTHETIC-LARGE")
    view_data = source / "报告" / "data" / "ViewData"
    for index in range(1000, 2043):
        (view_data / f"{index}_1.json").write_text(
            _jsonp(index, {"Info": {"type": "Chat"}, "Rows": []}),
            encoding="utf-8",
        )
    (view_data / "2043_1.json").write_text(
        ";static.report.records.data_2043_1 = function(){return 'SYNTHETIC';};",
        encoding="utf-8",
    )
    (view_data / "2044_1.json").write_bytes(b"\xff\xfeSYNTHETIC")

    snapshot = build_report_parse_input_snapshot(str(source))

    assert snapshot.report_format == ReportFormat.PINGHANG
    assert {item.relative_path for item in snapshot.dependencies} == {
        "SYNTHETIC-平航手机多路取证报告.html",
        "报告/data/navigation_data.js",
        "报告/data/ViewData/0_1.json",
        "报告/data/ViewData/11_1.json",
        "报告/data/ViewData/7_1.json",
        "报告/data/ViewData/4_1.json",
    }


def test_pinghang_selected_core_page_still_fails_closed(tmp_path):
    source = _write_pinghang_fixture(tmp_path / "SYNTHETIC-INVALID-CORE")
    case_page = source / "报告" / "data" / "ViewData" / "11_1.json"
    case_page.write_text(
        ";static.report.records.data_11_1 = function(){return 'SYNTHETIC';};",
        encoding="utf-8",
    )

    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
        detect_report_adapter(source)


def test_report_adapter_registry_rejects_unmatched_directory(tmp_path):
    with pytest.raises(ReportAdapterDetectionError) as error:
        detect_report_adapter(tmp_path)

    assert str(error.value) == "REPORT_ADAPTER_NOT_FOUND"
    assert str(tmp_path) not in str(error.value)


def test_pinghang_and_existing_format_collision_fails_closed(tmp_path):
    source = _write_pinghang_fixture(tmp_path)
    data = source / "data"
    data.mkdir()
    (data / "data_case_info.json").write_text(
        json.dumps({"contents": []}), encoding="utf-8",
    )
    (data / "data_device_lists.json").write_text(
        json.dumps({"contents": [{"c3": "SYNTHETIC-TIME"}]}), encoding="utf-8",
    )
    (data / "data_report_info.json").write_text(
        json.dumps({"contents": []}), encoding="utf-8",
    )

    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_AMBIGUOUS"):
        detect_report_adapter(source)


def test_source_registration_records_pinghang_adapter_metadata(tmp_path):
    source = _write_pinghang_fixture(tmp_path / "SYNTHETIC-REPORT")
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"),
        "SYNTHETIC-DEPLOYMENT",
    )
    service = SourceRecordService(
        database,
        ArchiveAuthorizationService(str(tmp_path / "SYNTHETIC-OUTPUT")),
    )

    descriptor = service.register_report_directory(str(source))

    assert descriptor["metadata"]["adapter_id"] == "pinghang-mobile-multipath-v1"
    assert descriptor["metadata"]["adapter_version"] == "1.1.0"
    assert len(descriptor["metadata"]["adapter_structure_fingerprint"]) == 64
    assert str(source) not in json.dumps(descriptor, ensure_ascii=False)


def test_pinghang_source_enters_existing_review_draft(tmp_path):
    source = _write_pinghang_fixture(tmp_path / "SYNTHETIC-REPORT")
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DRAFT-DEPLOYMENT"),
        "SYNTHETIC-DRAFT-DEPLOYMENT",
    )
    source_service = SourceRecordService(
        database,
        ArchiveAuthorizationService(str(tmp_path / "SYNTHETIC-OUTPUT")),
    )
    descriptor = source_service.register_report_directory(str(source))
    cases = CaseDraftService(
        database,
        source_service=source_service,
        environment_service=_PassthroughEnvironment(),
    )
    identifiers = cases.submit(descriptor)

    cases.run_parse_task(**identifiers)

    detail = CaseLifecycleService(database).detail(identifiers["case_id"])
    available = source_service.revalidate(identifiers["source_id"])
    assert detail["shell"]["lifecycle"] == "review_ready"
    assert detail["draft"]["report"]["attachments"]["photo_ids"] == []
    assert available["access_status"] == "available"
    assert available["metadata"]["adapter_id"] == "pinghang-mobile-multipath-v1"
