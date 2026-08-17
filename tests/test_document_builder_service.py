"""REQ-032/033：附件表格和 Word 生成完整性测试。"""

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.document_builder_service import build_record_document
from app.services.report_parser_service import parse_report
from app.services.record_generator_service import generate_docx


def _report():
    return {
        "title": "电子数据检查笔录",
        "document_number": "SYN-TEST〔2026〕000000号",
        "introduction": {
            "entrust_unit": "单位",
            "entrust_persons": ["人员"],
            "entrust_time": "",
            "case_summary": "案件",
            "evidence_list": [{
                "device_type": "HUAWEI Pura 70 Pro",
                "model": "HUAWEI Pura 70 Pro",
                "imei1": "123456789012345",
                "imei2": "543210987654321",
                "serial_number": "SYN-SERIAL-00000001",
                "evidence_number": "SYN-JC00000001",
            }],
            "inspection_requirement": "要求",
            "inspection_time_range": "",
            "inspectors": [],
            "inspection_place": "地点",
        },
        "inspection": {
            "method": "方法",
            "hardware_device": "取证塔",
            "software_tools": [{"name": "Python hashlib", "version": "标准库"}],
            "process_steps": [],
            "result": {
                "evidence_number": "SYN-JC00000001",
                "software_name": "工具",
                "software_version": "1",
                "data_summary": "数据",
                "rar_filename": "",
                "md5_hash": "",
                "file_size": "",
            },
        },
        "attachments": {"extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": ""},
    }


def test_build_table_contains_standard_headers_and_empty_row():
    commands = build_record_document(_report())
    table_index = next(i for i, command in enumerate(commands) if command.get("type") == "table")
    table = commands[table_index]
    assert table["props"]["cols"] == "5"
    cell_texts = [
        command["props"]["text"]
        for command in commands[table_index + 1:]
        if command.get("command") == "set" and "/tc[" in command.get("path", "")
    ]
    assert cell_texts[:5] == ["序号", "电子数据", "来源", "提取方式", "文件MD5哈希值"]
    assert len(cell_texts) == 10


def test_build_document_contains_evidence_fields():
    commands = build_record_document(_report())
    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in commands
        if command.get("type") == "paragraph"
    )
    assert "HUAWEI Pura 70 Pro" in paragraph_text
    assert "123456789012345" in paragraph_text
    assert "543210987654321" in paragraph_text
    assert "SYN-SERIAL-00000001" in paragraph_text
    assert "SYN-JC00000001" in paragraph_text


def test_batch_builder_normalizes_entrust_person_separators():
    report = _report()
    report["introduction"]["entrust_persons"] = ["SYNTHETIC-A; SYNTHETIC-B", "SYNTHETIC-C"]

    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in build_record_document(report)
        if command.get("type") == "paragraph"
    )

    assert "（二）委 托 人：SYNTHETIC-A、SYNTHETIC-B、SYNTHETIC-C" in paragraph_text


def test_batch_builder_appends_reviewed_material_type_to_device_name():
    report = _report()
    report["introduction"]["evidence_list"][0].update({
        "device_name": "SYNTHETIC HUAWEI SGU-AL10",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    })

    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in build_record_document(report)
        if command.get("type") == "paragraph"
    )

    assert "SYNTHETIC HUAWEI SGU-AL10手机一部" in paragraph_text
    assert "SYNTHETIC HUAWEI SGU-AL10一部" not in paragraph_text


def test_batch_builder_preserves_unconfirmed_legacy_device_type_priority():
    report = _report()
    report["introduction"]["evidence_list"][0].update({
        "device_type": "SYNTHETIC Android设备",
        "device_name": "SYNTHETIC HUAWEI",
        "model": "SYNTHETIC MODEL",
        "material_type": "unconfirmed",
        "material_type_status": "unconfirmed",
    })

    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in build_record_document(report)
        if command.get("type") == "paragraph"
    )

    assert "SYNTHETIC Android设备一部" in paragraph_text
    assert "SYNTHETIC HUAWEI一部" not in paragraph_text


