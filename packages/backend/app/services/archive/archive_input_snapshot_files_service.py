"""任务绑定密封归档输入的文件系统原语。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
from pathlib import Path
from typing import Any

from ...repository.archive.archive_input_repository import ArchiveInputError, InputInventory
from .archive_input_snapshot_layout_service import (
    EXTERNAL_SNAPSHOT_ROOT as _EXTERNAL_SNAPSHOT_ROOT,
    SHORT_SNAPSHOT_ROOT as _SHORT_SNAPSHOT_ROOT,
)
from .archive_input_snapshot_layout_service import private_snapshot_root


def assert_matches(inventory: InputInventory, manifest: list[dict[str, Any]]) -> None:
    actual = {item.relative_path: item.size_bytes for item in inventory.files}
    expected = {str(item["relative_path"]): int(item["size_bytes"]) for item in manifest}
    if actual != expected or len(actual) != len(manifest):
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Snapshot file set changed.")
    for item in manifest:
        if "modified_time_ns" not in item:
            continue
        path = safe_child(inventory.source_root, str(item["relative_path"]))
        try:
            modified = path.stat().st_mtime_ns
        except OSError as error:
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Snapshot content changed.") from error
        if int(modified) != int(item["modified_time_ns"]):
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Snapshot content changed.")


def fingerprint(source_root_id: str, inventory: InputInventory, manifest: list[dict[str, Any]]) -> str:
    payload = {
        "source_root_id": source_root_id,
        "directories": sorted(item.relative_path.casefold() for item in inventory.directories),
        "files": sorted(manifest, key=lambda item: str(item["relative_path"]).casefold()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assert_regular(path: Path) -> None:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        if getattr(os.lstat(path), "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0,
        ):
            raise OSError
    except OSError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Unsafe source file type.") from error


def safe_child(root: Path, relative: str) -> Path:
    candidate = (root / Path(relative.replace("\\", "/"))).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve(strict=False))
    except ValueError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "Snapshot path is invalid.") from error
    return candidate


def resolve_snapshot_dir(output_root: str | Path, locator: str) -> Path:
    if not isinstance(locator, str):
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_INVALID", "Snapshot locator is invalid.")
    normalized = locator.replace("\\", "/")
    if normalized.startswith(".inputs/"):
        base = (Path(output_root) / "compressed" / ".inputs").resolve(strict=False)
        relative = normalized.removeprefix(".inputs/")
    elif normalized.startswith(f"{_SHORT_SNAPSHOT_ROOT}/"):
        base = (Path(output_root) / _SHORT_SNAPSHOT_ROOT).resolve(strict=False)
        relative = normalized.removeprefix(f"{_SHORT_SNAPSHOT_ROOT}/")
    elif normalized.startswith(f"{_EXTERNAL_SNAPSHOT_ROOT}/"):
        base = private_snapshot_root().resolve(strict=False)
        relative = normalized.removeprefix(f"{_EXTERNAL_SNAPSHOT_ROOT}/")
    else:
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_INVALID", "Snapshot locator is invalid.")
    parts = relative.split("/")
    if not relative or len(parts) != 1 or any(part in {"", ".", ".."} for part in parts):
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_INVALID", "Snapshot locator is invalid.")
    candidate = (base / Path(relative)).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_INVALID", "Snapshot locator is invalid.") from error
    return candidate


def snapshot_name_matches_id(snapshot_id: str, snapshot_name: str) -> bool:
    """将旧版名称和短回退别名都绑定到完整 ID。"""
    if snapshot_name == snapshot_id:
        return True
    token = snapshot_id.removeprefix("snapshot-")
    return snapshot_name.startswith("s") and len(snapshot_name) > 1 and token.startswith(snapshot_name[1:])


def marker_path(snapshot_dir: Path) -> Path:
    return snapshot_dir.parent / f".{snapshot_dir.name}.owner.json"


def marker_payload(
    snapshot_id: str, task_id: str, attempt_id: str, deployment: str,
    root_id: str, token: str,
) -> dict[str, str | int]:
    return {
        "marker_version": 1, "snapshot_id": snapshot_id, "task_id": task_id,
        "attempt_id": attempt_id, "deployment_instance_id": deployment,
        "snapshot_root_id": root_id, "marker_token": token,
    }


def write_marker(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def assert_marker(path: Path, *expected: str) -> None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ArchiveInputError(
            "ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID", "Snapshot owner marker invalid.",
        ) from error
    actual = tuple(str(value.get(key)) for key in (
        "snapshot_id", "task_id", "attempt_id", "deployment_instance_id",
        "snapshot_root_id", "marker_token",
    ))
    if actual != expected:
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID", "Snapshot owner mismatch.")


def remove_paths(temporary: Path, final: Path, marker: Path) -> None:
    marker.unlink(missing_ok=True)
    make_tree_writable(final)
    make_tree_writable(temporary)
    shutil.rmtree(final, ignore_errors=True)
    shutil.rmtree(temporary, ignore_errors=True)


def assert_snapshot_tree_safe(root: Path) -> None:
    if not root.is_dir() or root.is_symlink():
        raise ArchiveInputError("ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID", "Snapshot owner mismatch.")
    for path in root.rglob("*"):
        try:
            if path.is_symlink() or getattr(os.lstat(path), "st_file_attributes", 0) & getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0,
            ):
                raise OSError
        except OSError as error:
            raise ArchiveInputError(
                "ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID", "Snapshot owner mismatch.",
            ) from error


def make_tree_read_only(root: Path) -> None:
    assert_snapshot_tree_safe(root)
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(
            stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
            if path.is_file() else
            stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
            | stat.S_IROTH | stat.S_IXOTH,
        )
    root.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def make_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        try:
            path.chmod(
                stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
                if path.is_dir() else stat.S_IRUSR | stat.S_IWUSR,
            )
        except OSError:
            pass
    try:
        root.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except OSError:
        pass


def fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def root_id(path: Path) -> str:
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source root cannot be resolved.") from error
    return hashlib.sha256(str(resolved).casefold().encode()).hexdigest()


def required(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ArchiveInputError(
            "ARCHIVE_INPUT_SNAPSHOT_BINDING_MISMATCH", "Snapshot binding is incomplete.",
        )
    return result
