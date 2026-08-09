"""Layer 22: resolve the persisted case template for formal export."""

from __future__ import annotations

from fastapi import HTTPException

from ..services.disc_mapping_service import DiscMappingState, resolve_disc_mapping_state
from ..services.workbench_factory_service import get_workbench_services


def resolve_case_template_context(
    case_id: str, case_revision: int | None,
    *, require_current_revision: bool = True,
) -> dict[str, object]:
    """Return generator dependencies without trusting client template metadata.

    ``require_current_revision`` only guards against exporting a stale draft
    (the caller passes the draft revision the client last saw).  The unified
    export flow keeps the optimistic concurrency check on the case shell inside
    ``archive_export_service.export_bundle`` and must not also require the shell
    revision to equal the independent draft revision, which legitimately
    diverges across lifecycle transitions.
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
    if require_current_revision and draft["revision"] != case_revision:
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


def resolve_case_disc_mapping(case_id: str) -> DiscMappingState:
    """Resolve plan presence and its authoritative mapping for case export."""
    if not case_id:
        return DiscMappingState(plan_exists=False, first_disc_number=None)
    services = get_workbench_services()
    return resolve_disc_mapping_state(services.database, case_id)


def _reject(
    status: int, code: str, message: str, cause: Exception | None = None,
) -> None:
    error = HTTPException(status_code=status, detail={"code": code, "message": message})
    if cause is not None:
        raise error from cause
    raise error
