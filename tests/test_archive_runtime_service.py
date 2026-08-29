import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_authorization_repository import AuthorizedInputRoot  # noqa: E402
from app.repository.archive_input_repository import ArchiveInputError, build_input_inventory  # noqa: E402
from app.services.archive.archive_inventory_snapshot_service import ArchiveInventorySnapshotStore  # noqa: E402
from app.services.archive.archive_runtime_service import (  # noqa: E402
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
    assert record.input_fingerprint == ""
    summary = record.public_summary()
    assert set(summary) == {
        "archive_context_id", "file_count", "total_input_bytes", "status",
        "context_kind", "inventory_ready",
        "created_at", "expires_at",
    }
    assert summary["context_kind"] == "formal"
    assert summary["inventory_ready"] is True
    assert str(source) not in str(summary)
    assert summary["file_count"] == 1
    assert summary["total_input_bytes"] == len(b"evidence")


def test_inventory_snapshot_cache_key_does_not_expose_output_path(tmp_path):
    output = tmp_path / "output"
    key = ArchiveInventorySnapshotStore.cache_key("source-key", str(output))

    assert str(output) not in key
    assert len(key.split("\0", 1)[1]) == 64


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


def test_context_reads_recheck_authorization_boundary(tmp_path):
    store, record, source = make_context(tmp_path)
    source.rename(tmp_path / "moved-case")

    with pytest.raises(ArchiveRuntimeError) as summary_error:
        store.get_context_summary(record.context_id)
    assert summary_error.value.code == "ARCHIVE_INPUT_CHANGED"

    with pytest.raises(ArchiveRuntimeError) as snapshot_error:
        store.get_context_snapshot(record.context_id)
    assert snapshot_error.value.code == "ARCHIVE_INPUT_CHANGED"


def test_context_reuses_inventory_without_recursive_currentness_scan(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    (source / "evidence.bin").write_bytes(b"evidence")
    output = tmp_path / "output"
    store = ArchiveRuntimeStore()
    authorized = AuthorizedInputRoot(
        source.resolve(), "exact_directory_grant", "internal-test",
    )

    with patch(
        "app.services.archive.archive_runtime_service.build_input_inventory",
        wraps=build_input_inventory,
    ) as build_inventory:
        first = store.create_context(authorized, "Synthetic case", output_root=str(output))
        second = store.create_context(authorized, "Synthetic case", output_root=str(output))
        assert build_inventory.call_count == 1
        assert first.inventory is second.inventory

        (source / "new-attachment.bin").write_bytes(b"new")
        refreshed = store.create_context(
            authorized, "Synthetic case", output_root=str(output),
        )
        assert build_inventory.call_count == 1
        assert refreshed.inventory is first.inventory

    from app.repository.archive_input_repository import verify_input_inventory

    with pytest.raises(ArchiveInputError) as error:
        verify_input_inventory(first.inventory)
    assert error.value.code == "ARCHIVE_INPUT_CHANGED"


def test_concurrent_context_creation_builds_one_snapshot(tmp_path):
    source = tmp_path / "case"
    source.mkdir()
    (source / "evidence.bin").write_bytes(b"evidence")
    output = tmp_path / "output"
    store = ArchiveRuntimeStore()
    authorized = AuthorizedInputRoot(
        source.resolve(), "exact_directory_grant", "internal-test",
    )

    with patch(
        "app.services.archive.archive_runtime_service.build_input_inventory",
        wraps=build_input_inventory,
    ) as build_inventory, ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(
            lambda _: store.create_context(
                authorized, "Synthetic case", output_root=str(output),
            ),
            range(4),
        ))

    assert build_inventory.call_count == 1
    assert len({id(record.inventory) for record in records}) == 1


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
    from app.services.archive.archive_runtime_service import ArchiveManifestRecord

    store._manifests["manifest-1"] = ArchiveManifestRecord(
        "manifest-1", "context-1", "fingerprint", {}, Path(final_dir), 0, 0,
    )
    store.cleanup_expired(now=1)
    assert final_dir.is_dir()
    assert (final_dir / "case.part1.rar").is_file()
