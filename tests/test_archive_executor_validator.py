import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_input_repository import build_input_inventory  # noqa: E402
from app.repository.archive_validator_repository import validate_archive_parts  # noqa: E402
from app.repository.winrar_discovery_repository import WinRarCapability  # noqa: E402
from app.repository.winrar_executor_repository import (  # noqa: E402
    ArchiveExecutionError,
    WinRarExecutor,
)


def capability() -> WinRarCapability:
    return WinRarCapability(True, "fake-winrar", "WinRAR.exe", "6.24", True)


def make_process_runner(part_count=1, payload=b"part"):
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        archive_path = Path(next(item for item in args if item.endswith(".rar") and not item.startswith("@")))
        for index in range(1, part_count + 1):
            archive_path.with_name(f"{archive_path.stem}.part{index}.rar").write_bytes(payload)
        return subprocess.CompletedProcess(args, 0, "", "")

    return runner, calls


def test_executor_uses_argument_array_and_dedicated_staging(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_text("合成", encoding="utf-8")
    inventory = build_input_inventory(source)
    runner, calls = make_process_runner()
    executor = WinRarExecutor(tmp_path / "staging", process_runner=runner)
    plan = SimpleNamespace(plan_id="plan-1", archive_base_name="合成案件", volume_size_bytes=4)
    result = executor.execute(plan, inventory.files, inventory.source_root, capability())
    args, kwargs = calls[0]
    assert kwargs["shell"] is False
    assert kwargs["cwd"] == str(source.resolve().parent)
    assert "-v4b" in args
    assert "-ep" not in " ".join(args)
    assert args[-1] == source.name
    assert result.staging_dir.is_dir()
    assert not (result.staging_dir / "source-list.txt").exists()


def test_executor_keeps_single_volume_base_name(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_text("synthetic", encoding="utf-8")
    inventory = build_input_inventory(source)

    def runner(args, **kwargs):
        archive_path = Path(next(item for item in args if item.endswith(".rar") and not item.startswith("@")))
        archive_path.write_bytes(b"single volume")
        return subprocess.CompletedProcess(args, 0, "", "")

    executor = WinRarExecutor(tmp_path / "staging", process_runner=runner)
    plan = SimpleNamespace(plan_id="plan-single", archive_base_name="synthetic", volume_size_bytes=4)
    result = executor.execute(plan, inventory.files, inventory.source_root, capability())
    assert (result.staging_dir / "synthetic.rar").is_file()
    assert not (result.staging_dir / "synthetic.part1.rar").exists()


def test_executor_does_not_rename_when_staging_contains_extra_rar(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_text("synthetic", encoding="utf-8")
    inventory = build_input_inventory(source)

    def runner(args, **kwargs):
        archive_path = Path(next(item for item in args if item.endswith(".rar") and not item.startswith("@")))
        archive_path.write_bytes(b"single volume")
        archive_path.with_name("unexpected.part2.rar").write_bytes(b"unexpected")
        return subprocess.CompletedProcess(args, 0, "", "")

    executor = WinRarExecutor(tmp_path / "staging", process_runner=runner)
    plan = SimpleNamespace(plan_id="plan-extra", archive_base_name="synthetic", volume_size_bytes=20)
    result = executor.execute(plan, inventory.files, inventory.source_root, capability())
    assert (result.staging_dir / "synthetic.rar").is_file()
    assert not (result.staging_dir / "synthetic.part1.rar").exists()


def test_executor_nonzero_exit_cleans_staging(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_text("x", encoding="utf-8")

    def runner(args, **kwargs):
        return subprocess.CompletedProcess(args, 7, "", "sensitive path")

    executor = WinRarExecutor(tmp_path / "staging", process_runner=runner)
    inventory = build_input_inventory(source)
    plan = SimpleNamespace(plan_id="plan-2", archive_base_name="案件", volume_size_bytes=4)
    result = executor.execute(plan, inventory.files, inventory.source_root, capability())
    assert result.returncode == 7
    assert not result.staging_dir.exists()
    assert "sensitive" not in result.safe_output


def test_executor_timeout_is_safe_and_cleans_staging(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.txt").write_text("x", encoding="utf-8")

    def runner(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 1)

    executor = WinRarExecutor(tmp_path / "staging", process_runner=runner)
    inventory = build_input_inventory(source)
    plan = SimpleNamespace(plan_id="plan-3", archive_base_name="案件", volume_size_bytes=4)
    with pytest.raises(ArchiveExecutionError) as error:
        executor.execute(plan, inventory.files, inventory.source_root, capability())
    assert error.value.code == "ARCHIVE_EXECUTION_TIMEOUT"
    assert list((tmp_path / "staging").glob("archive-*")) == []


def validator_plan(base="案件", capacity=4, max_parts=2):
    return SimpleNamespace(archive_base_name=base, volume_size_bytes=capacity, max_part_count=max_parts)


def integrity_ok(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, "", "")


def test_validator_accepts_numeric_continuous_parts_and_integrity_test(tmp_path):
    (tmp_path / "案件.part1.rar").write_bytes(b"1")
    (tmp_path / "案件.part2.rar").write_bytes(b"22")
    result = validate_archive_parts(tmp_path, validator_plan(), capability(), integrity_runner=integrity_ok)
    assert result.valid
    assert [part.part_number for part in result.parts] == [1, 2]


def test_validator_accepts_single_base_name(tmp_path):
    (tmp_path / "案件.rar").write_bytes(b"one")
    result = validate_archive_parts(
        tmp_path, validator_plan(), capability(), integrity_runner=integrity_ok,
    )
    assert result.valid
    assert result.parts[0].filename == "案件.rar"


@pytest.mark.parametrize("names", [
    ["案件.part2.rar"],
    ["案件.part1.rar", "案件.part3.rar"],
    ["案件.part1.rar", "案件.part01.rar"],
    ["案件.part1.rar", "其他.part2.rar"],
    ["案件.part1.rar", "案件.r99"],
])
def test_validator_rejects_missing_duplicate_or_extra_parts(tmp_path, names):
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    result = validate_archive_parts(tmp_path, validator_plan(), capability(), integrity_runner=integrity_ok)
    assert not result.valid
    assert result.diagnostic_code == "ARCHIVE_PARTS_INVALID"


def test_validator_allows_downward_size_but_rejects_zero_or_over_capacity(tmp_path):
    (tmp_path / "案件.part1.rar").write_bytes(b"x")
    result = validate_archive_parts(tmp_path, validator_plan(capacity=1), capability(), integrity_runner=integrity_ok)
    assert result.valid
    (tmp_path / "案件.part1.rar").write_bytes(b"")
    assert not validate_archive_parts(tmp_path, validator_plan(), capability(), integrity_runner=integrity_ok).valid
    (tmp_path / "案件.part1.rar").write_bytes(b"12345")
    assert not validate_archive_parts(tmp_path, validator_plan(), capability(), integrity_runner=integrity_ok).valid


def test_validator_integrity_failure_is_not_success(tmp_path):
    (tmp_path / "案件.part1.rar").write_bytes(b"x")

    def integrity_fail(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "")

    result = validate_archive_parts(tmp_path, validator_plan(), capability(), integrity_runner=integrity_fail)
    assert not result.valid
    assert result.diagnostic_code == "ARCHIVE_PARTS_INVALID"
