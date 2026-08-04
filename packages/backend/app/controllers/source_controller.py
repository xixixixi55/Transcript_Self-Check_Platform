"""Layer 22: opaque SourceRecord read and revalidation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..services.workbench_factory_service import get_workbench_services
from ..repository.workbench_errors import WorkbenchPersistenceError

router = APIRouter()


class SourceReplacementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str
    expected_revision: int = Field(ge=0)
    directory_grant_token: str | None = None
    source_authorization_enabled: bool = True


@router.get("/workbench/sources/{source_id}")
async def get_source_endpoint(source_id: str):
    try:
        return _envelope(get_workbench_services().sources.get(source_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/sources/{source_id}/revalidate")
async def revalidate_source_endpoint(source_id: str):
    try:
        return _envelope(get_workbench_services().sources.revalidate(source_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/cases/{case_id}/source")
async def replace_case_source_endpoint(case_id: str, body: SourceReplacementRequest):
    try:
        services = get_workbench_services()
        source = services.sources.replace_case_source(
            case_id,
            body.source_path,
            body.expected_revision,
            body.directory_grant_token,
            source_authorization_enabled=body.source_authorization_enabled,
        )
        task_id = services.lifecycle.detail(case_id)["shell"]["parse_task_id"]
        try:
            services.dispatcher.dispatch(services.cases, case_id, task_id)
        except Exception as error:
            services.cases.mark_dispatch_failed(case_id, task_id)
            raise WorkbenchPersistenceError("TASK_DISPATCH_FAILED") from error
        return _envelope(source)
    except Exception as error:
        _handle(error)


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _handle(error: Exception) -> None:
    code = getattr(error, "code", "WORKBENCH_REQUEST_FAILED")
    status = 404 if code == "SOURCE_NOT_FOUND" else 409 if code in {"REVISION_CONFLICT", "SOURCE_REVISION_CONFLICT", "SOURCE_REPLACEMENT_NOT_ALLOWED"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": _message(code)}) from error


def _message(code: str) -> str:
    return {
        "SOURCE_DIRECTORY_REQUIRED": "案件来源必须是报告目录，不接受文件或压缩包。",
        "SOURCE_ARCHIVE_NOT_ALLOWED": "案件来源不接受 ZIP、RAR 或其他压缩包。",
        "SOURCE_STRUCTURE_INVALID": "所选目录不包含可识别的报告结构。",
        "SOURCE_ACCESS_DENIED": "所选报告目录当前无法访问。",
        "ARCHIVE_INPUT_PATH_INVALID": "所选报告目录不存在或无效。",
        "ARCHIVE_INPUT_ROOT_NOT_ALLOWED": "所选报告目录未获授权。",
        "ARCHIVE_INPUT_LINK_NOT_ALLOWED": "所选报告目录包含不支持的链接或特殊路径。",
        "ARCHIVE_INPUT_OUTPUT_OVERLAP": "所选报告目录与系统输出区域冲突。",
    }.get(code, "报告来源不可用，请重新选择来源。")
