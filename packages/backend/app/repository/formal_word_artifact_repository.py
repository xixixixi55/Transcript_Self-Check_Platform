"""Durable Word artifact identity and safe projection foundation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .retention_repository_helpers import identifier, optional_time, relative_path, required_time, text
from .workbench_database import WorkbenchDatabase, utc_now_z
from .workbench_errors import WorkbenchPersistenceError

_STATUSES = {"pending", "verified", "invalid"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_FILE_SIZE = 2**53 - 1


def _digest(value: Any) -> str:
    digest = text(value, "INVALID_WORD_ARTIFACT")
    if not _SHA256.fullmatch(digest):
        raise WorkbenchPersistenceError("INVALID_WORD_ARTIFACT")
    return digest


def _file_size(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_FILE_SIZE:
        raise WorkbenchPersistenceError("INVALID_WORD_ARTIFACT")
    return value


class FormalWordArtifactRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, value: Mapping[str, Any]) -> dict[str, Any]:
        artifact_id = identifier(value.get("word_artifact_id"))
        case_id = identifier(value.get("case_id"))
        publication_id = identifier(value.get("publication_id"))
        status = value.get("status", "pending")
        if status not in _STATUSES:
            raise WorkbenchPersistenceError("INVALID_WORD_ARTIFACT")
        verified_at = optional_time(value.get("verified_at"))
        if (status == "verified") != (verified_at is not None):
            raise WorkbenchPersistenceError("INVALID_WORD_ARTIFACT")
        now = utc_now_z()
        fields = (
            artifact_id, self.database.deployment_instance_id, case_id, publication_id,
            relative_path(value.get("internal_relative_path")), _digest(value.get("file_digest")),
            _file_size(value.get("file_size", -1)), _digest(value.get("source_manifest_digest")),
            identifier(value.get("template_identity")), identifier(value.get("template_version")),
            required_time(value.get("generated_at", now)), verified_at, status,
            required_time(value.get("created_at", now)), required_time(value.get("updated_at", now)),
        )
        with self.database.transaction() as connection:
            publication = connection.execute(
                "SELECT phase,publication_status,publication_verified_at FROM archive_publish_intents "
                "WHERE publication_id=? AND deployment_instance_id=? AND case_id=?",
                (publication_id, self.database.deployment_instance_id, case_id),
            ).fetchone()
            if publication is None:
                raise WorkbenchPersistenceError("WORD_ARTIFACT_PUBLICATION_NOT_FOUND")
            if status == "verified" and (
                publication["phase"] != "verified"
                or publication["publication_status"] != "verified"
                or publication["publication_verified_at"] is None
            ):
                raise WorkbenchPersistenceError("WORD_ARTIFACT_PUBLICATION_UNVERIFIED")
            try:
                connection.execute(
                    "INSERT INTO formal_word_artifacts(word_artifact_id,deployment_instance_id,case_id,"
                    "publication_id,internal_relative_path,file_digest,file_size,source_manifest_digest,"
                    "template_identity,template_version,generated_at,verified_at,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    fields,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("WORD_ARTIFACT_CREATE_FAILED") from error
        return self.get_internal(artifact_id)

    def get_internal(self, artifact_id: str) -> dict[str, Any]:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM formal_word_artifacts WHERE word_artifact_id=? AND deployment_instance_id=?",
                (identifier(artifact_id), self.database.deployment_instance_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("WORD_ARTIFACT_NOT_FOUND")
            publication = connection.execute(
                "SELECT phase,publication_status,publication_verified_at FROM archive_publish_intents "
                "WHERE publication_id=? AND deployment_instance_id=? AND case_id=?",
                (row["publication_id"], self.database.deployment_instance_id, row["case_id"]),
            ).fetchone()
            if publication is None:
                raise WorkbenchPersistenceError("WORD_ARTIFACT_PUBLICATION_NOT_FOUND")
            if row["status"] == "verified" and (
                publication["phase"] != "verified"
                or publication["publication_status"] != "verified"
                or publication["publication_verified_at"] is None
            ):
                raise WorkbenchPersistenceError("WORD_ARTIFACT_PUBLICATION_UNVERIFIED")
            return dict(row)

    def get_public(self, artifact_id: str) -> dict[str, Any]:
        value = self.get_internal(artifact_id)
        return {key: value[key] for key in (
            "word_artifact_id", "case_id", "publication_id", "file_digest", "file_size",
            "source_manifest_digest", "template_identity", "template_version",
            "generated_at", "verified_at", "status",
        )}
