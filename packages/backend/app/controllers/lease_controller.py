"""Layer 22: case edit-lease DTO mapping."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..services.workbench_factory_service import get_workbench_services

router = APIRouter()


class LeaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: dict[str, Any]
    force_takeover: bool = False


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str
    now: datetime | None = None


class ReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str
    expected_revision: int | None = Field(default=None, ge=0)


@router.post("/workbench/cases/{case_id}/lease")
async def acquire_lease_endpoint(case_id: str, body: LeaseRequest):
    try:
        return _envelope(get_workbench_services().leases.acquire(case_id, body.identity, body.force_takeover))
    except Exception as error:
        _handle(error)


@router.post("/workbench/leases/{lease_id}/heartbeat")
async def heartbeat_lease_endpoint(lease_id: str, body: HeartbeatRequest):
    try:
        return _envelope(get_workbench_services().leases.heartbeat(lease_id, body.lease_token, body.now))
    except Exception as error:
        _handle(error)


@router.get("/workbench/leases/{lease_id}")
async def get_lease_endpoint(lease_id: str):
    try:
        return _envelope(get_workbench_services().leases.get(lease_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/leases/{lease_id}/release")
async def release_lease_endpoint(lease_id: str, body: ReleaseRequest):
    try:
        return _envelope(get_workbench_services().leases.release(lease_id, body.lease_token, body.expected_revision))
    except Exception as error:
        _handle(error)


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _handle(error: Exception) -> None:
    code = getattr(error, "code", "WORKBENCH_REQUEST_FAILED")
    status = 409 if code in {"LEASE_CONFLICT", "LEASE_TAKEOVER_REQUIRED", "REVISION_CONFLICT"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": "编辑租约请求未完成，请重试。"}) from error
