"""Source authorization, opaque storage and restart-time revalidation."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Any

from ..repository.case_workbench_repository import CaseShellRepository
from ..repository.source_record_repository import SourceRecordRepository
from ..repository.workbench_database import WorkbenchDatabase
from ..repository.workbench_errors import WorkbenchPersistenceError


class SourceRecordService:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.repository = SourceRecordRepository(database)

    def store_uploaded_archive(self, content: bytes, suffix: str) -> dict[str, Any]:
        if not isinstance(content, bytes) or not content:
            raise WorkbenchPersistenceError("SOURCE_EMPTY")
        normalized_suffix = suffix.casefold()
        if normalized_suffix not in {".rar", ".zip"}:
            raise WorkbenchPersistenceError("SOURCE_TYPE_UNSUPPORTED")
        source_id = _opaque_id("source")
        root = self.database.database_path.parent / "sources"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{source_id}{normalized_suffix}"
        path.write_bytes(content)
        stat = path.stat()
        return {
            "source_id": source_id,
            "source_type": "report_archive",
            "internal_path": str(path),
            "allowed_root": str(root),
            "allowed_root_id": _opaque_id("root"),
            "metadata": {"size_bytes": int(stat.st_size), "modified_time_ns": int(stat.st_mtime_ns)},
            "fingerprint": _fingerprint(path),
            "cleanup_path": path,
        }

    def get(self, source_id: str) -> dict[str, Any]:
        return self.repository.get(source_id)

    def replace_case_source(self, case_id: str, content: bytes, suffix: str, expected_revision: int) -> dict[str, Any]:
        descriptor = self.store_uploaded_archive(content, suffix)
        committed = False
        try:
            shell = CaseShellRepository(self.database).get(case_id)
            descriptor.update({"case_id": case_id, "task_id": shell["parse_task_id"]})
            result = self.repository.replace_for_case(case_id, descriptor, expected_revision)
            committed = True
            self.require_available(result["source_id"])
            return self.repository.get(result["source_id"])
        except Exception:
            if not committed:
                self.remove_unbound_file(descriptor)
            raise

    def revalidate(self, source_id: str) -> dict[str, Any]:
        try:
            locator = self.repository.get_internal_locator(source_id)
            current = _fingerprint(Path(locator["internal_path"]))
        except (OSError, ValueError, WorkbenchPersistenceError):
            current = None
        return self.repository.revalidate(source_id, current_fingerprint=current)

    def require_available(self, source_id: str) -> dict[str, Any]:
        result = self.revalidate(source_id)
        if result["access_status"] != "available":
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
        return result

    def internal_path(self, source_id: str) -> Path:
        result = self.repository.get_internal_locator(source_id)
        return Path(result["internal_path"])

    def remove_unbound_file(self, descriptor: dict[str, Any]) -> None:
        path = descriptor.get("cleanup_path")
        if isinstance(path, Path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _opaque_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(16)}"


def _fingerprint(path: Path) -> str:
    if path.is_file() and not path.is_symlink():
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    if path.is_dir() and not path.is_symlink():
        digest = hashlib.sha256()
        for child in sorted(path.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if child.is_file() and not child.is_symlink():
                stat = child.stat()
                digest.update(f"{child.relative_to(path).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode())
        return digest.hexdigest()
    raise OSError("source unavailable")
