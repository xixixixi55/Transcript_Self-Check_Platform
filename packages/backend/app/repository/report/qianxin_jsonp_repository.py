"""Layer 20：奇安信网页版报告严格 JSONP 数据赋值解码。"""

from __future__ import annotations

import json
import math
import re
from typing import Any


_ASSIGNMENT_RE = re.compile(
    r"\A\s*;?\s*static\.report\.context\.(?P<stem>[A-Za-z_]\w*)"
    r"\s*=\s*(?P<body>[\[{].*[\]}])\s*;?\s*\Z",
    re.DOTALL,
)
_DEFAULT_MAX_PAYLOAD_CHARS = 2 * 1024 * 1024
_MAX_DEPTH = 64


class QianxinPayloadError(ValueError):
    """奇安信核心元数据不是受支持的单一 JSON 数据赋值。"""


def parse_qianxin_payload(
    text: str, *, expected_stem: str,
    max_chars: int = _DEFAULT_MAX_PAYLOAD_CHARS,
) -> Any:
    """只解析固定变量名后的 JSON；绝不执行报告脚本。"""
    if (
        not isinstance(text, str)
        or len(text) > max_chars
        or "\x00" in text
    ):
        raise QianxinPayloadError("QIANXIN_PAYLOAD_SIZE_INVALID")
    match = _ASSIGNMENT_RE.fullmatch(text.lstrip("\ufeff").strip())
    if match is None or match.group("stem") != expected_stem:
        raise QianxinPayloadError("QIANXIN_PAYLOAD_ASSIGNMENT_INVALID")
    try:
        value = json.loads(
            match.group("body"),
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as error:
        raise QianxinPayloadError("QIANXIN_PAYLOAD_LITERAL_INVALID") from error
    if _nesting_depth(value) > _MAX_DEPTH:
        raise QianxinPayloadError("QIANXIN_PAYLOAD_STRUCTURE_INVALID")
    return value


def _reject_constant(_value: str) -> Any:
    raise QianxinPayloadError("QIANXIN_PAYLOAD_LITERAL_INVALID")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise QianxinPayloadError("QIANXIN_PAYLOAD_LITERAL_INVALID")
    return result


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QianxinPayloadError("QIANXIN_PAYLOAD_LITERAL_INVALID")
        result[key] = value
    return result


def _nesting_depth(value: Any, depth: int = 0) -> int:
    if not isinstance(value, (dict, list)):
        return depth
    if depth > _MAX_DEPTH:
        return depth
    children = value.values() if isinstance(value, dict) else value
    return max((_nesting_depth(item, depth + 1) for item in children), default=depth + 1)


__all__ = ["QianxinPayloadError", "parse_qianxin_payload"]
