"""DOCX XML regression tests for the accepted fixed-template structure."""

import base64
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.template_filler_service import fill_template  # noqa: E402
from app.services.template_profile_service import (  # noqa: E402
    TemplateProfileError,
    validate_current_template_profile,
)
from docx import Document  # noqa: E402


ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "word_templates" / "template.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def report(inspector_count=2):
    inspectors = [
        {"unit": "单位", "name": f"人员{index}", "badge_number": f"P{index}"}
        for index in range(inspector_count)
    ]
    return {
        "title": "电子数据检查笔录",
        "document_number": "SYN-TEST〔2026〕000号",
        "introduction": {
            "entrust_unit": "测试单位", "entrust_persons": ["测试人员"],
            "entrust_time": "2026年7月6日", "case_summary": "合成案件",
            "evidence_list": [
                {"evidence_number": "JC-A", "device_type": "手机"},
                {"evidence_number": "JC-B", "device_type": "平板"},
            ],
            "inspection_requirement": "测试要求", "inspection_time_range": "报告时间",
            "inspection_place": "测试鉴定中心",
            "inspector_snapshots": [
                {"unit": item["unit"], "name": item["name"], "police_number": item["badge_number"]}
                for item in inspectors
            ],
            "inspectors": inspectors,
        },
        "inspection": {
            "method": "测试方法", "hardware_device": "测试设备",
            "primary_software": {
                "name": "主取证软件", "version": "1.0",
                "confirmation_status": "confirmed_by_user",
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.12"},
            ],
            "process_steps": [],
            "result": {
                "evidence_number": "JC-A", "software_name": "主取证软件",
                "software_version": "1.0", "data_summary": "即时通讯、手机信息",
                "rar_filename": "client-value.rar", "md5_hash": "client-md5", "file_size": "1",
            },
        },
        "attachments": {
            "extract_list": {"rows": [{"electronic_data": "client-value.rar", "md5_hash": "client-md5"}]},
            "photo_ids": [], "disc_number": "GP20260706-01", "burning_date": "1900年1月1日",
        },
    }


def manifest(count):
    return {
        "manifest_id": "manifest-xml",
        "validation_status": "validated",
        "parts": [
            {
                "part_id": f"part-{index}", "part_number": index,
                "filename": f"server.part{index}.rar", "md5": f"{index:032x}",
                "disc_number": f"GP20260706-{index:02d}", "disc_date": "2026-07-06",
            }
            for index in range(1, count + 1)
        ],
    }


def document_root(path):
    with zipfile.ZipFile(path) as package:
        assert package.testzip() is None
        return ET.fromstring(package.read("word/document.xml"))


def visible_text(path):
    return "".join(document_root(path).itertext())


def body_paragraphs(root):
    return root.findall("./{%s}body/{%s}p" % (W_NS, W_NS))


def paragraph_text(paragraph):
    return "".join(node.text or "" for node in paragraph.findall(".//{%s}t" % W_NS))


def attachment_tables(root):
    return root.findall("./{%s}body/{%s}tbl" % (W_NS, W_NS))


def test_attachment1_starts_on_its_own_page_and_titles_are_single(tmp_path):
    output = tmp_path / "attachment-5.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(5))
    root = document_root(output)
    text = visible_text(output)
    assert text.count("附件1") == 1
    assert sum(paragraph_text(p) == "电子数据提取固定清单" for p in body_paragraphs(root)) == 1
    assert text.count("附件3") == 1
    page_breaks = root.findall(".//{%s}br" % W_NS)
    assert any(br.get("{%s}type" % W_NS) == "page" for br in page_breaks)
    tables = attachment_tables(root)
    assert [len(table.findall("./{%s}tr" % W_NS)) for table in tables] == [5, 5]
    assert "人员0" not in "".join("".join(node.itertext()) for node in tables[-1].iter())
    signature = "".join("".join(node.itertext()) for node in tables[-1].findall("./{%s}tr" % W_NS)[-1].iter())
    assert "检查人员" in signature and "盖章" in signature
    assert all(
        row.findall("./{%s}trPr/{%s}cantSplit" % (W_NS, W_NS))
        for table in tables for row in table.findall("./{%s}tr" % W_NS)
    )


