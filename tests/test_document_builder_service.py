"""REQ-032/033：附件表格和 Word 生成完整性测试。"""

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.document_builder_service import build_record_document
from app.services.record_generator_service import generate_docx


def _report():
    return {
        "title": "电子数据检查笔录",
        "document_number": "SYN-TEST〔2026〕000000号",
        "introduction": {
            "entrust_unit": "单位",
            "entrust_person": "人员",
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


def test_generate_docx_rejects_empty_output(tmp_path: Path):
    def fake_run(*args):
        if args[0] == "create":
            Path(args[1]).touch()
        return CompletedProcess(args, 0, "", "")

    with patch("app.services.record_generator_service._run_officecli", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="为空"):
            generate_docx(_report(), output_dir=str(tmp_path))
