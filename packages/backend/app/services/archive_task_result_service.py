"""Verified public archive-result projection and part download lookup."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ..repository.archive_asset_repository import ArchiveAssetRepository
from ..repository.archive_manifest_repository import ArchiveManifestRepository
from ..repository.archive_plan_repository import ArchivePlanRepository
from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ..repository.archive_task_repository import ArchiveTaskRepository
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_attempt_service import ArchiveAttemptService
from .archive_manifest_service import validate_manifest_files


class ArchiveTaskResultService:
    def __init__(
        self,
        tasks: ArchiveTaskRepository,
        plans: ArchivePlanRepository,
        assets: ArchiveAssetRepository,
        attempts: ArchiveAttemptService,
    ) -> None:
        self.tasks = tasks
        self.plans = plans
        self.assets = assets
        self.attempts = attempts
        self.manifests = ArchiveManifestRepository(attempts.output_root)

    def result(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        summary = self.tasks.get_task_card_summary(task_id)
        if "view_result" not in summary["allowed_actions"] or summary["status"] != "succeeded":
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
        attempt = self.attempts.repository.get_public(str(attempt_id))
        if attempt["status"] != "succeeded" or not attempt["manifest_id"]:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        manifest = self._verified_manifest(str(attempt_id), str(attempt["manifest_id"]))
        plan = self.plans.get_latest_for_case(task["case_id"])
        return {
            "task_id": task_id,
            "case_id": task["case_id"],
            "manifest_id": attempt["manifest_id"],
            "verified_slots": [] if plan is None else plan["verified_slots"],
            "assets": self.assets.list_public_for_task(task_id),
            "parts": [
                {
                    key: part[key] for key in (
                        "part_id", "filename", "size_bytes", "md5",
                        "disc_number", "disc_date",
                    )
                }
                for part in manifest.public_manifest["parts"]
            ],
            "finished_at": summary["finished_at"],
        }

    def download_part(self, task_id: str, part_id: str) -> tuple[str, Any]:
        task = self.tasks.get(task_id)
        summary = self.tasks.get_task_card_summary(task_id)
        if "view_result" not in summary["allowed_actions"]:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
        attempt = self.attempts.repository.get_public(str(attempt_id))
        if attempt["status"] != "succeeded":
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        manifest = self._verified_manifest(str(attempt_id), str(attempt["manifest_id"]))
        part = next(
            (
                item for item in manifest.public_manifest["parts"]
                if item.get("part_id") == part_id
            ),
            None,
        )
        if part is None:
            raise WorkbenchPersistenceError("ARCHIVE_PART_NOT_FOUND")
        root = self.manifests.resolve_final_dir(manifest).resolve(strict=True)
        path = (root / str(part["filename"])).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as error:
            raise WorkbenchPersistenceError("ARCHIVE_PART_NOT_FOUND") from error
        return str(part["filename"]), path

    def _verified_manifest(self, attempt_id: str, manifest_id: str) -> Any:
        records = [
            item for item in self.manifests.find_for_attempt(attempt_id)
            if item.manifest_id == manifest_id
        ]
        if len(records) != 1:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        record = records[0]
        intent = ArchivePublishIntentRepository(self.attempts.database).get_for_attempt(attempt_id)
        if intent is None or intent["phase"] != "verified" or any(
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
        view = SimpleNamespace(
            manifest_id=record.manifest_id,
            public_manifest=record.public_manifest,
            final_dir=self.manifests.resolve_final_dir(record),
        )
        if validate_manifest_files(view) is not None:
            raise WorkbenchPersistenceError("ARCHIVE_RESULT_NOT_AVAILABLE")
        return record
