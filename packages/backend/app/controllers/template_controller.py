"""Layer 22: approved template registry and case-selection HTTP boundary."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ..config import TEMPLATE_MAX_UPLOAD_SIZE
from ..repository.workbench_errors import WorkbenchPersistenceError
from ..services.workbench_factory_service import get_workbench_services

router = APIRouter()


class TemplateReferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class TemplateSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_ref: TemplateReferenceRequest
    expected_revision: int = Field(ge=0)
    lease_id: str = Field(min_length=1)
    lease_token: str = Field(min_length=1)


class TemplateDefaultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_ref: TemplateReferenceRequest
    expected_defaults_revision: int | None = Field(default=None, ge=0)


@router.get("/workbench/templates")
def list_templates_endpoint() -> dict[str, Any]:
    """Return only currently approved, revalidated, path-free versions."""
    try:
        templates = _template_service().list_available()
        return _envelope(templates)
    except Exception as error:
        _handle(error)


@router.get("/workbench/templates/management")
def list_template_management_endpoint() -> dict[str, Any]:
    try:
        return _envelope(_template_service().list_management())
    except Exception as error:
        _handle(error)


@router.put("/workbench/templates/default")
def set_template_default_endpoint(body: TemplateDefaultRequest) -> dict[str, Any]:
    try:
        result = _template_service().set_default(
            body.template_ref.model_dump(), body.expected_defaults_revision,
        )
        return _envelope(result)
    except Exception as error:
        _handle(error)


@router.post("/workbench/templates")
def add_template_endpoint(
    file: UploadFile = File(...),
    template_id: str = Form(...),
    version: str = Form(...),
    display_name: str = Form(...),
) -> dict[str, Any]:
    services = get_workbench_services()
    staged_path: Path | None = None
    registered = False
    try:
        staged_path = _stage_template_upload(file, services.database.database_path.parent)
        result = _template_service(services).register_uploaded(
            {"template_id": template_id, "version": version}, display_name, staged_path,
        )
        registered = True
        return _envelope(result)
    except Exception as error:
        _handle(error)
    finally:
        if staged_path is not None and not registered:
            staged_path.unlink(missing_ok=True)


@router.delete("/workbench/templates/{template_id}/{version}")
def remove_template_endpoint(template_id: str, version: str) -> dict[str, Any]:
    try:
        result = _template_service().remove({"template_id": template_id, "version": version})
        return _envelope(result)
    except Exception as error:
        _handle(error)


@router.put("/workbench/cases/{case_id}/template")
def select_case_template_endpoint(
    case_id: str, body: TemplateSelectionRequest,
) -> dict[str, Any]:
    """Persist only a selected ID/version under lease and revision protection."""
    try:
        services = get_workbench_services()
        services.leases.assert_active_for_case(
            case_id, body.lease_id, body.lease_token,
        )
        result = _template_service(services).select_for_case(
            case_id, body.template_ref.model_dump(), body.expected_revision,
        )
        return _envelope(result)
    except Exception as error:
        _handle(error)


def _template_service(services: Any | None = None) -> Any:
    services = services or get_workbench_services()
    if services.templates is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "TEMPLATE_REGISTRY_UNAVAILABLE",
                "message": "模板注册表暂不可用，请稍后重试。",
            },
        )
    return services.templates


def _stage_template_upload(upload: UploadFile, data_root: Path) -> Path:
    filename = upload.filename or ""
    if Path(filename).suffix.casefold() != ".docx":
        raise WorkbenchPersistenceError("TEMPLATE_UPLOAD_INVALID")
    asset_root = data_root / "template-assets"
    asset_root.mkdir(parents=True, exist_ok=True)
    destination = asset_root / f"uploaded-template-{secrets.token_hex(16)}.docx"
    total = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > TEMPLATE_MAX_UPLOAD_SIZE:
                    raise WorkbenchPersistenceError("TEMPLATE_UPLOAD_TOO_LARGE")
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if total == 0:
        destination.unlink(missing_ok=True)
        raise WorkbenchPersistenceError("TEMPLATE_UPLOAD_INVALID")
    return destination


def _envelope(data: Any) -> dict[str, Any]:
    return {"api_version": "v1", "schema_version": 1, "data": data}


def _handle(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    code = getattr(error, "code", None)
    if not isinstance(code, str):
        code = "TEMPLATE_REQUEST_FAILED"
    status = (
        404 if code in {"TEMPLATE_UNKNOWN", "DRAFT_NOT_FOUND"}
        else 409 if code in {
            "REVISION_CONFLICT", "LEASE_CONFLICT", "LEASE_NOT_ACTIVE",
            "LEASE_EXPIRED", "LEASE_TAKEOVER_REQUIRED", "DEFAULT_TEMPLATE_CANNOT_DELETE",
            "TEMPLATE_IN_USE", "TEMPLATE_VERSION_IMMUTABLE",
            "HISTORICAL_TEMPLATE_READ_ONLY",
        }
        else 422 if code in {
            "TEMPLATE_NOT_APPROVED", "TEMPLATE_ASSET_MISSING",
            "TEMPLATE_FINGERPRINT_MISMATCH", "TEMPLATE_RULE_VALIDATION_FAILED",
            "INVALID_TEMPLATE_REFERENCE", "FORBIDDEN_OPAQUE_ID", "INVALID_OPAQUE_ID",
            "INVALID_TEMPLATE_VERSION", "TEMPLATE_UPLOAD_INVALID",
        }
        else 413 if code == "TEMPLATE_UPLOAD_TOO_LARGE"
        else 500
    )
    raise HTTPException(
        status_code=status,
        detail={"code": code, "message": _safe_message(code)},
    ) from error


def _safe_message(code: str) -> str:
    return {
        "TEMPLATE_UNKNOWN": "所选模板版本不存在。",
        "TEMPLATE_NOT_APPROVED": "所选模板版本未通过审核。",
        "TEMPLATE_ASSET_MISSING": "所选模板资产不可用。",
        "TEMPLATE_FINGERPRINT_MISMATCH": "所选模板指纹校验失败。",
        "TEMPLATE_RULE_VALIDATION_FAILED": "所选模板结构校验失败。",
        "REVISION_CONFLICT": "案件已被其他会话修改，请重新读取后再选择模板。",
        "LEASE_CONFLICT": "案件当前由其他编辑会话占用。",
        "LEASE_NOT_ACTIVE": "当前编辑租约已失效，请重新获取后再选择模板。",
        "LEASE_EXPIRED": "当前编辑租约已过期，请重新获取后再选择模板。",
        "LEASE_TAKEOVER_REQUIRED": "编辑租约需要确认接管。",
        "DRAFT_NOT_FOUND": "案件草稿不存在，不能选择模板。",
        "INVALID_TEMPLATE_REFERENCE": "模板版本引用无效。",
        "DEFAULT_TEMPLATE_CANNOT_DELETE": "默认模板不能直接删除，请先选择其他默认模板。",
        "TEMPLATE_IN_USE": "已有案件引用该模板版本，不能删除。",
        "TEMPLATE_VERSION_IMMUTABLE": "相同模板 ID 和版本已经存在，不能覆盖。",
        "HISTORICAL_TEMPLATE_READ_ONLY": "历史内置模板仅供既有案件重导出，不能用于新选择、默认设置或删除。",
        "TEMPLATE_UPLOAD_INVALID": "请上传有效的 DOCX 模板文件。",
        "TEMPLATE_UPLOAD_TOO_LARGE": "模板文件不能超过 50MB。",
    }.get(code, "模板请求未完成，请稍后重试。")
