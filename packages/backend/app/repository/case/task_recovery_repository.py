"""进程重启后以事务方式规范化解析和归档任务。"""

from __future__ import annotations

from ..workbench.workbench_database import WorkbenchDatabase, utc_now
from ..workbench.workbench_errors import WorkbenchPersistenceError


def recover_tasks_after_restart(
    database: WorkbenchDatabase, *, include_archive: bool = True,
) -> list[str]:
    interrupted: list[str] = []
    now = utc_now()
    archive_clause = (
        " OR (kind='archive' AND status IN ('running','cancelling'))"
        if include_archive else ""
    )
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT task_id,case_id,kind,status FROM task_records WHERE "
            "(kind='parse' AND status IN ('queued','running','cancelling'))"
            + archive_clause
        ).fetchall()
        for row in rows:
            next_status = "failed_retryable" if row["status"] == "queued" else "interrupted"
            worker_state = "waiting_reclaim" if row["kind"] == "archive" else None
            actions = '["view_details","retry"]' if row["kind"] == "archive" else "[]"
            updated = connection.execute(
                "UPDATE task_records SET status=?,error_code='TASK_RESTART_INTERRUPTED',"
                "error_summary='TASK_RESTART_INTERRUPTED',worker_state=?,"
                "allowed_actions_json=?,updated_at=?,revision=revision+1 "
                "WHERE task_id=? AND status IN ('queued','running','cancelling')",
                (next_status, worker_state, actions, now, row["task_id"]),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
            if row["kind"] == "parse":
                shell_updated = connection.execute(
                    "UPDATE case_shells SET lifecycle='parse_failed_retryable',"
                    "report_available=0,revision=revision+1,updated_at=? "
                    "WHERE case_id=? AND lifecycle IN "
                    "('parse_queued','parsing','cancelling')",
                    (now, row["case_id"]),
                )
                if shell_updated.rowcount != 1:
                    raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            interrupted.append(str(row["task_id"]))
    return interrupted
