import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.report_format_adapter import extract_main_software_candidate
from app.services.export_gate_service import ExportGateInput, evaluate_export_gate
from app.services.software_policy_service import (
    is_primary_software_confirmed,
    normalize_primary_software_projection,
    normalize_runtime_software_tool_projection,
)


def test_report_candidate_requires_one_semantic_name_version_pair():
    candidate = extract_main_software_candidate([
        {"value": "报告生成软件：合成取证工具 V1.2.3"},
    ])
    assert candidate["status"] == "confirmed_by_report"
    assert candidate["name"] == "合成取证工具"
    assert candidate["version"] == "V1.2.3"


def test_bracketed_main_product_ignores_submodule_name_and_version():
    candidate = extract_main_software_candidate([{
        "value": (
            "该报告采用【手机大师-并行版V5（FL-901 手机取证塔V5） "
            "V3.2.12922 子模块MYReader V3.2.24111】生成。"
        ),
    }])
    assert candidate == {
        "name": "手机大师-并行版V5",
        "version": "V3.2.12922",
        "status": "confirmed_by_report",
        "candidates": [{
            "name": "手机大师-并行版V5",
            "version": "V3.2.12922",
        }],
    }


def test_main_software_name_preserves_identity_and_removes_generic_hardware_suffix():
    candidate = extract_main_software_candidate([{
        "value": "该报告采用【手机大师NEXT（FL-901 手机取证塔V5） V1.1.22111】生成。",
    }])
    assert candidate["name"] == "手机大师NEXT"
    assert candidate["version"] == "V1.1.22111"

    generic = extract_main_software_candidate([{
        "value": "该报告采用【合成取证软件（SYNTHETIC-X 取证工作站） V2.3.4】生成。",
    }])
    assert generic["name"] == "合成取证软件"
    assert generic["version"] == "V2.3.4"


@pytest.mark.parametrize("marker", ["子模块", "插件", "组件"])
def test_bracketed_main_product_supports_named_secondary_variants(marker):
    candidate = extract_main_software_candidate([{
        "value": f"该报告采用[合成主工具 Pro V2.4.6 {marker}Reader V9.8.7]生成。",
    }])
    assert (candidate["name"], candidate["version"]) == ("合成主工具 Pro", "V2.4.6")


def test_conflicting_report_candidates_stay_unconfirmed():
    candidate = extract_main_software_candidate([
        {"value": "主取证软件：工具甲 V1.0.0"},
        {"value": "主取证软件：工具乙 V2.0.0"},
    ])
    assert candidate["status"] == "unconfirmed"
    assert len(candidate["candidates"]) == 2


def test_repeated_identical_report_candidate_is_confirmed():
    candidate = extract_main_software_candidate([
        {"value": "主取证软件：工具甲 V1.0.0"},
        {"value": "报告生成软件：工具甲 V1.0.0"},
    ])
    assert candidate["status"] == "confirmed_by_report"
    assert candidate["candidates"] == [{"name": "工具甲", "version": "V1.0.0"}]


def test_bracketed_secondary_candidate_is_not_treated_as_confirmed():
    candidate = extract_main_software_candidate([
        {"value": "主取证软件：工具甲 V1.0.0"},
        {"value": "报告生成软件：工具甲 V1.0.0（升级工具）"},
    ])
    assert candidate["status"] == "unconfirmed"


def test_runtime_tools_do_not_replace_report_primary_software():
    report = {
        "inspection": {
            "primary_software": {
                "name": "报告工具",
                "version": "V2.0.0",
                "confirmation_status": "confirmed_by_report",
                "provenance": [],
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.11.0"},
            ],
            "result": {"software_name": "错误环境工具", "software_version": "9.9"},
        }
    }
    normalized = normalize_primary_software_projection(report)
    assert normalized["inspection"]["result"] == {
        "software_name": "报告工具", "software_version": "V2.0.0"
    }
    assert normalized["inspection"]["software_tools"][0] == {
        "name": "报告工具", "version": "V2.0.0"
    }
    assert is_primary_software_confirmed(normalized)


