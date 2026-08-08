"""Durable short leases for queued process-local archive contexts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .archive_attempt_restart_repository import _interrupt_attempt_in_transaction
from .archive_context_binding_repository import context_binding_hash
from .workbench_constants import ARCHIVE_TASK_ACTIONS
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text
from .workbench_serialization import validate_opaque_id


def lease_queued_runtime_context(
    database: WorkbenchDatabase, *, task_id: str, context_id: str, expires_at: str,
) -> bool:
    """Renew a context binding without changing the public task revision."""
    task_id = validate_opaque_id(task_id)
    context_hash = context_binding_hash(validate_opaque_id(context_id))
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT process_binding_json FROM task_records WHERE task_id=? AND kind='archive' "
            "AND deployment_instance_id=? AND status='queued'",
            (task_id, database.deployment_instance_id),
        ).fetchone()
        if row is None:
            return False
        binding = _binding(row["process_binding_json"])
        if not binding.get("staging_asset_id"):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        updated = connection.execute(
            "UPDATE archive_context_bindings SET expires_at=? WHERE attempt_id=? "
            "AND context_hash=? AND active=1",
            (expires_at, binding["staging_asset_id"], context_hash),
        )
        return updated.rowcount == 1


def interrupt_expired_queued_contexts(
    database: WorkbenchDatabase, *, observed_at: datetime | None = None,
    ownerless_grace_seconds: float = 30.0,
) -> list[str]:
    """Converge expired or never-leased bound tasks after a short grace."""
    observed = observed_at or datetime.now(timezone.utc)
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT t.task_id,t.process_binding_json,t.created_at,b.context_hash,b.expires_at "
            "FROM task_records t LEFT JOIN archive_attempts a ON a.task_id=t.task_id "
            "AND a.deployment_instance_id=t.deployment_instance_id "
            "LEFT JOIN archive_context_bindings b ON b.attempt_id=a.attempt_id AND b.active=1 "
            "WHERE t.kind='archive' AND t.deployment_instance_id=? AND t.status='queued'",
            (database.deployment_instance_id,),
        ).fetchall()
    interrupted = []
    for row in rows:
        binding = _binding(row["process_binding_json"])
        if row["expires_at"] is not None:
            should_interrupt = _lease_expired(row["expires_at"], observed)
        else:
            should_interrupt = bool(
                binding.get("staging_asset_id")
                and _timestamp_older_than(
                    row["created_at"], observed, ownerless_grace_seconds,
                )
            )
        if should_interrupt and interrupt_queued_runtime_context(
            database, task_id=str(row["task_id"]),
            expected_context_hash=(str(row["context_hash"]) if row["context_hash"] else None),
            expires_before=observed if row["expires_at"] is not None else None,
            require_unleased=row["expires_at"] is None,
        ):
            interrupted.append(str(row["task_id"]))
    return interrupted


def interrupt_queued_runtime_context(
    database: WorkbenchDatabase, *, task_id: str,
    expected_context_hash: str | None = None,
    expires_before: datetime | None = None,
    require_unleased: bool = False,
) -> bool:
    """Atomically interrupt one unclaimed task after its context is lost."""
    task_id = validate_opaque_id(task_id)
    now = utc_now()
    with database.transaction() as connection:
        task = connection.execute(
            "SELECT * FROM task_records WHERE task_id=? AND kind='archive' "
            "AND deployment_instance_id=?",
            (task_id, database.deployment_instance_id),
        ).fetchone()
        if task is None or task["status"] != "queued":
            return False
        attempt_id = _binding(task["process_binding_json"]).get("staging_asset_id")
        if not attempt_id:
            return False
        binding = connection.execute(
            "SELECT context_hash,expires_at FROM archive_context_bindings "
            "WHERE attempt_id=? AND active=1", (attempt_id,),
        ).fetchone()
        if binding is None:
            return False
        if expected_context_hash is not None and binding["context_hash"] != expected_context_hash:
            return False
        if require_unleased and binding["expires_at"] is not None:
            return False
        if expires_before is not None and not _lease_expired(binding["expires_at"], expires_before):
            return False
        attempt = connection.execute(
            "SELECT case_id,status FROM archive_attempts WHERE attempt_id=? AND task_id=? "
            "AND deployment_instance_id=?",
            (attempt_id, task_id, database.deployment_instance_id),
        ).fetchone()
        if attempt is not None and attempt["status"] in {"accepted", "running"}:
            _interrupt_attempt_in_transaction(
                connection, attempt_id, attempt["case_id"], now,
                deployment_instance_id=database.deployment_instance_id,
                error_code="ARCHIVE_RUNTIME_CONTEXT_EXPIRED",
            )
        updated = connection.execute(
            "UPDATE task_records SET status='interrupted', error_code=?, error_summary=?, "
            "finished_at=?, updated_at=?, worker_state='waiting_reclaim', "
            "allowed_actions_json=?, revision=revision+1 WHERE task_id=? "
            "AND deployment_instance_id=? AND status='queued'",
            (
                "ARCHIVE_RUNTIME_CONTEXT_EXPIRED",
                "Archive runtime context expired before execution.", now, now,
                json_text(ARCHIVE_TASK_ACTIONS["interrupted"]), task_id,
                database.deployment_instance_id,
            ),
        )
        return updated.rowcount == 1


def _binding(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _lease_expired(value: object, observed_at: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= observed_at


def _timestamp_older_than(value: object, observed_at: datetime, seconds: float) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp() + max(0.0, seconds) <= observed_at.timestamp()
