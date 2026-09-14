"""Layer 20：陌生报告的只读、有界 JSON/JSONP 结构发现。"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..source.filesystem_identity_repository import resolve_directory
from ..workbench.workbench_errors import WorkbenchPersistenceError
from .report_parse_input_filesystem import (
    ReportDependencyBudgetError,
    ancestor_identities,
    file_identity,
    read_bounded_dependency,
)
from .report_parse_input_models import ReportParseInputError

MAX_DISCOVERY_DEPTH = 4
MAX_DISCOVERY_FILES = 128
MAX_DISCOVERY_FILE_BYTES = 1024 * 1024
MAX_DISCOVERY_TOTAL_BYTES = 4 * 1024 * 1024
MAX_DISCOVERY_ENTRIES = 2048
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 8192
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_ASSIGNMENT = re.compile(
    r"^\s*(?:(?:var|let|const)\s+)?[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*\s*=\s*([\s\S]*?)\s*;?\s*$"
)
_SUPPORTED_SUFFIXES = {".json", ".jsonp", ".js"}
_EXCLUDED_DIRECTORY_NAMES = {
    "attachment", "attachments", "asset", "assets", "media", "image", "images",
    "photo", "photos", "picture", "pictures", "video", "videos", "audio",
    "audios", "resource", "resources", "static", "public", "tool", "tools",
    "program", "programs", "detail", "details", "file", "files",
}
_EXCLUDED_DIRECTORY_MARKERS = (
    "attachments", "assets", "images", "photos", "pictures", "videos", "audios",
    "resources", "tools", "programs", "details", "files", "附件", "媒体",
    "图片", "照片", "视频", "音频", "资源", "工具", "程序", "明细", "详情",
    "提取数据", "通讯录", "聊天记录",
)
_EXCLUDED_DIRECTORY_EDGE_MARKERS = (
    "attachment", "asset", "media", "image", "photo", "picture", "video", "audio",
    "resource", "static", "public", "tool", "program", "detail",
)
_ALIASES: dict[str, tuple[str, ...]] = {
    "case.case_name": ("案件名称", "案件名", "casename", "case_name"),
    "case.case_number": ("案件编号", "案号", "casenumber", "case_no", "caseid"),
    "case.entrust_unit": ("送检单位", "委托单位", "submitunit", "entrustunit"),
    "case.entrust_persons": ("送检人", "委托人", "submitperson", "entrustperson"),
    "case.case_summary": ("案件简要情况", "案情摘要", "案件摘要", "casesummary"),
    "case.created_at": ("创建时间", "案件时间", "createtime", "createdat"),
    "case.reported_at": ("报告时间", "生成时间", "reporttime", "reportedat"),
    "software.name": ("取证软件", "软件名称", "应用名称", "softwarename", "appname"),
    "software.version": ("软件版本", "应用版本", "softwareversion", "appversion"),
    "inspection.hardware_device": ("取证硬件", "硬件设备", "采集设备", "hardwaredevice"),
    "material.evidence_number": ("检材编号", "物证编号", "证据编号", "evidencenumber", "materialnumber"),
    "material.name": ("设备名称", "检材名称", "devicename", "materialname"),
    "material.model": ("设备型号", "型号", "devicemodel", "model"),
    "material.holder_name": ("持有人", "机主姓名", "用户姓名", "holdername", "ownername"),
    "material.imei1": ("imei1", "imei"),
    "material.imei2": ("imei2",),
    "material.serial_number": ("序列号", "serialnumber", "serialno", "sn"),
    "material.acquisition_started_at": ("取证开始时间", "提取开始时间", "starttime", "acquisitionstart"),
    "material.acquisition_ended_at": ("取证结束时间", "解析时间", "endtime", "acquisitionend"),
    "material.type": ("检材类型", "设备类型", "数据类型", "devicetype", "materialtype"),
}
_NORMALIZED_ALIASES = {
    field: {
        re.sub(r"[\s_\-:：./\\]+", "", str(alias)).casefold()
        for alias in aliases
    }
    for field, aliases in _ALIASES.items()
}


@dataclass(frozen=True)
class DiscoveryDependency:
    relative_path: str
    size_bytes: int
    modified_time_ns: int
    content_digest: str


@dataclass(frozen=True)
class _DiscoveryCandidateFile:
    path: Path
    expected_identity: tuple[int, int, int, int]
    expected_ancestors: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class ReportStructureDiscovery:
    structure_fingerprint: str
    source_fingerprint: str
    candidates: tuple[dict[str, Any], ...]
    dependencies: tuple[DiscoveryDependency, ...]
    payloads: dict[str, Any]

    def public(self) -> dict[str, Any]:
        return {
            "structure_fingerprint": self.structure_fingerprint,
            "candidate_count": len(self.candidates),
            "candidates": [dict(item) for item in self.candidates],
            "limits": {
                "max_depth": MAX_DISCOVERY_DEPTH,
                "max_files": MAX_DISCOVERY_FILES,
                "max_file_bytes": MAX_DISCOVERY_FILE_BYTES,
                "max_total_bytes": MAX_DISCOVERY_TOTAL_BYTES,
            },
        }


def discover_report_structure(source_dir: str | Path) -> ReportStructureDiscovery:
    root = resolve_directory(source_dir)
    paths = _candidate_files(root)
    if not paths:
        raise WorkbenchPersistenceError("REPORT_DISCOVERY_NO_METADATA")
    payloads: dict[str, Any] = {}
    dependencies: list[DiscoveryDependency] = []
    structure_rows: list[str] = []
    grouped_candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    total = 0
    for candidate_file in paths:
        path = candidate_file.path
        relative = path.relative_to(root).as_posix()
        remaining_total = MAX_DISCOVERY_TOTAL_BYTES - total
        if remaining_total <= 0:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED")
        try:
            raw, details = read_bounded_dependency(
                path,
                root,
                min(MAX_DISCOVERY_FILE_BYTES, remaining_total),
                expected_identity=candidate_file.expected_identity,
                expected_ancestors=candidate_file.expected_ancestors,
            )
        except ReportDependencyBudgetError as error:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED") from error
        except ReportParseInputError as error:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_STRUCTURE_CHANGED") from error
        total += len(raw)
        if total > MAX_DISCOVERY_TOTAL_BYTES:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED")
        try:
            payload = _parse_data_literal(raw)
        except WorkbenchPersistenceError:
            if path.suffix.casefold() in {".json", ".jsonp"}:
                raise
            continue
        _validate_payload_shape(payload)
        payloads[relative] = payload
        structure_rows.append(f"{relative}\0$file\0metadata")
        structure_rows.extend(
            f"{relative}\0{_json_path(tokens)}\0{node_type}"
            for tokens, node_type in _structure_nodes(payload)
        )
        content_digest = hashlib.sha256(raw).hexdigest()
        dependencies.append(DiscoveryDependency(
            relative, len(raw), int(details.st_mtime_ns), content_digest,
        ))
        for tokens, value in _scalar_leaves(payload):
            pattern = tuple("*" if isinstance(token, int) else token for token in tokens)
            json_path = _json_path(pattern)
            value_type = _value_type(value)
            leaf = str(tokens[-1]) if tokens else ""
            for canonical_field, aliases in _NORMALIZED_ALIASES.items():
                if value is None or _normalize_key(leaf) not in aliases:
                    continue
                key = (canonical_field, relative, json_path)
                candidate = grouped_candidates.setdefault(key, {
                    "candidate_id": _candidate_id(canonical_field, relative, json_path),
                    "canonical_field": canonical_field,
                    "source_file": relative,
                    "json_path": json_path,
                    "collection_path": _collection_path(
                        pattern, material=canonical_field.startswith("material."),
                    ),
                    "confidence": 0.95,
                    "evidence": [f"label:{leaf}"],
                    "preview_values": [],
                    "_value_types": set(),
                })
                candidate["_value_types"].add(value_type)
                preview = _preview(value)
                if preview not in candidate["preview_values"] and len(candidate["preview_values"]) < 3:
                    candidate["preview_values"].append(preview)
    structure_fingerprint = _digest_rows(sorted(set(structure_rows)))
    source_fingerprint = _digest_rows([
        f"{item.relative_path}\0{item.size_bytes}\0{item.modified_time_ns}\0{item.content_digest}"
        for item in dependencies
    ])
    candidates = tuple(sorted(
        (
            {
                **{key: value for key, value in item.items() if key != "_value_types"},
                "value_type": next(iter(item["_value_types"])),
            }
            for item in grouped_candidates.values()
            if len(item["_value_types"]) == 1
        ),
        key=lambda item: (item["canonical_field"], item["source_file"], item["json_path"]),
    ))
    if not candidates:
        raise WorkbenchPersistenceError("REPORT_DISCOVERY_NO_FIELDS")
    return ReportStructureDiscovery(
        structure_fingerprint, source_fingerprint, candidates,
        tuple(dependencies), payloads,
    )


def extract_profile_values(
    discovery: ReportStructureDiscovery,
    mappings: list[dict[str, Any]],
) -> dict[str, list[tuple[tuple[int, ...], str]]]:
    result: dict[str, list[tuple[tuple[int, ...], str]]] = {}
    for mapping in mappings:
        source_file = str(mapping["source_file"])
        payload = discovery.payloads.get(source_file)
        if payload is None:
            raise WorkbenchPersistenceError("REPORT_PROFILE_STRUCTURE_CHANGED")
        matches = _read_pattern(payload, _parse_json_path(str(mapping["json_path"])))
        if not matches and mapping.get("required"):
            raise WorkbenchPersistenceError("REPORT_PROFILE_STRUCTURE_CHANGED")
        expected_type = str(mapping.get("value_type", "string"))
        if any(value is not None and _value_type(value) != expected_type for _, value in matches):
            raise WorkbenchPersistenceError("REPORT_PROFILE_STRUCTURE_CHANGED")
        result[str(mapping["canonical_field"])] = [
            (indices, _normalize_value(value, mapping.get("normalizers", [])))
            for indices, value in matches
        ]
    return result


def extract_profile_collection_indices(
    discovery: ReportStructureDiscovery,
    mapping: dict[str, Any],
) -> tuple[tuple[int, ...], ...]:
    source_file = str(mapping["source_file"])
    payload = discovery.payloads.get(source_file)
    if payload is None:
        raise WorkbenchPersistenceError("REPORT_PROFILE_STRUCTURE_CHANGED")
    collection_path = _parse_json_path(str(mapping["collection_path"]))
    return tuple(indices for indices, _ in _read_pattern_nodes(payload, collection_path))


def _candidate_files(root: Path) -> list[_DiscoveryCandidateFile]:
    selected: list[_DiscoveryCandidateFile] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    visited_entries = 0
    while stack:
        directory, depth = stack.pop()
        entries: list[os.DirEntry[str]] = []
        try:
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    visited_entries += 1
                    if visited_entries > MAX_DISCOVERY_ENTRIES:
                        raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED")
                    entries.append(entry)
        except OSError as error:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_ACCESS_DENIED") from error
        for entry in sorted(entries, key=lambda item: item.name.casefold()):
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise WorkbenchPersistenceError("REPORT_DISCOVERY_ACCESS_DENIED") from error
            if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
                continue
            path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                if depth < MAX_DISCOVERY_DEPTH and not _is_excluded_directory(entry.name):
                    stack.append((path, depth + 1))
                continue
            if not entry.is_file(follow_symlinks=False) or path.suffix.casefold() not in _SUPPORTED_SUFFIXES:
                continue
            if info.st_size > MAX_DISCOVERY_FILE_BYTES:
                raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED")
            try:
                enumerated_identity = file_identity(path.lstat())
            except OSError as error:
                raise WorkbenchPersistenceError("REPORT_DISCOVERY_ACCESS_DENIED") from error
            try:
                enumerated_ancestors = ancestor_identities(path, root)
            except ReportParseInputError as error:
                raise WorkbenchPersistenceError("REPORT_DISCOVERY_ACCESS_DENIED") from error
            selected.append(_DiscoveryCandidateFile(
                path, enumerated_identity, enumerated_ancestors,
            ))
            if len(selected) > MAX_DISCOVERY_FILES:
                raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED")
    return sorted(
        selected,
        key=lambda item: item.path.relative_to(root).as_posix().casefold(),
    )


def _is_excluded_directory(name: str) -> bool:
    folded = unicodedata.normalize("NFKC", name).casefold()
    parts = tuple(part for part in re.split(r"[\s_\-:：./\\]+", folded) if part)
    normalized = "".join(parts)
    return (
        normalized.isdecimal()
        or normalized in _EXCLUDED_DIRECTORY_NAMES
        or any(part in _EXCLUDED_DIRECTORY_NAMES for part in parts)
        or any(
            normalized.startswith(marker) or normalized.endswith(marker)
            for marker in _EXCLUDED_DIRECTORY_EDGE_MARKERS
        )
        or any(marker in normalized for marker in _EXCLUDED_DIRECTORY_MARKERS)
    )


def _parse_data_literal(raw: bytes) -> Any:
    text = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise WorkbenchPersistenceError("REPORT_DISCOVERY_INVALID_METADATA")
    stripped = text.strip()
    payload_text = stripped
    if not stripped.startswith(("{", "[")):
        match = _ASSIGNMENT.fullmatch(stripped)
        if match is None:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_INVALID_METADATA")
        payload_text = match.group(1)
    try:
        return json.loads(
            payload_text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
            parse_float=_parse_finite_float,
        )
    except (json.JSONDecodeError, ValueError, RecursionError, MemoryError) as error:
        raise WorkbenchPersistenceError("REPORT_DISCOVERY_INVALID_METADATA") from error


def _validate_payload_shape(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    count = 0
    while stack:
        current, depth = stack.pop()
        count += 1
        if depth > MAX_JSON_DEPTH or count > MAX_JSON_NODES:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_BUDGET_EXCEEDED")
        if isinstance(current, dict):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _parse_finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON float")
    return result


def _scalar_leaves(value: Any, path: tuple[str | int, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _scalar_leaves(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _scalar_leaves(child, (*path, index))
    elif value is None or isinstance(value, (str, int, float, bool)):
        yield path, value


def _structure_nodes(value: Any, path: tuple[str | int, ...] = ()):
    if isinstance(value, dict):
        yield path, "object"
        for key, child in value.items():
            yield from _structure_nodes(child, (*path, str(key)))
    elif isinstance(value, list):
        yield path, "array"
        for member_shape in sorted({_shape_signature(child) for child in value}):
            yield path, f"array-member:{hashlib.sha256(member_shape.encode('utf-8')).hexdigest()}"
        for child in value:
            # 数组位置属于实例值；结构只保留成员骨架。
            yield from _structure_nodes(child, (*path, "*"))
    else:
        yield path, _value_type(value)


def _shape_signature(value: Any) -> str:
    if isinstance(value, dict):
        return "object{" + ",".join(
            f"{json.dumps(str(key), ensure_ascii=False)}:{_shape_signature(child)}"
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        ) + "}"
    if isinstance(value, list):
        return "array[" + ",".join(sorted({_shape_signature(child) for child in value})) + "]"
    return _value_type(value)


def _json_path(tokens: tuple[str, ...]) -> str:
    return "$" + "".join("/" + token.replace("~", "~0").replace("/", "~1") for token in tokens)


def _collection_path(tokens: tuple[str, ...], *, material: bool = False) -> str:
    wildcard = max((index for index, token in enumerate(tokens) if token == "*"), default=-1)
    if wildcard >= 0:
        return _json_path(tokens[:wildcard + 1])
    return _json_path(tokens[:-1]) if material and tokens else "$"


def _parse_json_path(value: str) -> tuple[str, ...]:
    if value == "$":
        return ()
    if not value.startswith("$/"):
        raise WorkbenchPersistenceError("REPORT_PROFILE_INVALID")
    return tuple(token.replace("~1", "/").replace("~0", "~") for token in value[2:].split("/"))


def _read_pattern(value: Any, tokens: tuple[str, ...], indices: tuple[int, ...] = ()):
    if not tokens:
        if value is None or isinstance(value, (str, int, float, bool)):
            return [(indices, value)]
        return []
    head, *tail = tokens
    if head == "*":
        if not isinstance(value, list):
            return []
        return [
            item
            for index, child in enumerate(value)
            for item in _read_pattern(child, tuple(tail), (*indices, index))
        ]
    if not isinstance(value, dict) or head not in value:
        return []
    return _read_pattern(value[head], tuple(tail), indices)


def _read_pattern_nodes(
    value: Any, tokens: tuple[str, ...], indices: tuple[int, ...] = (),
):
    if not tokens:
        return [(indices, value)]
    head, *tail = tokens
    if head == "*":
        if not isinstance(value, list):
            return []
        return [
            item
            for index, child in enumerate(value)
            for item in _read_pattern_nodes(child, tuple(tail), (*indices, index))
        ]
    if not isinstance(value, dict) or head not in value:
        return []
    return _read_pattern_nodes(value[head], tuple(tail), indices)


def _normalize_value(value: Any, normalizers: Any) -> str:
    result = "" if value is None else str(value)
    if "trim" in normalizers:
        result = result.strip()
    return result


def _normalize_key(value: Any) -> str:
    return re.sub(r"[\s_\-:：./\\]+", "", str(value)).casefold()


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def _preview(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text[:120]


def _candidate_id(canonical_field: str, relative: str, json_path: str) -> str:
    digest = hashlib.sha256(f"{canonical_field}\0{relative}\0{json_path}".encode("utf-8")).hexdigest()[:24]
    return f"candidate-{digest}"


def _digest_rows(rows: list[str]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


__all__ = [
    "DiscoveryDependency", "ReportStructureDiscovery", "discover_report_structure",
    "extract_profile_collection_indices", "extract_profile_values",
    "MAX_DISCOVERY_DEPTH", "MAX_DISCOVERY_FILES",
    "MAX_DISCOVERY_FILE_BYTES", "MAX_DISCOVERY_TOTAL_BYTES",
    "MAX_DISCOVERY_ENTRIES", "MAX_JSON_DEPTH", "MAX_JSON_NODES",
]
