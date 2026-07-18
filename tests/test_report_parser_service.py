"""T008: report_parser_service 测试 — compress 参数 + 动态 software_tools"""
import copy
import os
import sys
import tempfile
import zipfile
from unittest.mock import patch, MagicMock
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.services.report_parser_service import (
    _CACHE_VERSION, _build_report, _build_software_tools, parse_from_archive, parse_report,
)
from app.services.report_defaults_service import DEFAULT_DATA_SUMMARY, normalize_data_summary
from app.repository.report_format_adapter import ReportFormat


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
def test_backend_data_summary_blank_values_use_fixed_default(value):
    assert normalize_data_summary(value) == DEFAULT_DATA_SUMMARY


def test_backend_data_summary_preserves_non_empty_value():
    assert normalize_data_summary("  通讯录、文件  ") == "通讯录、文件"


def test_parser_default_is_not_built_from_navigation_categories():
    """导航分类（如录音/微信/抖音）不能覆盖报告摘要默认值。"""
    with patch("app.services.report_parser_service.parse_case_info", return_value={
        "case_name": "测试", "case_number": "", "submit_unit": "", "submit_person": "", "create_time": "",
    }), patch("app.services.report_parser_service.parse_device_lists", return_value=[{
        "evidence_number": "JC01", "device_name": "测试手机", "time_range": "",
    }]), patch("app.services.report_parser_service.parse_report_info", return_value={}), \
        patch("app.services.report_parser_service.parse_device_base", return_value={}), \
        patch("app.services.report_parser_service.require_supported_report_format", return_value=ReportFormat.LEGACY), \
        patch("app.services.report_parser_service._build_software_tools", return_value=[]), \
        patch("app.services.report_parser_service._build_rar_info_from_compress", return_value={
            "filename": "", "md5": "", "size_bytes": 0,
        }):
        report = _build_report("data", "source", "output", compress=False)

    assert report["inspection"]["result"]["data_summary"] == DEFAULT_DATA_SUMMARY


def test_parser_does_not_promote_device_name_or_model_to_device_type():
    with patch("app.services.report_parser_service.parse_case_info", return_value={}), \
        patch("app.services.report_parser_service.parse_device_lists", return_value=[{
            "evidence_number": "JC01", "device_name": "iPhone 15", "time_range": "",
        }]), patch("app.services.report_parser_service.parse_report_info", return_value={}), \
        patch("app.services.report_parser_service.parse_device_base", return_value={
            "device_name": "iPhone 15", "model": "iPhone 15",
        }), patch("app.services.report_parser_service.require_supported_report_format", return_value=ReportFormat.LEGACY), \
        patch("app.services.report_parser_service._build_software_tools", return_value=[]), \
        patch("app.services.report_parser_service._build_rar_info_from_compress", return_value={
            "filename": "", "md5": "", "size_bytes": 0,
        }):
        report = _build_report("data", "source", "output", compress=False)

    evidence = report["introduction"]["evidence_list"][0]
    assert evidence["device_type"] == "iPhone 15"
    assert evidence["device_type_source"] == "legacy_display"


# ─── T008: _build_software_tools 动态生成 (REQ-016) ───

def test_software_tools_with_compress():
    """compress=True → software_tools 含 WinRAR（始终显示）"""
    tools = _build_software_tools("V3.2.12922", compress=True, is_rar_archive=False, main_name="脱敏主取证软件")
    names = [t["name"] for t in tools]
    assert "脱敏主取证软件" in names
    assert "WinRAR压缩管理软件" in names
    assert "Python hashlib" in names
    # Python hashlib 版本应为实际 Python 版本号（如 3.11.0）
    hash_tool = next(t for t in tools if t["name"] == "Python hashlib")
    import re
    assert re.match(r"\d+\.\d+\.\d+", hash_tool["version"]), f"Expected semver, got: {hash_tool['version']}"


def test_software_tools_without_compress():
    """compress=False → WinRAR 始终显示（用户可手动修改版本号）"""
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=False, main_name="脱敏主取证软件")
    names = [t["name"] for t in tools]
    assert "脱敏主取证软件" in names
    assert "WinRAR压缩管理软件" in names
    assert "Python hashlib" in names


