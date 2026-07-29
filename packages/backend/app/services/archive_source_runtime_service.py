"""Layer 21: bounded preview-source handles and deferred archive preparation."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ..repository.archive_authorization_repository import AuthorizedInputRoot
from ..repository.filesystem_identity_repository import normalized_directory_key
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveRuntimeError
from .archive_source_runtime_models_service import PreviewSourceRecord, preview_source_summary
from .archive_source_security_service import cleanup_owned_source, validate_authorized_input


ARCHIVE_SOURCE_TTL_SECONDS = 30 * 60
ARCHIVE_SOURCE_CAPACITY = 32


class ArchiveSourceRuntimeStore:
    """Keep authorized source references separate from full archive contexts."""

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
        return preview_source_summary(record)

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
        ),
    )


def resolve_archive_context_id(source_id: str) -> str:
    return ARCHIVE_SOURCE_RUNTIME_STORE.formal_context_id(source_id)


__all__ = [
    "ARCHIVE_SOURCE_RUNTIME_STORE", "ArchiveSourceRuntimeStore",
    "create_preview_source", "discard_preview_source", "get_preview_source_summary",
    "prepare_archive_source", "resolve_archive_context_id",
]
