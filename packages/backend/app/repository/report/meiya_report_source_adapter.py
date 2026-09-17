"""Layer 20：美亚 legacy/new 报告家族的来源适配器。"""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path
from typing import Any

from ..source.filesystem_identity_repository import normalized_directory_key
from .device_field_parser import is_generic_device_label, try_parse_json
from .html_parser import (
    parse_case_info_payload,
    parse_device_base_payloads,
    parse_device_lists_payload,
    parse_report_info_payload,
)
from .json_loader import parse_js_json_content
from .report_format_adapter import (
    ReportFormat,
    detect_report_format_from_payloads,
    require_supported_report_format,
)
from .report_parse_input_filesystem import (
    directory_entries,
    fingerprint_dependencies,
    read_dependency,
    require_directory,
)
from .report_parse_input_models import (
    DependencyRecord,
    ReportParseInputError,
    ReportParseInputSnapshot,
)
from .report_parse_input_selection_repository import (
    build_evidence_directory_index,
    find_vendor_device_names,
    navigation_device_candidate_names,
    select_device_candidate_files,
    split_vendor_device_name,
)
from .report_source_adapter import (
    ReportAdapterDetectionError,
    ReportAdapterMatch,
)

MEIYA_ADAPTER_VERSION = "1.1.0"
MEIYA_LEGACY_ADAPTER_ID = "meiya-legacy-v1"
MEIYA_NEW_ADAPTER_ID = "meiya-new-v1"
_CORE_FILES = (
    "data_case_info.json", "data_device_lists.json", "data_report_info.json",
)


class MeiyaReportSourceAdapter:
    family_id = "meiya-html-v1"
    supported_adapter_ids = (MEIYA_LEGACY_ADAPTER_ID, MEIYA_NEW_ADAPTER_ID)
    snapshot_before_inflight = False

    def matches(self, source_root: Path) -> bool:
        data_root = source_root / "data"
        return data_root.is_dir() and all(
            (data_root / filename).is_file() for filename in _CORE_FILES
        )

    def detect(self, source_root: Path) -> ReportAdapterMatch:
        try:
            report_format = require_supported_report_format(str(source_root / "data"))
        except ValueError as error:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_STRUCTURE_INVALID") from error
        adapter_id = _adapter_id(report_format)
        return ReportAdapterMatch(
            adapter_id=adapter_id,
            adapter_version=MEIYA_ADAPTER_VERSION,
            report_format=report_format,
            structure_fingerprint=_structure_fingerprint(adapter_id),
        )

    def build_snapshot(self, source_root: Path) -> ReportParseInputSnapshot:
        data_root = source_root / "data"
        require_directory(data_root)
        dependencies: dict[str, DependencyRecord] = {}
        core_payloads: dict[str, Any] = {}
        for filename in _CORE_FILES:
            raw = read_dependency(data_root / filename, data_root, dependencies)
            core_payloads[filename] = parse_js_json_content(
                raw.decode("utf-8-sig"), filename,
            )

        report_format = detect_report_format_from_payloads(
            core_payloads[_CORE_FILES[0]],
            core_payloads[_CORE_FILES[1]],
            core_payloads[_CORE_FILES[2]],
        )
        if report_format == ReportFormat.UNSUPPORTED:
            raise ReportParseInputError("报告格式不受支持。")
        device_rows = tuple(parse_device_lists_payload(
            core_payloads["data_device_lists.json"], report_format,
        ))
        root_entries = directory_entries(data_root)
        evidence_numbers = [row.get("evidence_number", "") for row in device_rows]
        evidence_directories = build_evidence_directory_index(
            evidence_numbers, root_entries,
        )
        vendor_device_names = find_vendor_device_names(
            evidence_numbers, root_entries,
        )
        use_vendor_names_without_data_scan = (
            len(vendor_device_names) == len(device_rows)
            and all(_has_complete_device_fields(row) for row in device_rows)
        )
        navigation_candidates: dict[str, str] = {}
        if report_format == ReportFormat.NEW and not use_vendor_names_without_data_scan:
            try:
                navigation_raw = read_dependency(
                    data_root / "data_navigation.json", data_root, dependencies,
                )
            except ReportParseInputError:
                pass
            else:
                navigation_candidates = navigation_device_candidate_names(
                    navigation_raw.decode("utf-8-sig", errors="replace"),
                    device_rows,
                )

        device_base_info: dict[str, dict[str, str]] = {}
        for row in device_rows:
            evidence_number = row.get("evidence_number", "")
            candidate_files = select_device_candidate_files(
                evidence_directories.get(evidence_number, ""),
                report_format=report_format,
                include_data_files=not use_vendor_names_without_data_scan,
                preferred_data_filename=navigation_candidates.get(evidence_number, ""),
            )
            payloads: list[tuple[Any, str]] = []
            for path in candidate_files:
                raw = read_dependency(path, data_root, dependencies)
                text = raw.decode("utf-8", errors="replace")
                payloads.append((try_parse_json(text), text))
            device_base_info[evidence_number] = parse_device_base_payloads(
                report_format, payloads,
            )
        _apply_vendor_display_names(
            device_rows, device_base_info, vendor_device_names,
        )

        adapter_id = _adapter_id(report_format)
        structure_fingerprint = _structure_fingerprint(adapter_id)
        records = tuple(sorted(
            dependencies.values(), key=lambda item: item.relative_path.casefold(),
        ))
        return ReportParseInputSnapshot(
            source_key=normalized_directory_key(str(source_root)),
            report_format=report_format,
            adapter_id=adapter_id,
            adapter_version=MEIYA_ADAPTER_VERSION,
            structure_fingerprint=structure_fingerprint,
            case_info=parse_case_info_payload(core_payloads["data_case_info.json"]),
            device_rows=device_rows,
            report_info=parse_report_info_payload(core_payloads["data_report_info.json"]),
            case_source_file="data/data_case_info.json",
            report_source_file="data/data_report_info.json",
            device_source_files={
                row.get("evidence_number", ""): "data/data_device_lists.json"
                for row in device_rows if row.get("evidence_number")
            },
            evidence_directories=evidence_directories,
            device_base_info=device_base_info,
            dependencies=records,
            dependency_fingerprint=fingerprint_dependencies(
                records, adapter_id, MEIYA_ADAPTER_VERSION, structure_fingerprint,
            ),
            parsed_files=(
                "data_case_info.json", "data_device_lists.json",
                "data_report_info.json", "data_navigation.json",
            ),
        )


