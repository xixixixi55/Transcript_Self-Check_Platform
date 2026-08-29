"""持久案件保留事实；此处不启动资格扫描或删除。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..retention_repository_helpers import identifier, optional_time, required_time
from ..workbench_database import WorkbenchDatabase, utc_now_z
from ..workbench_errors import WorkbenchPersistenceError

_ELIGIBILITY = {"eligible", "ineligible", "unknown"}
_STATUS = {"unknown", "not_expired", "eligible", "blocked", "planned", "processing", "completed", "failed"}


class CaseRetentionRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def upsert(self, value: Mapping[str, Any]) -> dict[str, Any]:
        case_id = identifier(value.get("case_id"))
        eligibility = value.get("eligibility", "unknown")
        status = value.get("status", "unknown")
        if eligibility not in _ELIGIBILITY or status not in _STATUS:
            raise WorkbenchPersistenceError("INVALID_RETENTION_RECORD")
        record_id = identifier(value.get("retention_record_id"))
        now = utc_now_z()
        fields = (
            record_id, self.database.deployment_instance_id, case_id, eligibility, status,
            optional_time(value.get("last_meaningful_mutation_at")),
            optional_time(value.get("latest_verified_formal_publication_at")),
            optional_time(value.get("latest_successful_word_export_at")),
            optional_time(value.get("retention_anchor_utc")), optional_time(value.get("expires_at_utc")),
            value.get("last_blocker_code"), int(value.get("policy_revision", 1)),
            int(value.get("case_revision", 0)), int(value.get("cleanup_revision", 0)),
            required_time(value.get("created_at", now)), required_time(value.get("updated_at", now)),
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO case_retention_records(retention_record_id,deployment_instance_id,case_id,"
                    "eligibility,status,last_meaningful_mutation_at,latest_verified_formal_publication_at,"
                    "latest_successful_word_export_at,retention_anchor_utc,expires_at_utc,last_blocker_code,"
                    "policy_revision,case_revision,cleanup_revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(deployment_instance_id,case_id) DO UPDATE SET "
                    "eligibility=excluded.eligibility,status=excluded.status,"
                    "last_meaningful_mutation_at=excluded.last_meaningful_mutation_at,"
                    "latest_verified_formal_publication_at=excluded.latest_verified_formal_publication_at,"
                    "latest_successful_word_export_at=excluded.latest_successful_word_export_at,"
                    "retention_anchor_utc=excluded.retention_anchor_utc,expires_at_utc=excluded.expires_at_utc,"
                    "last_blocker_code=excluded.last_blocker_code,policy_revision=excluded.policy_revision,"
                    "case_revision=excluded.case_revision,cleanup_revision=excluded.cleanup_revision,"
                    "updated_at=excluded.updated_at",
                    fields,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("RETENTION_RECORD_CREATE_FAILED") from error
        return self.get_by_case(case_id)

    def get_by_case(self, case_id: str) -> dict[str, Any]:
        case_id = identifier(case_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM case_retention_records WHERE deployment_instance_id=? AND case_id=?",
                (self.database.deployment_instance_id, case_id),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("RETENTION_RECORD_NOT_FOUND")
        return _record_dict(row)


def _record_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("policy_revision", "case_revision", "cleanup_revision"):
        result[key] = int(result[key])
    return result
