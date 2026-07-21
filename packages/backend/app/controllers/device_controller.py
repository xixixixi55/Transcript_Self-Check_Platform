"""
Layer 22: BE_Controllers — 硬件设备管理 Controller
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.device_config_service import (
    list_devices, add_device, update_device, delete_device, DeviceConfigError,
)

router = APIRouter()


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    description: str = ""


class DeviceUpdate(BaseModel):
    name: str = ""
    model: str = ""
    description: str = ""


def _http_status(error: DeviceConfigError) -> int:
    """将服务层错误映射到 HTTP 状态码。"""
    if "不存在" in str(error):
        return 404
    if "已存在" in str(error):
        return 409
    return 400


@router.get("/devices")
async def get_devices():
    return {"success": True, "data": list_devices()}


@router.post("/devices")
async def create_device(body: DeviceCreate):
    try:
        device = add_device(body.name, body.model, body.description)
    except DeviceConfigError as e:
        raise HTTPException(status_code=_http_status(e), detail=str(e))
    return {"success": True, "data": device}


@router.put("/devices/{device_id}")
async def update_device_endpoint(device_id: str, body: DeviceUpdate):
    try:
        result = update_device(device_id, body.name, body.model, body.description)
    except DeviceConfigError as e:
        raise HTTPException(status_code=_http_status(e), detail=str(e))
    return {"success": True, "data": result}


@router.delete("/devices/{device_id}")
async def delete_device_endpoint(device_id: str):
    try:
        delete_device(device_id)
    except DeviceConfigError as e:
        raise HTTPException(status_code=_http_status(e), detail=str(e))
    return {"success": True}
