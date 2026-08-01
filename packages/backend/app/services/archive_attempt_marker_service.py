"""Owner-checked, idempotent staging marker removal."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ..repository.archive_publish_fence_repository import get as get_fence
from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ..repository.workbench_errors import WorkbenchPersistenceError
from ..repository.workbench_serialization import validate_opaque_id
from .archive_manifest_service import validate_published_manifest
from .archive_staging_security_service import OWNERSHIP_MARKER_NAME, remove_ownership_marker


def remove_owned_marker(service: Any, staging_dir: Path, attempt_id: str | None = None) -> None:
    marker = staging_dir / OWNERSHIP_MARKER_NAME
    attempt_id = attempt_id or service._attempt_for_final_dir(staging_dir)
    if attempt_id is None:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
    attempt_id = validate_opaque_id(attempt_id)
    intent = ArchivePublishIntentRepository(service.database).get_for_attempt(attempt_id)
    if intent is None:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_REQUIRED")
    expected_final = (service.output_root / "compressed" / intent["relative_final_dir"]).resolve(strict=False)
    if expected_final != staging_dir.resolve(strict=False) or not staging_dir.is_dir():
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_MISMATCH")
    fence = get_fence(service.database, str(intent.get("fence_id"))) if intent.get("fence_id") else None
    if (
        fence is None or fence["attempt_id"] != attempt_id
        or fence.get("task_id") != intent.get("task_id")
        or fence.get("deployment_instance_id") != service.database.deployment_instance_id
        or fence["status"] not in {"active", "pending_verification", "consumed"}
        or intent.get("publication_status") not in {"sealed", "published", "verified"}
    ):
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
    if not marker.exists():
        if intent.get("publication_status") in {"published", "verified"}:
            return
        if (
            intent.get("publication_status") == "sealed"
            and validate_published_manifest(SimpleNamespace(
                public_manifest=intent["public_manifest"], final_dir=staging_dir,
            ))
        ):
            return
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_MARKER_MISSING")
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED") from error
    attempt = service.repository.get_internal(attempt_id)
    expected = {
        "marker_version": 1, "attempt_id": attempt_id,
        "deployment_instance_id": service.database.deployment_instance_id,
        "staging_root_id": attempt.get("staging_root_id"),
        "marker_token": attempt.get("ownership_marker_token"),
    }
    if attempt.get("task_id") is not None:
        expected["task_id"] = attempt.get("task_id")
    if payload != expected:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
    try:
        remove_ownership_marker(staging_dir)
    except FileNotFoundError:
        if intent.get("publication_status") in {"published", "verified"}:
            return
        if not (
            intent.get("publication_status") == "sealed"
            and validate_published_manifest(SimpleNamespace(
                public_manifest=intent["public_manifest"], final_dir=staging_dir,
            ))
        ):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_MARKER_MISSING")
    try:
        staging_dir.chmod(
            stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IXOTH,
        )
    except OSError:
        pass
