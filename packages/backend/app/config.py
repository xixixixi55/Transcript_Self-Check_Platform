"""从进程运行时根目录一次性投影的应用设置。"""
from pathlib import Path

from .repository.runtime.runtime_paths import get_runtime_paths
from .repository.archive.archive_storage_settings_repository import ArchiveStorageSettingsRepository

RUNTIME_PATHS = get_runtime_paths()
if RUNTIME_PATHS.portable:
    UPLOAD_BASE = str(RUNTIME_PATHS.upload_root)
    OUTPUT_BASE = str(RUNTIME_PATHS.output_root)
else:
    # 保持源码/开发环境布局不变。只有打包后的运行时才会将可变状态
    # 从程序目录移至 LOCALAPPDATA。
    _SOURCE_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
    UPLOAD_BASE = str(_SOURCE_PACKAGE_ROOT / "uploads")
    OUTPUT_BASE = str(_SOURCE_PACKAGE_ROOT / "output")
_ARCHIVE_STORAGE_SELECTION = ArchiveStorageSettingsRepository().resolve(
    Path(OUTPUT_BASE), RUNTIME_PATHS.resource_root,
)
ARCHIVE_OUTPUT_BASE = str(
    _ARCHIVE_STORAGE_SELECTION.desired_output_root
    if _ARCHIVE_STORAGE_SELECTION.valid else Path(OUTPUT_BASE)
)
ARCHIVE_MAX_SIZE = 500 * 1024 * 1024  # 500MB
TEMPLATE_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
