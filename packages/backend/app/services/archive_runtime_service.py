"""In-process lifecycle store for opaque archive contexts and manifests."""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..repository.archive_authorization_repository import AuthorizedInputRoot
from ..repository.archive_input_repository import InputInventory, build_input_inventory


ARCHIVE_CONTEXT_TTL_SECONDS = 30 * 60
ARCHIVE_MANIFEST_TTL_SECONDS = 24 * 60 * 60


def _cleanup_owned_source(path: Path | None) -> None:
    if path and path.name.startswith("biji_archive_context_"):
        shutil.rmtree(path, ignore_errors=True)


class ArchiveRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass
class ArchiveContextRecord:
    context_id: str
    case_display_name: str
    inventory: InputInventory
    authorization_type: str
    authorized_root_id: str
    authorized_scope: Path | None
    input_fingerprint: str
    created_at: float
    expires_at: float
    cleanup_root: Path | None = None
    execution_state: str = "idle"
    active_execution_id: str | None = None
    successful_manifest_id: str | None = None

    @property
    def executing(self) -> bool:
        return self.active_execution_id is not None

    def public_summary(self) -> dict[str, object]:
        def iso(value: float) -> str:
            return datetime.fromtimestamp(value, timezone.utc).isoformat()

        return {
            "archive_context_id": self.context_id,
            "file_count": len(self.inventory.files),
            "total_input_bytes": self.inventory.total_input_bytes,
            "status": self.execution_state,
            "created_at": iso(self.created_at),
            "expires_at": iso(self.expires_at),
        }


@dataclass
class ArchiveManifestRecord:
    manifest_id: str
    context_id: str
    fingerprint: str
    public_manifest: dict[str, object]
    final_dir: Path
    created_at: float
    expires_at: float


class ArchiveRuntimeStore:
    def __init__(self) -> None:
        self._contexts: dict[str, ArchiveContextRecord] = {}
        self._manifests: dict[str, ArchiveManifestRecord] = {}
        self._lock = threading.RLock()

    def create_context(
        self,
        authorized_input: AuthorizedInputRoot,
        case_display_name: str,
        *,
        output_root: str,
        cleanup_root: str | None = None,
    ) -> ArchiveContextRecord:
        try:
            inventory = build_input_inventory(
                authorized_input.resolved_input_root, output_root=output_root,
            )
        except Exception:
            if cleanup_root:
                _cleanup_owned_source(Path(cleanup_root))
            raise
        now = time.time()
        fingerprint = hashlib.sha256(
            json.dumps(inventory.public_entries(), sort_keys=True).encode("utf-8")
        ).hexdigest()
        record = ArchiveContextRecord(
            context_id=str(uuid4()),
            case_display_name=case_display_name,
            inventory=inventory,
            authorization_type=authorized_input.authorization_type,
            authorized_root_id=authorized_input.authorized_root_id,
            authorized_scope=authorized_input.authorized_scope,
            input_fingerprint=fingerprint,
            created_at=now,
            expires_at=now + ARCHIVE_CONTEXT_TTL_SECONDS,
            cleanup_root=Path(cleanup_root) if cleanup_root else None,
        )
        with self._lock:
            self.cleanup_expired(now)
            self._contexts[record.context_id] = record
        return record

    def validate_context_authorization(self, record: ArchiveContextRecord) -> None:
        try:
            current_root = record.inventory.source_root.resolve(strict=True)
        except OSError as error:
            raise ArchiveRuntimeError("ARCHIVE_INPUT_CHANGED", "Archive input changed before execution.") from error
        scope = record.authorized_scope
        if scope is not None:
            try:
                current_root.relative_to(scope)
            except ValueError as error:
                raise ArchiveRuntimeError(
                    "ARCHIVE_AUTHORIZATION_INVALID", "Archive input authorization is no longer valid.",
                ) from error
        if record.authorization_type == "exact_directory_grant" and current_root != record.inventory.source_root:
            raise ArchiveRuntimeError("ARCHIVE_INPUT_CHANGED", "Archive input changed before execution.")

    def acquire_context(self, context_id: str) -> ArchiveContextRecord:
        with self._lock:
            record = self._contexts.get(context_id)
            if record is None:
                raise ArchiveRuntimeError("ARCHIVE_CONTEXT_NOT_FOUND", "Archive context was not found.")
            if record.expires_at <= time.time():
                self._contexts.pop(context_id, None)
                _cleanup_owned_source(record.cleanup_root)
                raise ArchiveRuntimeError("ARCHIVE_CONTEXT_EXPIRED", "Archive context has expired.")
            if record.executing:
                raise ArchiveRuntimeError("ARCHIVE_CONTEXT_BUSY", "Archive context is already running.")
            record.active_execution_id = str(uuid4())
            record.execution_state = "planning"
            return record

    def release_context(
        self,
        context_id: str,
        *,
        state: str = "idle",
        successful_manifest_id: str | None = None,
    ) -> None:
        with self._lock:
            record = self._contexts.get(context_id)
            if record:
                record.active_execution_id = None
                record.execution_state = state
                if successful_manifest_id:
                    record.successful_manifest_id = successful_manifest_id

    def find_reusable(self, context_id: str, fingerprint: str) -> ArchiveManifestRecord | None:
        with self._lock:
            self.cleanup_expired()
            return next(
                (item for item in self._manifests.values()
                 if item.context_id == context_id and item.fingerprint == fingerprint),
                None,
            )

    def save_manifest(self, record: ArchiveManifestRecord) -> None:
        with self._lock:
            self._manifests[record.manifest_id] = record
            context = self._contexts.get(record.context_id)
            if context:
                context.successful_manifest_id = record.manifest_id

    def get_manifest(self, manifest_id: str) -> ArchiveManifestRecord:
        with self._lock:
            self.cleanup_expired()
            record = self._manifests.get(manifest_id)
            if record is None:
                raise ArchiveRuntimeError("ARCHIVE_MANIFEST_MISSING", "Archive manifest is missing.")
            return record

    def get_context_summary(self, context_id: str) -> dict[str, object]:
        with self._lock:
            record = self._contexts.get(context_id)
            if record is None:
                raise ArchiveRuntimeError("ARCHIVE_CONTEXT_NOT_FOUND", "Archive context was not found.")
            if record.expires_at <= time.time():
                raise ArchiveRuntimeError("ARCHIVE_CONTEXT_EXPIRED", "Archive context has expired.")
            return record.public_summary()

    def cleanup_expired(self, now: float | None = None) -> None:
        current = time.time() if now is None else now
        expired_contexts = [
            key for key, item in self._contexts.items()
            if item.expires_at <= current and not item.executing
        ]
        for key in expired_contexts:
            record = self._contexts.pop(key)
            _cleanup_owned_source(record.cleanup_root)
        expired_manifests = [
            key for key, item in self._manifests.items() if item.expires_at <= current
        ]
        for key in expired_manifests:
            # Published successful archives are independent from in-memory
            # metadata; expiry must never delete their final output.
            self._manifests.pop(key)


ARCHIVE_RUNTIME_STORE = ArchiveRuntimeStore()
