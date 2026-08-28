"""第 20 层：为 Parser 输入快照安全选择候选项。"""

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
    "base", "basic", "info", "property", "data_",
)
_DEVICE_FILENAME_PRIORITY = {
    "device_metadata.json": 0,
    "device_table.json": 1,
    "device.json": 2,
}
# 受支持导出中的设备表将行标签放在 JSON 头部。由于普通 data_ 文件可能有数 MB，
# 应保持有限探测范围较小；完整解析器仍只读取通过该探测的文件。
_DATA_FILE_SCAN_BYTES = 16 * 1024
_STRUCTURED_DEVICE_LABELS = (
    "设备类型", "检材类型", "终端类型", "设备名称", "检材名称", "手机名称",
    "手机品牌", "设备品牌", "设备型号", "产品型号", "手机型号",
    "device_type", "material_type", "device_name", "phone_name", "phone_brand",
    "device_brand", "device_model", "product_model", "phone_model", "IMEI",
)


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
    """查找输出在 JC 证据目录旁、名称具体的设备目录。

    某种受支持的厂商导出将结构化设备行保存在 JC... 目录下，
    同时在同级输出以 ``Brand Model`` 命名的空 ``Base`` 目录。两棵目录树之间
    没有文件级关联，因此只能采用确定性名称顺序；仅当数量完全相同且名称具体时使用。
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
    include_data_files: bool = True,
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
            and (include_data_files or not _is_data_file(entry.name))
        ]
        role_files[role] = [Path(entry.path) for entry in candidate_entries]
        indexes.append(CandidateDirectoryIndex(
            f"{evidence_relative}/{role}", True,
            tuple(sorted(
                (_candidate_file_record(entry.path, data_root) for entry in candidate_entries),
                key=lambda item: item.relative_path.casefold(),
            )),
        ))
    named_files = [
        item for role in _METADATA_DIRECTORY_NAMES
        for item in role_files.get(role, [])
        if not _is_data_file(item.name)
    ]
    files = named_files or [
        item for role in _METADATA_DIRECTORY_NAMES
        for item in role_files.get(role, [])
        if _is_selected_data_file(item)
    ]
    if files:
        if report_format == ReportFormat.LEGACY:
            # 旧版解析器历来会合并指定 Base/Phone 元数据目录中的所有直接 JSON 文件。
            # 保留此规则，同时允许权威表位于 Phone、而 Base 目录仅包含辅助 data_ 文件的导出。
            return sorted(files, key=lambda item: str(item).casefold()), tuple(indexes)
        best_priority = min(_device_filename_priority(item.name) for item in files)
        selected = [
            item for item in files
            if _device_filename_priority(item.name) == best_priority
        ]
        return sorted(
            selected,
            key=lambda item: (
                _device_filename_priority(item.name), str(item).casefold(),
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
    return any(
        stem.startswith(marker) if marker == "data_" else marker in stem
        for marker in _DEVICE_FILENAME_MARKERS
    )


def _is_data_file(name: str) -> bool:
    return Path(name).stem.casefold().startswith("data_")


def _is_selected_data_file(path: Path) -> bool:
    """仅当 data_ JSON 的头部包含结构化表格时才选择它。

    大型导出会将普通证据表与设备元数据并列放置。有界标签探测可保持
    单次快照响应及时，且不依赖报告特定文件名或节点编号。
    """
    try:
        with path.open("rb") as stream:
            sample = stream.read(_DATA_FILE_SCAN_BYTES).decode("utf-8", errors="ignore")
    except OSError:
        return False
    return sum(label in sample for label in _STRUCTURED_DEVICE_LABELS) >= 2


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
