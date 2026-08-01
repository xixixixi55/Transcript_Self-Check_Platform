"""Server-fact revalidation immediately before archive publication."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..repository.archive_context_binding_repository import find_active_binding_for_attempt, report_fingerprint
from ..repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ..repository.workbench_errors import WorkbenchPersistenceError


def expired(value: object) -> bool:
    if value is None:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True


def revalidate_before_publish(service: Any, attempt_id: str, report: object) -> None:
    attempt = service.repository.get_internal(attempt_id)
    binding = find_active_binding_for_attempt(service.database, attempt_id)
    shell = CaseShellRepository(service.database).get(attempt["case_id"])
    source = service.sources.get(attempt["source_id"])
    draft = CaseDraftRepository(service.database).get(attempt["case_id"])
    if (
        not binding or expired(binding.get("expires_at")) or binding["context_kind"] != "workbench"
        or binding["case_id"] != attempt["case_id"] or binding["source_id"] != attempt["source_id"]
        or binding["source_revision"] != int(attempt["source_revision"])
        or binding["draft_revision"] != int(attempt["draft_revision"])
        or binding["report_fingerprint"] != attempt["report_fingerprint"]
        or shell["source_id"] != attempt["source_id"]
        or shell["lifecycle"] not in {"archive_queued", "archiving"}
        or source["access_status"] != "available"
        or int(source["revision"]) != int(attempt["source_revision"])
        or int(draft["revision"]) != int(attempt["draft_revision"])
        or report_fingerprint(draft["report"]) != attempt["report_fingerprint"]
        or report_fingerprint(report) != attempt["report_fingerprint"]
    ):
        raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
