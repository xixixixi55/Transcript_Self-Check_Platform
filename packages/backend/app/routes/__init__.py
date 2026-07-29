"""
Layer 23: BE_Routes — 路由定义与中间件编排

各资源路由在此聚合注册
"""

from fastapi import APIRouter

from ..controllers.record_controller import router as record_router
from ..controllers.device_controller import router as device_router
from ..controllers.inspector_controller import router as inspector_router
from ..controllers.archive_controller import router as archive_router
from ..controllers.cache_controller import router as cache_router
from ..controllers.pipeline_controller import router as pipeline_router
from ..controllers.demo_readiness_controller import router as demo_readiness_router
from .workbench_routes import router as workbench_router

router = APIRouter()

# 注册子路由（record_controller 内部已定义完整路径 /reports/parse /records/export）
router.include_router(record_router, tags=["检查笔录"])
router.include_router(device_router, tags=["硬件设备"])
router.include_router(inspector_router, tags=["检查人员"])
router.include_router(archive_router, tags=["归档"])
router.include_router(cache_router, tags=["缓存"])
router.include_router(pipeline_router, tags=["管线诊断"])
router.include_router(workbench_router)
router.include_router(demo_readiness_router, tags=["Demo 就绪状态"])
