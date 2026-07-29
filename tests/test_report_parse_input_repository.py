"""SYNTHETIC tests for the one-pass report Parser input snapshot."""

import json
import os
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.html_parser import (  # noqa: E402
    parse_case_info,
    parse_device_base,
    parse_device_lists,
    parse_report_info,
)
from app.repository.report_parse_input_repository import (  # noqa: E402
    build_report_parse_input_snapshot,
)
from app.services.report_parser_service import _build_report, parse_report  # noqa: E402


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_snapshot_fixture(root: Path, *, legacy: bool = False) -> Path:
    data = root / "data"
    data.mkdir()
    _write_json(data / "data_case_info.json", {"contents": [
        {"tp": "案件名称", "ct": "SYNTHETIC-案件"},
        {"tp": "案件编号", "ct": "SYNTHETIC-CASE-001"},
        {"tp": "创建时间", "ct": "2026-07-13 11:55:19"},
        {"tp": "报告时间", "ct": "2026-07-13 15:43:21"},
    ]})
    rows = []
    for index in range(1, 4):
        row = {"c1": str(index), "c2": f"JC-SYN-{index:02d}"}
        if legacy:
            row["c1"] = f"SYNTHETIC-设备-{index}"
            row["c3"] = "2026-01-01 00:00:00 ~ 2026-01-01 00:01:00"
        else:
            row["tb2"] = [
                {"tt": "检材编号", "ct": f"JC-SYN-{index:02d}"},
                {"tt": "IMEI1", "ct": f"11111111111111{index}"},
                {"tt": "取证时间段", "ct": "2026-01-01 00:00:00 ~ 2026-01-01 00:01:00"},
            ]
        rows.append(row)
        base = data / f"JC-SYN-{index:02d}" / "Base"
        base.mkdir(parents=True)
        candidate = {"rows": [
            {"c1": "设备名称", "c2": f"SYNTHETIC-手机-{index}"},
            {"c1": "设备型号", "c2": f"SYNTHETIC-MODEL-{index}"},
            {"c1": "序列号", "c2": f"SYNTHETIC-SN-{index}"},
        ]}
        if legacy:
            candidate = {
                "设备名称": f"SYNTHETIC-旧手机-{index}",
                "设备型号": f"SYNTHETIC-OLD-MODEL-{index}",
                "序列号": f"SYNTHETIC-OLD-SN-{index}",
            }
        _write_json(base / ("device.json" if legacy else "device_table.json"), candidate)
        _write_json(base / f"unrelated_{index}.json", {"value": "SYNTHETIC-NOISE"})
        (base / "attachment.html").write_text("SYNTHETIC-HTML", encoding="utf-8")
    _write_json(data / "data_device_lists.json", {"contents": rows})
    report_value = "产品版本：SYNTHETIC-Tool V3.2.1" if legacy else "报告生成软件：SYNTHETIC-Tool V5.1.2"
    _write_json(data / "data_report_info.json", {"contents": [{"value": report_value}]})
    (data / "data_navigation.json").write_text(
        "; static.mypico.json.navigation = []", encoding="utf-8",
    )
    unrelated = data / "UNRELATED-SYNTHETIC" / "Base"
    unrelated.mkdir(parents=True)
    _write_json(unrelated / "device.json", {"设备型号": "SYNTHETIC-WRONG"})
    return data


def _count_data_opens(data_root: Path):
    original_open = Path.open
    calls: Counter[str] = Counter()

    def counted_open(path: Path, *args, **kwargs):
        try:
            relative = path.relative_to(data_root).as_posix()
        except ValueError:
            relative = "outside-data"
        calls[relative] += 1
        return original_open(path, *args, **kwargs)

    return calls, counted_open


def test_snapshot_reads_core_and_selected_device_json_once(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path)
    calls, counted_open = _count_data_opens(data_root)

    with patch("pathlib.Path.open", new=counted_open):
        snapshot = build_report_parse_input_snapshot(str(tmp_path))

    assert [calls[name] for name in (
        "data_case_info.json", "data_device_lists.json", "data_report_info.json",
    )] == [1, 1, 1]
    assert calls["JC-SYN-01/Base/device_table.json"] == 1
    assert calls["JC-SYN-02/Base/device_table.json"] == 1
    assert calls["JC-SYN-03/Base/device_table.json"] == 1
    assert calls["JC-SYN-01/Base/unrelated_1.json"] == 0
    assert calls["JC-SYN-01/Base/attachment.html"] == 0
    assert calls["UNRELATED-SYNTHETIC/Base/device.json"] == 0
    assert len(snapshot.device_rows) == 3
    assert len(snapshot.evidence_directories) == 3
    assert all(not Path(item.relative_path).is_absolute() for item in snapshot.dependencies)
    assert all(str(tmp_path) not in item.relative_path for item in snapshot.dependencies)


