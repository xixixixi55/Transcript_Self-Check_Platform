"""内部保留权威和时间戳辅助函数。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from ...repository.archive.archive_publish_intent_repository import ArchivePublishIntentRepository
from ...repository.workbench_database import WorkbenchDatabase
from ...repository.workbench_errors import WorkbenchPersistenceError
from ...repository.retention_time import trusted_utc_timestamp
from ..archive.archive_publication_identity_service import publication_digest

PublicationRevalidator = Callable[[Mapping[str, Any]], Mapping[str, Any] | None]
WordArtifactRevalidator = Callable[[Mapping[str, Any]], Mapping[str, Any] | None]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ACTIVE_TASKS = ("queued", "running", "cancelling", "interrupted", "failed_retryable")
_ACTIVE_RUNS = (
    "planned", "claimed", "preflighted", "work_files_cleaned", "records_cleaned",
    "verified", "interrupted", "partial_failure", "failed_retryable", "cancel_requested",
)


def run_publication_revalidation(
    database: WorkbenchDatabase, rows: list[dict[str, Any]], case_id: str,
    now: datetime, revalidator: PublicationRevalidator | None,
) -> str | None:
    for row in rows:
        try:
            with database.connect() as connection:
                payload = publication_payload(database, connection, row)
            if row["publication_verified_at"] is None:
                if revalidator is None:
                    return "RETENTION_PUBLICATION_UNVERIFIED"
                verified_at = validated_publication_facts(payload, revalidator(payload), now)
                if verified_at is None:
                    return "RETENTION_PUBLICATION_TIME_MISSING"
                ArchivePublishIntentRepository(database).mark_publication_verified(
                    row["publication_id"], verified_at,
                    publication_digest=payload["publication_digest"],
                    file_set=payload["publication_file_set"], fence_id=payload["fence_id"],
                    case_id=case_id,
                )
            elif revalidator is not None:
                validated_publication_facts(payload, revalidator(payload), now)
        except WorkbenchPersistenceError as error:
            return error.code if error.code.startswith("RETENTION_") else "RETENTION_PUBLICATION_UNVERIFIED"
        except Exception:
            return "RETENTION_PUBLICATION_UNVERIFIED"
    return None


def run_word_revalidation(
    rows: list[dict[str, Any]], revalidator: WordArtifactRevalidator,
) -> str | None:
    for row in rows:
        try:
            facts = revalidator({key: row[key] for key in (
                "word_artifact_id", "case_id", "publication_id", "file_digest", "file_size",
                "source_manifest_digest", "template_identity", "template_version", "verified_at",
            )})
            if not isinstance(facts, Mapping) or facts.get("verified") is not True:
                return "RETENTION_WORD_ARTIFACT_UNVERIFIED"
            if any(facts.get(key) is not True for key in ("physical_file_verified", "manifest_verified", "ownership_verified")):
                return "RETENTION_WORD_ARTIFACT_UNVERIFIED"
            if facts.get("file_digest") != row["file_digest"] or facts.get("file_size") != row["file_size"]:
                return "RETENTION_AUTHORITY_INCONSISTENT"
            if facts.get("source_manifest_digest") != row["source_manifest_digest"]:
                return "RETENTION_AUTHORITY_INCONSISTENT"
        except Exception:
            return "RETENTION_WORD_ARTIFACT_UNVERIFIED"
    return None


def active_blocker(database: WorkbenchDatabase, case_id: str) -> str | None:
    placeholders = ",".join("?" for _ in _ACTIVE_TASKS)
    with database.connect() as connection:
        if connection.execute(
            f"SELECT 1 FROM task_records WHERE case_id=? AND deployment_instance_id=? AND status IN ({placeholders}) LIMIT 1",
            (case_id, database.deployment_instance_id, *_ACTIVE_TASKS),
        ).fetchone() is not None:
            return "RETENTION_ACTIVE_TASK"
        if connection.execute(
            "SELECT 1 FROM edit_leases WHERE case_id=? AND status='active' LIMIT 1", (case_id,),
        ).fetchone() is not None:
            return "RETENTION_ACTIVE_LEASE"
        if connection.execute(
            "SELECT 1 FROM archive_publish_fences WHERE case_id=? AND deployment_instance_id=? "
            "AND status IN ('active','pending_verification') LIMIT 1",
            (case_id, database.deployment_instance_id),
        ).fetchone() is not None:
            return "RETENTION_RECOVERY_IN_PROGRESS"
        if connection.execute(
            "SELECT 1 FROM archive_context_bindings WHERE case_id=? AND active=1 LIMIT 1", (case_id,),
        ).fetchone() is not None:
            return "RETENTION_RECOVERY_IN_PROGRESS"
        if connection.execute(
            "SELECT 1 FROM archive_attempts WHERE case_id=? AND deployment_instance_id=? "
            "AND (status IN ('accepted','running','interrupted') OR cleanup_status IN ('pending','unknown')) LIMIT 1",
            (case_id, database.deployment_instance_id),
        ).fetchone() is not None:
            return "RETENTION_RECOVERY_IN_PROGRESS"
        snapshots = connection.execute(
            "SELECT s.status,s.deployment_instance_id,s.case_id,s.task_id,t.case_id AS task_case,"
            "t.deployment_instance_id AS task_deployment,a.status AS attempt_status,a.cleanup_status "
            "FROM archive_input_snapshots s LEFT JOIN task_records t ON t.task_id=s.task_id "
            "LEFT JOIN archive_attempts a ON a.attempt_id=s.attempt_id WHERE s.case_id=?", (case_id,),
        ).fetchall()
        for snapshot in snapshots:
            if snapshot["deployment_instance_id"] != database.deployment_instance_id or snapshot["task_case"] != case_id or snapshot["task_deployment"] != database.deployment_instance_id:
                return "RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN"
            if snapshot["status"] in {"copying", "sealed"}:
                return "RETENTION_SNAPSHOT_ACTIVE"
            if snapshot["attempt_status"] in {"interrupted", "running"} or snapshot["cleanup_status"] in {"pending", "unknown"}:
                return "RETENTION_SNAPSHOT_RECOVERY_REFERENCED"
        runs = ",".join("?" for _ in _ACTIVE_RUNS)
        if connection.execute(
            f"SELECT 1 FROM case_cleanup_runs WHERE case_id=? AND deployment_instance_id=? AND current_phase IN ({runs}) LIMIT 1",
            (case_id, database.deployment_instance_id, *_ACTIVE_RUNS),
        ).fetchone() is not None:
            return "RETENTION_RECOVERY_IN_PROGRESS"
    return None


def publication_payload(database: WorkbenchDatabase, connection: Any, row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        manifest = json.loads(row["public_manifest_json"])
        file_set = json.loads(row["publication_file_set_json"])
        if not isinstance(manifest, Mapping) or not isinstance(file_set, list) or not row["publication_id"] or not _SHA256.fullmatch(str(row["publication_digest"])):
            raise ValueError
        expected_digest, expected_set = publication_digest(dict(row), manifest)
        if expected_digest != row["publication_digest"] or expected_set != file_set:
            raise ValueError
        fence = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE fence_id=? AND attempt_id=? "
            "AND case_id=? AND deployment_instance_id=?",
            (row["fence_id"], row["attempt_id"], row["case_id"], database.deployment_instance_id),
        ).fetchone()
        attempt = connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id=? AND case_id=? AND deployment_instance_id=?",
            (row["attempt_id"], row["case_id"], database.deployment_instance_id),
        ).fetchone()
        if fence is None or attempt is None or fence["task_id"] != row["task_id"] or fence["status"] not in {"active", "pending_verification", "consumed"}:
            raise ValueError
    except Exception as error:
        raise WorkbenchPersistenceError("RETENTION_AUTHORITY_INCONSISTENT") from error
    return {
        "publication_id": row["publication_id"], "case_id": row["case_id"],
        "deployment_instance_id": row["deployment_instance_id"], "attempt_id": row["attempt_id"],
        "task_id": row["task_id"], "source_id": row["source_id"], "manifest_id": row["manifest_id"],
        "relative_final_dir": row["relative_final_dir"], "fence_id": row["fence_id"],
        "publication_digest": row["publication_digest"], "publication_file_set": file_set,
        "public_manifest": manifest, "phase": row["phase"],
        "publication_status": row["publication_status"],
    }


def validated_publication_facts(
    payload: Mapping[str, Any], facts: Mapping[str, Any] | None, now: datetime,
) -> str | None:
    if not isinstance(facts, Mapping) or facts.get("verified") is not True:
        raise WorkbenchPersistenceError("RETENTION_PUBLICATION_UNVERIFIED")
    if any(facts.get(key) is not True for key in (
        "rar_verified", "manifest_verified", "md5_verified", "inventory_verified", "ownership_verified",
    )):
        raise WorkbenchPersistenceError("RETENTION_AUTHORITY_INCONSISTENT")
    for key in ("publication_digest", "publication_file_set", "fence_id", "case_id", "deployment_instance_id"):
        if facts.get(key) != payload[key]:
            raise WorkbenchPersistenceError("RETENTION_AUTHORITY_INCONSISTENT")
    if facts.get("verified_at") is None:
        return None
    return trusted_utc_timestamp(facts["verified_at"], now=now)


def checked_time(value: Any, missing_code: str, now: datetime) -> tuple[str | None, str | None]:
    if value is None:
        return None, missing_code
    try:
        return trusted_utc_timestamp(value, now=now), None
    except WorkbenchPersistenceError as error:
        return None, error.code if error.code in {"RETENTION_TIME_INVALID", "RETENTION_TIME_IN_FUTURE"} else missing_code


def record_id(deployment_id: str, case_id: str) -> str:
    return "retention-" + hashlib.sha256(f"{deployment_id}:{case_id}".encode()).hexdigest()


def latest_publication(database: WorkbenchDatabase, case_id: str) -> str | None:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT MAX(publication_verified_at) FROM archive_publish_intents WHERE case_id=? "
            "AND deployment_instance_id=? AND phase='verified' AND publication_status='verified'",
            (case_id, database.deployment_instance_id),
        ).fetchone()
    return row[0]


def latest_word(database: WorkbenchDatabase, case_id: str) -> str | None:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT MAX(verified_at) FROM formal_word_artifacts WHERE case_id=? "
            "AND deployment_instance_id=? AND status='verified'",
            (case_id, database.deployment_instance_id),
        ).fetchone()
    return row[0]
