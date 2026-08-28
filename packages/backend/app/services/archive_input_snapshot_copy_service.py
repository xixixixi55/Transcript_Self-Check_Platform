"""任务绑定归档输入快照的复制和密封检查。

输入密封仅使用元数据（路径、大小和 mtime）标识；不再计算过去写入快照 Manifest 的
逐文件内容哈希，因此归档绝不会重新读取数 GB 的来源内容。
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..repository.archive_input_repository import (
    ArchiveInputError, InputFileSnapshot, InputInventory, build_input_inventory, verify_input_inventory,
)
from .archive_input_snapshot_files_service import assert_matches, assert_regular, safe_child

logger = logging.getLogger(__name__)

_DEFAULT_COPY_WORKERS = 4


def copy_worker_count() -> int:
    """并行快照复制工作进程。

    基准测试（许多小文件）：移除逐文件 fsync 后速度约为单线程的 3.6 倍；SSD 在约 8 个
    线程时达到峰值，HDD 预计在 2 至 4 个线程时出现寻道竞争。默认值 4 是 HDD/SSD 的
    折中方案；部署可以覆盖。
    """
    raw = os.environ.get("BIJI_ARCHIVE_COPY_WORKERS")
    if raw is None:
        return _DEFAULT_COPY_WORKERS
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_COPY_WORKERS


def source_evidence(inventory: InputInventory) -> tuple[InputInventory, list[dict[str, Any]]]:
    verify_input_inventory(inventory)
    current = build_input_inventory(
        inventory.source_root, output_root=inventory.output_root, check_readability=True,
    )
    if current.public_entries() != inventory.public_entries():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source inventory changed.")
    evidence: list[dict[str, Any]] = [
        {
            "relative_path": item.relative_path, "size_bytes": item.size_bytes,
            "modified_time_ns": item.modified_time_ns,
        }
        for item in current.files
    ]
    return current, evidence


def copy_inventory(
    inventory: InputInventory, temporary: Path, evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for directory in inventory.directories:
        safe_child(temporary, directory.relative_path).mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=copy_worker_count()) as pool:
        futures = [
            pool.submit(_copy_one, item, temporary)
            for item in inventory.files
        ]
        for future in futures:
            future.result()
    final_inventory = build_input_inventory(temporary, check_readability=True)
    assert_matches(final_inventory, evidence)
    return evidence


def _copy_one(item: InputFileSnapshot, temporary: Path) -> None:
    """复制单个清单文件并恢复其修改时间。"""
    try:
        destination = safe_child(temporary, item.relative_path)
        copy_file(item.absolute_path, destination)
        os.utime(destination, ns=(item.modified_time_ns, item.modified_time_ns))
    except ArchiveInputError:
        logger.error("archive input copy failed for relative=%s", item.relative_path)
        raise


def copy_file(source: Path, destination: Path) -> None:
    assert_regular(source)
    if destination.exists() or destination.is_symlink():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Snapshot destination is not empty.")
    try:
        with source.open("rb") as reader, destination.open("xb") as writer:
            for block in iter(lambda: reader.read(1024 * 1024), b""):
                writer.write(block)
            writer.flush()
        assert_regular(source)
    except OSError as error:
        logger.error("archive input copy read/write error: %s", error)
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source file cannot be copied safely.") from error


def assert_source_matches(inventory: InputInventory, evidence: list[dict[str, Any]]) -> None:
    """在 WinRAR 可能看到快照前关闭复制到密封窗口。"""
    current = build_input_inventory(
        inventory.source_root, output_root=inventory.output_root, check_readability=True,
    )
    if current.public_entries() != inventory.public_entries():
        raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source changed before sealing.")
    expected = {
        str(item["relative_path"]): (int(item["size_bytes"]), int(item["modified_time_ns"]))
        for item in evidence
    }
    for item in current.files:
        meta = expected.get(item.relative_path)
        if meta is None or item.size_bytes != meta[0] or item.modified_time_ns != meta[1]:
            raise ArchiveInputError("ARCHIVE_INPUT_CHANGED", "Source changed before sealing.")
