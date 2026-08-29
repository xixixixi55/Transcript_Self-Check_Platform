"""第 22 层：本地检查人员库的 HTTP 管理端点。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..services.inspection.inspector_service import (
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
    position: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    police_number: Annotated[StrictStr, Field(min_length=1, max_length=64)]


class InspectorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[StrictStr, Field(min_length=1, max_length=100)] | None = None
    unit: Annotated[StrictStr, Field(min_length=1, max_length=200)] | None = None
    position: Annotated[StrictStr, Field(min_length=1, max_length=100)] | None = None
    police_number: Annotated[StrictStr, Field(min_length=1, max_length=64)] | None = None


def _handle_error(error: Exception) -> None:
    if isinstance(error, InspectorValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    if isinstance(error, InspectorNotFoundError):
        raise HTTPException(status_code=404, detail="检查人员不存在") from error
    if isinstance(error, InspectorDataError):
        raise HTTPException(status_code=500, detail="检查人员数据不可读取或写入") from error
    raise error


@router.get("/inspectors")
async def list_inspectors():
    try:
        return {"success": True, "data": _service.list()}
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
        return {"success": True, "data": _service.create(body.name, body.unit, body.position, body.police_number)}
    except Exception as error:
        _handle_error(error)


@router.put("/inspectors/{inspector_id}")
async def update_inspector(inspector_id: str, body: InspectorUpdate):
    try:
        return {"success": True, "data": _service.update(
            inspector_id, name=body.name, unit=body.unit,
            position=body.position, police_number=body.police_number,
        )}
    except Exception as error:
        _handle_error(error)


@router.delete("/inspectors/{inspector_id}")
async def delete_inspector(inspector_id: str):
    try:
        _service.delete(inspector_id)
        return {"success": True}
    except Exception as error:
        _handle_error(error)
