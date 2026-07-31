"""
Layer 23: BE_Routes — FastAPI 应用入口与路由注册

笔录自检平台（文枢）后端服务
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as api_router
from .services.pipeline_runtime_service import load_pipeline_settings
from .services.workbench_factory_service import (
    WorkbenchServices,
    get_workbench_services,
)

logger = logging.getLogger(__name__)


def create_app(
    *,
    service_provider: Callable[[], WorkbenchServices] | None = None,
    enable_archive_runtime: bool = True,
) -> FastAPI:
    """Build the API without starting workers until FastAPI lifespan startup."""
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

    app = FastAPI(
        title="笔录自检平台（文枢）",
        description="电子数据检查笔录自动生成平台 API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Read the migration mode once per application instance. Controllers receive
    # the same immutable settings object; parsers and renderers do not read env.
    app.state.pipeline_settings = load_pipeline_settings()

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

    return app


app = create_app()
