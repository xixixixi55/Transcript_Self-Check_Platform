"""Durable publish intent records used to reconcile filesystem/database gaps."""

from __future__ import annotations

import json
import re
from typing import Any

from .archive_context_binding_repository import (
    context_binding_hash, report_fingerprint as calculate_report_fingerprint,
)
from .archive_publish_fence_repository import active_for_case
from .workbench_database import WorkbenchDatabase, normalize_utc_z, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id

_HASH = re.compile(r"^[0-9a-f]{64}$")
_PHASES = {"intent_persisted", "published", "indexed", "verified", "conflict"}


def intent_dict(
    row: Any, *, include_publication_verified_at: bool = False,
) -> dict[str, Any]:
    value = dict(row)
    if not include_publication_verified_at:
        value.pop("publication_verified_at", None)
    value["source_revision"] = int(value["source_revision"])
    value["draft_revision"] = int(value["draft_revision"])
    value["public_manifest"] = json.loads(value.pop("public_manifest_json"))
    raw_file_set = value.pop("publication_file_set_json", None)
    value["publication_file_set"] = (
        None if raw_file_set is None else json.loads(raw_file_set)
    )
    return value


def same_publish_identity(
    connection: Any, existing: Any, *, attempt_id: str, case_id: str,
    source_id: str, source_revision: int, draft_revision: int,
    report_fingerprint: str, source_key: str, input_fingerprint: str,
    archive_fingerprint: str, manifest_id: str, relative_final_dir: str,
    serialized_manifest: str, context_hash: str, task_id: str,
    deployment_instance_id: str, publication_id: str,
) -> bool:
    expected = {
        "attempt_id": attempt_id, "case_id": case_id, "source_id": source_id,
        "source_revision": source_revision, "draft_revision": draft_revision,
        "report_fingerprint": report_fingerprint, "source_key": source_key,
        "input_fingerprint": input_fingerprint,
        "archive_fingerprint": archive_fingerprint,
        "manifest_id": manifest_id, "relative_final_dir": relative_final_dir,
        "public_manifest_json": serialized_manifest, "task_id": task_id,
        "deployment_instance_id": deployment_instance_id,
        "publication_id": publication_id,
        "publication_relative_dir": relative_final_dir,
    }
    if any(existing[key] != value for key, value in expected.items()):
        return False
    fence = connection.execute(
        "SELECT * FROM archive_publish_fences WHERE fence_id=? AND attempt_id=? "
        "AND deployment_instance_id=?",
        (existing["fence_id"], attempt_id, deployment_instance_id),
    ).fetchone()
    return bool(
        fence is not None
        and fence["fence_id"] == f"fence-{attempt_id}"
        and fence["case_id"] == case_id
        and fence["attempt_id"] == attempt_id
        and fence["task_id"] == task_id
        and fence["deployment_instance_id"] == deployment_instance_id
        and fence["source_id"] == source_id
        and int(fence["source_revision"]) == source_revision
        and int(fence["draft_revision"]) == draft_revision
        and fence["report_fingerprint"] == report_fingerprint
        and fence["context_hash"] == context_hash
        and fence["status"] in {"active", "pending_verification", "consumed"}
    )


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


class ArchivePublishIntentRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(
        self, *, attempt_id: str, case_id: str, source_id: str, context_id: str,
        target_context_id: str,
        source_revision: int, draft_revision: int, report_fingerprint: str,
        source_key: str, input_fingerprint: str, archive_fingerprint: str,
        manifest_id: str, relative_final_dir: str,
        public_manifest: dict[str, Any], task_id: str | None = None,
        deployment_instance_id: str | None = None, publication_id: str | None = None,
    ) -> dict[str, Any]:
        return create_intent(
            self, attempt_id=attempt_id, case_id=case_id, source_id=source_id,
            context_id=context_id, target_context_id=target_context_id,
            source_revision=source_revision, draft_revision=draft_revision,
            report_fingerprint=report_fingerprint, source_key=source_key,
            input_fingerprint=input_fingerprint, archive_fingerprint=archive_fingerprint,
            manifest_id=manifest_id, relative_final_dir=relative_final_dir,
            public_manifest=public_manifest, task_id=task_id,
            deployment_instance_id=deployment_instance_id, publication_id=publication_id,
        )
    def get_for_attempt(self, attempt_id: str) -> dict[str, Any] | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE attempt_id = ? "
                "AND deployment_instance_id=?",
                (validate_opaque_id(attempt_id), self.database.deployment_instance_id),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else intent_dict(row)

    def list_unfinished(self) -> list[dict[str, Any]]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE deployment_instance_id=? "
                "AND phase NOT IN ('verified', 'conflict') ORDER BY created_at, intent_id",
                (self.database.deployment_instance_id,),
            ).fetchall()
        finally:
            connection.close()
        return [intent_dict(row) for row in rows]

    def mark_phase(self, attempt_id: str, phase: str) -> dict[str, Any]:
        if phase not in _PHASES:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_PUBLISH_INTENT")
        with self.database.transaction() as connection:
            attempt_id = validate_opaque_id(attempt_id)
            current = connection.execute(
                "SELECT phase, publication_status FROM archive_publish_intents "
                "WHERE attempt_id = ? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
            if current is None:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
            current_phase = str(current["phase"])
            if phase in {"published", "indexed", "verified"} and current["publication_status"] not in {
                "sealed", "published", "verified",
            }:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_NOT_SEALED")
            allowed = {
                "intent_persisted": {"intent_persisted", "published", "conflict"},
                "published": {"published", "indexed", "conflict"},
                "indexed": {"indexed", "verified", "conflict"},
                "verified": {"verified"},
                "conflict": {"conflict"},
            }
            if phase not in allowed.get(current_phase, set()):
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_STATE_INVALID")
            updated = connection.execute(
                "UPDATE archive_publish_intents SET phase = ?, updated_at = ? "
                "WHERE attempt_id = ? AND deployment_instance_id=?",
                (phase, utc_now(), attempt_id, self.database.deployment_instance_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
            row = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE attempt_id = ? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
        return intent_dict(row)

    def seal_publication(
        self, attempt_id: str, publication_digest: str,
        file_set: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not _HASH.fullmatch(publication_digest):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
        attempt_id = validate_opaque_id(attempt_id)
        serialized = json.dumps(file_set, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE attempt_id=? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
            current = row["publication_status"] or "pending"
            if current in {"sealed", "published", "verified"}:
                if row["publication_digest"] != publication_digest or row["publication_file_set_json"] != serialized:
                    raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_CONFLICT")
                return intent_dict(row)
            if current != "pending" or row["phase"] != "intent_persisted":
                raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_STATE_INVALID")
            fence = connection.execute(
                "SELECT status, task_id, deployment_instance_id FROM archive_publish_fences "
                "WHERE fence_id=? AND attempt_id=? AND deployment_instance_id=?",
                (row["fence_id"], attempt_id, self.database.deployment_instance_id),
            ).fetchone()
            if (
                fence is None or fence["status"] != "active"
                or fence["deployment_instance_id"] != self.database.deployment_instance_id
                or fence["task_id"] != row["task_id"]
            ):
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_REQUIRED")
            connection.execute(
                "UPDATE archive_publish_intents SET publication_digest=?, "
                "publication_file_set_json=?, publication_status='sealed', updated_at=? "
                "WHERE attempt_id=? AND deployment_instance_id=? AND publication_status='pending'",
                (publication_digest, serialized, utc_now(), attempt_id, self.database.deployment_instance_id),
            )
            result = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE attempt_id=? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
        return intent_dict(result)

    def mark_publication_state(self, attempt_id: str, state: str) -> dict[str, Any]:
        if state not in {"published", "verified", "conflict"}:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_STATE_INVALID")
        attempt_id = validate_opaque_id(attempt_id)
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE attempt_id=? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
            current = row["publication_status"] or "pending"
            if current == state:
                return intent_dict(row)
            if state in {"published", "verified"} and current not in {"sealed", "published", "verified"}:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_NOT_SEALED")
            connection.execute(
                "UPDATE archive_publish_intents SET publication_status=?, updated_at=? "
                "WHERE attempt_id=? AND deployment_instance_id=?",
                (state, utc_now(), attempt_id, self.database.deployment_instance_id),
            )
            result = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE attempt_id=? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
        return intent_dict(result)

    def mark_publication_verified(
        self, publication_id: str, verified_at: str, *, publication_digest: str,
        file_set: list[dict[str, Any]], fence_id: str, case_id: str,
    ) -> dict[str, Any]:
        """Record the first verified UTC fact without changing publication identity.

        Revalidation is intentionally not performed here. The caller must
        supply facts already checked against the durable publication authority.
        The NULL-only predicate prevents ordinary reads or repeated checks from
        moving the retention anchor.
        """
        publication_id = validate_opaque_id(publication_id)
        fence_id = validate_opaque_id(fence_id)
        case_id = validate_opaque_id(case_id)
        if not _HASH.fullmatch(publication_digest):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_INVALID")
        serialized = json.dumps(file_set, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        timestamp = normalize_utc_z(verified_at)
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE publication_id=? "
                "AND deployment_instance_id=? AND case_id=?",
                (publication_id, self.database.deployment_instance_id, case_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
            if row["publication_verified_at"] is not None:
                return intent_dict(row, include_publication_verified_at=True)
            fence = connection.execute(
                "SELECT status FROM archive_publish_fences WHERE fence_id=? AND attempt_id=? "
                "AND deployment_instance_id=?",
                (fence_id, row["attempt_id"], self.database.deployment_instance_id),
            ).fetchone()
            if (
                row["publication_digest"] != publication_digest
                or row["publication_file_set_json"] != serialized
                or row["fence_id"] != fence_id
                or row["publication_status"] not in {"published", "verified"}
                or row["phase"] != "verified"
                or fence is None
                or fence["status"] not in {"active", "pending_verification", "consumed"}
            ):
                raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_VERIFICATION_BLOCKED")
            updated = connection.execute(
                "UPDATE archive_publish_intents SET publication_verified_at=? WHERE intent_id=? "
                "AND deployment_instance_id=? AND publication_verified_at IS NULL "
                "AND publication_id=? AND case_id=? AND publication_digest=? "
                "AND publication_file_set_json=? AND fence_id=?",
                (timestamp, row["intent_id"], self.database.deployment_instance_id,
                 publication_id, case_id, publication_digest, serialized, fence_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_VERIFICATION_CONFLICT")
            result = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE intent_id=? AND deployment_instance_id=?",
                (row["intent_id"], self.database.deployment_instance_id),
            ).fetchone()
        return intent_dict(result, include_publication_verified_at=True)
