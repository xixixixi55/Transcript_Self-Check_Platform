"""第 21 层：有界预览来源句柄和延迟归档准备。"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ...repository.archive.archive_authorization_repository import AuthorizedInputRoot
from ...repository.filesystem_identity_repository import normalized_directory_key
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveRuntimeError


ARCHIVE_SOURCE_TTL_SECONDS = 30 * 60
ARCHIVE_SOURCE_CAPACITY = 32
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def validate_authorized_input(authorized_input: AuthorizedInputRoot) -> None:
    root = authorized_input.resolved_input_root
    try:
        info = os.lstat(root)
        current = root.resolve(strict=True)
    except OSError as error:
        raise ArchiveRuntimeError(
            "ARCHIVE_AUTHORIZATION_INVALID",
            "Archive input authorization is no longer valid.",
        ) from error
    if not stat.S_ISDIR(info.st_mode) or root.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    ) or not current.is_dir():
        raise ArchiveRuntimeError(
            "ARCHIVE_AUTHORIZATION_INVALID",
            "Archive input authorization is no longer valid.",
        )
    if authorized_input.authorization_type == "exact_directory_grant" and current != root:
        raise ArchiveRuntimeError(
            "ARCHIVE_INPUT_CHANGED", "Archive input changed before preparation.",
        )
    scope = authorized_input.authorized_scope
    if scope is not None:
        try:
            current.relative_to(scope)
        except ValueError as error:
            raise ArchiveRuntimeError(
                "ARCHIVE_AUTHORIZATION_INVALID",
                "Archive input authorization is no longer valid.",
            ) from error


def cleanup_owned_source(path: Path | None) -> None:
    if path is None:
        return
    try:
        resolved = path.resolve(strict=False)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
        resolved.relative_to(temp_root)
    except (OSError, ValueError):
        return
    if resolved.name.startswith("biji_archive_context_"):
        shutil.rmtree(resolved, ignore_errors=True)


@dataclass
class PreviewSourceRecord:
    source_id: str
    authorized_input: AuthorizedInputRoot
    source_key: str
    created_at: float
    expires_at: float
    cleanup_root: Path | None = None
    prepared_context_id: str | None = None
    preparation_status: str = "not_prepared"
    prepare_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def _preview_source_summary(record: PreviewSourceRecord) -> dict[str, object]:
    def iso(value: float) -> str:
        return datetime.fromtimestamp(value, timezone.utc).isoformat()

    return {
        "archive_context_id": record.source_id,
        "file_count": None,
        "total_input_bytes": None,
        "status": record.preparation_status,
        "context_kind": "preview_source",
        "inventory_ready": False,
        "created_at": iso(record.created_at),
        "expires_at": iso(record.expires_at),
    }


class ArchiveSourceRuntimeStore:
    """使授权来源引用与完整归档上下文分离。"""

    def __init__(
        self,
        *,
        ttl_seconds: int = ARCHIVE_SOURCE_TTL_SECONDS,
        max_entries: int = ARCHIVE_SOURCE_CAPACITY,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("Archive source lifecycle limits are invalid.")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._records: dict[str, PreviewSourceRecord] = {}
        self._lock = threading.RLock()

    def create(
        self,
        authorized_input: AuthorizedInputRoot,
        *,
        cleanup_root: str | None = None,
    ) -> str:
        validate_authorized_input(authorized_input)
        now = self._clock()
        with self._lock:
            self.cleanup(now)
            if len(self._records) >= self.max_entries:
                raise ArchiveRuntimeError(
                    "ARCHIVE_SOURCE_CAPACITY",
                    "Archive preview source capacity is exhausted.",
                )
            source_id = str(uuid4())
            self._records[source_id] = PreviewSourceRecord(
                source_id,
                authorized_input,
                normalized_directory_key(authorized_input.resolved_input_root),
                now,
                now + self.ttl_seconds,
                Path(cleanup_root) if cleanup_root else None,
            )
            return source_id

    def public_summary(self, source_id: str) -> dict[str, object]:
        record = self._active(source_id)
        if record.prepared_context_id:
            try:
                formal = ARCHIVE_RUNTIME_STORE.get_context_summary(record.prepared_context_id)
            except ArchiveRuntimeError as error:
                if error.code not in {"ARCHIVE_CONTEXT_NOT_FOUND", "ARCHIVE_CONTEXT_EXPIRED"}:
                    raise
                record.prepared_context_id = None
                record.preparation_status = "not_prepared"
            else:
                return formal
        return _preview_source_summary(record)

    def prepare(
        self,
        source_id: str,
        builder: Callable[[AuthorizedInputRoot, Path | None], str],
    ) -> str:
        record = self._active(source_id)
        with record.prepare_lock:
            record = self._active(source_id)
            if record.prepared_context_id:
                try:
                    ARCHIVE_RUNTIME_STORE.get_context_summary(record.prepared_context_id)
                except ArchiveRuntimeError as error:
                    if error.code not in {"ARCHIVE_CONTEXT_NOT_FOUND", "ARCHIVE_CONTEXT_EXPIRED"}:
                        raise
                    record.prepared_context_id = None
                    record.preparation_status = "not_prepared"
                else:
                    return record.prepared_context_id
            record.preparation_status = "preparing"
            try:
                validate_authorized_input(record.authorized_input)
                context_id = builder(record.authorized_input, record.cleanup_root)
            except BaseException:
                with self._lock:
                    current = self._records.get(source_id)
                    if current is not None:
                        current.preparation_status = "failed"
                raise
            with self._lock:
                current = self._records.get(source_id)
                if current is None:
                    raise ArchiveRuntimeError(
                        "ARCHIVE_SOURCE_EXPIRED",
                        "Archive preview source has expired.",
                    )
                current.prepared_context_id = context_id
                current.preparation_status = "ready"
                current.cleanup_root = None
            return context_id

    def formal_context_id(self, source_id: str) -> str:
        try:
            ARCHIVE_RUNTIME_STORE.get_context_summary(source_id)
            return source_id
        except ArchiveRuntimeError as error:
            if error.code not in {"ARCHIVE_CONTEXT_NOT_FOUND", "ARCHIVE_CONTEXT_EXPIRED"}:
                raise
        record = self._active(source_id)
        if not record.prepared_context_id:
            raise ArchiveRuntimeError(
                "ARCHIVE_CONTEXT_NOT_PREPARED",
                "Archive preparation is required before formal use.",
            )
        try:
            ARCHIVE_RUNTIME_STORE.get_context_summary(record.prepared_context_id)
        except ArchiveRuntimeError as error:
            if error.code not in {"ARCHIVE_CONTEXT_NOT_FOUND", "ARCHIVE_CONTEXT_EXPIRED"}:
                raise
            record.prepared_context_id = None
            record.preparation_status = "not_prepared"
            raise ArchiveRuntimeError(
                "ARCHIVE_CONTEXT_NOT_PREPARED",
                "Archive preparation is required before formal use.",
            ) from error
        return record.prepared_context_id

    def cleanup(self, now: float | None = None) -> None:
        current = self._clock() if now is None else now
        with self._lock:
            expired: list[PreviewSourceRecord] = []
            for source_id, record in list(self._records.items()):
                if record.expires_at <= current and not record.prepare_lock.locked():
                    expired.append(self._records.pop(source_id))
        for record in expired:
            cleanup_owned_source(record.cleanup_root)

    def discard(self, source_id: str) -> None:
        with self._lock:
            record = self._records.pop(source_id, None)
        if record is not None:
            cleanup_owned_source(record.cleanup_root)

    def _active(self, source_id: str) -> PreviewSourceRecord:
        if not source_id or any(char in source_id for char in "\\/"):
            raise ArchiveRuntimeError("ARCHIVE_CONTEXT_NOT_FOUND", "Archive context was not found.")
        with self._lock:
            record = self._records.get(source_id)
            if record is None:
                raise ArchiveRuntimeError("ARCHIVE_CONTEXT_NOT_FOUND", "Archive context was not found.")
            if record.expires_at <= self._clock():
                self._records.pop(source_id, None)
                cleanup_owned_source(record.cleanup_root)
                raise ArchiveRuntimeError("ARCHIVE_SOURCE_EXPIRED", "Archive preview source has expired.")
            return record

ARCHIVE_SOURCE_RUNTIME_STORE = ArchiveSourceRuntimeStore()


def create_preview_source(
    authorized_input: AuthorizedInputRoot,
    *,
    cleanup_root: str | None = None,
) -> str:
    return ARCHIVE_SOURCE_RUNTIME_STORE.create(authorized_input, cleanup_root=cleanup_root)


def get_preview_source_summary(source_id: str) -> dict[str, object]:
    return ARCHIVE_SOURCE_RUNTIME_STORE.public_summary(source_id)


def discard_preview_source(source_id: str) -> None:
    ARCHIVE_SOURCE_RUNTIME_STORE.discard(source_id)


def prepare_archive_source(
    source_id: str,
    report: dict,
    *,
    output_root: str,
    cancellation_check: Callable[[], bool] | None = None,
) -> str:
    from .archive_execution_service import create_archive_context

    try:
        return ARCHIVE_SOURCE_RUNTIME_STORE.formal_context_id(source_id)
    except ArchiveRuntimeError as error:
        if error.code != "ARCHIVE_CONTEXT_NOT_PREPARED":
            raise
    return ARCHIVE_SOURCE_RUNTIME_STORE.prepare(
        source_id,
        lambda authorized, cleanup: create_archive_context(
            authorized,
            report,
            output_root=output_root,
            cleanup_root=str(cleanup) if cleanup else None,
            cancellation_check=cancellation_check,
        ),
    )


def resolve_archive_context_id(source_id: str) -> str:
    return ARCHIVE_SOURCE_RUNTIME_STORE.formal_context_id(source_id)


__all__ = [
    "ARCHIVE_SOURCE_RUNTIME_STORE", "ArchiveSourceRuntimeStore",
    "create_preview_source", "discard_preview_source", "get_preview_source_summary",
    "prepare_archive_source", "resolve_archive_context_id",
]
