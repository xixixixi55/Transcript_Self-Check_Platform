"""Synchronous archive orchestration: gate, plan, execute, validate, hash, publish."""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..repository.archive_authorization_repository import AuthorizedInputRoot
from ..repository.archive_input_repository import ArchiveInputError, verify_input_inventory
from ..repository.archive_manifest_repository import (
    ArchiveManifestRepository, ArchiveManifestRepositoryError)
from ..repository.filesystem_identity_repository import directory_content_fingerprint
from ..repository.archive_validator_repository import validate_archive_parts
from ..repository.winrar_discovery_repository import WinRarCapability, discover_winrar
from ..repository.winrar_executor_repository import ArchiveExecutionError, WinRarExecutor
from .archive_manifest_service import assemble_archive_manifest, validate_manifest_files
from .archive_manifest_access_service import (
    ArchiveGateError, archive_report_fingerprint as _fingerprint, get_valid_manifest)
from .archive_planner_service import (
    ArchiveDiagnostic, ArchivePlan, ArchivePolicy, ArchiveSourceEntry,
    PRODUCTION_ARCHIVE_POLICY, plan_archive, replan_to_next_tier)
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveManifestRecord
from .archive_manifest_reuse_service import restore_persisted_manifest
from .archive_attempt_service import ArchiveAttemptService
from .archive_attempt_completion_service import record_attempt_completion
from .export_gate_service import ExportGateCode, ExportGateIssue
from .archive_gate_policy_service import pre_archive_gate, raise_gate, with_archive_gate
from .archive_publish_service import publish_staged_archive
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
    attempt_id: str | None = None,
    attempt_service: ArchiveAttemptService | None = None,
    workbench_context_id: str | None = None,
    stage_observer: Callable[[str], None] | None = None,
    activity_observer: Callable[[Path], None] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> ArchiveExecutionOutcome:
    """Run at most one initial execution plus two upward replans per context."""
    context = ARCHIVE_RUNTIME_STORE.acquire_context(context_id)
    success = False
    successful_manifest_id: str | None = None
    final_state = "failed"
    registry = ArchiveManifestRepository(output_root)
    try:
        pre_gate = pre_archive_gate(report)
        raise_gate(pre_gate)
        _observe(stage_observer, "inventory")
        first_disc_number = str((report.get("attachments") or {}).get("disc_number"))
        ARCHIVE_RUNTIME_STORE.validate_context_authorization(context)
        verify_input_inventory(context.inventory)
        try:
            context.input_fingerprint = directory_content_fingerprint(context.inventory.source_root)
        except Exception as error:
            raise ArchiveGateError((ExportGateIssue(
                ExportGateCode.ARCHIVE_INPUT_CHANGED, "archive", "归档输入在执行前已变化。",
            ),)) from error
        if context.inventory.total_input_bytes <= 0:
            raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_INPUT_EMPTY, "archive", "归档输入不能为空。"),))
        fingerprint = _fingerprint(report, context.inventory, first_disc_number)
        registry.mark_source_changed(
            source_key=context.source_key,
            input_fingerprint=context.input_fingerprint,
            archive_fingerprint=fingerprint,
        )
        reusable = ARCHIVE_RUNTIME_STORE.find_reusable(context_id, fingerprint)
        if reusable and validate_manifest_files(reusable) is None:
            record_attempt_completion(
                attempt_service, attempt_id, registry, context, fingerprint, reusable,
                workbench_context_id,
            )
            success = True
            successful_manifest_id = reusable.manifest_id
            registry.touch(reusable.manifest_id)
            return ArchiveExecutionOutcome("completed", reusable.manifest_id, None, reused=True)
        if reusable:
            registry.mark_invalid(reusable.manifest_id)
        persisted = restore_persisted_manifest(context, fingerprint, registry)
        if persisted:
            record_attempt_completion(
                attempt_service, attempt_id, registry, context, fingerprint, persisted,
                workbench_context_id,
            )
            success = True
            successful_manifest_id = persisted.manifest_id
            return ArchiveExecutionOutcome("completed", persisted.manifest_id, None, reused=True)

        winrar = capability or discover_winrar(configured_winrar_path)
        raise_gate(with_archive_gate(pre_gate, winrar))
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
        _observe(stage_observer, "preflight_verified")
        staging_root = Path(output_root) / "compressed" / ".staging"
        marker_enabled = executor is None and attempt_id is not None and attempt_service is not None
        active_executor = executor or WinRarExecutor(
            staging_root,
            staging_initializer=attempt_service.staging_initializer(attempt_id) if marker_enabled else None,
            process_started_callback=attempt_service.process_started_callback(attempt_id) if marker_enabled else None,
            activity_callback=activity_observer,
            cancellation_check=cancellation_check,
        )
        retry_count = 0
        while True:
            try:
                context.execution_state = "compressing"
                _observe(stage_observer, "winrar")
                execution = active_executor.execute(plan, context.inventory.files, context.inventory.source_root, winrar)
            except ArchiveExecutionError as error:
                raise ArchiveGateError((ExportGateIssue(error.code, "archive", error.safe_message),)) from error
            if execution.returncode != 0:
                active_executor.cleanup(execution)
                raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_EXECUTION_FAILED, "archive", "归档执行失败。"),))
            validation_kwargs = {"integrity_runner": integrity_runner} if integrity_runner else {}
            validation_kwargs["integrity_started_callback"] = (
                lambda: _observe(stage_observer, "integrity")
            )
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
                _observe(stage_observer, "integrity_verified")
                context.execution_state = "hashing"
                _observe(stage_observer, "md5")
                public_manifest, _paths = assemble_archive_manifest(
                    plan, validation, winrar, retry_count=retry_count,
                )
                _observe(stage_observer, "manifest")
                manifest_id = str(public_manifest["manifest_id"])
                final_dir = Path(output_root) / "compressed" / context_id / manifest_id
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                created_at = time.time()
                record = ArchiveManifestRecord(
                    manifest_id, context_id, fingerprint, public_manifest, final_dir,
                    created_at, created_at + 24 * 60 * 60,
                )
                publish_staged_archive(
                    execution.staging_dir, final_dir, record, report, context=context,
                    attempt_id=attempt_id if marker_enabled else None,
                    attempt_service=attempt_service if marker_enabled else None,
                    workbench_context_id=workbench_context_id,
                )
            except Exception as error:
                if execution.staging_dir.exists():
                    active_executor.cleanup(execution)
                raise ArchiveGateError((ExportGateIssue(ExportGateCode.ARCHIVE_PARTS_INVALID, "archive", "归档清单生成失败。"),)) from error
            ARCHIVE_RUNTIME_STORE.save_manifest(record)
            try:
                registry.save(
                    source_key=context.source_key,
                    input_fingerprint=context.input_fingerprint,
                    archive_fingerprint=fingerprint,
                    manifest_id=manifest_id,
                    final_dir=final_dir,
                    public_manifest=public_manifest,
                    created_at=created_at,
                    workbench_attempt_id=attempt_id,
                )
            except ArchiveManifestRepositoryError:
                # The current in-memory context remains usable; no archive file is removed.
                if attempt_id is not None:
                    raise
            record_attempt_completion(
                attempt_service, attempt_id, registry, context, fingerprint, record,
                workbench_context_id,
            )
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


def _observe(observer: Callable[[str], None] | None, stage: str) -> None:
    if observer is not None:
        observer(stage)
