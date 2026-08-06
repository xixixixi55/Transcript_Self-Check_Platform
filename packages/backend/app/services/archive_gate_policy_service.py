"""Existing Legacy archive gate composition kept outside attempt recovery."""

from __future__ import annotations

from ..repository.winrar_discovery_repository import WinRarCapability
from .archive_manifest_access_service import ArchiveGateError
from .export_gate_service import ExportGateInput, ExportGateResult, evaluate_export_gate
from .disc_sequence_service import parse_disc_sequence


def pre_archive_gate(report: dict) -> ExportGateResult:
    attachments = report.get("attachments") or {}
    disc_number = attachments.get("disc_number")
    if disc_number is not None and str(disc_number).strip():
        disc_result = parse_disc_sequence(str(disc_number))
        return evaluate_export_gate(
            ExportGateInput(
                disc_sequence_valid=disc_result.valid,
                disc_sequence_error_code=disc_result.error_code,
            )
        )
    # Deferred disc number: compression may start without it; the sequence is
    # mapped before export, where the export gate still requires a valid number.
    return evaluate_export_gate(ExportGateInput())


def with_archive_gate(result: ExportGateResult, capability: WinRarCapability) -> ExportGateResult:
    if result.blockers:
        return result
    return evaluate_export_gate(
        ExportGateInput(
            automatic_archive_required=True,
            winrar_available=capability.available and capability.supports_rar_volumes,
        )
    )


def raise_gate(result: ExportGateResult) -> None:
    if result.blockers:
        raise ArchiveGateError(tuple(result.blockers))
