"""基于成功归档任务的统一导出编排。

为遵守单文件大小限制而与 ArchiveTaskApiService 分离，同时复用其仓储
（草稿、结果、外壳、任务和数据库）。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...config import RUNTIME_PATHS
from ...repository.case.asset_reference_repository import AssetReferenceRepository
from ...repository.case.case_asset_storage import CaseAssetStorage
from ...repository.workbench.workbench_errors import WorkbenchPersistenceError
from ..attachment.attachment2_plan_service import with_compatible_material_photo_groups
from ..case.case_asset_service import within_asset_orphan_retention
from ..inspection.software_policy_service import normalize_runtime_software_tool_projection
from ..export.unified_export_service import UnifiedExportError, unified_export, with_disc_mapping

DirectoryOpener = Callable[[Path], None]


def validate_export_directory(
    export_path: str | Path,
    *,
    protected_roots: tuple[str | Path, ...] | None = None,
) -> Path:
    """解析导出目录，不允许写入应用拥有的根目录。"""
    candidate = Path(export_path)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise WorkbenchPersistenceError(
            "EXPORT_PATH_INVALID", "导出目录不存在或不可用，请重新选择。",
        ) from error
    if not resolved.is_dir():
        raise WorkbenchPersistenceError(
            "EXPORT_PATH_INVALID", "导出目录不存在或不可用，请重新选择。",
        )
    roots = protected_roots or (
        RUNTIME_PATHS.resource_root,
        RUNTIME_PATHS.app_data_root,
    )
    for root in roots:
        protected = Path(root).resolve(strict=False)
        try:
            resolved.relative_to(protected)
        except ValueError:
            continue
        raise WorkbenchPersistenceError(
            "EXPORT_DIRECTORY_UNSAFE",
            "导出目录不能位于文枢程序或用户数据目录中，请选择其他位置。",
        )
    return resolved


def open_latest_export_directory(
    api: Any,
    case_id: str,
    *,
    opener: DirectoryOpener | None = None,
) -> dict[str, Any]:
    """仅打开绑定到 ``case_id`` 的最近成功导出目录。"""
    api.shells.get(case_id)
    record = api.export_directories.latest(case_id)
    if not record or not record["export_path"]:
        raise WorkbenchPersistenceError("EXPORT_DIRECTORY_NOT_FOUND")
    try:
        export_path = Path(record["export_path"]).resolve(strict=True)
    except (OSError, RuntimeError):
        raise WorkbenchPersistenceError("EXPORT_DIRECTORY_MISSING") from None
    if not export_path.is_dir():
        raise WorkbenchPersistenceError("EXPORT_DIRECTORY_MISSING")
    try:
        (opener or _open_windows_directory)(export_path)
    except OSError as error:
        raise WorkbenchPersistenceError("EXPORT_DIRECTORY_OPEN_FAILED") from error
    return {
        "case_id": case_id,
        "opened": True,
        "exported_at": record["exported_at"],
    }


def _open_windows_directory(path: Path) -> None:
    if os.name != "nt":
        raise OSError("Windows Explorer is unavailable")
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    explorer = system_root / "explorer.exe"
    subprocess.Popen(
        [str(explorer), str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def resolve_case_word_manifest(api: Any, case_id: str) -> dict[str, Any] | None:
    """解析统一导出所用的同一份已验证、已映射 Manifest。

    没有成功归档的案件保留仅报告兼容路径。一旦存在成功归档，独立 Word 导出必须
    使用其 Manifest 和附件计划，而不能根据旧版提取清单表渲染不同附件布局。
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
    """仅解析持久化到此精确 Manifest 中的计划标识。"""
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
    """将最新 Word 和所有 RAR 分卷写入 export_path。"""
    shell = api.shells.get(case_id)
    if shell["revision"] != expected_revision:
        raise WorkbenchPersistenceError("REVISION_CONFLICT")
    export_dir = validate_export_directory(export_path)
    if not api.sources.authorization.consume_exact_directory_grant(
        directory_token, str(export_dir),
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
    api.export_directories.remember(
        case_id, output["export_path"], output["exported_at"],
    )
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
    """仅解析草稿绑定的图片资产，保留 ``asset_refs`` 顺序。"""
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
