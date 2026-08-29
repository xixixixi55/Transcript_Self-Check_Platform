"""第 22 层：共享默认值 DTO 映射。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..services.runtime.workbench_factory_service import get_workbench_services

router = APIRouter()


class DefaultsSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, Any]
    expected_revision: int = Field(ge=0)
    identity: dict[str, Any]


class DefaultsMigrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    identity: dict[str, Any]
    values: dict[str, Any] | None = None


@router.get("/workbench/defaults")
async def get_defaults_endpoint():
    return _envelope(get_workbench_services().defaults.get())


@router.put("/workbench/defaults")
async def save_defaults_endpoint(body: DefaultsSaveRequest):
    try:
        result = get_workbench_services().defaults.patch(
            body.values, body.expected_revision, body.identity, allow_clear=True,
        )
        return _envelope(result["defaults"])
    except Exception as error:
        _handle(error)


@router.post("/workbench/defaults/migration")
async def decide_defaults_migration_endpoint(body: DefaultsMigrationRequest):
    try:
        result = get_workbench_services().defaults.decide_migration(body.decision, body.identity, body.values)
        return _envelope(result)
    except Exception as error:
        _handle(error)


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _handle(error: Exception) -> None:
    code = getattr(error, "code", "WORKBENCH_REQUEST_FAILED")
    status = 409 if code == "REVISION_CONFLICT" else 422
    messages = {
        "UNKNOWN_SHARED_DEFAULT_FIELD": "共享默认值字段不在允许范围内。",
        "INVALID_SHARED_DEFAULTS": "共享默认值内容无效。",
        "UNAUTHENTICATED_IDENTITY_REQUIRED": "客户端部署身份不被接受。",
    }
    raise HTTPException(status_code=status, detail={"code": code, "message": messages.get(code, "共享默认值请求未完成，请重试。")}) from error
