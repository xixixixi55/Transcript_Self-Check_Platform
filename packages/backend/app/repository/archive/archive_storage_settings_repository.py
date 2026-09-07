"""仅只读解析旧版归档存储位置，用于查找历史产物；新归档不使用该配置。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..runtime.runtime_paths import get_runtime_paths

_SCHEMA_VERSION = 1
_WORKSPACE_NAME = "文枢归档工作区"


@dataclass(frozen=True)
class ArchiveStorageSelection:
    configured_parent: Path | None
    desired_output_root: Path
    valid: bool
    error_code: str | None = None

    @property
    def custom(self) -> bool:
        return self.configured_parent is not None


class ArchiveStorageSettingsRepository:
    def __init__(self, file_path: str | os.PathLike[str] | None = None) -> None:
        self.file_path = Path(file_path) if file_path else (
            get_runtime_paths().data_root / "archive-storage-settings.json"
        )

    def resolve(self, default_output_root: Path, resource_root: Path) -> ArchiveStorageSelection:
        configured = self._read_parent()
        if configured is None:
            return ArchiveStorageSelection(None, default_output_root.resolve(strict=False), True)
        desired = (configured / _WORKSPACE_NAME).resolve(strict=False)
        if not configured.is_absolute() or not configured.is_dir():
            return ArchiveStorageSelection(configured, desired, False, "ARCHIVE_STORAGE_DIRECTORY_UNAVAILABLE")
        if _paths_overlap(desired, resource_root.resolve(strict=False)):
            return ArchiveStorageSelection(configured, desired, False, "ARCHIVE_STORAGE_DIRECTORY_UNSAFE")
        if not desired.is_dir():
            return ArchiveStorageSelection(configured, desired, False, "ARCHIVE_STORAGE_DIRECTORY_UNAVAILABLE")
        return ArchiveStorageSelection(configured, desired, True)

    def _read_parent(self) -> Path | None:
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            return None
        value = payload.get("selected_parent")
        return Path(value) if isinstance(value, str) and value else None

def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        try:
            right.relative_to(left)
            return True
        except ValueError:
            return False


__all__ = ["ArchiveStorageSelection", "ArchiveStorageSettingsRepository"]
