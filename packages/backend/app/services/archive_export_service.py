"""Unified export orchestration over a succeeded archive task.

Kept separate from ArchiveTaskApiService to respect the per-file size limit
while reusing its repositories (drafts, results, shells, tasks, database).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..repository.workbench_errors import WorkbenchPersistenceError
from .unified_export_service import UnifiedExportError, unified_export


def export_bundle(
    api: Any,
    case_id: str,
    expected_revision: int,
    export_path: str,
    *,
    directory_token: str,
    word_filename: str | None = None,
    template_context: dict[str, object],
) -> dict[str, Any]:
    """Write latest Word + all RAR parts + verification HTML into export_path."""
    shell = api.shells.get(case_id)
    if shell["revision"] != expected_revision:
        raise WorkbenchPersistenceError("REVISION_CONFLICT")
    if not api.sources.authorization.consume_exact_directory_grant(
        directory_token, export_path,
    ):
        raise WorkbenchPersistenceError(
            "EXPORT_PATH_NOT_AUTHORIZED", "导出目录未授权，请通过目录选择器重新选择。",
        )
    task = api.tasks.get_current_or_recent(case_id)
    if task is None or task["status"] != "succeeded":
        raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
    bundle = api.results.manifest_bundle(task["task_id"])
    draft = api.drafts.get(case_id)
    report = draft["report"]
    export_dir = Path(export_path)
    if not export_dir.is_absolute() or not export_dir.is_dir():
        raise WorkbenchPersistenceError("EXPORT_PATH_INVALID", "导出路径无效。")
    try:
        output = unified_export(
            report=report, manifest=bundle["public_manifest"],
            final_dir=bundle["final_dir"], export_path=export_dir,
            photo_paths=_resolve_photo_paths(api, case_id),
            template_context=template_context,
            word_filename=word_filename,
            database=api.database, case_id=case_id, task_id=task["task_id"],
            plan=api.plans.get_latest_for_case(case_id),
        )
    except UnifiedExportError as error:
        raise WorkbenchPersistenceError(error.code, error.args[0]) from error
    try:
        api.shells.update_lifecycle(case_id, "exported", expected_revision)
    except Exception as error:
        raise WorkbenchPersistenceError("EXPORT_LIFECYCLE_FAILED", "导出完成但状态标记失败。") from error
    return {
        "case_id": case_id, "task_id": task["task_id"],
        "expected_revision": expected_revision, "lifecycle": "exported",
        "output": output,
    }


def _resolve_photo_paths(api: Any, case_id: str) -> list[Path]:
    """Photo files ordered by the draft's photo_groups asset ids."""
    from ..repository.case_asset_storage import CaseAssetStorage

    assets_root = api.database.database_path.parent / "assets"
    storage = CaseAssetStorage(assets_root)
    files = sorted(storage.files_for_case(case_id))
    by_asset = {path.stem: path for path in files}
    draft = api.drafts.get(case_id)
    report = draft["report"]
    ordered: list[Path] = []
    for group in (report.get("attachments") or {}).get("photo_groups") or []:
        for photo in group.get("photo_ids") or []:
            path = by_asset.get(str(photo))
            if path is not None:
                ordered.append(path)
    return ordered or files
