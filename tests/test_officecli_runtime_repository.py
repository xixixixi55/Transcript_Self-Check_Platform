"""私有 Node/OfficeCLI 命令边界的 SYNTHETIC 测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.runtime.officecli_runtime_repository import (  # noqa: E402
    OfficeCliRuntimeError,
    resolve_officecli_command,
    run_officecli,
)
from app.repository.runtime.runtime_paths import resolve_runtime_paths  # noqa: E402


def portable_paths(tmp_path: Path):
    return resolve_runtime_paths({
        "BIJI_PORTABLE_MODE": "1",
        "BIJI_RESOURCE_ROOT": str(tmp_path / "程序 空格"),
        "BIJI_APP_DATA_ROOT": str(tmp_path / "用户 数据"),
    }, platform_name="nt")


def test_portable_command_uses_private_node_and_entry(tmp_path: Path) -> None:
    paths = portable_paths(tmp_path)
    paths.node_executable.parent.mkdir(parents=True)
    paths.node_executable.write_bytes(b"SYNTHETIC/NODE")
    paths.officecli_entry.parent.mkdir(parents=True)
    paths.officecli_entry.write_text("// SYNTHETIC/OFFICECLI", encoding="utf-8")
    command = resolve_officecli_command(
        paths, env={"PATH": ""}, path_lookup=lambda _name: (_ for _ in ()).throw(AssertionError("PATH lookup")),
    )
    assert command.prefix == (str(paths.node_executable), str(paths.officecli_entry))
    assert command.arguments(("create", "含 空格.docx"))[-2:] == ["create", "含 空格.docx"]


def test_portable_command_never_falls_back_to_global_path(tmp_path: Path) -> None:
    paths = portable_paths(tmp_path)
    with pytest.raises(OfficeCliRuntimeError, match="OFFICECLI_RUNTIME_UNAVAILABLE"):
        resolve_officecli_command(
            paths,
            env={"PATH": "SYNTHETIC"},
            path_lookup=lambda _name: (_ for _ in ()).throw(AssertionError("PATH lookup")),
        )


def test_portable_command_ignores_external_runtime_overrides(tmp_path: Path) -> None:
    paths = portable_paths(tmp_path)
    paths.node_executable.parent.mkdir(parents=True)
    paths.node_executable.write_bytes(b"SYNTHETIC/NODE")
    paths.officecli_entry.parent.mkdir(parents=True)
    paths.officecli_entry.write_text("// SYNTHETIC/OFFICECLI", encoding="utf-8")
    command = resolve_officecli_command(paths, env={
        "BIJI_NODE_PATH": str(tmp_path / "SYNTHETIC-untrusted-node.exe"),
        "BIJI_OFFICECLI_ENTRY": str(tmp_path / "SYNTHETIC-untrusted-officecli.js"),
    })
    assert command.prefix == (str(paths.node_executable), str(paths.officecli_entry))


def test_development_command_can_use_global_officecli(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(
        {"LOCALAPPDATA": str(tmp_path / "local")},
        module_path=tmp_path / "repo" / "packages" / "backend" / "app" / "repository" / "runtime_paths.py",
        platform_name="nt",
    )
    command = resolve_officecli_command(
        paths, env={"PATH": "SYNTHETIC"}, path_lookup=lambda name: "C:/tools/officecli.cmd" if name == "officecli" else None,
    )
    assert command.prefix == ("C:/tools/officecli.cmd",)


def test_run_officecli_passes_argument_array_without_shell(tmp_path: Path) -> None:
    paths = portable_paths(tmp_path)
    paths.node_executable.parent.mkdir(parents=True)
    paths.node_executable.write_bytes(b"SYNTHETIC/NODE")
    paths.officecli_entry.parent.mkdir(parents=True)
    paths.officecli_entry.write_text("// SYNTHETIC/OFFICECLI", encoding="utf-8")
    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, "SYNTHETIC/OK", "")

    result = run_officecli(
        "create", str(tmp_path / "中文 空格.docx"), paths=paths,
        env={"SystemRoot": r"C:\Windows", "PATH": ""}, runner=runner,
    )
    assert result.returncode == 0
    assert captured["command"] == [
        str(paths.node_executable), str(paths.officecli_entry),
        "create", str(tmp_path / "中文 空格.docx"),
    ]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["env"]["OFFICECLI_NO_AUTO_RESIDENT"] == "1"


def test_development_run_keeps_officecli_resident_default(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(
        {"LOCALAPPDATA": str(tmp_path / "local")},
        module_path=tmp_path / "repo" / "packages" / "backend" / "app" / "repository" / "runtime_paths.py",
        platform_name="nt",
    )
    captured = {}

    def runner(command, **kwargs):
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, "SYNTHETIC/OK", "")

    run_officecli(
        "--version", paths=paths,
        env={"PATH": "SYNTHETIC"}, runner=runner,
    )
    assert "OFFICECLI_NO_AUTO_RESIDENT" not in captured["env"]
