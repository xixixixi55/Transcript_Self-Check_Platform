"""Layer 20：平航 v1 原始事实到统一输入快照的来源适配器。"""

from __future__ import annotations

import hashlib
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


class PinghangReportSourceAdapter:
    family_id = "pinghang-mobile-multipath-v1"
    supported_adapter_ids = (PINGHANG_ADAPTER_ID,)
    snapshot_before_inflight = True

    def matches(self, source_root: Path) -> bool:
        return looks_like_pinghang_report(source_root)

    def detect(self, source_root: Path) -> ReportAdapterMatch:
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


def _metadata_fingerprint(source_root: Path, facts) -> str:
    digest = hashlib.sha256()
    digest.update(facts.structure_fingerprint.encode("ascii"))
    for relative in facts.relative_files:
        digest.update(relative.encode("utf-8"))
        digest.update(str(file_identity((source_root / relative).stat())).encode("ascii"))
    return digest.hexdigest()


PINGHANG_REPORT_SOURCE_ADAPTER = PinghangReportSourceAdapter()

__all__ = ["PINGHANG_REPORT_SOURCE_ADAPTER", "PinghangReportSourceAdapter"]
