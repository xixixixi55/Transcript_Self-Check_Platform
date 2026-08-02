"""HTML/JSON 报告解析器测试：只使用脱敏合成 fixture。"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.device_field_parser import (
    extract_device_fields,
    extract_strong_device_fields,
    normalise_imei,
)
from app.repository.device_candidate_parser import select_best_device_candidate
from app.repository.html_parser import (
    format_inspection_time_range,
    parse_case_info,
    parse_device_base,
    parse_device_lists,
    parse_navigation,
    parse_report_info,
)
from app.repository.report_parse_input_repository import build_report_parse_input_snapshot
from app.repository.report_format_adapter import (
    ReportFormat,
    ReportFormatError,
    detect_report_format,
    extract_main_software_version,
)
from app.services.material_policy_service import enrich_report_material_types


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _case_payload():
    values = {
        "案件名称": "合成案件",
        "案件编号": "CASE-SYNTH-001",
        "采集人": "合成采集员",
        "采集单位": "合成采集单位",
        "送检人": "合成送检人",
        "送检单位": "合成送检单位",
        "案件类型": "测试案",
        "创建时间": "2026-07-13 11:55:19",
        "报告时间": "2026-07-13 15:43:21",
    }
    return {"columns": [], "contents": [{"tp": key, "ct": value} for key, value in values.items()]}


def _write_report_fixture(root, report_format="legacy", *, mixed=False, known_software=True):
    data_dir = root / "data"
    base_dir = data_dir / "JC01" / "Base"
    base_dir.mkdir(parents=True)
    _write_json(data_dir / "data_case_info.json", _case_payload())

    row = {"c1": "1", "c2": "JC01"}
    if report_format == "legacy" or mixed:
        row["c3"] = "2026-01-01 00:00:00 ~ 2026-01-01 00:01:00"
    if report_format == "new":
        row["tb2"] = [
            {"tt": "检材编号", "ct": "JC01"},
            {"tt": "IMEI1", "ct": " 111111111111111 "},
            {"tt": "IMEI2", "ct": "222222222222222"},
            {"tt": "取证时间段", "ct": "2099-01-01 00:00:00 ~ 2099-01-01 00:01:00"},
            {"tt": "检材来源", "ct": "不进入标准模型"},
        ]
    _write_json(data_dir / "data_device_lists.json", {"columns": [], "contents": [row]})

    if report_format == "legacy":
        values = ["取证报告", "产品版本：FL-901 V3.2.1"]
    elif known_software:
        values = ["取证报告", "报告生成软件：美亚手机大师-并行版 V5.1.2"]
    else:
        values = ["取证报告", "取证OS客户端 V9.9.9", "美亚阅读器 V8.8.8"]
    _write_json(
        data_dir / "data_report_info.json",
        {"config": {}, "contents": [{"value": value} for value in values]},
    )
    navigation = [{"name": "合成分类", "pid": "root", "dataTotal": 1,
                   "dataConfig": {"varName": "synthetic"}, "children": []}]
    (data_dir / "data_navigation.json").write_text(
        "; static.mypico.json.navigation = " + json.dumps(navigation, ensure_ascii=False),
        encoding="utf-8",
    )

    if report_format == "legacy":
        _write_json(
            base_dir / "device.json",
            {"设备名称": "合成手机", "设备型号": "Model-S", "IMEI1": "333333333333333",
             "IMEI2": "444444444444444", "序列号": "SN-SYNTH"},
        )
    else:
        for index in range(20):
            _write_json(
                base_dir / f"unrelated_{index}.json",
                {"序列号": f"NOISE-SERIAL-{index}", "value": "555555555555555"},
            )
        _write_json(
            base_dir / "device_table.json",
            {"rows": [
                {"c1": "设备名称", "c2": "合成新手机"},
                {"c1": "设备型号", "c2": "Model-NEW"},
                {"c1": "IMEI2", "c2": "999999999999999"},
                {"c1": "序列号", "c2": "SN-NEW"},
            ]},
        )
    return data_dir


def test_legacy_fixture_is_detected_and_parsed(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "legacy")

    assert detect_report_format(str(data_dir)) == ReportFormat.LEGACY
    info = parse_case_info(str(data_dir))
    assert info["case_name"] == "合成案件"
    assert info["case_number"] == "CASE-SYNTH-001"
    assert parse_device_lists(str(data_dir))[0]["evidence_number"] == "JC01"
    assert parse_device_lists(str(data_dir))[0]["device_name"] == "1"
    assert "2026-01-01" in parse_device_lists(str(data_dir))[0]["time_range"]
    assert "FL-901" in parse_report_info(str(data_dir))["product_version"]
    assert parse_navigation(str(data_dir))["total_items"] == 1


def test_new_fixture_uses_tb2_and_strong_device_table(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "new")

    assert detect_report_format(str(data_dir)) == ReportFormat.NEW
    device = parse_device_lists(str(data_dir))[0]
    assert device["device_name"] == ""
    assert device["imei1"] == "111111111111111"
    assert device["imei2"] == "222222222222222"
    assert device["time_range"] == ""
    fields = parse_device_base(str(data_dir), "JC01")
    assert fields == {
        "device_type": "", "device_name": "合成新手机", "brand": "", "model": "Model-NEW",
        "imei1": "", "imei2": "999999999999999", "serial_number": "SN-NEW",
    }


def test_device_metadata_table_variant_a_reads_phone_table_and_keeps_missing_imei_empty(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "legacy")
    (data_dir / "JC01" / "Base" / "device.json").unlink()
    phone_dir = data_dir / "JC01" / "Phone"
    phone_dir.mkdir()
    _write_json(phone_dir / "data_SYNTHETIC-A.json", {"rows": [
        {"c1": "检材名称", "c2": "SYNTHETIC-A-PHONE"},
        {"c1": "手机品牌", "c2": "SYNTHETIC-A-BRAND"},
        {"c1": "手机型号", "c2": "SYNTHETIC-A-MODEL"},
        {"c1": "设备类型", "c2": "手机"},
        {"c1": "IMEI", "c2": ""},
        {"c1": "IMEI2", "c2": ""},
        {"c1": "序列号", "c2": "SYNTHETIC-SERIAL-A"},
    ]})

    snapshot = build_report_parse_input_snapshot(str(tmp_path))
    fields = snapshot.device_base_info["JC01"]

    assert fields["device_name"] == "SYNTHETIC-A-PHONE"
    assert fields["brand"] == "SYNTHETIC-A-BRAND"
    assert fields["model"] == "SYNTHETIC-A-MODEL"
    assert fields["device_type"] == "手机"
    assert fields["imei1"] == ""
    assert fields["imei2"] == ""


def test_device_metadata_nested_variant_b_accepts_imei_aliases_and_ignores_identifier_noise(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "new")
    (data_dir / "JC01" / "Base" / "device_table.json").unlink()
    base_dir = data_dir / "JC01" / "Base"
    _write_json(base_dir / "data_SYNTHETIC-B.json", {"metadata": {"rows": [
        {"c1": "设备名称", "c2": "SYNTHETIC-B-PHONE"},
        {"c1": "设备品牌", "c2": "SYNTHETIC-B-BRAND"},
        {"c1": "设备型号", "c2": "SYNTHETIC-B-MODEL"},
        {"c1": "终端类型", "c2": "手机"},
        {"c1": "IMEI", "c2": "123456789012345"},
        {"c1": "IMEI 2", "c2": "543210987654321"},
        {"c1": "序列号", "c2": "SYNTHETIC-SERIAL-B"},
    ]}})
    _write_json(base_dir / "data_SYNTHETIC-B-noise.json", {"rows": [
        {"c1": "IMSI", "c2": "123456789012345"},
        {"c1": "ICCID", "c2": "1234567890123456789"},
        {"c1": "MEID", "c2": "123456789012345"},
    ]})

    fields = parse_device_base(str(data_dir), "JC01")

    assert fields["device_name"] == "SYNTHETIC-B-PHONE"
    assert fields["brand"] == "SYNTHETIC-B-BRAND"
    assert fields["model"] == "SYNTHETIC-B-MODEL"
    assert fields["device_type"] == "手机"
    assert fields["imei1"] == "123456789012345"
    assert fields["imei2"] == "543210987654321"


def test_device_type_label_variant_c_enriches_existing_name_and_imei(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "new")
    device_file = data_dir / "data_device_lists.json"
    device_data = json.loads(device_file.read_text(encoding="utf-8"))
    device_data["contents"][0]["tb2"].append({"tt": "检材类型", "ct": "手机"})
    _write_json(device_file, device_data)

    device = parse_device_lists(str(data_dir))[0]
    fields = parse_device_base(str(data_dir), "JC01")
    enriched = enrich_report_material_types({
        "introduction": {"evidence_list": [{
            "id": "JC01", "device_type": device["device_type"],
            "device_name": fields["device_name"], "imei1": device["imei1"],
            "imei2": device["imei2"],
        }]},
    })["introduction"]["evidence_list"][0]

    assert fields["device_name"] == "合成新手机"
    assert device["imei1"] == "111111111111111"
    assert device["imei2"] == "222222222222222"
    assert enriched["material_type"] == "phone"
    assert enriched["material_type_status"] == "confirmed_by_report"


def test_mixed_format_prefers_tb2_and_new_device_rules(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "new", mixed=True)
    assert detect_report_format(str(data_dir)) == ReportFormat.NEW
    device = parse_device_lists(str(data_dir))[0]
    assert device["imei1"] == "111111111111111"
    assert device["time_range"].startswith("2026-01-01")


def test_unsupported_core_structure_is_explicit(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "new", known_software=False)
    device_file = data_dir / "data_device_lists.json"
    _write_json(device_file, {"columns": [], "contents": [{"c1": "1", "c2": "JC01"}]})
    assert detect_report_format(str(data_dir)) == ReportFormat.UNSUPPORTED
    with pytest.raises(ReportFormatError):
        parse_device_lists(str(data_dir))


def test_inspection_time_uses_case_start_and_end_only():
    assert format_inspection_time_range(
        "2026-07-13 11:55:19", "2026-07-13 15:43:21"
    ) == "2026年7月13日11点55分至2026年7月13日15点43分"
    assert format_inspection_time_range("", "2026-07-13 15:43:21") == ""
    assert format_inspection_time_range("bad", "2026-07-13 15:43:21") == ""


def test_extract_device_fields_supports_confirmed_aliases_and_tables():
    assert extract_device_fields({"device_type": "iPhone"}, "")["device_type"] == "iPhone"
    assert extract_device_fields({"model": "iPhone"}, "")["device_type"] == ""
    assert extract_device_fields({"设备型号": "Model-A"}, "")["model"] == "Model-A"
    info_content = {"rows": [{"信息": "设备型号", "内容": "Model-B"}]}
    assert extract_device_fields(info_content, "")["model"] == "Model-B"
    c1_c2 = {"rows": [{"c1": "序列号", "c2": "SN-C1C2"}]}
    assert extract_device_fields(c1_c2, "")["serial_number"] == "SN-C1C2"
    tt_ct = {"rows": [{"tt": "设备型号", "ct": "Model-TT"}]}
    assert extract_device_fields(tt_ct, "")["model"] == ""
    assert extract_device_fields(tt_ct, "", allow_tt_ct=True)["model"] == "Model-TT"
    generic = extract_device_fields({"设备名称": "手机"}, "")
    assert generic["model"] == ""


def test_device_field_normalization_keeps_empty_candidates_safe_and_identifiers_distinct():
    fields = extract_device_fields({"rows": [
        {"c1": "IMEI", "c2": ""},
        {"c1": "IMEI\n1", "c2": "123 456 789 012 345"},
        {"c1": "IMEI：2", "c2": "543210987654321"},
        {"c1": "IMSI", "c2": "999999999999999"},
        {"c1": "ICCID", "c2": "999999999999999"},
        {"c1": "MEID", "c2": "999999999999999"},
    ]}, "")
    text_only = extract_device_fields({}, "IMEI/MEID：123456789012345")

    assert fields["imei1"] == "123456789012345"
    assert fields["imei2"] == "543210987654321"
    assert text_only["imei1"] == ""


def test_strong_tt_ct_device_table_is_accepted_only_as_a_table():
    payload = {"rows": [
        {"tt": "设备名称", "ct": "合成TT手机"},
        {"tt": "设备型号", "ct": "Model-TT"},
        {"tt": "序列号", "ct": "SN-TT"},
    ]}
    fields = extract_strong_device_fields(payload, allow_tt_ct=True)
    assert fields["device_name"] == "合成TT手机"
    assert fields["model"] == "Model-TT"
    assert fields["serial_number"] == "SN-TT"


def test_main_software_version_requires_semantic_record():
    assert extract_main_software_version([{
        "value": "该报告采用【手机大师NEXT（FL-901 手机取证塔V5.1.2）】生成。"
    }]) == ""
    assert extract_main_software_version([{"value": "美亚阅读器 V8.8.8"}]) == ""


def test_strong_device_table_rejects_single_business_field():
    payload = {"rows": [{"c1": "序列号", "c2": "ONLY-SERIAL"}]}
    assert not any(extract_strong_device_fields(payload).values())


def test_main_software_version_accepts_explicit_name_and_version():
    value = "\u62a5\u544a\u751f\u6210\u8f6f\u4ef6：\u7f8e\u4e9a\u624b\u673a\u5927\u5e08-\u5e76\u884c\u7248 V5.1.2"
    assert extract_main_software_version([{"value": value}]) == "V5.1.2"


def test_parse_device_base_keeps_legacy_base_and_phone_compatibility(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(data_dir / "data_case_info.json", {"contents": []})
    _write_json(data_dir / "data_device_lists.json", {
        "contents": [{"c1": "\u5408\u6210\u624b\u673a", "c2": "JC01", "c3": "2026-01-01 00:00:00"}],
    })
    _write_json(data_dir / "data_report_info.json", {
        "contents": [{"value": "\u4ea7\u54c1\u7248\u672c：FL-901 V3.2.1"}],
    })
    base_dir = data_dir / "JC01" / "Base"
    base_dir.mkdir(parents=True)
    (base_dir / "device.json").write_text(
        '{"设备名称":"合成手机","型号":"Model-BASE","IMEI1":"123456789012345",'
        '"IMEI2":"543210987654321","序列号":"SN-BASE"}', encoding="utf-8"
    )
    fields = parse_device_base(str(data_dir), "JC01")
    assert fields["model"] == "Model-BASE"
    assert fields["imei1"] == "123456789012345"

    phone_dir = data_dir / "JC02" / "Phone"
    phone_dir.mkdir(parents=True)
    (phone_dir / "device.json").write_text(
        '{"型号":"Model-PHONE","IMEI1":"111111111111111"}', encoding="utf-8"
    )
    phone_fields = parse_device_base(str(data_dir), "JC02")
    assert phone_fields["model"] == "Model-PHONE"
    assert phone_fields["imei1"] == "111111111111111"


def test_parse_device_base_reads_vendor_named_base_metadata(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "legacy")
    base_dir = data_dir / "JC01" / "Base"
    (base_dir / "device.json").unlink()
    (base_dir / "base_info.json").write_text(
        '{"设备名称":"手机","设备型号":"Vendor-Model-01",'
        '"IMEI1":"123456789012345"}', encoding="utf-8",
    )
    fields = parse_device_base(str(data_dir), "JC01")
    assert fields["model"] == "Vendor-Model-01"


@pytest.mark.parametrize("tb2", [[], {}, [{"tt": "\u8bbe\u5907\u578b\u53f7", "ct": "Model"}],
                                   [{"tt": ["\u8bbe\u5907\u578b\u53f7"], "ct": "Model"}],
                                   [{"tt": "\u672a\u77e5\u5b57\u6bb5", "ct": "value"}]])
def test_invalid_tb2_shapes_do_not_trigger_new_format(tmp_path, tb2):
    data_dir = _write_report_fixture(tmp_path, "new")
    device_data = json.loads((data_dir / "data_device_lists.json").read_text(encoding="utf-8"))
    device_data["contents"][0]["tb2"] = tb2
    (data_dir / "data_device_lists.json").write_text(
        json.dumps(device_data, ensure_ascii=False), encoding="utf-8"
    )
    expected = ReportFormat.NEW if tb2 == [{"tt": "\u8bbe\u5907\u578b\u53f7", "ct": "Model"}] else ReportFormat.UNSUPPORTED
    assert detect_report_format(str(data_dir)) == expected


def test_missing_core_files_are_reported_explicitly(tmp_path):
    with pytest.raises(ReportFormatError):
        detect_report_format(str(tmp_path))


def test_mixed_invalid_new_features_fall_back_to_legacy(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "legacy")
    device_data = json.loads((data_dir / "data_device_lists.json").read_text(encoding="utf-8"))
    device_data["contents"][0]["tb2"] = [{"tt": "\u672a\u77e5\u5b57\u6bb5", "ct": "value"}]
    (data_dir / "data_device_lists.json").write_text(
        json.dumps(device_data, ensure_ascii=False), encoding="utf-8"
    )
    assert detect_report_format(str(data_dir)) == ReportFormat.LEGACY


def _legacy_c1_is_retained_as_device_name_legacy_definition():
    payload = {"contents": [{"c1": "\u5408\u6210\u8bbe\u5907", "c2": "JC01", "c3": "old"}]}
    assert extract_device_fields(payload["contents"], "")["device_name"] == "\u5408\u8bbe\u5907"


def _candidate_rows(structure, values):
    key_name = "tt" if structure == "ttct" else "c1"
    value_name = "ct" if structure == "ttct" else "c2"
    return {"rows": [{key_name: key, value_name: value} for key, value in values.items()]}


def test_device_candidate_does_not_merge_across_files_or_branches():
    payloads = [
        _candidate_rows("c1c2", {"\u8bbe\u5907\u540d\u79f0": "Name", "\u8bbe\u5907\u578b\u53f7": "Model"}),
        _candidate_rows("c1c2", {"\u5e8f\u5217\u53f7": "Serial", "IMEI1": "123456789012345"}),
        {"left": _candidate_rows("c1c2", {"\u8bbe\u5907\u540d\u79f0": "Name", "\u8bbe\u5907\u578b\u53f7": "Model"}),
         "right": _candidate_rows("c1c2", {"\u5e8f\u5217\u53f7": "Serial", "IMEI1": "123456789012345"})},
    ]
    assert not any(select_best_device_candidate(payloads, allow_tt_ct=False).values())


def test_device_candidate_uses_highest_score_and_requires_identity():
    low = _candidate_rows("c1c2", {
        "\u8bbe\u5907\u540d\u79f0": "Low Name", "\u8bbe\u5907\u578b\u53f7": "Low Model", "\u5e8f\u5217\u53f7": "Low Serial",
    })
    high = _candidate_rows("c1c2", {
        "\u8bbe\u5907\u540d\u79f0": "High Name", "\u8bbe\u5907\u578b\u53f7": "High Model", "\u5e8f\u5217\u53f7": "High Serial",
        "IMEI1": "123456789012345",
    })
    selected = select_best_device_candidate([low, high], allow_tt_ct=False)
    assert selected["model"] == "High Model"
    assert not any(select_best_device_candidate([_candidate_rows("c1c2", {
        "IMEI1": "123456789012345", "IMEI2": "543210987654321", "\u8bbe\u5907\u578b\u53f7": "",
    })], allow_tt_ct=False).values())


def test_same_score_candidates_with_conflict_are_blank_and_same_values_are_stable():
    first = _candidate_rows("c1c2", {"\u8bbe\u5907\u578b\u53f7": "Model-A", "\u5e8f\u5217\u53f7": "SN-A", "IMEI1": "123456789012345"})
    same = _candidate_rows("c1c2", {"\u8bbe\u5907\u578b\u53f7": "Model-A", "\u5e8f\u5217\u53f7": "SN-A", "IMEI1": "123456789012345"})
    conflict = _candidate_rows("c1c2", {"\u8bbe\u5907\u578b\u53f7": "Model-B", "\u5e8f\u5217\u53f7": "SN-B", "IMEI1": "123456789012345"})
    assert select_best_device_candidate([first, same], allow_tt_ct=False)["model"] == "Model-A"
    assert not any(select_best_device_candidate([first, conflict], allow_tt_ct=False).values())
    assert not any(select_best_device_candidate([conflict, first], allow_tt_ct=False).values())


def test_tt_ct_candidate_is_scoped_to_an_explicit_device_table():
    payload = _candidate_rows("ttct", {
        "\u8bbe\u5907\u540d\u79f0": "TT Phone", "\u8bbe\u5907\u578b\u53f7": "TT-Model", "\u5e8f\u5217\u53f7": "TT-SN",
    })
    fields = select_best_device_candidate([payload], allow_tt_ct=True)
    assert fields["device_name"] == "TT Phone"
    assert fields["model"] == "TT-Model"
    assert fields["serial_number"] == "TT-SN"


def test_imei_cleanup_rejects_placeholders_and_invalid_lengths():
    assert normalise_imei("123 456-789·012345") == "123456789012345"
    assert normalise_imei("unknown") == ""
    assert normalise_imei("12345678901234") == ""
    assert normalise_imei(["123456789012345"]) == ""


def test_device_base_uses_only_named_directory_and_normalized_match(tmp_path):
    data_dir = _write_report_fixture(tmp_path, "new")
    named = data_dir / "JC01"
    normalized_name = data_dir / " JC01 "
    named.rename(normalized_name)
    unrelated = data_dir / "AAA"
    unrelated_base = unrelated / "Base"
    unrelated_base.mkdir(parents=True)
    _write_json(unrelated_base / "device.json", {
        "\u8bbe\u5907\u540d\u79f0": "Wrong", "\u8bbe\u5907\u578b\u53f7": "Wrong-Model", "\u5e8f\u5217\u53f7": "Wrong-SN",
        "IMEI1": "999999999999999",
    })
    assert not any(parse_device_base(str(data_dir), "MISSING").values())
    fields = parse_device_base(str(data_dir), "JC01")
    assert fields["model"] == "Model-NEW"
    assert fields["serial_number"] == "SN-NEW"


def test_main_software_version_conflicts_and_incomplete_records_stay_blank():
    assert extract_main_software_version([
        {"value": "\u4e3b\u53d6\u8bc1\u8f6f\u4ef6：\u7f8e\u4e9a\u624b\u673a\u5927\u5e08 V5.1.2"},
        {"value": "\u4e3b\u53d6\u8bc1\u8f6f\u4ef6：\u7f8e\u4e9a\u624b\u673a\u5927\u5e08 V5.2.0"},
    ]) == ""
    assert extract_main_software_version([{"value": "\u4e3b\u53d6\u8bc1\u8f6f\u4ef6：\u7f8e\u4e9a\u624b\u673a\u5927\u5e08"}]) == ""
    assert extract_main_software_version([{"value": "\u4e3b\u53d6\u8bc1\u8f6f\u4ef6 V5.1.2"}]) == ""
    assert extract_main_software_version([{"value": "\u5347\u7ea7\u5de5\u5177 V9.9.9"}]) == ""
