"""Conservative cleanup for task-owned input snapshots left by a crash."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..repository.archive_input_snapshot_repository import ArchiveInputSnapshotRepository
from ..repository.workbench_database import WorkbenchDatabase
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_input_snapshot_files_service import (
    assert_marker, assert_snapshot_tree_safe, make_tree_writable,
    resolve_snapshot_dir, snapshot_name_matches_id,
)


def cleanup_unfinished_snapshot(
    database: WorkbenchDatabase, output_root: str | Path, value: dict[str, Any],
) -> str:
    """Remove only a durable row's exact task-owned copying/sealed paths.

    A copying row is durable ownership evidence even when the marker was not
    flushed before a process died.  The locator is still resolved below a
    controlled legacy or short snapshot root and the only candidates are the
    row's exact final name and its exact ``.copying`` sibling.
    """
    if value.get("deployment_instance_id") != database.deployment_instance_id:
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_MISMATCH")
    snapshot_id = str(value.get("snapshot_id") or "")
    if not snapshot_id:
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_INVALID")
    final = resolve_snapshot_dir(output_root, str(value.get("snapshot_locator") or ""))
    root = final.parent
    expected_final = (root / final.name).resolve(strict=False)
    if (
        final != expected_final
        or not snapshot_name_matches_id(snapshot_id, final.name)
    ):
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_MISMATCH")
    copying = root / f".{final.name}.copying"
    marker = root / f".{final.name}.owner.json"
    status = str(value.get("status") or "")
    if status not in {"copying", "invalidated", "sealed"}:
        return "not_required" if status == "cleaned" else "unknown"

    if marker.exists():
        assert_marker(
            marker, snapshot_id, str(value["task_id"]), str(value["attempt_id"]),
            database.deployment_instance_id, str(value["snapshot_root_id"]),
            str(value["marker_token"]),
        )
    elif status == "sealed":
        # A sealed input must retain its owner marker until normal completion.
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID")

    for candidate in (copying, final):
        if not candidate.exists():
            continue
        if candidate.is_symlink() or candidate.resolve(strict=False).parent != root:
            raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID")
        assert_snapshot_tree_safe(candidate)
        make_tree_writable(candidate)
        shutil.rmtree(candidate)
    marker.unlink(missing_ok=True)
    ArchiveInputSnapshotRepository(database).mark_cleaned(snapshot_id)
    return "succeeded"


def cleanup_unfinished_snapshots(
    database: WorkbenchDatabase, output_root: str | Path,
) -> list[str]:
    """Best-effort cleanup, retaining durable diagnostics for unsafe rows."""
    repository = ArchiveInputSnapshotRepository(database)
    cleaned: list[str] = []
    for value in repository.list_unfinished():
        try:
            if cleanup_unfinished_snapshot(database, output_root, value) == "succeeded":
                cleaned.append(str(value["snapshot_id"]))
        except (OSError, ValueError, KeyError, WorkbenchPersistenceError):
            # The row remains copying/invalidated/sealed and is retried by the
            # next bounded recovery pass; never delete outside its owner root.
            continue
    return cleaned
