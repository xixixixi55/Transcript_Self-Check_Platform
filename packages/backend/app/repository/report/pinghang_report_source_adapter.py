"""Layer 20：平航 v1 原始事实到统一输入快照的来源适配器。"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from ..source.filesystem_identity_repository import normalized_directory_key
from .pinghang_report_adapter import (
    PINGHANG_ADAPTER_ID,
    PINGHANG_ADAPTER_VERSION,
    PinghangReportError,
    looks_like_pinghang_report,
    parse_pinghang_report,
)
from .report_format_adapter import ReportFormat
from .report_parse_input_filesystem import (
    directory_entries,
    file_identity,
    fingerprint_dependencies,
    read_dependency,
)
from .report_parse_input_models import (
    DependencyRecord,
    ReportParseInputError,
    ReportParseInputSnapshot,
)
from .report_source_adapter import (
    ReportAdapterDetectionError,
    ReportAdapterMatch,
)


PINGHANG_BUNDLE_ADAPTER_ID = "pinghang-mobile-multipath-bundle-v1"
PINGHANG_BUNDLE_ADAPTER_VERSION = "1.1.0"
_MAX_BUNDLE_PACKAGES = 256
_NATURAL_PART_RE = re.compile(r"(\d+)")


class PinghangReportSourceAdapter:
    family_id = "pinghang-mobile-multipath-v1"
    supported_adapter_ids = (PINGHANG_ADAPTER_ID, PINGHANG_BUNDLE_ADAPTER_ID)
    snapshot_before_inflight = True

    def matches(self, source_root: Path) -> bool:
        return looks_like_pinghang_report(source_root) or _looks_like_pinghang_bundle(
            source_root,
        )

    def detect(self, source_root: Path) -> ReportAdapterMatch:
        if not looks_like_pinghang_report(source_root):
            try:
                snapshot = _build_bundle_snapshot(source_root)
            except (PinghangReportError, ReportParseInputError) as error:
                raise ReportAdapterDetectionError(
                    "REPORT_ADAPTER_STRUCTURE_INVALID"
                ) from error
            return ReportAdapterMatch(
                adapter_id=snapshot.adapter_id,
                adapter_version=snapshot.adapter_version,
                report_format=snapshot.report_format,
                structure_fingerprint=snapshot.structure_fingerprint,
                source_fingerprint=snapshot.dependency_fingerprint,
            )
        try:
            facts = parse_pinghang_report(source_root)
        except PinghangReportError as error:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_STRUCTURE_INVALID") from error
        return ReportAdapterMatch(
            adapter_id=PINGHANG_ADAPTER_ID,
            adapter_version=PINGHANG_ADAPTER_VERSION,
            report_format=ReportFormat.PINGHANG,
            structure_fingerprint=facts.structure_fingerprint,
            source_fingerprint=_metadata_fingerprint(source_root, facts),
        )

    def build_snapshot(self, source_root: Path) -> ReportParseInputSnapshot:
        if not looks_like_pinghang_report(source_root):
            return _build_bundle_snapshot(source_root)
        return _build_single_snapshot(source_root)


def _build_single_snapshot(source_root: Path) -> ReportParseInputSnapshot:
    dependencies: dict[str, DependencyRecord] = {}

    def read_file(path: Path) -> bytes:
        return read_dependency(path, source_root, dependencies)

    try:
        facts = parse_pinghang_report(source_root, read_file=read_file)
    except PinghangReportError as error:
        raise ReportParseInputError("平航报告结构不受支持。") from error
    records = tuple(sorted(
        dependencies.values(), key=lambda item: item.relative_path.casefold(),
    ))
    return ReportParseInputSnapshot(
        source_key=normalized_directory_key(str(source_root)),
        report_format=ReportFormat.PINGHANG,
        adapter_id=PINGHANG_ADAPTER_ID,
        adapter_version=PINGHANG_ADAPTER_VERSION,
        structure_fingerprint=facts.structure_fingerprint,
        case_info=facts.case_info,
        device_rows=facts.device_rows,
        report_info=facts.report_info,
        case_source_file=facts.case_source_file,
        report_source_file=facts.report_source_file,
        device_source_files=facts.device_source_files,
        holder_source_files=facts.holder_source_files,
        evidence_directories={},
        device_base_info=facts.device_base_info,
        dependencies=records,
        dependency_fingerprint=fingerprint_dependencies(
            records, PINGHANG_ADAPTER_ID, PINGHANG_ADAPTER_VERSION,
            facts.structure_fingerprint,
        ),
        parsed_files=("entry", "navigation", "case", "report", "materials"),
        preserve_material_order=True,
    )


def _build_bundle_snapshot(source_root: Path) -> ReportParseInputSnapshot:
    package_roots = _bundle_package_roots(source_root)
    dependencies: dict[str, DependencyRecord] = {}

    def read_file(path: Path) -> bytes:
        return read_dependency(path, source_root, dependencies)

    try:
        packages = [
            (package_root, parse_pinghang_report(package_root, read_file=read_file))
            for package_root in package_roots
        ]
    except PinghangReportError as error:
        raise ReportParseInputError("平航多报告包结构不受支持。") from error

    first_root, first = packages[0]
    if any(facts.case_info != first.case_info for _, facts in packages[1:]):
        raise ReportParseInputError("平航多报告包案件信息不一致。")
    if any(facts.report_info != first.report_info for _, facts in packages[1:]):
        raise ReportParseInputError("平航多报告包软件信息不一致。")

    rows: list[dict[str, str]] = []
    bases: dict[str, dict[str, str]] = {}
    device_sources: dict[str, str] = {}
    holder_sources: dict[str, str] = {}
    evidence_numbers: set[str] = set()
    for package_root, facts in packages:
        prefix = package_root.relative_to(source_root).as_posix()
        for row in facts.device_rows:
            evidence_number = row["evidence_number"].strip()
            normalized = evidence_number.casefold()
            if not normalized or normalized in evidence_numbers:
                raise ReportParseInputError("平航多报告包包含重复检材编号。")
            evidence_numbers.add(normalized)
            material_id = row.get("material_id") or evidence_number
            rows.append(row)
            bases[material_id] = facts.device_base_info[material_id]
            device_sources[material_id] = _prefixed(
                prefix, facts.device_source_files[material_id],
            )
            holder_source = facts.holder_source_files.get(material_id)
            if holder_source:
                holder_sources[material_id] = _prefixed(prefix, holder_source)

    rows.sort(key=lambda row: _natural_key(row["evidence_number"]))
    structure = "\n".join((
        PINGHANG_BUNDLE_ADAPTER_ID,
        PINGHANG_BUNDLE_ADAPTER_VERSION,
        *(sorted(facts.structure_fingerprint for _, facts in packages)),
    ))
    structure_fingerprint = hashlib.sha256(structure.encode("utf-8")).hexdigest()
    records = tuple(sorted(
        dependencies.values(), key=lambda item: item.relative_path.casefold(),
    ))
    prefix = first_root.relative_to(source_root).as_posix()
    return ReportParseInputSnapshot(
        source_key=normalized_directory_key(str(source_root)),
        report_format=ReportFormat.PINGHANG,
        adapter_id=PINGHANG_BUNDLE_ADAPTER_ID,
        adapter_version=PINGHANG_BUNDLE_ADAPTER_VERSION,
        structure_fingerprint=structure_fingerprint,
        case_info=first.case_info,
        device_rows=tuple(rows),
        report_info=first.report_info,
        case_source_file=_prefixed(prefix, first.case_source_file),
        report_source_file=_prefixed(prefix, first.report_source_file),
        device_source_files=device_sources,
        holder_source_files=holder_sources,
        evidence_directories={},
        device_base_info=bases,
        dependencies=records,
        dependency_fingerprint=fingerprint_dependencies(
            records, PINGHANG_BUNDLE_ADAPTER_ID,
            PINGHANG_BUNDLE_ADAPTER_VERSION, structure_fingerprint,
        ),
        parsed_files=(
            "report_packages", "entry", "navigation", "case", "report", "materials",
        ),
        preserve_material_order=True,
    )


def _looks_like_pinghang_bundle(source_root: Path) -> bool:
    try:
        count = 0
        with os.scandir(source_root) as entries:
            for entry in entries:
                if (
                    entry.is_dir(follow_symlinks=False)
                    and (Path(entry.path) / "报告").is_dir()
                ):
                    count += 1
                    if count >= 2:
                        return True
    except OSError:
        return False
    return False


def _bundle_package_roots(source_root: Path) -> list[Path]:
    roots = [
        Path(entry.path) for entry in directory_entries(source_root)
        if (Path(entry.path) / "报告").is_dir()
    ]
    if len(roots) < 2 or len(roots) > _MAX_BUNDLE_PACKAGES:
        raise ReportParseInputError("平航多报告包数量不受支持。")
    return sorted(roots, key=lambda path: path.name.casefold())


def _prefixed(prefix: str, relative: str) -> str:
    return f"{prefix}/{relative}"


def _natural_key(value: str) -> tuple[tuple[int, object], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in _NATURAL_PART_RE.split(value)
        if part
    )


def _metadata_fingerprint(source_root: Path, facts) -> str:
    digest = hashlib.sha256()
    digest.update(facts.structure_fingerprint.encode("ascii"))
    for relative in facts.relative_files:
        digest.update(relative.encode("utf-8"))
        digest.update(str(file_identity((source_root / relative).stat())).encode("ascii"))
    return digest.hexdigest()


PINGHANG_REPORT_SOURCE_ADAPTER = PinghangReportSourceAdapter()

__all__ = [
    "PINGHANG_BUNDLE_ADAPTER_ID", "PINGHANG_BUNDLE_ADAPTER_VERSION",
    "PINGHANG_REPORT_SOURCE_ADAPTER", "PinghangReportSourceAdapter",
]
