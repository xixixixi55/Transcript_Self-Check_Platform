"""分别解析不可变程序资源和逐用户应用数据。"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class RuntimePathError(RuntimeError):
    """便携运行时无法建立安全根目录时引发。"""


def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        try:
            right.relative_to(left)
            return True
        except ValueError:
            return False


@dataclass(frozen=True)
class RuntimePaths:
    resource_root: Path
    app_data_root: Path
    data_root: Path
    workspace_root: Path
    upload_root: Path
    output_root: Path
    log_root: Path
    backup_root: Path
    templates_root: Path
    web_root: Path
    node_executable: Path
    officecli_entry: Path
    hashmyfiles_executable: Path
    portable: bool

    def ensure_user_directories(self) -> None:
        for path in (
            self.data_root, self.upload_root, self.output_root,
            self.log_root, self.backup_root,
        ):
            path.mkdir(parents=True, exist_ok=True)


def resolve_runtime_paths(
    env: Mapping[str, str] | None = None,
    *,
    module_path: Path | None = None,
    executable_path: Path | None = None,
    platform_name: str | None = None,
) -> RuntimePaths:
    values = os.environ if env is None else env
    platform = os.name if platform_name is None else platform_name
    portable = values.get("BIJI_PORTABLE_MODE", "").strip() == "1"
    source_module = module_path or Path(__file__).resolve()
    executable = executable_path or Path(sys.executable).resolve()

    resource_override = values.get("BIJI_RESOURCE_ROOT", "").strip()
    if resource_override:
        resource_root = Path(resource_override).expanduser().resolve()
    elif portable:
        resource_root = executable.parent.parent.parent
    else:
        resource_root = source_module.parents[4]

    app_override = values.get("BIJI_APP_DATA_ROOT", "").strip()
    if app_override:
        app_data_root = Path(app_override).expanduser().resolve()
    elif platform == "nt":
        local_app_data = values.get("LOCALAPPDATA", "").strip()
        if not local_app_data:
            if portable:
                raise RuntimePathError("LOCALAPPDATA_UNAVAILABLE")
            app_data_root = Path(tempfile.gettempdir()) / "文枢"
        else:
            app_data_root = Path(local_app_data).resolve() / "文枢"
    else:
        app_data_root = Path(tempfile.gettempdir()) / "文枢"

    if portable and _paths_overlap(resource_root, app_data_root):
        raise RuntimePathError("PROGRAM_DATA_ROOTS_OVERLAP")

    workspace_root = app_data_root / "workspace"
    return RuntimePaths(
        resource_root=resource_root,
        app_data_root=app_data_root,
        data_root=app_data_root / "data",
        workspace_root=workspace_root,
        upload_root=workspace_root / "uploads",
        output_root=workspace_root / "output",
        log_root=app_data_root / "logs",
        backup_root=app_data_root / "backups",
        templates_root=resource_root / "resources" / "word_templates" if portable
        else resource_root / "word_templates",
        web_root=resource_root / "web",
        node_executable=resource_root / "runtime" / "node" / "node.exe",
        officecli_entry=resource_root / "tools" / "officecli" / "officecli.js",
        hashmyfiles_executable=(
            resource_root / "tools" / "hashmyfiles" / "HashMyFiles.exe"
            if portable else resource_root / "hashmyfiles" / "HashMyFiles.exe"
        ),
        portable=portable,
    )


def get_runtime_paths() -> RuntimePaths:
    return resolve_runtime_paths()


__all__ = ["RuntimePathError", "RuntimePaths", "get_runtime_paths", "resolve_runtime_paths"]
