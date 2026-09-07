"""SYNTHETIC: 已移除设置，仅允许只读定位旧归档。"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/backend"))
from app.repository.archive.archive_storage_settings_repository import ArchiveStorageSettingsRepository


def test_legacy_storage_is_read_only_and_never_creates_work_directory(tmp_path):
    settings = tmp_path / "SYNTHETIC-settings.json"
    settings.write_text(json.dumps({"schema_version": 1, "selected_parent": str(tmp_path)}), encoding="utf-8")
    repository = ArchiveStorageSettingsRepository(settings)
    before = settings.read_bytes()
    selected = repository.resolve(tmp_path / "SYNTHETIC-default", tmp_path / "SYNTHETIC-program")
    assert selected.valid is False
    assert not (tmp_path / "文枢归档工作区").exists()
    assert settings.read_bytes() == before
    assert not hasattr(repository, "save_parent")
    assert not hasattr(repository, "reset")


def test_legacy_existing_root_remains_discoverable(tmp_path):
    old = tmp_path / "文枢归档工作区"
    old.mkdir()
    settings = tmp_path / "SYNTHETIC-settings.json"
    settings.write_text(json.dumps({"schema_version": 1, "selected_parent": str(tmp_path)}), encoding="utf-8")
    selection = ArchiveStorageSettingsRepository(settings).resolve(tmp_path / "SYNTHETIC-default", tmp_path / "SYNTHETIC-program")
    assert selection.valid
    assert selection.desired_output_root == old
