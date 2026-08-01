"""Durable publish intent records used to reconcile filesystem/database gaps."""

from __future__ import annotations

import json
import re
from typing import Any

from .archive_publish_identity_repository import intent_dict, same_publish_identity
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id

_HASH = re.compile(r"^[0-9a-f]{64}$")
_PHASES = {"intent_persisted", "published", "indexed", "verified", "conflict"}


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
        from .archive_publish_intent_create_repository import create_intent
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
