"""Backfill inspection result and attachment 1 from a verified manifest.

WinRAR produces volume parts as a batch (no per-volume completion event is
exposed by the executor), so the backfill runs as soon as the manifest is
assembled. Values overwrite any previous/manual content per the confirmed
"实时填且覆盖手工值" decision.
"""

from __future__ import annotations

from typing import Any, Mapping

from .archive_manifest_projection_service import (
    project_manifest_to_legacy_report_with_plan,
)
from .attachment_plan_errors_service import AttachmentPlanError


def backfill_from_manifest(report: dict[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``report`` with 检查结果 and 附件1 filled from ``manifest``."""
    parts = [
        item for item in manifest.get("parts", [])
        if isinstance(item, Mapping) and str(item.get("filename") or "").strip()
    ]
    inspection = dict(report.get("inspection") or {})
    result = dict(inspection.get("result") or {})
    result.update({
        "rar_filename": "、".join(str(item.get("filename", "")) for item in parts),
        "md5_hash": "、".join(str(item.get("md5", "")) for item in parts),
        "file_size": "、".join(str(item.get("size_bytes", "")) for item in parts),
    })
    inspection["result"] = result
    filled = dict(report)
    filled["inspection"] = inspection
    try:
        projected, _ = project_manifest_to_legacy_report_with_plan(filled, dict(manifest))
        filled["attachments"] = projected.get("attachments", filled.get("attachments", {}))
    except AttachmentPlanError:
        # Incomplete review fields must not turn a valid archive into a failure.
        pass
    return filled
