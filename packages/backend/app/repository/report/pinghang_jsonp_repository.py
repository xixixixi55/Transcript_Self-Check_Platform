"""第 20 层：平航报告中受限 JSONP/JavaScript 字面量的安全解码。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


_PAYLOAD_RE = re.compile(
    r"\A\s*;?\s*static\.report\.records\.data_(?P<index>\d+)_(?P<page>\d+)"
    r"\s*=\s*(?P<body>\{.*\})\s*;?\s*\Z",
    re.DOTALL,
)
_NAVIGATION_RE = re.compile(
    r"\A\s*;?\s*window\.static\.report\.zNodes\s*=\s*"
    r"\[(?P<body>.*)\]\s*;?\s*\Z",
    re.DOTALL,
)
_OBJECT_RE = re.compile(r"\{(?P<body>(?:'(?:\\.|[^'\\])*'|[^{}])*)\}", re.DOTALL)
_PROPERTY_RE = re.compile(
    r"(?P<key>[A-Za-z_]\w*)\s*:\s*"
    r"(?P<value>'(?:\\.|[^'\\])*'|-?\d+|true|false|null)",
    re.DOTALL,
)
_MAX_PAGE_CHARS = 2 * 1024 * 1024
_MAX_DEPTH = 64


class PinghangPayloadError(ValueError):
    """平航元数据不是受支持的受限字面量。"""


@dataclass(frozen=True)
class PinghangNavigationNode:
    node_id: int
    parent_id: int
    encoded_name: str
    data_index: str
    view_type: str
    range_count: int


def parse_pinghang_payload(
    text: str, *, expected_index: str, expected_page: int,
) -> dict[str, Any]:
    """仅接受单一、完整的平航数据赋值；绝不执行输入。"""
    cleaned = _clean_text(text)
    match = _PAYLOAD_RE.fullmatch(cleaned)
    if (
        match is None
        or match.group("index") != str(expected_index)
        or int(match.group("page")) != expected_page
    ):
        raise PinghangPayloadError("PINGHANG_PAYLOAD_ASSIGNMENT_INVALID")
    try:
        value = json.loads(_remove_trailing_commas(match.group("body")))
    except (json.JSONDecodeError, ValueError, RecursionError) as error:
        raise PinghangPayloadError("PINGHANG_PAYLOAD_LITERAL_INVALID") from error
    if not isinstance(value, dict) or _nesting_depth(value) > _MAX_DEPTH:
        raise PinghangPayloadError("PINGHANG_PAYLOAD_STRUCTURE_INVALID")
    return value


def parse_pinghang_navigation(text: str) -> tuple[PinghangNavigationNode, ...]:
    """解析导航中的扁平节点对象；函数、表达式和嵌套对象均被拒绝。"""
    cleaned = _clean_text(text)
    match = _NAVIGATION_RE.fullmatch(cleaned)
    if match is None:
        raise PinghangPayloadError("PINGHANG_NAVIGATION_ASSIGNMENT_INVALID")
    body = match.group("body")
    nodes: list[PinghangNavigationNode] = []
    consumed: list[tuple[int, int]] = []
    for object_match in _OBJECT_RE.finditer(body):
        consumed.append(object_match.span())
        properties = _parse_properties(object_match.group("body"))
        try:
            nodes.append(PinghangNavigationNode(
                node_id=_required_int(properties, "id"),
                parent_id=_required_int(properties, "pid"),
                encoded_name=_optional_text(properties.get("name")),
                data_index=_optional_text(properties.get("dataIndex")),
                view_type=_optional_text(properties.get("viewType")),
                range_count=max(1, int(properties.get("rangeCount", 1))),
            ))
        except (TypeError, ValueError) as error:
            raise PinghangPayloadError("PINGHANG_NAVIGATION_NODE_INVALID") from error
    residual = _remove_spans(body, consumed)
    if residual.strip(" \t\r\n,") or not nodes:
        raise PinghangPayloadError("PINGHANG_NAVIGATION_LITERAL_INVALID")
    return tuple(nodes)


def _parse_properties(body: str) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    spans: list[tuple[int, int]] = []
    for match in _PROPERTY_RE.finditer(body):
        key = match.group("key")
        if key in properties:
            raise PinghangPayloadError("PINGHANG_NAVIGATION_PROPERTY_DUPLICATE")
        properties[key] = _parse_scalar(match.group("value"))
        spans.append(match.span())
    if _remove_spans(body, spans).strip(" \t\r\n,"):
        raise PinghangPayloadError("PINGHANG_NAVIGATION_PROPERTY_INVALID")
    return properties


def _parse_scalar(value: str) -> Any:
    if value.startswith("'"):
        raw = value[1:-1]
        result: list[str] = []
        index = 0
        escapes = {"n": "\n", "r": "\r", "t": "\t", "'": "'", "\\": "\\"}
        while index < len(raw):
            char = raw[index]
            if char != "\\":
                result.append(char)
                index += 1
                continue
            index += 1
            if index >= len(raw):
                raise PinghangPayloadError("PINGHANG_NAVIGATION_STRING_INVALID")
            escaped = raw[index]
            if escaped == "u" and index + 4 < len(raw):
                digits = raw[index + 1:index + 5]
                if not re.fullmatch(r"[0-9A-Fa-f]{4}", digits):
                    raise PinghangPayloadError("PINGHANG_NAVIGATION_STRING_INVALID")
                result.append(chr(int(digits, 16)))
                index += 5
                continue
            if escaped not in escapes:
                raise PinghangPayloadError("PINGHANG_NAVIGATION_STRING_INVALID")
            result.append(escapes[escaped])
            index += 1
        return "".join(result)
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    return int(value)


def _clean_text(text: str) -> str:
    if not isinstance(text, str) or len(text) > _MAX_PAGE_CHARS:
        raise PinghangPayloadError("PINGHANG_PAYLOAD_SIZE_INVALID")
    return text.lstrip("\ufeff").replace("\x00", "").strip()


def _remove_trailing_commas(text: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == ",":
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following < len(text) and text[following] in "}]":
                index += 1
                continue
        result.append(char)
        index += 1
    return "".join(result)


def _nesting_depth(value: Any, depth: int = 0) -> int:
    if not isinstance(value, (dict, list)):
        return depth
    if depth > _MAX_DEPTH:
        return depth
    children = value.values() if isinstance(value, dict) else value
    return max((_nesting_depth(item, depth + 1) for item in children), default=depth + 1)


def _remove_spans(value: str, spans: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(value[cursor:start])
        cursor = end
    parts.append(value[cursor:])
    return "".join(parts)


def _required_int(properties: dict[str, Any], key: str) -> int:
    value = properties.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PinghangPayloadError("PINGHANG_NAVIGATION_NODE_INVALID")
    return value


def _optional_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


__all__ = [
    "PinghangNavigationNode", "PinghangPayloadError",
    "parse_pinghang_navigation", "parse_pinghang_payload",
]
