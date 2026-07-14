"""Layer 20: data_navigation.json 分类树解析。"""

import json
import re
from typing import Any


def parse_navigation(data_dir: str) -> dict[str, Any]:
    filepath = f"{data_dir}/data_navigation.json"
    with open(filepath, "rb") as file:
        content = file.read()
    match = re.search(rb"=\s*(\[.*)", content, re.DOTALL)
    if not match:
        return {"categories": [], "total_items": 0}
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return _parse_navigation_fallback(content)

    categories: list[str] = []
    total_items = 0

    def traverse(nodes):
        nonlocal total_items
        for node in nodes:
            name = node.get("name", "")
            total_items += node.get("dataTotal", 0) or 0
            pid = node.get("pid", "")
            if pid and pid not in {"report_info", "device_lists"}:
                if node.get("dataConfig", {}).get("varName") and name and name not in categories:
                    categories.append(name)
            traverse(node.get("children", []))

    traverse(data if isinstance(data, list) else [])
    return {"categories": categories, "total_items": total_items}


def _parse_navigation_fallback(raw: bytes) -> dict[str, Any]:
    names = re.findall(rb'"name":"([^"]{1,60})"', raw)
    categories = set()
    for name_bytes in names:
        try:
            name = name_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not name.replace(" ", "").isdigit() and "wxid_" not in name and "@chatroom" not in name and len(name) > 1:
            categories.add(name)
    totals = re.findall(rb'"dataTotal":(\d+)', raw)
    return {"categories": list(categories)[:20], "total_items": sum(map(int, totals)) if totals else 0}
