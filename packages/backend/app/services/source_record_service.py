"""目录来源授权、不透明持久化和重新验证。"""

from __future__ import annotations

import errno
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import OUTPUT_BASE, UPLOAD_BASE
from ..repository.archive.archive_authorization_repository import AuthorizedInputRoot
from ..repository.case_workbench_repository import CaseShellRepository
from ..repository.source_locator_repository import SourceLocatorRepository
from ..repository.source_record_repository import SourceRecordRepository
from ..repository.workbench_database import WorkbenchDatabase
from ..repository.workbench_errors import WorkbenchPersistenceError
from ..repository.report_format_adapter import ReportFormatError, require_supported_report_format
from .archive.archive_authorization_service import ArchiveAuthorizationService
from .source_record_fingerprint_service import (
    directory_summary,
    fingerprint as _fingerprint,
    fingerprint_with_metadata as _fingerprint_with_metadata,
    opaque_id,
    SourceFingerprintCancelledError,
    validate_pending_locator,
)


def is_temporary_source_failure(error: Exception) -> bool:
    if isinstance(error, FileNotFoundError):
        return False
    if isinstance(error, (PermissionError, TimeoutError, BlockingIOError, OSError)):
        return True
    return getattr(error, "code", None) in {
        "SOURCE_ACCESS_DENIED", "ARCHIVE_INPUT_ACCESS_DENIED", errno.EACCES,
    }


