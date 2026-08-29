"""第 20 层报告子包：Parser 依赖 Manifest 的已验证序列化。"""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

from .report_parse_input_models import (
    CandidateDirectoryIndex,
    CandidateFileRecord,
    DependencyRecord,
)


def serialize_dependencies(dependencies: tuple[DependencyRecord, ...]) -> list[dict[str, object]]:
    return [
        {
            "relative_path": item.relative_path,
            "size_bytes": item.size_bytes,
            "modified_time_ns": item.modified_time_ns,
            "stable_identity": item.stable_identity,
            "content_digest": item.content_digest,
        }
        for item in dependencies
    ]


def serialize_candidate_indexes(indexes: tuple[CandidateDirectoryIndex, ...]) -> list[dict[str, object]]:
    return [
        {
            "relative_directory": index.relative_directory,
            "exists": index.exists,
            "files": [
                {
                    "relative_path": item.relative_path,
                    "size_bytes": item.size_bytes,
                    "modified_time_ns": item.modified_time_ns,
                    "stable_identity": item.stable_identity,
                }
                for item in index.files
            ],
        }
        for index in indexes
    ]


def parse_manifest(payload: dict[str, object]) -> tuple[
    tuple[DependencyRecord, ...] | None,
    tuple[CandidateDirectoryIndex, ...] | None,
]:
    if "dependencies" not in payload and "candidate_indexes" not in payload:
        return None, None
    return _parse_dependencies(payload.get("dependencies")), _parse_candidate_indexes(
        payload.get("candidate_indexes"),
    )


def _parse_dependencies(value: object) -> tuple[DependencyRecord, ...] | None:
    if not isinstance(value, list):
        return None
    parsed: list[DependencyRecord] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        relative, size, modified, stable, digest = (
            item.get("relative_path"), item.get("size_bytes"),
            item.get("modified_time_ns"), item.get("stable_identity"),
            item.get("content_digest"),
        )
        if (
            not _safe_relative(relative) or not _int_value(size)
            or not _int_value(modified) or not isinstance(stable, str)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            return None
        parsed.append(DependencyRecord(relative, size, modified, stable, digest))
    return tuple(parsed)


def _parse_candidate_indexes(value: object) -> tuple[CandidateDirectoryIndex, ...] | None:
    if not isinstance(value, list):
        return None
    parsed: list[CandidateDirectoryIndex] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        relative, exists, files = (
            item.get("relative_directory"), item.get("exists"), item.get("files"),
        )
        if not _safe_relative(relative) or not isinstance(exists, bool) or not isinstance(files, list):
            return None
        parsed_files: list[CandidateFileRecord] = []
        for file_item in files:
            if not isinstance(file_item, dict):
                return None
            file_path, size, modified, stable = (
                file_item.get("relative_path"), file_item.get("size_bytes"),
                file_item.get("modified_time_ns"), file_item.get("stable_identity"),
            )
            if not _safe_relative(file_path) or not _int_value(size) or not _int_value(modified) or not isinstance(stable, str):
                return None
            parsed_files.append(CandidateFileRecord(file_path, size, modified, stable))
        parsed.append(CandidateDirectoryIndex(relative, exists, tuple(parsed_files)))
    return tuple(parsed)


def _safe_relative(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return not (
        posix.is_absolute() or windows.is_absolute()
        or ".." in posix.parts or ".." in windows.parts or ":" in value
    )


def _int_value(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = ["parse_manifest", "serialize_candidate_indexes", "serialize_dependencies"]
