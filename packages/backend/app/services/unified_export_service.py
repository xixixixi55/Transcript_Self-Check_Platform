"""Unified export: latest Word + all RAR parts + HashMyFiles verification PNG.

The service writes a complete archive bundle into a user-chosen export path.
Inputs are pre-resolved by the controller (report, validated manifest, physical
part files, photos, template context) so the service stays testable.
"""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from ..config import OUTPUT_BASE
from ..repository.audit_event_repository import AuditEventRepository
from ..repository.hashmyfiles_repository import HashMyFilesError
from ..repository.workbench_database import WorkbenchDatabase
from .hashmyfiles_service import generate_verification_image
from .record_generator_service import generate_docx


class UnifiedExportError(ValueError):
    """Stable, path-free diagnostic for unified export failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


HashRunner = Callable[[list[Path], Path], str]


def _require_disc_mapping(
    manifest: dict[str, Any], plan: dict[str, Any] | None = None,
) -> None:
    # REQ-030: disc numbers live on the persisted plan slots (deferred mapping),
    # so the gate checks the plan when it exists and falls back to manifest parts
    # for callers without a plan (e.g. direct service tests).
    if plan is not None:
        missing = [
            slot for slot in plan.get("volume_slots", [])
            if slot.get("status") != "removed"
            and (
                (slot.get("disc_mapping") or {}).get("confirmation") != "confirmed"
                or not str((slot.get("disc_mapping") or {}).get("disc_number") or "").strip()
            )
        ]
        if missing:
            raise UnifiedExportError(
                "DISC_MAPPING_INCOMPLETE", "光盘编号尚未全部补齐，无法导出。",
            )
        return
    parts = manifest.get("parts") or []
    missing = [
        part.get("filename") for part in parts if not str(part.get("disc_number") or "").strip()
    ]
    if missing:
        raise UnifiedExportError(
            "DISC_MAPPING_INCOMPLETE", "光盘编号尚未全部补齐，无法导出。",
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
    hash_runner: HashRunner | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the archive bundle into ``export_path`` and return its projection."""
    _require_disc_mapping(manifest, plan)
    parts = manifest.get("parts") or []
    rar_paths = [final_dir / str(part["filename"]) for part in parts]
    for rar in rar_paths:
        if not rar.is_file():
            raise UnifiedExportError("ARCHIVE_PART_MISSING", "归档分卷文件缺失，无法导出。")

    export_path.mkdir(parents=True, exist_ok=True)
    runner = hash_runner or (lambda paths, out: generate_verification_image(paths, out))
    with tempfile.TemporaryDirectory(prefix=".biji-export-", dir=export_path) as temp_dir:
        staging_path = Path(temp_dir)
        word_filename = _export_word(
            report, _with_disc_mapping(manifest, plan), staging_path, photo_paths,
            template_context, word_filename,
        )
        for rar in rar_paths:
            shutil.copy2(rar, staging_path / rar.name)
        rar_filenames = [rar.name for rar in rar_paths]
        staged_rar_paths = [staging_path / name for name in rar_filenames]
        try:
            hash_image = runner(staged_rar_paths, staging_path)
        except HashMyFilesError as error:
            raise UnifiedExportError(error.code, error.args[0]) from error
        _publish_staged_bundle(
            staging_path, export_path,
            [word_filename, *rar_filenames, hash_image],
        )

    exported_at = _utc_now()
    _record_export(
        database, case_id, task_id, export_path, word_filename,
        rar_filenames, hash_image, exported_at,
    )
    return {
        "export_path": str(export_path),
        "word_filename": word_filename,
        "rar_filenames": rar_filenames,
        "hash_verification_image": hash_image,
        "exported_at": exported_at,
    }


def _publish_staged_bundle(
    staging_path: Path, export_path: Path, filenames: list[str],
) -> None:
    """Publish one complete bundle and restore the previous version on error."""
    names = list(dict.fromkeys(Path(name).name for name in filenames))
    rollback_path = staging_path / ".rollback"
    rollback_path.mkdir()
    backed_up: list[str] = []
    published: list[str] = []
    try:
        for name in [*names, "hash-verification.html"]:
            target = export_path / name
            if target.is_file():
                os.replace(target, rollback_path / name)
                backed_up.append(name)
        for name in names:
            source = staging_path / name
            if not source.is_file():
                raise OSError("staged export artifact missing")
            os.replace(source, export_path / name)
            published.append(name)
    except OSError as error:
        for name in published:
            (export_path / name).unlink(missing_ok=True)
        for name in backed_up:
            backup = rollback_path / name
            if backup.is_file():
                os.replace(backup, export_path / name)
        raise UnifiedExportError(
            "EXPORT_PUBLISH_FAILED", "统一导出文件发布失败，已保留上一版导出。",
        ) from error


def _with_disc_mapping(
    manifest: dict[str, Any], plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a manifest copy with deferred disc numbers layered from the plan.

    The stored manifest stays immutable (empty disc metadata for a deferred
    mapping); the Word renderer needs each part's disc date/number, so the
    mapped values are applied to a working copy before DOCX generation.
    """
    if plan is None:
        return manifest
    disc_by_ordinal = {
        slot["ordinal"]: slot.get("disc_mapping") or {}
        for slot in plan.get("volume_slots", [])
        if slot["status"] != "removed"
    }
    working = copy.deepcopy(manifest)
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
    hash_image: str,
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
            "hash_verification_image": hash_image,
            "exported_at": exported_at,
        },
        "created_at": exported_at,
    })


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
