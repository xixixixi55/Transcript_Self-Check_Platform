"""Python 架构依赖检查器的自动化测试。

验证 `scripts/_python_imports.py` AST 导入提取器：
- 相对导入和项目内部绝对导入均可提取
- 语法错误文件返回错误标记
- 标准库/第三方导入被正确跳过
"""
import json
import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = REPO_ROOT / "scripts" / "_python_imports.py"
sys.path.insert(0, str(EXTRACTOR.parent))

from _python_imports import extract_files  # noqa: E402


def _extract(files: list[str]) -> dict:
    """Directly exercise the AST and payload logic without a process startup."""
    return extract_files(files)


def _extract_cli(files: list[str]) -> dict:
    """Keep one real CLI boundary test for argument and JSON output wiring."""
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


def test_cli_batches_relative_import_shapes(tmp_path):
    files = [
        _write_py(str(tmp_path), "controllers/level2.py",
                  "from ..services.foo import bar\nfrom ..config import X\n"),
        _write_py(str(tmp_path), "controllers/level1.py", "from .other import helper\n"),
        _write_py(str(tmp_path), "services/multiline.py",
                  "from ..repository.foo import (\n    bar,\n    baz,\n)\n"),
        _write_py(str(tmp_path), "services/type_checking.py",
                  "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from ..config import X\n"),
    ]

    data = _extract_cli(files)

    level2 = data[files[0].replace("\\", "/")]
    assert [(item["level"], item["module"]) for item in level2] == [
        (2, "services.foo"), (2, "config"),
    ]
    assert data[files[1].replace("\\", "/")][0] == {
        "line": 1, "level": 1, "module": "other",
    }
    assert data[files[2].replace("\\", "/")][0]["module"] == "repository.foo"
    assert data[files[3].replace("\\", "/")][0]["module"] == "config"


def test_absolute_imports_include_only_app_modules(tmp_path):
    internal = _write_py(
        str(tmp_path), "controllers/absolute.py",
        "from app.services.report_parser_service import parse_report\n",
    )
    external = _write_py(
        str(tmp_path), "controllers/external.py",
        "from fastapi import APIRouter\nimport os\nfrom typing import Optional\n",
    )

    data = _extract([internal, external])
    imports = data[internal.replace("\\", "/")]
    assert data[external.replace("\\", "/")] == []
    assert len(imports) == 1
    assert imports[0]["level"] == 0
    assert imports[0]["absolute"] is True
    assert imports[0]["module"] == "services.report_parser_service"


def test_syntax_errors_are_reported_without_affecting_valid_files(tmp_path):
    broken = _write_py(
        str(tmp_path), "services/broken.py", "this is @@@ not valid python\n",
    )
    valid = _write_py(
        str(tmp_path), "services/valid.py", "from ..repository.foo import bar\n",
    )

    data = _extract([broken, valid])
    assert data[broken.replace("\\", "/")] == []
    assert data[valid.replace("\\", "/")][0]["module"] == "repository.foo"
    errors = data.get("__errors__", [])
    assert len(errors) == 1
    assert errors[0]["file"] == broken.replace("\\", "/")
    assert "SyntaxError" in errors[0]["error"]


def test_app_root_relative_imports_are_extracted(tmp_path):
    fp = _write_py(
        str(tmp_path), "main.py",
        "from .routes import router\n"
        "from .services.pipeline_runtime_service import load_pipeline_settings\n",
    )
    imports = _extract([fp])[fp.replace("\\", "/")]
    assert [(item["level"], item["module"]) for item in imports] == [
        (1, "routes"), (1, "services.pipeline_runtime_service"),
    ]
