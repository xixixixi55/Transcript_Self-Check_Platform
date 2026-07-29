"""Project internal capability facts to a fixed, path-free Demo DTO."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..repository.demo_readiness_repository import (
    probe_archive_output,
    probe_winrar,
)
from ..repository.winrar_discovery_repository import WinRarCapability


def _item(
    key: str, label: str, status: str, code: str | None, guidance: str,
) -> dict[str, str | None]:
    return {
        "key": key, "label": label, "status": status,
        "code": code, "guidance": guidance,
    }


def _source_item(authorization_store: Any | None) -> dict[str, str | None]:
    if authorization_store is None:
        return _item(
            "source_authorization", "来源目录授权", "unknown",
            "DEMO_SOURCE_AUTH_UNKNOWN", "请检查后端配置并重启后再次确认。",
        )
    try:
        roots = authorization_store.configured_roots
        warnings = authorization_store.configuration_warnings
    except Exception:
        return _item(
            "source_authorization", "来源目录授权", "unknown",
            "DEMO_SOURCE_AUTH_UNKNOWN", "请检查后端配置并重启后再次确认。",
        )
    if not roots:
        return _item(
            "source_authorization", "来源目录授权", "not_configured",
            "DEMO_SOURCE_AUTH_NOT_CONFIGURED",
            "请在后端启动前配置授权输入根，修改后重启后端。",
        )
    if warnings:
        return _item(
            "source_authorization", "来源目录授权", "unknown",
            "DEMO_SOURCE_AUTH_PARTIAL",
            "部分授权配置无法确认，请修正配置并重启后端。",
        )
    return _item(
        "source_authorization", "来源目录授权", "ready", None,
        "仅可登记位于后端授权输入根内的报告目录。",
    )


def _winrar_item(
    winrar_probe: Callable[[], WinRarCapability],
) -> dict[str, str | None]:
    try:
        capability = winrar_probe()
    except Exception:
        return _item(
            "winrar", "WinRAR", "unknown", "DEMO_WINRAR_UNKNOWN",
            "请在服务器检查 WinRAR 配置并重启后端。",
        )
    if capability.available and capability.supports_rar_volumes:
        return _item("winrar", "WinRAR", "ready", None, "自动分卷能力可用。")
    return _item(
        "winrar", "WinRAR", "unavailable", "WINRAR_UNAVAILABLE",
        "请安装或配置支持分卷的 WinRAR，并重启后端。",
    )


def _output_item(
    output_root: str, output_probe: Callable[[str], str],
) -> dict[str, str | None]:
    try:
        status = output_probe(output_root)
    except Exception:
        status = "unknown"
    if status == "ready":
        return _item(
            "archive_output", "归档输出根", "ready", None,
            "归档输出区域可访问。",
        )
    if status == "unavailable":
        return _item(
            "archive_output", "归档输出根", "unavailable",
            "DEMO_ARCHIVE_OUTPUT_UNAVAILABLE",
            "请检查服务器输出目录及访问权限。",
        )
    return _item(
        "archive_output", "归档输出根", "unknown",
        "DEMO_ARCHIVE_OUTPUT_UNKNOWN",
        "当前无法确认输出区域，请检查服务器配置。",
    )


def build_demo_readiness(
    authorization_store: Any | None,
    output_root: str,
    *,
    winrar_probe: Callable[[], WinRarCapability] = probe_winrar,
    output_probe: Callable[[str], str] = probe_archive_output,
) -> dict[str, list[dict[str, str | None]]]:
    return {
        "items": [
            _item("backend", "后端服务", "ready", None, "后端服务可用。"),
            _source_item(authorization_store),
            _winrar_item(winrar_probe),
            _output_item(output_root, output_probe),
        ],
    }
