"""
Layer 22: BE_Controllers — 硬件设备管理 Controller
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..repository.device_config import list_devices, add_device, update_device, delete_device

router = APIRouter()


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    description: str = ""


class DeviceUpdate(BaseModel):
    name: str = ""
    model: str = ""
    description: str = ""


@router.get("/devices")
async def get_devices():
    return {"success": True, "data": list_devices()}


@router.post("/devices")
async def create_device(body: DeviceCreate):
    device = add_device(body.name, body.model, body.description)
    return {"success": True, "data": device}


@router.put("/devices/{device_id}")
async def update_device_endpoint(device_id: str, body: DeviceUpdate):
    result = update_device(device_id, body.name, body.model, body.description)
    if not result:
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"success": True, "data": result}


@router.delete("/devices/{device_id}")
async def delete_device_endpoint(device_id: str):
    if not delete_device(device_id):
        raise HTTPException(status_code=404, detail="设备不存在")
    return {"success": True}
