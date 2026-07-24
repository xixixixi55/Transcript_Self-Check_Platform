"""Internal models for one report Parser input snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from .report_format_adapter import ReportFormat


class ReportParseInputError(ValueError):
    """Safe diagnostics for an invalid or unstable parser input snapshot."""


@dataclass(frozen=True)
class DependencyRecord:
    relative_path: str
    size_bytes: int
    modified_time_ns: int
    stable_identity: str
    content_digest: str


@dataclass(frozen=True)
class CandidateFileRecord:
    relative_path: str
    size_bytes: int
    modified_time_ns: int
    stable_identity: str


@dataclass(frozen=True)
class CandidateDirectoryIndex:
    relative_directory: str
    exists: bool
    files: tuple[CandidateFileRecord, ...]


@dataclass(frozen=True)
class ReportParseInputSnapshot:
    """Internal parse state; never serialized into a report or public response."""

    source_key: str
    report_format: ReportFormat
    case_info: dict[str, str]
    device_rows: tuple[dict[str, str], ...]
    report_info: dict[str, str]
    evidence_directories: dict[str, str]
    device_base_info: dict[str, dict[str, str]]
    dependencies: tuple[DependencyRecord, ...]
    candidate_indexes: tuple[CandidateDirectoryIndex, ...]
    dependency_fingerprint: str


__all__ = [
    "CandidateDirectoryIndex", "CandidateFileRecord", "DependencyRecord",
    "ReportParseInputError", "ReportParseInputSnapshot",
]
