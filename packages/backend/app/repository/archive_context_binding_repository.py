"""用于区分工作台归档上下文的持久单向绑定。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_serialization import validate_opaque_id


def context_binding_hash(context_id: str) -> str:
    value = validate_opaque_id(context_id).encode("utf-8")
    return hashlib.sha256(b"workbench-archive-context\0" + value).hexdigest()


def report_fingerprint(report: object) -> str:
    serialized = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def replace_active_binding(
    connection: Any, attempt_id: str, case_id: str, context_id: str,
    *, source_id: str, source_revision: int, draft_revision: int,
    report_hash: str, expires_at: str | None = None,
) -> None:
    attempt_id = validate_opaque_id(attempt_id)
    case_id = validate_opaque_id(case_id)
    digest = context_binding_hash(context_id)
    connection.execute(
        "UPDATE archive_context_bindings SET active = 0 WHERE attempt_id = ?",
        (attempt_id,),
    )
    connection.execute(
        "INSERT INTO archive_context_bindings"
        "(context_hash, attempt_id, case_id, source_id, source_revision, draft_revision, "
        "report_fingerprint, context_kind, active, expires_at, consumed_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'workbench', 1, ?, NULL, ?)",
        (
            digest, attempt_id, case_id, validate_opaque_id(source_id), source_revision,
            draft_revision, report_hash, expires_at, utc_now(),
        ),
    )


def deactivate_bindings(connection: Any, attempt_id: str) -> None:
    connection.execute(
        "UPDATE archive_context_bindings SET active = 0 WHERE attempt_id = ?",
        (validate_opaque_id(attempt_id),),
    )


def find_binding(database: WorkbenchDatabase, context_id: str) -> dict[str, Any] | None:
    connection = database.connect()
    try:
        row = connection.execute(
            "SELECT b.attempt_id, b.case_id, b.source_id, b.source_revision, "
            "b.draft_revision, b.report_fingerprint, b.context_kind, b.active, "
            "b.expires_at, b.consumed_at, a.status "
            "FROM archive_context_bindings b JOIN archive_attempts a "
            "ON a.attempt_id = b.attempt_id WHERE b.context_hash = ?",
            (context_binding_hash(context_id),),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return {
        "attempt_id": str(row["attempt_id"]),
        "case_id": str(row["case_id"]),
        "source_id": str(row["source_id"]),
        "source_revision": int(row["source_revision"]),
        "draft_revision": int(row["draft_revision"]),
        "report_fingerprint": str(row["report_fingerprint"]),
        "context_kind": str(row["context_kind"]),
        "active": bool(row["active"]),
        "expires_at": row["expires_at"],
        "consumed_at": row["consumed_at"],
        "attempt_status": str(row["status"]),
    }


def find_active_binding_for_attempt(
    database: WorkbenchDatabase, attempt_id: str,
) -> dict[str, Any] | None:
    """返回唯一活动的工作台绑定，不暴露其原始上下文。"""
    attempt_id = validate_opaque_id(attempt_id)
    connection = database.connect()
    try:
        rows = connection.execute(
            "SELECT attempt_id, case_id, source_id, source_revision, draft_revision, "
            "report_fingerprint, context_kind, active, expires_at, consumed_at "
            "FROM archive_context_bindings WHERE attempt_id = ? AND active = 1",
            (attempt_id,),
        ).fetchall()
    finally:
        connection.close()
    if len(rows) != 1:
        return None
    row = rows[0]
    return {
        "attempt_id": str(row["attempt_id"]), "case_id": str(row["case_id"]),
        "source_id": str(row["source_id"]), "source_revision": int(row["source_revision"]),
        "draft_revision": int(row["draft_revision"]),
        "report_fingerprint": str(row["report_fingerprint"]),
        "context_kind": str(row["context_kind"]), "active": bool(row["active"]),
        "expires_at": row["expires_at"], "consumed_at": row["consumed_at"],
    }
