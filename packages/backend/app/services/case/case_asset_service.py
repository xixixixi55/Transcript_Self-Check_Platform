"""持久案件绑定图片资产；路径绝不跨越 HTTP 边界。"""

from __future__ import annotations

import hashlib
import mimetypes
import secrets
from collections.abc import Mapping, Sequence
from pathlib import PureWindowsPath
from typing import Any

from ...repository.asset_reference_repository import AssetReferenceRepository
from ...repository.case.case_asset_storage import CaseAssetStorage
from ...repository.workbench_constants import (
    ASSET_ORPHAN_RETENTION_SECONDS, MAX_CASE_IMAGE_BYTES, MAX_CASE_IMAGE_COUNT,
    MAX_CASE_IMAGE_TOTAL_BYTES,
)
from ...repository.workbench_database import WorkbenchDatabase
from ...repository.workbench_errors import WorkbenchPersistenceError
from ...repository.workbench_serialization import validate_opaque_id
from ..attachment2_image_service import Attachment2ImageError, validate_attachment2_photos

_SUFFIXES = {".jpg", ".jpeg", ".png"}


class CaseAssetService:
    def __init__(self, database: WorkbenchDatabase, lease_service: Any) -> None:
        self.database = database
        self.references = AssetReferenceRepository(database)
        self.storage = CaseAssetStorage(database.database_path.parent / "assets")
        self.leases = lease_service

    def upload_image(
        self, case_id: str, filename: str, content: bytes, lease_id: str, lease_token: str,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        self.leases.assert_active_for_case(case_id, lease_id, lease_token)
        suffix = _suffix(filename)
        if len(content) > MAX_CASE_IMAGE_BYTES:
            raise WorkbenchPersistenceError("ASSET_IMAGE_TOO_LARGE")
        current = self.references.list_case(case_id, "image")
        total = sum(_size(item) for item in current)
        if len(current) >= MAX_CASE_IMAGE_COUNT:
            raise WorkbenchPersistenceError("ASSET_IMAGE_COUNT_EXCEEDED")
        if total + len(content) > MAX_CASE_IMAGE_TOTAL_BYTES:
            raise WorkbenchPersistenceError("ASSET_CASE_SIZE_EXCEEDED")
        staged = self.storage.stage(case_id, suffix, content)
        try:
            try:
                validate_attachment2_photos([str(staged)])
            except Attachment2ImageError as error:
                raise WorkbenchPersistenceError("ASSET_IMAGE_INVALID") from error
            asset_id = f"asset-{secrets.token_hex(16)}"
            safe_name = _safe_name(filename, suffix)
            reference = {
                "asset_id": asset_id, "case_id": case_id, "asset_kind": "image",
                "fingerprint": hashlib.sha256(content).hexdigest(),
                "metadata": {
                    "file_name": safe_name, "extension": suffix,
                    "media_type": mimetypes.types_map.get(suffix, "application/octet-stream"),
                    "size_bytes": len(content),
                },
            }
            self.leases.assert_active_for_case(case_id, lease_id, lease_token)
            self.storage.finalize(staged, case_id, asset_id, suffix)
            try:
                saved = self.references.create(reference)
            except Exception:
                self.storage.delete(case_id, asset_id, suffix)
                raise
            return self._public(saved)
        except Exception:
            self.storage.discard(staged)
            raise

    def list_images(self, case_id: str) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        bound_ids = self._draft_asset_ids(case_id)
        items = [
            self._public(item)
            for item in self.references.list_case(case_id, "image")
            if item["asset_id"] in bound_ids or within_asset_orphan_retention(item["created_at"])
        ]
        return {"items": items}

    def read_image(self, case_id: str, asset_id: str) -> tuple[bytes, dict[str, Any]]:
        case_id = validate_opaque_id(case_id)
        reference = self.references.get(asset_id)
        if reference["case_id"] != case_id or reference["asset_kind"] != "image":
            raise WorkbenchPersistenceError("ASSET_NOT_FOUND")
        metadata = reference.get("metadata", {})
        suffix = str(metadata.get("extension", ""))
        try:
            content = self.storage.read(case_id, asset_id, suffix)
        except (OSError, ValueError) as error:
            raise WorkbenchPersistenceError("ASSET_CONTENT_MISSING") from error
        if hashlib.sha256(content).hexdigest() != reference.get("fingerprint"):
            raise WorkbenchPersistenceError("ASSET_CONTENT_CORRUPT")
        return content, metadata

    def release_unreferenced(self, case_id: str, asset_ids: Sequence[str]) -> None:
        for asset_id in asset_ids:
            try:
                reference = self.references.get(asset_id)
                if reference["case_id"] != case_id or reference["asset_kind"] != "image":
                    continue
                self.references.delete(case_id, asset_id)
                self.storage.delete(case_id, asset_id, str(reference["metadata"].get("extension", "")))
            except (OSError, WorkbenchPersistenceError):
                continue

    def cleanup_orphans(self) -> int:
        """宽限期后移除过期未引用记录和文件。"""
        removed = 0
        for case_id in self.storage.case_ids():
            if not _is_opaque_case_id(case_id):
                continue
            referenced = self._draft_asset_ids(case_id)
            references = self.references.list_case(case_id, "image")
            known_files = {
                f"{item['asset_id']}{item.get('metadata', {}).get('extension', '')}" for item in references
            }
            for reference in references:
                if reference["asset_id"] in referenced or not _old_enough(reference["created_at"]):
                    continue
                self.release_unreferenced(case_id, [reference["asset_id"]])
                removed += 1
            for path in self.storage.files_for_case(case_id):
                if path.name in known_files or not _old_enough_file(path):
                    continue
                self.storage.discard(path)
                removed += 1
        return removed

    def _public(self, reference: Mapping[str, Any]) -> dict[str, Any]:
        result = {key: reference[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata")}
        result["content_status"] = self._content_status(reference)
        return result

    def _content_status(self, reference: Mapping[str, Any]) -> str:
        try:
            content, _ = self.read_image(str(reference["case_id"]), str(reference["asset_id"]))
            return "available" if content else "corrupt"
        except WorkbenchPersistenceError as error:
            return "missing" if error.code == "ASSET_CONTENT_MISSING" else "corrupt"

    def _draft_asset_ids(self, case_id: str) -> set[str]:
        import json
        with self.database.connect() as connection:
            rows = connection.execute("SELECT asset_refs_json FROM case_drafts WHERE case_id = ?", (case_id,)).fetchall()
        ids: set[str] = set()
        for row in rows:
            try:
                ids.update(str(item["asset_id"]) for item in json.loads(row[0]))
            except (TypeError, ValueError, KeyError):
                continue
        return ids


def _suffix(filename: str) -> str:
    suffix = PureWindowsPath(str(filename).replace("/", "\\")).suffix.casefold()
    if suffix not in _SUFFIXES:
        raise WorkbenchPersistenceError("ASSET_IMAGE_FORMAT_INVALID")
    return suffix


def _safe_name(filename: str, suffix: str) -> str:
    name = PureWindowsPath(str(filename).replace("/", "\\")).name
    safe = "".join(char if char.isprintable() and char not in '<>:/\\|?*"' else "_" for char in name)
    return (safe[:160] or "photo") if safe.casefold().endswith(suffix) else f"photo{suffix}"


def _size(reference: Mapping[str, Any]) -> int:
    value = reference.get("metadata", {}).get("size_bytes", 0)
    return int(value) if isinstance(value, (int, float)) and value >= 0 else 0


def _old_enough(created_at: str) -> bool:
    from datetime import datetime, timedelta, timezone
    try:
        timestamp = datetime.fromisoformat(str(created_at)).astimezone(timezone.utc)
        return datetime.now(timezone.utc) - timestamp > timedelta(seconds=ASSET_ORPHAN_RETENTION_SECONDS)
    except (TypeError, ValueError):
        return False


def within_asset_orphan_retention(created_at: str) -> bool:
    """未绑定资产是否仍符合草稿恢复条件。"""
    return not _old_enough(created_at)


def _old_enough_file(path: Any) -> bool:
    from datetime import datetime, timedelta, timezone
    try:
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        return datetime.now(timezone.utc) - timestamp > timedelta(seconds=ASSET_ORPHAN_RETENTION_SECONDS)
    except OSError:
        return False


def _is_opaque_case_id(value: str) -> bool:
    try:
        validate_opaque_id(value)
        return True
    except WorkbenchPersistenceError:
        return False
