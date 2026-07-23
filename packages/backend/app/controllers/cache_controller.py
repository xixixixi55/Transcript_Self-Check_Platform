"""Layer 22: safe lifecycle controls for server-side caches."""

import os

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..config import OUTPUT_BASE
from ..services.report_parsing_cache_service import (
    ReportParsingCacheError,
    clear_report_parsing_cache,
)


router = APIRouter()


@router.delete("/cache/report-parsing")
async def clear_report_parsing_cache_endpoint():
    """Clear only the configured report parsing cache; no client path is accepted."""
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
