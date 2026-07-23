"""模板填充回归测试：VML、默认数据摘要和附件分页。"""

import os
import struct
import sys
import zipfile
import zlib
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.template_filler_service import _flatten_report, fill_template
from app.services.attachment2_image_service import (
    ATTACHMENT2_SLOT_HEIGHT_EMU,
    ATTACHMENT2_SLOT_WIDTH_EMU,
)


_ROOT = Path(__file__).parents[1]
_TEMPLATE = _ROOT / "word_templates" / "template.docx"
_DEFAULT_SUMMARY = "即时通讯、手机信息"


def _report(data_summary_marker=...):
    result = {
        "evidence_number": "JC01",
        "software_name": "测试工具",
        "software_version": "1.0",
        "rar_filename": "case.rar",
        "md5_hash": "a" * 32,
        "file_size": "123",
    }
    if data_summary_marker is not ...:
        result["data_summary"] = data_summary_marker
    return {
        "title": "电子数据检查笔录",
        "document_number": "SYN-TEST〔2026〕000号",
        "introduction": {
            "entrust_unit": "测试单位",
            "entrust_persons": ["测试人员"],
            "entrust_time": "2026年7月16日",
            "case_summary": "测试案件",
            "evidence_list": [{"evidence_number": "JC01", "device_type": "测试手机"}],
            "inspection_requirement": "测试要求",
            "inspection_time_range": "2026年7月16日",
            "inspectors": [],
            "inspection_place": "测试鉴定中心",
        },
        "inspection": {
            "method": "测试方法",
            "hardware_device": "测试设备",
            "software_tools": [],
            "process_steps": [],
            "result": result,
        },
        "attachments": {
            "extract_list": {"rows": []},
            "photo_ids": [],
            "disc_number": "TEST-DISC",
            "burning_date": "2026年7月16日",
        },
    }


def _manifest(count=3):
    return {
        "manifest_id": "trusted-synthetic-manifest",
        "validation_status": "validated",
        "volume_size_bytes": 4_000_000_000,
        "parts": [
            {
                "part_id": f"part-{index}",
                "part_number": index,
                "filename": f"synthetic.part{index}.rar",
                "size_bytes": index * 100,
                "md5": f"{index:032x}",
                "disc_number": f"GP20260706-{index:02d}",
                "disc_date": "2026-07-06",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            }
            for index in range(1, count + 1)
        ],
    }


@pytest.mark.parametrize("value", [None, "", "   "])
def test_data_summary_blank_values_use_fixed_default(value):
    report = _report(value)
    assert _flatten_report(report)["data_summary"] == _DEFAULT_SUMMARY


def test_data_summary_missing_uses_fixed_default():
    assert _flatten_report(_report())["data_summary"] == _DEFAULT_SUMMARY


def test_data_summary_normal_value_is_preserved():
    assert _flatten_report(_report("  通讯录  "))["data_summary"] == "通讯录"


def test_flatten_report_names_all_evidence_items_in_result():
    report = _report()
    report["introduction"]["evidence_list"].append({
        "evidence_number": "JC02",
        "device_type": "测试平板",
    })
    assert _flatten_report(report)["evidence_number"] == "JC01、JC02"


def test_fill_template_combines_all_evidence_numbers_in_result_sentence(tmp_path):
    report = _report()
    report["introduction"]["evidence_list"].append({
        "evidence_number": "JC02",
        "device_type": "测试平板",
    })
    output = tmp_path / "combined-result.docx"
    fill_template(report, str(_TEMPLATE), str(output))

    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert "经对编号为JC01、JC02号检材使用测试工具" in document_xml
    assert "；经对编号为JC02号检材" not in document_xml


def test_evidence_renderer_projects_identifiers_by_confirmed_material_type(tmp_path):
    report = _report()
    report["introduction"]["evidence_list"] = [
        {
            "id": "phone", "evidence_number": "JC-PHONE", "device_type": "手机",
            "material_type": "phone", "material_type_status": "confirmed_by_user",
            "material_type_source": "user", "imei1": "111111111111111",
            "serial_number": "PHONE-SERIAL-MUST-NOT-RENDER",
        },
        {
            "id": "tablet", "evidence_number": "JC-TABLET", "device_type": "平板",
            "material_type": "tablet", "material_type_status": "confirmed_by_user",
            "material_type_source": "user", "imei1": "222222222222222",
            "serial_number": "TABLET-SERIAL-MUST-RENDER",
        },
    ]
    output = tmp_path / "material-identifiers.docx"
    fill_template(report, str(_TEMPLATE), str(output))

    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert "111111111111111" in document_xml
    assert "PHONE-SERIAL-MUST-NOT-RENDER" not in document_xml
    assert "TABLET-SERIAL-MUST-RENDER" in document_xml
    assert "222222222222222" not in document_xml


def test_manifest_result_uses_every_part_filename_hash_size_and_disc(tmp_path):
    report = _report()
    report["introduction"]["evidence_list"] = [
        {"evidence_number": "JC-A", "device_type": "测试手机"},
        {"evidence_number": "JC-B", "device_type": "测试手机"},
        {"evidence_number": "JC-C", "device_type": "测试手机"},
    ]
    report["inspection"]["primary_software"] = {
        "name": "已确认取证软件",
        "version": "3.2",
        "confirmation_status": "confirmed_by_report",
    }
    report["inspection"]["software_tools"] = [
        {"name": "WinRAR压缩管理软件", "version": "6.24"},
        {"name": "Python hashlib", "version": "3.12"},
    ]
    output = tmp_path / "manifest-result.docx"
    fill_template(report, str(_TEMPLATE), str(output), [], _manifest())

    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert "经对编号为JC-A、JC-B、JC-C号检材使用已确认取证软件（版本号为3.2）" in document_xml
    for index in range(1, 4):
        assert f"synthetic.part{index}.rar" in document_xml
        assert f"文件大小为“{index * 100}”字节" in document_xml
        assert f"GP20260706-{index:02d}" in document_xml
    assert "case.rar" not in document_xml
    assert "client-value.rar" not in document_xml


