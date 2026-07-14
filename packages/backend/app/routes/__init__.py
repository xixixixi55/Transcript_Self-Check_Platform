"""
Layer 23: BE_Routes — 路由定义与中间件编排

各资源路由在此聚合注册
"""

from fastapi import APIRouter

from ..controllers.record_controller import router as record_router
from ..controllers.device_controller import router as device_router

router = APIRouter()

# 注册子路由（record_controller 内部已定义完整路径 /reports/parse /records/export）
router.include_router(record_router, tags=["检查笔录"])
router.include_router(device_router, tags=["硬件设备"])
