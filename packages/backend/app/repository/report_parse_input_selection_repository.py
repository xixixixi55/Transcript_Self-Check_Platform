"""Layer 20: safe candidate selection for Parser input snapshots."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from .device_field_parser import is_generic_device_label
from .report_format_adapter import ReportFormat
from .report_parse_input_filesystem import directory_entries, file_entries, stable_identity
from .report_parse_input_models import (
    CandidateDirectoryIndex,
    CandidateFileRecord,
    ReportParseInputError,
)

_METADATA_DIRECTORY_NAMES = ("base", "phone")
_DEVICE_FILENAME_MARKERS = (
    "device", "phone", "mobile", "metadata", "equipment", "material",
    "base", "basic", "info", "property",
)
_DEVICE_FILENAME_PRIORITY = {
    "device_metadata.json": 0,
    "device_table.json": 1,
    "device.json": 2,
}


def build_evidence_directory_index(
    evidence_numbers: list[str], entries: list,
) -> dict[str, str]:
    exact = {entry.name: entry.path for entry in entries}
    normalized: dict[str, list[Path]] = {}
    for entry in entries:
        normalized.setdefault(_normalise_directory_name(entry.name), []).append(entry.path)
    result: dict[str, str] = {}
    for evidence_number in evidence_numbers:
        if evidence_number in exact:
            result[evidence_number] = str(exact[evidence_number])
            continue
        matches = normalized.get(_normalise_directory_name(evidence_number), [])
        if len(matches) == 1:
            result[evidence_number] = str(matches[0])
    return result


def find_vendor_device_names(
    evidence_numbers: list[str], entries: list,
) -> tuple[str, ...]:
    """Find concrete device-name directories emitted beside JC evidence dirs.

    One supported vendor export keeps the structured device rows under JC...
    directories but emits empty ``Base`` directories named ``Brand Model`` at
    the same level.  The export has no file-level relation between the two
    trees, so the only available association is a deterministic name order;
    it is used only when the counts match exactly and names are concrete.
    """
    evidence_keys = {_normalise_directory_name(item) for item in evidence_numbers}
    names: list[str] = []
    for entry in entries:
        if _normalise_directory_name(entry.name) in evidence_keys:
            continue
        if not _is_concrete_vendor_device_name(entry.name):
            continue
        children = {
            child.name.casefold(): child
            for child in directory_entries(Path(entry.path))
        }
        if "base" in children:
            names.append(entry.name.strip())
    return tuple(sorted(names, key=str.casefold))


def split_vendor_device_name(value: str) -> tuple[str, str]:
    parts = " ".join(str(value).split()).split(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])


def select_device_candidate_files(
    evidence_dir: str, data_root: Path, *, report_format: ReportFormat,
) -> tuple[list[Path], tuple[CandidateDirectoryIndex, ...]]:
    if not evidence_dir:
        return [], ()
    root = Path(evidence_dir)
    evidence_relative = root.relative_to(data_root).as_posix()
    directories = {
        entry.name.casefold(): entry
        for entry in directory_entries(root)
        if entry.name.casefold() in _METADATA_DIRECTORY_NAMES
    }
    role_files: dict[str, list[Path]] = {}
    indexes: list[CandidateDirectoryIndex] = []
    for role in _METADATA_DIRECTORY_NAMES:
        directory = directories.get(role)
        if directory is None:
            indexes.append(CandidateDirectoryIndex(
                f"{evidence_relative}/{role}", False, (),
            ))
            continue
        candidate_entries = [
            entry for entry in file_entries(directory.path)
            if is_json(entry.name) and is_device_metadata_name(entry.name)
        ]
        role_files[role] = [Path(entry.path) for entry in candidate_entries]
        indexes.append(CandidateDirectoryIndex(
            f"{evidence_relative}/{role}", True,
            tuple(sorted(
                (_candidate_file_record(entry.path, data_root) for entry in candidate_entries),
                key=lambda item: item.relative_path.casefold(),
            )),
        ))
    for role in _METADATA_DIRECTORY_NAMES:
        files = role_files.get(role, [])
        if files:
            if report_format == ReportFormat.LEGACY:
                # The Legacy parser historically merged all direct JSON files
                # in the named Base/Phone metadata directory. Keep that
                # compatibility rule without touching media or other report
                # directories; vendor files are often split across files.
                return sorted(files, key=lambda item: item.name.casefold()), tuple(indexes)
            best_priority = min(_device_filename_priority(item.name) for item in files)
            selected = [
                item for item in files
                if _device_filename_priority(item.name) == best_priority
            ]
            return sorted(
                selected,
                key=lambda item: (
                    _device_filename_priority(item.name), item.name.casefold(),
                ),
            ), tuple(indexes)
    return [], tuple(indexes)


def _candidate_file_record(path: str, data_root: Path) -> CandidateFileRecord:
    try:
        info = Path(path).stat()
        relative = Path(path).relative_to(data_root).as_posix()
    except (OSError, ValueError) as error:
        raise ReportParseInputError("candidate metadata unreadable") from error
    return CandidateFileRecord(
        relative, int(info.st_size), int(info.st_mtime_ns), stable_identity(info),
    )


def is_device_metadata_name(name: str) -> bool:
    stem = Path(name).stem.casefold()
    return any(marker in stem for marker in _DEVICE_FILENAME_MARKERS)


def is_json(name: str) -> bool:
    return name.casefold().endswith(".json")


def _is_concrete_vendor_device_name(value: str) -> bool:
    normalized = " ".join(str(value).split())
    parts = normalized.split(" ")
    return len(parts) >= 2 and not is_generic_device_label(normalized)


def _device_filename_priority(name: str) -> int:
    return _DEVICE_FILENAME_PRIORITY.get(name.casefold(), 10)


def _normalise_directory_name(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


__all__ = [
    "build_evidence_directory_index", "find_vendor_device_names",
    "is_device_metadata_name", "is_json", "select_device_candidate_files",
    "split_vendor_device_name",
]