def test_fill_template_preserves_vml_and_renders_default_and_pagination(tmp_path):
    output = tmp_path / "filled.docx"
    fill_template(_report(), str(_TEMPLATE), str(output))

    with zipfile.ZipFile(output) as package:
        assert package.testzip() is None
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert document_xml.count("<w:pict") >= 2
    assert document_xml.count("<v:textbox") == 2
    assert document_xml.count("<w:txbxContent") == 2
    assert "检验单位：测试鉴定中心" in document_xml
    assert _DEFAULT_SUMMARY in document_xml
    assert "<w:pageBreakBefore" not in document_xml
    assert document_xml.count('w:type="page"') == 4


def test_generated_docx_removes_comments_and_nonessential_metadata(tmp_path):
    output = tmp_path / "sanitized.docx"
    fill_template(_report(), str(_TEMPLATE), str(output))

    with zipfile.ZipFile(output) as package:
        names = set(package.namelist())
        assert "word/comments.xml" not in names
        assert "word/commentsExtended.xml" not in names
        assert "word/people.xml" not in names
        assert "docProps/custom.xml" not in names
        xml_parts = {
            name: package.read(name).decode("utf-8")
            for name in names
            if name.endswith(".xml") or name.endswith(".rels")
        }
        document_xml = xml_parts["word/document.xml"]
        settings_xml = xml_parts["word/settings.xml"]
        core = ET.fromstring(xml_parts["docProps/core.xml"])
        content_types = xml_parts["[Content_Types].xml"]
        package_rels = xml_parts["_rels/.rels"]

    assert "commentRangeStart" not in document_xml
    assert "commentRangeEnd" not in document_xml
    assert "commentReference" not in document_xml
    assert "comments.xml" not in "".join(xml_parts.values())
    assert "commentsExtended.xml" not in "".join(xml_parts.values())
    assert "people.xml" not in "".join(xml_parts.values())
    assert "docVars" not in settings_xml
    assert "custom.xml" not in content_types
    assert "custom.xml" not in package_rels
    tracked_change_names = {"ins", "del", "moveFrom", "moveTo"}
    for xml in xml_parts.values():
        root = ET.fromstring(xml)
        assert not any(
            node.tag.rsplit("}", 1)[-1] in tracked_change_names
            for node in root.iter()
        )

    core_values = {
        node.tag.rsplit("}", 1)[-1]: node.text or ""
        for node in core
    }
    assert core_values["creator"] == "文枢"
    assert core_values["lastModifiedBy"] == "文枢"
    assert core_values["revision"] == "1"
    assert "lastPrinted" not in core_values
    assert "subject" not in core_values
    assert "keywords" not in core_values

    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    for name, xml in xml_parts.items():
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        root = ET.fromstring(xml)
        for run in root.findall(".//{%s}r" % w_ns):
            color = run.find("./{%s}rPr/{%s}color" % (w_ns, w_ns))
            assert color is not None
            assert color.get("{%s}val" % w_ns) == "000000"


def _write_png(path: Path, width: int, height: int, color=(50, 120, 200)):
    """使用标准库生成可被 Word 读取的真实 PNG 样例。"""
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(raw, 1))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


@pytest.mark.parametrize("sizes", [
    [],
    [(1600, 900)],       # 1张横图
    [(900, 1600)],       # 1张竖图
    [(4000, 4000)],      # 1张超出页面可用区域的图
    [(1600, 900), (900, 1600)],  # 2张横/竖图
    [(4000, 4000), (4000, 4000)],  # 2张超尺寸图
])
def test_photo_regression_scenarios_keep_images_and_page_xml(tmp_path, sizes):
    photos = []
    for index, (width, height) in enumerate(sizes):
        path = tmp_path / f"photo-{index}.png"
        _write_png(path, width, height, color=(50 + index * 20, 120, 200))
        photos.append(str(path))

    output = tmp_path / "photos.docx"
    fill_template(_report(), str(_TEMPLATE), str(output), photos)

    with zipfile.ZipFile(output) as package:
        assert package.testzip() is None
        document_xml = package.read("word/document.xml").decode("utf-8")
        root = ET.fromstring(document_xml)

    assert document_xml.count("<w:drawing") == len(photos)
    doc_pr_ids = [doc_pr.get("id") for doc_pr in root.findall(
        ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")]
    assert len(doc_pr_ids) == len(set(doc_pr_ids))
    extents = [
        (int(extent.get("cx")), int(extent.get("cy")))
        for extent in root.findall(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent")
    ]
    for (render_width, render_height) in extents:
        assert (render_width, render_height) == (
            ATTACHMENT2_SLOT_WIDTH_EMU, ATTACHMENT2_SLOT_HEIGHT_EMU,
        )
    assert document_xml.count('w:type="page"') == 4
    assert 'w:type="oddPage"' not in document_xml
    assert 'w:type="evenPage"' not in document_xml
    assert "w:pageBreakBefore" not in document_xml
    assert "w:keepNext" not in document_xml
    assert "w:keepLines" not in document_xml
