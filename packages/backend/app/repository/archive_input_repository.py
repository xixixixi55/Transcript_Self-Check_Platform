"""Trusted case-input inventory used by archive planning and execution."""

from __future__ import annotations

import os
import hashlib
import stat
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .archive_input_inventory_worker import inspect_file, inventory_worker_count


MAX_SAFE_INTEGER = 2**53 - 1


class ArchiveInputError(ValueError):
    """Safe, stable input diagnostics without filesystem paths."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class InputFileSnapshot:
    relative_path: str
    absolute_path: Path
    size_bytes: int
    modified_time_ns: int

    def public_entry(self) -> dict[str, int | str]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "modified_time_ns": self.modified_time_ns,
        }


@dataclass(frozen=True)
class InputDirectorySnapshot:
    relative_path: str
    modified_time_ns: int

    def public_entry(self) -> dict[str, int | str]:
        return {
            "relative_path": self.relative_path,
            "modified_time_ns": self.modified_time_ns,
            "entry_type": "directory",
        }


@dataclass(frozen=True)
class InputInventory:
    source_root: Path
    files: tuple[InputFileSnapshot, ...]
    directories: tuple[InputDirectorySnapshot, ...] = ()
    output_root: Path | None = None
    metadata_fingerprint: str = ""

    @property
    def total_input_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files)

    def public_entries(self) -> list[dict[str, int | str]]:
        return [
            *[item.public_entry() for item in self.files],
            *[item.public_entry() for item in self.directories],
        ]


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = os.lstat(path).st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _is_unsafe_special_path(path: Path) -> bool:
    """Injectable boundary for symlink, junction and other reparse checks."""
    try:
        return path.is_symlink() or _is_reparse_point(path)
    except OSError:
        return True


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_relative_path(relative_path: str) -> None:
    normalized = relative_path.replace("\\", "/")
    path = Path(normalized)
    if not normalized or any(ord(char) < 32 for char in normalized) or path.is_absolute() or ".." in path.parts:
        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "归档输入包含非法相对路径。")


def _should_skip(path: Path, source_root: Path, output_root: Path | None) -> bool:
    return bool(output_root and _is_within(path, output_root))


def build_input_inventory(
    source_root: str | os.PathLike[str],
    *,
    output_root: str | os.PathLike[str] | None = None,
    check_readability: bool = True,
) -> InputInventory:
    """Walk the allowed case root without following links or junctions.

    Context creation can request a metadata-only snapshot so preview does not
    open every media file. Archive execution keeps the default readability
    check before WinRAR starts.
    """

    root = Path(source_root)
    if _is_unsafe_special_path(root):
        raise ArchiveInputError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "归档输入根目录不能是链接路径。")
    try:
        root = root.resolve(strict=True)
    except OSError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "归档输入根目录不可访问。") from error
    if not root.is_dir():
        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "归档输入根目录无效。")

    current = root
    while True:
        if _is_unsafe_special_path(current):
            raise ArchiveInputError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "归档输入不能包含链接或特殊路径。")
        parent = current.parent
        if parent == current:
            break
        current = parent

    output = None
    if output_root is not None:
        try:
            output = Path(output_root).resolve(strict=False)
        except OSError as error:
            raise ArchiveInputError("ARCHIVE_INPUT_OUTPUT_OVERLAP", "归档输出目录无效。") from error
        if _is_within(output, root):
            output.mkdir(parents=True, exist_ok=True)

    snapshots: list[InputFileSnapshot] = []
    directories: list[InputDirectorySnapshot] = []
    seen: set[str] = set()
    file_tasks: list[tuple[str, Path]] = []
    pending = [root]
    while pending:
        current = pending.pop()
        for entry in os.scandir(current):
            path = Path(entry.path)
            if _is_unsafe_special_path(path):
                raise ArchiveInputError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "归档输入不能包含符号链接或特殊路径。")
            if entry.is_dir(follow_symlinks=False):
                if not _should_skip(path, root, output):
                    relative = path.relative_to(root).as_posix()
                    _validate_relative_path(relative)
                    directories.append(InputDirectorySnapshot(relative, path.stat().st_mtime_ns))
                    pending.append(path)
                continue
            if not entry.is_file(follow_symlinks=False) or _should_skip(path, root, output):
                continue
            relative = path.relative_to(root).as_posix()
            _validate_relative_path(relative)
            key = relative.casefold()
            if key in seen:
                raise ArchiveInputError("ARCHIVE_PLAN_INVALID", "归档输入包含重复文件。")
            seen.add(key)
            file_tasks.append((relative, path))

    if file_tasks:
        with ThreadPoolExecutor(max_workers=inventory_worker_count()) as pool:
            snapshots = list(pool.map(inspect_file, file_tasks, [check_readability] * len(file_tasks)))
    snapshots.sort(key=lambda item: item.relative_path.casefold())
    directories.sort(key=lambda item: item.relative_path.casefold())
    return InputInventory(
        root, tuple(snapshots), tuple(directories), output,
        _inventory_metadata_fingerprint(snapshots, directories),
    )


def metadata_fingerprint_for_directory(
    source_root: str | os.PathLike[str],
    output_root: str | os.PathLike[str] | None = None,
) -> str:
    """Read only current paths and metadata for preview snapshot validation."""
    from .archive_input_metadata_repository import metadata_fingerprint_for_directory as read_metadata

    return read_metadata(source_root, output_root)


def _inventory_metadata_fingerprint(
    files: list[InputFileSnapshot], directories: list[InputDirectorySnapshot],
) -> str:
    digest = hashlib.sha256()
    for item in directories:
        digest.update(b"directory\0")
        digest.update(item.relative_path.casefold().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item.modified_time_ns).encode("ascii"))
        digest.update(b"\0")
    for item in files:
        digest.update(b"file\0")
        digest.update(item.relative_path.casefold().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item.size_bytes).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(item.modified_time_ns).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def verify_input_inventory(inventory: InputInventory) -> None:
    """Reject source metadata changes before or after WinRAR execution."""

    try:
        current_inventory = build_input_inventory(
            inventory.source_root, output_root=inventory.output_root,
            check_readability=False,
        )
    except ArchiveInputError as error:
        if error.code == "ARCHIVE_INPUT_CHANGED":
            raise
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "归档输入已发生变化。") from error

    # build_input_inventory already stats every file (size + mtime) without a
    # per-file open; comparing the ordered public entries covers additions,
    # removals, size and mtime changes in one pass.
    expected_entries = [item.public_entry() for item in inventory.files]
    current_entries = [item.public_entry() for item in current_inventory.files]
    expected_directories = [item.public_entry() for item in inventory.directories]
    current_directories = [item.public_entry() for item in current_inventory.directories]
    if expected_entries != current_entries or expected_directories != current_directories:
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "归档输入已发生变化。")