class SourceRecordService:
    def __init__(
        self,
        database: WorkbenchDatabase,
        authorization: ArchiveAuthorizationService | None = None,
    ) -> None:
        self.database = database
        self.repository = SourceRecordRepository(database)
        self.locators = SourceLocatorRepository(database)
        self.authorization = authorization or ArchiveAuthorizationService(UPLOAD_BASE, OUTPUT_BASE)

    _PENDING_FINGERPRINT_PREFIX = "pending:"
    _MAX_REVISION_CONFLICT_RETRIES = 3

    def register_report_directory(
        self,
        report_dir: str,
        grant_token: str | None = None,
        *,
        source_authorization_enabled: bool = True,
    ) -> dict[str, Any]:
        if not isinstance(report_dir, str) or not report_dir.strip():
            raise WorkbenchPersistenceError("SOURCE_DIRECTORY_REQUIRED")
        candidate = Path(report_dir)
        if candidate.is_file():
            if candidate.suffix.casefold() in {".rar", ".zip"}:
                raise WorkbenchPersistenceError("SOURCE_ARCHIVE_NOT_ALLOWED")
            raise WorkbenchPersistenceError("SOURCE_DIRECTORY_REQUIRED")
        authorized = self.authorization.authorize_report_directory(
            report_dir,
            grant_token=grant_token,
            source_authorization_enabled=source_authorization_enabled,
        )
        self._validate_report_structure(authorized.resolved_input_root)
        source_id = opaque_id("source")
        allowed_root = authorized.authorized_scope or authorized.resolved_input_root.parent
        try:
            metadata = directory_summary(authorized.resolved_input_root)
            self.locators.save(source_id, str(authorized.resolved_input_root), str(allowed_root))
        except OSError as error:
            self.locators.remove(source_id)
            raise WorkbenchPersistenceError("SOURCE_ACCESS_DENIED") from error
        return {
            "source_id": source_id,
            "source_type": "report_directory",
            "internal_path": f"locator://{source_id}",
            "allowed_root": f"root://{authorized.authorized_root_id}",
            "allowed_root_id": authorized.authorized_root_id,
            "metadata": metadata,
            "fingerprint": f"{self._PENDING_FINGERPRINT_PREFIX}{source_id}",
            "cleanup_path": None,
            "locator_id": source_id,
        }

    def get(self, source_id: str) -> dict[str, Any]:
        return self.repository.get(source_id)

    def replace_case_source(
        self, case_id: str, report_dir: str, expected_revision: int,
        grant_token: str | None = None,
        *,
        source_authorization_enabled: bool = True,
    ) -> dict[str, Any]:
        descriptor = self.register_report_directory(
            report_dir,
            grant_token,
            source_authorization_enabled=source_authorization_enabled,
        )
        committed = False
        try:
            shell = CaseShellRepository(self.database).get(case_id)
            descriptor.update({"case_id": case_id, "task_id": shell["parse_task_id"]})
            result = self.repository.replace_for_case(case_id, descriptor, expected_revision)
            committed = True
            return self.repository.get(result["source_id"])
        except Exception:
            if not committed:
                self.remove_unbound_source(descriptor)
            raise

    def revalidate(
        self, source_id: str, should_cancel: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        record = self.repository.get(source_id)
        if (
            record["access_status"] == "pending"
            and str(record.get("fingerprint", "")).startswith(self._PENDING_FINGERPRINT_PREFIX)
        ):
            return self._activate_pending(source_id, should_cancel)
        try:
            locator = self.repository.get_internal_locator(source_id)
            path = Path(locator["internal_path"])
            if self.repository.get(source_id)["source_type"] == "report_directory":
                self._validate_report_structure(path)
            current = _fingerprint(path, should_cancel)
        except SourceFingerprintCancelledError:
            return self.repository.get(source_id)
        except Exception as error:
            if is_temporary_source_failure(error):
                return self.repository.mark_pending_revalidation(source_id)
            current = None
        return self.repository.revalidate(source_id, current_fingerprint=current)

    def _activate_pending(
        self, source_id: str, should_cancel: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        try:
            locator = self.repository.get_internal_locator(source_id)
            path = Path(locator["internal_path"])
            validate_pending_locator(path, Path(locator["allowed_root"]))
            self._validate_report_structure(path)
            metadata, current_fingerprint = _fingerprint_with_metadata(path, should_cancel)
            return self.repository.activate_pending(source_id, metadata, current_fingerprint)
        except SourceFingerprintCancelledError:
            return self.repository.get(source_id)
        except Exception as error:
            if is_temporary_source_failure(error):
                return self.repository.mark_pending_revalidation(source_id)
            return self.repository.revalidate(source_id, current_fingerprint=None)

    def require_available(self, source_id: str) -> dict[str, Any]:
        result = self.revalidate(source_id)
        if result["access_status"] == "pending":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING")
        if result["access_status"] != "available":
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
        return result

    def require_parse_ready(self, source_id: str, *, verify_existing: bool = False) -> dict[str, Any]:
        """仅验证旧版 Parser 所需的授权报告输入。"""
        record = self.repository.get(source_id)
        if record["access_status"] in {"invalid", "requires_reselection"}:
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
        if verify_existing and record["access_status"] == "available":
            record = self.revalidate(source_id)
            if record["access_status"] == "pending":
                raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING")
            if record["access_status"] != "available":
                raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
        try:
            locator = self.repository.get_internal_locator(source_id)
            path = Path(locator["internal_path"])
            validate_pending_locator(path, Path(locator["allowed_root"]))
            if record["source_type"] == "report_directory":
                self._validate_report_structure(path)
        except Exception as error:
            if is_temporary_source_failure(error):
                self.repository.mark_pending_revalidation(source_id)
                raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING") from error
            self.repository.revalidate(source_id, current_fingerprint=None)
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED") from error
        return record

    def verify_after_parse(
        self,
        source_id: str,
        expected_revision: int | None = None,
        cancellation_event: Any | None = None,
    ) -> dict[str, Any]:
        """运行延迟的有界核心来源验证。"""
        current = self.repository.get(source_id)
        should_cancel = cancellation_event.is_set if cancellation_event is not None else None
        if should_cancel is not None and should_cancel():
            return current
        if expected_revision is not None and current["revision"] != expected_revision:
            return current
        for _ in range(self._MAX_REVISION_CONFLICT_RETRIES):
            try:
                return self.revalidate(source_id, should_cancel)
            except WorkbenchPersistenceError as error:
                if error.code != "SOURCE_REVISION_CONFLICT":
                    raise
                try:
                    fingerprint = self._compute_current_fingerprint(source_id, should_cancel)
                except SourceFingerprintCancelledError:
                    return self.repository.get(source_id)
                except Exception as fingerprint_error:
                    if is_temporary_source_failure(fingerprint_error):
                        return self.repository.mark_pending_revalidation(source_id)
                    fingerprint = None
                try:
                    return self.repository.revalidate(source_id, current_fingerprint=fingerprint)
                except WorkbenchPersistenceError as retry_error:
                    if retry_error.code != "SOURCE_REVISION_CONFLICT":
                        raise
        return self.repository.mark_pending_revalidation(source_id, "SOURCE_REVISION_CONFLICT_RETRY_EXHAUSTED")

    def _compute_current_fingerprint(
        self, source_id: str, should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        locator = self.repository.get_internal_locator(source_id)
        path = Path(locator["internal_path"])
        if self.repository.get(source_id)["source_type"] == "report_directory":
            self._validate_report_structure(path)
        return _fingerprint(path, should_cancel)

    def recover_pending_after_startup(self, dispatcher: Any) -> list[str]:
        scheduled: list[str] = []
        for item in self.repository.pending_review_records():
            source_id = str(item["source_id"])
            try:
                dispatcher.dispatch_source_verification(self, source_id, int(item["revision"]))
                scheduled.append(source_id)
            except Exception:
                self.repository.mark_pending_revalidation(source_id)
        return scheduled

    def mark_verification_pending(
        self, source_id: str, error_code: str, expected_revision: int,
    ) -> dict[str, Any]:
        """持久化调度器级验证失败，不暴露仓储。"""
        return self.repository.mark_pending_revalidation(
            source_id, error_code, expected_revision=expected_revision,
        )

    def internal_path(self, source_id: str) -> Path:
        return Path(self.repository.get_internal_locator(source_id)["internal_path"])

    def create_legacy_preview_source(self, case_id: str) -> str:
        """仅为现有旧版归档入口创建不透明运行时句柄。"""
        from .archive.archive_source_runtime_service import create_preview_source

        shell = CaseShellRepository(self.database).get(case_id)
        source = self.require_available(shell["source_id"])
        locator = self.repository.get_internal_locator(source["source_id"])
        authorized = AuthorizedInputRoot(
            Path(locator["internal_path"]), "configured_root", source["allowed_root_id"], Path(locator["allowed_root"]),
        )
        return create_preview_source(authorized)

    def remove_unbound_source(self, descriptor: dict[str, Any]) -> None:
        locator_id = descriptor.get("locator_id")
        if isinstance(locator_id, str):
            self.locators.remove(locator_id)

    def _validate_report_structure(self, report_dir: Path) -> None:
        try:
            require_supported_report_format(str(report_dir / "data"))
        except ReportFormatError as error:
            raise WorkbenchPersistenceError("SOURCE_STRUCTURE_INVALID") from error
        except OSError as error:
            raise WorkbenchPersistenceError("SOURCE_ACCESS_DENIED") from error