@pytest.mark.parametrize(("count", "table_rows"), [(1, [6]), (4, [4, 5]), (8, [5, 3, 5]), (9, [5, 4, 5])])
def test_attachment1_final_page_keeps_template_signature_row(tmp_path, count, table_rows):
    output = tmp_path / f"attachment-{count}.docx"
    fill_template(report(20), str(TEMPLATE), str(output), [], manifest(count))
    tables = attachment_tables(document_root(output))
    assert [len(table.findall("./{%s}tr" % W_NS)) for table in tables] == table_rows
    for table in tables[:-1]:
        assert "检查人员" not in "".join("".join(node.itertext()) for node in table.iter())
    final_text = "".join("".join(node.itertext()) for node in tables[-1].iter())
    assert "检查人员" in final_text
    assert "盖章" in final_text


def test_body_keeps_dynamic_inspector_snapshots_but_attachment1_does_not(tmp_path):
    output = tmp_path / "inspectors.docx"
    fill_template(report(2), str(TEMPLATE), str(output), [], manifest(1))
    root = document_root(output)
    text = visible_text(output)
    assert "人员0" in text and "人员1" in text
    tables = attachment_tables(root)
    attachment_text = "".join("".join(node.itertext()) for node in tables[0].iter())
    assert "人员0" not in attachment_text
    assert "P0" not in attachment_text
    assert "inspector_final" not in text


def test_zero_photos_skip_attachment2_but_attachment3_remains(tmp_path):
    output = tmp_path / "attachment-2-empty.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(1))
    root = document_root(output)
    text = visible_text(output)
    assert "附件2" not in text
    assert "附件3" in text


    label3 = next(
        p for p in body_paragraphs(root) if paragraph_text(p) == "\u9644\u4ef63\uff1a"
    )
    body = root.find("./{%s}body" % W_NS)
    children = list(body)
    assert children[children.index(label3) - 1].tag == "{%s}tbl" % W_NS


def test_two_photos_start_attachment2_on_a_new_page(tmp_path):
    photo1, photo2 = tmp_path / "photo1.png", tmp_path / "photo2.png"
    photo1.write_bytes(MINIMAL_PNG)
    photo2.write_bytes(MINIMAL_PNG)
    output = tmp_path / "attachment-2-two-photos.docx"
    fill_template(report(), str(TEMPLATE), str(output), [str(photo1), str(photo2)], manifest(1))
    root = document_root(output)
    paragraphs = body_paragraphs(root)
    label2 = next(p for p in paragraphs if paragraph_text(p) == "附件2：")
    page_breaks = label2.findall(".//{%s}br[@{%s}type='page']" % (W_NS, W_NS))
    assert page_breaks
    assert "附件2" in visible_text(output)
    assert "附件3" in visible_text(output)


def test_attachment3_has_vertical_metadata_and_part_specific_bottom_anchor(tmp_path):
    output = tmp_path / "attachment-3.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(3))
    root = document_root(output)
    text = visible_text(output)
    assert text.count("附件3") == 1
    assert "文件名：server.part1.rar" in text
    assert "文件名：server.part2.rar" in text
    assert "文件名：server.part3.rar" in text
    assert text.count("本鉴定中心刻制的GP20260706-01号光盘") == 1
    assert text.count("本鉴定中心刻制的GP20260706-02号光盘") == 1
    assert text.count("本鉴定中心刻制的GP20260706-03号光盘") == 1
    assert "文件名：server.part1.rar；检验单位" not in text
    textboxes = root.findall(".//{%s}textbox" % V_NS)
    for textbox in textboxes:
        paragraphs = textbox.findall(".//{%s}txbxContent/{%s}p" % (W_NS, W_NS))
        lines = [paragraph_text(p) for p in paragraphs]
        if lines and lines[0].startswith("\u6587\u4ef6\u540d\uff1a"):
            size = paragraphs[4].find(
                "./{%s}pPr/{%s}rPr/{%s}sz" % (W_NS, W_NS, W_NS)
            )
            assert size is not None and size.get("{%s}val" % W_NS) == "32"
    metadata_lines = []
    for textbox in textboxes:
        lines = [paragraph_text(p) for p in textbox.findall(".//{%s}txbxContent/{%s}p" % (W_NS, W_NS))]
        if any(line.startswith("文件名：") for line in lines):
            metadata_lines.append(lines[:5])
    assert metadata_lines == [
        ["文件名：server.part1.rar", "检验单位：测试鉴定中心", "光盘编号：GP20260706-01", "文件哈希：00000000000000000000000000000001", "刻录时间：2026年7月6日"],
        ["文件名：server.part2.rar", "检验单位：测试鉴定中心", "光盘编号：GP20260706-02", "文件哈希：00000000000000000000000000000002", "刻录时间：2026年7月6日"],
        ["文件名：server.part3.rar", "检验单位：测试鉴定中心", "光盘编号：GP20260706-03", "文件哈希：00000000000000000000000000000003", "刻录时间：2026年7月6日"],
    ]


