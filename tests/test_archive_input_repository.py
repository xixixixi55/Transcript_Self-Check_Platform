import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_input_repository import (  # noqa: E402
    ArchiveInputError,
    build_input_inventory,
    verify_input_inventory,
)


def test_inventory_sums_multiple_files_and_keeps_stable_relative_paths(tmp_path):
    (tmp_path / "data" / "nested").mkdir(parents=True)
    (tmp_path / "data" / "b.json").write_text("12", encoding="utf-8")
    (tmp_path / "data" / "nested" / "a.json").write_text("123", encoding="utf-8")
    inventory = build_input_inventory(tmp_path)
    assert [item.relative_path for item in inventory.files] == [
        "data/b.json", "data/nested/a.json"
    ]
    assert inventory.total_input_bytes == 5
    assert all("absolute" not in item for item in inventory.public_entries())


def test_inventory_excludes_only_the_platform_output_subtree(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "input.json").write_text("x", encoding="utf-8")
    output = tmp_path / "output"
    (output / "compressed").mkdir(parents=True)
    (output / "compressed" / "old.part1.rar").write_bytes(b"old")
    (tmp_path / "old.docx").write_bytes(b"docx")
    inventory = build_input_inventory(tmp_path, output_root=output)
    assert [item.relative_path for item in inventory.files] == [
        "data/input.json", "old.docx",
    ]


def test_inventory_preserves_nested_and_empty_directories(tmp_path):
    nested = tmp_path / "中文目录" / "带 空格" / "third"
    nested.mkdir(parents=True)
    (tmp_path / "empty").mkdir()
    (nested / "same.txt").write_text("one", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    (other / "same.txt").write_text("two", encoding="utf-8")
    inventory = build_input_inventory(tmp_path)
    assert [item.relative_path for item in inventory.directories] == [
        "empty", "other", "中文目录", "中文目录/带 空格", "中文目录/带 空格/third",
    ]
    assert [item.relative_path for item in inventory.files] == [
        "other/same.txt", "中文目录/带 空格/third/same.txt",
    ]


def test_inventory_rejects_duplicate_case_insensitive_relative_paths(tmp_path):
    (tmp_path / "same.txt").write_text("a", encoding="utf-8")
    (tmp_path / "SAME.TXT").write_text("b", encoding="utf-8")
    if len(list(tmp_path.iterdir())) < 2:
        pytest.skip("当前 Windows 文件系统按大小写折叠文件名，无法构造重复相对路径")
    with pytest.raises(ArchiveInputError, match="重复"):
        build_input_inventory(tmp_path)


def test_inventory_detects_file_change_before_execution(tmp_path):
    source = tmp_path / "input.bin"
    source.write_bytes(b"before")
    inventory = build_input_inventory(tmp_path)
    source.write_bytes(b"after!!")
    with pytest.raises(ArchiveInputError, match="变化") as error:
        verify_input_inventory(inventory)
    assert error.value.code == "ARCHIVE_INPUT_CHANGED"


def test_empty_inventory_is_explicit_and_does_not_create_fake_entry(tmp_path):
    inventory = build_input_inventory(tmp_path)
    assert inventory.files == ()
    assert inventory.public_entries() == []


def test_symlink_is_rejected_when_platform_allows_creation(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("x", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("test environment does not allow symlink creation")
    with pytest.raises(ArchiveInputError, match="链接"):
        build_input_inventory(tmp_path)


def test_injected_special_path_boundary_rejects_synthetic_link_or_reparse(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    synthetic = source / "synthetic-link.bin"
    synthetic.write_bytes(b"x")
    from app.repository.archive import archive_input_repository as repository

    monkeypatch.setattr(
        repository,
        "_is_unsafe_directory_entry",
        lambda entry, _info: entry.path == str(synthetic),
    )
    with pytest.raises(ArchiveInputError) as error:
        build_input_inventory(source)
    assert error.value.code == "ARCHIVE_INPUT_LINK_NOT_ALLOWED"


def test_inventory_stops_when_preparation_is_cancelled(tmp_path):
    source = tmp_path / "SYNTHETIC-CANCEL-INVENTORY"
    source.mkdir()
    for index in range(20):
        (source / f"SYNTHETIC-{index:02d}.bin").write_bytes(b"TEST")
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 5

    with pytest.raises(ArchiveInputError) as error:
        build_input_inventory(
            source,
            check_readability=False,
            cancellation_check=cancelled,
        )

    assert error.value.code == "ARCHIVE_EXECUTION_CANCELLED"
    assert checks == 5
