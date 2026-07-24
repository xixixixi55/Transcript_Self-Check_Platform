"""Layer 20: 美亚报告 JS-JSON 文件读取。"""

import json
import os
import re
from typing import Any


class ReportParseError(Exception):
    pass


def load_js_json(filepath: str) -> Any:
    if not os.path.exists(filepath):
        raise ReportParseError(f"文件不存在: {filepath}")
    with open(filepath, "r", encoding="utf-8-sig") as file:
        content = file.read()
    return parse_js_json_content(content, filepath)


def parse_js_json_content(content: str, filepath: str = "") -> Any:
    """Parse already-read vendor JS JSON content without reopening its file."""
    json_str = re.sub(r"^;\s*static\.mypico\.(?:json\.)?\w+\s*=\s*", "", content.strip())
    if not json_str:
        suffix = f": {filepath}" if filepath else ""
        raise ReportParseError(f"无法解析 JSON{suffix}")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as error:
        suffix = f": {filepath}" if filepath else ""
        raise ReportParseError(f"无法解析 JSON{suffix}") from error
