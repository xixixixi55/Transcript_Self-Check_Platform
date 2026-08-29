"""持久化并验证部署本地归档存储选择。"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from ..runtime.runtime_paths import get_runtime_paths

_SCHEMA_VERSION = 1
_WORKSPACE_NAME = "文枢归档工作区"
_PROBE_CREATE_ATTEMPTS = 3
_LOCK = threading.RLock()


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
        if not _probe_writable(desired):
            return ArchiveStorageSelection(configured, desired, False, "ARCHIVE_STORAGE_DIRECTORY_UNAVAILABLE")
        return ArchiveStorageSelection(configured, desired, True)

    def save_parent(self, selected_parent: str | os.PathLike[str], resource_root: Path) -> None:
        parent = Path(selected_parent).resolve(strict=True)
        desired = (parent / _WORKSPACE_NAME).resolve(strict=False)
        if _paths_overlap(desired, resource_root.resolve(strict=False)):
            raise ValueError("ARCHIVE_STORAGE_DIRECTORY_UNSAFE")
        if not _probe_writable(desired):
            raise OSError("ARCHIVE_STORAGE_DIRECTORY_UNAVAILABLE")
        self._write({"schema_version": _SCHEMA_VERSION, "selected_parent": str(parent)})

    def reset(self) -> None:
        with _LOCK:
            try:
                self.file_path.unlink(missing_ok=True)
            except OSError as error:
                raise OSError("ARCHIVE_STORAGE_SETTINGS_WRITE_FAILED") from error

    def _read_parent(self) -> Path | None:
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            return None
        value = payload.get("selected_parent")
        return Path(value) if isinstance(value, str) and value else None

    def _write(self, payload: dict[str, object]) -> None:
        temporary: Path | None = None
        with _LOCK:
            try:
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=self.file_path.parent,
                    prefix=".archive-storage-", suffix=".tmp", delete=False,
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump(payload, handle, ensure_ascii=False)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.file_path)
                temporary = None
            except (OSError, UnicodeError, ValueError) as error:
                raise OSError("ARCHIVE_STORAGE_SETTINGS_WRITE_FAILED") from error
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def _probe_writable(root: Path) -> bool:
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    for _attempt in range(_PROBE_CREATE_ATTEMPTS):
        probe = root / f".wenshu-write-probe-{secrets.token_hex(16)}.tmp"
        try:
            handle = probe.open("xb")
        except FileExistsError:
            continue
        except OSError:
            return False

        try:
            with handle:
                handle.write(b"ok")
                handle.flush()
                os.fsync(handle.fileno())
            return True
        except OSError:
            return False
        finally:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
    return False


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
