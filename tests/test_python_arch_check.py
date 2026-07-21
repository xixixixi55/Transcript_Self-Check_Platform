"""Python 架构依赖检查器的自动化测试。

验证 `scripts/_python_imports.py` AST 导入提取器：
- 相对导入和项目内部绝对导入均可提取
- 语法错误文件返回错误标记
- 标准库/第三方导入被正确跳过
"""
import json
import os
import sys
import tempfile
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = REPO_ROOT / "scripts" / "_python_imports.py"


def _extract(files: list[str]) -> dict:
    """运行 AST 提取器并返回解析后的 JSON。"""
    r = subprocess.run(
        [sys.executable, str(EXTRACTOR)] + files,
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, f"提取器非零退出: {r.stderr}"
    return json.loads(r.stdout)


def _write_py(tmpdir: str, relpath: str, content: str) -> str:
    """在临时目录中写入 Python 文件，自动创建父目录。"""
    fp = os.path.join(tmpdir, relpath)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    Path(fp).write_text(content, encoding="utf-8")
    return fp


class TestRelativeImports:
    """相对导入提取"""

    def test_level2_services_and_config(self, tmp_path):
        fp = _write_py(str(tmp_path), "controllers/test1.py",
                       "from ..services.foo import bar\nfrom ..config import X\n")
        data = _extract([fp])
        key = fp.replace("\\", "/")
        imports = data[key]
        assert len(imports) == 2
        assert imports[0]["level"] == 2
        assert imports[0]["module"] == "services.foo"
        assert imports[1]["level"] == 2
        assert imports[1]["module"] == "config"

    def test_level1_same_package(self, tmp_path):
        fp = _write_py(str(tmp_path), "controllers/test2.py",
                       "from .other import helper\n")
        data = _extract([fp])
        imports = data[fp.replace("\\", "/")]
        assert len(imports) == 1
        assert imports[0]["level"] == 1
        assert imports[0]["module"] == "other"

    def test_multi_line_parenthesized(self, tmp_path):
        fp = _write_py(str(tmp_path), "services/test4.py",
                       "from ..repository.foo import (\n    bar,\n    baz,\n)\n")
        data = _extract([fp])
        imports = data[fp.replace("\\", "/")]
        assert len(imports) == 1
        assert imports[0]["level"] == 2
        assert imports[0]["module"] == "repository.foo"

    def test_type_checking_block_still_extracted(self, tmp_path):
        fp = _write_py(str(tmp_path), "services/test6.py",
                       "from typing import TYPE_CHECKING\n"
                       "if TYPE_CHECKING:\n"
                       "    from ..config import X\n")
        data = _extract([fp])
        imports = data[fp.replace("\\", "/")]
        assert len(imports) == 1
        assert imports[0]["module"] == "config"


class TestAbsoluteImports:
    """项目内部绝对导入提取"""

    def test_app_prefix_absolute_import(self, tmp_path):
        fp = _write_py(str(tmp_path), "controllers/test_abs.py",
                       "from app.services.report_parser_service import parse_report\n")
        data = _extract([fp])
        imports = data[fp.replace("\\", "/")]
        assert len(imports) == 1
        assert imports[0]["level"] == 0
        assert imports[0]["absolute"] is True
        # 已去除 app. 前缀
        assert imports[0]["module"] == "services.report_parser_service"

    def test_third_party_absolute_skipped(self, tmp_path):
        fp = _write_py(str(tmp_path), "controllers/test_3rd.py",
                       "from fastapi import APIRouter\nimport os\nfrom typing import Optional\n")
        data = _extract([fp])
        imports = data[fp.replace("\\", "/")]
        assert len(imports) == 0


class TestSyntaxErrors:
    """语法错误 → 错误标记，不能静默跳过"""

    def test_syntax_error_reported(self, tmp_path):
        fp = _write_py(str(tmp_path), "services/broken.py",
                       "this is @@@ not valid python\n")
        data = _extract([fp])
        # imports 为空
        assert data[fp.replace("\\", "/")] == []
        # __errors__ 中包含该文件
        errors = data.get("__errors__", [])
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]["error"]

    def test_valid_file_no_errors(self, tmp_path):
        fp = _write_py(str(tmp_path), "services/valid.py",
                       "from ..repository.foo import bar\n")
        data = _extract([fp])
        assert data.get("__errors__") == []


class TestAppRootFiles:
    """app/*.py 文件导入提取"""

    def test_main_py_imports_extracted(self, tmp_path):
        fp = _write_py(str(tmp_path), "main.py",
                       "from .routes import router\n"
                       "from .services.pipeline_runtime_service import load_pipeline_settings\n")
        data = _extract([fp])
        imports = data[fp.replace("\\", "/")]
        assert len(imports) == 2
        assert imports[0]["level"] == 1
        assert imports[0]["module"] == "routes"
        assert imports[1]["level"] == 1
        assert imports[1]["module"] == "services.pipeline_runtime_service"
