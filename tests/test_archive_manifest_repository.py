"""Synthetic tests for independent ArchiveManifest registration."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_manifest_repository import (  # noqa: E402
    ArchiveManifestRepository,
)
from app.services.report_parsing_cache_service import ReportParsingCacheService  # noqa: E402


def manifest():
    return {
        "manifest_id": "manifest-synthetic",
        "validation_status": "validated",
        "parts": [{
            "part_id": "part-synthetic",
            "filename": "SYNTHETIC-CASE.rar",
            "size_bytes": 12,
            "md5": "a" * 32,
        }],
    }


def test_registry_persists_path_free_reusable_record(tmp_path):
    output = tmp_path / "output"
    final_dir = output / "compressed" / "context-1" / "manifest-1"
    final_dir.mkdir(parents=True)
    (final_dir / "SYNTHETIC-CASE.rar").write_bytes(b"synthetic-rar")
    repository = ArchiveManifestRepository(output)
    values = {"source_key": "1" * 64, "input_fingerprint": "2" * 64, "archive_fingerprint": "3" * 64}

    saved = repository.save(
        **values, manifest_id="manifest-1", final_dir=final_dir,
        public_manifest=manifest(), created_at=1,
    )
    restarted = ArchiveManifestRepository(output)
    matches = restarted.find_reusable(**values)

    assert saved.relative_final_dir == os.path.join("context-1", "manifest-1").replace("\\", "/")
    assert len(matches) == 1
    assert str(output) not in json.dumps(matches[0].__dict__, ensure_ascii=False)
    assert restarted.resolve_final_dir(matches[0]) == final_dir.resolve()


def test_input_change_marks_old_record_stale_without_deleting_rar(tmp_path):
    output = tmp_path / "output"
    first_dir = output / "compressed" / "context-1" / "manifest-1"
    second_dir = output / "compressed" / "context-2" / "manifest-2"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    rar = first_dir / "SYNTHETIC-CASE.rar"
    rar.write_bytes(b"synthetic-rar")
    repository = ArchiveManifestRepository(output)
    source = "1" * 64
    repository.save(
        source_key=source, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id="manifest-1", final_dir=first_dir, public_manifest=manifest(),
    )
    repository.save(
        source_key=source, input_fingerprint="4" * 64, archive_fingerprint="5" * 64,
        manifest_id="manifest-2", final_dir=second_dir, public_manifest=manifest(),
    )

    assert not repository.find_reusable(source, "2" * 64, "3" * 64)
    assert rar.is_file()


def test_mark_invalid_keeps_manifest_directory_and_rar(tmp_path):
    output = tmp_path / "output"
    final_dir = output / "compressed" / "context" / "manifest"
    final_dir.mkdir(parents=True)
    rar = final_dir / "SYNTHETIC.rar"
    rar.write_bytes(b"synthetic-rar")
    repository = ArchiveManifestRepository(output)
    repository.save(
        source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id="manifest", final_dir=final_dir, public_manifest=manifest(),
    )

    repository.mark_invalid("manifest")

    assert not repository.find_reusable("1" * 64, "2" * 64, "3" * 64)
    assert rar.is_file()


def test_parsing_cache_clear_does_not_touch_manifest_registry(tmp_path):
    output = tmp_path / "output"
    final_dir = output / "compressed" / "context" / "manifest"
    final_dir.mkdir(parents=True)
    rar = final_dir / "SYNTHETIC.rar"
    rar.write_bytes(b"synthetic-rar")
    repository = ArchiveManifestRepository(output)
    repository.save(
        source_key="1" * 64, input_fingerprint="2" * 64, archive_fingerprint="3" * 64,
        manifest_id="manifest", final_dir=final_dir, public_manifest=manifest(),
    )
    cache_dir = output / "parsed"
    cache_dir.mkdir()
    (cache_dir / "cache.json").write_text("{}", encoding="utf-8")

    assert ReportParsingCacheService().clear_all(str(cache_dir)) == 1
    assert (output / "compressed" / ".archive-manifest-index.json").is_file()
    assert rar.is_file()
