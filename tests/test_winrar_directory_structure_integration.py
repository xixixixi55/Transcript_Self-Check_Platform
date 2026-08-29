"""目录保留的小型真实 WinRAR 契约测试。"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive.archive_input_repository import build_input_inventory  # noqa: E402
from app.repository.archive.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.archive.winrar_executor_repository import WinRarExecutor  # noqa: E402


WINRAR = Path(r"C:\Program Files\WinRAR\WinRAR.exe")
RAR_CLI = Path(r"C:\Program Files\WinRAR\Rar.exe")


def _hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


@pytest.mark.skipif(
    not WINRAR.is_file() or not RAR_CLI.is_file(),
    reason="real WinRAR CLI is not installed",
)
def test_real_winrar_preserves_root_nested_names_empty_dirs_and_file_content(tmp_path):
    source = tmp_path / "合成 案件_20260722_html"
    nested = source / "中文目录" / "带 空格" / "third"
    nested.mkdir(parents=True)
    (source / "业务空目录").mkdir()
    (source / "root.json").write_text('{"synthetic":true}', encoding="utf-8")
    (nested / "same.txt").write_text("nested", encoding="utf-8")
    other = source / "other"
    other.mkdir()
    (other / "same.txt").write_text("other", encoding="utf-8")

    inventory = build_input_inventory(source)
    capability = WinRarCapability(
        True, str(WINRAR), "WinRAR.exe", "installed", True,
    )
    plan = SimpleNamespace(
        plan_id="synthetic-directory-tree",
        archive_base_name="合成案件",
        volume_size_bytes=4_000_000_000,
    )
    result = WinRarExecutor(tmp_path / "staging").execute(
        plan, inventory.files, inventory.source_root, capability,
    )
    try:
        archive = result.staging_dir / "合成案件.rar"
        assert archive.is_file()
        listing = subprocess.run(
            [str(RAR_CLI), "lb", str(archive)],
            capture_output=True, text=True, check=True,
        ).stdout.replace("\\", "/")
        entries = [line.strip().rstrip("/") for line in listing.splitlines() if line.strip()]
        assert f"{source.name}/root.json" in entries
        assert f"{source.name}/中文目录/带 空格/third/same.txt" in entries
        assert f"{source.name}/other/same.txt" in entries
        assert {entry.split("/", 1)[0] for entry in entries} == {source.name}
        assert all(entry == source.name or entry.startswith(f"{source.name}/") for entry in entries)
        assert not any(
            marker in entry.casefold()
            for entry in entries
            for marker in (".i/", ".inputs/", ".t/", "snapshot-", ".copying")
        )
        assert str(tmp_path).replace("\\", "/") not in listing
        assert "archive-" not in listing

        extracted = tmp_path / "extracted"
        extracted.mkdir()
        subprocess.run(
            [str(RAR_CLI), "x", "-y", "-inul", str(archive), str(extracted) + os.sep],
            check=True,
        )
        assert {path.name for path in extracted.iterdir()} == {source.name}
        restored = extracted / source.name
        assert (restored / "业务空目录").is_dir()
        assert _hashes(restored) == _hashes(source)
        assert {
            path.relative_to(restored).as_posix()
            for path in restored.rglob("*") if path.is_dir()
        } == {
            path.relative_to(source).as_posix()
            for path in source.rglob("*") if path.is_dir()
        }
    finally:
        shutil.rmtree(result.staging_dir, ignore_errors=True)
