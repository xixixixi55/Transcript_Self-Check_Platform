"""经验证的公开归档结果投影和分卷下载查询。"""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from typing import Any

from ..repository.archive_asset_repository import ArchiveAssetRepository
from ..repository.archive_manifest_repository import ArchiveManifestRepository
from ..repository.archive_plan_repository import ArchivePlanRepository
from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ..repository.archive_task_repository import ArchiveTaskRepository
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_attempt_service import ArchiveAttemptService
from .archive_manifest_service import validate_manifest_files, validate_manifest_metadata
from .archive_publication_identity_service import assert_publication_identity
from .disc_sequence_service import archive_medium_for_mode


class ArchiveTaskResultService:
    def __init__(
        self,
        tasks: ArchiveTaskRepository,
        plans: ArchivePlanRepository,
        assets: ArchiveAssetRepository,
        attempts: ArchiveAttemptService,
        legacy_output_roots: tuple[str | Path, ...] = (),
    ) -> None:
        self.tasks = tasks
        self.plans = plans
        self.assets = assets
        self.attempts = attempts
        roots = (attempts.output_root, *legacy_output_roots)
        unique_roots = tuple(dict.fromkeys(Path(root).resolve(strict=False) for root in roots))
        self.manifests = tuple(
            ArchiveManifestRepository(root, database=attempts.database)
            for root in unique_roots
        )

    def result(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        summary = self.tasks.get_task_card_summary(task_id)
        if "view_result" not in summary["allowed_actions"] or summary["status"] != "succeeded":
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
        if not attempt_id:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt = self.attempts.repository.get_internal(str(attempt_id))
        self._assert_task_attempt(task, attempt)
        if attempt["status"] != "succeeded" or not attempt["manifest_id"]:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        manifest, _repository = self._verified_manifest(
            task_id, str(attempt_id), str(attempt["manifest_id"]),
            verify_content=False,
        )
        archive_mode = str(manifest.public_manifest.get("archive_mode") or "standard_split")
        plan = self.plans.get_latest_for_case(task["case_id"])
        disc_by_ordinal = {
            slot["ordinal"]: slot.get("disc_mapping") or {}
            for slot in (plan["volume_slots"] if plan else [])
            if slot["status"] != "removed"
        }
        parts = []
        for part in manifest.public_manifest["parts"]:
            mapping = disc_by_ordinal.get(part["part_number"], {}) or {}
            mapping_confirmed = mapping.get("confirmation") == "confirmed"
            disc_number = str(mapping.get("disc_number") or "") if mapping_confirmed else ""
            disc_date = str(mapping.get("disc_date") or "") if mapping_confirmed else ""
            if not disc_number and plan is None:
                # 对未持久化计划的调用方（合成工作线程、预填充路径），
                # 回退到 manifest 自身的光盘元数据。
                disc_number = str(part.get("disc_number") or "")
                disc_date = str(part.get("disc_date") or "")
            parts.append({
                "part_id": part["part_id"],
                "filename": part["filename"],
                "size_bytes": part["size_bytes"],
                "md5": str(part["md5"]).upper(),
                "disc_number": disc_number,
                "disc_date": disc_date,
            })
        return {
            "task_id": task_id,
            "case_id": task["case_id"],
            "manifest_id": attempt["manifest_id"],
            "archive_mode": archive_mode,
            "archive_medium": archive_medium_for_mode(archive_mode),
            "plan_row_revision": None if plan is None else plan["revision"],
            "verified_slots": [] if plan is None else plan["verified_slots"],
            "assets": self.assets.list_public_for_task(task_id),
            "parts": parts,
            "finished_at": summary["finished_at"],
        }

    def manifest_bundle(self, task_id: str) -> dict[str, Any]:
        """经验证的公开 Manifest 及其物理最终目录。"""
        task = self.tasks.get(task_id)
        summary = self.tasks.get_task_card_summary(task_id)
        if "view_result" not in summary["allowed_actions"] or summary["status"] != "succeeded":
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
        if not attempt_id:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt = self.attempts.repository.get_internal(str(attempt_id))
        self._assert_task_attempt(task, attempt)
        if attempt["status"] != "succeeded" or not attempt["manifest_id"]:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        record, repository = self._verified_manifest(
            task_id, str(attempt_id), str(attempt["manifest_id"]),
        )
        return {
            "public_manifest": record.public_manifest,
            "final_dir": repository.resolve_final_dir(record),
        }

    def download_part(self, task_id: str, part_id: str) -> tuple[str, Any]:
        task = self.tasks.get(task_id)
        summary = self.tasks.get_task_card_summary(task_id)
        if "view_result" not in summary["allowed_actions"]:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
        if not attempt_id:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt = self.attempts.repository.get_internal(str(attempt_id))
        self._assert_task_attempt(task, attempt)
        if attempt["status"] != "succeeded":
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        manifest, repository = self._verified_manifest(
            task_id, str(attempt_id), str(attempt["manifest_id"]),
        )
        part = next(
            (
                item for item in manifest.public_manifest["parts"]
                if item.get("part_id") == part_id
            ),
            None,
        )
        if part is None:
            raise WorkbenchPersistenceError("ARCHIVE_PART_NOT_FOUND")
        root = repository.resolve_final_dir(manifest).resolve(strict=True)
        path = (root / str(part["filename"])).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as error:
            raise WorkbenchPersistenceError("ARCHIVE_PART_NOT_FOUND") from error
        return str(part["filename"]), path

    def _verified_manifest(
        self, task_id: str, attempt_id: str, manifest_id: str, *,
        verify_content: bool = True,
    ) -> Any:
        matches = []
        for repository in self.manifests:
            records = [
                item for item in repository.find_for_attempt(attempt_id)
                if item.manifest_id == manifest_id
            ]
            if len(records) == 1 and repository.resolve_final_dir(records[0]).is_dir():
                matches.append((records[0], repository))
        if len(matches) != 1:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        record, repository = matches[0]
        intent = ArchivePublishIntentRepository(self.attempts.database).get_for_attempt(attempt_id)
        if intent is None or intent["phase"] != "verified" or intent.get("publication_status") != "verified" or any(
            intent[key] != value for key, value in {
                "manifest_id": record.manifest_id,
                "source_key": record.source_key,
                "input_fingerprint": record.input_fingerprint,
                "archive_fingerprint": record.archive_fingerprint,
                "relative_final_dir": record.relative_final_dir,
                "public_manifest": record.public_manifest,
            }.items()
        ):
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        if (
            intent.get("task_id") != task_id
            or intent.get("deployment_instance_id") != self.attempts.database.deployment_instance_id
            or record.publication_id != intent.get("publication_id")
            or record.publication_digest != intent.get("publication_digest")
        ):
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        view = SimpleNamespace(
            manifest_id=record.manifest_id,
            public_manifest=record.public_manifest,
            final_dir=repository.resolve_final_dir(record),
        )
        try:
            assert_publication_identity(record, intent)
        except WorkbenchPersistenceError as error:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE") from error
        validation_error = (
            validate_manifest_files(view)
            if verify_content
            else validate_manifest_metadata(view)
        )
        if validation_error is not None:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        return record, repository

    def _assert_task_attempt(self, task: dict[str, Any], attempt: dict[str, Any]) -> None:
        if (
            attempt.get("task_id") != task["task_id"]
            or attempt.get("deployment_instance_id") != self.attempts.database.deployment_instance_id
            or attempt.get("case_id") != task["case_id"]
        ):
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
