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
    parse_report, parse_from_archive, _build_software_tools,
)


# ─── T008: _build_software_tools 动态生成 (REQ-016) ───

def test_software_tools_with_compress():
    """compress=True → software_tools 含 WinRAR"""
    tools = _build_software_tools("V3.2.12922", compress=True, is_rar_archive=False)
    names = [t["name"] for t in tools]
    assert "美亚手机大师-并行版V5" in names
    assert "WinRAR压缩管理软件" in names
    assert "Python hashlib" in names


def test_software_tools_without_compress():
    """compress=False + 非 rar → software_tools 不含 WinRAR"""
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=False)
    names = [t["name"] for t in tools]
    assert "美亚手机大师-并行版V5" in names
    assert "WinRAR压缩管理软件" not in names
    assert "Python hashlib" in names


def test_software_tools_rar_archive():
    """上传 .rar → software_tools 含 WinRAR"""
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=True)
    names = [t["name"] for t in tools]
    assert "WinRAR压缩管理软件" in names


def test_software_tools_zip_archive():
    """上传 .zip → software_tools 不含 WinRAR（用 zipfile 解压）"""
    tools = _build_software_tools("V3.2.12922", compress=False, is_rar_archive=False)
    names = [t["name"] for t in tools]
    assert "WinRAR压缩管理软件" not in names


def test_software_tools_empty_version():
    """无版本号 → 只含基础工具"""
    tools = _build_software_tools("", compress=True, is_rar_archive=False)
    names = [t["name"] for t in tools]
    # 空版本号不追加美亚大师，但 WinRAR 仍需存在
    assert "美亚手机大师-并行版V5" not in names
    assert "WinRAR压缩管理软件" in names


# ─── parse_report 集成测试（mock html_parser） ───

_MOCK_REPORT = {
    "title": "电子数据检查笔录",
    "document_number": "",
    "introduction": {
        "entrust_unit": "测试公安局", "entrust_person": "张三",
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
