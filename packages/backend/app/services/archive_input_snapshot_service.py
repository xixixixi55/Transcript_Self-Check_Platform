"""Task-bound sealed input snapshots for archive execution."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..repository.archive_input_repository import ArchiveInputError, InputInventory, build_input_inventory
from ..repository.archive_input_snapshot_repository import ArchiveInputSnapshotRepository
from ..repository.workbench_database import WorkbenchDatabase
from .archive_input_snapshot_copy_service import (
    assert_source_matches as _assert_source_matches, copy_inventory, source_evidence,
)
from .archive_input_snapshot_files_service import (
    assert_marker, assert_matches, assert_snapshot_tree_safe, fingerprint,
    fsync_dir, make_tree_read_only, make_tree_writable, marker_path,
    marker_payload, remove_paths, required, resolve_snapshot_dir,
    root_id as root_identifier,
    write_marker,
)

_MARKER_NAME = ".archive-input-owner.json"


@dataclass(frozen=True)
class SealedInputSnapshot:
    snapshot_id: str
    task_id: str
    attempt_id: str
    deployment_instance_id: str
    source_root_id: str
    snapshot_root_id: str
    snapshot_dir: Path
    inventory: InputInventory
    input_fingerprint: str
    manifest: tuple[dict[str, Any], ...]
    marker_token: str


def create_sealed_input_snapshot(
    database: WorkbenchDatabase, output_root: str | Path,
    attempt: dict[str, Any], source_inventory: InputInventory,
) -> SealedInputSnapshot:
    task_id = required(attempt, "task_id")
    attempt_id = required(attempt, "attempt_id")
    token = secrets.token_hex(24)
    snapshot_id = f"snapshot-{token}"
    root_id = f"snapshot-root-{token}"
    marker_token = f"snapshot-marker-{secrets.token_hex(20)}"
    root = Path(output_root) / "compressed" / ".inputs"
    temporary = root / f".{snapshot_id}.copying"
    final = root / snapshot_id
    marker = root / f".{snapshot_id}.owner.json"
    current, evidence = source_evidence(source_inventory)
    source_root_id = root_identifier(current.source_root)
    repository = ArchiveInputSnapshotRepository(database)
    repository.create_copying({
        "snapshot_id": snapshot_id, "task_id": task_id, "attempt_id": attempt_id,
        "case_id": required(attempt, "case_id"), "source_id": required(attempt, "source_id"),
        "source_revision": int(attempt["source_revision"]),
        "draft_revision": int(attempt.get("draft_revision") or 0),
        "source_root_id": source_root_id, "snapshot_root_id": root_id,
        "snapshot_locator": f".inputs/{snapshot_id}", "marker_token": marker_token,
    })
    try:
        root.mkdir(parents=True, exist_ok=True)
        if temporary.exists() or final.exists() or marker.exists():
            raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_CONFLICT", "Snapshot name conflict.")
        temporary.mkdir()
        manifest = copy_inventory(current, temporary, evidence)
        _assert_source_matches(current, evidence)
        write_marker(marker, marker_payload(
            snapshot_id, task_id, attempt_id, database.deployment_instance_id,
            root_id, marker_token,
        ))
        os.replace(temporary, final)
        fsync_dir(root)
        inventory = build_input_inventory(final, check_readability=True)
        assert_matches(inventory, manifest)
        input_fingerprint = fingerprint(source_root_id, inventory, manifest)
        make_tree_read_only(final)
        repository.seal(snapshot_id, manifest=manifest, input_fingerprint=input_fingerprint)
        return SealedInputSnapshot(
            snapshot_id, task_id, attempt_id, database.deployment_instance_id,
            source_root_id, root_id, final, inventory, input_fingerprint,
            tuple(manifest), marker_token,
        )
    except Exception:
        remove_paths(temporary, final, marker)
        try:
            repository.mark_invalidated(snapshot_id)
        except Exception:
            pass
        raise


def create_ephemeral_sealed_input_snapshot(
    output_root: str | Path, source_inventory: InputInventory,
) -> SealedInputSnapshot:
    current, evidence = source_evidence(source_inventory)
    token = secrets.token_hex(24)
    snapshot_id = f"snapshot-ephemeral-{token}"
    task_id = f"ephemeral-task-{token}"
    attempt_id = f"ephemeral-attempt-{token}"
    root_id = f"snapshot-root-{token}"
    marker_token = f"snapshot-marker-{secrets.token_hex(20)}"
    root = Path(output_root) / "compressed" / ".inputs"
    temporary = root / f".{snapshot_id}.copying"
    final = root / snapshot_id
    marker = root / f".{snapshot_id}.owner.json"
    try:
        root.mkdir(parents=True, exist_ok=True)
        temporary.mkdir()
        manifest = copy_inventory(current, temporary, evidence)
        _assert_source_matches(current, evidence)
        write_marker(marker, marker_payload(
            snapshot_id, task_id, attempt_id, "ephemeral", root_id, marker_token,
        ))
        os.replace(temporary, final)
        fsync_dir(root)
        inventory = build_input_inventory(final, check_readability=True)
        assert_matches(inventory, manifest)
        source_root_id = root_identifier(current.source_root)
        make_tree_read_only(final)
        return SealedInputSnapshot(
            snapshot_id, task_id, attempt_id, "ephemeral", source_root_id, root_id,
            final, inventory, fingerprint(source_root_id, inventory, manifest),
            tuple(manifest), marker_token,
        )
    except Exception:
        remove_paths(temporary, final, marker)
        raise


def load_sealed_input_snapshot(
    database: WorkbenchDatabase, output_root: str | Path, attempt_id: str,
) -> SealedInputSnapshot:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM archive_input_snapshots WHERE attempt_id=? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
    if row is None or row["status"] != "sealed":
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_NOT_SEALED", "Input snapshot is not sealed.")
    value = dict(row)
    snapshot_dir = resolve_snapshot_dir(output_root, value["snapshot_locator"])
    inventory = build_input_inventory(snapshot_dir, check_readability=True)
    manifest = tuple(json.loads(value["manifest_json"]))
    assert_matches(inventory, list(manifest))
    assert_marker(
        marker_path(snapshot_dir), value["snapshot_id"], value["task_id"],
        value["attempt_id"], value["deployment_instance_id"],
        value["snapshot_root_id"], value["marker_token"],
    )
    if fingerprint(value["source_root_id"], inventory, list(manifest)) != value["input_fingerprint"]:
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_CHANGED", "Input snapshot changed.")
    return SealedInputSnapshot(
        value["snapshot_id"], value["task_id"], value["attempt_id"],
        value["deployment_instance_id"], value["source_root_id"], value["snapshot_root_id"],
        snapshot_dir, inventory, value["input_fingerprint"], manifest, value["marker_token"],
    )


def assert_sealed_input(snapshot: SealedInputSnapshot) -> None:
    if not snapshot.snapshot_dir.is_dir():
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_CHANGED", "Input snapshot is missing.")
    inventory = build_input_inventory(snapshot.snapshot_dir, check_readability=True)
    assert_matches(inventory, list(snapshot.manifest))
    if fingerprint(snapshot.source_root_id, inventory, list(snapshot.manifest)) != snapshot.input_fingerprint:
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_CHANGED", "Input snapshot changed.")


def cleanup_sealed_input_snapshot(
    database: WorkbenchDatabase, output_root: str | Path, attempt_id: str,
) -> str:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM archive_input_snapshots WHERE attempt_id=? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
    if row is None:
        return "not_required"
    value = dict(row)
    snapshot_dir = resolve_snapshot_dir(output_root, value["snapshot_locator"])
    assert_snapshot_tree_safe(snapshot_dir)
    assert_marker(
        marker_path(snapshot_dir), value["snapshot_id"], value["task_id"],
        value["attempt_id"], value["deployment_instance_id"],
        value["snapshot_root_id"], value["marker_token"],
    )
    for path in sorted(snapshot_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o700 if path.is_dir() else 0o600)
    shutil.rmtree(snapshot_dir)
    marker_path(snapshot_dir).unlink(missing_ok=True)
    ArchiveInputSnapshotRepository(database).mark_cleaned(value["snapshot_id"])
    return "succeeded"


def cleanup_ephemeral_input_snapshot(snapshot: SealedInputSnapshot) -> None:
    """Remove an unpersisted snapshot after making its owned tree writable."""
    assert_snapshot_tree_safe(snapshot.snapshot_dir)
    make_tree_writable(snapshot.snapshot_dir)
    shutil.rmtree(snapshot.snapshot_dir, ignore_errors=True)
    marker_path(snapshot.snapshot_dir).unlink(missing_ok=True)