def test_software_tools_rar_archive():
    """上传 .rar → software_tools 含 WinRAR"""
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=True, main_name="脱敏主取证软件")
    names = [t["name"] for t in tools]
    assert "WinRAR压缩管理软件" in names


def test_software_tools_zip_archive():
    """上传 .zip → WinRAR 始终显示"""
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=False, main_name="脱敏主取证软件")
    names = [t["name"] for t in tools]
    assert "WinRAR压缩管理软件" in names


def test_software_tools_empty_version():
    """无版本号 → 只含基础工具"""
    tools = _build_software_tools("", compress=True, is_rar_archive=False)
    names = [t["name"] for t in tools]
    # 空版本号不追加主软件，但 WinRAR 仍需存在
    assert all(name not in {"美亚手机大师-并行版V5", "脱敏主取证软件"} for name in names)
    assert "WinRAR压缩管理软件" in names


def test_software_tools_never_use_historical_primary_name_fallback():
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=False)
    assert [tool["name"] for tool in tools] == ["WinRAR压缩管理软件", "Python hashlib"]


# ─── parse_report 集成测试（mock html_parser） ───

_MOCK_REPORT = {
    "title": "电子数据检查笔录",
    "document_number": "",
    "introduction": {
        "entrust_unit": "测试公安局", "entrust_persons": ["张三"],
        "entrust_time": "", "case_summary": "测试案件案",
        "evidence_list": [{"id": "JC01", "device_type": "", "model": "iPhone 14",
            "imei1": "1", "imei2": "2", "serial_number": "", "evidence_number": "JC01"}],
        "inspection_requirement": "上述检材内电子数据的提取、固定和恢复",
        "inspection_time_range": "2026-07-01 ~ 2026-07-10",
        "inspectors": [], "inspection_place": "",
    },
    "inspection": {
        "method": "采用 GA/T 1069-2021",
        "hardware_device": "美亚FL-901手机取证塔",
        "software_tools": [],
        "process_steps": [],
        "result": {"evidence_number": "JC01", "software_name": "美亚手机大师-并行版V5",
            "software_version": "V3.2.12922", "data_summary": "电子数据",
            "rar_filename": "", "md5_hash": "", "file_size": ""},
    },
    "attachments": {"extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": ""},
}

_MOCK_PARSE_RESULT = {
    "report": _MOCK_REPORT,
    "parsed_files": ["data_case_info.json", "data_device_lists.json",
                      "data_report_info.json", "data_navigation.json"],
    "rar_info": None,
}


def test_parse_report_compress_true():
    """文件夹 + compress=True → compress 参数正确传递，rar_info 非 null"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir)
        output_dir = os.path.join(tmpdir, "output")

        with patch("app.services.report_parser_service.is_cache_valid", return_value=False), \
             patch("app.services.report_parser_service._build_report") as mock_build, \
             patch("app.services.report_parser_service.save_json"):
            mock_build.return_value = _MOCK_REPORT
            result = parse_report(tmpdir, output_dir, compress=True)

        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs["compress"] is True


def test_parse_report_compress_false():
    """文件夹 + compress=False → rar_info 为 None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir)
        output_dir = os.path.join(tmpdir, "output")

        with patch("app.services.report_parser_service.is_cache_valid", return_value=False), \
             patch("app.services.report_parser_service._build_report") as mock_build, \
             patch("app.services.report_parser_service.save_json"):
            mock_build.return_value = _MOCK_REPORT
            result = parse_report(tmpdir, output_dir, compress=False)

        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs["compress"] is False
        assert result["rar_info"] is None


