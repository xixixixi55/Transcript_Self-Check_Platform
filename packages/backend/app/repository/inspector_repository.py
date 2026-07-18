"""Versioned, atomic JSON storage for the local inspector library."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
MAX_NAME_LENGTH = 100
MAX_UNIT_LENGTH = 200
MAX_POLICE_NUMBER_LENGTH = 64
_WRITE_LOCK = threading.RLock()


class InspectorValidationError(ValueError):
    """A user-supplied inspector field failed validation."""


class InspectorDataError(RuntimeError):
    """The library file is missing, corrupt, or cannot be safely written."""


class InspectorNotFoundError(LookupError):
    """The requested inspector ID does not exist."""


@dataclass(frozen=True)
class InspectorRecord:
    id: str
    name: str
    unit: str
    police_number: str
    enabled: bool
    created_at: str
    updated_at: str


def resolve_app_data_dir(env: Mapping[str, str] | None = None) -> Path:
    """Resolve the application data directory without logging user paths."""

    values = env if env is not None else os.environ
    override = str(values.get("BIJI_APP_DATA_DIR", "")).strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        local_app_data = str(values.get("LOCALAPPDATA", "")).strip()
        if local_app_data:
            return Path(local_app_data) / "文枢" / "data"
        return Path(tempfile.gettempdir()) / "biji-zijian-platform" / "data"
    xdg_data_home = str(values.get("XDG_DATA_HOME", "")).strip()
    if xdg_data_home:
        return Path(xdg_data_home) / "文枢"
    return Path.home() / ".local" / "share" / "文枢"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_text(field: str, value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        raise InspectorValidationError(f"{field}必须是文本")
    normalized = value.strip()
    if not normalized:
        raise InspectorValidationError(f"{field}不能为空")
    if len(normalized) > maximum:
        raise InspectorValidationError(f"{field}长度超过限制")
    if any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F for char in normalized):
        raise InspectorValidationError(f"{field}包含非法控制字符")
    return normalized


def _validate_fields(name: Any, unit: Any, police_number: Any) -> tuple[str, str, str]:
    return (
        _validate_text("姓名", name, MAX_NAME_LENGTH),
        _validate_text("单位", unit, MAX_UNIT_LENGTH),
        _validate_text("警号", police_number, MAX_POLICE_NUMBER_LENGTH),
    )


class InspectorRepository:
    """Repository interface that can later be replaced without changing services."""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else resolve_app_data_dir()
        self.file_path = self.data_dir / "inspectors.json"
        self.backup_path = self.data_dir / "inspectors.json.bak"

    def list(self, *, enabled_only: bool = False) -> list[InspectorRecord]:
        with _WRITE_LOCK:
            records = self._read_records(create_if_missing=True)
            return [record for record in records if record.enabled or not enabled_only]

    def get(self, inspector_id: str) -> InspectorRecord | None:
        with _WRITE_LOCK:
            return next((record for record in self._read_records(True) if record.id == inspector_id), None)

    def create(self, name: Any, unit: Any, police_number: Any) -> InspectorRecord:
        fields = _validate_fields(name, unit, police_number)
        with _WRITE_LOCK:
            records = self._read_records(True)
            self._reject_duplicate(records, fields)
            now = _now()
            record = InspectorRecord(str(uuid.uuid4()), *fields, True, now, now)
            self._write_records([*records, record])
            return record

    def update(self, inspector_id: str, *, name: Any = None, unit: Any = None, police_number: Any = None) -> InspectorRecord:
        with _WRITE_LOCK:
            records = self._read_records(True)
            current = self._find_or_raise(records, inspector_id)
            fields = _validate_fields(
                current.name if name is None else name,
                current.unit if unit is None else unit,
                current.police_number if police_number is None else police_number,
            )
            self._reject_duplicate(records, fields, exclude_id=inspector_id)
            updated = InspectorRecord(current.id, *fields, current.enabled, current.created_at, _now())
            self._write_records([updated if item.id == inspector_id else item for item in records])
            return updated

    def set_enabled(self, inspector_id: str, enabled: Any) -> InspectorRecord:
        if not isinstance(enabled, bool):
            raise InspectorValidationError("enabled必须是布尔值")
        with _WRITE_LOCK:
            records = self._read_records(True)
            current = self._find_or_raise(records, inspector_id)
            updated = InspectorRecord(current.id, current.name, current.unit, current.police_number, enabled, current.created_at, _now())
            self._write_records([updated if item.id == inspector_id else item for item in records])
            return updated

    def delete(self, inspector_id: str) -> None:
        with _WRITE_LOCK:
            records = self._read_records(True)
            self._find_or_raise(records, inspector_id)
            self._write_records([item for item in records if item.id != inspector_id])

    def recover_from_backup(self) -> list[InspectorRecord]:
        with _WRITE_LOCK:
            records = self._load_records_from(self.backup_path)
            self._write_records(records, keep_backup=False)
            return records

    def _read_records(self, create_if_missing: bool) -> list[InspectorRecord]:
        if not self.file_path.exists():
            if create_if_missing:
                self._write_records([])
                return []
            return []
        return self._load_records_from(self.file_path)

    def _load_records_from(self, path: Path) -> list[InspectorRecord]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InspectorDataError("检查人员数据文件损坏或不可读取") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
            raise InspectorDataError("检查人员数据版本不受支持")
        raw_records = payload.get("inspectors")
        if not isinstance(raw_records, list):
            raise InspectorDataError("检查人员数据结构无效")
        records = [self._record_from_json(item) for item in raw_records]
        if len({record.id for record in records}) != len(records):
            raise InspectorDataError("检查人员数据包含重复ID")
        return records

    def _record_from_json(self, item: Any) -> InspectorRecord:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item.get("id", "").strip()
            or not isinstance(item.get("enabled"), bool)
        ):
            raise InspectorDataError("检查人员数据结构无效")
        try:
            name, unit, police_number = _validate_fields(item.get("name"), item.get("unit"), item.get("police_number"))
        except InspectorValidationError as exc:
            raise InspectorDataError("检查人员数据校验失败") from exc
        created_at = item.get("created_at")
        updated_at = item.get("updated_at")
        if not isinstance(created_at, str) or not isinstance(updated_at, str):
            raise InspectorDataError("检查人员时间字段无效")
        return InspectorRecord(item["id"].strip(), name, unit, police_number, item["enabled"], created_at, updated_at)

    def _write_records(self, records: list[InspectorRecord], *, keep_backup: bool = True) -> None:
        temp_path: Path | None = None
        backup_temp_path: Path | None = None
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.data_dir, delete=False, prefix=".inspectors-", suffix=".tmp") as handle:
                temp_path = Path(handle.name)
                json.dump({"schema_version": SCHEMA_VERSION, "inspectors": [asdict(record) for record in records]}, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            if keep_backup and self.file_path.exists():
                with self.file_path.open("rb") as source, tempfile.NamedTemporaryFile(
                    "wb", dir=self.data_dir, delete=False, prefix=".inspectors-backup-", suffix=".tmp"
                ) as backup_handle:
                    backup_temp_path = Path(backup_handle.name)
                    shutil.copyfileobj(source, backup_handle)
                    backup_handle.flush()
                    os.fsync(backup_handle.fileno())
                os.replace(backup_temp_path, self.backup_path)
                backup_temp_path = None
            os.replace(temp_path, self.file_path)
            temp_path = None
        except (OSError, ValueError) as exc:
            raise InspectorDataError("检查人员数据写入失败，原文件未替换") from exc
        finally:
            for path in (temp_path, backup_temp_path):
                if path is None:
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _reject_duplicate(records: list[InspectorRecord], fields: tuple[str, str, str], exclude_id: str | None = None) -> None:
        if any((item.id != exclude_id and (item.name, item.unit, item.police_number) == fields) for item in records):
            raise InspectorValidationError("相同姓名、单位和警号的人员已存在")

    @staticmethod
    def _find_or_raise(records: list[InspectorRecord], inspector_id: str) -> InspectorRecord:
        for record in records:
            if record.id == inspector_id:
                return record
        raise InspectorNotFoundError("检查人员不存在")
