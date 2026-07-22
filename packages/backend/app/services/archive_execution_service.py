"""Synchronous archive orchestration: gate, plan, execute, validate, hash, publish."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..repository.archive_authorization_repository import AuthorizedInputRoot
from ..repository.archive_input_repository import ArchiveInputError, verify_input_inventory
from ..repository.archive_validator_repository import validate_archive_parts
from ..repository.winrar_discovery_repository import WinRarCapability, discover_winrar
from ..repository.winrar_executor_repository import ArchiveExecutionError, WinRarExecutor
from .archive_manifest_service import assemble_archive_manifest, validate_published_manifest
from .archive_manifest_access_service import (
    ArchiveGateError,
    archive_report_fingerprint as _fingerprint,
    get_valid_manifest,
)
from .archive_planner_service import (
    ArchiveDiagnostic,
    ArchivePlan,
    ArchivePolicy,
    ArchiveSourceEntry,
    PRODUCTION_ARCHIVE_POLICY,
    plan_archive,
    replan_to_next_tier,
)
from .archive_runtime_service import (
    ARCHIVE_RUNTIME_STORE,
    ArchiveManifestRecord,
)
from .export_gate_service import ExportGateCode, ExportGateInput, ExportGateIssue, ExportGateResult, evaluate_export_gate
from .disc_sequence_service import parse_disc_sequence

@dataclass(frozen=True)
class ArchiveExecutionOutcome:
    status: str
    manifest_id: str | None
    plan: ArchivePlan | None
    diagnostics: tuple[ArchiveDiagnostic, ...] = ()
    reused: bool = False

def create_archive_context(
    authorized_input: AuthorizedInputRoot,
    report: dict,
    *,
    output_root: str,
    cleanup_root: str | None = None,
) -> str:
    case_name = report.get("introduction", {}).get("case_summary", "")
    record = ARCHIVE_RUNTIME_STORE.create_context(
        authorized_input, str(case_name), output_root=output_root, cleanup_root=cleanup_root,
    )
    return record.context_id

def _pre_archive_gate(report: dict) -> ExportGateResult:
    attachments = report.get("attachments") or {}
    disc_result = parse_disc_sequence(attachments.get("disc_number"))
    return evaluate_export_gate(
        ExportGateInput(
            disc_sequence_valid=disc_result.valid,
            disc_sequence_error_code=disc_result.error_code,
        )
    )

def _with_archive_gate(result: ExportGateResult, capability: WinRarCapability) -> ExportGateResult:
    if result.blockers:
        return result
    return evaluate_export_gate(
        ExportGateInput(
            automatic_archive_required=True,
            winrar_available=capability.available and capability.supports_rar_volumes,
        )
    )

def _raise_gate(result: ExportGateResult) -> None:
    if result.blockers:
        raise ArchiveGateError(tuple(result.blockers))


def _diagnostic_for(code: str, message: str) -> ArchiveDiagnostic:
    return ArchiveDiagnostic(code, message)


def execute_archive(
    context_id: str,
    report: dict,
    *,
    output_root: str,
    configured_winrar_path: str | None = None,
    policy: ArchivePolicy = PRODUCTION_ARCHIVE_POLICY,
    capability: WinRarCapability | None = None,
    executor: WinRarExecutor | None = None,
    integrity_runner: Callable | None = None,
) -> ArchiveExecutionOutcome:
    """Run at most one initial execution plus two upward replans per context."""

    context = ARCHIVE_RUNTIME_STORE.acquire_context(context_id)
    success = False
    successful_manifest_id: str | None = None
    final_state = "failed"
    try:
        pre_gate = _pre_archive_gate(report)
        _raise_gate(pre_gate)
        first_disc_number = str((report.get("attachments") or {}).get("disc_number"))
        ARCHIVE_RUNTIME_STORE.validate_context_authorization(context)
        verify_input_inventory(context.inventory)
        if context.inventory.total_input_bytes <= 0:
            raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_INPUT_EMPTY, "archive", "归档输入不能为空。"),))

        fingerprint = _fingerprint(report, context.inventory, first_disc_number)
        reusable = ARCHIVE_RUNTIME_STORE.find_reusable(context_id, fingerprint)
        if reusable and validate_published_manifest(reusable):
            success = True
            successful_manifest_id = reusable.manifest_id
            return ArchiveExecutionOutcome("completed", reusable.manifest_id, None, reused=True)

        winrar = capability or discover_winrar(configured_winrar_path)
        _raise_gate(_with_archive_gate(pre_gate, winrar))

        entries = tuple(
            ArchiveSourceEntry(item.relative_path, item.size_bytes, item.modified_time_ns)
            for item in context.inventory.files
        )
        case_display_name = str(
            (report.get("introduction") or {}).get("case_summary") or ""
        ).strip()
        plan = plan_archive(
            case_display_name, entries,
            first_disc_number=first_disc_number, policy=policy,
        )
        if plan.status != "planned":
            code = plan.diagnostics[0].code if plan.diagnostics else "ARCHIVE_PLAN_INVALID"
            raise ArchiveGateError((ExportGateIssue(code, "archive", "归档计划未通过校验。"),))

        staging_root = Path(output_root) / "compressed" / ".staging"
        active_executor = executor or WinRarExecutor(staging_root)
        retry_count = 0
        while True:
            try:
                context.execution_state = "compressing"
                execution = active_executor.execute(plan, context.inventory.files, context.inventory.source_root, winrar)
            except ArchiveExecutionError as error:
                raise ArchiveGateError((ExportGateIssue(error.code, "archive", error.safe_message),)) from error
            if execution.returncode != 0:
                active_executor.cleanup(execution)
                raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_EXECUTION_FAILED, "archive", "归档执行失败。"),))
            validation_kwargs = {"integrity_runner": integrity_runner} if integrity_runner else {}
            context.execution_state = "validating"
            validation = validate_archive_parts(execution.staging_dir, plan, winrar, **validation_kwargs)
            if not validation.valid:
                active_executor.cleanup(execution)
                if validation.replan_allowed:
                    if retry_count >= plan.max_replan_attempts:
                        raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_REPLAN_EXHAUSTED, "archive", "归档重规划次数已用尽。"),))
                    next_plan = replan_to_next_tier(plan, policy)
                    if next_plan is None or next_plan.status != "planned":
                        raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_REPLAN_EXHAUSTED, "archive", "没有可用的更高归档档位。"),))
                    retry_count += 1
                    plan = next_plan
                    continue
                raise ArchiveGateError((ExportGateIssue(validation.diagnostic_code or ExportGateCode.ARCHIVE_PARTS_INVALID, "archive", validation.safe_message),))

            try:
                context.execution_state = "hashing"
                public_manifest, _paths = assemble_archive_manifest(
                    plan, validation, winrar, retry_count=retry_count,
                )
                manifest_id = str(public_manifest["manifest_id"])
                final_dir = Path(output_root) / "compressed" / context_id / manifest_id
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                os.replace(execution.staging_dir, final_dir)
                created_at = time.time()
                record = ArchiveManifestRecord(
                    manifest_id, context_id, fingerprint, public_manifest, final_dir,
                    created_at, created_at + 24 * 60 * 60,
                )
                if not validate_published_manifest(record):
                    shutil.rmtree(final_dir, ignore_errors=True)
                    raise ValueError("ARCHIVE_PARTS_INVALID")
            except Exception as error:
                if execution.staging_dir.exists():
                    active_executor.cleanup(execution)
                raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_PARTS_INVALID, "archive", "归档清单生成失败。"),)) from error
            ARCHIVE_RUNTIME_STORE.save_manifest(record)
            success = True
            final_state = "completed"
            successful_manifest_id = manifest_id
            return ArchiveExecutionOutcome("completed", manifest_id, plan)
    except ArchiveGateError as error:
        blocked_codes = {
            "WINRAR_UNAVAILABLE", "ARCHIVE_INPUT_EMPTY", "ARCHIVE_INPUT_CHANGED",
            "ARCHIVE_TOO_LARGE", "ARCHIVE_PLAN_INVALID", "DISC_SEQUENCE_INVALID",
            "FIRST_DISC_NUMBER_MISSING", "FIRST_DISC_NUMBER_INVALID",
        }
        codes = {str(item.code.value if hasattr(item.code, "value") else item.code) for item in error.blockers}
        final_state = "blocked" if codes & blocked_codes else "failed"
        raise
    except ArchiveInputError as error:
        raise ArchiveGateError((ExportGateIssue(error.code, "archive", error.safe_message),)) from error
    finally:
        ARCHIVE_RUNTIME_STORE.release_context(
            context_id,
            state=final_state if not success else "completed",
            successful_manifest_id=successful_manifest_id,
        )
