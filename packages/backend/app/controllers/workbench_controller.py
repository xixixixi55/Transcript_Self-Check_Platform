"""Layer 22: case workbench HTTP DTO mapping and error boundary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..services.workbench_factory_service import get_workbench_services
from ..services.archive_source_runtime_service import discard_preview_source

router = APIRouter()


class DraftSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft: dict[str, Any]
    expected_revision: int = Field(ge=0)
    shared_defaults_patch: dict[str, Any] | None = None
    shared_defaults: dict[str, Any] | None = None
    shared_defaults_revision: int | None = Field(default=None, ge=0)
    identity: dict[str, Any] | None = None
    lease_id: str | None = None
    lease_token: str | None = None


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str
    expected_revision: int = Field(ge=0)


class TaskCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)


class CaseSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str
    case_name: str = ""
    case_summary: str = ""
    case_number: str | None = None
    directory_grant_token: str | None = None
    client_instance_id: str = "local-client"
    session_id: str = "local-session"
    local_display_name: str | None = None


class ArchiveDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    expected_revision: int = Field(ge=0)
    identity: dict[str, Any] | None = None


@router.post("/workbench/cases")
def submit_case_endpoint(body: CaseSubmissionRequest):
    """Persist a case shell before scheduling parsing of an authorized directory."""
    services = get_workbench_services()
    identity = {
        "identity_kind": "local_session",
        "client_instance_id": body.client_instance_id or "local-client",
        "session_id": body.session_id or "local-session",
        "local_display_name": body.local_display_name,
        "deployment_instance_id": services.database.deployment_instance_id,
    }
    try:
        descriptor = services.sources.register_report_directory(body.source_path, body.directory_grant_token)
        identifiers = services.cases.submit(
            descriptor,
            case_name=body.case_name,
            case_summary=body.case_summary,
            case_number=body.case_number,
            identity=identity,
            dispatch=lambda case_id, task_id: _dispatch_parse(services, case_id, task_id),
        )
    except Exception as error:
        _handle(error)
    detail = services.lifecycle.detail(identifiers["case_id"])
    return _envelope({
        **{key: detail[key] for key in ("shell", "source", "parse_task")},
        "shared_defaults": services.defaults.get(),
    })


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


@router.post("/workbench/cases/{case_id}/archive-decision")
async def decide_archive_endpoint(case_id: str, body: ArchiveDecisionRequest):
    try:
        services = get_workbench_services()
        context_id = None
        attempt_id = None
        if body.decision == "immediate" and services.archive_attempts is not None:
            before = services.lifecycle.detail(case_id)
            source = services.sources.require_available(before["shell"]["source_id"])
            context_id = services.sources.create_legacy_preview_source(case_id)
            source = services.sources.get(source["source_id"])
            try:
                if before["shell"]["lifecycle"] == "archive_queued":
                    attempt = services.archive_attempts.reissue_context(
                        case_id, source["source_id"], source["revision"], context_id, body.expected_revision,
                    )
                else:
                    attempt = services.archive_attempts.accept(
                        case_id, source["source_id"], source["revision"], context_id, body.expected_revision,
                    )
            except Exception:
                discard_preview_source(context_id)
                raise
            attempt_id = attempt["attempt_id"]
            detail = services.lifecycle.detail(case_id)
        else:
            context_id = services.sources.create_legacy_preview_source(case_id) if body.decision == "immediate" else None
            detail = services.lifecycle.decide_archive(
                case_id, body.decision, body.expected_revision, body.identity,
            )
        return _envelope({
            "case": detail,
            "decision": body.decision,
            "archive_status": "legacy_explicit_ready" if body.decision == "immediate" else "deferred",
            "archive_context_id": context_id,
            "archive_attempt_id": attempt_id,
        })
    except Exception as error:
        _handle(error)


@router.patch("/workbench/cases/{case_id}/draft")
async def save_draft_endpoint(case_id: str, body: DraftSaveRequest):
    try:
        payload = dict(body.draft)
        payload["case_id"] = case_id
        result = get_workbench_services().lifecycle.save_draft(
            payload, body.expected_revision, body.shared_defaults_patch if body.shared_defaults_patch is not None else body.shared_defaults,
            body.shared_defaults_revision, body.identity, body.lease_id, body.lease_token,
        )
        if result["draft_save_status"]["status"] == "conflict":
            raise HTTPException(status_code=409, detail={"code": "REVISION_CONFLICT", "message": "案件已被其他会话修改，请重新读取后再保存。", "data": result})
        return _envelope(result)
    except Exception as error:
        _handle(error)


@router.post("/workbench/cases/{case_id}/retry")
def retry_case_endpoint(case_id: str):
    try:
        services = get_workbench_services()
        result = services.cases.retry(
            case_id,
            dispatch=lambda retry_case_id, task_id: _dispatch_parse(services, retry_case_id, task_id),
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


def _dispatch_parse(services: Any, case_id: str, task_id: str) -> None:
    services.dispatcher.dispatch(services.cases, case_id, task_id)


def _handle(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    code = getattr(error, "code", None)
    if not isinstance(code, str):
        code = "WORKBENCH_REQUEST_FAILED"
    status = 404 if code.endswith("NOT_FOUND") or code == "CASE_NOT_FOUND" else 409 if code in {"REVISION_CONFLICT", "LEASE_CONFLICT", "LEASE_TAKEOVER_REQUIRED", "LEASE_NOT_ACTIVE", "LEASE_EXPIRED", "SOURCE_RESELECTION_REQUIRED", "SOURCE_REVALIDATION_PENDING", "ARCHIVE_ATTEMPT_NOT_ALLOWED", "ARCHIVE_ATTEMPT_REQUIRED", "ARCHIVE_ATTEMPT_BINDING_MISMATCH", "ARCHIVE_ATTEMPT_BINDING_STALE", "ARCHIVE_REPORT_MISMATCH"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": _message(code)}) from error
def _message(code: str) -> str:
    messages = {
        "SOURCE_REQUIRED": "请登记报告目录路径。",
        "SOURCE_DIRECTORY_REQUIRED": "案件来源必须是报告目录，不接受文件或压缩包。",
        "SOURCE_ARCHIVE_NOT_ALLOWED": "案件来源不接受 ZIP、RAR 或其他压缩包。",
        "SOURCE_STRUCTURE_INVALID": "所选目录不包含可识别的报告结构。",
        "SOURCE_ACCESS_DENIED": "所选目录当前无法访问。",
        "ARCHIVE_INPUT_PATH_INVALID": "所选报告目录不存在或无效。",
        "ARCHIVE_INPUT_ROOT_NOT_ALLOWED": "所选报告目录未获授权。",
        "ARCHIVE_INPUT_LINK_NOT_ALLOWED": "所选报告目录包含不支持的链接或特殊路径。",
        "ARCHIVE_INPUT_OUTPUT_OVERLAP": "所选报告目录与系统输出区域冲突。",
        "ARCHIVE_AUTHORIZATION_INVALID": "所选报告目录授权无效。",
        "ARCHIVE_AUTHORIZATION_EXPIRED": "所选报告目录授权已过期。",
        "REVISION_CONFLICT": "案件已被其他会话修改，请重新读取后再保存。",
        "LEASE_CONFLICT": "案件当前由其他编辑会话占用。",
        "LEASE_TAKEOVER_REQUIRED": "编辑租约已过期但需要确认接管。",
        "SOURCE_RESELECTION_REQUIRED": "报告来源已失效，请重新选择来源。",
        "SOURCE_REVALIDATION_PENDING": "报告来源正在等待复核，请稍后重试。",
        "ARCHIVE_ATTEMPT_NOT_ALLOWED": "当前案件不能开始新的归档尝试。",
        "ARCHIVE_ATTEMPT_REQUIRED": "归档必须通过受控准备流程创建归档尝试。",
        "ARCHIVE_ATTEMPT_BINDING_MISMATCH": "归档上下文绑定不一致，请重新确认来源和草稿。",
        "ARCHIVE_ATTEMPT_BINDING_STALE": "草稿或来源已变化，请重新确认归档。",
        "ARCHIVE_REPORT_MISMATCH": "归档报告与服务端草稿不一致，请重新读取案件。",
        "UNKNOWN_SHARED_DEFAULT_FIELD": "共享默认值字段不在允许范围内。",
        "INVALID_SHARED_DEFAULTS": "共享默认值内容无效。",
        "UNAUTHENTICATED_IDENTITY_REQUIRED": "客户端身份必须由服务端当前部署实例确认。",
        "INVALID_ARCHIVE_DECISION": "压缩决策无效，请重新选择。",
    }
    return messages.get(code, "工作台请求未完成，请稍后重试。")
