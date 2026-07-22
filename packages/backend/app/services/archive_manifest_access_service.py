"""Access and revalidate the immutable manifest used by DOCX export."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..repository.archive_input_repository import ArchiveInputError, verify_input_inventory
from ..repository.filesystem_identity_repository import directory_content_fingerprint
from .archive_manifest_service import compute_disc_capacity, validate_manifest_files
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveManifestRecord, ArchiveRuntimeError
from .export_gate_service import ExportGateCode, ExportGateIssue


class ArchiveGateError(ArchiveRuntimeError):
    def __init__(self, blockers: tuple[ExportGateIssue, ...]):
        super().__init__("EXPORT_BLOCKED", "导出门控未通过。")
        self.blockers = blockers


def archive_report_fingerprint(report: dict, inventory, first_disc_number: str) -> str:
    payload = {
        "archive_base_name": str(
            (report.get("introduction") or {}).get("case_summary") or ""
        ).strip(),
        "first_disc_number": first_disc_number,
        "input": inventory.public_entries(),
        "input_content_fingerprint": directory_content_fingerprint(inventory.source_root),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()


def get_valid_manifest(context_id: str, manifest_id: str, report: dict) -> dict[str, object]:
    record = ARCHIVE_RUNTIME_STORE.get_manifest(manifest_id)
    if not record.belongs_to(context_id):
        raise ArchiveGateError((ExportGateIssue(
            ExportGateCode.ARCHIVE_MANIFEST_CONTEXT_MISMATCH, "archive_manifest", "归档清单不属于当前归档上下文。",
        ),))
    _raise_manifest_file_error(record)
    first_disc = str((report.get("attachments") or {}).get("disc_number"))
    context = ARCHIVE_RUNTIME_STORE.acquire_context(context_id)
    try:
        if context.successful_manifest_id != manifest_id:
            raise ArchiveGateError((ExportGateIssue(
                ExportGateCode.ARCHIVE_MANIFEST_MISSING, "archive_manifest", "归档清单不是当前上下文的成功结果。",
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
    normalized = copy.deepcopy(record.public_manifest)
    for part in normalized.get("parts", []):
        if "disc_capacity_bytes" not in part:
            try:
                part["disc_capacity_bytes"] = compute_disc_capacity(part["size_bytes"])
            except ValueError:
                pass  # size_bytes already validated, should not happen
    return normalized


@dataclass(frozen=True)
class ArchiveDownload:
    filename: str
    path: Path
    size_bytes: int


def get_manifest_part_download(
    context_id: str, manifest_id: str, part_id: str,
) -> ArchiveDownload:
    """Resolve one opaque manifest part and revalidate it before download."""
    record = ARCHIVE_RUNTIME_STORE.get_current_manifest(context_id, manifest_id)
    _raise_manifest_file_error(record)
    part = next(
        (
            item for item in record.public_manifest.get("parts", [])
            if isinstance(item, dict) and item.get("part_id") == part_id
        ),
        None,
    )
    if part is None:
        raise ArchiveRuntimeError("ARCHIVE_PART_NOT_FOUND", "归档分卷不存在。")
    filename = str(part["filename"])
    root = record.final_dir.resolve(strict=True)
    path = (root / filename).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ArchiveRuntimeError("ARCHIVE_PART_NOT_FOUND", "归档分卷不存在。") from error
    return ArchiveDownload(filename, path, int(part["size_bytes"]))


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
