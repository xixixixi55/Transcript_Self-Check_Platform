"""报告解析边界的安全 HTTP 错误映射。"""

from __future__ import annotations

from fastapi import HTTPException

from ..archive.archive_runtime_service import ArchiveRuntimeError
from ..archive.archive_authorization_service import ArchiveAuthorizationError
from .report_parse_inflight_service import (
    ReportParseInFlightCapacityError,
    ReportParseInFlightError,
    ReportParseWaitTimeout,
)


def report_parse_http_error(error: Exception) -> HTTPException:
    if isinstance(error, ArchiveAuthorizationError):
        return HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.safe_message},
        )
    if isinstance(error, ArchiveRuntimeError):
        return HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.safe_message},
        )
    if isinstance(error, ReportParseInFlightCapacityError):
        return HTTPException(
            status_code=429,
            detail={
                "code": "PARSER_INFLIGHT_CAPACITY",
                "message": "报告解析任务容量已满，请稍后重试。",
            },
        )
    if isinstance(error, ReportParseWaitTimeout):
        return HTTPException(
            status_code=504,
            detail={
                "code": "PARSER_WAIT_TIMEOUT",
                "message": "报告解析任务仍在后台运行，请稍后重试。",
            },
        )
    if isinstance(error, ReportParseInFlightError):
        return HTTPException(
            status_code=503,
            detail={
                "code": "PARSER_INFLIGHT_UNAVAILABLE",
                "message": "报告解析任务暂时不可用，请稍后重试。",
            },
        )
    return HTTPException(
        status_code=422,
        detail="报告解析失败：报告结构缺失、格式不受支持或字段无效，请检查后重试。",
    )


__all__ = ["report_parse_http_error"]
