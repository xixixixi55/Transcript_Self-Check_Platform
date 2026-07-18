"""Layer 22: archive execution endpoint used before document export."""

from __future__ import annotations

import json

from fastapi import APIRouter, Form, HTTPException

from ..services.archive_execution_service import (
    ArchiveGateError,
    execute_archive,
)
from ..services.archive_runtime_service import ArchiveRuntimeError
from ..services.software_policy_service import normalize_primary_software_projection
from .record_controller import OUTPUT_BASE


router = APIRouter()


def _blocker(code: object, field: str = "archive", message: str = "归档门控未通过。") -> dict[str, str]:
    value = code.value if hasattr(code, "value") else str(code)
    return {"code": value, "field": field, "message": message}


def _archive_error(error: Exception) -> HTTPException:
    if isinstance(error, ArchiveGateError):
        return HTTPException(
            status_code=422,
            detail={"code": "EXPORT_BLOCKED", "blockers": [
                _blocker(item.code, item.field, item.message) for item in error.blockers
            ]},
        )
    if isinstance(error, ArchiveRuntimeError):
        return HTTPException(
            status_code=422,
            detail={"code": error.code, "blockers": [
                _blocker(error.code, message=error.safe_message)
            ]},
        )
    return HTTPException(status_code=422, detail={"code": "ARCHIVE_EXECUTION_FAILED", "blockers": [
        _blocker("ARCHIVE_EXECUTION_FAILED", message="归档执行失败，请检查后重试。")
    ]})


@router.post("/records/archive")
async def execute_archive_endpoint(
    report_json: str = Form(""),
    archive_context_id: str = Form(""),
):
    """Execute the reviewed archive synchronously; no client path is accepted."""

    if not report_json or not archive_context_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "ARCHIVE_CONTEXT_INVALID", "blockers": [
                _blocker("ARCHIVE_CONTEXT_INVALID", message="归档上下文无效，请重新解析报告。")
            ]},
        )
    try:
        report = normalize_primary_software_projection(json.loads(report_json))
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="笔录数据 JSON 格式无效")
    try:
        outcome = execute_archive(
            archive_context_id, report, output_root=OUTPUT_BASE,
        )
    except Exception as error:
        raise _archive_error(error) from error
    return {
        "success": True,
        "data": {
            "status": outcome.status,
            "manifest_id": outcome.manifest_id,
            "plan": outcome.plan.public_dict() if outcome.plan else None,
            "diagnostics": [item.__dict__ for item in outcome.diagnostics],
            "reused": outcome.reused,
        },
    }