def _adapter_id(report_format: ReportFormat) -> str:
    if report_format == ReportFormat.LEGACY:
        return MEIYA_LEGACY_ADAPTER_ID
    if report_format == ReportFormat.NEW:
        return MEIYA_NEW_ADAPTER_ID
    raise ReportParseInputError("报告格式不受支持。")


def _structure_fingerprint(adapter_id: str) -> str:
    return hashlib.sha256(adapter_id.encode("ascii")).hexdigest()


def _has_complete_device_fields(row: dict[str, str]) -> bool:
    return all(str(row.get(key) or "").strip() for key in (
        "device_type", "imei1", "imei2", "serial_number",
    ))


def _vendor_name_key(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


def _apply_vendor_display_names(
    device_rows: tuple[dict[str, str], ...],
    device_base_info: dict[str, dict[str, str]],
    vendor_device_names: list[str],
) -> None:
    if len(vendor_device_names) != len(device_rows):
        return
    vendor_names_by_key = {
        _vendor_name_key(name): name for name in vendor_device_names
    }
    explicit_names = [
        vendor_names_by_key.get(_vendor_name_key(row.get("vendor_device_name", "")))
        for row in device_rows
    ]
    used_explicit_names = {name for name in explicit_names if name}
    remaining_names = iter(
        name for name in vendor_device_names if name not in used_explicit_names
    )
    for index, row in enumerate(device_rows):
        info = device_base_info[row.get("evidence_number", "")]
        if info.get("model") and not is_generic_device_label(info.get("model")):
            continue
        display_name = explicit_names[index] or next(remaining_names)
        brand, model = split_vendor_device_name(display_name)
        info.update({"device_name": display_name, "brand": brand, "model": model})


MEIYA_REPORT_SOURCE_ADAPTER = MeiyaReportSourceAdapter()

__all__ = [
    "MEIYA_ADAPTER_VERSION", "MEIYA_LEGACY_ADAPTER_ID",
    "MEIYA_NEW_ADAPTER_ID", "MEIYA_REPORT_SOURCE_ADAPTER",
    "MeiyaReportSourceAdapter",
]
