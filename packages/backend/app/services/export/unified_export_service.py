"""统一导出：最新 Word 文件及所有已验证的 RAR 分卷。

该服务将完整归档包写入用户选择的导出路径。输入由控制器预先解析（报告、
已验证的 Manifest、物理分卷文件、照片和模板上下文），从而保持服务可测试。
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
import threading
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Callable
from uuid import uuid4

from ...config import OUTPUT_BASE
from ...repository.case.audit_event_repository import AuditEventRepository
from ...repository.case.local_case_export_directory_repository import LocalCaseExportDirectoryRepository
from ...repository.workbench.workbench_database import WorkbenchDatabase
from ...repository.archive.archive_hash_repository import compute_hash_streaming
from ...repository.integrity.hash_algorithm_repository import manifest_part_business_hash
from ..attachment.attachment2_image_service import Attachment2ImageError
from ..attachment.attachment_plan_models_service import AttachmentPlanError
from ..document.record_generator_service import generate_docx
from ..archive.archive_manifest_output_security_service import assert_safe_output_file


_EXPORT_DIRECTORY_LOCKS: weakref.WeakValueDictionary[str, threading.Lock] = (
    weakref.WeakValueDictionary()
)
_EXPORT_DIRECTORY_LOCKS_GUARD = threading.RLock()


class UnifiedExportError(ValueError):
    """不含路径的稳定统一导出失败诊断信息。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_disc_mapping(
    manifest: dict[str, Any], plan: dict[str, Any] | None = None,
) -> None:
    # REQ-030：光盘编号位于持久化计划槽位中（延迟映射），
    # 因此计划存在时门禁检查该计划；对于没有计划的调用方
    #（例如直接服务测试），则回退到 manifest 分卷。
    if plan is not None:
        slots = [slot for slot in plan.get("volume_slots", []) if slot.get("status") != "removed"]
        ordinals = [slot.get("ordinal") for slot in slots]
        part_ordinals = [part.get("part_number") or index for index, part in enumerate(manifest.get("parts") or [], 1)]
        if not part_ordinals or len(ordinals) != len(part_ordinals) or set(ordinals) != set(part_ordinals):
            raise UnifiedExportError("DISC_MAPPING_INCOMPLETE", "介质映射与实际分卷不一致，无法导出。")
        missing = [
            slot for slot in slots
            if (
                (slot.get("disc_mapping") or {}).get("confirmation") != "confirmed"
                or not str((slot.get("disc_mapping") or {}).get("disc_number") or "").strip()
            )
        ]
        if missing:
            raise UnifiedExportError(
                "DISC_MAPPING_INCOMPLETE", "介质编号尚未全部补齐，无法导出。",
            )
        return
    parts = manifest.get("parts") or []
    missing = [
        part.get("filename") for part in parts if not str(part.get("disc_number") or "").strip()
    ]
    if missing:
        raise UnifiedExportError(
            "DISC_MAPPING_INCOMPLETE", "介质编号尚未全部补齐，无法导出。",
        )


