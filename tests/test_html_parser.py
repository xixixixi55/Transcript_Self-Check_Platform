"""T006: HTML 解析器测试 — 使用SYNTHETIC案件案实际数据验证"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.repository.html_parser import (
    parse_case_info,
    parse_device_lists,
    parse_report_info,
    parse_navigation,
    parse_device_base,
)
from app.repository.device_field_parser import extract_device_fields

# 实际报告数据目录
REPORT_DATA_DIR = r"D:\脱敏示例\SYNTHETIC案件SYNTHETIC当事人被诈骗案_20260707161248_html\data"


def test_parse_case_info():
    """验证案件信息提取"""
    info = parse_case_info(REPORT_DATA_DIR)

    assert info["case_name"] == "SYNTHETIC案件SYNTHETIC当事人被诈骗案"
    assert info["case_number"] == "A0000000000000000000000"
    assert info["collector"] == "洪腾峰"
    assert "台州市公安局测试地区分局" in info["collect_unit"]
    assert "许人天" in info["submit_person"]
    assert "张维乐" in info["submit_person"]
    assert "白云派出所" in info["submit_unit"]
    assert info["case_type"] == "诈骗案"


def test_parse_device_lists():
    """验证设备列表提取"""
    devices = parse_device_lists(REPORT_DATA_DIR)

    assert len(devices) >= 1
    assert devices[0]["evidence_number"] == "SYN-JC00000001"
    assert "2026-07-07" in devices[0]["time_range"]


def test_parse_report_info():
    """验证取证工具版本提取"""
    info = parse_report_info(REPORT_DATA_DIR)

    assert "product_version" in info
    assert "FL-901" in info.get("product_version", "")


def test_parse_navigation():
    """验证数据分类树提取"""
    nav = parse_navigation(REPORT_DATA_DIR)

    assert "categories" in nav
    assert nav["total_items"] > 0
    # 应该包含常见分类
    categories = nav["categories"]
    assert len(categories) > 0
    print(f"\n  提取到 {len(categories)} 个分类: {categories[:10]}")
    print(f"  总条目数: {nav['total_items']}")


def test_parse_device_base_maps_name_imeis_and_serial(tmp_path):
    base_dir = tmp_path / "data" / "SYN-JC00000001" / "Base"
    base_dir.mkdir(parents=True)
    (base_dir / "device.json").write_text(
        '{"设备名称":"HUAWEI Pura 70 Pro","IMEI1":"123456789012345",'
        '"IMEI2":"543210987654321","序列号":"SYN-SERIAL-00000001"}',
        encoding="utf-8",
    )

    fields = parse_device_base(str(tmp_path / "data"), "SYN-JC00000001")

    assert fields["device_name"] == "HUAWEI Pura 70 Pro"
    assert fields["model"] == "HUAWEI Pura 70 Pro"
    assert fields["imei1"] == "123456789012345"
    assert fields["imei2"] == "543210987654321"
    assert fields["serial_number"] == "SYN-SERIAL-00000001"


def test_parse_device_base_maps_label_value_records(tmp_path):
    base_dir = tmp_path / "data" / "JC01" / "Base"
    base_dir.mkdir(parents=True)
    (base_dir / "device.json").write_text(
        '{"items":[{"name":"设备名称","value":"HUAWEI Pura 70 Pro"},'
        '{"name":"型号","value":"HUAWEI Pura 70 Pro"},'
        '{"name":"IMEI1","value":"123456789012345"},'
        '{"name":"序列号","value":"SYN-SERIAL-00000001"}]}',
        encoding="utf-8",
    )

    fields = parse_device_base(str(tmp_path / "data"), "JC01")

    assert fields["device_name"] == "HUAWEI Pura 70 Pro"
    assert fields["model"] == "HUAWEI Pura 70 Pro"
    assert fields["imei1"] == "123456789012345"
    assert fields["serial_number"] == "SYN-SERIAL-00000001"


def test_extract_device_fields_accepts_device_model_alias():
    fields = extract_device_fields({"设备型号": "iPhone 15 Pro"}, "")

    assert fields["model"] == "iPhone 15 Pro"
    assert fields["device_name"] == "iPhone 15 Pro"


def test_extract_device_fields_accepts_information_content_rows():
    payload = {
        "rows": [
            {"信息": "设备型号", "内容": "HUAWEI Mate 60"},
            {"信息": "IMEI1", "内容": "123456789012345"},
        ]
    }

    fields = extract_device_fields(payload, "")

    assert fields["model"] == "HUAWEI Mate 60"
    assert fields["device_name"] == "HUAWEI Mate 60"
    assert fields["imei1"] == "123456789012345"


def test_extract_device_fields_accepts_c1_c2_table_rows():
    payload = {
        "rows": [
            {"c1": "设备名称", "c2": "Google Pixel 8"},
            {"c1": "设备型号", "c2": "Pixel 8"},
            {"c1": "IMEI1", "c2": "543210987654321"},
            {"c1": "序列号", "c2": "SN123456"},
        ]
    }

    fields = extract_device_fields(payload, "")

    assert fields == {
        "device_name": "Google Pixel 8",
        "model": "Pixel 8",
        "imei1": "543210987654321",
        "imei2": "",
        "serial_number": "SN123456",
    }


def test_extract_device_fields_ignores_empty_missing_and_malformed_rows():
    payload = [
        {"信息": "设备型号", "内容": ""},
        {"信息": "设备型号"},
        {"c1": "设备型号"},
        {"c1": "设备型号", "c2": {"nested": "not a scalar"}},
        {"c2": "iPhone 15"},
        "not a row",
        None,
    ]

    fields = extract_device_fields(payload, "")

    assert fields == {
        "device_name": "",
        "model": "",
        "imei1": "",
        "imei2": "",
        "serial_number": "",
    }


def test_parse_device_base_keeps_phone_directory_compatibility(tmp_path):
    phone_dir = tmp_path / "data" / "JC02" / "Phone"
    phone_dir.mkdir(parents=True)
    (phone_dir / "device.json").write_text(
        '{"型号":"SM-S9180","IMEI1":"111111111111111"}',
        encoding="utf-8",
    )

    fields = parse_device_base(str(tmp_path / "data"), "JC02")

    assert fields["model"] == "SM-S9180"
    assert fields["device_name"] == "SM-S9180"
    assert fields["imei1"] == "111111111111111"
