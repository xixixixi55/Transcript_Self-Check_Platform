"""Layer 22: HTTP management endpoints for the local inspector library."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from ..services.inspector_service import (
    InspectorDataError,
    InspectorNotFoundError,
    InspectorService,
    InspectorValidationError,
)

router = APIRouter()
_service = InspectorService()


class InspectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    unit: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    police_number: Annotated[StrictStr, Field(min_length=1, max_length=64)]


class InspectorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[StrictStr, Field(min_length=1, max_length=100)] | None = None
    unit: Annotated[StrictStr, Field(min_length=1, max_length=200)] | None = None
    police_number: Annotated[StrictStr, Field(min_length=1, max_length=64)] | None = None


class InspectorStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


def _handle_error(error: Exception) -> None:
    if isinstance(error, InspectorValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    if isinstance(error, InspectorNotFoundError):
        raise HTTPException(status_code=404, detail="检查人员不存在") from error
    if isinstance(error, InspectorDataError):
        raise HTTPException(status_code=500, detail="检查人员数据不可读取或写入") from error
    raise error


@router.get("/inspectors")
async def list_inspectors(enabled_only: bool = Query(False)):
    try:
        return {"success": True, "data": _service.list(enabled_only=enabled_only)}
    except Exception as error:
        _handle_error(error)


@router.get("/inspectors/{inspector_id}")
async def get_inspector(inspector_id: str):
    try:
        result = _service.get(inspector_id)
        if result is None:
            raise InspectorNotFoundError("检查人员不存在")
        return {"success": True, "data": result}
    except Exception as error:
        _handle_error(error)


@router.post("/inspectors")
async def create_inspector(body: InspectorCreate):
    try:
        return {"success": True, "data": _service.create(body.name, body.unit, body.police_number)}
    except Exception as error:
        _handle_error(error)


@router.put("/inspectors/{inspector_id}")
async def update_inspector(inspector_id: str, body: InspectorUpdate):
    try:
        return {"success": True, "data": _service.update(inspector_id, name=body.name, unit=body.unit, police_number=body.police_number)}
    except Exception as error:
        _handle_error(error)


@router.post("/inspectors/{inspector_id}/status")
async def set_inspector_status(inspector_id: str, body: InspectorStatus):
    try:
        return {"success": True, "data": _service.set_enabled(inspector_id, body.enabled)}
    except Exception as error:
        _handle_error(error)


@router.delete("/inspectors/{inspector_id}")
async def delete_inspector(inspector_id: str):
    try:
        _service.delete(inspector_id)
        return {"success": True}
    except Exception as error:
        _handle_error(error)
