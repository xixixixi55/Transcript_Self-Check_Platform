"""便携资源与每用户数据分离的 SYNTHETIC 测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.runtime_paths import (  # noqa: E402
    RuntimePathError,
    resolve_runtime_paths,
)


def test_source_layout_uses_repository_resources_and_local_app_data(tmp_path: Path) -> None:
    module = tmp_path / "repo" / "packages" / "backend" / "app" / "repository" / "runtime_paths.py"
    paths = resolve_runtime_paths(
        {"LOCALAPPDATA": str(tmp_path / "local")},
        module_path=module,
        platform_name="nt",
    )
    assert paths.resource_root == tmp_path / "repo"
    assert paths.templates_root == tmp_path / "repo" / "word_templates"
    assert paths.data_root == tmp_path / "local" / "文枢" / "data"
    assert paths.output_root == tmp_path / "local" / "文枢" / "workspace" / "output"
    assert paths.resource_root not in paths.data_root.parents
    assert paths.portable is False


def test_portable_layout_uses_explicit_roots_and_never_program_data(tmp_path: Path) -> None:
    program = tmp_path / "程序 空格" / "文枢-vTEST"
    app_data = tmp_path / "用户 数据"
    paths = resolve_runtime_paths({
        "BIJI_PORTABLE_MODE": "1",
        "BIJI_RESOURCE_ROOT": str(program),
        "BIJI_APP_DATA_ROOT": str(app_data),
    }, platform_name="nt")
    assert paths.resource_root == program.resolve()
    assert paths.templates_root == program.resolve() / "resources" / "word_templates"
    assert paths.node_executable == program.resolve() / "runtime" / "node" / "node.exe"
    assert paths.officecli_entry == program.resolve() / "tools" / "officecli" / "officecli.js"
    assert paths.hashmyfiles_executable == program.resolve() / "tools" / "hashmyfiles" / "HashMyFiles.exe"
    assert paths.app_data_root == app_data.resolve()
    assert program.resolve() not in paths.output_root.parents


def test_portable_layout_derives_root_from_backend_executable(tmp_path: Path) -> None:
    executable = tmp_path / "文枢" / "runtime" / "backend" / "backend.exe"
    paths = resolve_runtime_paths(
        {"BIJI_PORTABLE_MODE": "1", "LOCALAPPDATA": str(tmp_path / "local")},
        executable_path=executable,
        platform_name="nt",
    )
    assert paths.resource_root == tmp_path / "文枢"


def test_portable_windows_requires_local_app_data_without_override(tmp_path: Path) -> None:
    with pytest.raises(RuntimePathError, match="LOCALAPPDATA_UNAVAILABLE"):
        resolve_runtime_paths(
            {"BIJI_PORTABLE_MODE": "1"},
            executable_path=tmp_path / "runtime" / "backend" / "backend.exe",
            platform_name="nt",
        )


def test_ensure_user_directories_only_writes_under_data_root(tmp_path: Path) -> None:
    program = tmp_path / "program"
    paths = resolve_runtime_paths({
        "BIJI_PORTABLE_MODE": "1",
        "BIJI_RESOURCE_ROOT": str(program),
        "BIJI_APP_DATA_ROOT": str(tmp_path / "local"),
    }, platform_name="nt")
    paths.ensure_user_directories()
    assert paths.data_root.is_dir()
    assert paths.upload_root.is_dir()
    assert paths.output_root.is_dir()
    assert paths.log_root.is_dir()
    assert paths.backup_root.is_dir()
    assert not program.exists()


@pytest.mark.parametrize("data_relative", [".", "data", ".."])
def test_portable_rejects_overlapping_program_and_data_roots(
    tmp_path: Path, data_relative: str,
) -> None:
    program = tmp_path / "program-parent" / "program"
    app_data = (program / data_relative).resolve()
    with pytest.raises(RuntimePathError, match="PROGRAM_DATA_ROOTS_OVERLAP"):
        resolve_runtime_paths({
            "BIJI_PORTABLE_MODE": "1",
            "BIJI_RESOURCE_ROOT": str(program),
            "BIJI_APP_DATA_ROOT": str(app_data),
        }, platform_name="nt")
