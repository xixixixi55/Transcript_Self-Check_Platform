"""Read-only capability probes for the Demo readiness snapshot."""

from __future__ import annotations

import os
from pathlib import Path

from .winrar_discovery_repository import WinRarCapability, discover_winrar
from .runtime_paths import get_runtime_paths


def probe_archive_output(output_root: str) -> str:
    """Return a safe state without creating or writing to the output root."""
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
