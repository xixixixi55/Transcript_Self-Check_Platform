"""Extract intra-package imports from Python files using AST.

Usage: python scripts/_python_imports.py <file1> <file2> ...
Output: JSON map of {
    normalized_path: [{line, level, module}],
    "__errors__": [{file, error}]   // 语法错误文件列表
}

覆盖：
- 相对导入 (level>=1): from ..services.foo import bar
- 项目内部绝对导入 (level=0, module 以 app. 开头): from app.services.foo import bar
- 不提取标准库/第三方绝对导入
"""
import ast
import json
import sys
from pathlib import Path

APP_ROOT_MARKER = "app."

def extract_imports(filepath: str) -> tuple[list[dict], str | None]:
    """返回 (imports, error_string)。error_string 非空时 imports 应被忽略。"""
    try:
        source = Path(filepath).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [], f"SyntaxError: {e.msg} (line {e.lineno})"
    except Exception as e:
        return [], f"ParseError: {e}"

    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            names = [alias.name for alias in node.names]
            if not names:
                continue

            # 相对导入 (level >= 1)
            if node.level >= 1:
                results.append({
                    "line": node.lineno,
                    "level": node.level,
                    "module": node.module,
                })
            # 项目内部绝对导入 (level=0, 以 app. 开头)
            elif node.module.startswith(APP_ROOT_MARKER):
                # 去掉 app. 前缀，保留后续的 services.foo.bar
                internal_module = node.module[len(APP_ROOT_MARKER):]
                results.append({
                    "line": node.lineno,
                    "level": 0,
                    "module": internal_module,
                    "absolute": True,
                })

    return results, None

def main():
    files = sys.argv[1:]
    output = {}
    errors = []

    for f in files:
        imports, error = extract_imports(f)
        norm = f.replace("\\", "/")
        if error:
            errors.append({"file": norm, "error": error})
            output[norm] = []  # 语法错误文件返回空 imports，但错误列表单独记录
        else:
            output[norm] = imports

    output["__errors__"] = errors
    json.dump(output, sys.stdout, ensure_ascii=False)

if __name__ == "__main__":
    main()
