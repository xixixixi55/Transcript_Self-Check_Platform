"""流水线防护、后台 Shadow 观测和安全诊断查询。"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ..services.archive.archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveRuntimeError
from ..services.pipeline_runtime_service import PipelineMode, pipeline_settings_for_app
from ..services.shadow_pipeline_service import (
    begin_shadow_stage, record_shadow_failure, run_shadow_archive, run_shadow_export,
    run_shadow_parse,
)
from ..services.shadow_runtime_service import SHADOW_RUNTIME_STORE


router = APIRouter()
_LOGGER = logging.getLogger(__name__)


def pipeline_settings_for_request(request: Request):
    settings = pipeline_settings_for_app(request.app)
    if settings.mode is PipelineMode.CANONICAL:
        raise HTTPException(
            status_code=501,
            detail={"code": "CANONICAL_NOT_ENABLED", "message": "Canonical 正式输出尚未启用。"},
        )
    return settings


def observe_shadow_parse(
    report: Mapping[str, Any], settings: Any, context_id: str | None, background_tasks: BackgroundTasks,
) -> None:
    if settings.mode is not PipelineMode.SHADOW:
        return
    handle = begin_shadow_stage(settings, context_id, "parse")
    if handle is not None:
        background_tasks.add_task(
            _run_parse, report, settings, context_id, handle.run_id, handle.task_token,
        )


def observe_shadow_archive(
    context_id: str, report: Mapping[str, Any], manifest: Mapping[str, Any], settings: Any,
    background_tasks: BackgroundTasks, *, legacy_plan: Any = None,
    canonical_source: Mapping[str, Any] | None = None,
) -> None:
    if settings.mode is not PipelineMode.SHADOW:
        return
    handle = begin_shadow_stage(settings, context_id, "archive")
    if handle is None:
        return
    try:
        context = ARCHIVE_RUNTIME_STORE.get_context_snapshot(context_id)
    except Exception:
        record_shadow_failure(
            settings, context_id, "archive", run_id=handle.run_id,
            task_token=handle.task_token, code="SHADOW_ARCHIVE_CONTEXT_UNAVAILABLE",
        )
        return
    background_tasks.add_task(
        _run_archive, context_id, report, manifest, context, settings,
        legacy_plan, canonical_source, handle.run_id, handle.task_token,
    )


def observe_shadow_export(
    context_id: str, report: Mapping[str, Any], manifest: Mapping[str, Any], settings: Any,
    background_tasks: BackgroundTasks, *, legacy_plan: Any = None,
    canonical_source: Mapping[str, Any] | None = None,
) -> None:
    if settings.mode is not PipelineMode.SHADOW:
        return
    handle = begin_shadow_stage(settings, context_id, "export")
    if handle is not None:
        background_tasks.add_task(
            _run_export, context_id, report, manifest, settings, legacy_plan,
            canonical_source, handle.run_id, handle.task_token,
        )


def record_shadow_export_failure_at_controller(settings: Any, context_id: str) -> None:
    if settings.mode is PipelineMode.SHADOW:
        try:
            record_shadow_failure(settings, context_id, "export", code="LEGACY_DOCX_RENDER_FAILED")
        except Exception:
            _LOGGER.error(
                "SHADOW_DIAGNOSTIC_WRITE_FAILED stage=export code=LEGACY_DOCX_RENDER_FAILED",
            )


@router.get("/records/archive/{archive_context_id}/pipeline")
async def shadow_pipeline_status_endpoint(archive_context_id: str):
    try:
        ARCHIVE_RUNTIME_STORE.get_context_summary(archive_context_id)
    except ArchiveRuntimeError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "message": error.safe_message},
        ) from error
    summary = SHADOW_RUNTIME_STORE.public_summary(context_id=archive_context_id)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SHADOW_DIAGNOSTICS_NOT_FOUND", "message": "Shadow 诊断记录不存在或已过期。"},
        )
    return {"success": True, "data": summary}


def _run_parse(
    report: Mapping[str, Any], settings: Any, context_id: str | None,
    run_id: str, task_token: str | None,
) -> None:
    try:
        run_shadow_parse(report, settings, context_id, run_id=run_id, task_token=task_token)
    except Exception:
        _record_boundary_failure(settings, context_id, "parse", run_id, task_token)


def _run_archive(
    context_id: str, report: Mapping[str, Any], manifest: Mapping[str, Any], context: Any,
    settings: Any, legacy_plan: Any, canonical_source: Mapping[str, Any] | None,
    run_id: str, task_token: str | None,
) -> None:
    try:
        run_shadow_archive(
            context_id, report, manifest, context, settings,
            legacy_plan=legacy_plan, canonical_source=canonical_source,
            run_id=run_id, task_token=task_token,
        )
    except Exception:
        _record_boundary_failure(settings, context_id, "archive", run_id, task_token)


def _run_export(
    context_id: str, report: Mapping[str, Any], manifest: Mapping[str, Any], settings: Any,
    legacy_plan: Any, canonical_source: Mapping[str, Any] | None,
    run_id: str, task_token: str | None,
) -> None:
    try:
        run_shadow_export(
            context_id, report, manifest, settings,
            legacy_plan=legacy_plan, canonical_source=canonical_source,
            run_id=run_id, task_token=task_token, legacy_export_succeeded=True,
        )
    except Exception:
        _record_boundary_failure(settings, context_id, "export", run_id, task_token)


def _record_boundary_failure(
    settings: Any, context_id: str | None, stage: str, run_id: str, task_token: str | None,
) -> None:
    try:
        record_shadow_failure(settings, context_id, stage, run_id=run_id, task_token=task_token)
    except Exception:
        _LOGGER.error("SHADOW_DIAGNOSTIC_WRITE_FAILED stage=%s code=SHADOW_RUNTIME_FAILED", stage)


__all__ = [
    "observe_shadow_archive", "observe_shadow_export", "observe_shadow_parse",
    "pipeline_settings_for_request", "record_shadow_export_failure_at_controller", "router",
]
