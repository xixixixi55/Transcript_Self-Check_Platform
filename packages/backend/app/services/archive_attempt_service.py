"""Phase 1D archive-attempt boundary around the existing Legacy executor."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Any

from ..repository.archive_attempt_repository import ArchiveAttemptRepository
from ..repository.source_record_repository import SourceRecordRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_staging_security_service import (
    cleanup_owned_staging,
    controlled_staging_root_id,
    remove_ownership_marker,
    write_ownership_marker,
)
from ..repository.workbench_serialization import validate_opaque_id


class ArchiveAttemptService:
    def __init__(self, database: WorkbenchDatabase, output_root: str | Path) -> None:
        self.database = database
        self.repository = ArchiveAttemptRepository(database)
        self.sources = SourceRecordRepository(database)
        self.staging_root = Path(output_root) / "compressed" / ".staging"
        self.staging_root_id = controlled_staging_root_id(
            self.staging_root, database.deployment_instance_id,
        )
        self._context_lock = Lock()
        self._runtime_contexts: dict[str, str] = {}

    def accept(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int,
    ) -> dict[str, Any]:
        self._require_archive_source(source_id)
        context_id = validate_opaque_id(context_id)
        result = self.repository.accept(
            case_id, source_id, source_revision, expected_case_revision,
        )
        self._remember_context(result["attempt_id"], context_id)
        return result

    def start(self, attempt_id: str) -> dict[str, Any]:
        return self.repository.mark_running(attempt_id)

    def reissue_context(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int,
    ) -> dict[str, Any]:
        self._require_archive_source(source_id)
        context_id = validate_opaque_id(context_id)
        result = self.repository.reissue_context(
            case_id, source_id, source_revision, expected_case_revision,
        )
        self._remember_context(result["attempt_id"], context_id)
        return result

    def context_matches(self, attempt_id: str, context_id: str) -> bool:
        try:
            attempt_id = validate_opaque_id(attempt_id)
            context_id = validate_opaque_id(context_id)
        except WorkbenchPersistenceError:
            return False
        with self._context_lock:
            return self._runtime_contexts.get(attempt_id) == context_id

    def succeed(self, attempt_id: str, manifest_id: str) -> dict[str, Any]:
        return self.repository.mark_succeeded(attempt_id, manifest_id)

    def fail(self, attempt_id: str, error_code: str) -> dict[str, Any]:
        result = self.repository.mark_failed(attempt_id, error_code)
        self.repository.interrupt_case(attempt_id)
        record = self.repository.get_internal(attempt_id)
        if record["staging_locator"]:
            cleanup = cleanup_owned_staging(
                record, self.staging_root, self.database.deployment_instance_id,
            )
            if cleanup != "not_required":
                cleanup_error = "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
                if cleanup == "failed":
                    cleanup_error = "ARCHIVE_STAGING_CLEANUP_FAILED"
                result = self.repository.mark_cleanup(attempt_id, cleanup, cleanup_error)
        return result

    def staging_initializer(self, attempt_id: str) -> Callable[[Path], None]:
        root_id = self.staging_root_id
        deployment_id = self.database.deployment_instance_id

        def initialize(staging_dir: Path) -> None:
            token = write_ownership_marker(staging_dir, attempt_id, deployment_id, root_id)
            try:
                self.repository.bind_staging(attempt_id, str(staging_dir), root_id, token)
            except Exception:
                remove_ownership_marker(staging_dir)
                raise

        return initialize

    def process_started_callback(self, attempt_id: str) -> Callable[[int], None]:
        return lambda pid: self.repository.bind_process(attempt_id, pid, utc_now())

    def remove_marker(self, staging_dir: Path) -> None:
        remove_ownership_marker(staging_dir)

    def recover_after_restart(self) -> list[str]:
        with self._context_lock:
            self._runtime_contexts.clear()
        interrupted = self.repository.recover_unfinished()
        for record in interrupted:
            cleanup = cleanup_owned_staging(
                record, self.staging_root, self.database.deployment_instance_id,
            )
            if cleanup != "not_required":
                error_code = "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
                if cleanup == "failed":
                    error_code = "ARCHIVE_STAGING_CLEANUP_FAILED"
                self.repository.mark_cleanup(record["attempt_id"], cleanup, error_code)
        return [str(record["attempt_id"]) for record in interrupted]

    def _remember_context(self, attempt_id: str, context_id: str) -> None:
        with self._context_lock:
            self._runtime_contexts[validate_opaque_id(attempt_id)] = context_id

    def _require_archive_source(self, source_id: str) -> None:
        status = self.sources.get(source_id)["access_status"]
        if status == "pending":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING")
        if status != "available":
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
