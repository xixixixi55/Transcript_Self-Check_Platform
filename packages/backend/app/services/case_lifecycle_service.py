"""Case reads, revision-checked saves, lifecycle guards and delete checks."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

from ..repository.audit_event_repository import AuditEventRepository
from ..repository.archive_task_repository import ArchiveTaskRepository
from ..repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ..repository.case_workflow_repository import CaseWorkflowRepository
from ..repository.task_record_repository import TaskRecordRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .case_order_service import CaseOrderService
from .field_provenance_service import FieldProvenanceService


class CaseLifecycleService:
    def __init__(
        self, database: WorkbenchDatabase, asset_service: Any = None,
        artifact_deletion_service: Any = None,
    ) -> None:
        self.shells = CaseShellRepository(database)
        self.drafts = CaseDraftRepository(database)
        self.tasks = TaskRecordRepository(database)
        self.workflow = CaseWorkflowRepository(database)
        self.audit = AuditEventRepository(database)
        self.assets = asset_service
        self.artifacts = artifact_deletion_service
        self.archive_tasks = ArchiveTaskRepository(database)

    def list(self, offset: int, limit: int) -> dict[str, Any]:
        if offset < 0 or limit < 1 or limit > 100:
            raise WorkbenchPersistenceError("INVALID_PAGE")
        items = self.shells.list(offset, limit + 1)
        public_items = [
            {**item, "archive_task_summary": self.archive_tasks.get_card_summary(item["case_id"])}
            for item in items[:limit]
        ]
        return {"items": public_items, "offset": offset, "limit": limit, "has_more": len(items) > limit}

    def detail(self, case_id: str) -> dict[str, Any]:
        for _ in range(3):
            shell = self.shells.get(case_id)
            if shell["record_cleaned"]:
                return {"shell": shell, "draft": None, "source": None, "parse_task": None}
            task = self.tasks.get(shell["parse_task_id"])
            source = self._source_public(case_id)
            draft = None
            try:
                draft = self.drafts.get(case_id)
            except WorkbenchPersistenceError as error:
                if error.code != "DRAFT_NOT_FOUND":
                    raise
            if self.shells.get(case_id)["revision"] == shell["revision"]:
                return {
                    "shell": {
                        **shell,
                        "archive_task_summary": self.archive_tasks.get_card_summary(case_id),
                    },
                    "draft": draft,
                    "source": source,
                    "parse_task": task,
                }
        raise WorkbenchPersistenceError("CASE_DETAIL_CHANGED_DURING_READ")

    def save_draft(
        self,
        draft: Mapping[str, Any],
        expected_revision: int,
        shared_values: Mapping[str, Any] | None,
        shared_revision: int | None,
        identity: Mapping[str, Any] | None = None,
        lease_id: str | None = None,
        lease_token: str | None = None,
    ) -> dict[str, Any]:
        draft_status: dict[str, Any]
        defaults_status: dict[str, Any]
        case_id = str(draft["case_id"])
        previous = self._draft_or_none(case_id)
        normalized_draft = dict(draft)
        normalized_report = CaseOrderService().prepare_save(
            (previous or {}).get("report"), draft.get("report", {}),
        )
        normalized_draft["report"] = normalized_report
        normalized_draft["field_states"] = FieldProvenanceService().reconcile(
            (previous or {}).get("report", {}), (previous or {}).get("field_states", {}),
            normalized_report, draft.get("field_states"),
        )
        previous_ids = {str(item["asset_id"]) for item in (previous or {}).get("asset_refs", [])}
        next_ids = {str(item["asset_id"]) for item in normalized_draft.get("asset_refs", [])}
        if previous_ids != next_ids:
            if self.assets is None or not lease_id or not lease_token:
                raise WorkbenchPersistenceError("LEASE_NOT_ACTIVE")
            self.assets.leases.assert_active_for_case(case_id, lease_id, lease_token)
        try:
            saved = self.drafts.save(normalized_draft, expected_revision=expected_revision)
            draft_status = {"status": "saved", "revision": saved["revision"]}
        except RevisionConflictError as error:
            draft_status = {"status": "conflict", "error_code": error.code}
            saved = None
        except WorkbenchPersistenceError as error:
            draft_status = {"status": "failed", "error_code": error.code}
            saved = None
        if saved is not None and self.assets is not None:
            self.assets.release_unreferenced(case_id, sorted(previous_ids - next_ids))
        if shared_values is None or not shared_values:
            defaults_status = {"status": "unchanged", "revision": self._defaults_revision()}
        elif draft_status["status"] != "saved":
            defaults_status = {"status": "failed", "error_code": "DRAFT_SAVE_NOT_APPLIED"}
        elif shared_revision is None:
            defaults_status = {"status": "failed", "error_code": "REVISION_REQUIRED"}
        else:
            try:
                from .shared_defaults_service import SharedDefaultsService
                result = SharedDefaultsService(self._database()).patch(shared_values, shared_revision, identity or {})
                defaults_status = {
                    "status": result["status"],
                    "revision": result["defaults"]["revision"],
                }
            except RevisionConflictError as error:
                defaults_status = {
                    "status": "revision_conflict",
                    "error_code": error.code,
                    "revision": self._defaults_revision(),
                }
            except WorkbenchPersistenceError as error:
                defaults_status = {
                    "status": "failed",
                    "error_code": error.code,
                    "revision": self._defaults_revision(),
                }
        if identity and draft_status["status"] == "saved":
            self._record_save(identity, str(draft["case_id"]))
        return {
            "draft_save_status": draft_status,
            "shared_defaults_save_status": defaults_status,
            "draft": saved,
        }

    def _draft_or_none(self, case_id: str) -> dict[str, Any] | None:
        try:
            return self.drafts.get(case_id)
        except WorkbenchPersistenceError as error:
            if error.code == "DRAFT_NOT_FOUND":
                return None
            raise

    def transition(self, case_id: str, target: str, expected_revision: int) -> dict[str, Any]:
        if target == "archive_queued":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_REQUIRED")
        if target in {"archiving", "archive_verified", "exporting_word", "exported"}:
            raise WorkbenchPersistenceError("WORKBENCH_ARCHIVE_NOT_IMPLEMENTED")
        return self.shells.update_lifecycle(case_id, target, expected_revision)

    def decide_archive(
        self, case_id: str, decision: str, expected_revision: int,
        identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.workflow.decide_archive(case_id, decision, expected_revision)
        if identity is not None:
            self.audit.record({
                "event_id": f"audit-{secrets.token_hex(16)}", "event_type": "archive_decision",
                **identity, "case_id": case_id, "payload": {"decision": decision}, "created_at": utc_now(),
            })
        return self.detail(case_id)

    def delete_preflight(self, case_id: str) -> dict[str, Any]:
        return self.workflow.delete_preflight(case_id)

    def delete_case(self, case_id: str) -> dict[str, Any]:
        plan = self.artifacts.prepare(case_id) if self.artifacts is not None else None
        if plan is not None:
            self.artifacts.cleanup(plan)
        result = self.workflow.delete_case(case_id)
        if plan is not None:
            self.artifacts.remove_manifest_index(plan)
        return result

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
