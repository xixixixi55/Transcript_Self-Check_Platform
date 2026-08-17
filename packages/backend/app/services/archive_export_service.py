"""Unified export orchestration over a succeeded archive task.

Kept separate from ArchiveTaskApiService to respect the per-file size limit
while reusing its repositories (drafts, results, shells, tasks, database).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..repository.asset_reference_repository import AssetReferenceRepository
from ..repository.case_asset_storage import CaseAssetStorage
from ..repository.workbench_errors import WorkbenchPersistenceError
from .attachment2_plan_service import with_compatible_material_photo_groups
from .case_asset_service import within_asset_orphan_retention
from .software_policy_service import normalize_runtime_software_tool_projection
from .unified_export_service import UnifiedExportError, unified_export, with_disc_mapping


def resolve_case_word_manifest(api: Any, case_id: str) -> dict[str, Any] | None:
    """Resolve the same verified, mapped manifest used by unified export.

    A case without a successful archive keeps the report-only compatibility
    path. Once a successful archive exists, standalone Word export must use its
    manifest and attachment plan instead of rendering a different attachment
    layout from the legacy extract-list table.
    """
    task = next(
        (item for item in api.tasks.get_history(case_id) if item["status"] == "succeeded"),
        None,
    )
    if task is None:
        return None
    bundle = api.results.manifest_bundle(task["task_id"])
    plan = _bound_manifest_plan(api, case_id, bundle["public_manifest"])
    return with_disc_mapping(bundle["public_manifest"], plan)


def _bound_manifest_plan(
    api: Any, case_id: str, manifest: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve only the plan identity persisted into this exact Manifest."""
    plan_id = str(manifest.get("plan_id") or "")
    if not plan_id:
        return None
    plan = api.plans.get(plan_id)
    if plan.get("case_id") != case_id:
        raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
    return plan


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
    """Write latest Word + all RAR parts + verification PNG into export_path."""
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
    bound_plan = _bound_manifest_plan(api, case_id, bundle["public_manifest"])
    draft = api.drafts.get(case_id)
    report = normalize_runtime_software_tool_projection(draft["report"])
    bound_photo_ids = [
        str(reference["asset_id"])
        for reference in draft.get("asset_refs", [])
        if reference.get("asset_kind") == "image"
    ]
    attachments = report.setdefault("attachments", {})
    attachments["photo_ids"] = bound_photo_ids
    report = with_compatible_material_photo_groups(report)
    export_dir = Path(export_path)
    if not export_dir.is_absolute() or not export_dir.is_dir():
        raise WorkbenchPersistenceError("EXPORT_PATH_INVALID", "导出路径无效。")
    try:
        output = unified_export(
            report=report, manifest=bundle["public_manifest"],
            final_dir=bundle["final_dir"], export_path=export_dir,
            photo_paths=_resolve_photo_paths(api, case_id, draft),
            template_context=template_context,
            word_filename=word_filename,
            database=api.database, case_id=case_id, task_id=task["task_id"],
            plan=bound_plan,
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


def _resolve_photo_paths(
    api: Any, case_id: str, draft: dict[str, Any] | None = None,
) -> list[Path]:
    """Resolve only draft-bound image assets, preserving ``asset_refs`` order."""
    draft = draft or api.drafts.get(case_id)
    bound_refs = [
        reference for reference in draft.get("asset_refs", [])
        if reference.get("asset_kind") == "image"
    ]
    registered = AssetReferenceRepository(api.database).list_case(case_id, "image")
    registered_by_id = {str(reference["asset_id"]): reference for reference in registered}
    bound_ids = [str(reference["asset_id"]) for reference in bound_refs]
    bound_id_set = set(bound_ids)
    if any(
        asset_id not in bound_id_set
        and within_asset_orphan_retention(str(reference["created_at"]))
        for asset_id, reference in registered_by_id.items()
    ):
        raise WorkbenchPersistenceError(
            "PHOTO_ASSETS_NOT_SAVED",
            "检测到已上传但尚未保存到草稿的图片，请返回审核页完成图片恢复与保存后再导出。",
        )
    assets_root = api.database.database_path.parent / "assets"
    storage = CaseAssetStorage(assets_root)
    ordered: list[Path] = []
    for reference in bound_refs:
        asset_id = str(reference["asset_id"])
        registered_reference = registered_by_id.get(asset_id)
        if registered_reference is None:
            raise WorkbenchPersistenceError("ASSET_CONTENT_MISSING")
        suffix = str((registered_reference.get("metadata") or {}).get("extension") or "")
        try:
            path = storage.path_for(case_id, asset_id, suffix)
        except ValueError as error:
            raise WorkbenchPersistenceError("ASSET_CONTENT_MISSING") from error
        if not path.is_file():
            raise WorkbenchPersistenceError("ASSET_CONTENT_MISSING")
        fingerprint = str(registered_reference.get("fingerprint") or "")
        if not fingerprint or hashlib.sha256(path.read_bytes()).hexdigest() != fingerprint:
            raise WorkbenchPersistenceError("ASSET_CONTENT_CORRUPT")
        ordered.append(path)
    return ordered
