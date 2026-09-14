"""Layer 21：陌生结构候选确认、Profile 复用和统一快照编排。"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from ...repository.report.report_adapter_registry import select_report_adapter
from ...repository.report.report_format_adapter import ReportFormat
from ...repository.report.report_parse_input_models import DependencyRecord, ReportParseInputSnapshot
from ...repository.report.report_profile_discovery_repository import (
    ReportStructureDiscovery,
    discover_report_structure,
    extract_profile_collection_indices,
    extract_profile_values,
)
from ...repository.report.report_profile_repository import (
    REPORT_PROFILE_ADAPTER_ID,
    REPORT_PROFILE_ADAPTER_VERSION,
    ReportProfileRepository,
)
from ...repository.report.report_source_adapter import ReportAdapterDetectionError, ReportAdapterMatch
from ...repository.workbench.workbench_errors import WorkbenchPersistenceError

_SESSION_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class _DiscoverySession:
    source_root: Path
    structure_fingerprint: str
    expires_at: float


class ReportProfileService:
    """内置适配器未命中后才允许调用的 Profile 能力。"""

    def __init__(self, database: Any) -> None:
        self.repository = ReportProfileRepository(database)
        self._sessions: dict[str, _DiscoverySession] = {}
        self._lock = Lock()

    def prepare_selection(self, source_dir: str | Path) -> dict[str, Any]:
        """已知格式直接返回；未知格式发现候选或复用 confirmed Profile。"""
        resolved = Path(source_dir).resolve(strict=True)
        try:
            match = select_report_adapter(resolved).detect(resolved)
            return {"kind": "builtin", "adapter": _public_match(match)}
        except ReportAdapterDetectionError as error:
            if str(error) != "REPORT_ADAPTER_NOT_FOUND":
                raise
        discovery = discover_report_structure(resolved)
        profile = self.repository.find_confirmed(discovery.structure_fingerprint)
        if profile is not None:
            try:
                _validated_values(discovery, profile)
            except WorkbenchPersistenceError as error:
                if error.code not in {
                    "REPORT_PROFILE_STRUCTURE_CHANGED",
                    "REPORT_PROFILE_CARDINALITY_INVALID",
                    "REPORT_PROFILE_MATERIAL_COLLECTION_CONFLICT",
                }:
                    raise
            else:
                return {"kind": "profile", "profile": _public_profile(profile)}
        token = f"discovery-{secrets.token_hex(16)}"
        with self._lock:
            self._purge_expired_locked()
            self._sessions[token] = _DiscoverySession(
                resolved,
                discovery.structure_fingerprint,
                time.monotonic() + _SESSION_TTL_SECONDS,
            )
        return {"kind": "discovery", "discovery_token": token, **discovery.public()}

    def confirm(
        self,
        discovery_token: str,
        candidate_ids: list[str],
        display_name: str,
    ) -> tuple[dict[str, Any], Path]:
        session = self._session(discovery_token)
        discovery = discover_report_structure(session.source_root)
        if discovery.structure_fingerprint != session.structure_fingerprint:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_STRUCTURE_CHANGED")
        selected = _select_candidates(discovery, candidate_ids)
        _validate_selected_mappings(discovery, selected)
        profile = self.repository.save_confirmed(
            profile_id=f"report-profile-{secrets.token_hex(16)}",
            display_name=display_name,
            structure_fingerprint=discovery.structure_fingerprint,
            mappings=selected,
        )
        with self._lock:
            self._sessions.pop(discovery_token, None)
        return _public_profile(profile), session.source_root

    def detect_confirmed(self, source_dir: str | Path) -> ReportAdapterMatch:
        discovery = discover_report_structure(source_dir)
        profile = self.repository.find_confirmed(discovery.structure_fingerprint)
        if profile is None:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_NOT_FOUND")
        try:
            _validated_values(discovery, profile)
        except WorkbenchPersistenceError as error:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_NOT_FOUND") from error
        return ReportAdapterMatch(
            adapter_id=REPORT_PROFILE_ADAPTER_ID,
            adapter_version=REPORT_PROFILE_ADAPTER_VERSION,
            report_format=ReportFormat.PROFILE,
            structure_fingerprint=discovery.structure_fingerprint,
            source_fingerprint=discovery.source_fingerprint,
            profile_id=str(profile["profile_id"]),
            profile_version=int(profile["version"]),
        )

    def build_snapshot(
        self, source_dir: str | Path, profile_id: str, profile_version: int,
    ) -> ReportParseInputSnapshot:
        profile = self.repository.get(profile_id, profile_version)
        if profile["status"] != "confirmed":
            raise WorkbenchPersistenceError("REPORT_PROFILE_NOT_CONFIRMED")
        discovery = discover_report_structure(source_dir)
        if discovery.structure_fingerprint != profile["structure_fingerprint"]:
            raise WorkbenchPersistenceError("REPORT_PROFILE_STRUCTURE_CHANGED")
        values = _validated_values(discovery, profile)
        return _snapshot(discovery, profile, values)

    def parse_report(
        self, source_dir: str | Path, output_dir: str | Path,
        profile_id: str, profile_version: int,
    ) -> dict[str, Any]:
        from .report_parser_service import _build_parse_result

        snapshot = self.build_snapshot(source_dir, profile_id, profile_version)
        return _build_parse_result(
            str(source_dir), str(output_dir), False, input_snapshot=snapshot,
        )

    def _session(self, token: str) -> _DiscoverySession:
        with self._lock:
            self._purge_expired_locked()
            session = self._sessions.get(token)
        if session is None:
            raise WorkbenchPersistenceError("REPORT_DISCOVERY_SESSION_EXPIRED")
        return session

    def _purge_expired_locked(self) -> None:
        now = time.monotonic()
        self._sessions = {
            token: session for token, session in self._sessions.items()
            if session.expires_at > now
        }


def _validated_values(
    discovery: ReportStructureDiscovery,
    profile: dict[str, Any],
) -> dict[str, list[tuple[tuple[int, ...], str]]]:
    values = extract_profile_values(discovery, profile["mappings"])
    _validate_selected_mappings(discovery, profile["mappings"], values=values)
    return values


def _select_candidates(
    discovery: ReportStructureDiscovery, candidate_ids: list[str],
) -> list[dict[str, Any]]:
    if not candidate_ids:
        raise WorkbenchPersistenceError("REPORT_PROFILE_SELECTION_REQUIRED")
    available = {str(item["candidate_id"]): item for item in discovery.candidates}
    selected: list[dict[str, Any]] = []
    fields: set[str] = set()
    for candidate_id in candidate_ids:
        candidate = available.get(str(candidate_id))
        if candidate is None:
            raise WorkbenchPersistenceError("REPORT_PROFILE_CANDIDATE_INVALID")
        field = str(candidate["canonical_field"])
        if field in fields:
            raise WorkbenchPersistenceError("REPORT_PROFILE_FIELD_CONFLICT")
        fields.add(field)
        selected.append({
            "canonical_field": field,
            "source_file": candidate["source_file"],
            "json_path": candidate["json_path"],
            "collection_path": candidate["collection_path"],
            "value_type": candidate["value_type"],
            "normalizers": ["trim"],
            "required": True,
            "confidence": candidate["confidence"],
            "evidence": candidate["evidence"],
            "confirmation": "userConfirmed",
        })
    return selected


def _validate_selected_mappings(
    discovery: ReportStructureDiscovery,
    mappings: list[dict[str, Any]],
    *,
    values: dict[str, list[tuple[tuple[int, ...], str]]] | None = None,
) -> None:
    resolved_values = values if values is not None else extract_profile_values(discovery, mappings)
    material_anchor: tuple[str, str] | None = None
    material_indices: tuple[tuple[int, ...], ...] | None = None
    for mapping in mappings:
        field = str(mapping["canonical_field"])
        matches = resolved_values.get(field, [])
        if not field.startswith("material."):
            if len(matches) != 1 or matches[0][0]:
                raise WorkbenchPersistenceError("REPORT_PROFILE_CARDINALITY_INVALID")
            continue
        anchor = (str(mapping["source_file"]), str(mapping["collection_path"]))
        indices = tuple(item_indices for item_indices, _ in matches)
        expected_indices = extract_profile_collection_indices(discovery, mapping)
        if indices != expected_indices:
            raise WorkbenchPersistenceError("REPORT_PROFILE_MATERIAL_COLLECTION_CONFLICT")
        if material_anchor is None:
            material_anchor = anchor
            material_indices = indices
        elif anchor != material_anchor or indices != material_indices:
            raise WorkbenchPersistenceError("REPORT_PROFILE_MATERIAL_COLLECTION_CONFLICT")


def _snapshot(
    discovery: ReportStructureDiscovery,
    profile: dict[str, Any],
    values: dict[str, list[tuple[tuple[int, ...], str]]],
) -> ReportParseInputSnapshot:
    def scalar(field: str) -> str:
        matches = values.get(field, [])
        return matches[0][1] if matches else ""

    material_fields = {
        field: matches for field, matches in values.items() if field.startswith("material.")
    }
    material_keys = sorted({
        indices for matches in material_fields.values() for indices, _ in matches
    }) if material_fields else []
    mapping_by_field = {
        str(item["canonical_field"]): item for item in profile["mappings"]
    }
    material_source = str(next(
        (
            mapping["source_file"]
            for field, mapping in mapping_by_field.items()
            if field.startswith("material.")
        ),
        discovery.dependencies[0].relative_path,
    ))
    rows: list[dict[str, str]] = []
    bases: dict[str, dict[str, str]] = {}
    source_files: dict[str, str] = {}
    for order, indices in enumerate(material_keys, start=1):
        material_id = f"profile-material-{order}"

        def material_value(field: str) -> str:
            return next(
                (
                    value for item_indices, value in material_fields.get(field, [])
                    if item_indices == indices
                ),
                "",
            )

        rows.append({
            "material_id": material_id,
            "evidence_number": material_value("material.evidence_number"),
            "device_name": material_value("material.name"),
            "start_time": material_value("material.acquisition_started_at"),
            "end_time": material_value("material.acquisition_ended_at"),
        })
        bases[material_id] = {
            "device_name": material_value("material.name"),
            "model": material_value("material.model"),
            "holder_name": material_value("material.holder_name"),
            "imei1": material_value("material.imei1"),
            "imei2": material_value("material.imei2"),
            "serial_number": material_value("material.serial_number"),
            "device_type": material_value("material.type"),
        }
        source_files[material_id] = material_source
    case_mapping = next(
        (
            mapping for field, mapping in mapping_by_field.items()
            if field.startswith("case.")
        ),
        None,
    )
    report_mapping = next(
        (
            mapping for field, mapping in mapping_by_field.items()
            if field.startswith("software.")
        ),
        case_mapping,
    )
    software_name = scalar("software.name")
    software_version = scalar("software.version")
    return ReportParseInputSnapshot(
        source_key=(
            f"profile:{profile['profile_id']}@{profile['version']}:"
            f"{discovery.structure_fingerprint}"
        ),
        report_format=ReportFormat.PROFILE,
        adapter_id=REPORT_PROFILE_ADAPTER_ID,
        adapter_version=REPORT_PROFILE_ADAPTER_VERSION,
        structure_fingerprint=discovery.structure_fingerprint,
        case_info={
            "case_name": scalar("case.case_name"),
            "case_number": scalar("case.case_number"),
            "submit_unit": scalar("case.entrust_unit"),
            "submit_person": scalar("case.entrust_persons"),
            "create_time": scalar("case.created_at"),
            "report_time": scalar("case.reported_at"),
            "case_summary": scalar("case.case_summary"),
        },
        device_rows=tuple(rows),
        report_info={
            "main_software": {
                "name": software_name,
                "version": software_version,
                "status": "confirmed_by_user" if software_name and software_version else "unconfirmed",
                "candidates": [],
            },
            "hardware_device": scalar("inspection.hardware_device"),
        },
        case_source_file=str(
            case_mapping["source_file"] if case_mapping else discovery.dependencies[0].relative_path
        ),
        report_source_file=str(
            report_mapping["source_file"] if report_mapping else discovery.dependencies[0].relative_path
        ),
        device_source_files=source_files,
        evidence_directories={},
        device_base_info=bases,
        dependencies=tuple(
            DependencyRecord(
                relative_path=item.relative_path,
                size_bytes=item.size_bytes,
                modified_time_ns=item.modified_time_ns,
                stable_identity=item.content_digest,
                content_digest=item.content_digest,
            )
            for item in discovery.dependencies
        ),
        dependency_fingerprint=discovery.source_fingerprint,
        parsed_files=tuple(item.relative_path for item in discovery.dependencies),
        preserve_material_order=True,
        field_mappings={
            str(item["canonical_field"]): dict(item)
            for item in profile["mappings"]
        },
    )


def _public_match(match: ReportAdapterMatch) -> dict[str, Any]:
    return {
        "adapter_id": match.adapter_id,
        "adapter_version": match.adapter_version,
        "structure_fingerprint": match.structure_fingerprint,
    }


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        key: profile[key]
        for key in (
            "profile_id", "version", "display_name", "structure_fingerprint",
            "adapter_id", "adapter_version", "status", "mappings",
            "created_at", "updated_at",
        )
    }


__all__ = ["ReportProfileService"]
