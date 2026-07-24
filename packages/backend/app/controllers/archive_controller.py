"""Layer 22: preview archive execution, status, and secure part download."""

from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..services.archive_execution_service import (
    ArchiveGateError,
    execute_archive,
)
from ..services.archive_runtime_service import ArchiveRuntimeError
from ..services.archive_runtime_service import ARCHIVE_RUNTIME_STORE
from ..services.archive_source_runtime_service import (
    get_preview_source_summary,
    prepare_archive_source,
    resolve_archive_context_id,
)
from ..services.archive_manifest_access_service import get_manifest_part_download
from ..services.archive_manifest_projection_service import project_manifest_to_legacy_report_with_plan
from ..services.attachment_plan_errors_service import AttachmentPlanError
from ..services.software_policy_service import normalize_primary_software_projection
from .pipeline_controller import (
    observe_shadow_archive,
    pipeline_settings_for_request,
)
from ..config import OUTPUT_BASE


router = APIRouter()


def _blocker(code: object, field: str = "archive", message: str = "归档门控未通过。") -> dict[str, str]:
    value = code.value if hasattr(code, "value") else str(code)
    return {"code": value, "field": field, "message": message}


def _archive_error(error: Exception) -> HTTPException:
    if isinstance(error, ArchiveGateError):
        return HTTPException(
            status_code=422,
            detail={"code": "EXPORT_BLOCKED", "blockers": [
                _blocker(item.code, item.field, item.message) for item in error.blockers
            ]},
        )
    if isinstance(error, ArchiveRuntimeError):
        return HTTPException(
            status_code=422,
            detail={"code": error.code, "blockers": [
                _blocker(error.code, message=error.safe_message)
            ]},
        )
    return HTTPException(status_code=422, detail={"code": "ARCHIVE_EXECUTION_FAILED", "blockers": [
        _blocker("ARCHIVE_EXECUTION_FAILED", message="归档执行失败，请检查后重试。")
    ]})


@router.post("/records/archive")
async def execute_archive_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    report_json: str = Form(""),
    archive_context_id: str = Form(""),
):
    """Execute the reviewed archive synchronously; no client path is accepted."""

    settings = pipeline_settings_for_request(request)
    if not report_json or not archive_context_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "ARCHIVE_CONTEXT_INVALID", "blockers": [
                _blocker("ARCHIVE_CONTEXT_INVALID", message="归档上下文无效，请重新解析报告。")
            ]},
        )
    try:
        report = normalize_primary_software_projection(json.loads(report_json))
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="笔录数据 JSON 格式无效")
    try:
        formal_context_id = await run_in_threadpool(
            prepare_archive_source, archive_context_id, report, output_root=OUTPUT_BASE,
        )
        outcome = await run_in_threadpool(
            execute_archive, formal_context_id, report, output_root=OUTPUT_BASE,
        )
    except Exception as error:
        raise _archive_error(error) from error
    stored_manifest = (
        ARCHIVE_RUNTIME_STORE.get_manifest(outcome.manifest_id).public_manifest
        if outcome.manifest_id else None
    )
    attachment_preview = None
    legacy_report = report
    legacy_plan = None
    if stored_manifest:
        try:
            projected, legacy_plan = project_manifest_to_legacy_report_with_plan(report, stored_manifest)
            legacy_report = projected
            attachment_preview = projected.get("attachments", {}).get("extract_list")
        except AttachmentPlanError:
            # Incomplete review fields must not turn a valid archive into a failure.
            pass
    observe_shadow_archive(
        archive_context_id, legacy_report, stored_manifest or {}, settings, background_tasks,
        legacy_plan=legacy_plan, canonical_source=report,
    )
    data = {
        "status": outcome.status,
        "manifest_id": outcome.manifest_id,
        "manifest": stored_manifest,
        "attachment_preview": attachment_preview,
        "plan": outcome.plan.public_dict() if outcome.plan else None,
        "diagnostics": [item.__dict__ for item in outcome.diagnostics],
        "reused": outcome.reused,
    }
    return {
        "success": True,
        "data": data,
    }


@router.get("/records/archive/{archive_context_id}/status")
async def archive_status_endpoint(archive_context_id: str):
    try:
        try:
            summary = ARCHIVE_RUNTIME_STORE.get_context_summary(archive_context_id)
        except ArchiveRuntimeError as error:
            if error.code != "ARCHIVE_CONTEXT_NOT_FOUND":
                raise
            summary = get_preview_source_summary(archive_context_id)
        return {
            "success": True,
            "data": summary,
        }
    except ArchiveRuntimeError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "message": error.safe_message},
        ) from error


@router.get(
    "/records/archive/{archive_context_id}/manifests/{manifest_id}/parts/{part_id}"
)
async def download_archive_part_endpoint(
    archive_context_id: str, manifest_id: str, part_id: str,
):
    try:
        formal_context_id = resolve_archive_context_id(archive_context_id)
        download = get_manifest_part_download(
            formal_context_id, manifest_id, part_id,
        )
    except ArchiveGateError as error:
        raw_code = error.blockers[0].code if error.blockers else "ARCHIVE_MANIFEST_INVALID"
        code = raw_code.value if hasattr(raw_code, "value") else str(raw_code)
        status = 404 if code == "ARCHIVE_MANIFEST_PART_MISSING" else 409
        raise HTTPException(status_code=status, detail={"code": code}) from error
    except ArchiveRuntimeError as error:
        status = 404 if error.code in {
            "ARCHIVE_CONTEXT_EXPIRED", "ARCHIVE_MANIFEST_MISSING", "ARCHIVE_PART_NOT_FOUND",
        } else 403
        raise HTTPException(
            status_code=status,
            detail={"code": error.code, "message": error.safe_message},
        ) from error
    return FileResponse(
        path=download.path,
        filename=download.filename,
        media_type="application/vnd.rar",
        headers={"Content-Length": str(download.size_bytes)},
    )
