"""Access and revalidate the immutable manifest used by DOCX export."""

from __future__ import annotations

import hashlib
import json

from ..repository.archive_input_repository import ArchiveInputError, verify_input_inventory
from .archive_manifest_service import validate_manifest_files
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveManifestRecord, ArchiveRuntimeError
from .export_gate_service import ExportGateIssue


class ArchiveGateError(ArchiveRuntimeError):
    def __init__(self, blockers: tuple[ExportGateIssue, ...]):
        super().__init__("EXPORT_BLOCKED", "导出门控未通过。")
        self.blockers = blockers


def archive_report_fingerprint(report: dict, inventory, first_disc_number: str) -> str:
    fingerprint_report = dict(report)
    fingerprint_attachments = dict(fingerprint_report.get("attachments") or {})
    fingerprint_attachments.pop("photo_ids", None)
    fingerprint_report["attachments"] = fingerprint_attachments
    payload = {
        "report": fingerprint_report,
        "first_disc_number": first_disc_number,
        "input": [item.public_entry() for item in inventory.files],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()


def get_valid_manifest(context_id: str, manifest_id: str, report: dict) -> dict[str, object]:
    record = ARCHIVE_RUNTIME_STORE.get_manifest(manifest_id)
    if record.context_id != context_id:
        raise ArchiveGateError((ExportGateIssue(
            "ARCHIVE_MANIFEST_CONTEXT_MISMATCH", "archive_manifest", "归档清单不属于当前归档上下文。",
        ),))
    _raise_manifest_file_error(record)
    first_disc = str((report.get("attachments") or {}).get("disc_number"))
    context = ARCHIVE_RUNTIME_STORE.acquire_context(context_id)
    try:
        if context.successful_manifest_id != manifest_id:
            raise ArchiveGateError((ExportGateIssue(
                "ARCHIVE_MANIFEST_MISSING", "archive_manifest", "归档清单不是当前上下文的成功结果。",
            ),))
        ARCHIVE_RUNTIME_STORE.validate_context_authorization(context)
        try:
            verify_input_inventory(context.inventory)
        except ArchiveInputError as error:
            raise ArchiveGateError((ExportGateIssue(
                error.code, "archive_manifest", "归档输入已变化，请重新解析。",
            ),)) from error
        if record.fingerprint != archive_report_fingerprint(report, context.inventory, first_disc):
            raise ArchiveGateError((ExportGateIssue(
                "ARCHIVE_MANIFEST_MISSING", "archive_manifest", "审核数据已变化，请重新生成归档。",
            ),))
    finally:
        ARCHIVE_RUNTIME_STORE.release_context(context_id)
    return record.public_manifest


def _raise_manifest_file_error(record: ArchiveManifestRecord) -> None:
    code = validate_manifest_files(record)
    if code:
        messages = {
            "ARCHIVE_MANIFEST_PART_MISSING": "归档分卷不存在。",
            "ARCHIVE_MANIFEST_PART_CHANGED": "归档分卷已发生变化。",
        }
        raise ArchiveGateError((ExportGateIssue(
            code, "archive_manifest", messages.get(code, "归档清单校验失败。"),
        ),))
