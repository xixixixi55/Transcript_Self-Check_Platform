"""Application settings projected once from the process runtime roots."""
from pathlib import Path

from .repository.runtime_paths import get_runtime_paths

RUNTIME_PATHS = get_runtime_paths()
if RUNTIME_PATHS.portable:
    UPLOAD_BASE = str(RUNTIME_PATHS.upload_root)
    OUTPUT_BASE = str(RUNTIME_PATHS.output_root)
else:
    # Preserve the source/development layout.  Only the packaged runtime moves
    # mutable state out of the program directory and into LOCALAPPDATA.
    _SOURCE_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
    UPLOAD_BASE = str(_SOURCE_PACKAGE_ROOT / "uploads")
    OUTPUT_BASE = str(_SOURCE_PACKAGE_ROOT / "output")
ARCHIVE_MAX_SIZE = 500 * 1024 * 1024  # 500MB
TEMPLATE_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
REPORT_PARSING_CACHE_LIMIT = 5
