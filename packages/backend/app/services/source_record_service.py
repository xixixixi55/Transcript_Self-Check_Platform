"""Directory-source authorization, opaque persistence and revalidation."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Any

from ..config import OUTPUT_BASE, UPLOAD_BASE
from ..repository.archive_authorization_repository import AuthorizedInputRoot
from ..repository.case_workbench_repository import CaseShellRepository
from ..repository.source_locator_repository import SourceLocatorRepository
from ..repository.source_record_repository import SourceRecordRepository
from ..repository.workbench_database import WorkbenchDatabase
from ..repository.workbench_errors import WorkbenchPersistenceError
from ..repository.report_format_adapter import ReportFormatError, require_supported_report_format
from .archive_authorization_service import ArchiveAuthorizationService
from .source_revalidation_policy_service import is_temporary_source_failure


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

    def register_report_directory(
        self, report_dir: str, grant_token: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(report_dir, str) or not report_dir.strip():
            raise WorkbenchPersistenceError("SOURCE_DIRECTORY_REQUIRED")
        candidate = Path(report_dir)
        if candidate.is_file():
            if candidate.suffix.casefold() in {".rar", ".zip"}:
                raise WorkbenchPersistenceError("SOURCE_ARCHIVE_NOT_ALLOWED")
            raise WorkbenchPersistenceError("SOURCE_DIRECTORY_REQUIRED")
        authorized = self.authorization.authorize_report_directory(report_dir, grant_token=grant_token)
        self._validate_report_structure(authorized.resolved_input_root)
        source_id = _opaque_id("source")
        allowed_root = authorized.authorized_scope or authorized.resolved_input_root.parent
        try:
            metadata = _directory_summary(authorized.resolved_input_root)
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
    ) -> dict[str, Any]:
        descriptor = self.register_report_directory(report_dir, grant_token)
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

    def revalidate(self, source_id: str) -> dict[str, Any]:
        record = self.repository.get(source_id)
        if (
            record["access_status"] == "pending"
            and str(record.get("fingerprint", "")).startswith(self._PENDING_FINGERPRINT_PREFIX)
        ):
            return self._activate_pending(source_id)
        try:
            locator = self.repository.get_internal_locator(source_id)
            path = Path(locator["internal_path"])
            if self.repository.get(source_id)["source_type"] == "report_directory":
                self._validate_report_structure(path)
            current = _fingerprint(path)
        except Exception as error:
            if is_temporary_source_failure(error):
                return self.repository.mark_pending_revalidation(source_id)
            current = None
        return self.repository.revalidate(source_id, current_fingerprint=current)

    def _activate_pending(self, source_id: str) -> dict[str, Any]:
        try:
            locator = self.repository.get_internal_locator(source_id)
            path = Path(locator["internal_path"])
            _validate_pending_locator(path, Path(locator["allowed_root"]))
            self._validate_report_structure(path)
            metadata = _directory_metadata(path)
            fingerprint = _fingerprint(path)
            return self.repository.activate_pending(source_id, metadata, fingerprint)
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
        """Validate only the authorized report inputs needed by the Legacy Parser.

        Full metadata and content fingerprinting belongs to explicit source
        revalidation/archive preparation and must not delay review readiness.
        """
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
            _validate_pending_locator(path, Path(locator["allowed_root"]))
            if record["source_type"] == "report_directory":
                self._validate_report_structure(path)
        except Exception as error:
            if is_temporary_source_failure(error):
                self.repository.mark_pending_revalidation(source_id)
                raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING") from error
            self.repository.revalidate(source_id, current_fingerprint=None)
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED") from error
        return record

    def verify_after_parse(self, source_id: str, expected_revision: int | None = None) -> dict[str, Any]:
        """Run the deferred full source verification without changing case state."""
        try:
            current = self.repository.get(source_id)
            if expected_revision is not None and current["revision"] != expected_revision:
                return current
            return self.revalidate(source_id)
        except Exception:
            try:
                return self.repository.revalidate(source_id, current_fingerprint=None)
            except WorkbenchPersistenceError:
                return {"source_id": source_id, "access_status": "requires_reselection"}

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

    def internal_path(self, source_id: str) -> Path:
        return Path(self.repository.get_internal_locator(source_id)["internal_path"])

    def create_legacy_preview_source(self, case_id: str) -> str:
        """Create only an opaque runtime handle for the existing Legacy archive entry."""
        from .archive_source_runtime_service import create_preview_source

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


def _directory_metadata(path: Path) -> dict[str, str | int | float | bool]:
    entries = [item for item in path.rglob("*") if not item.is_symlink()]
    return {
        "display_name": path.name,
        "file_count": sum(item.is_file() for item in entries),
        "directory_count": sum(item.is_dir() for item in entries),
        "modified_time_ns": int(path.stat().st_mtime_ns),
    }


def _directory_summary(path: Path) -> dict[str, str | int | float | bool]:
    return {
        "display_name": path.name,
        "modified_time_ns": int(path.stat().st_mtime_ns),
    }


def _validate_pending_locator(path: Path, allowed_root: Path) -> None:
    resolved_path = path.resolve(strict=True)
    resolved_root = allowed_root.resolve(strict=True)
    resolved_path.relative_to(resolved_root)
    if path.is_symlink() or not resolved_path.is_dir() or not os.access(resolved_path, os.R_OK):
        raise OSError("source unavailable")


def _opaque_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(16)}"


def _fingerprint(path: Path) -> str:
    if not path.is_dir() or path.is_symlink():
        raise OSError("source unavailable")
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if child.is_file() and not child.is_symlink():
            stat = child.stat()
            digest.update(f"{child.relative_to(path).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode())
    return digest.hexdigest()