def test_attachment_summary_uses_manifest_range_and_counts(tmp_path):
    output = tmp_path / "attachment-summary.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(9))
    text = visible_text(output)
    assert "3、本鉴定中心刻制的编号为“GP20260706-01”至“GP20260706-09”的光盘9张，共9页。" in text
    assert "GP20260706-01”的光盘1张，共1页" not in text


def test_footer_fields_are_dynamic_and_not_section_pages(tmp_path):
    output = tmp_path / "footer-fields.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(5))
    with zipfile.ZipFile(output) as package:
        settings = package.read("word/settings.xml").decode("utf-8")
        footer_xml = "".join(
            package.read(info.filename).decode("utf-8")
            for info in package.infolist()
            if info.filename.startswith("word/footer") and info.filename.endswith(".xml")
        )
        document = package.read("word/document.xml").decode("utf-8")
    assert 'w:updateFields w:val="true"' in settings
    assert "PAGE" in footer_xml and "NUMPAGES" in footer_xml
    assert "SECTIONPAGES" not in footer_xml
    assert 'w:pgNumType w:start="1"' not in document
    assert footer_xml.count('w:fldCharType="begin"') >= 4


def test_vml_and_relationship_ids_are_preserved_and_unique(tmp_path):
    output = tmp_path / "attachment-vml.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(3))
    root = document_root(output)
    xml = ET.tostring(root, encoding="unicode")
    assert xml.count("textbox") >= 6
    assert xml.count("txbxContent") >= 6
    vml_ids = [node.get("id") for node in root.iter() if node.tag.startswith("{%s}" % V_NS) and node.get("id")]
    assert len(vml_ids) == len(set(vml_ids))
    doc_pr_ids = [node.get("id") for node in root.findall(".//{%s}docPr" % WP_NS)]
    assert len(doc_pr_ids) == len(set(doc_pr_ids))
    with zipfile.ZipFile(output) as package:
        rel_root = ET.fromstring(package.read("word/_rels/document.xml.rels"))
    relationship_ids = {node.get("Id") for node in rel_root.findall("./{%s}Relationship" % REL_NS)}
    referenced_ids = {
        value for node in root.iter() for key, value in node.attrib.items()
        if key.endswith("}id") or key.endswith("}embed")
    }
    assert referenced_ids <= relationship_ids


def test_template_profile_matches_fixed_signature_and_anchors(tmp_path):
    copied = tmp_path / "template.docx"
    shutil.copyfile(TEMPLATE, copied)
    mutated = tmp_path / "mutated.docx"
    with zipfile.ZipFile(copied, "r") as source, zipfile.ZipFile(
        mutated, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename == "word/document.xml":
                content = content.replace(b"document", b"document-x", 1)
            target.writestr(info.filename, content)
    mutated.replace(copied)
    with pytest.raises(TemplateProfileError) as error:
        validate_current_template_profile(str(copied), Document(str(TEMPLATE)))
    assert error.value.code == "TEMPLATE_PROFILE_MISMATCH"
    output = tmp_path / "profile-mismatch-no-output.docx"
    with pytest.raises(TemplateProfileError):
        fill_template(report(), str(copied), str(output), [], manifest(1))
    assert not output.exists()
    profile = validate_current_template_profile(str(TEMPLATE), Document(str(TEMPLATE)))
    assert profile.profile_id == "current-template-v1"
    assert profile.expected_attachment1_header == ("序号", "电子数据", "来源", "提取方法", "文件MD5哈希值")
