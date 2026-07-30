"""Layer 22: approved template registry and case-selection HTTP boundary."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

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


@router.get("/workbench/templates")
def list_templates_endpoint() -> dict[str, Any]:
    """Return only currently approved, revalidated, path-free versions."""
    try:
        templates = _template_service().list_available()
        return _envelope(templates)
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
            "LEASE_EXPIRED", "LEASE_TAKEOVER_REQUIRED",
        }
        else 422 if code in {
            "TEMPLATE_NOT_APPROVED", "TEMPLATE_ASSET_MISSING",
            "TEMPLATE_FINGERPRINT_MISMATCH", "TEMPLATE_RULE_VALIDATION_FAILED",
            "INVALID_TEMPLATE_REFERENCE", "FORBIDDEN_OPAQUE_ID",
        }
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
    }.get(code, "模板请求未完成，请稍后重试。")
