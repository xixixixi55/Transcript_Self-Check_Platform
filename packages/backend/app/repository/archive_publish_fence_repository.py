"""正式发布短临界区的内部持久围栏。"""

from __future__ import annotations

from typing import Any

from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id


def active_for_case(connection: Any, case_id: str) -> Any | None:
    return connection.execute(
        "SELECT * FROM archive_publish_fences WHERE case_id = ? AND status = 'active' "
        "AND deployment_instance_id = (SELECT deployment_instance_id FROM workbench_deployment_owner WHERE owner_id=1)",
        (validate_opaque_id(case_id),),
    ).fetchone()


def active_for_source(connection: Any, source_id: str) -> Any | None:
    return connection.execute(
        "SELECT * FROM archive_publish_fences WHERE source_id = ? AND status = 'active' "
        "AND deployment_instance_id = (SELECT deployment_instance_id FROM workbench_deployment_owner WHERE owner_id=1)",
        (validate_opaque_id(source_id),),
    ).fetchone()


def reject_if_active(connection: Any, *, case_id: str | None = None, source_id: str | None = None) -> None:
    row = None
    if case_id is not None:
        row = active_for_case(connection, case_id)
    if row is None and source_id is not None:
        row = active_for_source(connection, source_id)
    if row is not None:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_ACTIVE")


def invalidate_pending(connection: Any, *, case_id: str | None = None, source_id: str | None = None) -> None:
    """允许重启后编辑，同时使旧证据无法完成。"""
    clauses: list[str] = []
    values: list[str] = []
    if case_id is not None:
        clauses.append("case_id = ?")
        values.append(validate_opaque_id(case_id))
    if source_id is not None:
        clauses.append("source_id = ?")
        values.append(validate_opaque_id(source_id))
    if not clauses:
        return
    connection.execute(
        "UPDATE archive_publish_fences SET status = 'invalidated', "
        "reason = 'ARCHIVE_BINDING_EDITED', updated_at = ? WHERE status = 'pending_verification' "
        "AND deployment_instance_id = (SELECT deployment_instance_id FROM workbench_deployment_owner WHERE owner_id=1) "
        "AND (" + " OR ".join(clauses) + ")",
        (utc_now(), *values),
    )


def get(database: WorkbenchDatabase, fence_id: str) -> dict[str, Any] | None:
    fence_id = validate_opaque_id(fence_id)
    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE fence_id = ? AND deployment_instance_id=?",
            (fence_id, database.deployment_instance_id),
        ).fetchone()
    finally:
        connection.close()
    return None if row is None else dict(row)


def set_status(
    database: WorkbenchDatabase, fence_id: str, status: str, reason: str | None = None,
) -> dict[str, Any]:
    if status not in {"active", "pending_verification", "consumed", "released", "invalidated"}:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_STATE_INVALID")
    fence_id = validate_opaque_id(fence_id)
    with database.transaction() as connection:
        updated = connection.execute(
            "UPDATE archive_publish_fences SET status = ?, reason = ?, updated_at = ? "
            "WHERE fence_id = ? AND deployment_instance_id=? AND status != 'consumed'",
            (status, reason, utc_now(), fence_id, database.deployment_instance_id),
        )
        if updated.rowcount != 1:
            row = connection.execute(
                "SELECT * FROM archive_publish_fences WHERE fence_id = ? AND deployment_instance_id=?",
                (fence_id, database.deployment_instance_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_NOT_FOUND")
            if row["status"] == status:
                return dict(row)
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_STATE_INVALID")
        row = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE fence_id = ? AND deployment_instance_id=?",
            (fence_id, database.deployment_instance_id),
        ).fetchone()
    return dict(row)


def normalize_active_for_restart(database: WorkbenchDatabase) -> list[dict[str, Any]]:
    """将过期运行时围栏转换为证据待定围栏，绝不转换为运行中围栏。"""
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE status = 'active' "
            "AND deployment_instance_id=? ORDER BY created_at, fence_id",
            (database.deployment_instance_id,),
        ).fetchall()
        if rows:
            connection.execute(
                "UPDATE archive_publish_fences SET status = 'pending_verification', "
                "reason = 'ARCHIVE_RESTART_PENDING_VERIFICATION', updated_at = ? "
                "WHERE status = 'active' AND deployment_instance_id=?",
                (utc_now(), database.deployment_instance_id),
            )
    return [dict(row) for row in rows]


def assert_publishable(database: WorkbenchDatabase, attempt_id: str) -> dict[str, Any]:
    attempt_id = validate_opaque_id(attempt_id)
    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE attempt_id = ? "
            "AND deployment_instance_id=? AND status = 'active'",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_REQUIRED")
    return dict(row)