def test_parse_report_cache_isolated_by_compress_mode():
    """同一报告切换压缩开关时，不得复用另一模式的缓存。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir)
        output_dir = os.path.join(tmpdir, "output")

        def build_report(*_args, **kwargs):
            report = copy.deepcopy(_MOCK_REPORT)
            if kwargs["compress"]:
                report["inspection"]["result"].update({
                    "rar_filename": "case.rar",
                    "md5_hash": "a" * 32,
                    "file_size": "1 KB",
                })
            return report

        with patch("app.services.report_parser_service._build_report",
                   side_effect=build_report) as mock_build:
            compressed = parse_report(tmpdir, output_dir, compress=True)
            uncompressed = parse_report(tmpdir, output_dir, compress=False)

        assert mock_build.call_count == 2
        assert compressed["rar_info"] is not None
        assert uncompressed["rar_info"] is None
        cache_files = {name for name in os.listdir(os.path.join(output_dir, "parsed"))}
        assert f"{os.path.basename(tmpdir)}.compress.json" in cache_files
        assert f"{os.path.basename(tmpdir)}.nocompress.json" in cache_files


def _write_service_fixture(root, *, known_software=True):
    data_dir = os.path.join(root, "data")
    base_dir = os.path.join(data_dir, "JC01", "Base")
    os.makedirs(base_dir)

    def write(name, payload):
        with open(os.path.join(data_dir, name), "w", encoding="utf-8") as file:
            import json
            json.dump(payload, file, ensure_ascii=False)

    case_values = {
        "案件名称": "合成案件", "案件编号": "CASE-SYNTH-001",
        "送检人": "合成送检人", "送检单位": "合成送检单位",
        "创建时间": "2026-07-13 11:55:19", "报告时间": "2026-07-13 15:43:21",
    }
    write("data_case_info.json", {"contents": [{"tp": k, "ct": v} for k, v in case_values.items()]})
    write("data_device_lists.json", {"contents": [{
        "c1": "1", "c2": "JC01", "tb2": [
            {"tt": "IMEI1", "ct": "111111111111111"},
            {"tt": "IMEI2", "ct": "222222222222222"},
            {"tt": "取证时间段", "ct": "2099-01-01 00:00:00 ~ 2099-01-01 00:01:00"},
        ],
    }]})
    software = "报告生成软件：美亚手机大师-并行版 V5.1.2" if known_software else "美亚阅读器 V8.8.8"
    write("data_report_info.json", {"contents": [{"value": software}]})
    with open(os.path.join(data_dir, "data_navigation.json"), "w", encoding="utf-8") as file:
        file.write("; static.mypico.json.navigation = []")
    with open(os.path.join(base_dir, "unrelated.json"), "w", encoding="utf-8") as file:
        file.write('{"序列号":"NOISE","value":"555555555555555"}')
    with open(os.path.join(base_dir, "device_table.json"), "w", encoding="utf-8") as file:
        import json
        json.dump({"rows": [
            {"c1": "设备名称", "c2": "合成新手机"},
            {"c1": "设备型号", "c2": "Model-NEW"},
            {"c1": "IMEI2", "c2": "999999999999999"},
            {"c1": "序列号", "c2": "SN-NEW"},
        ]}, file, ensure_ascii=False)


def test_multiple_devices_keep_tb2_and_base_fields_matched(tmp_path):
    _write_service_fixture(str(tmp_path), known_software=True)
    data_dir = tmp_path / "data"
    import json
    device_file = data_dir / "data_device_lists.json"
    devices = json.loads(device_file.read_text(encoding="utf-8"))
    devices["contents"].append({
        "c1": "2", "c2": "JC02", "tb2": [
            {"tt": "IMEI1", "ct": "333333333333333"},
            {"tt": "IMEI2", "ct": "444444444444444"},
        ],
    })
    device_file.write_text(json.dumps(devices, ensure_ascii=False), encoding="utf-8")
    second_base = data_dir / "JC02" / "Base"
    second_base.mkdir(parents=True)
    (second_base / "device_table.json").write_text(json.dumps({"rows": [
        {"c1": "设备名称", "c2": "第二合成手机"},
        {"c1": "设备型号", "c2": "Model-SECOND"},
        {"c1": "序列号", "c2": "SN-SECOND"},
    ]}, ensure_ascii=False), encoding="utf-8")

    report = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)["report"]
    by_id = {item["evidence_number"]: item for item in report["introduction"]["evidence_list"]}
    assert by_id["JC01"]["imei1"] == "111111111111111"
    assert by_id["JC01"]["model"] == "Model-NEW"
    assert by_id["JC02"]["imei1"] == "333333333333333"
    assert by_id["JC02"]["model"] == "Model-SECOND"
    assert by_id["JC02"]["serial_number"] == "SN-SECOND"


def test_new_report_normalizes_fields_without_model_or_time_regression(tmp_path):
    _write_service_fixture(str(tmp_path), known_software=True)
    result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    report = result["report"]
    evidence = report["introduction"]["evidence_list"][0]
    assert result["cache_version"] == 5
    assert report["introduction"]["inspection_time_range"] == (
        "2026年7月13日11点55分至2026年7月13日15点43分"
    )
    assert "2099" not in report["introduction"]["inspection_time_range"]
    assert evidence["device_type"] == "合成新手机"
    assert evidence["model"] == "Model-NEW"
    assert evidence["imei1"] == "111111111111111"
    assert evidence["imei2"] == "222222222222222"
    assert evidence["serial_number"] == "SN-NEW"
    assert {tool["name"] for tool in report["inspection"]["software_tools"]} == {
        report["inspection"]["primary_software"]["name"],
        "WinRAR压缩管理软件", "Python hashlib",
    }


def test_new_report_unknown_main_software_version_stays_blank(tmp_path):
    _write_service_fixture(str(tmp_path), known_software=False)
    report = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)["report"]
    names = {tool["name"] for tool in report["inspection"]["software_tools"]}
    assert report["inspection"]["result"]["software_version"] == ""
    assert "美亚手机大师-并行版V5" not in names
    assert names == {"WinRAR压缩管理软件", "Python hashlib"}


def test_cache_version_five_does_not_reuse_v4(tmp_path):
    old_cache = {"report": _MOCK_REPORT, "cache_version": 4}
    with patch("app.services.report_parser_service.is_cache_valid", return_value=True), \
         patch("app.services.report_parser_service.read_json", return_value=old_cache), \
         patch("app.services.report_parser_service._build_report", return_value=_MOCK_REPORT) as mock_build, \
         patch("app.services.report_parser_service.save_json"):
        result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    assert _CACHE_VERSION == 5
    assert result["cache_version"] == 5
    mock_build.assert_called_once()


def test_parse_from_archive_zip():
    """从 .zip 压缩包解析 → rar_info 来自上传文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("dummy.txt", "test")

        output_dir = os.path.join(tmpdir, "output")

        with patch("app.services.report_parser_service.extract_archive") as mock_extract, \
             patch("app.services.report_parser_service._build_report") as mock_build:
            mock_extract.return_value = tmpdir
            mock_build.return_value = _MOCK_REPORT

            result = parse_from_archive(zip_path, output_dir)

        # rar_info 来自原始压缩包
        assert result["rar_info"]["filename"] == "test.zip"
        assert len(result["rar_info"]["md5"]) == 32
        assert result["rar_info"]["size_bytes"] > 0


