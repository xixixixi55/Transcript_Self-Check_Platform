"""第 20 层：持久化每个案件最近成功的统一导出目录。"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .workbench_database import normalize_utc
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id

_SCHEMA_VERSION = 1
_WRITE_LOCK = threading.RLock()


class LocalCaseExportDirectoryRepository:
    """仅在专用本地路径注册表中存储绝对导出路径。"""

    def __init__(self, file_path: str | os.PathLike[str]) -> None:
        self.file_path = Path(file_path)

    def remember(
        self,
        case_id: str,
        export_path: str | os.PathLike[str],
        exported_at: str,
    ) -> dict[str, str]:
        validated_case_id = validate_opaque_id(case_id)
        candidate = Path(export_path)
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            raise WorkbenchPersistenceError("EXPORT_DIRECTORY_RECORD_FAILED") from None
        if not candidate.is_absolute() or not resolved.is_dir():
            raise WorkbenchPersistenceError("EXPORT_DIRECTORY_RECORD_FAILED")
        record = {
            "case_id": validated_case_id,
            "export_path": str(resolved),
            "exported_at": normalize_utc(exported_at),
        }
        temp_path: Path | None = None
        with _WRITE_LOCK:
            try:
                records = self._read_records()
                records[validated_case_id] = record
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=self.file_path.parent,
                    delete=False,
                    prefix=".case-export-directories-",
                    suffix=".tmp",
                ) as handle:
                    temp_path = Path(handle.name)
                    json.dump(
                        {"schema_version": _SCHEMA_VERSION, "records": records},
                        handle,
                        ensure_ascii=False,
                    )
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.file_path)
                temp_path = None
            except (OSError, UnicodeError, ValueError) as error:
                raise WorkbenchPersistenceError("EXPORT_DIRECTORY_RECORD_FAILED") from error
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass
        return record

    def latest(self, case_id: str) -> dict[str, str] | None:
        validated_case_id = validate_opaque_id(case_id)
        with _WRITE_LOCK:
            record = self._read_records().get(validated_case_id)
        if not isinstance(record, dict):
            return None
        export_path = record.get("export_path")
        exported_at = record.get("exported_at")
        if (
            not isinstance(export_path, str)
            or not Path(export_path).is_absolute()
            or not isinstance(exported_at, str)
        ):
            return None
        return {
            "case_id": validated_case_id,
            "export_path": export_path,
            "exported_at": exported_at,
        }

    def _read_records(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA_VERSION:
            return {}
        records = payload.get("records")
        return dict(records) if isinstance(records, dict) else {}
