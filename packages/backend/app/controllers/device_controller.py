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
    company: str = Field(..., min_length=1, max_length=100, pattern=r".*\S.*")
    description: str = ""


class DeviceUpdate(BaseModel):
    name: str = ""
    model: str = ""
    company: str | None = Field(default=None, max_length=100, pattern=r".*\S.*")
    description: str = ""


@router.get("/devices")
async def get_devices():
    return {"success": True, "data": list_devices()}


@router.post("/devices")
async def create_device(body: DeviceCreate):
    device = add_device(body.name, body.model, body.company, body.description)
    return {"success": True, "data": device}


@router.put("/devices/{device_id}")
async def update_device_endpoint(device_id: str, body: DeviceUpdate):
    try:
        result = update_device(
            device_id, name=body.name, model=body.model,
            description=body.description, company=body.company,
        )
    except DeviceConfigError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "data": result}


@router.delete("/devices/{device_id}")
async def delete_device_endpoint(device_id: str):
    try:
        delete_device(device_id)
    except DeviceConfigError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True}
