"""Layer 22: case workbench HTTP DTO mapping and error boundary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..services.workbench_factory_service import get_workbench_services

router = APIRouter()


class DraftSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft: dict[str, Any]
    expected_revision: int = Field(ge=0)
    shared_defaults: dict[str, Any] | None = None
    shared_defaults_revision: int | None = Field(default=None, ge=0)
    identity: dict[str, Any] | None = None


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str
    expected_revision: int = Field(ge=0)


class TaskCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)


@router.post("/workbench/cases")
async def submit_case_endpoint(request: Request, background_tasks: BackgroundTasks):
    """Persist a case shell before scheduling parsing of an uploaded archive."""
    form = await request.form()
    upload = form.get("archive_file")
    if not upload or not isinstance(getattr(upload, "filename", None), str) or not upload.filename or not hasattr(upload, "read"):
        _raise("SOURCE_REQUIRED", 422)
    suffix = _suffix(upload.filename)
    services = get_workbench_services()
    identity = {
        "identity_kind": "local_session",
        "client_instance_id": _form_string(form.get("client_instance_id")) or "local-client",
        "session_id": _form_string(form.get("session_id")) or "local-session",
        "local_display_name": _form_optional(form.get("local_display_name")),
        "deployment_instance_id": services.database.deployment_instance_id,
    }
    try:
        descriptor = services.sources.store_uploaded_archive(await upload.read(), suffix)
        identifiers = services.cases.submit(
            descriptor,
            case_name=_form_string(form.get("case_name")),
            case_summary=_form_string(form.get("case_summary")),
            case_number=_form_optional(form.get("case_number")),
            identity=identity,
            dispatch=lambda case_id, task_id: _dispatch_parse(background_tasks, services, case_id, task_id),
        )
    except Exception as error:
        _handle(error)
    detail = services.lifecycle.detail(identifiers["case_id"])
    return _envelope({key: detail[key] for key in ("shell", "source", "parse_task")})


@router.get("/workbench/cases")
async def list_cases_endpoint(offset: int = Query(0, ge=0), limit: int = Query(6, ge=1, le=100)):
    try:
        return _envelope(get_workbench_services().lifecycle.list(offset, limit))
    except Exception as error:
        _handle(error)


@router.get("/workbench/cases/{case_id}")
async def get_case_endpoint(case_id: str):
    try:
        return _envelope(get_workbench_services().lifecycle.detail(case_id))
    except Exception as error:
        _handle(error)


@router.patch("/workbench/cases/{case_id}/draft")
async def save_draft_endpoint(case_id: str, body: DraftSaveRequest):
    try:
        payload = dict(body.draft)
        payload["case_id"] = case_id
        result = get_workbench_services().lifecycle.save_draft(
            payload, body.expected_revision, body.shared_defaults,
            body.shared_defaults_revision, body.identity,
        )
        if result["draft_save_status"]["status"] == "conflict":
            raise HTTPException(status_code=409, detail={"code": "REVISION_CONFLICT", "message": "案件已被其他会话修改，请重新读取后再保存。", "data": result})
        return _envelope(result)
    except Exception as error:
        _handle(error)


@router.post("/workbench/cases/{case_id}/retry")
async def retry_case_endpoint(case_id: str, background_tasks: BackgroundTasks):
    try:
        services = get_workbench_services()
        result = services.cases.retry(
            case_id,
            dispatch=lambda retry_case_id, task_id: _dispatch_parse(background_tasks, services, retry_case_id, task_id),
        )
        return _envelope(services.lifecycle.detail(case_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/cases/{case_id}/lifecycle")
async def transition_case_endpoint(case_id: str, body: LifecycleRequest):
    try:
        return _envelope(get_workbench_services().lifecycle.transition(case_id, body.target, body.expected_revision))
    except Exception as error:
        _handle(error)


@router.get("/workbench/cases/{case_id}/delete-preflight")
async def delete_preflight_endpoint(case_id: str):
    try:
        return _envelope(get_workbench_services().lifecycle.delete_preflight(case_id))
    except Exception as error:
        _handle(error)


@router.get("/workbench/tasks/{task_id}")
async def get_task_endpoint(task_id: str):
    try:
        return _envelope(get_workbench_services().tasks.get(task_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: str, body: TaskCancelRequest):
    try:
        return _envelope(get_workbench_services().tasks.request_cancel(task_id, body.expected_revision))
    except Exception as error:
        _handle(error)


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _dispatch_parse(background_tasks: BackgroundTasks, services: Any, case_id: str, task_id: str) -> None:
    background_tasks.add_task(services.cases.run_parse_task, case_id, task_id)


def _suffix(filename: str) -> str:
    import os
    suffix = os.path.splitext(filename)[1].casefold()
    if suffix not in {".rar", ".zip"}:
        _raise("SOURCE_TYPE_UNSUPPORTED", 422)
    return suffix


def _form_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _form_optional(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _handle(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    code = getattr(error, "code", None)
    if not isinstance(code, str):
        code = "WORKBENCH_REQUEST_FAILED"
    status = 404 if code.endswith("NOT_FOUND") or code == "CASE_NOT_FOUND" else 409 if code in {"REVISION_CONFLICT", "LEASE_CONFLICT", "LEASE_TAKEOVER_REQUIRED", "SOURCE_RESELECTION_REQUIRED"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": _message(code)}) from error


def _raise(code: str, status: int) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": _message(code)})


def _message(code: str) -> str:
    messages = {
        "SOURCE_REQUIRED": "请上传报告压缩包。",
        "SOURCE_TYPE_UNSUPPORTED": "仅支持受控的报告压缩包来源。",
        "REVISION_CONFLICT": "案件已被其他会话修改，请重新读取后再保存。",
        "LEASE_CONFLICT": "案件当前由其他编辑会话占用。",
        "LEASE_TAKEOVER_REQUIRED": "编辑租约已过期但需要确认接管。",
        "SOURCE_RESELECTION_REQUIRED": "报告来源已失效，请重新选择来源。",
        "WORKBENCH_ARCHIVE_NOT_IMPLEMENTED": "本阶段未启用归档执行。",
    }
    return messages.get(code, "工作台请求未完成，请稍后重试。")
