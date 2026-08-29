"""第 22 层：服务器端缓存的安全生命周期控制。"""

import os

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..config import OUTPUT_BASE
from ..services.report.report_parsing_cache_service import (
    ReportParsingCacheError,
    clear_report_parsing_cache,
)


router = APIRouter()


@router.delete("/cache/report-parsing")
async def clear_report_parsing_cache_endpoint():
    """仅清除已配置的报告解析缓存；不接受客户端路径。"""
    try:
        cleared_count = await run_in_threadpool(
            clear_report_parsing_cache, os.path.join(OUTPUT_BASE, "parsed"),
        )
    except ReportParsingCacheError as error:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "REPORT_PARSING_CACHE_CLEAR_FAILED",
                "message": "解析缓存清理失败，请稍后重试。",
            },
        ) from error
    return {"success": True, "data": {"cleared_count": cleared_count}}
