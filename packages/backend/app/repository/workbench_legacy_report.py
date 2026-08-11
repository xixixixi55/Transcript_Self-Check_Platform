"""Shape validation for the bounded Legacy InspectionReport DTO."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_errors import WorkbenchPersistenceError


def validate_legacy_report(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    _strings(value, ("title", "document_number"))
    if "case_number" in value and value["case_number"] is not None:
        _string(value["case_number"])
    introduction = _mapping(value, "introduction")
    if "entrust_unit_prefix" in introduction:
        _string(introduction["entrust_unit_prefix"])
    _strings(introduction, (
        "entrust_unit", "entrust_time", "case_summary", "inspection_requirement",
        "inspection_time_range", "inspection_place",
    ))
    _strings_list(introduction, "entrust_persons")
    _evidence_list(introduction)
    _inspectors(introduction, "inspectors", ("name", "unit", "badge_number"))
    if "inspector_snapshots" in introduction:
        _inspectors(introduction, "inspector_snapshots", ("name", "unit", "police_number"))

    inspection = _mapping(value, "inspection")
    _strings(inspection, ("method", "hardware_device"))
    _software_tools(inspection)
    _process_steps(inspection)
    result = _mapping(inspection, "result")
    _strings(result, (
        "evidence_number", "software_name", "software_version", "data_summary",
        "rar_filename", "md5_hash", "file_size",
    ))
    if "primary_software" in inspection and inspection["primary_software"] is not None:
        _primary_software(inspection["primary_software"])

    attachments = _mapping(value, "attachments")
    _table_data(attachments, "extract_list")
    _strings_list(attachments, "photo_ids")
    if "photo_groups" in attachments and attachments["photo_groups"] is not None:
        _photo_groups(attachments["photo_groups"])
    _strings(attachments, ("disc_number",))
    if "burning_date" in attachments and attachments["burning_date"] is not None:
        _string(attachments["burning_date"])
    if "disc_sequence" in attachments and attachments["disc_sequence"] is not None:
        if not isinstance(attachments["disc_sequence"], Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    return value


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    return value


def _string(value: Any) -> None:
    if not isinstance(value, str):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")


def _strings(parent: Mapping[str, Any], keys: tuple[str, ...]) -> None:
    if not set(keys).issubset(parent):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for key in keys:
        _string(parent[key])


def _strings_list(parent: Mapping[str, Any], key: str) -> None:
    value = parent.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")


def _evidence_list(introduction: Mapping[str, Any]) -> None:
    evidence = introduction.get("evidence_list")
    if not isinstance(evidence, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for item in evidence:
        if not isinstance(item, Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(item, ("id", "device_type", "evidence_number"))
        for key in ("device_name", "brand", "model", "imei1", "imei2", "serial_number", "device_type_source", "material_type", "material_type_status", "material_type_source", "material_type_diagnostic"):
            if key in item and item[key] is not None:
                _string(item[key])


def _inspectors(parent: Mapping[str, Any], key: str, required: tuple[str, ...]) -> None:
    value = parent.get(key)
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for item in value:
        if not isinstance(item, Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(item, required)


def _software_tools(inspection: Mapping[str, Any]) -> None:
    value = inspection.get("software_tools")
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for item in value:
        if not isinstance(item, Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(item, ("name", "version"))


def _process_steps(inspection: Mapping[str, Any]) -> None:
    value = inspection.get("process_steps")
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for item in value:
        if not isinstance(item, Mapping) or isinstance(item.get("step_number"), bool) or not isinstance(item.get("step_number"), int):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(item, ("content",))


def _table_data(attachments: Mapping[str, Any], key: str) -> None:
    table = _mapping(attachments, key)
    columns = table.get("columns")
    rows = table.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for column in columns:
        if not isinstance(column, Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(column, ("key", "title"))
        if "width" in column and column["width"] is not None:
            _string(column["width"])
    for row in rows:
        if not isinstance(row, Mapping) or any(not isinstance(key, str) or not isinstance(item, str) for key, item in row.items()):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")


def _photo_groups(value: Any) -> None:
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for group in value:
        if not isinstance(group, Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(group, ("material_id", "material_number", "display_text"))
        images = group.get("ordered_image_ids")
        if not isinstance(images, list) or len(images) != 2 or any(not isinstance(item, str) for item in images):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        if isinstance(group.get("source_order"), bool) or not isinstance(group.get("source_order"), int):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")


def _primary_software(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    _strings(value, ("name", "version", "display_name", "confirmation_status"))
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        _strings(candidate, ("name", "version"))
