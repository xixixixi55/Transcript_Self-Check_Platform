"""Case reads, revision-checked saves, lifecycle guards and delete checks."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

from ..repository.audit_event_repository import AuditEventRepository
from ..repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ..repository.case_workflow_repository import CaseWorkflowRepository
from ..repository.task_record_repository import TaskRecordRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import RevisionConflictError, WorkbenchPersistenceError


class CaseLifecycleService:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.shells = CaseShellRepository(database)
        self.drafts = CaseDraftRepository(database)
        self.tasks = TaskRecordRepository(database)
        self.workflow = CaseWorkflowRepository(database)
        self.audit = AuditEventRepository(database)

    def list(self, offset: int, limit: int) -> dict[str, Any]:
        if offset < 0 or limit < 1 or limit > 100:
            raise WorkbenchPersistenceError("INVALID_PAGE")
        items = self.shells.list(offset, limit + 1)
        return {"items": items[:limit], "offset": offset, "limit": limit, "has_more": len(items) > limit}

    def detail(self, case_id: str) -> dict[str, Any]:
        shell = self.shells.get(case_id)
        task = self.tasks.get(shell["parse_task_id"])
        source = self._source_public(case_id)
        draft = None
        try:
            draft = self.drafts.get(case_id)
        except WorkbenchPersistenceError as error:
            if error.code != "DRAFT_NOT_FOUND":
                raise
        return {"shell": shell, "draft": draft, "source": source, "parse_task": task}

    def save_draft(
        self,
        draft: Mapping[str, Any],
        expected_revision: int,
        shared_values: Mapping[str, Any] | None,
        shared_revision: int | None,
        identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        draft_status: dict[str, Any]
        defaults_status: dict[str, Any]
        try:
            saved = self.drafts.save(draft, expected_revision=expected_revision)
            draft_status = {"status": "saved", "revision": saved["revision"]}
        except RevisionConflictError as error:
            draft_status = {"status": "conflict", "error_code": error.code}
            saved = None
        except WorkbenchPersistenceError as error:
            draft_status = {"status": "failed", "error_code": error.code}
            saved = None
        if shared_values is None:
            defaults_status = {"status": "saved", "revision": self._defaults_revision()}
        elif draft_status["status"] != "saved":
            defaults_status = {"status": "failed", "error_code": "DRAFT_SAVE_NOT_APPLIED"}
        elif shared_revision is None:
            defaults_status = {"status": "failed", "error_code": "REVISION_REQUIRED"}
        else:
            try:
                from .shared_defaults_service import SharedDefaultsService
                updated = SharedDefaultsService(self._database()).save(shared_values, shared_revision, identity or {})
                defaults_status = {"status": "saved", "revision": updated["revision"]}
            except RevisionConflictError as error:
                defaults_status = {"status": "conflict", "error_code": error.code}
            except WorkbenchPersistenceError as error:
                defaults_status = {"status": "failed", "error_code": error.code}
        if identity and draft_status["status"] == "saved":
            self._record_save(identity, str(draft["case_id"]))
        return {
            "draft_save_status": draft_status,
            "shared_defaults_save_status": defaults_status,
            "draft": saved,
        }

    def transition(self, case_id: str, target: str, expected_revision: int) -> dict[str, Any]:
        if target in {"archiving", "archive_verified", "exporting_word", "exported"}:
            raise WorkbenchPersistenceError("WORKBENCH_ARCHIVE_NOT_IMPLEMENTED")
        return self.shells.update_lifecycle(case_id, target, expected_revision)

    def delete_preflight(self, case_id: str) -> dict[str, Any]:
        return self.workflow.delete_preflight(case_id)

    def _source_public(self, case_id: str) -> dict[str, Any]:
        row = self.shells.database.connect()
        try:
            source_id = row.execute("SELECT source_id FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()[0]
        finally:
            row.close()
        from ..repository.source_record_repository import SourceRecordRepository
        return SourceRecordRepository(self.shells.database).get(source_id)

    def _defaults_revision(self) -> int:
        from ..repository.shared_defaults_repository import SharedDefaultsRepository
        return SharedDefaultsRepository(self.shells.database).get()["revision"]

    def _database(self) -> WorkbenchDatabase:
        return self.shells.database

    def _record_save(self, identity: Mapping[str, Any], case_id: str) -> None:
        self.audit.record({
            "event_id": f"audit-{secrets.token_hex(16)}", "event_type": "case_draft_saved",
            **identity, "case_id": case_id, "payload": {}, "created_at": utc_now(),
        })
