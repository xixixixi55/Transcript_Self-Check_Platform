"""Copy-and-seal checks for task-bound archive input snapshots."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ..repository.archive_input_repository import ArchiveInputError, InputInventory, build_input_inventory, verify_input_inventory
from .archive_input_snapshot_files_service import assert_matches, assert_regular, hash_file, safe_child


def source_evidence(inventory: InputInventory) -> tuple[InputInventory, list[dict[str, Any]]]:
    verify_input_inventory(inventory)
    current = build_input_inventory(
        inventory.source_root, output_root=inventory.output_root, check_readability=True,
    )
    if current.public_entries() != inventory.public_entries():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source inventory changed.")
    evidence: list[dict[str, Any]] = []
    for item in current.files:
        before = hash_file(item.absolute_path)
        after = hash_file(item.absolute_path)
        if before != after:
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source content changed.")
        evidence.append({
            "relative_path": item.relative_path, "size_bytes": item.size_bytes,
            "sha256": before,
        })
    return current, evidence


def copy_inventory(
    inventory: InputInventory, temporary: Path, evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected = {str(item["relative_path"]): item for item in evidence}
    for directory in inventory.directories:
        safe_child(temporary, directory.relative_path).mkdir(parents=True, exist_ok=True)
    for item in inventory.files:
        destination = safe_child(temporary, item.relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = copy_file(item.absolute_path, destination)
        if digest != expected[item.relative_path]["sha256"] or hash_file(item.absolute_path) != digest:
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source content changed during snapshot.")
        os.utime(destination, ns=(item.modified_time_ns, item.modified_time_ns))
    final_inventory = build_input_inventory(temporary, check_readability=True)
    assert_matches(final_inventory, evidence)
    return evidence


def copy_file(source: Path, destination: Path) -> str:
    assert_regular(source)
    if destination.exists() or destination.is_symlink():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Snapshot destination is not empty.")
    digest = hashlib.sha256()
    try:
        with source.open("rb") as reader, destination.open("xb") as writer:
            for block in iter(lambda: reader.read(1024 * 1024), b""):
                digest.update(block)
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        assert_regular(source)
    except OSError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source file cannot be copied safely.") from error
    return digest.hexdigest()


def assert_source_matches(inventory: InputInventory, evidence: list[dict[str, Any]]) -> None:
    """Close the copy-to-seal window before WinRAR may see the snapshot."""
    current = build_input_inventory(
        inventory.source_root, output_root=inventory.output_root, check_readability=True,
    )
    if current.public_entries() != inventory.public_entries():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source changed before sealing.")
    expected = {str(item["relative_path"]): str(item["sha256"]) for item in evidence}
    for item in current.files:
        if hash_file(item.absolute_path) != expected.get(item.relative_path):
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source changed before sealing.")
