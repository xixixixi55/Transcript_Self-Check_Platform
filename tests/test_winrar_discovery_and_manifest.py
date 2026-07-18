import hashlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.archive_validator_repository import validate_archive_parts  # noqa: E402
from app.repository.winrar_discovery_repository import (  # noqa: E402
    discover_winrar,
)
from app.services.archive_manifest_service import (  # noqa: E402
    assemble_archive_manifest,
    validate_published_manifest,
)


def probe_ok(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, "WinRAR 6.24\n-v<bytes>b", "")


def test_discovery_priority_config_then_environment_then_path(tmp_path):
    configured = tmp_path / "configured.exe"
    configured.write_bytes(b"x")
    env_path = tmp_path / "env.exe"
    env_path.write_bytes(b"x")
    calls = []

    def path_lookup(name):
        calls.append(name)
        return str(tmp_path / "path.exe")

    capability = discover_winrar(
        str(configured), env={"BIJI_WINRAR_PATH": str(env_path)},
        path_lookup=path_lookup, probe_runner=probe_ok,
    )
    assert capability.available
    assert capability.executable_path == str(configured)
    assert capability.public_dict()["executable_name"] == "configured.exe"
    assert str(tmp_path) not in str(capability.public_dict())
    assert calls == []


def test_discovery_uses_environment_then_path_and_rejects_directory(tmp_path):
    env_dir = tmp_path / "env-dir"
    env_dir.mkdir()
    path_file = tmp_path / "path.exe"
    path_file.write_bytes(b"x")
    capability = discover_winrar(
        str(env_dir), env={"BIJI_WINRAR_PATH": str(tmp_path / "missing.exe")},
        path_lookup=lambda name: str(path_file), probe_runner=probe_ok,
    )
    assert capability.available
    assert capability.executable_path == str(path_file)


def test_discovery_no_executable_or_failed_probe_is_unavailable(tmp_path):
    bad = tmp_path / "bad.exe"
    bad.write_bytes(b"x")

    def probe_fail(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "C:\\sensitive\\path", "error")

    capability = discover_winrar(str(bad), env={}, path_lookup=lambda name: None, probe_runner=probe_fail)
    assert not capability.available
    assert capability.diagnostic_code == "WINRAR_UNAVAILABLE"
    assert capability.public_dict()["executable_name"] is None


def test_discovery_accepts_rar_volume_help_syntax(tmp_path):
    candidate = tmp_path / "rar.exe"
    candidate.write_bytes(b"synthetic")

    def probe_rar(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "RAR 5.90\nv<size>[k,b]", "")

    capability = discover_winrar(
        str(candidate), env={}, path_lookup=lambda name: None, probe_runner=probe_rar
    )
    assert capability.available
    assert capability.supports_rar_volumes


def test_discovery_winrar_config_prefers_console_sibling_without_gui_probe(tmp_path):
    gui = tmp_path / "WinRAR.exe"
    console = tmp_path / "rar.exe"
    gui.write_bytes(b"gui")
    console.write_bytes(b"console")
    calls = []

    def probe_rar(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "RAR 5.90\nv<size>[k,b]", "")

    capability = discover_winrar(str(gui), env={}, path_lookup=lambda name: None, probe_runner=probe_rar)
    assert capability.executable_name == "rar.exe"
    assert all(args[0].casefold().endswith("rar.exe") for args in calls)
    assert not any("WinRAR.exe".casefold() in str(args[0]).casefold() for args in calls)


def test_manifest_uses_actual_numeric_order_streaming_md5_and_disc_date(tmp_path):
    first = tmp_path / "案件.part1.rar"
    second = tmp_path / "案件.part2.rar"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    plan = SimpleNamespace(
        plan_id="plan", archive_base_name="案件", volume_size_bytes=10,
        volume_tier_gb=4, max_part_count=2, total_input_bytes=8,
        first_disc_number="GP20260718-09", expected_disc_numbers=("GP20260718-09", "GP20260718-10"),
    )
    capability = SimpleNamespace(available=True, executable_path="fake", executable_name="WinRAR.exe", version="6.24", supports_rar_volumes=True,
                                 public_dict=lambda: {"available": True, "executable_name": "WinRAR.exe", "version": "6.24", "supports_rar_volumes": True})
    validation = validate_archive_parts(tmp_path, plan, capability, integrity_runner=probe_ok)
    manifest, paths = assemble_archive_manifest(plan, validation, capability, retry_count=0)
    assert [part["part_number"] for part in manifest["parts"]] == [1, 2]
    assert manifest["parts"][0]["filename"] == "案件.part1.rar"
    assert manifest["parts"][0]["md5"] == hashlib.md5(b"first").hexdigest()
    assert manifest["parts"][0]["disc_date"] == "2026-07-18"
    assert all(Path(name).name == name for name in paths)


def test_manifest_uses_actual_part_count_when_less_than_expected(tmp_path):
    part = tmp_path / "案件.part1.rar"
    part.write_bytes(b"one")
    plan = SimpleNamespace(
        plan_id="plan", archive_base_name="案件", volume_size_bytes=10,
        volume_tier_gb=4, max_part_count=2, total_input_bytes=20,
        first_disc_number="GP20260718-01", expected_disc_numbers=("GP20260718-01", "GP20260718-02"),
    )
    capability = SimpleNamespace(available=True, executable_path="fake", executable_name="WinRAR.exe", version="6.24", supports_rar_volumes=True,
                                 public_dict=lambda: {"available": True, "executable_name": "WinRAR.exe", "version": "6.24", "supports_rar_volumes": True})
    validation = validate_archive_parts(tmp_path, plan, capability, integrity_runner=probe_ok)
    manifest, _ = assemble_archive_manifest(plan, validation, capability, retry_count=0)
    assert len(manifest["parts"]) == 1
    assert manifest["parts"][0]["disc_number"] == "GP20260718-01"


def test_published_manifest_detects_modified_part(tmp_path):
    part = tmp_path / "案件.part1.rar"
    part.write_bytes(b"original")
    digest = hashlib.md5(b"original").hexdigest()
    record = SimpleNamespace(
        final_dir=tmp_path,
        public_manifest={
            "archive_base_name": "案件", "volume_size_bytes": 10, "max_part_count": 2,
            "parts": [{"part_number": 1, "filename": part.name, "size_bytes": 8, "md5": digest}],
            "actual_archive_bytes": 8,
        },
    )
    assert validate_published_manifest(record)
    part.write_bytes(b"changed!")
    assert not validate_published_manifest(record)
