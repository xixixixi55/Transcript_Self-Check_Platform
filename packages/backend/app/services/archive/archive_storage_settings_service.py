"""选择重启绑定归档存储根目录的应用服务。"""

from __future__ import annotations

from pathlib import Path

from ...repository.archive_storage_settings_repository import ArchiveStorageSettingsRepository
from ...repository.workbench_errors import WorkbenchPersistenceError


class ArchiveStorageSettingsService:
    def __init__(
        self, repository: ArchiveStorageSettingsRepository, *,
        default_output_root: str | Path, active_output_root: str | Path,
        resource_root: str | Path,
    ) -> None:
        self.repository = repository
        self.default_output_root = Path(default_output_root).resolve(strict=False)
        self.active_output_root = Path(active_output_root).resolve(strict=False)
        self.resource_root = Path(resource_root).resolve(strict=False)

    def status(self) -> dict[str, object]:
        selection = self.repository.resolve(self.default_output_root, self.resource_root)
        return {
            "active_directory": str(self.active_output_root),
            "configured_directory": str(selection.desired_output_root),
            "default_directory": str(self.default_output_root),
            "custom": selection.custom,
            "valid": selection.valid,
            "restart_required": selection.desired_output_root != self.active_output_root,
            "error_code": selection.error_code,
        }

    def select(self, selected_parent: str) -> dict[str, object]:
        try:
            self.repository.save_parent(selected_parent, self.resource_root)
        except ValueError as error:
            raise WorkbenchPersistenceError(str(error)) from error
        except OSError as error:
            code = str(error) if str(error).startswith("ARCHIVE_STORAGE_") else "ARCHIVE_STORAGE_SETTINGS_WRITE_FAILED"
            raise WorkbenchPersistenceError(code) from error
        return self.status()

    def reset(self) -> dict[str, object]:
        try:
            self.repository.reset()
        except OSError as error:
            raise WorkbenchPersistenceError("ARCHIVE_STORAGE_SETTINGS_WRITE_FAILED") from error
        return self.status()

    def require_ready_for_new_archive(self) -> None:
        status = self.status()
        if not status["valid"]:
            raise WorkbenchPersistenceError(str(status["error_code"]))
        if status["restart_required"]:
            raise WorkbenchPersistenceError("ARCHIVE_STORAGE_RESTART_REQUIRED")


__all__ = ["ArchiveStorageSettingsService"]
