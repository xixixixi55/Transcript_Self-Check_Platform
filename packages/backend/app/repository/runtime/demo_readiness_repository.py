"""演示就绪快照的只读能力探测。"""

from __future__ import annotations

import os
from pathlib import Path

from ..archive.winrar_discovery_repository import WinRarCapability, discover_winrar
from .runtime_paths import get_runtime_paths


def probe_archive_output(output_root: str) -> str:
    """返回安全状态，不创建或写入输出根目录。"""
    try:
        root = Path(output_root)
        if not root.exists() or not root.is_dir():
            return "unavailable"
        return "ready" if os.access(root, os.R_OK | os.W_OK) else "unavailable"
    except OSError:
        return "unknown"


def probe_winrar() -> WinRarCapability:
    return discover_winrar()


def probe_portable_runtime() -> str | None:
    paths = get_runtime_paths()
    if not paths.portable:
        return None
    required = (
        paths.web_root / "index.html",
        paths.templates_root / "template.docx",
        paths.node_executable,
        paths.officecli_entry,
        paths.hashmyfiles_executable,
    )
    try:
        return "ready" if all(path.is_file() for path in required) else "unavailable"
    except OSError:
        return "unknown"
