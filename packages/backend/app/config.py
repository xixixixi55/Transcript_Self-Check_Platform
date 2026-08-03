"""应用级路径常量和纯设置 — 中立基础设施。

此模块不包含任何 I/O 操作或业务逻辑。
任何架构层均可安全导入。
"""
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_BASE = os.path.join(_PROJECT_ROOT, "uploads")
OUTPUT_BASE = os.path.join(_PROJECT_ROOT, "output")
ARCHIVE_MAX_SIZE = 500 * 1024 * 1024  # 500MB
TEMPLATE_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
REPORT_PARSING_CACHE_LIMIT = 5
