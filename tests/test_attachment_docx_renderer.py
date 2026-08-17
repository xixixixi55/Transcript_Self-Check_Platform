"""DOCX XML regression tests for the accepted fixed-template structure."""

import base64
import hashlib
import os
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.template_filler_service import fill_template  # noqa: E402
from app.services.attachment2_image_service import (  # noqa: E402
    ATTACHMENT2_CAPTION_LINE_TWIPS,
    ATTACHMENT2_DUAL_GROUP_IMAGE_ROW_HEIGHT_TWIPS,
    ATTACHMENT2_DUAL_GROUP_SLOT_HEIGHT_EMU,
    ATTACHMENT2_GROUP_GAP_TWIPS,
    ATTACHMENT2_SLOT_HEIGHT_EMU,
    ATTACHMENT2_SLOT_WIDTH_EMU,
    calculate_fixed_geometry,
)
from app.services.template_profile_service import (  # noqa: E402
    TemplateProfileError,
    current_template_profile,
    validate_current_template_profile,
)
from docx import Document  # noqa: E402


ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "word_templates" / "template.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def png_bytes(width: int, height: int) -> bytes:
    rows = b"".join(b"\x00" + b"\x30\x80\xc0\xff" * width for _ in range(height))

    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


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


def report_with_photo_count(photo_count: int) -> dict:
    value = report()
    value["introduction"]["evidence_list"] = [
        {
            "id": f"material-{index + 1}",
            "evidence_number": f"JC-{chr(65 + index)}",
            "device_type": "synthetic",
        }
        for index in range(photo_count // 2)
    ] or value["introduction"]["evidence_list"]
    set_photo_ids(value, [f"photo-{index + 1}" for index in range(photo_count)])
    return value


def set_photo_ids(report_value: dict, photo_ids: list[str]) -> None:
    report_value["attachments"]["photo_ids"] = photo_ids
    evidence_list = report_value["introduction"]["evidence_list"]
    report_value["attachments"]["photo_groups"] = [
        {
            "material_id": evidence_list[index]["id"],
            "material_number": evidence_list[index]["evidence_number"],
            "display_text": f"检材{evidence_list[index]['evidence_number']}照片",
            "ordered_image_ids": photo_ids[index * 2:index * 2 + 2],
            "source_order": index + 1,
        }
        for index in range(len(photo_ids) // 2)
    ]


def manifest(count):
    return {
        "manifest_id": "manifest-xml",
        "validation_status": "validated",
        "volume_size_bytes": 4_000_000_000,
        "parts": [
            {
                "part_id": f"part-{index}", "part_number": index,
                "filename": f"server.part{index}.rar", "md5": f"{index:032x}",
                "size_bytes": index * 100,
                "disc_number": f"GP20260706-{index:02d}", "disc_date": "2026-07-06",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
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


def attachment2_tables(root):
    return [
        table for table in attachment_tables(root)
        if [len(row.findall("./{%s}tc" % W_NS))
            for row in table.findall("./{%s}tr" % W_NS)] in ([2], [2, 1], [2, 2])
        or [len(row.findall("./{%s}tc" % W_NS))
            for row in table.findall("./{%s}tr" % W_NS)] in (
                [1, 1], [2, 1, 2, 1], [2, 1, 1, 2, 1],
            )
        or (
            [len(row.findall("./{%s}tc" % W_NS))
             for row in table.findall("./{%s}tr" % W_NS)] == [1]
            and len(table.findall(".//{%s}drawing" % W_NS)) == 2
        )
    ]


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
    assert [len(table.findall("./{%s}tr" % W_NS)) for table in tables] == [5, 2]
    assert "附件：1、电子数据提取固定清单，共2页；" in text
    assert "人员0" not in "".join("".join(node.itertext()) for node in tables[-1].iter())
    signature = "".join("".join(node.itertext()) for node in tables[-1].findall("./{%s}tr" % W_NS)[-1].iter())
    assert "检查人员" in signature and "盖章" in signature
    assert all(
        row.findall("./{%s}trPr/{%s}cantSplit" % (W_NS, W_NS))
        for table in tables for row in table.findall("./{%s}tr" % W_NS)
    )


@pytest.mark.parametrize(
    ("count", "table_rows"),
    [
        (1, [5]), (3, [5]), (4, [5, 1]), (5, [5, 2]),
        (6, [5, 3]), (8, [5, 4, 1]), (9, [5, 4, 2]),
    ],
)
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


def test_attachment1_three_rows_match_customer_font_baseline(tmp_path):
    output = tmp_path / "attachment-1-three.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(3))
    table = attachment_tables(document_root(output))[0]
    rows = table.findall("./{%s}tr" % W_NS)
    assert len(rows) == 5
    expected = [
        ("\u6977\u4f53", "32"),
        ("\u4eff\u5b8b_GB2312", "32"),
        ("\u4eff\u5b8b_GB2312", "32"),
        ("\u4eff\u5b8b_GB2312", "22"),
        ("\u4eff\u5b8b_GB2312", "32"),
    ]
    cells = rows[1].findall("./{%s}tc" % W_NS)
    for cell, (east_asia, size) in zip(cells, expected):
        run = cell.find(".//{%s}r" % W_NS)
        r_pr = run.find("./{%s}rPr" % W_NS)
        fonts = r_pr.find("./{%s}rFonts" % W_NS)
        assert fonts.get("{%s}eastAsia" % W_NS) == east_asia
        assert r_pr.find("./{%s}sz" % W_NS).get("{%s}val" % W_NS) == size
    assert "\u68c0\u67e5\u4eba\u5458" in "".join(rows[-1].itertext())


def test_attachment1_latin_fields_allow_character_wrap_on_every_page(tmp_path):
    output = tmp_path / "attachment-1-latin-wrap.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(5))

    for table in attachment_tables(document_root(output)):
        for row in table.findall("./{%s}tr" % W_NS):
            cells = row.findall("./{%s}tc" % W_NS)
            if len(cells) < 5 or "检查人员" in "".join(row.itertext()):
                continue
            for cell_index in (1, 4):
                paragraphs = cells[cell_index].findall(".//{%s}p" % W_NS)
                assert paragraphs
                for paragraph in paragraphs:
                    paragraph_pr = paragraph.find("./{%s}pPr" % W_NS)
                    word_wrap = paragraph_pr.find("./{%s}wordWrap" % W_NS)
                    assert word_wrap is not None
                    assert word_wrap.get("{%s}val" % W_NS) == "off"
                    properties = list(paragraph_pr)
                    later_properties = [
                        node for node in properties
                        if node.tag in {
                            "{%s}spacing" % W_NS,
                            "{%s}ind" % W_NS,
                            "{%s}jc" % W_NS,
                            "{%s}rPr" % W_NS,
                        }
                    ]
                    assert all(
                        properties.index(word_wrap) < properties.index(node)
                        for node in later_properties
                    )


def test_attachment1_source_puts_each_material_number_on_its_own_line(tmp_path):
    current_report = report()
    material_numbers = [f"JC202605790{index}" for index in range(1, 7)]
    current_report["introduction"]["evidence_list"] = [
        {"evidence_number": number, "device_type": "手机"}
        for number in material_numbers
    ]
    output = tmp_path / "attachment-1-source-lines.docx"
    fill_template(current_report, str(TEMPLATE), str(output), [], manifest(5))

    expected_lines = [
        *[f"{number}、" for number in material_numbers[:-1]],
        material_numbers[-1],
        "检材内提取",
    ]
    tables = attachment_tables(document_root(output))
    assert len(tables) == 2
    for table_index, table in enumerate(tables):
        rows = table.findall("./{%s}tr" % W_NS)
        first_data_index = 1 if table_index == 0 else 0
        source_cell = rows[first_data_index].findall("./{%s}tc" % W_NS)[2]
        paragraph = source_cell.find(".//{%s}p" % W_NS)
        assert [node.text for node in paragraph.findall(".//{%s}t" % W_NS)] == expected_lines
        assert len(paragraph.findall(".//{%s}br" % W_NS)) == len(material_numbers)
        merge = source_cell.find("./{%s}tcPr/{%s}vMerge" % (W_NS, W_NS))
        assert merge.get("{%s}val" % W_NS) == "restart"
        for continuation in rows[first_data_index + 1:]:
            if ".rar" not in "".join(continuation.itertext()):
                continue
            continuation_source = continuation.findall("./{%s}tc" % W_NS)[2]
            assert "".join(continuation_source.itertext()) == ""
            continuation_merge = continuation_source.find(
                "./{%s}tcPr/{%s}vMerge" % (W_NS, W_NS)
            )
            assert continuation_merge is not None
            assert continuation_merge.get("{%s}val" % W_NS) is None


def test_attachment1_four_rows_put_signature_on_new_page(tmp_path):
    output = tmp_path / "attachment-1-four.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(4))
    tables = attachment_tables(document_root(output))
    assert [len(table.findall("./{%s}tr" % W_NS)) for table in tables] == [5, 1]
    first_text = "".join(tables[0].itertext())
    second_text = "".join(tables[1].itertext())
    assert "server.part4.rar" in first_text
    assert "\u68c0\u67e5\u4eba\u5458" not in first_text
    assert "\u68c0\u67e5\u4eba\u5458" in second_text


def test_attachment1_six_rows_use_one_blank_row_before_signature(tmp_path):
    output = tmp_path / "attachment-1-six.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(6))
    tables = attachment_tables(document_root(output))
    assert [len(table.findall("./{%s}tr" % W_NS)) for table in tables] == [5, 3]
    second_rows = tables[1].findall("./{%s}tr" % W_NS)
    assert "server.part5.rar" in "".join(second_rows[0].itertext())
    assert "server.part6.rar" in "".join(second_rows[1].itertext())
    assert "\u68c0\u67e5\u4eba\u5458" in "".join(second_rows[2].itertext())


@pytest.mark.parametrize(("count", "max_end_y"), [(1, 100), (2, 50)])
def test_attachment1_blank_diagonal_stays_inside_blank_rows(tmp_path, count, max_end_y):
    output = tmp_path / f"attachment-{count}-diagonal.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(count))
    table = attachment_tables(document_root(output))[-1]
    rows = table.findall("./{%s}tr" % W_NS)
    lines = table.findall(".//{%s}line" % V_NS)

    assert len(lines) == 1
    end_y = float(lines[0].get("to").rsplit(",", 1)[1].removesuffix("pt"))
    assert end_y < max_end_y
    assert not rows[-1].findall(".//{%s}line" % V_NS)


def test_attachment1_three_rows_do_not_copy_blank_diagonal(tmp_path):
    output = tmp_path / "attachment-3-no-diagonal.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(3))
    table = attachment_tables(document_root(output))[0]
    assert not table.findall(".//{%s}line" % V_NS)


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
    fill_template(report_with_photo_count(2), str(TEMPLATE), str(output), [str(photo1), str(photo2)], manifest(1))
    root = document_root(output)
    paragraphs = body_paragraphs(root)
    label2 = next(p for p in paragraphs if paragraph_text(p) == "附件2：")
    page_breaks = label2.findall(".//{%s}br[@{%s}type='page']" % (W_NS, W_NS))
    assert page_breaks
    assert "附件2" in visible_text(output)
    assert "附件3" in visible_text(output)


@pytest.mark.parametrize("photo_count", [2, 4, 6, 8])
def test_attachment2_uses_fixed_pair_grids_and_preserves_order(tmp_path, photo_count):
    current_report = report_with_photo_count(photo_count)
    set_photo_ids(current_report, [
        f"reviewed-{index}" for index in range(1, photo_count + 1)
    ])
    photo_paths = []
    for index in range(1, photo_count + 1):
        path = tmp_path / f"photo-{index}.png"
        path.write_bytes(png_bytes(300 + index * 10, 500 + index * 7))
        photo_paths.append(str(path))
    output = tmp_path / f"attachment-2-{photo_count}.docx"

    fill_template(current_report, str(TEMPLATE), str(output), photo_paths, manifest(1))
    root = document_root(output)
    tables = attachment2_tables(root)
    assert len(tables) == (photo_count + 3) // 4
    text = visible_text(output)
    assert text.count("附件2") == 1
    assert text.count("附件3") == 1
    assert f"检材图{photo_count}张，共{len(tables)}页" in text
    expected_captions = [f"检材JC-{chr(65 + index)}照片" for index in range(photo_count // 2)]
    assert all(text.count(caption) == 1 for caption in expected_captions)
    evidence_label = "、".join(
        f"JC-{chr(65 + index)}" for index in range(photo_count // 2)
    )
    assert f"经对编号为{evidence_label}号检材使用主取证软件" in text
    expected_shapes = [[2, 1]] if photo_count == 2 else (
        [[2, 1, 1, 2, 1]] * (photo_count // 4) + ([[2, 1]] if photo_count % 4 else [])
    )
    assert [
        [len(row.findall("./{%s}tc" % W_NS))
         for row in table.findall("./{%s}tr" % W_NS)]
        for table in tables
    ] == expected_shapes
    assert [len(table.findall(".//{%s}drawing" % W_NS)) for table in tables] == [
        2 if shape == [2, 1] else 4 for shape in expected_shapes
    ]

    with zipfile.ZipFile(output) as package:
        rel_root = ET.fromstring(package.read("word/_rels/document.xml.rels"))
        relationships = {
            node.get("Id"): node.get("Target")
            for node in rel_root.findall("./{%s}Relationship" % REL_NS)
            if node.get("Type", "").endswith("/image")
        }
        media = sorted(
            info.filename for info in package.infolist()
            if info.filename.startswith("word/media/")
        )
        media_bytes = {
            info.filename.removeprefix("word/"): package.read(info.filename)
            for info in package.infolist()
            if info.filename.startswith("word/media/")
        }
    assert len(media) == photo_count
    embeds = [
        drawing.find(".//{%s}blip" % A_NS).get("{%s}embed" % DOC_REL_NS)
        for table in tables
        for drawing in table.findall(".//{%s}drawing" % W_NS)
    ]
    expected_sequence = list(range(1, photo_count + 1))
    source_hashes = [
        hashlib.sha256(Path(photo_paths[index - 1]).read_bytes()).digest()
        for index in expected_sequence
    ]
    embedded_hashes = [
        hashlib.sha256(media_bytes[relationships[relationship_id]]).digest()
        for relationship_id in embeds
    ]
    assert embedded_hashes == source_hashes
    drawing_ids = [
        node.get("id") for node in root.iter()
        if node.tag in {
            "{%s}docPr" % WP_NS,
            "{%s}cNvPr" % "http://schemas.openxmlformats.org/drawingml/2006/picture",
        }
    ]
    assert len(drawing_ids) == len(set(drawing_ids))


@pytest.mark.parametrize(("photo_count", "expected_rows"), [(2, 2), (4, 5)])
def test_attachment2_grid_cells_are_centered_and_use_profile_slots(
    tmp_path, photo_count, expected_rows,
):
    current_report = report_with_photo_count(photo_count)
    set_photo_ids(current_report, [f"center-{index}" for index in range(photo_count)])
    paths = []
    for index in range(photo_count):
        path = tmp_path / f"center-{index}.png"
        path.write_bytes(png_bytes(600 + index, 400 + index))
        paths.append(str(path))
    output = tmp_path / f"center-{photo_count}.docx"
    fill_template(current_report, str(TEMPLATE), str(output), paths, manifest(1))
    root = document_root(output)
    table = attachment2_tables(root)[0]
    profile = current_template_profile()
    body = root.find("./{%s}body" % W_NS)
    page_break = list(body)[list(body).index(table) - 1]
    spacing = page_break.find("./{%s}pPr/{%s}spacing" % (W_NS, W_NS))
    assert spacing.get("{%s}after" % W_NS) == (
        str(profile.attachment2_page_break_after_twips)
        if photo_count == 2 else "0"
    )
    slot_twips = round(profile.attachment2_slot_width_emu / 635)
    table_width = table.find("./{%s}tblPr/{%s}tblW" % (W_NS, W_NS))
    assert table_width.get("{%s}w" % W_NS) == str(slot_twips * 2)
    expected_columns = 2
    assert len(table.findall("./{%s}tblGrid/{%s}gridCol" % (W_NS, W_NS))) == expected_columns
    rows = table.findall("./{%s}tr" % W_NS)
    assert len(rows) == expected_rows
    image_rows = [row for row in rows if row.findall(".//{%s}drawing" % W_NS)]
    for row in image_rows:
        height = row.find("./{%s}trPr/{%s}trHeight" % (W_NS, W_NS))
        assert height.get("{%s}val" % W_NS) == str(
            ATTACHMENT2_DUAL_GROUP_IMAGE_ROW_HEIGHT_TWIPS,
        )
        assert height.get("{%s}hRule" % W_NS) == "exact"
        for cell in row.findall("./{%s}tc" % W_NS):
            tc_pr = cell.find("./{%s}tcPr" % W_NS)
            assert tc_pr.find("./{%s}vAlign" % W_NS).get("{%s}val" % W_NS) == "center"
            margins = tc_pr.find("./{%s}tcMar" % W_NS)
            assert margins is not None
            assert list(tc_pr).index(margins) < list(tc_pr).index(tc_pr.find("./{%s}vAlign" % W_NS))
            assert all(
                item.get("{%s}w" % W_NS) == "0" for item in list(margins)
            )
            paragraph_pr = cell.find("./{%s}p/{%s}pPr" % (W_NS, W_NS))
            assert paragraph_pr.find("./{%s}spacing" % W_NS) is not None
            alignment = paragraph_pr.find("./{%s}jc" % W_NS).get("{%s}val" % W_NS)
            assert alignment == "center"
    caption_rows = [
        row for row in rows
        if any(paragraph_text(p) for p in row.findall(".//{%s}p" % W_NS))
    ]
    expected_caption_heights = [ATTACHMENT2_CAPTION_LINE_TWIPS] * (
        2 if photo_count == 4 else 1
    )
    for row, expected_height in zip(caption_rows, expected_caption_heights):
        height = row.find("./{%s}trPr/{%s}trHeight" % (W_NS, W_NS))
        assert height.get("{%s}val" % W_NS) == str(expected_height)
        assert height.get("{%s}hRule" % W_NS) == "exact"
    spacer_rows = [
        row for row in rows
        if not row.findall(".//{%s}drawing" % W_NS)
        and not any(paragraph_text(p) for p in row.findall(".//{%s}p" % W_NS))
    ]
    assert len(spacer_rows) == (1 if photo_count == 4 else 0)
    if spacer_rows:
        spacer_height = spacer_rows[0].find("./{%s}trPr/{%s}trHeight" % (W_NS, W_NS))
        assert spacer_height.get("{%s}val" % W_NS) == str(ATTACHMENT2_GROUP_GAP_TWIPS)
        assert spacer_height.get("{%s}hRule" % W_NS) == "exact"
    slot_height_emu = ATTACHMENT2_DUAL_GROUP_SLOT_HEIGHT_EMU
    extents = [
        (int(extent.get("cx")), int(extent.get("cy")))
        for extent in table.findall(".//{%s}extent" % WP_NS)
    ]
    assert extents == [
        (
            calculate_fixed_geometry(600 + index, 400 + index,
                                     slot_height_emu=slot_height_emu).render_width_emu,
            calculate_fixed_geometry(600 + index, 400 + index,
                                     slot_height_emu=slot_height_emu).render_height_emu,
        )
        for index in range(photo_count)
    ]
    first_cell_runs = table.findall("./{%s}tr[1]/{%s}tc[1]/{%s}p/{%s}r" % (
        W_NS, W_NS, W_NS, W_NS,
    ))
    assert len(first_cell_runs) == 1
    captions = [
        paragraph_text(paragraph)
        for row in rows
        for cell in row.findall("./{%s}tc" % W_NS)
        for paragraph in cell.findall("./{%s}p" % W_NS)
        if paragraph_text(paragraph)
    ]
    assert captions == (
        ["检材JC-A照片"] if photo_count == 2
        else ["检材JC-A照片", "检材JC-B照片"]
    )


def test_attachment2_drawing_extents_are_fixed_for_landscape_and_portrait(
    tmp_path,
):
    current_report = report_with_photo_count(2)
    paths = []
    for index, (width, height) in enumerate(((1600, 400), (400, 1600))):
        path = tmp_path / f"SYNTHETIC-target-box-{index}.png"
        path.write_bytes(png_bytes(width, height))
        paths.append(str(path))

    output = tmp_path / "SYNTHETIC-target-box.docx"
    fill_template(current_report, str(TEMPLATE), str(output), paths, manifest(1))
    tables = attachment2_tables(document_root(output))
    extents = [
        (int(extent.get("cx")), int(extent.get("cy")))
        for extent in tables[0].findall(".//{%s}extent" % WP_NS)
    ]
    transform_extents = [
        (int(extent.get("cx")), int(extent.get("cy")))
        for extent in tables[0].findall(
            ".//{%s}graphic//{%s}xfrm/{%s}ext" % (A_NS, A_NS, A_NS)
        )
    ]

    assert len(tables) == 1
    assert [len(row.findall("./{%s}tc" % W_NS)) for row in tables[0].findall("./{%s}tr" % W_NS)] == [2, 1]
    assert extents == [
        (
            calculate_fixed_geometry(width, height).render_width_emu,
            calculate_fixed_geometry(width, height).render_height_emu,
        )
        for width, height in ((1600, 400), (400, 1600))
    ]
    assert transform_extents == extents


def test_three_material_attachment2_centers_single_group_continuation(tmp_path):
    current_report = report_with_photo_count(6)
    set_photo_ids(current_report, [f"center-three-{index}" for index in range(6)])
    paths = []
    for index in range(6):
        path = tmp_path / f"center-three-{index}.png"
        path.write_bytes(png_bytes(700 + index, 500 + index))
        paths.append(str(path))
    output = tmp_path / "attachment-2-three-materials.docx"
    fill_template(current_report, str(TEMPLATE), str(output), paths, manifest(1))
    root = document_root(output)
    tables = attachment2_tables(root)
    assert len(tables) == 2
    assert [len(row.findall("./{%s}tc" % W_NS)) for row in tables[0].findall("./{%s}tr" % W_NS)] == [2, 1, 1, 2, 1]
    assert [len(row.findall("./{%s}tc" % W_NS)) for row in tables[1].findall("./{%s}tr" % W_NS)] == [2, 1]
    body = root.find("./{%s}body" % W_NS)
    page_breaks = [list(body)[list(body).index(table) - 1] for table in tables]
    profile = current_template_profile()
    assert [paragraph_text(page) for page in page_breaks] == ["附件2：", ""]
    assert [
        page.find("./{%s}pPr/{%s}spacing" % (W_NS, W_NS)).get("{%s}after" % W_NS)
        for page in page_breaks
    ] == ["0", str(profile.attachment2_page_break_after_twips)]
    assert page_breaks[0].find("./{%s}pPr" % W_NS) is not None
    assert page_breaks[1].find("./{%s}pPr" % W_NS) is not None


def test_attachment2_continuation_titles_are_empty_break_paragraphs(tmp_path):
    current_report = report_with_photo_count(6)
    set_photo_ids(current_report, [
        "one", "two", "three", "four", "five", "six",
    ])
    paths = []
    for index in range(6):
        path = tmp_path / f"continuation-{index}.png"
        path.write_bytes(png_bytes(800 + index, 600 + index))
        paths.append(str(path))
    output = tmp_path / "attachment-2-continuation.docx"
    fill_template(current_report, str(TEMPLATE), str(output), paths, manifest(1))
    root = document_root(output)
    paragraphs = body_paragraphs(root)
    title_paragraphs = [p for p in paragraphs if paragraph_text(p) == "附件2："]
    assert len(title_paragraphs) == 1
    assert sum(
        paragraph_text(p) == "" and any(
            br.get("{%s}type" % W_NS) == "page"
            for br in p.findall(".//{%s}br" % W_NS)
        )
        for p in paragraphs
    ) >= 1
    assert sum(
        any(br.get("{%s}type" % W_NS) == "page" for br in p.findall(".//{%s}br" % W_NS))
        for p in paragraphs
    ) >= 2


@pytest.mark.parametrize("photo_count", [1, 3, 5])
def test_attachment2_odd_images_do_not_leave_a_docx(tmp_path, photo_count):
    paths = []
    for index in range(photo_count):
        path = tmp_path / f"odd-{index}.png"
        path.write_bytes(png_bytes(10, 10))
        paths.append(str(path))
    output = tmp_path / f"odd-{photo_count}.docx"

    with pytest.raises(Exception) as error:
        fill_template(report(), str(TEMPLATE), str(output), paths, manifest(1))

    assert getattr(error.value, "code", None) == "ATTACHMENT2_IMAGE_COUNT_ODD"
    assert not output.exists()


def test_attachment2_invalid_images_do_not_leave_a_docx(tmp_path):
    paths = []
    for index in range(2):
        path = tmp_path / f"invalid-{index}.png"
        path.write_bytes(b"corrupt-image")
        paths.append(str(path))
    output = tmp_path / "invalid-images.docx"

    with pytest.raises(Exception) as error:
        fill_template(report_with_photo_count(2), str(TEMPLATE), str(output), paths, manifest(1))

    assert getattr(error.value, "code", None) == "ATTACHMENT2_IMAGE_INVALID"
    assert not output.exists()


def test_attachment3_has_vertical_metadata_and_part_specific_bottom_anchor(tmp_path):
    output = tmp_path / "attachment-3.docx"
    fill_template(report(), str(TEMPLATE), str(output), [], manifest(3))
    root = document_root(output)
    text = visible_text(output)
    assert text.count("附件3") == 1
    assert "文件名：" not in text
    assert text.count("本鉴定中心刻制的GP20260706-01号光盘") == 1
    assert text.count("本鉴定中心刻制的GP20260706-02号光盘") == 1
    assert text.count("本鉴定中心刻制的GP20260706-03号光盘") == 1
    textboxes = root.findall(".//{%s}textbox" % V_NS)
    for textbox in textboxes:
        paragraphs = textbox.findall(".//{%s}txbxContent/{%s}p" % (W_NS, W_NS))
        lines = [paragraph_text(p) for p in paragraphs]
        if lines and lines[0].startswith("检验单位："):
            size = paragraphs[3].find(
                "./{%s}pPr/{%s}rPr/{%s}sz" % (W_NS, W_NS, W_NS)
            )
            assert size is not None and size.get("{%s}val" % W_NS) == "32"
    metadata_lines = []
    for textbox in textboxes:
        lines = [paragraph_text(p) for p in textbox.findall(".//{%s}txbxContent/{%s}p" % (W_NS, W_NS))]
        if any(line.startswith("检验单位：") for line in lines):
            metadata_lines.append([line for line in lines if line])
    assert metadata_lines == [
        ["检验单位：测试鉴定中心", "光盘编号：GP20260706-01", "文件哈希：00000000000000000000000000000001", "刻录时间：2026年7月6日"],
        ["检验单位：测试鉴定中心", "光盘编号：GP20260706-02", "文件哈希：00000000000000000000000000000002", "刻录时间：2026年7月6日"],
        ["检验单位：测试鉴定中心", "光盘编号：GP20260706-03", "文件哈希：00000000000000000000000000000003", "刻录时间：2026年7月6日"],
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