def test_build_document_marks_unextractable_evidence_without_identifiers():
    report = _report()
    item = report["introduction"]["evidence_list"][0]
    item.update({"device_type": "SYNTHETIC vivo V2141A", "extractable": False})
    report["inspection"]["process_steps"] = [{
        "step_number": 1,
        "content": "将SYNTHETIC vivo V2141A（无法提取）编号为SYN-JC00000001。",
    }]

    commands = build_record_document(report)
    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in commands if command.get("type") == "paragraph"
    )
    assert "1、SYNTHETIC vivo V2141A一部（无法提取）。" in paragraph_text
    assert "将SYNTHETIC vivo V2141A（无法提取）编号为SYN-JC00000001。" in paragraph_text
    assert "123456789012345" not in paragraph_text
    assert "SYN-SERIAL-00000001" not in paragraph_text


def test_build_document_combines_entrust_unit_prefix_without_separator():
    report = _report()
    report["introduction"]["entrust_unit_prefix"] = "SYNTHETIC-公安分局"
    report["introduction"]["entrust_unit"] = "SYNTHETIC-派出所"

    commands = build_record_document(report)
    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in commands
        if command.get("type") == "paragraph"
    )
    assert "（一）委托单位：SYNTHETIC-公安分局SYNTHETIC-派出所" in paragraph_text

    report["introduction"]["entrust_unit_prefix"] = ""
    commands = build_record_document(report)
    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in commands
        if command.get("type") == "paragraph"
    )
    assert "（一）委托单位：SYNTHETIC-派出所" in paragraph_text


def test_build_document_result_names_all_evidence_items():
    report = _report()
    report["introduction"]["evidence_list"].append({
        "device_type": "平板",
        "evidence_number": "SYN-JC00000002",
    })
    commands = build_record_document(report)
    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in commands
        if command.get("type") == "paragraph"
    )
    assert "经对编号为SYN-JC00000001、SYN-JC00000002号检材使用" in paragraph_text


def test_batch_fallback_normalizes_titles_md5_and_extract_source():
    report = _report()
    report["inspection"]["result"]["md5_hash"] = "abcdef0123456789abcdef0123456789"
    report["attachments"]["extract_list"] = {
        "columns": [],
        "rows": [{
            "no": "1", "electronic_data": "SYNTHETIC.rar",
            "source": "SYN-JC00000001内提取", "extraction_method": "SYNTHETIC/TEST",
            "md5_hash": "abcdef0123456789abcdef0123456789",
        }],
    }

    commands = build_record_document(report)
    paragraphs = [
        command for command in commands if command.get("type") == "paragraph"
    ]
    title = next(command for command in paragraphs
                 if command["props"].get("text") == "电子数据检查笔录")
    extract_heading = next(command for command in paragraphs
                           if command["props"].get("text") == "电子数据提取固定清单")
    attachment_summary = next(command for command in paragraphs
                              if "电子数据提取固定清单，共" in command["props"].get("text", ""))
    assert title["props"]["align"] == "center"
    assert title["props"]["bold"] == "true"
    assert extract_heading["props"]["bold"] == "true"
    assert attachment_summary["props"]["text"].startswith("附件：1、")
    assert any(
        "ABCDEF0123456789ABCDEF0123456789" in command["props"].get("text", "")
        for command in paragraphs
    )
    cell_texts = [
        command["props"]["text"] for command in commands
        if command.get("command") == "set" and "/tc[" in command.get("path", "")
    ]
    assert "SYN-JC00000001检材内提取" in cell_texts
    assert "ABCDEF0123456789ABCDEF0123456789" in cell_texts
    header_cells = [
        command for command in commands
        if command.get("command") == "set"
        and command.get("path") in {
            "/body/tbl[1]/tr[1]/tc[2]", "/body/tbl[1]/tr[1]/tc[3]",
        }
    ]
    assert [command["props"]["text"] for command in header_cells] == ["电子数据", "来源"]
    assert all(command["props"]["align"] == "center" for command in header_cells)
    source_cell = next(
        command for command in commands
        if command.get("command") == "set"
        and command.get("path") == "/body/tbl[1]/tr[2]/tc[3]"
    )
    assert source_cell["props"]["align"] == "both"


