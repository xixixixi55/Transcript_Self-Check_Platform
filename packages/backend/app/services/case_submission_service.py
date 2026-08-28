"""第 21 层：路径和原生选择器提交共享的案件外壳创建。"""

from __future__ import annotations

from typing import Any


def submit_case(
    services: Any,
    source_path: str,
    *,
    case_name: str = "",
    case_summary: str = "",
    case_number: str | None = None,
    directory_grant_token: str | None = None,
    source_authorization_enabled: bool = True,
    client_instance_id: str = "local-client",
    session_id: str = "local-session",
    local_display_name: str | None = None,
) -> dict[str, Any]:
    identity = {
        "identity_kind": "local_session",
        "client_instance_id": client_instance_id or "local-client",
        "session_id": session_id or "local-session",
        "local_display_name": local_display_name,
        "deployment_instance_id": services.database.deployment_instance_id,
    }
    descriptor = services.sources.register_report_directory(
        source_path,
        directory_grant_token,
        source_authorization_enabled=source_authorization_enabled,
    )
    identifiers = services.cases.submit(
        descriptor,
        case_name=case_name,
        case_summary=case_summary,
        case_number=case_number,
        identity=identity,
        dispatch=lambda case_id, task_id: services.dispatcher.dispatch(
            services.cases, case_id, task_id,
        ),
    )
    detail = services.lifecycle.detail(identifiers["case_id"])
    return {
        **{key: detail[key] for key in ("shell", "source", "parse_task")},
        "shared_defaults": services.defaults.get(),
    }