def unified_export(
    *,
    report: dict[str, Any],
    manifest: dict[str, Any],
    final_dir: Path,
    export_path: Path,
    photo_paths: list[Path],
    template_context: dict[str, Any],
    word_filename: str | None = None,
    database: WorkbenchDatabase | None = None,
    case_id: str | None = None,
    task_id: str | None = None,
    output_root: str | Path = OUTPUT_BASE,
    plan: dict[str, Any] | None = None,
    relocate: bool = False,
) -> dict[str, Any]:
    """将归档包写入 ``export_path`` 并返回其投影。"""
    _require_disc_mapping(manifest, plan)
    parts = manifest.get("parts") or []
    rar_paths = [final_dir / str(part["filename"]) for part in parts]
    for rar in rar_paths:
        if not rar.is_file():
            raise UnifiedExportError("ARCHIVE_PART_MISSING", "归档分卷文件缺失，无法导出。")

    export_path.mkdir(parents=True, exist_ok=True)
    with _export_directory_lock(export_path), tempfile.TemporaryDirectory(prefix=".biji-export-", dir=export_path) as temp_dir:
        staging_path = Path(temp_dir)
        word_filename = _export_word(
            report, with_disc_mapping(manifest, plan), staging_path, photo_paths,
            template_context, word_filename,
        )
        already_at_destination = final_dir.resolve() == export_path.resolve()
        if relocate and not already_at_destination:
            for rar in rar_paths:
                if (export_path / rar.name).exists():
                    raise UnifiedExportError("EXPORT_TARGET_CONFLICT", "报告上级目录已有同名压缩包，请先移走已有文件后重试。")
        for rar in rar_paths:
            if not already_at_destination:
                shutil.copy2(rar, staging_path / rar.name)
        if not already_at_destination:
            # 历史工作区迁移只有副本校验通过后才能发布、登记并清理原件。
            for part in parts:
                copied = staging_path / str(part["filename"])
                try:
                    assert_safe_output_file(copied)
                    algorithm, expected_hash = manifest_part_business_hash(part)
                    if copied.stat().st_size != part["size_bytes"] or compute_hash_streaming(
                        copied, staging_path, algorithm,
                    ).lower() != expected_hash.lower():
                        raise ValueError("ARCHIVE_COPY_CHANGED")
                except (OSError, ValueError, KeyError) as error:
                    raise UnifiedExportError(
                        "EXPORT_PUBLISH_FAILED", "归档副本校验失败，已保留原压缩包和上一版导出。",
                    ) from error
        rar_filenames = [rar.name for rar in rar_paths]
        origin = final_dir.resolve()
        remember = None
        if relocate and not already_at_destination:
            if database is None:
                raise UnifiedExportError("EXPORT_DIRECTORY_RECORD_FAILED", "导出位置无法登记。")
            locations = LocalCaseExportDirectoryRepository(
                database.database_path.parent / "archive-export-locations.json",
                strict=True,
            )
            def remember() -> None:
                locations.remember(
                    str(manifest["manifest_id"]), export_path, _utc_now(),
                    artifact_origin=str(origin),
                )
        elif relocate and database is not None:
            # 历史迁移可能已登记目标、但尚未来得及清理工作区原件；损坏的
            # 旧投影不得阻断以 SQLite 绝对定位的新直出结果。
            locations = LocalCaseExportDirectoryRepository(
                database.database_path.parent / "archive-export-locations.json",
                strict=False,
            )
            previous = locations.latest(str(manifest["manifest_id"]))
            if previous and previous.get("artifact_origin"):
                origin = Path(previous["artifact_origin"])
        _publish_staged_bundle(
            staging_path, export_path,
            [word_filename, *([] if already_at_destination else rar_filenames)],
            **({"on_publish": remember, "remove_legacy": False,
                "exclusive_names": set(rar_filenames) if not already_at_destination else set()} if relocate else {}),
        )

        if relocate and origin != export_path.resolve():
            # 仅清理登记的工作区原件；重试也可完成上次登记后的残留清理。
            for name in rar_filenames:
                rar = origin / name
                if rar.exists():
                    assert_safe_output_file(rar)
                    origin.chmod(origin.stat().st_mode | 0o700)
                    rar.chmod(rar.stat().st_mode | 0o200)
                    rar.unlink()

    exported_at = _utc_now()
    _record_export(
        database, case_id, task_id, export_path, word_filename,
        rar_filenames, exported_at,
    )
    return {
        "export_path": str(export_path),
        "word_filename": word_filename,
        "rar_filenames": rar_filenames,
        "exported_at": exported_at,
    }


def _publish_staged_bundle(
    staging_path: Path, export_path: Path, filenames: list[str],
    *, on_publish: Callable[[], None] | None = None, remove_legacy: bool = True,
    exclusive_names: set[str] | None = None,
) -> None:
    """发布一个完整包，并在出错时恢复上一版本。"""
    with _export_directory_lock(export_path):
        _publish_staged_bundle_unlocked(
            staging_path, export_path, filenames, on_publish=on_publish, remove_legacy=remove_legacy,
            exclusive_names=exclusive_names,
        )


def _export_directory_lock(export_path: Path) -> threading.Lock:
    normalized = os.path.normcase(
        os.path.normpath(str(export_path.resolve(strict=False)))
    ).casefold()
    with _EXPORT_DIRECTORY_LOCKS_GUARD:
        lock = _EXPORT_DIRECTORY_LOCKS.get(normalized)
        if lock is None:
            lock = threading.RLock()
            _EXPORT_DIRECTORY_LOCKS[normalized] = lock
        return lock


