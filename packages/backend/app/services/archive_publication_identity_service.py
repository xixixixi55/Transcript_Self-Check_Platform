"""Canonical publication-generation identities shared by publish and completion."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ..repository.workbench_errors import WorkbenchPersistenceError


def publication_id(attempt_id: str, manifest_id: str) -> str:
    return f"publication-{attempt_id}-{manifest_id}"


def publication_file_set(public_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    parts = public_manifest.get("parts")
    if not isinstance(parts, list) or not parts:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part in parts:
        if not isinstance(part, Mapping):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
        filename = part.get("filename")
        size = part.get("size_bytes")
        md5 = part.get("md5")
        if (
            not isinstance(filename, str) or not filename or filename.casefold() in seen
            or isinstance(size, bool) or not isinstance(size, int) or size < 0
            or not isinstance(md5, str) or len(md5) != 32
        ):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
        seen.add(filename.casefold())
        result.append({"filename": filename, "size_bytes": size, "md5": md5.casefold()})
    return sorted(result, key=lambda item: str(item["filename"]).casefold())


def publication_digest(intent: Mapping[str, Any], public_manifest: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    file_set = publication_file_set(public_manifest)
    identity = {
        "task_id": intent.get("task_id"),
        "attempt_id": intent.get("attempt_id"),
        "case_id": intent.get("case_id"),
        "deployment_instance_id": intent.get("deployment_instance_id"),
        "source_id": intent.get("source_id"),
        "source_revision": intent.get("source_revision"),
        "draft_revision": intent.get("draft_revision"),
        "report_fingerprint": intent.get("report_fingerprint"),
        "source_key": intent.get("source_key"),
        "input_fingerprint": intent.get("input_fingerprint"),
        "archive_fingerprint": intent.get("archive_fingerprint"),
        "manifest_id": intent.get("manifest_id"),
        "relative_final_dir": intent.get("relative_final_dir"),
        "publication_id": intent.get("publication_id"),
        "fence_id": intent.get("fence_id"),
        "public_manifest": public_manifest,
        "file_set": file_set,
    }
    serialized = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest(), file_set


def assert_publication_identity(record: Any, intent: Mapping[str, Any]) -> None:
    manifest = _value(record, "public_manifest")
    expected_id = intent.get("publication_id")
    if not isinstance(expected_id, str) or not expected_id:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
    actual_id = getattr(record, "publication_id", None)
    if actual_id is not None and actual_id != expected_id:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_CONFLICT")
    digest, file_set = publication_digest(intent, manifest)
    actual_digest = getattr(record, "publication_digest", None)
    if actual_digest is not None and actual_digest != digest:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_CONFLICT")
    if intent.get("publication_digest") != digest:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_CONFLICT")
    if intent.get("publication_file_set") != file_set:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_CONFLICT")


def _value(record: Any, name: str) -> Any:
    value = getattr(record, name, None)
    if value is not None:
        return value
    if isinstance(record, Mapping):
        return record.get(name)
    raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
