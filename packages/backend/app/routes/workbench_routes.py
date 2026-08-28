"""第 23 层：持久化工作台路由聚合。"""

from fastapi import APIRouter

from ..controllers.case_asset_controller import router as asset_router
from ..controllers.archive_task_controller import router as archive_task_router
from ..controllers.defaults_controller import router as defaults_router
from ..controllers.lease_controller import router as lease_router
from ..controllers.source_controller import router as source_router
from ..controllers.template_controller import router as template_router
from ..controllers.workbench_controller import router as workbench_router

router = APIRouter()
router.include_router(archive_task_router, tags=["归档任务"])
router.include_router(asset_router, tags=["case-assets"])
router.include_router(template_router, tags=["案件模板"])
router.include_router(workbench_router, tags=["案件工作台"])
router.include_router(defaults_router, tags=["共享默认值"])
router.include_router(lease_router, tags=["编辑租约"])
router.include_router(source_router, tags=["报告来源"])
