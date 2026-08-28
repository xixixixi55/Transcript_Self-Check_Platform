"""持久报告目录来源的受保护文件系统定位符。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .workbench_database import WorkbenchDatabase
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id


class SourceLocatorRepository:
    """使本地路径不进入公开 SQLite 工作台记录。"""

    def __init__(self, database: WorkbenchDatabase) -> None:
        self.root = database.database_path.parent / "source-locators"

    def save(self, source_id: str, internal_path: str, allowed_root: str) -> None:
        source_id = validate_opaque_id(source_id)
        if not internal_path or not allowed_root:
            raise WorkbenchPersistenceError("SOURCE_LOCATOR_INVALID")
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"internal_path": internal_path, "allowed_root": allowed_root}
        temporary = self.root / f".{source_id}.tmp"
        target = self.root / f"{source_id}.json"
        try:
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            temporary.replace(target)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise WorkbenchPersistenceError("SOURCE_LOCATOR_WRITE_FAILED") from error

    def get(self, source_id: str) -> dict[str, str]:
        source_id = validate_opaque_id(source_id)
        try:
            value: Any = json.loads((self.root / f"{source_id}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkbenchPersistenceError("SOURCE_LOCATOR_MISSING") from error
        if not isinstance(value, dict) or not all(isinstance(value.get(key), str) for key in ("internal_path", "allowed_root")):
            raise WorkbenchPersistenceError("SOURCE_LOCATOR_INVALID")
        return {"internal_path": value["internal_path"], "allowed_root": value["allowed_root"]}

    def remove(self, source_id: str) -> None:
        try:
            (self.root / f"{validate_opaque_id(source_id)}.json").unlink(missing_ok=True)
        except (OSError, WorkbenchPersistenceError):
            return
