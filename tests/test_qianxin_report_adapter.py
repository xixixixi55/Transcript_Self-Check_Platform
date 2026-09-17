"""奇安信网页版报告 v1 的 SYNTHETIC 适配器合同测试。"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.report.qianxin_jsonp_repository import (  # noqa: E402
    QianxinPayloadError,
    parse_qianxin_payload,
)
from app.repository.report.qianxin_report_source_adapter import (  # noqa: E402
    _map_package_profile,
)
from app.repository.report.report_adapter_registry import (  # noqa: E402
    ReportAdapterDetectionError,
    detect_report_adapter,
)
from app.repository.report.report_parse_input_repository import (  # noqa: E402
    build_report_parse_input_snapshot,
)
from app.repository.report.report_parse_input_models import ReportParseInputError  # noqa: E402
from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.services.archive.archive_authorization_service import (  # noqa: E402
    ArchiveAuthorizationService,
)
from app.services.canonical.canonical_report_projector_service import (  # noqa: E402
    project_report_snapshot,
)
from app.services.report.report_parser_service import parse_report  # noqa: E402
from app.services.source.source_record_service import SourceRecordService  # noqa: E402


def _jsonp(stem: str, payload: object) -> str:
    return (
        f";static.report.context.{stem}="
        f"{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};"
    )


def _pairs(values: dict[str, str]) -> list[dict[str, str]]:
    return [{"key": key, "value": value} for key, value in values.items()]


def test_qianxin_explicit_material_type_takes_precedence_over_platform():
    row, base = _map_package_profile({
        "info": _pairs({
            "检材编号": "SYNTHETIC-E-1",
            "检材平台": "Android",
            "检材类型": "平板",
            "提取时间": "2026/06/17 10:30:00 +08:00",
            "解析时间": "2026/06/17 12:00:00 +08:00",
        }),
        "deviceInfo": _pairs({"设备名称": "SYNTHETIC-TABLET", "型号": "T-1"}),
    }, 1)

    assert row["device_type"] == "平板"
    assert base["device_type"] == "平板"


def _write_qianxin_fixture(root: Path) -> Path:
    root.mkdir()
    (root / "SYNTHETIC-取证报告.html").write_text(
        "<html><script>static.report.context;data_report_profile;"
        "data_package_profile;data_navigation;</script></html>",
        encoding="utf-8",
    )
    data = root / "data"
    data.mkdir()
    report = {
        "name": "SYNTHETIC-REPORT",
        "createTime": "2026/06/17 15:14:14 +08:00",
        "source": {
            "name": "SYNTHETIC-盘古石手机取证分析系统",
            "appVersion": "8.5.1-TEST",
            "platformVersion": "SYNTHETIC-WINDOWS",
        },
        "caseInfo": _pairs({
            "案件名称": "SYNTHETIC-案件",
            "案件编号": "SYNTHETIC-CASE-001",
            "送检人": "SYNTHETIC-送检人",
            "送检人单位": "SYNTHETIC-送检单位",
            "创建时间": "2026/06/17 10:00:00 +08:00",
        }),
    }
    navigation = [{
        "id": 1, "pid": 0, "name": "SYNTHETIC-NODE",
        "contextConfig": "config_1", "parserConfig": "data_1_1",
    }]
    (data / "data_report_profile.json").write_text(
        _jsonp("data_report_profile", report), encoding="utf-8",
    )
    (data / "data_navigation.json").write_text(
        _jsonp("data_navigation", navigation), encoding="utf-8",
    )
    packages = {
        10: {
            "info": _pairs({
                "检材编号": "",
                "检材平台": "Android",
                "机主姓名": "SYNTHETIC-持有人-10",
                "提取时间": "2026/06/17 11:00:00 +08:00",
                "解析时间": "2026/06/17 12:30:00 +08:00",
            }),
            "deviceInfo": _pairs({
                "设备名称": "SYNTHETIC-设备-10",
                "型号": "SYNTHETIC-MODEL-10",
                "序列号": "SYNTHETIC-SERIAL-10",
            }),
        },
        2: {
            "info": _pairs({
                "检材编号": "SYNTHETIC-E-002",
                "检材平台": "Android",
                "机主姓名": "SYNTHETIC-持有人-2",
                "IMEI1": "111111111111111",
                "提取时间": "2026/06/17 10:30:00 +08:00",
                "解析时间": "2026/06/17 12:00:00 +08:00",
            }),
            "deviceInfo": _pairs({
                "设备名称": "SYNTHETIC-设备-2",
                "型号": "SYNTHETIC-MODEL-2",
            }),
        },
    }
    for index, payload in packages.items():
        stem = f"data_package_profile_{index}"
        (data / f"{stem}.json").write_text(_jsonp(stem, payload), encoding="utf-8")
    ignored = data / "999"
    ignored.mkdir()
    (ignored / "data_999_1.json").write_text(
        "SYNTHETIC-INVALID-UNSELECTED-CONTENT", encoding="utf-8",
    )
    (root / "files").mkdir()
    (root / "files" / "SYNTHETIC-MEDIA.bin").write_bytes(b"SYNTHETIC")
    return root


def test_qianxin_v1_maps_unified_business_contract_without_scanning_content(tmp_path):
    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-QIANXIN")
    snapshot = build_report_parse_input_snapshot(str(source))
    canonical = project_report_snapshot(snapshot).report
    parsed = parse_report(str(source), str(tmp_path / "output"), compress=False)["report"]

    assert {
        "adapter": snapshot.adapter_id,
        "dependencies": {item.relative_path for item in snapshot.dependencies},
        "case_number": canonical["case_number"],
        "entrust": (
            canonical["introduction"]["entrust_unit"],
            canonical["introduction"]["entrust_persons"],
        ),
        "time_range": canonical["introduction"]["inspection_time_range"],
        "software": canonical["inspection"]["primary_software"],
        "materials": [
            (
                item["id"], item["evidence_number"], item["model"],
                item["material_type"], item["material_type_status"],
            )
            for item in canonical["introduction"]["evidence_list"]
        ],
        "parsed_evidence": [
            (item["id"], item["evidence_number"], item["holder_name"])
            for item in parsed["introduction"]["evidence_list"]
        ],
        "hardware": parsed["inspection"]["hardware_device"],
    } == {
        "adapter": "qianxin-web-report-v1",
        "dependencies": {
            "SYNTHETIC-取证报告.html",
            "data/data_navigation.json",
            "data/data_package_profile_2.json",
            "data/data_package_profile_10.json",
            "data/data_report_profile.json",
        },
        "case_number": "SYNTHETIC-CASE-001",
        "entrust": ("SYNTHETIC-送检单位", ["SYNTHETIC-送检人"]),
        "time_range": "2026年6月17日10点30分至2026年6月17日12点30分",
        "software": {
            "name": "SYNTHETIC-盘古石手机取证分析系统",
            "version": "8.5.1-TEST",
            "display_name": "SYNTHETIC-盘古石手机取证分析系统",
            "confirmation_status": "confirmed_by_report",
            "provenance": [{
                "source_type": "report",
                "source_file": "data_report_profile.json",
                "json_path": "source",
                "adapter": "qianxin-web-report-v1",
                "confidence": 1.0,
            }],
            "candidates": [],
        },
        "materials": [
            (
                "qianxin-package-2", "SYNTHETIC-E-002", "SYNTHETIC-MODEL-2",
                "unconfirmed", "unconfirmed",
            ),
            (
                "qianxin-package-10", "", "SYNTHETIC-MODEL-10",
                "unconfirmed", "unconfirmed",
            ),
        ],
        "parsed_evidence": [
            ("qianxin-package-2", "SYNTHETIC-E-002", "SYNTHETIC-持有人-2"),
            ("qianxin-package-10", "", "SYNTHETIC-持有人-10"),
        ],
        "hardware": "",
    }


def test_qianxin_accepts_bounded_navigation_larger_than_four_mibibytes(tmp_path):
    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-LARGE-NAVIGATION")
    navigation_path = source / "data" / "data_navigation.json"
    navigation = [{
        "id": 1,
        "pid": 0,
        "name": "SYNTHETIC-LARGE-NODE",
        "contextConfig": "SYNTHETIC-CONTEXT-" + "X" * (5 * 1024 * 1024),
        "parserConfig": "SYNTHETIC-PARSER",
    }]
    navigation_path.write_text(
        _jsonp("data_navigation", navigation), encoding="utf-8",
    )

    snapshot = build_report_parse_input_snapshot(str(source))

    assert snapshot.adapter_id == "qianxin-web-report-v1"
    assert len(snapshot.device_rows) == 2
    assert navigation_path.stat().st_size > 4 * 1024 * 1024


def test_qianxin_accepts_entry_html_larger_than_four_mibibytes(tmp_path):
    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-LARGE-ENTRY")
    html_path = source / "SYNTHETIC-取证报告.html"
    html_path.write_text(
        html_path.read_text(encoding="utf-8") + " " * (5 * 1024 * 1024),
        encoding="utf-8",
    )

    snapshot = build_report_parse_input_snapshot(str(source))

    assert snapshot.adapter_id == "qianxin-web-report-v1"
    assert html_path.stat().st_size > 4 * 1024 * 1024


@pytest.mark.parametrize("body", [
    '{"source":{},"source":{}}',
    '{"source":{}};alert("SYNTHETIC")',
    '{"value":NaN}',
])
def test_qianxin_jsonp_rejects_ambiguous_or_executable_payload(body):
    with pytest.raises(QianxinPayloadError):
        parse_qianxin_payload(
            f";static.report.context.data_report_profile={body};",
            expected_stem="data_report_profile",
        )


def test_qianxin_and_existing_format_collision_fails_closed(tmp_path):
    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-COLLISION")
    data = source / "data"
    for name, payload in {
        "data_case_info.json": {"contents": []},
        "data_device_lists.json": {"contents": [{"c3": "SYNTHETIC-TIME"}]},
        "data_report_info.json": {"contents": []},
    }.items():
        (data / name).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_AMBIGUOUS"):
        detect_report_adapter(source)


def test_qianxin_duplicate_numeric_package_index_fails_closed(tmp_path):
    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-DUPLICATE")
    original = source / "data" / "data_package_profile_2.json"
    duplicate = source / "data" / "data_package_profile_02.json"
    duplicate.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ReportAdapterDetectionError, match="REPORT_ADAPTER_STRUCTURE_INVALID"):
        detect_report_adapter(source)


def test_qianxin_source_registration_uses_versioned_adapter_identity(tmp_path):
    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-SOURCE")
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-QIANXIN-DEPLOYMENT"),
        "SYNTHETIC-QIANXIN-DEPLOYMENT",
    )
    service = SourceRecordService(
        database,
        ArchiveAuthorizationService(str(tmp_path / "SYNTHETIC-OUTPUT")),
    )

    descriptor = service.register_report_directory(str(source))

    assert {
        "adapter_id": descriptor["metadata"]["adapter_id"],
        "adapter_version": descriptor["metadata"]["adapter_version"],
        "path_leaked": str(source) in json.dumps(descriptor, ensure_ascii=False),
    } == {
        "adapter_id": "qianxin-web-report-v1",
        "adapter_version": "1.1.0",
        "path_leaked": False,
    }


def test_qianxin_rejects_core_metadata_growth_between_identity_check_and_read(
    tmp_path, monkeypatch,
):
    from app.repository.report import qianxin_report_source_adapter as adapter

    source = _write_qianxin_fixture(tmp_path / "SYNTHETIC-GROWTH")
    target = source / "data" / "data_navigation.json"
    original_read = adapter.read_bounded_dependency
    mutated = False

    def grow_before_bound_read(path, source_root, limit, **kwargs):
        nonlocal mutated
        if path == target and not mutated:
            mutated = True
            path.write_bytes(b"X" * (limit + 1))
        return original_read(path, source_root, limit, **kwargs)

    monkeypatch.setattr(adapter, "read_bounded_dependency", grow_before_bound_read)
    with pytest.raises(ReportParseInputError):
        adapter.QianxinReportSourceAdapter().build_snapshot(source)