def test_incomplete_primary_software_does_not_project_a_fake_tool():
    report = {
        "inspection": {
            "primary_software": {
                "name": "",
                "version": "V2.0.0",
                "confirmation_status": "unconfirmed",
                "provenance": [],
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.11.0"},
            ],
            "result": {"software_name": "", "software_version": "V2.0.0"},
        }
    }
    normalized = normalize_primary_software_projection(report)
    assert [tool["name"] for tool in normalized["inspection"]["software_tools"]] == [
        "WinRAR压缩管理软件", "HashMyFiles",
    ]
    assert normalized["inspection"]["software_tools"][1]["version"] == "2.51"
    assert not is_primary_software_confirmed(normalized)


def test_legacy_hashlib_runtime_tool_is_projected_as_hashmyfiles():
    report = {
        "inspection": {
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.11.0"},
            ],
            "result": {"software_name": "", "software_version": ""},
        }
    }
    normalized = normalize_primary_software_projection(report)
    assert normalized["inspection"]["software_tools"] == [
        {"name": "WinRAR压缩管理软件", "version": "6.24"},
        {"name": "HashMyFiles", "version": "2.51"},
    ]


def test_hashmyfiles_runtime_tool_is_preserved_by_projection():
    report = {
        "inspection": {
            "primary_software": {
                "name": "", "version": "V2.0.0",
                "confirmation_status": "unconfirmed", "provenance": [],
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "HashMyFiles", "version": "2.51"},
            ],
            "result": {"software_name": "", "software_version": "V2.0.0"},
        }
    }
    normalized = normalize_primary_software_projection(report)
    assert [tool["name"] for tool in normalized["inspection"]["software_tools"]] == [
        "WinRAR压缩管理软件", "HashMyFiles",
    ]


def test_runtime_detail_projection_preserves_hashmyfiles_metadata():
    report = {"inspection": {"software_tools": [{
        "category": "hashmyfiles", "name": "HashMyFiles", "version": "2.51",
        "display_name": "HashMyFiles 2.51", "confirmation_status": "confirmed",
    }]}}
    normalized = normalize_runtime_software_tool_projection(report)
    assert normalized["inspection"]["software_tools"] == report["inspection"]["software_tools"]


def test_runtime_detail_projection_migrates_legacy_identity_without_losing_metadata():
    legacy_tool = {
        "category": "python_hashlib", "name": "Python hashlib", "version": "3.11.0",
        "display_name": "Python hashlib 3.11.0", "confirmation_status": "confirmed",
        "provenance": [{"source_type": "runtime"}], "extension": "SYNTHETIC/TEST",
    }
    report = {"inspection": {"software_tools": [legacy_tool]}}
    normalized = normalize_runtime_software_tool_projection(report)
    assert normalized["inspection"]["software_tools"] == [{
        **legacy_tool,
        "category": "hashmyfiles", "name": "HashMyFiles", "version": "2.51",
        "display_name": "HashMyFiles 2.51",
    }]
    assert report["inspection"]["software_tools"] == [legacy_tool]


def test_unconfirmed_primary_software_is_an_export_blocker():
    result = evaluate_export_gate(
        ExportGateInput(primary_software_confirmed=False),
    )
    assert not result.allowed
    assert result.blockers[0].code.value == "PRIMARY_SOFTWARE_UNCONFIRMED"
    assert result.blockers[0].field == "inspection.primary_software"


def test_legacy_confirmed_alias_does_not_bypass_primary_gate():
    report = {
        "inspection": {
            "primary_software": {
                "name": "报告工具",
                "version": "V1.0.0",
                "confirmation_status": "confirmed",
            }
        }
    }
    assert not is_primary_software_confirmed(report)
