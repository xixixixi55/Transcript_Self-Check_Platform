"""Report-authoritative primary-software normalization and export facts."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .canonical_models_service import (
    FieldProvenance,
    PrimarySoftware,
    PrimarySoftwareCandidate,
    SoftwareTool,
)

_CONFIRMED_STATUSES = {"confirmed_by_report", "confirmed_by_user"}
_RUNTIME_TOOL_NAMES = {"winrar压缩管理软件", "python hashlib"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def primary_software_facts(report: Mapping[str, Any]) -> dict[str, Any]:
    """Read the stable primary-software fields without guessing from tool order."""
    inspection = report.get("inspection") or {}
    raw = inspection.get("primary_software")
    result = inspection.get("result") or {}
    if not isinstance(raw, Mapping):
        return {
            "name": _text(result.get("software_name")),
            "version": _text(result.get("software_version")),
            "status": "unconfirmed",
            "candidates": [],
        }
    return {
        "name": _text(raw.get("name")),
        "version": _text(raw.get("version")),
        "status": _text(raw.get("confirmation_status")) or "unconfirmed",
        "candidates": [
            item for item in raw.get("candidates", [])
            if isinstance(item, Mapping)
        ],
    }


def is_primary_software_confirmed(report: Mapping[str, Any]) -> bool:
    facts = primary_software_facts(report)
    return bool(
        facts["name"]
        and facts["version"]
        and facts["status"] in _CONFIRMED_STATUSES
    )


def normalize_primary_software_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    """Derive legacy result/tool fields from the one editable primary structure."""
    normalized = copy.deepcopy(dict(report))
    inspection = normalized.setdefault("inspection", {})
    result = inspection.setdefault("result", {})
    facts = primary_software_facts(normalized)
    primary = inspection.get("primary_software")
    if not isinstance(primary, Mapping):
        primary = {
            "name": facts["name"],
            "version": facts["version"],
            "display_name": " ".join(filter(None, [facts["name"], facts["version"]])),
            "confirmation_status": "unconfirmed",
            "provenance": [],
            "candidates": facts["candidates"],
        }
    else:
        primary = dict(primary)
        primary["name"] = facts["name"]
        primary["version"] = facts["version"]
        primary.setdefault("display_name", " ".join(filter(None, [facts["name"], facts["version"]])))
        primary.setdefault("provenance", [])
        primary.setdefault("candidates", facts["candidates"])
    inspection["primary_software"] = primary
    result["software_name"] = facts["name"]
    result["software_version"] = facts["version"]

    runtime_tools = []
    for tool in inspection.get("software_tools") or []:
        if not isinstance(tool, Mapping):
            continue
        name = _text(tool.get("name"))
        if name.casefold() in _RUNTIME_TOOL_NAMES:
            runtime_tools.append({"name": name, "version": _text(tool.get("version"))})
    primary_tool = []
    if facts["name"] and facts["version"]:
        primary_tool.append({"name": facts["name"], "version": facts["version"]})
    inspection["software_tools"] = primary_tool + runtime_tools
    return normalized


def migrate_legacy_software(
    inspection: Mapping[str, Any],
    result: Mapping[str, Any],
) -> tuple[PrimarySoftware | None, list[SoftwareTool]]:
    raw_primary = inspection.get("primary_software")
    result_name = _text(result.get("software_name"))
    result_version = _text(result.get("software_version"))
    primary = None
    if isinstance(raw_primary, Mapping):
        name = _text(raw_primary.get("name"))
        version = _text(raw_primary.get("version"))
        primary = PrimarySoftware(
            name=name,
            version=version,
            display_name=_text(raw_primary.get("display_name"))
            or " ".join(filter(None, [name, version])),
            confirmation_status=_text(raw_primary.get("confirmation_status"))
            or "unconfirmed",
            provenance=[
                FieldProvenance(
                    source_type=_text(item.get("source_type")) or "legacy_report",
                    source_file=_text(item.get("source_file")) or None,
                    json_path=_text(item.get("json_path")) or None,
                    adapter=_text(item.get("adapter")) or "legacy-report-adapter",
                    confidence=(
                        item.get("confidence")
                        if isinstance(item.get("confidence"), (int, float))
                        else None
                    ),
                )
                for item in raw_primary.get("provenance") or []
                if isinstance(item, Mapping)
            ],
            candidates=[
                PrimarySoftwareCandidate(
                    name=_text(item.get("name")),
                    version=_text(item.get("version")),
                )
                for item in raw_primary.get("candidates") or []
                if isinstance(item, Mapping)
            ],
        )
    elif result_name or result_version:
        primary = PrimarySoftware(
            name=result_name,
            version=result_version,
            display_name=" ".join(filter(None, [result_name, result_version])),
            confirmation_status="unconfirmed",
        )

    tools: list[SoftwareTool] = []
    for item in inspection.get("software_tools") or []:
        if not isinstance(item, Mapping):
            continue
        name = _text(item.get("name"))
        version = _text(item.get("version"))
        normalized_name = name.casefold()
        if normalized_name == "winrar压缩管理软件".casefold():
            category = "winrar"
        elif normalized_name == "python hashlib".casefold():
            category = "python_hashlib"
        elif primary and primary.name and primary.version and name == primary.name:
            category = "main_forensic"
        else:
            category = "unclassified"
        if category == "unclassified":
            continue
        tools.append(SoftwareTool(
            category=category,
            name=name,
            version=version,
            display_name=" ".join(filter(None, [name, version])),
            confirmation_status=(
                primary.confirmation_status
                if category == "main_forensic" and primary
                else "confirmed"
            ),
        ))
    if primary and primary.name and primary.version and not any(
        tool.category == "main_forensic" for tool in tools
    ):
        tools.insert(0, SoftwareTool(
            category="main_forensic",
            name=primary.name,
            version=primary.version,
            display_name=primary.display_name,
            provenance=primary.provenance,
            confirmation_status=primary.confirmation_status,
        ))
    return primary, tools
