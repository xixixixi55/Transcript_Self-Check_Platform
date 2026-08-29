"""在授权来源和发布边界上进行同步归档编排。"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from ...repository.archive_authorization_repository import AuthorizedInputRoot
from ...repository.filesystem_identity_repository import directory_fingerprint_matches
from ...repository.archive_manifest_repository import (
    ArchiveManifestRepository, ArchiveManifestRepositoryError,
)
from ...repository.archive_validator_repository import validate_archive_parts
from ...repository.winrar_discovery_repository import WinRarCapability, discover_winrar
from ...repository.winrar_executor_repository import ArchiveExecutionError, WinRarExecutor
from ...repository.workbench_errors import WorkbenchPersistenceError
from .archive_attempt_completion_service import record_attempt_completion
from .archive_attempt_service import ArchiveAttemptService
from .archive_manifest_access_service import (
    ArchiveGateError, archive_report_fingerprint as _fingerprint, get_valid_manifest,
)
from .archive_mapping_service import persist_archive_plan_for_attempt
from .archive_manifest_reuse_service import restore_persisted_manifest
from .archive_manifest_service import assemble_archive_manifest, validate_manifest_files
from .archive_planner_service import (
    ArchiveDiagnostic, ArchivePlan, ArchivePolicy, ArchiveSourceEntry,
    PRODUCTION_ARCHIVE_POLICY, plan_archive, replan_to_next_tier,
)
from ..disc_sequence_service import (
    generate_disc_numbers, parse_archive_medium_sequence, parse_disc_sequence,
)
from .archive_publish_service import publish_staged_archive
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveManifestRecord
from ..export_gate_service import (
    ExportGateCode, ExportGateInput, ExportGateIssue, ExportGateResult,
    evaluate_export_gate,
)
from ..hash_algorithm_service import report_hash_algorithm

_PUBLICATION_EVIDENCE_RETRIES = 3


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
    # 延迟光盘编号：压缩可在没有编号时开始；序号会在导出前映射，
    # 届时导出门禁仍要求有效编号。
    return evaluate_export_gate(ExportGateInput())


def with_archive_gate(
    result: ExportGateResult, capability: WinRarCapability,
) -> ExportGateResult:
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


@dataclass(frozen=True)
class ArchiveExecutionOutcome:
    status: str
    manifest_id: str | None
    plan: ArchivePlan | None
    diagnostics: tuple[ArchiveDiagnostic, ...] = ()
    reused: bool = False


def create_archive_context(
    authorized_input: AuthorizedInputRoot, report: dict, *, output_root: str,
    cleanup_root: str | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> str:
    case_name = report.get("introduction", {}).get("case_summary", "")
    return ARCHIVE_RUNTIME_STORE.create_context(
        authorized_input, str(case_name), output_root=output_root,
        cleanup_root=cleanup_root,
        cancellation_check=cancellation_check,
    ).context_id


def observe_stage(observer: Callable[[str], None] | None, stage: str) -> None:
    if observer is not None:
        observer(stage)


def find_reusable(
    runtime_store: Any, context_id: str, fingerprint: str,
    attempt_service: Any, attempt_id: str | None,
) -> Any:
    if attempt_service is not None and attempt_id is not None:
        return None
    return runtime_store.find_reusable(context_id, fingerprint)


def assert_source_unchanged(context: Any) -> None:
    try:
        unchanged = directory_fingerprint_matches(
            context.inventory.source_root, context.input_fingerprint,
        )
    except Exception as error:
        raise ArchiveGateError((ExportGateIssue(
            ExportGateCode.ARCHIVE_INPUT_CHANGED, "archive", "归档输入在执行期间无法确认。",
        ),)) from error
    if not unchanged:
        raise ArchiveGateError((ExportGateIssue(
            ExportGateCode.ARCHIVE_INPUT_CHANGED, "archive", "归档输入在执行期间发生变化。",
        ),))


def execute_archive(
    context_id: str, report: dict, *, output_root: str,
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
    context = ARCHIVE_RUNTIME_STORE.acquire_context(context_id)
    success = False
    successful_manifest_id: str | None = None
    final_state = "failed"
    registry = ArchiveManifestRepository(
        output_root,
        database=getattr(attempt_service, "database", None),
    )
    try:
        pre_gate = pre_archive_gate(report)
        raise_gate(pre_gate)
        observe_stage(stage_observer, "inventory")
        first_disc_number = str((report.get("attachments") or {}).get("disc_number") or "").strip() or None
        ARCHIVE_RUNTIME_STORE.validate_context_authorization(context)
        execution_inventory = context.inventory
        context.input_fingerprint = execution_inventory.metadata_fingerprint
        if execution_inventory.total_input_bytes <= 0:
            raise ArchiveGateError((ExportGateIssue(
                ExportGateCode.ARCHIVE_INPUT_EMPTY, "archive", "Archive input is empty.",
            ),))
        fingerprint = _fingerprint(
            report, execution_inventory,
            content_fingerprint=context.input_fingerprint,
        )
        registry.mark_source_changed(
            source_key=context.source_key, input_fingerprint=context.input_fingerprint,
            archive_fingerprint=fingerprint,
        )
        reusable = find_reusable(
            ARCHIVE_RUNTIME_STORE, context_id, fingerprint, attempt_service, attempt_id,
        )
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
        persisted = restore_persisted_manifest(
            context, fingerprint, registry, attempt_service=attempt_service,
            attempt_id=attempt_id,
        )
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
            for item in execution_inventory.files
        )
        case_display_name = str(
            (report.get("introduction") or {}).get("case_summary") or ""
        ).strip()
        plan = plan_archive(
            case_display_name, entries, first_disc_number=first_disc_number, policy=policy,
        )
        if plan.status != "planned":
            code = plan.diagnostics[0].code if plan.diagnostics else "ARCHIVE_PLAN_INVALID"
            raise ArchiveGateError((ExportGateIssue(code, "archive", "Archive plan rejected."),))
        observe_stage(stage_observer, "preflight_verified")
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
                observe_stage(stage_observer, "winrar")
                execution = active_executor.execute(
                    plan, execution_inventory.files, execution_inventory.source_root, winrar,
                )
            except ArchiveExecutionError as error:
                raise ArchiveGateError((ExportGateIssue(error.code, "archive", error.safe_message),)) from error
            if execution.returncode != 0:
                active_executor.cleanup(execution)
                raise ArchiveGateError((ExportGateIssue(
                    ExportGateCode.ARCHIVE_EXECUTION_FAILED, "archive", "Archive execution failed.",
                ),))
            validation_kwargs = {"integrity_runner": integrity_runner} if integrity_runner else {}
            validation_kwargs["integrity_started_callback"] = lambda: observe_stage(stage_observer, "integrity")
            validation = validate_archive_parts(execution.staging_dir, plan, winrar, **validation_kwargs)
            if not validation.valid:
                active_executor.cleanup(execution)
                if validation.replan_allowed and retry_count < plan.max_replan_attempts:
                    next_plan = replan_to_next_tier(plan, policy)
                    if next_plan and next_plan.status == "planned":
                        retry_count += 1
                        plan = next_plan
                        continue
                code = validation.diagnostic_code or ExportGateCode.ARCHIVE_PARTS_INVALID
                if validation.replan_allowed:
                    code = ExportGateCode.ARCHIVE_REPLAN_EXHAUSTED
                raise ArchiveGateError((ExportGateIssue(code, "archive", validation.safe_message),))
            try:
                publication_attempt = 0
                verified_output_md5s: dict[str, str] | None = None
                verified_business_hashes: dict[str, str] | None = None
                while True:
                    publication_report = report
                    publication_snapshot = None
                    if attempt_service is not None and attempt_id is not None:
                        try:
                            publication_snapshot = attempt_service.revalidate_before_publish(
                                attempt_id, report,
                            )
                        except WorkbenchPersistenceError as error:
                            if (
                                error.code == "ARCHIVE_ATTEMPT_BINDING_STALE"
                                and publication_attempt < _PUBLICATION_EVIDENCE_RETRIES
                            ):
                                publication_attempt += 1
                                continue
                            raise
                        publication_report = publication_snapshot.report
                    latest_disc = str(
                        (publication_report.get("attachments") or {}).get("disc_number") or ""
                    ).strip()
                    raise_gate(pre_archive_gate(publication_report))
                    parsed_disc = parse_archive_medium_sequence(latest_disc, plan.archive_mode)
                    first_disc_number = (
                        parsed_disc.sequence.first_disc_number
                        if parsed_disc.valid and parsed_disc.sequence is not None else None
                    )
                    plan = replace(
                        plan,
                        first_disc_number=first_disc_number,
                        expected_disc_numbers=tuple(generate_disc_numbers(
                            first_disc_number, plan.expected_part_count,
                        )) if first_disc_number else (),
                    )
                    fingerprint = _fingerprint(
                        publication_report, execution_inventory,
                        content_fingerprint=context.input_fingerprint,
                    )
                    observe_stage(stage_observer, "integrity_verified")
                    observe_stage(stage_observer, "md5")
                    business_algorithm = report_hash_algorithm(publication_report)
                    public_manifest, _ = assemble_archive_manifest(
                        plan, validation, winrar, retry_count=retry_count,
                        verified_md5s=verified_output_md5s,
                        business_hash_algorithm=business_algorithm,
                        verified_business_hashes=verified_business_hashes,
                    )
                    if verified_output_md5s is None:
                        verified_output_md5s = {
                            str(part["filename"]): str(part["md5"])
                            for part in public_manifest["parts"]
                        }
                    if verified_business_hashes is None:
                        verified_business_hashes = {
                            str(part["filename"]): str(part["hash_value"])
                            for part in public_manifest["parts"]
                        }
                    observe_stage(stage_observer, "manifest")
                    manifest_id = str(public_manifest["manifest_id"])
                    final_dir = Path(output_root) / "compressed" / context_id / manifest_id
                    final_dir.parent.mkdir(parents=True, exist_ok=True)
                    created_at = time.time()
                    record = ArchiveManifestRecord(
                        manifest_id, context_id, fingerprint, public_manifest, final_dir,
                        created_at, created_at + 24 * 60 * 60,
                    )
                    try:
                        verified_output_identities = publish_staged_archive(
                            execution.staging_dir, final_dir, record, publication_report,
                            context=context,
                            attempt_id=attempt_id if marker_enabled else None,
                            attempt_service=attempt_service if marker_enabled else None,
                            workbench_context_id=workbench_context_id,
                            expected_draft_revision=(
                                publication_snapshot.draft_revision if publication_snapshot else None
                            ),
                            expected_report_fingerprint=(
                                publication_snapshot.report_fingerprint if publication_snapshot else None
                            ),
                            verified_md5s=verified_output_md5s,
                        )
                        break
                    except WorkbenchPersistenceError as error:
                        if (
                            error.code == "ARCHIVE_ATTEMPT_BINDING_STALE"
                            and publication_attempt < _PUBLICATION_EVIDENCE_RETRIES
                        ):
                            publication_attempt += 1
                            continue
                        raise
            except ArchiveGateError:
                if execution.staging_dir.exists():
                    active_executor.cleanup(execution)
                raise
            except WorkbenchPersistenceError as error:
                if execution.staging_dir.exists():
                    active_executor.cleanup(execution)
                message = (
                    "草稿或来源在归档期间发生了不允许的变化，请重新确认后归档。"
                    if error.code == "ARCHIVE_ATTEMPT_BINDING_STALE"
                    else "归档发布未完成，请重试。"
                )
                raise ArchiveGateError((ExportGateIssue(
                    error.code, "archive", message,
                ),)) from error
            except Exception as error:
                if execution.staging_dir.exists():
                    active_executor.cleanup(execution)
                raise ArchiveGateError((ExportGateIssue(
                    "ARCHIVE_PUBLISH_FAILED", "archive", "Archive publication failed.",
                ),)) from error
            ARCHIVE_RUNTIME_STORE.save_manifest(record)
            try:
                registry.save(
                    source_key=context.source_key, input_fingerprint=context.input_fingerprint,
                    archive_fingerprint=fingerprint, manifest_id=manifest_id,
                    final_dir=final_dir, public_manifest=public_manifest,
                    created_at=created_at, workbench_attempt_id=attempt_id,
                    publication_id=record.publication_id,
                    publication_digest=record.publication_digest,
                )
            except ArchiveManifestRepositoryError:
                if attempt_id is not None:
                    raise
            record_attempt_completion(
                attempt_service, attempt_id, registry, context, fingerprint, record,
                workbench_context_id, verified_md5s=verified_output_md5s,
                verified_file_identities=verified_output_identities,
            )
            try:  # 计划投影仅尽力执行；归档已经成功
                persist_archive_plan_for_attempt(attempt_service, attempt_id, plan, public_manifest)
            except Exception:
                pass
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
    finally:
        ARCHIVE_RUNTIME_STORE.release_context(
            context_id, state=final_state if not success else "completed",
            successful_manifest_id=successful_manifest_id,
        )
