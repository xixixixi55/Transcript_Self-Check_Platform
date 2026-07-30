"""Layer 22: public archive task, mapping, history, and result endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from ..services.workbench_factory_service import ensure_archive_task_api
from . import workbench_controller
from .workbench_controller import _envelope, _handle

router = APIRouter()


class TaskCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)


class TaskRetryRequest(TaskCommandRequest):
    expected_case_revision: int = Field(ge=0)


class DiscMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str
    disc_number: str
    disc_date: str
    source: str
    confirmation: str


class MappingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    mappings: list[DiscMappingRequest]


def _archive_api() -> Any:
    services = workbench_controller.get_workbench_services()
    archive_api = ensure_archive_task_api(services)
    if archive_api is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "ARCHIVE_TASK_API_UNAVAILABLE", "message": "归档任务服务暂不可用。"},
        )
    return archive_api


@router.get("/workbench/tasks/{task_id}")
async def get_task_endpoint(task_id: str):
    try:
        services = workbench_controller.get_workbench_services()
        task = services.tasks.get(task_id)
        return _envelope(
            _archive_api().detail(task_id) if task["kind"] == "archive" else task
        )
    except Exception as error:
        _handle(error)


@router.get("/workbench/tasks/{task_id}/progress")
async def get_task_progress_endpoint(task_id: str):
    try:
        return _envelope(_archive_api().progress_summary(task_id))
    except Exception as error:
        _handle(error)


@router.get("/workbench/tasks/{task_id}/details")
async def get_task_details_endpoint(task_id: str):
    try:
        return _envelope(_archive_api().detail(task_id))
    except Exception as error:
        _handle(error)


@router.get("/workbench/cases/{case_id}/archive-history")
async def get_archive_history_endpoint(case_id: str):
    try:
        return _envelope(_archive_api().history(case_id))
    except Exception as error:
        _handle(error)


@router.get("/workbench/tasks/{task_id}/result")
async def get_archive_result_endpoint(task_id: str):
    try:
        return _envelope(_archive_api().result(task_id))
    except Exception as error:
        _handle(error)


@router.get("/workbench/tasks/{task_id}/result/parts/{part_id}")
async def download_archive_result_part_endpoint(task_id: str, part_id: str):
    try:
        filename, path = _archive_api().download_result_part(task_id, part_id)
        return FileResponse(
            path=path,
            filename=filename,
            media_type="application/vnd.rar",
        )
    except Exception as error:
        _handle(error)


@router.post("/workbench/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str, body: TaskCommandRequest):
    try:
        services = workbench_controller.get_workbench_services()
        task = services.tasks.get(task_id)
        result = (
            _archive_api().cancel(task_id, body.expected_revision)
            if task["kind"] == "archive"
            else services.tasks.request_cancel(task_id, body.expected_revision)
        )
        return _envelope(result)
    except Exception as error:
        _handle(error)


@router.post("/workbench/tasks/{task_id}/retry")
async def retry_archive_task_endpoint(task_id: str, body: TaskRetryRequest):
    try:
        return _envelope(_archive_api().retry(
            task_id, body.expected_revision, body.expected_case_revision,
        ))
    except Exception as error:
        _handle(error)


@router.get("/workbench/cases/{case_id}/archive-plan")
async def get_archive_plan_endpoint(case_id: str):
    try:
        return _envelope(_archive_api().get_plan(case_id))
    except Exception as error:
        _handle(error)


@router.patch("/workbench/cases/{case_id}/archive-plan")
async def update_archive_mapping_endpoint(case_id: str, body: MappingUpdateRequest):
    try:
        mappings = [mapping.model_dump() for mapping in body.mappings]
        return _envelope(_archive_api().update_mappings(
            case_id, mappings, body.expected_revision,
        ))
    except Exception as error:
        _handle(error)
