"""Public archive-task orchestration and deliberately safe projections."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..repository.archive_asset_repository import ArchiveAssetRepository
from ..repository.archive_plan_repository import ArchivePlanRepository
from ..repository.archive_task_repository import ArchiveTaskRepository
from ..repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ..repository.local_case_export_directory_repository import LocalCaseExportDirectoryRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_attempt_service import ArchiveAttemptService
from .archive_progress_service import ArchiveProgressService
from .archive_source_runtime_service import discard_preview_source
from .archive_task_result_service import ArchiveTaskResultService
from .source_record_service import SourceRecordService

if TYPE_CHECKING:
    from .archive_runtime_coordinator_service import ArchiveRuntimeCoordinator


class ArchiveTaskApiService:
    def __init__(
        self,
        database: WorkbenchDatabase,
        attempts: ArchiveAttemptService,
        sources: SourceRecordService,
        progress: ArchiveProgressService,
        runtime: ArchiveRuntimeCoordinator | None = None,
        legacy_output_roots: tuple[str | Path, ...] = (),
    ) -> None:
        self.database = database
        self.attempts = attempts
        self.sources = sources
        self.progress = progress
        self.runtime = runtime
        self.tasks = ArchiveTaskRepository(database)
        self.plans = ArchivePlanRepository(database)
        self.assets = ArchiveAssetRepository(database)
        self.results = ArchiveTaskResultService(
            self.tasks, self.plans, self.assets, attempts, legacy_output_roots,
        )
        self.shells = CaseShellRepository(database)
        self.drafts = CaseDraftRepository(database)
        self.export_directories = LocalCaseExportDirectoryRepository(
            database.database_path.parent / "case-export-directories.json",
        )

    def enqueue(self, case_id: str, expected_case_revision: int) -> dict[str, Any]:
        shell = self.shells.get(case_id)
        if shell["revision"] != expected_case_revision:
            raise WorkbenchPersistenceError("REVISION_CONFLICT")
        active = self.tasks.get_current_or_recent(case_id)
        if active and active["status"] in {"queued", "running", "cancelling", "blocked"}:
            active = self._reconcile_or_reject_active(active)
        # create_legacy_preview_source performs the bounded core-source check.
        # Do not run the same source check twice in one archive-decision request.
        context_id = self.sources.create_legacy_preview_source(case_id)
        task_id = f"archive-task-{secrets.token_hex(20)}"
        registered = False
        try:
            source = self.sources.get(shell["source_id"])
            attempt = self.attempts.accept(
                case_id, source["source_id"], source["revision"],
                context_id, expected_case_revision, task_id=task_id,
            )
            task = self.tasks.create({
                "task_id": task_id,
                "case_id": case_id,
                "status": "queued",
                "stage": "queued",
                "input_revision": self.drafts.get(case_id)["revision"],
                "attempt": len(self.tasks.get_history(case_id)) + 1,
                "created_at": utc_now(),
            })
            task = self.tasks.bind_attempt(task_id, attempt["attempt_id"])
            # The scheduler only claims process-local eligible IDs. Persist
            # the context lease after the durable attempt binding exists, then
            # expose the task through this coordinator's eligible set.
            if self.runtime is not None:
                self.runtime.register(task_id, context_id)
                registered = True
        except Exception:
            if registered and self.runtime is not None:
                self.runtime.unregister(task_id)
            if "task" in locals() and "attempt" in locals():
                try:
                    from ..repository.archive_runtime_context_lease_repository import (
                        interrupt_queued_runtime_context,
                    )
                    interrupt_queued_runtime_context(
                        self.attempts.database, task_id=task_id,
                    )
                except Exception:
                    pass
            discard_preview_source(context_id)
            if "attempt" in locals():
                try:
                    self.attempts.fail(attempt["attempt_id"], "ARCHIVE_TASK_CREATE_FAILED")
                except Exception:
                    pass
            raise
        return {
            "task": self.detail(task["task_id"]),
            "archive_context_id": context_id,
            "archive_attempt_id": attempt["attempt_id"],
        }

    def cancel(self, task_id: str, expected_revision: int) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        self._require_action(task, "cancel", expected_revision)
        result = self.progress.request_cancel(task_id, expected_revision)
        if result["status"] == "cancelled":
            if self.runtime is not None:
                self.runtime.unregister(task_id)
            attempt_id = (result.get("process_binding") or {}).get("staging_asset_id")
            if attempt_id:
                self.attempts.fail(str(attempt_id), "ARCHIVE_CANCELLED")
        return self.detail(task_id)

    def retry(
        self,
        task_id: str,
        expected_revision: int,
        expected_case_revision: int,
    ) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        self._require_action(task, "retry", expected_revision)
        current = self.tasks.get_current_or_recent(task["case_id"])
        if current is None or current["task_id"] != task_id:
            raise WorkbenchPersistenceError("ARCHIVE_TASK_STALE")
        return self.enqueue(task["case_id"], expected_case_revision)

    def progress_summary(self, task_id: str) -> dict[str, Any]:
        return self.tasks.get_task_card_summary(task_id)

    def detail(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        summary = self.tasks.get_task_card_summary(task_id)
        plan = self.plans.get_latest_for_case(task["case_id"])
        return {
            **summary,
            "created_at": task["created_at"],
            "revision": task["revision"],
            "attempt": task["attempt"],
            "cancel_requested": task["cancel_requested"],
            "error_code": (
                "ARCHIVE_MANIFEST_UNVERIFIED"
                if task["status"] == "succeeded" and summary["status"] != "succeeded"
                else task.get("error_code")
            ),
            "archive_plan": plan,
        }

    def history(self, case_id: str) -> dict[str, Any]:
        self.shells.get(case_id)
        return {
            "case_id": case_id,
            "items": [self.detail(task["task_id"]) for task in self.tasks.get_history(case_id)],
        }

    def result(self, task_id: str) -> dict[str, Any]:
        return self.results.result(task_id)

    def download_result_part(self, task_id: str, part_id: str) -> tuple[str, Any]:
        return self.results.download_part(task_id, part_id)

    def get_plan(self, case_id: str) -> dict[str, Any] | None:
        self.shells.get(case_id)
        return self.plans.get_latest_for_case(case_id)

    def update_mappings(
        self,
        case_id: str,
        mappings: list[dict[str, Any]],
        expected_revision: int,
    ) -> dict[str, Any]:
        current = self.tasks.get_current_or_recent(case_id)
        if current and current["status"] in {"queued", "running", "cancelling", "blocked", "succeeded"}:
            raise WorkbenchPersistenceError("ARCHIVE_MAPPING_LOCKED")
        plan = self.plans.get_latest_for_case(case_id)
        if plan is None:
            raise WorkbenchPersistenceError("ARCHIVE_PLAN_NOT_FOUND")
        return self.plans.update_mappings(plan["plan_id"], mappings, expected_revision)

    def map_disc_numbers(
        self,
        case_id: str,
        expected_revision: int,
        expected_plan_row_revision: int,
        first_disc_number: str,
    ) -> dict[str, Any]:
        """Generate the full sequence from the first disc number and persist it."""
        shell = self.shells.get(case_id)
        if shell["revision"] != expected_revision:
            raise WorkbenchPersistenceError("REVISION_CONFLICT")
        current = self.tasks.get_current_or_recent(case_id)
        if current and current["status"] in {"queued", "running", "cancelling", "blocked"}:
            raise WorkbenchPersistenceError("ARCHIVE_MAPPING_LOCKED")
        from .disc_mapping_service import DiscMappingError, apply_disc_mapping

        try:
            archive_mode = "standard_split"
            if current is not None and current["status"] == "succeeded":
                archive_mode = str(self.results.result(current["task_id"])["archive_mode"])
            result = apply_disc_mapping(
                self.database, case_id, expected_revision,
                expected_plan_row_revision, first_disc_number, archive_mode,
            )
            if current is not None:
                result["task_id"] = current["task_id"]
            return result
        except DiscMappingError as error:
            raise WorkbenchPersistenceError(error.code, error.args[0]) from error

    def export_bundle(
        self,
        case_id: str,
        expected_revision: int,
        export_path: str,
        *,
        directory_token: str,
        word_filename: str | None = None,
        template_context: dict[str, object],
    ) -> dict[str, Any]:
        from .archive_export_service import export_bundle as _export_bundle

        return _export_bundle(
            self, case_id, expected_revision, export_path,
            directory_token=directory_token,
            word_filename=word_filename,
            template_context=template_context,
        )

    def open_export_directory(self, case_id: str) -> dict[str, Any]:
        from .archive_export_service import open_latest_export_directory

        return open_latest_export_directory(self, case_id)

    @staticmethod
    def _require_action(
        task: dict[str, Any], action: str, expected_revision: int,
    ) -> None:
        if task["revision"] != expected_revision:
            raise WorkbenchPersistenceError("REVISION_CONFLICT")
        if action not in task["allowed_actions"]:
            raise WorkbenchPersistenceError(f"ARCHIVE_{action.upper()}_NOT_ALLOWED")

    def _reconcile_or_reject_active(self, task: dict[str, Any]) -> dict[str, Any]:
        attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
        attempt_status = None
        if attempt_id:
            try:
                attempt_status = self.attempts.repository.get_public(
                    str(attempt_id)
                )["status"]
            except WorkbenchPersistenceError:
                pass
        if task["status"] == "queued" and attempt_status in {"failed", "interrupted"}:
            if self.runtime is not None:
                self.runtime.unregister(task["task_id"])
            recovering = self.tasks.update_state(task["task_id"], {
                "status": "running",
                "worker_state": "recovering",
            }, task["revision"])
            return self.tasks.update_state(task["task_id"], {
                "status": "interrupted",
                "worker_state": "waiting_reclaim",
                "error_code": "ARCHIVE_WAITING_RECLAIM",
                "error_summary": "Archive task requires a new confirmed attempt.",
            }, recovering["revision"])
        raise WorkbenchPersistenceError("ARCHIVE_TASK_ALREADY_ACTIVE")
