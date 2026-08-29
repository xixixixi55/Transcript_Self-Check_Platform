"""
Layer 22: BE_Controllers — 硬件设备管理 Controller
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..services.inspection.device_config_service import (
    list_devices, add_device, update_device, delete_device, DeviceConfigError,
)

router = APIRouter()


class DeviceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    company: str = Field(..., min_length=1, max_length=100, pattern=r".*\S.*")


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    company: str | None = Field(default=None, max_length=100, pattern=r".*\S.*")


@router.get("/devices")
async def get_devices():
    return {"success": True, "data": list_devices()}


@router.post("/devices")
async def create_device(body: DeviceCreate):
    device = add_device(body.name, body.company)
    return {"success": True, "data": device}


@router.put("/devices/{device_id}")
async def update_device_endpoint(device_id: str, body: DeviceUpdate):
    try:
        result = update_device(
            device_id, name=body.name, company=body.company,
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
