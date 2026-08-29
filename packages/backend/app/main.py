"""
Layer 23: BE_Routes — FastAPI 应用入口与路由注册

笔录自检平台（文枢）后端服务
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as api_router
from .routes.portable_web import configure_portable_web
from .services.runtime.pipeline_runtime_service import load_pipeline_settings
from .services.runtime.workbench_factory_service import (
    WorkbenchServices,
    get_workbench_services,
)

logger = logging.getLogger(__name__)


def create_app(
    *,
    service_provider: Callable[[], WorkbenchServices] | None = None,
    enable_archive_runtime: bool = True,
    portable_web_root: str | Path | None = None,
    desktop_secret: str | None = None,
) -> FastAPI:
    """构建 API；在 FastAPI 生命周期启动前不启动工作进程。"""
    provider = service_provider or get_workbench_services

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services = provider()
        app.state.workbench_services = services
        runtime = services.archive_runtime if enable_archive_runtime else None
        owns_runtime = bool(runtime and runtime.start())
        try:
            yield
        finally:
            if owns_runtime and runtime is not None:
                try:
                    stopped = runtime.stop()
                    if not stopped:
                        logger.error("Archive runtime shutdown exceeded its bounded wait.")
                except Exception:
                    logger.exception("Archive runtime shutdown failed safely.")
            services.dispatcher.shutdown(wait=False)

    app = FastAPI(
        title="笔录自检平台（文枢）",
        description="电子数据检查笔录自动生成平台 API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 每个应用实例只读取一次迁移模式。控制器接收同一个不可变设置对象；
    # 解析器和渲染器不读取环境变量。
    app.state.pipeline_settings = load_pipeline_settings()

    portable_mode = os.environ.get("BIJI_PORTABLE_MODE", "").strip() == "1"
    if not portable_mode and portable_web_root is None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:30000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """健康检查端点"""
        return {"status": "ok", "service": "biji-zijian-platform"}

    if portable_mode or portable_web_root is not None:
        if portable_web_root is None:
            raise RuntimeError("PORTABLE_WEB_ROOT_REQUIRED")
        root = Path(portable_web_root)
        secret = desktop_secret or os.environ.get("BIJI_DESKTOP_SECRET", "")
        configure_portable_web(app, root, secret)

    return app


app = create_app() if os.environ.get("BIJI_PORTABLE_MODE", "").strip() != "1" else None
