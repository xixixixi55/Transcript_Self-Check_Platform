"""Copy-and-seal checks for task-bound archive input snapshots.

Input sealing uses metadata (path + size + mtime) identities only; the
per-file content hashes formerly written into the snapshot manifest are no
longer computed, so archiving never re-reads multi-gigabyte source content.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from ..repository.archive_input_repository import ArchiveInputError, InputInventory, build_input_inventory, verify_input_inventory
from .archive_input_snapshot_files_service import assert_matches, assert_regular, safe_child

logger = logging.getLogger(__name__)


def source_evidence(inventory: InputInventory) -> tuple[InputInventory, list[dict[str, Any]]]:
    verify_input_inventory(inventory)
    current = build_input_inventory(
        inventory.source_root, output_root=inventory.output_root, check_readability=True,
    )
    if current.public_entries() != inventory.public_entries():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source inventory changed.")
    evidence: list[dict[str, Any]] = [
        {
            "relative_path": item.relative_path, "size_bytes": item.size_bytes,
            "modified_time_ns": item.modified_time_ns,
        }
        for item in current.files
    ]
    return current, evidence


def copy_inventory(
    inventory: InputInventory, temporary: Path, evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for directory in inventory.directories:
        safe_child(temporary, directory.relative_path).mkdir(parents=True, exist_ok=True)
    for item in inventory.files:
        destination = safe_child(temporary, item.relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            copy_file(item.absolute_path, destination)
        except ArchiveInputError:
            logger.error("archive input copy failed for relative=%s", item.relative_path)
            raise
        os.utime(destination, ns=(item.modified_time_ns, item.modified_time_ns))
    final_inventory = build_input_inventory(temporary, check_readability=True)
    assert_matches(final_inventory, evidence)
    return evidence


def copy_file(source: Path, destination: Path) -> None:
    assert_regular(source)
    if destination.exists() or destination.is_symlink():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Snapshot destination is not empty.")
    try:
        with source.open("rb") as reader, destination.open("xb") as writer:
            for block in iter(lambda: reader.read(1024 * 1024), b""):
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        assert_regular(source)
    except OSError as error:
        logger.error("archive input copy read/write error: %s", error)
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source file cannot be copied safely.") from error


def assert_source_matches(inventory: InputInventory, evidence: list[dict[str, Any]]) -> None:
    """Close the copy-to-seal window before WinRAR may see the snapshot."""
    current = build_input_inventory(
        inventory.source_root, output_root=inventory.output_root, check_readability=True,
    )
    if current.public_entries() != inventory.public_entries():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source changed before sealing.")
    expected = {
        str(item["relative_path"]): (int(item["size_bytes"]), int(item["modified_time_ns"]))
        for item in evidence
    }
    for item in current.files:
        meta = expected.get(item.relative_path)
        if meta is None or item.size_bytes != meta[0] or item.modified_time_ns != meta[1]:
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source changed before sealing.")
