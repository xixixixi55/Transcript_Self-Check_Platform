"""Trusted projection of verified archive parts into the Legacy report DTO."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text


def apply_verified_archive_result(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a report with the existing three archive result fields filled.

    The caller must have verified the manifest and its physical files.  This
    helper only performs the stable Legacy DTO projection and never adds a
    manifest identifier or filesystem detail to the report.
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
    return result


def verified_archive_result_fields(manifest: Mapping[str, Any]) -> dict[str, str]:
    """Build the existing stable string contract from ordered manifest parts."""
    parts = manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    values: dict[str, list[str]] = {"rar_filename": [], "md5_hash": [], "file_size": []}
    for part in parts:
        if not isinstance(part, Mapping):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
        values["rar_filename"].append(_required_text(part, "filename"))
        values["md5_hash"].append(_required_text(part, "md5"))
        size = part.get("size_bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
        values["file_size"].append(str(size))
    return {key: "、".join(items) for key, items in values.items()}


def update_verified_draft(
    connection: Any, draft: Mapping[str, Any], intent: Mapping[str, Any],
    case_id: str, expected_revision: int, now: str,
) -> None:
    report = apply_verified_archive_result(
        json.loads(draft["report_json"]),
        json.loads(intent["public_manifest_json"]),
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


def _required_text(part: Mapping[str, Any], key: str) -> str:
    value = part.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    return value.strip()
