from pathlib import Path
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_storage_settings_repository import (  # noqa: E402
    ArchiveStorageSettingsRepository,
)
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_storage_settings_service import (  # noqa: E402
    ArchiveStorageSettingsService,
)


def test_custom_archive_storage_is_atomic_and_requires_restart(tmp_path: Path) -> None:
    default_root = tmp_path / "SYNTHETIC-DEFAULT"
    resource_root = tmp_path / "SYNTHETIC-PROGRAM"
    selected = tmp_path / "SYNTHETIC-D-DRIVE"
    default_root.mkdir()
    resource_root.mkdir()
    selected.mkdir()
    repository = ArchiveStorageSettingsRepository(tmp_path / "settings.json")
    service = ArchiveStorageSettingsService(
        repository,
        default_output_root=default_root,
        active_output_root=default_root,
        resource_root=resource_root,
    )

    updated = service.select(str(selected))

    assert updated["configured_directory"] == str(selected / "文枢归档工作区")
    assert updated["active_directory"] == str(default_root)
    assert updated["valid"] is True
    assert updated["restart_required"] is True
    assert (selected / "文枢归档工作区").is_dir()
    with pytest.raises(WorkbenchPersistenceError) as failure:
        service.require_ready_for_new_archive()
    assert failure.value.code == "ARCHIVE_STORAGE_RESTART_REQUIRED"


def test_active_custom_archive_storage_is_ready_and_reset_is_restart_bound(tmp_path: Path) -> None:
    default_root = tmp_path / "SYNTHETIC-DEFAULT"
    resource_root = tmp_path / "SYNTHETIC-PROGRAM"
    selected = tmp_path / "SYNTHETIC-D-DRIVE"
    for path in (default_root, resource_root, selected):
        path.mkdir()
    repository = ArchiveStorageSettingsRepository(tmp_path / "settings.json")
    repository.save_parent(selected, resource_root)
    active = selected / "文枢归档工作区"
    service = ArchiveStorageSettingsService(
        repository, default_output_root=default_root,
        active_output_root=active, resource_root=resource_root,
    )

    service.require_ready_for_new_archive()
    reset = service.reset()

    assert reset["custom"] is False
    assert reset["configured_directory"] == str(default_root)
    assert reset["restart_required"] is True


def test_archive_storage_rejects_program_directory_overlap(tmp_path: Path) -> None:
    resource_root = tmp_path / "SYNTHETIC-PROGRAM"
    resource_root.mkdir()
    repository = ArchiveStorageSettingsRepository(tmp_path / "settings.json")

    with pytest.raises(ValueError, match="ARCHIVE_STORAGE_DIRECTORY_UNSAFE"):
        repository.save_parent(resource_root, resource_root)
