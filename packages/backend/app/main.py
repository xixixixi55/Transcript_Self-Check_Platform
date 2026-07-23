"""
Layer 23: BE_Routes — FastAPI 应用入口与路由注册

笔录自检平台（文枢）后端服务
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as api_router
from .services.pipeline_runtime_service import load_pipeline_settings

app = FastAPI(
    title="笔录自检平台（文枢）",
    description="电子数据检查笔录自动生成平台 API",
    version="0.1.0",
)

# Read the migration mode once at application startup. Controllers receive the
# same immutable settings object; parsers and renderers do not read the env.
app.state.pipeline_settings = load_pipeline_settings()

# CORS 配置（开发阶段允许前端跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:30000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "service": "biji-zijian-platform"}