def test_snapshot_preserves_parser_evidence_order_for_case_initialization(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path)
    rename_map = {
        "JC-SYN-01": "JC-SYN-10",
        "JC-SYN-02": "JC-SYN-2",
        "JC-SYN-03": "JC-SYN-1",
    }
    for old_name, new_name in rename_map.items():
        (data_root / old_name).rename(data_root / new_name)
    device_list_path = data_root / "data_device_lists.json"
    device_lists = json.loads(device_list_path.read_text(encoding="utf-8"))
    device_lists["contents"] = [
        {**device_lists["contents"][0], "c2": "JC-SYN-10"},
        {**device_lists["contents"][1], "c2": "JC-SYN-2"},
        {**device_lists["contents"][2], "c2": "JC-SYN-1"},
    ]
    _write_json(device_list_path, device_lists)

    snapshot = build_report_parse_input_snapshot(str(tmp_path))
    assert [row["evidence_number"] for row in snapshot.device_rows] == [
        "JC-SYN-10", "JC-SYN-2", "JC-SYN-1",
    ]
    report = _build_report(
        str(data_root), str(tmp_path), str(tmp_path / "output"),
        compress=False, input_snapshot=snapshot,
    )
    assert [item["evidence_number"] for item in report["introduction"]["evidence_list"]] == [
        "JC-SYN-10", "JC-SYN-2", "JC-SYN-1",
    ]
    assert report["inspection"]["result"]["evidence_number"] == (
        "JC-SYN-10、JC-SYN-2、JC-SYN-1"
    )


def test_snapshot_reuses_legacy_and_new_adapter_values(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path, legacy=True)
    snapshot = build_report_parse_input_snapshot(str(tmp_path))

    assert snapshot.report_format.value == "legacy"
    assert snapshot.case_info == parse_case_info(str(data_root))
    assert list(snapshot.device_rows) == parse_device_lists(str(data_root))
    assert snapshot.report_info == parse_report_info(str(data_root))
    for row in snapshot.device_rows:
        evidence_number = row["evidence_number"]
        assert snapshot.device_base_info[evidence_number] == parse_device_base(
            str(data_root), evidence_number,
        )
    assert all(record.size_bytes > 0 for record in snapshot.dependencies)
    assert all(len(record.content_digest) == 64 for record in snapshot.dependencies)
    assert len(snapshot.dependency_fingerprint) == 64


def test_snapshot_uses_vendor_display_directories_when_jc_base_is_empty(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path)
    for index in range(1, 4):
        (data_root / f"JC-SYN-{index:02d}" / "Base" / "device_table.json").unlink()
    vendor_names = (
        "SYNTHETIC-BRAND-ONE MODEL-ONE",
        "SYNTHETIC-BRAND-TWO MODEL-TWO",
        "SYNTHETIC-BRAND-THREE MODEL-THREE",
    )
    for name in vendor_names:
        (data_root / name / "Base").mkdir(parents=True)

    snapshot = build_report_parse_input_snapshot(str(tmp_path))

    assert [
        snapshot.device_base_info[f"JC-SYN-{index:02d}"]["device_name"]
        for index in range(1, 4)
    ] == sorted(vendor_names, key=str.casefold)
    assert snapshot.device_base_info["JC-SYN-01"]["brand"] == "SYNTHETIC-BRAND-ONE"
    assert snapshot.device_base_info["JC-SYN-01"]["model"] == "MODEL-ONE"


def test_legacy_snapshot_merges_split_vendor_metadata_files(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path, legacy=True)
    base_dir = data_root / "JC-SYN-01" / "Base"
    (base_dir / "device.json").write_text(
        '{"设备名称":"手机","IMEI1":"111111111111111"}',
        encoding="utf-8",
    )
    (base_dir / "base_info.json").write_text(
        '{"设备名称":"手机","设备型号":"SYNTHETIC-VENDOR-MODEL"}',
        encoding="utf-8",
    )

    snapshot = build_report_parse_input_snapshot(str(tmp_path))

    assert snapshot.device_base_info["JC-SYN-01"]["model"] == (
        "SYNTHETIC-VENDOR-MODEL"
    )


def test_snapshot_directory_index_does_not_scan_unrelated_report_root(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path)
    original_scandir = os.scandir
    scanned: list[str] = []

    def counted_scandir(path):
        scanned.append(os.path.normcase(os.fspath(path)))
        return original_scandir(path)

    with patch("app.repository.report_parse_input_filesystem.os.scandir", new=counted_scandir):
        build_report_parse_input_snapshot(str(tmp_path))

    assert not any("UNRELATED-SYNTHETIC" in path for path in scanned)
    assert sum(path.endswith("data") for path in scanned) == 1


def test_parser_uses_snapshot_dto_without_reopening_legacy_readers(tmp_path):
    _write_snapshot_fixture(tmp_path, legacy=True)
    with patch("app.services.report_parser_service.parse_case_info", side_effect=AssertionError), \
         patch("app.services.report_parser_service.parse_device_lists", side_effect=AssertionError), \
         patch("app.services.report_parser_service.parse_report_info", side_effect=AssertionError), \
         patch("app.services.report_parser_service.parse_device_base", side_effect=AssertionError), \
         patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        report = parse_report(str(tmp_path), str(tmp_path / "output"), compress=False)["report"]

    assert len(report["introduction"]["evidence_list"]) == 3
    assert report["introduction"]["evidence_list"][0]["model"] == "SYNTHETIC-OLD-MODEL-1"


def test_snapshot_report_matches_existing_report_assembly(tmp_path):
    data_root = _write_snapshot_fixture(tmp_path, legacy=True)
    snapshot = build_report_parse_input_snapshot(str(tmp_path))
    with patch("app.services.report_parser_service.detect_winrar_version", return_value=None):
        before = _build_report(str(data_root), str(tmp_path), str(tmp_path / "output"), compress=False)
        after = _build_report(
            str(data_root), str(tmp_path), str(tmp_path / "output"), compress=False,
            input_snapshot=snapshot,
        )
    assert after == before
