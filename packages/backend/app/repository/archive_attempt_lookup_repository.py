"""Deployment-scoped lookups used by archive completion persistence."""

from __future__ import annotations

from typing import Any

from .archive_attempt_projection_repository import public_attempt
from .workbench_database import WorkbenchDatabase


def row(database: WorkbenchDatabase, attempt_id: str) -> Any:
    connection = database.connect()
    try:
        return connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id=? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
    finally:
        connection.close()


def public(database: WorkbenchDatabase, attempt_id: str) -> dict[str, Any]:
    return public_attempt(row(database, attempt_id))
