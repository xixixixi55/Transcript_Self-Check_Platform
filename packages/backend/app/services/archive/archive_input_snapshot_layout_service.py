"""选择私有快照存储路径，不更改来源相对路径。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

from ...repository.archive.archive_input_repository import ArchiveInputError


_WINDOWS_FILE_PATH_LIMIT = 260
_WINDOWS_DIRECTORY_PATH_LIMIT = 248
SHORT_SNAPSHOT_ROOT = ".i"
EXTERNAL_SNAPSHOT_ROOT = ".t"


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
    """选择可安全容纳来源树的受控根目录。"""
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
    """外部快照根目录，默认为项目所在驱动器；可由环境变量覆盖。

    旧默认值（临时目录的父目录）位于经常空间不足的系统盘。默认改为
    <project>/external-snapshots，使深层报告写入有空间的输出盘。部署仍可通过
    BIJI_ARCHIVE_EXTERNAL_ROOT 覆盖。
    """
    override = os.environ.get("BIJI_ARCHIVE_EXTERNAL_ROOT")
    if override:
        return Path(override)
    from ...config import OUTPUT_BASE

    return Path(OUTPUT_BASE).parent.parent / "external-snapshots"


__all__ = [
    "EXTERNAL_SNAPSHOT_ROOT", "SHORT_SNAPSHOT_ROOT", "SnapshotLayout",
    "choose_snapshot_layout", "private_snapshot_root",
]