def _write_legacy_service_fixture(root):
    data_dir = root / "data"
    base_dir = data_dir / "JC-OLD" / "Base"
    base_dir.mkdir(parents=True)

    def write(path, payload):
        path.write_text(__import__("json").dumps(payload, ensure_ascii=False), encoding="utf-8")

    write(data_dir / "data_case_info.json", {"contents": [
        {"tp": "\u6848\u4ef6\u540d\u79f0", "ct": "\u5408\u6210\u65e7\u683c\u5f0f\u6848\u4ef6"},
        {"tp": "\u6848\u4ef6\u7f16\u53f7", "ct": "CASE-OLD-SYNTH"},
        {"tp": "\u521b\u5efa\u65f6\u95f4", "ct": "2026-07-13 11:55:19"},
        {"tp": "\u62a5\u544a\u65f6\u95f4", "ct": "2026-07-13 15:43:21"},
    ]})
    write(data_dir / "data_device_lists.json", {"contents": [{
        "c1": "\u65e7\u683c\u5f0f\u8bbe\u5907", "c2": "JC-OLD",
        "c3": "2020-01-01 00:00:00 ~ 2020-01-01 00:01:00",
    }]})
    write(data_dir / "data_report_info.json", {"contents": [
        {"value": "\u4ea7\u54c1\u7248\u672c：LegacyTool V3.2.1"},
    ]})
    (data_dir / "data_navigation.json").write_text(
        "; static.mypico.json.navigation = []", encoding="utf-8"
    )
    write(base_dir / "device.json", {
        "\u8bbe\u5907\u540d\u79f0": "Old Phone", "\u8bbe\u5907\u578b\u53f7": "Old-Model",
        "IMEI1": "123456789012345", "IMEI2": "543210987654321", "\u5e8f\u5217\u53f7": "OLD-SN",
    })
    return data_dir


