"""保留锚点、发布重新验证和失败关闭资格。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ..repository.case_retention_repository import CaseRetentionRepository
from ..repository.retention_policy_repository import RetentionPolicyRepository
from ..repository.retention_time import expires_at_utc
from ..repository.workbench_database import WorkbenchDatabase, normalize_utc_z
from ..repository.workbench_errors import WorkbenchPersistenceError
from ..repository.workbench_serialization import validate_opaque_id
from .case_retention_authority_service import (
    PublicationRevalidator, WordArtifactRevalidator, active_blocker, checked_time, latest_publication,
    latest_word, publication_payload, record_id, run_publication_revalidation,
    run_word_revalidation, validated_publication_facts,
)

_UNKNOWN = {
    "RETENTION_CASE_MUTATION_TIME_MISSING", "RETENTION_PUBLICATION_MISSING",
    "RETENTION_PUBLICATION_UNVERIFIED", "RETENTION_PUBLICATION_TIME_MISSING",
    "RETENTION_WORD_ARTIFACT_MISSING", "RETENTION_WORD_ARTIFACT_UNVERIFIED",
    "RETENTION_TIME_INVALID", "RETENTION_TIME_IN_FUTURE", "RETENTION_AUTHORITY_INCONSISTENT",
    "RETENTION_OWNERSHIP_UNKNOWN",
}


class CaseRetentionService:
    """读取持久事实并持久化安全且可重算的保留投影。"""

    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def evaluate_case(
        self, case_id: str, *, now: datetime | str | None = None,
        publication_revalidator: PublicationRevalidator | None = None,
        word_artifact_revalidator: WordArtifactRevalidator | None = None,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        reference = _reference_time(now)
        policy = RetentionPolicyRepository(self.database).get()
        shell, retention, publications, words = self._load(case_id)
        blocker = run_publication_revalidation(
            self.database, publications, case_id, reference, publication_revalidator,
        )
        if blocker is None and word_artifact_revalidator is not None:
            blocker = run_word_revalidation(words, word_artifact_revalidator)
        shell, retention, publications, words = self._load(case_id)
        anchor, expiry, blocker = self._assess(
            shell, retention, publications, words, policy, reference, blocker,
        )
        return self._persist(
            case_id, shell, retention, policy, anchor, expiry, blocker, reference,
        )

    def revalidate_publication(
        self, publication_id: str, *, case_id: str, now: datetime | str | None = None,
        revalidator: PublicationRevalidator,
    ) -> dict[str, Any]:
        publication_id = validate_opaque_id(publication_id)
        case_id = validate_opaque_id(case_id)
        reference = _reference_time(now)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE publication_id=? "
                "AND deployment_instance_id=? AND case_id=?",
                (publication_id, self.database.deployment_instance_id, case_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("RETENTION_PUBLICATION_MISSING")
            payload = publication_payload(self.database, connection, row)
        verified_at = validated_publication_facts(
            payload, revalidator(payload), reference,
        )
        if row["publication_verified_at"] is None:
            if verified_at is None:
                raise WorkbenchPersistenceError("RETENTION_PUBLICATION_TIME_MISSING")
            return ArchivePublishIntentRepository(self.database).mark_publication_verified(
                publication_id, verified_at, publication_digest=payload["publication_digest"],
                file_set=payload["publication_file_set"], fence_id=payload["fence_id"],
                case_id=case_id,
            )
        return dict(row)

    def _load(self, case_id: str) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
        with self.database.connect() as connection:
            shell = connection.execute(
                "SELECT * FROM case_shells WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchone()
            if shell is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            retention = connection.execute(
                "SELECT * FROM case_retention_records WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchone()
            publications = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE case_id=? AND deployment_instance_id=? "
                "AND publication_id IS NOT NULL ORDER BY publication_id",
                (case_id, self.database.deployment_instance_id),
            ).fetchall()
            words = connection.execute(
                "SELECT * FROM formal_word_artifacts WHERE case_id=? AND deployment_instance_id=? "
                "ORDER BY word_artifact_id",
                (case_id, self.database.deployment_instance_id),
            ).fetchall()
        return dict(shell), None if retention is None else dict(retention), [dict(row) for row in publications], [dict(row) for row in words]

    def _assess(
        self, shell: Mapping[str, Any], retention: Mapping[str, Any] | None,
        publications: list[Mapping[str, Any]], words: list[Mapping[str, Any]],
        policy: Mapping[str, Any], now: datetime, initial_blocker: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        if initial_blocker is not None:
            return None, None, initial_blocker
        if retention is None:
            return None, None, "RETENTION_CASE_MUTATION_TIME_MISSING"
        mutation, blocker = checked_time(retention.get("last_meaningful_mutation_at"), "RETENTION_CASE_MUTATION_TIME_MISSING", now)
        if blocker:
            return None, None, blocker
        if not publications:
            return None, None, "RETENTION_PUBLICATION_MISSING"
        publication_times: list[str] = []
        with self.database.connect() as connection:
            for row in publications:
                try:
                    publication_payload(self.database, connection, row)
                except WorkbenchPersistenceError as error:
                    return None, None, error.code
                if row["phase"] != "verified" or row["publication_status"] != "verified":
                    return None, None, "RETENTION_PUBLICATION_UNVERIFIED"
                value, blocker = checked_time(row.get("publication_verified_at"), "RETENTION_PUBLICATION_TIME_MISSING", now)
                if blocker:
                    return None, None, blocker
                publication_times.append(value)
        if not words:
            return None, None, "RETENTION_WORD_ARTIFACT_MISSING"
        word_times: list[str] = []
        publication_ids = {row["publication_id"] for row in publications}
        for row in words:
            if row["publication_id"] not in publication_ids or row["status"] != "verified":
                return None, None, "RETENTION_WORD_ARTIFACT_UNVERIFIED"
            if len(str(row["file_digest"])) != 64 or len(str(row["source_manifest_digest"])) != 64:
                return None, None, "RETENTION_AUTHORITY_INCONSISTENT"
            value, blocker = checked_time(row.get("verified_at"), "RETENTION_WORD_ARTIFACT_UNVERIFIED", now)
            if blocker:
                return None, None, blocker
            word_times.append(value)
        if shell.get("lifecycle") not in {"exported", "record_retention_expired"}:
            return None, None, "RETENTION_AUTHORITY_INCONSISTENT"
        blocker = active_blocker(self.database, shell["case_id"])
        if blocker:
            return None, None, blocker
        times = [mutation, max(publication_times), max(word_times)]
        anchor = max(times)
        try:
            expiry = expires_at_utc(anchor, int(policy["retention_days"]), now=now)
        except WorkbenchPersistenceError as error:
            return None, None, error.code
        return anchor, expiry, None if expiry <= _iso(now) else "RETENTION_NOT_EXPIRED"

    def _persist(self, case_id: str, shell: Mapping[str, Any], retention: Mapping[str, Any] | None, policy: Mapping[str, Any], anchor: str | None, expiry: str | None, blocker: str | None, now: datetime) -> dict[str, Any]:
        eligibility = "eligible" if blocker is None else ("unknown" if blocker in _UNKNOWN else "ineligible")
        status = "eligible" if blocker is None else ("not_expired" if blocker == "RETENTION_NOT_EXPIRED" else ("unknown" if eligibility == "unknown" else "blocked"))
        now_value = _iso(now)
        record = CaseRetentionRepository(self.database).upsert({
            "retention_record_id": retention.get("retention_record_id") if retention else record_id(self.database.deployment_instance_id, case_id),
            "case_id": case_id, "eligibility": eligibility, "status": status,
            "last_meaningful_mutation_at": _persistable_time(retention.get("last_meaningful_mutation_at")) if retention else None,
            "latest_verified_formal_publication_at": _persistable_time(latest_publication(self.database, case_id)),
            "latest_successful_word_export_at": _persistable_time(latest_word(self.database, case_id)),
            "retention_anchor_utc": anchor, "expires_at_utc": expiry, "last_blocker_code": blocker,
            "policy_revision": policy["policy_revision"], "case_revision": shell["revision"],
            "cleanup_revision": retention.get("cleanup_revision", 0) if retention else 0,
            "created_at": retention.get("created_at", now_value) if retention else now_value,
            "updated_at": now_value,
        })
        return {**record, "policy_mode": policy["mode"], "enforce_allowed": policy["mode"] == "enforce"}

def _reference_time(value: datetime | str | None) -> datetime:
    parsed = datetime.now(timezone.utc) if value is None else (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkbenchPersistenceError("RETENTION_TIME_INVALID")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _persistable_time(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return normalize_utc_z(value)
    except WorkbenchPersistenceError:
        return None
