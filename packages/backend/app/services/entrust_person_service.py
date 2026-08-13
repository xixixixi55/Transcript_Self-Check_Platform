"""Layer 21: BE_Services — 委托人列表规范化。"""

import re
from collections.abc import Iterable


_ENTRUST_PERSON_SEPARATOR = re.compile(r"[、,，;；/／|｜\r\n]+")


def normalize_entrust_persons(value: str | Iterable[str] | None) -> list[str]:
    """将常见分隔形式统一拆分为清理过空白的委托人数组。"""
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    persons: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        persons.extend(
            person.strip()
            for person in _ENTRUST_PERSON_SEPARATOR.split(item)
            if person.strip()
        )
    return persons


def format_entrust_persons(value: str | Iterable[str] | None) -> str:
    """使用中文顿号连接规范化后的委托人。"""
    return "、".join(normalize_entrust_persons(value))
