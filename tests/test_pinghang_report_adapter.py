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
    parse_pinghang_navigation,
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
from app.services.inspection.software_policy_service import (  # noqa: E402
    is_primary_software_confirmed,
)
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
    include_second_device: bool = True,
    include_owner_info: bool = False,
    duplicate_owner_info: bool = False,
    first_device_type: str = "Android 设备",
    second_device_type: str = "Android设备",
    second_device_times: tuple[str, str] = (
        "2026-01-02 02:50:00", "2026-01-02 04:30:00",
    ),
) -> Path:
    view_data = root / "报告" / "data" / "ViewData"
    view_data.mkdir(parents=True)
    (root / "SYNTHETIC-平航手机多路取证报告.html").write_text(
        "<title>平航手机多路取证报告 SYNTHETIC/TEST</title>", encoding="utf-8",
    )
    navigation = [
        {"id": 10, "pid": 0, "name": _nav_name("案件信息"), "dataIndex": "11", "viewType": "Table", "rangeCount": 1},
        {"id": 1, "pid": 32 if include_owner_info else 0, "name": _nav_name("SYNTHETIC-设备-B"), "dataIndex": "7", "viewType": "DeviceInfo", "rangeCount": 1},
    ]
    if include_second_device:
        navigation.append(
            {"id": 2, "pid": 33 if include_owner_info else 0, "name": _nav_name("SYNTHETIC-设备-A"), "dataIndex": "4", "viewType": "DeviceInfo", "rangeCount": 1}
        )
    if include_owner_info:
        navigation.extend([
            {"id": 30, "pid": 0, "name": _nav_name("SYNTHETIC-设备作用域-B"), "dataIndex": "30"},
            {"id": 32, "pid": 30, "name": _nav_name("手机信息"), "dataIndex": "32"},
        ])
        if include_second_device:
            navigation.extend([
                {"id": 31, "pid": 0, "name": _nav_name("SYNTHETIC-设备作用域-A"), "dataIndex": "31"},
                {"id": 33, "pid": 31, "name": _nav_name("手机信息"), "dataIndex": "33"},
            ])
        navigation.append(
            {"id": 20, "pid": 30, "name": _nav_name("机主信息"), "dataIndex": "5", "viewType": "Table", "rangeCount": 1}
        )
        if include_second_device:
            navigation.append(
                {"id": 21, "pid": 31, "name": _nav_name("机主信息"), "dataIndex": "6", "viewType": "Table", "rangeCount": 1}
            )
        if duplicate_owner_info:
            navigation.append(
                {"id": 22, "pid": 30, "name": _nav_name("机主信息"), "dataIndex": "8", "viewType": "Table", "rangeCount": 1}
            )
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
        ("送检人员", "SYNTHETIC-PERSON-A、SYNTHETIC-PERSON-B"),
        ("送检单位", "SYNTHETIC-UNIT"),
    ])), encoding="utf-8")
    (view_data / "0_1.json").write_text(_jsonp(0, _table([
        ("数据取证软件版本", "SYNTHETIC-PH 1.2.3"),
        ("报告导出软件版本", "SYNTHETIC-EXPORT 4.5.6"),
        ("报告完成日期", "2026-01-02 05:06:07"),
    ])), encoding="utf-8")
    (view_data / "7_1.json").write_text(_jsonp(7, _device([
        ("检材名称", "SYNTHETIC-设备-B"),
        ("检材编号", "SYNTHETIC-EVIDENCE-20"),
        ("数据类型", first_device_type),
        ("设备品牌", "SYNTHETIC-BRAND-B"),
        ("设备型号", "SYNTHETIC-MODEL-B"),
        ("IMEI", "111111111111111"),
        ("序列码", "SYNTHETIC-SERIAL-B"),
        ("取证开始时间", "2026-01-02 03:10:00"),
        ("取证结束时间", "2026-01-02 03:20:00"),
    ])), encoding="utf-8")
    if include_second_device:
        (view_data / "4_1.json").write_text(_jsonp(4, _device([
            ("检材名称", "SYNTHETIC-设备-A"),
            ("检材编号", "SYNTHETIC-EVIDENCE-10"),
            ("数据类型", second_device_type),
            ("设备品牌", "SYNTHETIC-BRAND-A"),
            ("设备型号", "SYNTHETIC-MODEL-A"),
            ("IMEI", "222222222222222"),
            ("IMEI2", "333333333333333"),
            ("序列码", "SYNTHETIC-SERIAL-A"),
            ("取证开始时间", second_device_times[0]),
            ("取证结束时间", second_device_times[1]),
        ])), encoding="utf-8")
    if include_owner_info:
        (view_data / "5_1.json").write_text(_jsonp(5, _table([
            ("用户姓名", "SYNTHETIC-HOLDER-B"),
            ("电话号码1", "SYNTHETIC-NOT-A-HOLDER"),
        ])), encoding="utf-8")
        if include_second_device:
            (view_data / "6_1.json").write_text(_jsonp(6, _table([
                ("用户姓名", "SYNTHETIC-HOLDER-A"),
            ])), encoding="utf-8")
        if duplicate_owner_info:
            (view_data / "8_1.json").write_text(_jsonp(8, _table([
                ("用户姓名", "SYNTHETIC-AMBIGUOUS-HOLDER"),
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
    assert snapshot.case_info["submit_person"] == (
        "SYNTHETIC-PERSON-A、SYNTHETIC-PERSON-B"
    )
    assert snapshot.case_info["submit_unit"] == "SYNTHETIC-UNIT"
    assert snapshot.report_info["main_software"] == {
        "name": "平航手机多路分析取证软件",
        "version": "SYNTHETIC-PH 1.2.3",
        "status": "confirmed_by_user",
        "candidates": [],
    }
    assert [row["evidence_number"] for row in snapshot.device_rows] == [
        "SYNTHETIC-EVIDENCE-20", "SYNTHETIC-EVIDENCE-10",
    ]
    assert snapshot.device_base_info["SYNTHETIC-EVIDENCE-10"]["imei2"] == (
        "333333333333333"
    )
    assert any(item.relative_path == "报告/data/navigation_data.js" for item in snapshot.dependencies)


def test_pinghang_owner_info_is_bound_to_its_parent_material(tmp_path):
    from app.services.canonical.pinghang_canonical_service import pinghang_snapshot_to_canonical
    source = _write_pinghang_fixture(tmp_path, include_owner_info=True)

    snapshot = build_report_parse_input_snapshot(str(source))
    canonical = pinghang_snapshot_to_canonical(snapshot)
    assert canonical.materials[0].holder_name == "SYNTHETIC-HOLDER-B"
    assert canonical.materials[0].holder_provenance[0].source_file == "5_1.json"
    assert canonical.materials[0].holder_provenance[0].json_path == "用户姓名"
    assert all(item.provenance[0].source_type == "report" for item in canonical.materials)
    report = parse_report(str(source), str(tmp_path / "output"), compress=False)["report"]

    assert [row["holder_name"] for row in snapshot.device_rows] == [
        "SYNTHETIC-HOLDER-B", "SYNTHETIC-HOLDER-A",
    ]
    assert [item["holder_name"] for item in report["introduction"]["evidence_list"]] == [
        "SYNTHETIC-HOLDER-B", "SYNTHETIC-HOLDER-A",
    ]
    assert any(
        item.relative_path == "报告/data/ViewData/5_1.json"
        for item in snapshot.dependencies
    )


def test_pinghang_ambiguous_owner_info_fails_closed(tmp_path):
    source = _write_pinghang_fixture(
        tmp_path, include_owner_info=True, duplicate_owner_info=True,
    )

    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
        detect_report_adapter(source)


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


def test_parse_report_maps_pinghang_android_device_to_phone(tmp_path):
    source = _write_pinghang_fixture(tmp_path)

    result = parse_report(str(source), str(tmp_path / "output"), compress=False)

    report = result["report"]
    assert report["introduction"]["case_summary"] == "SYNTHETIC-案情摘要"
    assert report["introduction"]["entrust_unit"] == "SYNTHETIC-UNIT"
    assert report["introduction"]["entrust_persons"] == [
        "SYNTHETIC-PERSON-A", "SYNTHETIC-PERSON-B",
    ]
    assert [item["evidence_number"] for item in report["introduction"]["evidence_list"]] == [
        "SYNTHETIC-EVIDENCE-20", "SYNTHETIC-EVIDENCE-10",
    ]
    evidence_list = report["introduction"]["evidence_list"]
    assert all(item["material_type"] == "phone" for item in evidence_list)
    assert all(
        item["material_type_status"] == "confirmed_by_report"
        for item in evidence_list
    )
    assert all(item["material_type_source"] == "report" for item in evidence_list)
    assert all(item["material_type_diagnostic"] is None for item in evidence_list)
    assert "IMEI1：" in report["inspection"]["process_steps"][0]["content"]
    assert "序列号：" not in report["inspection"]["process_steps"][0]["content"]
    primary = report["inspection"]["primary_software"]
    assert primary["name"] == "平航手机多路分析取证软件"
    assert primary["version"] == "SYNTHETIC-PH 1.2.3"
    assert primary["confirmation_status"] == "confirmed_by_user"
    assert primary["provenance"][0] == {
        "source_type": "user",
        "source_file": None,
        "json_path": None,
        "adapter": "pinghang-mobile-multipath-v1",
        "confidence": 1.0,
    }
    assert primary["provenance"][1] == {
        "source_type": "report",
        "source_file": "0_1.json",
        "json_path": "Rows",
        "adapter": "pinghang-mobile-multipath-v1",
        "confidence": 1.0,
    }
    assert report["inspection"]["software_tools"][0]["name"] == (
        "平航手机多路分析取证软件"
    )
    assert report["inspection"]["software_tools"][0]["version"] == (
        "SYNTHETIC-PH 1.2.3"
    )
    assert report["inspection"]["result"]["software_name"] == (
        "平航手机多路分析取证软件"
    )
    assert report["inspection"]["result"]["software_version"] == (
        "SYNTHETIC-PH 1.2.3"
    )
    assert report["inspection"]["process_steps"][3]["content"] == (
        "启动平航手机多路分析取证软件，使用该软件对检材"
        "SYNTHETIC-EVIDENCE-20、SYNTHETIC-EVIDENCE-10进行检查。"
    )
    assert is_primary_software_confirmed(report)
    assert report["attachments"]["photo_ids"] == []
    assert "navigation" in result["parsed_files"]
    assert report["introduction"]["inspection_time_range"] == (
        "2026年1月2日2点50分至2026年1月2日4点30分"
    )
    assert report["inspection"]["hardware_device"] == ""


@pytest.mark.parametrize("reported_type", ["android设备", "Ａｎｄｒｏｉｄ　设备"])
def test_pinghang_android_device_mapping_normalizes_case_width_and_space(
    tmp_path, reported_type,
):
    source = _write_pinghang_fixture(
        tmp_path, include_second_device=False, first_device_type=reported_type,
    )

    material = parse_report(
        str(source), str(tmp_path / "output"), compress=False,
    )["report"]["introduction"]["evidence_list"][0]

    assert material["material_type"] == "phone"
    assert material["material_type_status"] == "confirmed_by_report"
    assert material["material_type_source"] == "report"


def test_pinghang_unknown_device_type_still_requires_confirmation(tmp_path):
    source = _write_pinghang_fixture(
        tmp_path,
        include_second_device=False,
        first_device_type="SYNTHETIC-UNKNOWN-TYPE",
    )

    material = parse_report(
        str(source), str(tmp_path / "output"), compress=False,
    )["report"]["introduction"]["evidence_list"][0]

    assert material["material_type"] == "unconfirmed"
    assert material["material_type_status"] == "unconfirmed"
    assert material["material_type_source"] == "report"
    assert material["material_type_diagnostic"] == (
        "MATERIAL_TYPE_DEVICE_TYPE_UNRECOGNIZED"
    )


def test_single_pinghang_device_uses_its_acquisition_time_range(tmp_path):
    source = _write_pinghang_fixture(
        tmp_path, include_second_device=False,
    )

    report = parse_report(
        str(source), str(tmp_path / "output"), compress=False,
    )["report"]

    assert report["introduction"]["inspection_time_range"] == (
        "2026年1月2日3点10分至2026年1月2日3点20分"
    )


@pytest.mark.parametrize("second_device_times", [
    ("", "2026-01-02 04:30:00"),
    ("SYNTHETIC-NOT-A-TIME", "2026-01-02 04:30:00"),
    ("2026-01-02 05:00:00", "2026-01-02 04:30:00"),
])
def test_pinghang_incomplete_or_invalid_device_time_requires_review(
    tmp_path, second_device_times,
):
    source = _write_pinghang_fixture(
        tmp_path, second_device_times=second_device_times,
    )

    report = parse_report(
        str(source), str(tmp_path / "output"), compress=False,
    )["report"]

    assert report["introduction"]["inspection_time_range"] == ""


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
    assert descriptor["metadata"]["adapter_version"] == "1.6.0"
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

    device = source / "报告/data/ViewData/7_1.json"
    device.write_text(device.read_text(encoding="utf-8").replace(
        "111111111111111", "999999999999999",
    ), encoding="utf-8")
    changed = source_service.revalidate(identifiers["source_id"])
    assert changed["access_status"] != "available"


@pytest.mark.parametrize("body", [
    "{id:1 pid:0}", "{id:1,pid:0}{id:2,pid:0}",
    "{id:1,,pid:0}", ",{id:1,pid:0}",
    "{id:1,pid:0,rangeCount:0}", "{id:1,pid:0,rangeCount:true}",
    "{id:1,pid:0},{id:1,pid:0}",
])
def test_navigation_rejects_invalid_separators_ranges_and_duplicate_ids(body):
    with pytest.raises(PinghangPayloadError):
        parse_pinghang_navigation(f";window.static.report.zNodes = [{body}];")


@pytest.mark.parametrize("body", [
    '{"v":NaN}', '{"v":Infinity}', '{"v":1,"v":2}', '{"v":1e400}', '{"v":-1e400}',
])
def test_payload_rejects_non_json_values_and_duplicate_keys(body):
    with pytest.raises(PinghangPayloadError):
        parse_pinghang_payload(f";static.report.records.data_1_1 = {body};",
                              expected_index="1", expected_page=1)


def test_pinghang_does_not_infer_holder_from_device_fields(tmp_path):
    source = _write_pinghang_fixture(tmp_path, include_second_device=False)
    device = source / "报告/data/ViewData/7_1.json"
    payload = parse_pinghang_payload(device.read_text(encoding="utf-8"),
                                     expected_index="7", expected_page=1)
    payload["Data"].append({"Val1": ["持有人"], "Val2": ["SYNTHETIC-FALLBACK"]})
    device.write_text(_jsonp(7, payload), encoding="utf-8")
    assert build_report_parse_input_snapshot(str(source)).device_rows[0]["holder_name"] == ""


def test_pinghang_public_diagnostics_omit_entry_filename(tmp_path):
    source = _write_pinghang_fixture(tmp_path)
    result = parse_report(str(source), str(tmp_path / "output"), compress=False)
    assert "SYNTHETIC-平航手机多路取证报告.html" not in json.dumps(result, ensure_ascii=False)


def test_pinghang_changed_content_cannot_join_an_older_parse(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app.services.report import report_parser_service as parser

    source = _write_pinghang_fixture(tmp_path)
    entered, release = Event(), Event()
    original = parser._build_parse_result
    def blocked(*args, **kwargs):
        if not entered.is_set():
            entered.set()
            assert release.wait(10)
        return original(*args, **kwargs)
    monkeypatch.setattr(parser, "_build_parse_result", blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(parse_report, str(source), str(tmp_path / "output"), False)
        assert entered.wait(5)
        device = source / "报告/data/ViewData/7_1.json"
        device.write_text(device.read_text(encoding="utf-8").replace(
            "111111111111111", "999999999999999"), encoding="utf-8")
        second = pool.submit(parse_report, str(source), str(tmp_path / "output"), False)
        try:
            current = second.result(timeout=5)
            assert current["report"]["introduction"]["evidence_list"][0]["imei1"] == "999999999999999"
        finally:
            release.set()
        assert first.result()["report"]["introduction"]["evidence_list"][0]["imei1"] == "111111111111111"


def test_pinghang_ancestor_link_is_rejected_before_reading_external_pages(tmp_path, monkeypatch):
    import subprocess
    from app.repository.report import pinghang_report_adapter as adapter

    source = _write_pinghang_fixture(tmp_path / "SYNTHETIC-ROOT")
    link = source / "报告"
    target = tmp_path / "SYNTHETIC-EXTERNAL"
    link.rename(target)
    if os.name == "nt":
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "New-Item -ItemType Junction -Path $env:SYNTHETIC_LINK -Target $env:SYNTHETIC_TARGET | Out-Null"],
                       env={**os.environ, "SYNTHETIC_LINK": str(link), "SYNTHETIC_TARGET": str(target)},
                       check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    def forbidden_read(_path):
        pytest.fail("SYNTHETIC linked report content must not be read")
    monkeypatch.setattr(adapter, "_read_file", forbidden_read)
    try:
        with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
            detect_report_adapter(source)
    finally:
        if os.name == "nt":
            os.rmdir(link)  # 只移除测试 junction，不递归删除目标。
        else:
            link.unlink()


def test_pinghang_parse_and_source_verification_read_only_core_files_once(tmp_path, monkeypatch):
    source = _write_pinghang_fixture(tmp_path / "SYNTHETIC-LIGHTWEIGHT")
    from collections import Counter
    opened = Counter()
    original = Path.open
    def tracked(path, *args, **kwargs):
        if path.is_relative_to(source):
            opened[path.relative_to(source).as_posix()] += 1
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", tracked)
    parse_report(str(source), str(tmp_path / "output"), compress=False)
    assert len(opened) == 6
    assert set(opened.values()) == {1}
    opened.clear()
    match = detect_report_adapter(source)
    from app.services.source.source_record_fingerprint_service import fingerprint
    assert fingerprint(source, report_fingerprint=match.source_fingerprint)
    assert len(opened) == 6
    assert set(opened.values()) == {1}
