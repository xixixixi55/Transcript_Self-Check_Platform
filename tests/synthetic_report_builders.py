"""Shared synthetic builders for report/template tests."""

import json
from pathlib import Path


def build_ordered_report():
    return {
        "title": "SYNTHETIC/TEST Record",
        "document_number": "SYNTHETIC-DOC",
        "field_states": {"evidence.SYNTHETIC-10.model": {"source": "user"}},
        "introduction": {
            "entrust_unit": "SYNTHETIC-UNIT",
            "entrust_persons": [],
            "entrust_time": "",
            "case_summary": "SYNTHETIC",
            "inspection_requirement": "",
            "inspection_time_range": "",
            "inspection_place": "SYNTHETIC-PLACE",
            "evidence_list": [
                {
                    "id": "material-10",
                    "evidence_id": "SYNTHETIC-EVIDENCE-10",
                    "device_type": "SYNTHETIC-TEN",
                    "evidence_number": "SYNTHETIC-10",
                    "review_color": "SYNTHETIC-UI-COLOR",
                },
                {
                    "id": "material-2",
                    "evidence_id": "SYNTHETIC-EVIDENCE-2",
                    "device_type": "SYNTHETIC-TWO",
                    "evidence_number": "SYNTHETIC-2",
                    "review_source": "SYNTHETIC-UI-SOURCE",
                },
            ],
            "inspectors": [{
                "name": "SYNTHETIC-LIBRARY-STALE",
                "unit": "SYNTHETIC",
                "badge_number": "000",
            }],
            "inspector_snapshots": [
                {
                    "snapshot_id": "SYNTHETIC-SNAPSHOT-B",
                    "name": "SYNTHETIC-B",
                    "unit": "SYNTHETIC-UNIT",
                    "police_number": "SYNTHETIC-002",
                    "source_version": "SYNTHETIC-UI-SOURCE",
                },
                {
                    "snapshot_id": "SYNTHETIC-SNAPSHOT-A",
                    "name": "SYNTHETIC-A",
                    "unit": "SYNTHETIC-UNIT",
                    "police_number": "SYNTHETIC-001",
                },
            ],
        },
        "inspection": {
            "method": "SYNTHETIC-METHOD",
            "hardware_device": "SYNTHETIC-HARDWARE",
            "primary_software": {
                "name": "SYNTHETIC-TOOL",
                "version": "1.0",
                "confirmation_status": "confirmed_by_report",
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.12"},
            ],
            "process_steps": [],
            "result": {
                "evidence_number": "SYNTHETIC-2、SYNTHETIC-10",
                "software_name": "SYNTHETIC-TOOL",
                "software_version": "1.0",
                "data_summary": "SYNTHETIC",
                "rar_filename": "SYNTHETIC.rar",
                "md5_hash": "",
                "file_size": "",
            },
        },
        "attachments": {
            "photo_ids": ["photo-2a", "photo-2b", "photo-10a", "photo-10b"],
            "disc_number": "GP20260706-01",
            "extract_list": {"columns": [], "rows": []},
            "photo_groups": [
                {
                    "material_id": "material-2",
                    "material_number": "SYNTHETIC-2",
                    "display_text": "检材SYNTHETIC-2照片",
                    "ordered_image_ids": ["photo-2a", "photo-2b"],
                    "source_order": 1,
                },
                {
                    "material_id": "material-10",
                    "material_number": "SYNTHETIC-10",
                    "display_text": "检材SYNTHETIC-10照片",
                    "ordered_image_ids": ["photo-10a", "photo-10b"],
                    "source_order": 2,
                },
            ],
        },
    }


def build_archive_manifest(count=3):
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


def write_synthetic_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def build_parse_cache_report_tree(root: Path) -> tuple[Path, Path, Path]:
    data = root / "data"
    base = data / "JC-SYN-01" / "Base"
    base.mkdir(parents=True)
    write_synthetic_json(data / "data_case_info.json", {"contents": [
        {"tp": "案件名称", "ct": "SYNTHETIC-CACHE"},
        {"tp": "案件编号", "ct": "SYNTHETIC-CACHE-001"},
    ]})
    write_synthetic_json(data / "data_device_lists.json", {"contents": [{
        "c1": "SYNTHETIC-设备",
        "c2": "JC-SYN-01",
        "tb2": [{"tt": "检材编号", "ct": "JC-SYN-01"}],
    }]})
    write_synthetic_json(data / "data_report_info.json", {"contents": [
        {"value": "报告生成软件：SYNTHETIC-Tool V1.0.0"},
    ]})
    candidate = base / "device_table.json"
    write_synthetic_json(candidate, {"rows": [
        {"c1": "设备名称", "c2": "SYNTHETIC-PHONE"},
        {"c1": "设备型号", "c2": "SYNTHETIC-MODEL"},
        {"c1": "序列号", "c2": "SYNTHETIC-SN"},
    ]})
    unrelated = base / "unrelated.json"
    unrelated.write_text("SYNTHETIC-NOISE", encoding="utf-8")
    attachment = base / "attachment.html"
    attachment.write_text("SYNTHETIC-HTML", encoding="utf-8")
    return data, candidate, unrelated
