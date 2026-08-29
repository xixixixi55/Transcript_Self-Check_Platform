"""归档尝试的持久证据绑定。"""

from __future__ import annotations

import re

from ..workbench_database import WorkbenchDatabase
from ..workbench_errors import WorkbenchPersistenceError
from ..workbench_serialization import validate_opaque_id

_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def bind_manifest_evidence(
    database: WorkbenchDatabase, attempt_id: str, manifest_id: str,
    source_key: str, input_fingerprint: str, archive_fingerprint: str,
) -> None:
    values = (source_key, input_fingerprint, archive_fingerprint)
    if not all(isinstance(value, str) and _FINGERPRINT.fullmatch(value) for value in values):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_COMPLETION_EVIDENCE")
    with database.transaction() as connection:
        updated = connection.execute(
            "UPDATE archive_attempts SET manifest_id = ?, manifest_source_key = ?, "
            "manifest_input_fingerprint = ?, manifest_archive_fingerprint = ?, "
            "revision = revision + 1 WHERE attempt_id = ? AND deployment_instance_id=? "
            "AND status IN ('accepted', 'running')",
            (
                validate_opaque_id(manifest_id), *values,
                validate_opaque_id(attempt_id), database.deployment_instance_id,
            ),
        )
        if updated.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
