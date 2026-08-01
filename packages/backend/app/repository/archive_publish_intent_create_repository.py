"""Validated creation and task/fence binding of durable publish intents."""

from __future__ import annotations

import json
import re
from typing import Any

from .archive_context_binding_repository import (
    context_binding_hash, report_fingerprint as calculate_report_fingerprint,
)
from .archive_publish_fence_repository import active_for_case
from .workbench_database import utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id

_HASH = re.compile(r"^[0-9a-f]{64}$")


def create_intent(repository: Any, *, attempt_id: str, case_id: str, source_id: str,
                  context_id: str, target_context_id: str, source_revision: int,
                  draft_revision: int, report_fingerprint: str, source_key: str,
                  input_fingerprint: str, archive_fingerprint: str, manifest_id: str,
                  relative_final_dir: str, public_manifest: dict[str, Any],
                  task_id: str | None = None, deployment_instance_id: str | None = None,
                  publication_id: str | None = None) -> dict[str, Any]:
    database = repository.database
    values = (source_key, input_fingerprint, archive_fingerprint, report_fingerprint)
    if not all(isinstance(value, str) and _HASH.fullmatch(value) for value in values):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_COMPLETION_EVIDENCE")
    attempt_id = validate_opaque_id(attempt_id)
    case_id = validate_opaque_id(case_id)
    source_id = validate_opaque_id(source_id)
    context_id = validate_opaque_id(context_id)
    target_context_id = validate_opaque_id(target_context_id)
    manifest_id = validate_opaque_id(manifest_id)
    task_id = validate_opaque_id(task_id) if task_id is not None else f"legacy-task-{attempt_id}"
    deployment_instance_id = validate_opaque_id(
        deployment_instance_id or database.deployment_instance_id,
    )
    if deployment_instance_id != database.deployment_instance_id:
        raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
    publication_id = validate_opaque_id(publication_id or f"publication-{attempt_id}-{manifest_id}")
    if (
        not isinstance(relative_final_dir, str) or not relative_final_dir
        or relative_final_dir.startswith(("/", "\\"))
        or ".." in relative_final_dir.replace("\\", "/").split("/")
    ):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_PUBLISH_INTENT")
    if not isinstance(public_manifest, dict):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_PUBLISH_INTENT")
    if relative_final_dir.replace("\\", "/") != f"{target_context_id}/{manifest_id}":
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_MISMATCH")
    serialized = json.dumps(public_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    now = utc_now()
    with database.transaction() as connection:
        existing = connection.execute(
            "SELECT * FROM archive_publish_intents WHERE attempt_id = ? "
            "AND deployment_instance_id = ?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if existing is not None:
            from .archive_publish_identity_repository import intent_dict, same_publish_identity
            if not same_publish_identity(
                connection, existing, attempt_id=attempt_id, case_id=case_id,
                source_id=source_id, source_revision=source_revision,
                draft_revision=draft_revision, report_fingerprint=report_fingerprint,
                source_key=source_key, input_fingerprint=input_fingerprint,
                archive_fingerprint=archive_fingerprint, manifest_id=manifest_id,
                relative_final_dir=relative_final_dir, serialized_manifest=serialized,
                context_hash=context_binding_hash(context_id), task_id=task_id,
                deployment_instance_id=deployment_instance_id, publication_id=publication_id,
            ):
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_CONFLICT")
            if existing["phase"] == "conflict" or existing["publication_status"] == "conflict":
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_CONFLICT")
            return intent_dict(existing)
        attempt = connection.execute(
            "SELECT case_id, task_id, deployment_instance_id, source_id, input_revision, "
            "source_revision, draft_revision, report_fingerprint, status "
            "FROM archive_attempts WHERE attempt_id = ? AND deployment_instance_id = ?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if attempt is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
        if (
            attempt["case_id"] != case_id or attempt["source_id"] != source_id
            or attempt["task_id"] not in (None, task_id)
            or attempt["deployment_instance_id"] != database.deployment_instance_id
            or int(attempt["source_revision"] or attempt["input_revision"]) != source_revision
            or int(attempt["draft_revision"] or 0) != draft_revision
            or attempt["report_fingerprint"] != report_fingerprint
            or attempt["status"] not in {"accepted", "running"}
        ):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
        legacy_task_id = f"legacy-task-{attempt_id}"
        if task_id != legacy_task_id:
            task = connection.execute(
                "SELECT case_id, deployment_instance_id, status, process_binding_json FROM task_records "
                "WHERE task_id=? AND kind='archive'", (task_id,),
            ).fetchone()
            try:
                process_binding = json.loads(task["process_binding_json"] or "{}") if task else {}
            except (TypeError, ValueError):
                process_binding = {}
            if (
                task is None or task["case_id"] != case_id
                or task["deployment_instance_id"] != database.deployment_instance_id
                or task["status"] not in {"running", "cancelling"}
                or process_binding.get("staging_asset_id") != attempt_id
                or attempt["task_id"] != task_id
            ):
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        elif attempt["task_id"] not in (None, legacy_task_id):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        shell = connection.execute(
            "SELECT source_id, lifecycle, revision FROM case_shells WHERE case_id = ?", (case_id,),
        ).fetchone()
        source = connection.execute(
            "SELECT case_id, revision, access_status FROM source_records WHERE source_id = ?", (source_id,),
        ).fetchone()
        draft = connection.execute(
            "SELECT revision, report_json, lifecycle FROM case_drafts WHERE case_id = ?", (case_id,),
        ).fetchone()
        binding = connection.execute(
            "SELECT case_id, source_id, source_revision, draft_revision, report_fingerprint, "
            "context_kind, active FROM archive_context_bindings "
            "WHERE context_hash = ? AND attempt_id = ?",
            (context_binding_hash(context_id), attempt_id),
        ).fetchone()
        if (
            shell is None or source is None or draft is None or binding is None
            or shell["source_id"] != source_id or shell["lifecycle"] not in {"archive_queued", "archiving"}
            or source["case_id"] != case_id or int(source["revision"]) != source_revision
            or source["access_status"] != "available" or int(draft["revision"]) != draft_revision
            or draft["lifecycle"] not in {"archive_queued", "archiving"}
            or calculate_report_fingerprint(json.loads(draft["report_json"])) != report_fingerprint
            or binding["case_id"] != case_id or binding["source_id"] != source_id
            or int(binding["source_revision"]) != source_revision
            or int(binding["draft_revision"]) != draft_revision
            or binding["report_fingerprint"] != report_fingerprint
            or binding["context_kind"] != "workbench" or not bool(binding["active"])
        ):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
        existing_fence = active_for_case(connection, case_id)
        if existing_fence is not None and existing_fence["attempt_id"] != attempt_id:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_ACTIVE")
        intent_id = f"publish-{attempt_id}-{manifest_id}"
        fence_id = f"fence-{attempt_id}"
        connection.execute(
            "INSERT INTO archive_publish_fences(fence_id, attempt_id, task_id, deployment_instance_id, "
            "case_id, source_id, source_revision, draft_revision, report_fingerprint, context_hash, "
            "shell_revision, status, reason, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, ?, ?)",
            (
                fence_id, attempt_id, task_id, deployment_instance_id, case_id, source_id,
                source_revision, draft_revision, report_fingerprint, context_binding_hash(context_id),
                int(shell["revision"]), now, now,
            ),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id, attempt_id, task_id, deployment_instance_id, "
            "case_id, source_id, source_revision, draft_revision, report_fingerprint, source_key, "
            "input_fingerprint, archive_fingerprint, manifest_id, relative_final_dir, public_manifest_json, "
            "publication_id, publication_relative_dir, publication_digest, publication_file_set_json, "
            "publication_status, fence_id, phase, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'pending', ?, 'intent_persisted', ?, ?)",
            (
                intent_id, attempt_id, task_id, deployment_instance_id, case_id, source_id,
                source_revision, draft_revision, report_fingerprint, source_key, input_fingerprint,
                archive_fingerprint, manifest_id, relative_final_dir, serialized, publication_id,
                relative_final_dir, fence_id, now, now,
            ),
        )
        return {
            "intent_id": intent_id, "attempt_id": attempt_id, "case_id": case_id,
            "source_id": source_id, "source_revision": source_revision,
            "draft_revision": draft_revision, "report_fingerprint": report_fingerprint,
            "source_key": source_key, "input_fingerprint": input_fingerprint,
            "archive_fingerprint": archive_fingerprint, "manifest_id": manifest_id,
            "relative_final_dir": relative_final_dir, "public_manifest": public_manifest,
            "task_id": task_id, "deployment_instance_id": deployment_instance_id,
            "publication_id": publication_id, "publication_relative_dir": relative_final_dir,
            "publication_digest": None, "publication_file_set": None,
            "publication_status": "pending", "fence_id": fence_id,
            "phase": "intent_persisted", "created_at": now, "updated_at": now,
        }
