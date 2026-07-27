"""Layer 22: case-bound image asset HTTP endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..services.workbench_factory_service import get_workbench_services

router = APIRouter()


@router.post("/workbench/cases/{case_id}/assets")
async def upload_case_asset_endpoint(
    case_id: str,
    photo: UploadFile = File(...),
    lease_id: str = Form(""),
    lease_token: str = Form(""),
):
    try:
        services = get_workbench_services()
        if services.assets is None:
            raise RuntimeError("asset service unavailable")
        content = await photo.read()
        return _envelope(services.assets.upload_image(
            case_id, photo.filename or "", content, lease_id, lease_token,
        ))
    except Exception as error:
        _handle(error)


@router.get("/workbench/cases/{case_id}/assets")
async def list_case_assets_endpoint(case_id: str):
    try:
        services = get_workbench_services()
        if services.assets is None:
            raise RuntimeError("asset service unavailable")
        return _envelope(services.assets.list_images(case_id))
    except Exception as error:
        _handle(error)


@router.get("/workbench/cases/{case_id}/assets/{asset_id}")
async def read_case_asset_endpoint(case_id: str, asset_id: str):
    try:
        services = get_workbench_services()
        if services.assets is None:
            raise RuntimeError("asset service unavailable")
        content, metadata = services.assets.read_image(case_id, asset_id)
        filename = str(metadata.get("file_name", "photo")).replace('"', "_")
        media_type = str(metadata.get("media_type", "application/octet-stream"))
        return Response(
            content=content, media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
    except Exception as error:
        _handle(error)


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _handle(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    code = getattr(error, "code", "WORKBENCH_REQUEST_FAILED")
    status = 404 if code in {"CASE_NOT_FOUND", "ASSET_NOT_FOUND", "ASSET_REFERENCE_NOT_FOUND"} else 409 if code in {"LEASE_NOT_ACTIVE", "LEASE_EXPIRED", "REVISION_CONFLICT"} else 422
    raise HTTPException(status_code=status, detail={"code": code, "message": _message(code)}) from error


def _message(code: str) -> str:
    return {
        "ASSET_IMAGE_FORMAT_INVALID": "鍥剧墖鏍煎紡涓嶆敮鎸侊紝璇峰厓鎴愪负 JPG 鎴?PNG 鍥剧墖銆?",
        "ASSET_IMAGE_INVALID": "鍥剧墖鏃犳硶璇诲彇鎴栨牸寮忎笉姝ｇ‘锛岃鏇存崲鍚庨噸璇曘€?",
        "ASSET_IMAGE_TOO_LARGE": "鍗曞紶鍥剧墖瓒呭嚭 10MB 闄愬埗銆?",
        "ASSET_IMAGE_COUNT_EXCEEDED": "妗堜欢鍥剧墖鏁伴噺瓒呭嚭闄愬埗銆?",
        "ASSET_CASE_SIZE_EXCEEDED": "妗堜欢鍥剧墖鎬诲ぇ灏忚秴鍑洪檺鍒躲€?",
        "ASSET_CONTENT_MISSING": "鍥剧墖璧勪骇缂哄け锛岃閲嶆柊涓婁紶銆?",
        "ASSET_CONTENT_CORRUPT": "鍥剧墖璧勪骇宸茬牬鎹燂紝璇烽噸鏂颁笂浼犮€?",
        "LEASE_NOT_ACTIVE": "当前页面没有有效编辑租约，不能修改图片。",
        "LEASE_EXPIRED": "编辑租约已失效，请重新获取后再修改图片。",
    }.get(code, "图片请求未完成，请稍后重试。")