def _publish_staged_bundle_unlocked(
    staging_path: Path, export_path: Path, filenames: list[str],
    *, on_publish: Callable[[], None] | None = None, remove_legacy: bool = True,
    exclusive_names: set[str] | None = None,
) -> None:
    names = list(dict.fromkeys(Path(name).name for name in filenames))
    rollback_path = staging_path / ".rollback"
    rollback_path.mkdir()
    backed_up: list[str] = []
    published: list[str] = []
    try:
        for name in [*names, *(["hash-verification.png", "hash-verification.html"] if remove_legacy else [])]:
            if name in (exclusive_names or set()):
                continue
            target = export_path / name
            if target.is_file():
                os.replace(target, rollback_path / name)
                backed_up.append(name)
        for name in names:
            source = staging_path / name
            if not source.is_file():
                raise OSError("staged export artifact missing")
            if name in (exclusive_names or set()):
                # 同卷原子排他创建；不得覆盖复制期间由其他程序创建的同名文件。
                if os.name == "nt":
                    os.rename(source, export_path / name)
                else:
                    os.link(source, export_path / name)
            else:
                os.replace(source, export_path / name)
            published.append(name)
        if on_publish is not None:
            on_publish()
    except Exception as error:
        for name in published:
            target = export_path / name
            if target.is_file():
                target.chmod(target.stat().st_mode | 0o200)
                target.unlink()
        for name in backed_up:
            backup = rollback_path / name
            if backup.is_file():
                os.replace(backup, export_path / name)
        raise UnifiedExportError(
            "EXPORT_PUBLISH_FAILED", "统一导出文件发布失败，已保留上一版导出。",
        ) from error


def with_disc_mapping(
    manifest: dict[str, Any], plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """返回一份 Manifest 副本，并在其上叠加计划中的延迟光盘编号。

    存储的 Manifest 保持不可变（延迟映射的光盘元数据为空）。独立 Word 导出和统一导出
    都调用此辅助函数，因此其附件计划会收到一致的光盘元数据。
    """
    working = copy.deepcopy(manifest)
    if plan is None:
        return working
    disc_by_ordinal = {
        slot["ordinal"]: slot.get("disc_mapping") or {}
        for slot in plan.get("volume_slots", [])
        if slot["status"] != "removed"
    }
    for index, part in enumerate(working.get("parts", [])):
        ordinal = part.get("part_number") or (index + 1)
        mapping = disc_by_ordinal.get(ordinal, {}) or {}
        if mapping.get("confirmation") != "confirmed":
            continue
        disc_number = str(mapping.get("disc_number") or "")
        if disc_number:
            part["disc_number"] = disc_number
            part["disc_date"] = str(mapping.get("disc_date") or part.get("disc_date") or "")
    return working


def _export_word(
    report: dict[str, Any],
    manifest: dict[str, Any],
    export_path: Path,
    photo_paths: list[Path],
    template_context: dict[str, Any],
    word_filename: str | None = None,
) -> str:
    try:
        docx_path = generate_docx(
            report, photo_paths=photo_paths, output_dir=str(export_path),
            archive_manifest=manifest, output_filename=word_filename,
            **template_context,
        )
    except (AttachmentPlanError, Attachment2ImageError) as error:
        raise UnifiedExportError(error.code, error.safe_message) from error
    except Exception as error:
        raise UnifiedExportError(
            "WORD_RENDER_FAILED", "Word 生成失败，导出未完成。",
        ) from error
    return os.path.basename(str(docx_path))


def _record_export(
    database: WorkbenchDatabase | None,
    case_id: str | None,
    task_id: str | None,
    export_path: Path,
    word_filename: str,
    rar_filenames: list[str],
    exported_at: str,
) -> None:
    if database is None:
        return
    AuditEventRepository(database).record({
        "event_id": str(uuid4()),
        "event_type": "unified_export",
        "deployment_instance_id": database.deployment_instance_id,
        "client_instance_id": "system",
        "session_id": "system",
        "local_display_name": None,
        "identity_kind": "local_session",
        "case_id": case_id,
        "task_id": task_id,
        "payload": {
            "word_filename": word_filename,
            "rar_filenames": rar_filenames,
            "exported_at": exported_at,
        },
        "created_at": exported_at,
    })


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
