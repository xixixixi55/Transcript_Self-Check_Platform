"""Layer 22: case workbench HTTP DTO mapping and error boundary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..repository.workbench_errors import WorkbenchPersistenceError
from ..services.case_submission_service import submit_case
from ..services.workbench_factory_service import ensure_archive_task_api, get_workbench_services
from .workbench_error_messages_controller import message_for_workbench_error as _message

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


class CaseSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str
    case_name: str = ""
    case_summary: str = ""
    case_number: str | None = None
    directory_grant_token: str | None = None
    source_authorization_enabled: bool = True
    client_instance_id: str = "local-client"
    session_id: str = "local-session"
    local_display_name: str | None = None


class DirectoryCaseSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_name: str = ""
    case_summary: str = ""
    case_number: str | None = None
    source_authorization_enabled: bool = False
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
    """Persist a case shell before scheduling parsing of a selected directory."""
    services = get_workbench_services()
    try:
        return _envelope(submit_case(
            services,
            body.source_path,
            case_name=body.case_name,
            case_summary=body.case_summary,
            case_number=body.case_number,
            directory_grant_token=body.directory_grant_token,
            source_authorization_enabled=body.source_authorization_enabled,
            client_instance_id=body.client_instance_id,
            session_id=body.session_id,
            local_display_name=body.local_display_name,
        ))
    except Exception as error:
        _handle(error)


@router.post("/workbench/cases/select-directory")
def select_directory_case_endpoint(body: DirectoryCaseSubmissionRequest):
    """Pick a local folder and immediately submit it through the directory contract."""
    services = get_workbench_services()
    try:
        if services.directory_picker is None:
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE")
        selected_path = services.directory_picker.select(history_kind="report")
        if selected_path is None:
            return _envelope({"cancelled": True})
        return _envelope(submit_case(
            services,
            selected_path,
            case_name=body.case_name,
            case_summary=body.case_summary,
            case_number=body.case_number,
            source_authorization_enabled=body.source_authorization_enabled,
            client_instance_id=body.client_instance_id,
            session_id=body.session_id,
            local_display_name=body.local_display_name,
        ))
    except Exception as error:
        _handle(error)


@router.post("/workbench/select-export-directory")
def select_export_directory_endpoint():
    """Open the trusted native picker and return the chosen path plus a one-use grant."""
    services = get_workbench_services()
    try:
        if services.directory_picker is None:
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE")
        selected_path = services.directory_picker.select(
            description="选择导出目录",
            history_kind="export",
        )
        if selected_path is None:
            return _envelope({"cancelled": True})
        token = services.sources.authorization.issue_exact_directory_grant(selected_path)
        return _envelope({"path": selected_path, "token": token})
    except Exception as error:
        _handle(error)


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
        archive_task = None
        if body.decision == "immediate" and services.archive_attempts is not None:
            archive_api = ensure_archive_task_api(services)
            if archive_api is None:
                raise HTTPException(
                    status_code=503,
                    detail={"code": "ARCHIVE_TASK_API_UNAVAILABLE", "message": "归档任务服务暂不可用。"},
                )
            queued = archive_api.enqueue(case_id, body.expected_revision)
            archive_task = queued["task"]
            detail = services.lifecycle.detail(case_id)
        else:
            context_id = services.sources.create_legacy_preview_source(case_id) if body.decision == "immediate" else None
            detail = services.lifecycle.decide_archive(
                case_id, body.decision, body.expected_revision, body.identity,
            )
        return _envelope({
            "case": detail,
            "decision": body.decision,
            "archive_status": "archive_task_queued" if body.decision == "immediate" else "deferred",
            "archive_context_id": None,
            "archive_attempt_id": None,
            "archive_task": archive_task,
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


@router.delete("/workbench/cases/{case_id}")
async def delete_case_endpoint(case_id: str):
    try:
        return _envelope(get_workbench_services().lifecycle.delete_case(case_id))
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
    status = 404 if code.endswith("NOT_FOUND") or code == "CASE_NOT_FOUND" else 409 if code in {"REVISION_CONFLICT", "LEASE_CONFLICT", "LEASE_TAKEOVER_REQUIRED", "LEASE_NOT_ACTIVE", "LEASE_EXPIRED", "SOURCE_RESELECTION_REQUIRED", "SOURCE_REVALIDATION_PENDING", "ARCHIVE_ATTEMPT_NOT_ALLOWED", "ARCHIVE_ATTEMPT_REQUIRED", "ARCHIVE_ATTEMPT_BINDING_MISMATCH", "ARCHIVE_ATTEMPT_BINDING_STALE", "ARCHIVE_REPORT_MISMATCH", "ARCHIVE_TASK_ALREADY_ACTIVE", "ARCHIVE_TASK_STALE", "ARCHIVE_CANCEL_NOT_ALLOWED", "ARCHIVE_RETRY_NOT_ALLOWED", "ARCHIVE_MAPPING_LOCKED"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": _message(code)}) from error
