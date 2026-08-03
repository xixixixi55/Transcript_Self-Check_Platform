"""Select private snapshot storage paths without changing source-relative paths."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Iterable

from ..repository.archive_input_repository import ArchiveInputError


_WINDOWS_FILE_PATH_LIMIT = 260
_WINDOWS_DIRECTORY_PATH_LIMIT = 248
SHORT_SNAPSHOT_ROOT = ".i"
EXTERNAL_SNAPSHOT_ROOT = ".t"
_PRIVATE_SNAPSHOT_ROOT_NAME = ".bi"


@dataclass(frozen=True)
class SnapshotLayout:
    root: Path
    snapshot_name: str
    locator: str


def choose_snapshot_layout(
    output_root: str | Path,
    snapshot_id: str,
    file_paths: Iterable[str],
    directory_paths: Iterable[str] = (),
) -> SnapshotLayout:
    """Choose a controlled root that can hold the source tree safely."""
    output = Path(output_root)
    files = tuple(file_paths)
    directories = tuple(directory_paths)
    standard = SnapshotLayout(
        output / "compressed" / ".inputs", snapshot_id, f".inputs/{snapshot_id}",
    )
    if _layout_fits(standard, files, directories):
        return standard

    token = snapshot_id.removeprefix("snapshot-")
    for token_length in range(16, 3, -1):
        snapshot_name = f"s{token[:token_length]}"
        short = SnapshotLayout(
            output / SHORT_SNAPSHOT_ROOT, snapshot_name,
            f"{SHORT_SNAPSHOT_ROOT}/{snapshot_name}",
        )
        if _layout_fits(short, files, directories):
            return short
        external = SnapshotLayout(
            private_snapshot_root(), snapshot_name,
            f"{EXTERNAL_SNAPSHOT_ROOT}/{snapshot_name}",
        )
        if _layout_fits(external, files, directories):
            return external
    raise ArchiveInputError(
        "ARCHIVE_INPUT_PATH_TOO_LONG",
        "Archive input path is too long for a safe snapshot.",
    )


def _layout_fits(
    layout: SnapshotLayout, file_paths: tuple[str, ...], directory_paths: tuple[str, ...],
) -> bool:
    temporary = layout.root / f".{layout.snapshot_name}.copying"
    file_lengths = [_path_length(temporary, path) for path in file_paths]
    directory_lengths = [_path_length(temporary, path) for path in directory_paths]
    if not directory_lengths:
        directory_lengths = [len(str(temporary))]
    return (
        max(file_lengths, default=len(str(temporary))) < _WINDOWS_FILE_PATH_LIMIT
        and max(directory_lengths) < _WINDOWS_DIRECTORY_PATH_LIMIT
    )


def _path_length(root: Path, relative_path: str) -> int:
    return len(str(root / Path(str(relative_path).replace("\\", "/"))))


def private_snapshot_root() -> Path:
    temporary_root = Path(tempfile.gettempdir())
    if os.name == "nt":
        return temporary_root.parent / _PRIVATE_SNAPSHOT_ROOT_NAME
    return temporary_root / _PRIVATE_SNAPSHOT_ROOT_NAME


__all__ = [
    "EXTERNAL_SNAPSHOT_ROOT", "SHORT_SNAPSHOT_ROOT", "SnapshotLayout",
    "choose_snapshot_layout", "private_snapshot_root",
]
