"""Layer 22: opaque SourceRecord read and revalidation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..services.workbench_factory_service import get_workbench_services

router = APIRouter()


@router.get("/workbench/sources/{source_id}")
async def get_source_endpoint(source_id: str):
    try:
        return _envelope(get_workbench_services().sources.get(source_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/sources/{source_id}/revalidate")
async def revalidate_source_endpoint(source_id: str):
    try:
        return _envelope(get_workbench_services().sources.revalidate(source_id))
    except Exception as error:
        _handle(error)


@router.post("/workbench/cases/{case_id}/source")
async def replace_case_source_endpoint(case_id: str, request: Request):
    form = await request.form()
    upload = form.get("archive_file")
    if not upload or not isinstance(getattr(upload, "filename", None), str) or not upload.filename or not hasattr(upload, "read"):
        _raise("SOURCE_REQUIRED", 422)
    import os
    suffix = os.path.splitext(upload.filename)[1].casefold()
    if suffix not in {".rar", ".zip"}:
        _raise("SOURCE_TYPE_UNSUPPORTED", 422)
    expected_revision = _form_int(form.get("expected_revision"))
    try:
        return _envelope(get_workbench_services().sources.replace_case_source(case_id, await upload.read(), suffix, expected_revision))
    except Exception as error:
        _handle(error)


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _handle(error: Exception) -> None:
    code = getattr(error, "code", "WORKBENCH_REQUEST_FAILED")
    status = 404 if code == "SOURCE_NOT_FOUND" else 409 if code in {"REVISION_CONFLICT", "SOURCE_REVISION_CONFLICT"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": "报告来源不可用，请重新选择来源。"}) from error


def _form_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail={"code": "REVISION_REQUIRED", "message": "revision is required"}) from None
    if parsed < 0:
        raise HTTPException(status_code=422, detail={"code": "REVISION_REQUIRED", "message": "revision is invalid"})
    return parsed


def _raise(code: str, status: int) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": "报告来源不可用，请重新选择来源。"})
