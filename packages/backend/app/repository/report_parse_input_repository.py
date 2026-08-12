"""Layer 20: one-pass, request-scoped report Parser input snapshots."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path
from typing import Any

from .filesystem_identity_repository import normalized_directory_key, resolve_directory
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
)
from .device_field_parser import is_generic_device_label, try_parse_json
from .report_parse_input_models import (
    DependencyRecord,
    ReportParseInputError,
    ReportParseInputSnapshot,
)
from .report_parse_input_filesystem import (
    directory_entries,
    file_entries,
    file_identity,
    require_directory,
    require_regular_file,
    stable_identity,
)
from .report_parse_input_selection_repository import (
    build_evidence_directory_index,
    find_vendor_device_names,
    select_device_candidate_files,
    split_vendor_device_name,
)

_CORE_FILES = (
    "data_case_info.json", "data_device_lists.json", "data_report_info.json",
)


def build_report_parse_input_snapshot(source_dir: str) -> ReportParseInputSnapshot:
    """Read core and explicitly selected device metadata exactly once."""
    source_root = resolve_directory(source_dir)
    data_root = source_root / "data"
    require_directory(data_root)
    dependencies: dict[str, DependencyRecord] = {}
    core_payloads: dict[str, Any] = {}
    for filename in _CORE_FILES:
        path = data_root / filename
        raw = _read_dependency(path, data_root, dependencies)
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
        and all(_has_core_device_identity(row) for row in device_rows)
    )
    device_base_info: dict[str, dict[str, str]] = {}
    candidate_indexes: list[CandidateDirectoryIndex] = []
    for row in device_rows:
        evidence_number = row.get("evidence_number", "")
        candidate_files, indexes = select_device_candidate_files(
            evidence_directories.get(evidence_number, ""), data_root,
            report_format=report_format,
            include_data_files=not use_vendor_names_without_data_scan,
        )
        candidate_indexes.extend(indexes)
        payloads: list[tuple[Any, str]] = []
        for path in candidate_files:
            try:
                raw = _read_dependency(path, data_root, dependencies)
                text = raw.decode("utf-8", errors="replace")
                payloads.append((try_parse_json(text), text))
            except UnicodeError:
                continue
        device_base_info[evidence_number] = parse_device_base_payloads(
            report_format, payloads,
        )
    if len(vendor_device_names) == len(device_rows):
        vendor_names_by_key = {_vendor_name_key(name): name for name in vendor_device_names}
        explicit_names = [
            vendor_names_by_key.get(_vendor_name_key(row.get("vendor_device_name", "")))
            for row in device_rows
        ]
        used_explicit_names = {name for name in explicit_names if name}
        remaining_names = iter(
            name for name in vendor_device_names if name not in used_explicit_names
        )
        for index, row in enumerate(device_rows):
            evidence_number = row.get("evidence_number", "")
            info = device_base_info[evidence_number]
            if info.get("model") and not is_generic_device_label(info.get("model")):
                continue
            display_name = explicit_names[index] or next(remaining_names)
            brand, model = split_vendor_device_name(display_name)
            info.update({
                "device_name": display_name,
                "brand": brand,
                "model": model,
            })

    records = tuple(sorted(dependencies.values(), key=lambda item: item.relative_path.casefold()))
    return ReportParseInputSnapshot(
        source_key=normalized_directory_key(str(source_root)),
        report_format=report_format,
        case_info=parse_case_info_payload(core_payloads["data_case_info.json"]),
        device_rows=device_rows,
        report_info=parse_report_info_payload(core_payloads["data_report_info.json"]),
        evidence_directories=evidence_directories,
        device_base_info=device_base_info,
        dependencies=records,
        candidate_indexes=tuple(candidate_indexes),
        dependency_fingerprint=_fingerprint_records(records),
    )


def _candidate_file_record(path: str, data_root: Path) -> CandidateFileRecord:
    try:
        info = Path(path).stat()
        relative = Path(path).relative_to(data_root).as_posix()
    except (OSError, ValueError) as error:
        raise ReportParseInputError("报告候选目录无法读取。") from error
    return CandidateFileRecord(
        relative, int(info.st_size), int(info.st_mtime_ns), stable_identity(info),
    )


def _read_dependency(
    path: Path, data_root: Path, dependencies: dict[str, DependencyRecord],
) -> bytes:
    require_regular_file(path)
    try:
        relative = path.relative_to(data_root).as_posix()
        before = path.stat()
        with path.open("rb") as stream:
            raw = stream.read()
        after = path.stat()
    except (OSError, ValueError) as error:
        raise ReportParseInputError("报告依赖文件无法读取。") from error
    if file_identity(before) != file_identity(after):
        raise ReportParseInputError("报告依赖文件在读取期间发生变化。")
    record = DependencyRecord(
        relative_path=relative,
        size_bytes=int(after.st_size),
        modified_time_ns=int(after.st_mtime_ns),
        stable_identity=stable_identity(after),
        content_digest=hashlib.sha256(raw).hexdigest(),
    )
    dependencies[relative.casefold()] = record
    return raw


def _fingerprint_records(records: tuple[DependencyRecord, ...]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record.relative_path.casefold().encode("utf-8"))
        digest.update(f"\0{record.size_bytes}\0{record.modified_time_ns}\0".encode("ascii"))
        digest.update(record.stable_identity.encode("ascii"))
        digest.update(b"\0" + record.content_digest.encode("ascii") + b"\0")
    return digest.hexdigest()


def _has_core_device_identity(row: dict[str, str]) -> bool:
    return any(str(row.get(key) or "").strip() for key in (
        "device_type", "imei1", "imei2",
    ))


def _vendor_name_key(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


def _is_device_metadata_name(name: str) -> bool:
    stem = Path(name).stem.casefold()
    return any(marker in stem for marker in _DEVICE_FILENAME_MARKERS)


def _device_filename_priority(name: str) -> int:
    return _DEVICE_FILENAME_PRIORITY.get(name.casefold(), 10)


def _is_json(name: str) -> bool:
    return name.casefold().endswith(".json")


def _normalise_directory_name(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()

__all__ = [
    "DependencyRecord", "ReportParseInputError", "ReportParseInputSnapshot",
    "build_report_parse_input_snapshot",
]
