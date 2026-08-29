"""本地检查人员库的版本化原子 JSON 存储。"""

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

SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
MAX_NAME_LENGTH = 100
MAX_UNIT_LENGTH = 200
MAX_POSITION_LENGTH = 100
MAX_POLICE_NUMBER_LENGTH = 64
_WRITE_LOCK = threading.RLock()


class InspectorValidationError(ValueError):
    """用户提供的检查人员字段验证失败。"""


class InspectorDataError(RuntimeError):
    """库文件缺失、损坏或无法安全写入。"""


class InspectorNotFoundError(LookupError):
    """请求的检查人员 ID 不存在。"""


@dataclass(frozen=True)
class InspectorRecord:
    id: str
    name: str
    unit: str
    position: str
    police_number: str
    created_at: str
    updated_at: str


def project_case_inspector_snapshot(
    value: Any, *, snapshot_id: str, selected_order: int,
) -> dict[str, Any]:
    """将库或解析器值复制到分离的案件级检查人员快照。"""
    raw = dict(value) if isinstance(value, Mapping) else {
        "id": value.id, "name": value.name, "unit": value.unit, "position": value.position,
        "police_number": value.police_number,
    }
    snapshot = {
        "snapshot_id": snapshot_id,
        "name": str(raw.get("name", "")),
        "unit": str(raw.get("unit", "")),
        "position": str(raw.get("position", "")),
        "police_number": str(raw.get("police_number", raw.get("badge_number", ""))),
        "selected_order": selected_order,
    }
    inspector_id = raw.get("inspector_id", raw.get("id"))
    if isinstance(inspector_id, str) and inspector_id.strip():
        snapshot["inspector_id"] = inspector_id.strip()
    for key in ("captured_at", "source_version"):
        if isinstance(raw.get(key), str) and raw[key].strip():
            snapshot[key] = raw[key]
    return snapshot


def resolve_app_data_dir(env: Mapping[str, str] | None = None) -> Path:
    """解析应用数据目录，不记录用户路径。"""

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


def _validate_fields(
    name: Any, unit: Any, position: Any, police_number: Any, *, position_required: bool = True,
) -> tuple[str, str, str, str]:
    if position_required:
        position_value = _validate_text("职位", position, MAX_POSITION_LENGTH)
    elif not isinstance(position, str):
        raise InspectorValidationError("职位必须是文本")
    else:
        position_value = position.strip()
        if position_value:
            position_value = _validate_text("职位", position_value, MAX_POSITION_LENGTH)
    return (
        _validate_text("姓名", name, MAX_NAME_LENGTH),
        _validate_text("单位", unit, MAX_UNIT_LENGTH),
        position_value,
        _validate_text("警号", police_number, MAX_POLICE_NUMBER_LENGTH),
    )


class InspectorRepository:
    """可在不更改服务的情况下替换的仓储接口。"""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else resolve_app_data_dir()
        self.file_path = self.data_dir / "inspectors.json"
        self.backup_path = self.data_dir / "inspectors.json.bak"

    def list(self) -> list[InspectorRecord]:
        with _WRITE_LOCK:
            records = self._read_records(create_if_missing=True)
            return records

    def get(self, inspector_id: str) -> InspectorRecord | None:
        with _WRITE_LOCK:
            return next((record for record in self._read_records(True) if record.id == inspector_id), None)

    def create(self, name: Any, unit: Any, position: Any, police_number: Any) -> InspectorRecord:
        fields = _validate_fields(name, unit, position, police_number)
        with _WRITE_LOCK:
            records = self._read_records(True)
            self._reject_duplicate(records, fields)
            now = _now()
            record = InspectorRecord(str(uuid.uuid4()), *fields, now, now)
            self._write_records([*records, record])
            return record

    def update(
        self, inspector_id: str, *, name: Any = None, unit: Any = None,
        position: Any = None, police_number: Any = None,
    ) -> InspectorRecord:
        with _WRITE_LOCK:
            records = self._read_records(True)
            current = self._find_or_raise(records, inspector_id)
            fields = _validate_fields(
                current.name if name is None else name,
                current.unit if unit is None else unit,
                current.position if position is None else position,
                current.police_number if police_number is None else police_number,
                position_required=position is not None or bool(current.position),
            )
            self._reject_duplicate(records, fields, exclude_id=inspector_id)
            updated = InspectorRecord(current.id, *fields, current.created_at, _now())
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
        schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
        if schema_version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
            raise InspectorDataError("检查人员数据版本不受支持")
        raw_records = payload.get("inspectors")
        if not isinstance(raw_records, list):
            raise InspectorDataError("检查人员数据结构无效")
        records = [self._record_from_json(item, schema_version) for item in raw_records]
        if len({record.id for record in records}) != len(records):
            raise InspectorDataError("检查人员数据包含重复ID")
        return records

    def _record_from_json(self, item: Any, schema_version: int) -> InspectorRecord:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item.get("id", "").strip()
        ):
            raise InspectorDataError("检查人员数据结构无效")
        try:
            name, unit, position, police_number = _validate_fields(
                item.get("name"), item.get("unit"),
                item.get("position", "") if schema_version == SCHEMA_VERSION else "",
                item.get("police_number"), position_required=False,
            )
        except InspectorValidationError as exc:
            raise InspectorDataError("检查人员数据校验失败") from exc
        created_at = item.get("created_at")
        updated_at = item.get("updated_at")
        if not isinstance(created_at, str) or not isinstance(updated_at, str):
            raise InspectorDataError("检查人员时间字段无效")
        return InspectorRecord(item["id"].strip(), name, unit, position, police_number, created_at, updated_at)

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
    def _reject_duplicate(records: list[InspectorRecord], fields: tuple[str, str, str, str], exclude_id: str | None = None) -> None:
        if any((item.id != exclude_id and (item.name, item.unit, item.position, item.police_number) == fields) for item in records):
            raise InspectorValidationError("相同姓名、单位、职位和警号的人员已存在")

    @staticmethod
    def _find_or_raise(records: list[InspectorRecord], inspector_id: str) -> InspectorRecord:
        for record in records:
            if record.id == inspector_id:
                return record
        raise InspectorNotFoundError("检查人员不存在")
