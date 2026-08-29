"""定向测试：归档输入快照并行拷贝与拷贝工作线程配置。"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_input_repository import (  # noqa: E402
    build_input_inventory,
)
from app.services.archive.archive_input_snapshot_copy_service import (  # noqa: E402
    copy_inventory,
    copy_worker_count,
    source_evidence,
)


def test_copy_worker_count_defaults_to_four(monkeypatch):
    monkeypatch.delenv("BIJI_ARCHIVE_COPY_WORKERS", raising=False)
    assert copy_worker_count() == 4


def test_copy_worker_count_honors_override_and_sanitizes(monkeypatch):
    monkeypatch.setenv("BIJI_ARCHIVE_COPY_WORKERS", "8")
    assert copy_worker_count() == 8
    monkeypatch.setenv("BIJI_ARCHIVE_COPY_WORKERS", "0")
    assert copy_worker_count() == 1
    monkeypatch.setenv("BIJI_ARCHIVE_COPY_WORKERS", "not-a-number")
    assert copy_worker_count() == 4


def test_copy_inventory_parallel_preserves_content_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "SYNTHETIC-SOURCE-COPY"
    source.mkdir()
    for group in range(8):
        directory = source / "data" / f"g{group}"
        directory.mkdir(parents=True)
        for index in range(12):
            (directory / f"f{index:03d}.bin").write_bytes(
                b"SYNTHETIC/%02d/%03d" % (group, index),
            )
    output = tmp_path / "SYNTHETIC-OUTPUT-COPY"
    inventory = build_input_inventory(source, output_root=output)

    current, evidence = source_evidence(inventory)
    temporary = output / "compressed" / ".inputs" / ".snapshot-test.copying"
    temporary.mkdir(parents=True)
    copy_inventory(current, temporary, evidence)

    copied = build_input_inventory(temporary, check_readability=True)
    assert len(copied.files) == 96
    assert {item.relative_path for item in copied.files} == {
        item.relative_path for item in current.files
    }
    for item in current.files:
        payload = (temporary / item.relative_path).read_bytes()
        assert payload == (source / item.relative_path).read_bytes()
        restored = (temporary / item.relative_path).stat().st_mtime_ns
        assert restored == item.modified_time_ns
