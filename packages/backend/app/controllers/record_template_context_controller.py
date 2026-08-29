"""第 22 层：为正式导出解析持久化案件模板。"""

from __future__ import annotations

from fastapi import HTTPException

from ..services.archive.archive_export_service import resolve_case_word_manifest
from ..services.disc.disc_mapping_service import DiscMappingState, resolve_disc_mapping_state
from ..services.runtime.workbench_factory_service import get_workbench_services


def resolve_case_template_context(
    case_id: str, case_revision: int | None,
    *, require_current_revision: bool = True,
    allow_attachment2_revision_drift: bool = False,
    submitted_report: dict[str, object] | None = None,
) -> dict[str, object]:
    """返回生成器依赖，不信任客户端模板元数据。

    `require_current_revision` 仅用于防止导出过期草稿（调用方传入客户端最后看到的
    草稿修订号）。统一导出流程在 `archive_export_service.export_bundle` 内保留案件外壳的
    乐观并发检查，不能再要求外壳修订号等于独立的草稿修订号，因为二者会在生命周期
    转换期间合理分离。
    """
    if not case_id:
        if case_revision is not None:
            _reject(422, "CASE_ID_REQUIRED", "案件标识不能为空。")
        return {}
    if case_revision is None:
        _reject(422, "CASE_REVISION_REQUIRED", "案件版本不能为空。")
    try:
        services = get_workbench_services()
        draft = services.cases.drafts.get(case_id)
    except Exception as error:
        code = getattr(error, "code", "")
        status = 404 if code == "DRAFT_NOT_FOUND" else 422
        safe_code = code if isinstance(code, str) and code else "CASE_TEMPLATE_CONTEXT_INVALID"
        _reject(status, safe_code, "案件模板上下文不可用，请重新加载案件。", error)
    attachment2_only_drift = (
        allow_attachment2_revision_drift
        and case_revision < draft["revision"]
        and _differs_only_in_attachment2(draft.get("report"), submitted_report)
    )
    if require_current_revision and draft["revision"] != case_revision and not attachment2_only_drift:
        _reject(409, "REVISION_CONFLICT", "案件已被其他会话修改，请重新读取后再导出。")
    template_ref = draft.get("template_ref")
    if template_ref is None:
        return {}
    if services.template_registry is None or services.template_approvals is None:
        _reject(503, "TEMPLATE_REGISTRY_UNAVAILABLE", "模板注册表暂不可用，请稍后重试。")
    return {
        "template_ref": template_ref,
        "template_registry": services.template_registry,
        "template_approvals": services.template_approvals,
    }


def _differs_only_in_attachment2(current: object, submitted: object) -> bool:
    """允许后期绑定照片，同时不削弱普通草稿 CAS。"""
    if not isinstance(current, dict) or not isinstance(submitted, dict):
        return False

    def split(report: dict) -> tuple[dict, tuple[object, object]]:
        normalized = dict(report)
        attachments = report.get("attachments")
        if not isinstance(attachments, dict):
            return normalized, (None, None)
        normalized["attachments"] = {
            key: value for key, value in attachments.items()
            if key not in {"photo_ids", "photo_groups"}
        }
        photo_ids = attachments.get("photo_ids")
        photo_groups = attachments.get("photo_groups")
        return normalized, (
            [] if photo_ids is None else photo_ids,
            [] if photo_groups is None else photo_groups,
        )

    current_report, current_photos = split(current)
    submitted_report, submitted_photos = split(submitted)
    return current_report == submitted_report and current_photos != submitted_photos


def resolve_case_disc_mapping(case_id: str) -> DiscMappingState:
    """为案件导出解析计划是否存在及其权威映射。"""
    if not case_id:
        return DiscMappingState(plan_exists=False, first_disc_number=None)
    services = get_workbench_services()
    return resolve_disc_mapping_state(services.database, case_id)


def resolve_case_archive_manifest(case_id: str) -> dict[str, object] | None:
    """返回持久化案件的统一导出 Manifest 投影。"""
    if not case_id:
        return None
    services = get_workbench_services()
    if services.archive_api is None:
        _reject(503, "ARCHIVE_SERVICE_UNAVAILABLE", "归档服务暂不可用，请稍后重试。")
    try:
        return resolve_case_word_manifest(services.archive_api, case_id)
    except Exception as error:
        _reject(
            422, "ARCHIVE_RESULT_NOT_AVAILABLE",
            "已归档结果不可用，请重新完成归档后再导出。", error,
        )


def _reject(
    status: int, code: str, message: str, cause: Exception | None = None,
) -> None:
    error = HTTPException(status_code=status, detail={"code": code, "message": message})
    if cause is not None:
        raise error from cause
    raise error
