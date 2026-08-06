"""Benchmark archive snapshot copy parallelism on the current disk.

Usage: python scripts/benchmark_snapshot_copy.py [files] [file_bytes]

Creates a synthetic report-like tree (many small files + nested dirs), then
copies it with 1/2/4/8/16 worker threads, with and without per-file fsync.
Run it on BOTH a mechanical HDD and an SSD to decide the copy parallelism.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHUNK = 1024 * 1024


def copy_one(src: Path, dst: Path, fsync: bool) -> None:
    with src.open("rb") as reader, dst.open("xb") as writer:
        while True:
            block = reader.read(CHUNK)
            if not block:
                break
            writer.write(block)
        writer.flush()
        if fsync:
            os.fsync(writer.fileno())


def build_tree(root: Path, file_count: int, file_bytes: int) -> None:
    (root / "data" / "nested").mkdir(parents=True)
    for i in range(file_count):
        directory = root / "data" / f"dir{i % 20}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"f{i:06d}.bin").write_bytes(b"x" * file_bytes)


def run_parallel(src: Path, out: Path, threads: int, fsync: bool) -> float:
    files = [p for p in src.rglob("*") if p.is_file()]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = []
        for source in files:
            relative = source.relative_to(src)
            destination = out / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            futures.append(pool.submit(copy_one, source, destination, fsync))
        for future in futures:
            future.result()
    return time.perf_counter() - started


def main() -> None:
    file_count = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    file_bytes = int(sys.argv[2]) if len(sys.argv) > 2 else 8 * 1024
    base = Path(tempfile.gettempdir()) / "biji-copy-bench"
    source = base / "src"
    if source.exists():
        shutil.rmtree(source)
    build_tree(source, file_count, file_bytes)
    total_bytes = file_count * file_bytes
    print(f"files={file_count}  bytes={total_bytes / 1024 / 1024:.1f}MB")
    for fsync in (True, False):
        print(f"fsync={fsync}")
        for threads in (1, 2, 4, 8, 16):
            out = base / f"out-{int(fsync)}-{threads}"
            if out.exists():
                shutil.rmtree(out)
            elapsed = run_parallel(source, out, threads, fsync)
            mbps = total_bytes / 1024 / 1024 / elapsed
            print(f"  threads={threads:2d}  elapsed={elapsed:6.2f}s  {mbps:7.1f} MB/s")
            shutil.rmtree(out)
    shutil.rmtree(base)


if __name__ == "__main__":
    main()
