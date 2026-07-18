import os
import sys
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_authorization_repository import AuthorizedInputRoot  # noqa: E402
from app.services.archive_runtime_service import (  # noqa: E402
    ArchiveRuntimeError,
    ArchiveRuntimeStore,
)


def make_context(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    (source / "evidence.bin").write_bytes(b"evidence")
    output = tmp_path / "output"
    store = ArchiveRuntimeStore()
    record = store.create_context(
        AuthorizedInputRoot(source.resolve(), "exact_directory_grant", "internal-test"),
        "Synthetic case",
        output_root=str(output),
    )
    return store, record, source


def test_context_id_is_random_and_public_summary_has_no_paths(tmp_path):
    store, record, source = make_context(tmp_path)
    UUID(record.context_id)
    summary = record.public_summary()
    assert set(summary) == {
        "archive_context_id", "file_count", "total_input_bytes", "status",
        "created_at", "expires_at",
    }
    assert str(source) not in str(summary)
    assert summary["file_count"] == 1
    assert summary["total_input_bytes"] == len(b"evidence")


def test_context_busy_expired_and_not_found_codes(tmp_path):
    store, record, _ = make_context(tmp_path)
    store.acquire_context(record.context_id)
    with pytest.raises(ArchiveRuntimeError) as busy:
        store.acquire_context(record.context_id)
    assert busy.value.code == "ARCHIVE_CONTEXT_BUSY"
    store.release_context(record.context_id)
    record.expires_at = 0
    with pytest.raises(ArchiveRuntimeError) as expired:
        store.acquire_context(record.context_id)
    assert expired.value.code == "ARCHIVE_CONTEXT_EXPIRED"
    with pytest.raises(ArchiveRuntimeError) as missing:
        store.get_context_summary(record.context_id)
    assert missing.value.code == "ARCHIVE_CONTEXT_NOT_FOUND"


def test_cleanup_never_deletes_original_case_input(tmp_path):
    store, record, source = make_context(tmp_path)
    record.expires_at = 0
    store.cleanup_expired(now=1)
    assert source.is_dir()
    assert (source / "evidence.bin").is_file()


def test_expiring_manifest_metadata_never_deletes_published_output(tmp_path):
    store = ArchiveRuntimeStore()
    final_dir = tmp_path / "published" / "manifest-1"
    final_dir.mkdir(parents=True)
    (final_dir / "case.part1.rar").write_bytes(b"archive")
    from app.services.archive_runtime_service import ArchiveManifestRecord

    store._manifests["manifest-1"] = ArchiveManifestRecord(
        "manifest-1", "context-1", "fingerprint", {}, Path(final_dir), 0, 0,
    )
    store.cleanup_expired(now=1)
    assert final_dir.is_dir()
    assert (final_dir / "case.part1.rar").is_file()