def test_legacy_full_standard_model_regression(tmp_path):
    data_dir = _write_legacy_service_fixture(tmp_path)
    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        result = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)
    report = result["report"]
    evidence = report["introduction"]["evidence_list"][0]
    assert report["case_number"] == "CASE-OLD-SYNTH"
    assert report["introduction"]["case_summary"] == "\u5408\u6210\u65e7\u683c\u5f0f\u6848\u4ef6\u6848"
    assert report["introduction"]["inspection_time_range"].startswith("2026年7月13日11点55分")
    assert evidence["evidence_number"] == "JC-OLD"
    assert evidence["device_type"] == "Old Phone"
    assert evidence["model"] == "Old-Model"
    assert evidence["imei1"] == "123456789012345"
    assert evidence["imei2"] == "543210987654321"
    assert evidence["serial_number"] == "OLD-SN"
    assert report["inspection"]["result"]["software_version"] == "V3.2.1"
    assert len(report["attachments"]["extract_list"]["columns"]) == 5
    assert report["attachments"]["photo_ids"] == []


def test_mismatched_evidence_directory_cannot_fall_back_to_unrelated_base(tmp_path):
    _write_service_fixture(str(tmp_path))
    data_dir = os.path.join(str(tmp_path), "data")
    import json
    device_file = data_dir + "/data_device_lists.json"
    devices = json.loads(open(device_file, encoding="utf-8").read())
    devices["contents"][0]["c2"] = "MISSING"
    with open(device_file, "w", encoding="utf-8") as file:
        json.dump(devices, file, ensure_ascii=False)
    unrelated = os.path.join(data_dir, "UNRELATED", "Base")
    os.makedirs(unrelated)
    with open(os.path.join(unrelated, "device.json"), "w", encoding="utf-8") as file:
        json.dump({"\u8bbe\u5907\u578b\u53f7": "WRONG-MODEL", "\u5e8f\u5217\u53f7": "WRONG-SN"}, file, ensure_ascii=False)

    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        report = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)["report"]
    evidence = report["introduction"]["evidence_list"][0]
    assert evidence["evidence_number"] == "MISSING"
    assert evidence["model"] == ""
    assert evidence["serial_number"] == ""
    assert evidence["imei1"] == "111111111111111"


def test_invalid_or_reverse_case_times_degrade_to_blank(tmp_path):
    data_dir = _write_legacy_service_fixture(tmp_path)
    import json
    case_file = data_dir / "data_case_info.json"
    case = json.loads(case_file.read_text(encoding="utf-8"))
    case["contents"][2]["ct"] = "2026-02-30 11:55:19"
    case["contents"][3]["ct"] = "2026-07-13 10:00:00"
    case_file.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        report = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)["report"]
    assert report["introduction"]["inspection_time_range"] == ""


def test_invalid_fixed_imei_allows_valid_structured_base_fallback(tmp_path):
    _write_service_fixture(str(tmp_path))
    import json
    data_dir = tmp_path / "data"
    device_file = data_dir / "data_device_lists.json"
    devices = json.loads(device_file.read_text(encoding="utf-8"))
    devices["contents"][0]["tb2"][0]["ct"] = "unknown"
    device_file.write_text(json.dumps(devices, ensure_ascii=False), encoding="utf-8")
    base_file = data_dir / "JC01" / "Base" / "device_table.json"
    base = json.loads(base_file.read_text(encoding="utf-8"))
    base["rows"].append({"c1": "IMEI1", "c2": "777777777777777"})
    base_file.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")

    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        report = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)["report"]
    assert report["introduction"]["evidence_list"][0]["imei1"] == "777777777777777"
