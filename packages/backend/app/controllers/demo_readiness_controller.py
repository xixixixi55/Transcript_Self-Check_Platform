"""Layer 22: safe Demo readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ..config import OUTPUT_BASE
from ..services.demo_readiness_service import build_demo_readiness
from ..services.workbench_factory_service import get_workbench_services

router = APIRouter()


@router.get("/demo/readiness")
async def get_demo_readiness_endpoint():
    try:
        store = get_workbench_services().sources.authorization.store
    except Exception:
        store = None
    return {
        "api_version": "v1",
        "schema_version": 1,
        "data": build_demo_readiness(store, OUTPUT_BASE),
    }