def test_generate_docx_rejects_empty_output(tmp_path: Path):
    def fake_run(*args):
        if args[0] == "create":
            Path(args[1]).touch()
        return CompletedProcess(args, 0, "", "")

    # 使用不存在的模板路径，强制回退到 batch 模式
    with patch("app.services.record_generator_service._TEMPLATE_PATH", "/nonexistent/template.docx"), \
         patch("app.services.record_generator_service._run_officecli", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="为空"):
            generate_docx(_report(), output_dir=str(tmp_path))


def test_manifest_render_failure_does_not_fallback_to_legacy(tmp_path: Path):
    with patch("app.services.record_generator_service.fill_template", side_effect=ValueError("render failed")), \
         patch("app.services.record_generator_service._generate_via_batch", side_effect=AssertionError("legacy fallback")):
        with pytest.raises(ValueError, match="render failed"):
            generate_docx(_report(), output_dir=str(tmp_path), archive_manifest={})


def test_legacy_parsed_model_feeds_word_builder_and_export(tmp_path: Path):
    data_dir = tmp_path / "legacy" / "data"
    base_dir = data_dir / "JC-OLD" / "Base"
    base_dir.mkdir(parents=True)

    def write(path, payload):
        import json
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    write(data_dir / "data_case_info.json", {"contents": [
        {"tp": "\u6848\u4ef6\u540d\u79f0", "ct": "\u65e7\u683c\u5f0fWord\u6d4b\u8bd5"},
        {"tp": "\u6848\u4ef6\u7f16\u53f7", "ct": "CASE-WORD-SYNTH"},
        {"tp": "\u521b\u5efa\u65f6\u95f4", "ct": "2026-07-13 11:55:19"},
        {"tp": "\u62a5\u544a\u65f6\u95f4", "ct": "2026-07-13 15:43:21"},
    ]})
    write(data_dir / "data_device_lists.json", {"contents": [{
        "c1": "\u65e7\u8bbe\u5907", "c2": "JC-OLD", "c3": "2020-01-01 00:00:00",
    }]})
    write(data_dir / "data_report_info.json", {"contents": [{"value": "\u4ea7\u54c1\u7248\u672c：LegacyTool V3.2.1"}]})
    (data_dir / "data_navigation.json").write_text(
        "; static.mypico.json.navigation = []", encoding="utf-8"
    )
    write(base_dir / "device.json", {
        "\u8bbe\u5907\u540d\u79f0": "Old Phone", "\u8bbe\u5907\u578b\u53f7": "Old-Model",
        "IMEI1": "123456789012345", "\u5e8f\u5217\u53f7": "OLD-SN",
    })

    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        parsed = parse_report(str(data_dir.parent), str(tmp_path / "parsed"), compress=False)["report"]
    commands = build_record_document(parsed)
    paragraph_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in commands if command.get("type") == "paragraph"
    )
    assert parsed["introduction"]["evidence_list"][0]["model"] == "Old-Model"
    assert parsed["case_number"] == "CASE-WORD-SYNTH"
    assert "Old Phone" in paragraph_text
    assert "123456789012345" in paragraph_text

    def fake_fill_template(_report, _template, filepath, _photos):
        Path(filepath).write_bytes(b"synthetic-docx")

    with patch("app.services.record_generator_service.fill_template", side_effect=fake_fill_template):
        output = generate_docx(parsed, output_dir=str(tmp_path / "exports"))
    assert Path(output).is_file()
