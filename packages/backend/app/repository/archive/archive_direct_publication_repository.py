"""报告上级目录同卷发布日志：只重命名本次拥有的文件，不复制或覆盖。"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any
from contextlib import contextmanager

from ..case.local_case_export_directory_repository import LocalCaseExportDirectoryRepository
from ..workbench.workbench_database import utc_now
from ..workbench.workbench_errors import WorkbenchPersistenceError

JOURNAL_NAME = ".direct-publication.json"


def assert_direct_output_available(destination: Path, archive_base_name: str) -> None:
    """启动压缩前拒绝同名包及旧分卷，避免实际分卷数变化时混入旧产物。"""
    pattern = re.compile(
        rf"{re.escape(archive_base_name)}(?:\.part[0-9]+)?\.rar", re.IGNORECASE,
    )
    with os.scandir(destination) as entries:
        for entry in entries:
            # 名称已被目录或链接占用也属于冲突，不跟随链接读取内容。
            if pattern.fullmatch(entry.name):
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_CONFLICT")


def file_identity(path: Path) -> list[int]:
    value = path.lstat()
    if path.is_symlink() or not path.is_file() or getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        raise WorkbenchPersistenceError("ARCHIVE_PARTS_INVALID")
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns]


class ArchiveDirectPublicationRepository:
    def __init__(self, database: Any) -> None:
        self.database = database
        self.locations = LocalCaseExportDirectoryRepository(
            database.database_path.parent / "archive-export-locations.json", strict=True,
        )

    def prepare(
        self, origin: Path, staging: Path, destination: Path, manifest_id: str,
        filenames: list[str],
    ) -> None:
        if staging.resolve().parent != destination.resolve():
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_STAGING_INVALID")
        if any(Path(name).name != name or (destination / name).exists() for name in filenames):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_CONFLICT")
        payload = {
            "manifest_id": manifest_id, "staging": str(staging.resolve()),
            "destination": str(destination.resolve()),
            "files": {name: file_identity(staging / name) for name in filenames},
        }
        origin.mkdir(parents=True, exist_ok=False)
        with (origin / JOURNAL_NAME).open("x", encoding="utf-8") as stream:
            json.dump(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())

    def publish(self, origin: Path, destination: Path, manifest_id: str) -> Path:
        """幂等继续同卷发布；崩溃后通过文件身份辨别已移动和未移动分卷。"""
        payload = json.loads((origin / JOURNAL_NAME).read_text(encoding="utf-8"))
        staging = Path(payload["staging"])
        if (
            payload["manifest_id"] != manifest_id
            or Path(payload["destination"]) != destination.resolve()
            or staging.is_symlink() or staging.resolve().parent != destination.resolve()
            or not staging.name.startswith("archive-")
        ):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_MISMATCH")
        moved: list[str] = []
        try:
            for name, identity in payload["files"].items():
                if Path(name).name != name:
                    raise WorkbenchPersistenceError("ARCHIVE_PARTS_INVALID")
                source, target = staging / name, destination / name
                if target.exists() or target.is_symlink():
                    if file_identity(target) != identity or source.exists():
                        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_CONFLICT")
                    continue
                if file_identity(source) != identity:
                    raise WorkbenchPersistenceError("ARCHIVE_PARTS_INVALID")
                if os.name == "nt":
                    os.rename(source, target)  # Windows 同卷排他重命名，包括非 NTFS 卷。
                else:
                    os.link(source, target)
                    source.unlink()
                moved.append(name)
            self.locations.remember(
                manifest_id, destination, utc_now(), artifact_origin=str(origin.resolve()),
            )
        except Exception:
            for name in reversed(moved):
                target, source = destination / name, staging / name
                if not source.exists() and file_identity(target) == payload["files"][name]:
                    os.rename(target, source)
            raise
        return destination

    def resolve(self, origin: Path, manifest_id: str) -> Path:
        record = self.locations.latest(manifest_id)
        if record and record.get("artifact_origin") == str(origin.resolve(strict=False)):
            return Path(record["export_path"])
        return origin

    def assert_binding(self, origin: Path, attempt: dict[str, Any], manifest: dict[str, Any]) -> Path:
        payload = json.loads((origin / JOURNAL_NAME).read_text(encoding="utf-8"))
        staging = Path(str(attempt.get("staging_locator") or ""))
        names = {str(part["filename"]) for part in manifest["parts"]}
        if (
            not staging.is_absolute() or payload.get("staging") != str(staging.resolve())
            or payload.get("manifest_id") != manifest["manifest_id"]
            or set(payload.get("files", {})) != names
        ):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
        return staging

    @contextmanager
    def recovery_guard(self, attempt: dict[str, Any], intent: dict[str, Any]):
        """短发布事务阻止检查后、重命名前的来源编辑使授权失效。"""
        with self.database.transaction() as connection:
            fence = connection.execute(
                "SELECT * FROM archive_publish_fences WHERE fence_id=? AND deployment_instance_id=?",
                (intent.get("fence_id"), self.database.deployment_instance_id),
            ).fetchone()
            current = connection.execute(
                "SELECT s.source_id,s.revision,s.access_status,c.lifecycle "
                "FROM case_shells c JOIN source_records s ON c.source_id=s.source_id "
                "WHERE c.case_id=? AND c.deployment_instance_id=?",
                (attempt["case_id"], self.database.deployment_instance_id),
            ).fetchone()
            allowed = {"pending_verification"}
            if attempt["status"] == "succeeded":
                allowed.add("consumed")
            keys = ("attempt_id", "task_id", "case_id", "source_id", "source_revision", "draft_revision", "report_fingerprint")
            if (
                fence is None or fence["status"] not in allowed
                or any(fence[key] != intent[key] for key in keys)
                or current is None or current["source_id"] != attempt["source_id"]
                or current["revision"] != attempt["source_revision"]
                or current["access_status"] != "available"
                or (attempt["status"] != "succeeded" and current["lifecycle"] != "archive_interrupted")
            ):
                raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
            yield
