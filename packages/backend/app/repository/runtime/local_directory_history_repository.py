"""第 20 层：原生目录选择器历史的本地持久化。"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Literal

from ..inspection.inspector_repository import resolve_app_data_dir

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_WRITE_LOCK = threading.RLock()
DirectoryHistoryKind = Literal["report", "export", "archive"]


class LocalDirectoryHistoryRepository:
    """持久化独立的报告和导出选择器历史，不记录路径。"""

    def __init__(self, file_path: str | os.PathLike[str] | None = None) -> None:
        self.file_path = (
            Path(file_path)
            if file_path is not None
            else resolve_app_data_dir() / "directory-picker-history.json"
        )
    def last_directory(self, kind: DirectoryHistoryKind) -> str | None:
        with _WRITE_LOCK:
            candidate_value = self._read_directories().get(kind)
            if not isinstance(candidate_value, str):
                return None
            candidate = Path(candidate_value)
            if not candidate.is_absolute() or not candidate.is_dir():
                return None
            return str(candidate)

    def remember_directory(
        self,
        kind: DirectoryHistoryKind,
        selected_path: str | os.PathLike[str],
    ) -> None:
        candidate = Path(selected_path)
        if not candidate.is_absolute() or not candidate.is_dir():
            return
        temp_path: Path | None = None
        with _WRITE_LOCK:
            try:
                directories = self._read_directories()
                directories[kind] = str(candidate)
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=self.file_path.parent,
                    delete=False,
                    prefix=".directory-picker-history-",
                    suffix=".tmp",
                ) as handle:
                    temp_path = Path(handle.name)
                    json.dump(
                        {
                            "schema_version": _SCHEMA_VERSION,
                            "directories": directories,
                        },
                        handle,
                        ensure_ascii=False,
                    )
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.file_path)
                temp_path = None
            except (OSError, UnicodeError, ValueError):
                logger.warning("directory picker: unable to persist local directory history")
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass

    def _read_directories(self) -> dict[str, str]:
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            return {}
        raw = payload.get("directories")
        directories = (
            {key: value for key, value in raw.items() if key in {"report", "export", "archive"} and isinstance(value, str)}
            if isinstance(raw, dict)
            else {}
        )
        legacy_export = payload.get("export_directory")
        if "export" not in directories and isinstance(legacy_export, str):
            directories["export"] = legacy_export
        return directories
