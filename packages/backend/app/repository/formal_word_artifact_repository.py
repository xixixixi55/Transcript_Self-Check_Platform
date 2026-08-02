"""Durable Word artifact identity and safe projection foundation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .retention_repository_helpers import identifier, optional_time, relative_path, required_time, text
from .workbench_database import WorkbenchDatabase, utc_now_z
from .workbench_errors import WorkbenchPersistenceError

_STATUSES = {"pending", "verified", "invalid"}


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
        if status == "verified" and verified_at is None:
            raise WorkbenchPersistenceError("INVALID_WORD_ARTIFACT")
        now = utc_now_z()
        fields = (
            artifact_id, self.database.deployment_instance_id, case_id, publication_id,
            relative_path(value.get("internal_relative_path")), text(value.get("file_digest")),
            int(value.get("file_size", -1)), text(value.get("source_manifest_digest")),
            identifier(value.get("template_identity")), identifier(value.get("template_version")),
            required_time(value.get("generated_at", now)), verified_at, status,
            required_time(value.get("created_at", now)), required_time(value.get("updated_at", now)),
        )
        if fields[6] < 0:
            raise WorkbenchPersistenceError("INVALID_WORD_ARTIFACT")
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
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM formal_word_artifacts WHERE word_artifact_id=? AND deployment_instance_id=?",
                (identifier(artifact_id), self.database.deployment_instance_id),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("WORD_ARTIFACT_NOT_FOUND")
        return dict(row)

    def get_public(self, artifact_id: str) -> dict[str, Any]:
        value = self.get_internal(artifact_id)
        return {key: value[key] for key in (
            "word_artifact_id", "case_id", "publication_id", "file_digest", "file_size",
            "source_manifest_digest", "template_identity", "template_version",
            "generated_at", "verified_at", "status",
        )}
