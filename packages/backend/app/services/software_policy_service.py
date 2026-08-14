"""Report-authoritative primary-software normalization and export facts."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from ..repository.hashmyfiles_repository import HASHMYFILES_DISPLAY_VERSION
from .canonical_models_service import (
    FieldProvenance,
    PrimarySoftware,
    PrimarySoftwareCandidate,
    SoftwareTool,
)

_CONFIRMED_STATUSES = {"confirmed_by_report", "confirmed_by_user"}
_RUNTIME_TOOL_NAMES = {"winrar压缩管理软件", "python hashlib", "hashmyfiles"}
_LEGACY_HASH_TOOL_NAME = "python hashlib"
_HASHMYFILES_NAME = "HashMyFiles"


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


def apply_device_company_prefix(
    report: Mapping[str, Any], company: object,
) -> dict[str, Any]:
    """Prefix one report-confirmed primary tool without rewriting report evidence."""
    normalized = copy.deepcopy(dict(report))
    company_value = _text(company)
    facts = primary_software_facts(normalized)
    if (
        not company_value
        or facts["status"] != "confirmed_by_report"
        or not facts["name"]
        or not facts["version"]
    ):
        return normalized

    source_name = facts["name"]
    prefixed_name = (
        source_name
        if source_name.casefold().startswith(company_value.casefold())
        else f"{company_value}{source_name}"
    )
    inspection = normalized.setdefault("inspection", {})
    primary = inspection.get("primary_software")
    if not isinstance(primary, Mapping):
        return normalized
    projected_primary = dict(primary)
    projected_primary["name"] = prefixed_name
    projected_primary["display_name"] = " ".join(
        filter(None, [prefixed_name, facts["version"]])
    )
    inspection["primary_software"] = projected_primary

    result = inspection.setdefault("result", {})
    result["software_name"] = prefixed_name
    result["software_version"] = facts["version"]

    tools = []
    main_projected = False
    for tool in inspection.get("software_tools") or []:
        if not isinstance(tool, Mapping):
            tools.append(copy.deepcopy(tool))
            continue
        projected_tool = dict(tool)
        tool_name = _text(tool.get("name"))
        tool_version = _text(tool.get("version"))
        is_primary = not main_projected and (
            _text(tool.get("category")) == "main_forensic"
            or (tool_name == source_name and tool_version == facts["version"])
        )
        if is_primary:
            projected_tool["name"] = prefixed_name
            if "display_name" in projected_tool or tool.get("category") == "main_forensic":
                projected_tool["display_name"] = " ".join(
                    filter(None, [prefixed_name, facts["version"]])
                )
            main_projected = True
        tools.append(projected_tool)
    if not main_projected:
        tools.insert(0, {"name": prefixed_name, "version": facts["version"]})
    inspection["software_tools"] = tools

    process_steps = []
    for step in inspection.get("process_steps") or []:
        if not isinstance(step, Mapping):
            process_steps.append(copy.deepcopy(step))
            continue
        projected_step = dict(step)
        if step.get("step_number") == 4:
            projected_step["content"] = _text(step.get("content")).replace(
                source_name, prefixed_name, 1,
            )
        process_steps.append(projected_step)
    inspection["process_steps"] = process_steps
    return normalized


def normalize_runtime_software_tool_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    """Show the active hash tool while continuing to accept legacy stored data."""
    normalized = copy.deepcopy(dict(report))
    inspection = normalized.setdefault("inspection", {})
    tools = inspection.get("software_tools") or []
    has_hashmyfiles = any(
        isinstance(tool, Mapping)
        and _text(tool.get("name")).casefold() == _HASHMYFILES_NAME.casefold()
        for tool in tools
    )
    projected = []
    emitted_hashmyfiles = False
    for tool in tools:
        if not isinstance(tool, Mapping):
            continue
        name = _text(tool.get("name"))
        normalized_name = name.casefold()
        if normalized_name == _LEGACY_HASH_TOOL_NAME:
            if not has_hashmyfiles and not emitted_hashmyfiles:
                projected_tool = dict(tool)
                projected_tool.update({
                    "category": "hashmyfiles",
                    "name": _HASHMYFILES_NAME,
                    "version": HASHMYFILES_DISPLAY_VERSION,
                    "display_name": f"{_HASHMYFILES_NAME} {HASHMYFILES_DISPLAY_VERSION}",
                })
                projected.append(projected_tool)
                emitted_hashmyfiles = True
            continue
        if normalized_name == _HASHMYFILES_NAME.casefold():
            if emitted_hashmyfiles:
                continue
            projected_tool = dict(tool)
            projected_tool["category"] = "hashmyfiles"
            projected_tool["name"] = _HASHMYFILES_NAME
            projected_tool["version"] = HASHMYFILES_DISPLAY_VERSION
            projected_tool["display_name"] = f"{_HASHMYFILES_NAME} {HASHMYFILES_DISPLAY_VERSION}"
            projected.append(projected_tool)
            emitted_hashmyfiles = True
            continue
        projected.append(dict(tool))
    inspection["software_tools"] = projected
    return normalized


def normalize_primary_software_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    """Derive legacy result/tool fields from the one editable primary structure."""
    normalized = normalize_runtime_software_tool_projection(report)
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
        elif normalized_name == "hashmyfiles".casefold():
            category = "hashmyfiles"
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
