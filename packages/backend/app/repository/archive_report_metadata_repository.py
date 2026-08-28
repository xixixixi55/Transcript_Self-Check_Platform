"""将已验证归档分卷投影到旧版报告 DTO 的可信映射。"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

from .workbench_errors import WorkbenchPersistenceError
from .workbench_database import WorkbenchDatabase
from .workbench_repository_helpers import json_text
from .hash_algorithm_repository import manifest_part_business_hash


_VERIFIED_RESULT_KEYS = ("rar_filename", "md5_hash", "file_size", "hash_algorithm")


def apply_verified_archive_result(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
    attachment_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """返回已填入经验证归档元数据的报告。

    调用方必须已验证 Manifest 及其物理文件。此辅助函数仅执行稳定的旧版 DTO 投影，
    绝不向报告添加 Manifest 标识符或文件系统详情。可选附件投影由服务层准备，
    并在同一草稿事务中提交。
    """
    fields = verified_archive_result_fields(manifest)
    result = copy.deepcopy(dict(report))
    inspection = result.get("inspection")
    if not isinstance(inspection, dict):
        inspection = {}
        result["inspection"] = inspection
    inspection_result = inspection.get("result")
    if not isinstance(inspection_result, dict):
        inspection_result = {}
        inspection["result"] = inspection_result
    inspection_result.update(fields)
    if attachment_projection is not None:
        _apply_verified_archive_attachments(result, attachment_projection)
    return result


def verified_archive_result_fields(manifest: Mapping[str, Any]) -> dict[str, str]:
    """根据有序 Manifest 分卷构建现有稳定字符串契约。"""
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    values: dict[str, list[str]] = {"rar_filename": [], "md5_hash": [], "file_size": []}
    algorithms: set[str] = set()
    for part in parts:
        if not isinstance(part, Mapping):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
        values["rar_filename"].append(_required_text(part, "filename"))
        try:
            algorithm, digest = manifest_part_business_hash(part)
        except ValueError as error:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED") from error
        algorithms.add(algorithm)
        values["md5_hash"].append(digest.upper())
        size = part.get("size_bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
        values["file_size"].append(str(size))
    if len(algorithms) != 1:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    return {
        **{key: "、".join(items) for key, items in values.items()},
        "hash_algorithm": algorithms.pop(),
    }


def preserve_verified_archive_projection(
    report: Mapping[str, Any], verified_report: Mapping[str, Any],
) -> dict[str, Any]:
    """重定基编辑器保存，同时不丢失可信归档完成字段。"""
    result = copy.deepcopy(dict(report))
    verified_inspection = verified_report.get("inspection")
    verified_result = (
        verified_inspection.get("result")
        if isinstance(verified_inspection, Mapping) else None
    )
    if isinstance(verified_result, Mapping):
        inspection = result.setdefault("inspection", {})
        if not isinstance(inspection, dict):
            inspection = {}
            result["inspection"] = inspection
        target = inspection.setdefault("result", {})
        if not isinstance(target, dict):
            target = {}
            inspection["result"] = target
        for key in _VERIFIED_RESULT_KEYS:
            value = verified_result.get(key)
            if isinstance(value, str) and value:
                target[key] = value
    verified_attachments = verified_report.get("attachments")
    extract_list = (
        verified_attachments.get("extract_list")
        if isinstance(verified_attachments, Mapping) else None
    )
    if isinstance(extract_list, Mapping):
        attachments = result.setdefault("attachments", {})
        if not isinstance(attachments, dict):
            attachments = {}
            result["attachments"] = attachments
        attachments["extract_list"] = copy.deepcopy(dict(extract_list))
    return result


def is_archive_completion_revision(
    database: WorkbenchDatabase, current: Mapping[str, Any], expected_revision: int,
) -> bool:
    """标识经验证完成操作写入的唯一草稿修订版。"""
    if (
        current.get("lifecycle") != "archive_verified"
        or int(current.get("revision", -1)) != expected_revision + 1
        or not current.get("updated_at")
    ):
        return False
    with database.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM archive_publish_intents WHERE case_id=? "
            "AND deployment_instance_id=? AND phase='verified' "
            "AND publication_status='verified' AND updated_at=? LIMIT 1",
            (
                current.get("case_id"), database.deployment_instance_id,
                current.get("updated_at"),
            ),
        ).fetchone()
    return row is not None


def update_verified_draft(
    connection: Any, draft: Mapping[str, Any], intent: Mapping[str, Any],
    case_id: str, expected_revision: int, now: str,
    attachment_projection: Mapping[str, Any],
) -> None:
    report = apply_verified_archive_result(
        json.loads(draft["report_json"]),
        json.loads(intent["public_manifest_json"]),
        attachment_projection,
    )
    updated = connection.execute(
        "UPDATE case_drafts SET report_json = ?, lifecycle = 'archive_verified', "
        "revision = revision + 1, updated_at = ? "
        "WHERE case_id = ? AND revision = ? AND lifecycle IN "
        "('archive_queued', 'archiving', 'archive_interrupted')",
        (json_text(report), now, case_id, expected_revision),
    )
    if updated.rowcount != 1:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")


def _apply_verified_archive_attachments(
    report: dict[str, Any], projection: Mapping[str, Any],
) -> None:
    extract_list = projection.get("extract_list")
    if not isinstance(extract_list, Mapping):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    columns = extract_list.get("columns")
    rows = extract_list.get("rows")
    if (not isinstance(columns, list) or not isinstance(rows, list)
            or not all(isinstance(column, Mapping) for column in columns)
            or not all(isinstance(row, Mapping) for row in rows)):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    attachments = report.get("attachments")
    if not isinstance(attachments, dict):
        attachments = {}
        report["attachments"] = attachments
    attachments["extract_list"] = {
        "columns": copy.deepcopy(columns), "rows": copy.deepcopy(rows),
    }
    for key in ("disc_number", "burning_date"):
        value = projection.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
            attachments[key] = value


def _required_text(part: Mapping[str, Any], key: str) -> str:
    value = part.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    return value.strip()
