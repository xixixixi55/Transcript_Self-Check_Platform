"""旧版流水线的失败开放且不生成输出的 Shadow 观测。"""

from __future__ import annotations

from typing import Any, Mapping

from .archive_planner_service import ArchiveSourceEntry, plan_archive
from .attachment_plan_service import build_attachment_plan
from .canonical_adapter_service import canonical_to_inspection_report, inspection_report_to_canonical
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE, ArchiveRuntimeError
from .pipeline_runtime_service import PipelineSettings
from .shadow_comparison_service import compare_shadow_snapshots, snapshot_from_canonical, snapshot_from_legacy_report
from .shadow_archive_facts_service import validated_manifest, with_archive_facts
from .shadow_runtime_service import (
    SHADOW_RUNTIME_STORE, ShadowRunHandle, ShadowStageRecord, public_pipeline_metadata,
    shadow_runtime_failure,
)


PARSE_STAGE = "parse"
ARCHIVE_STAGE = "archive"
EXPORT_STAGE = "export"


def begin_shadow_stage(
    settings: PipelineSettings, context_id: str | None, stage: str,
) -> ShadowRunHandle | None:
    try:
        handle = SHADOW_RUNTIME_STORE.issue_stage(
            settings, context_id, stage, new_run=stage == PARSE_STAGE,
        )
        SHADOW_RUNTIME_STORE.record(
            handle.run_id,
            ShadowStageRecord(
                stage, "pending", diagnostic_codes=("SHADOW_OBSERVATION_QUEUED",),
                observation_point="queued", task_token=handle.task_token,
            ),
            task_token=handle.task_token,
        )
        return handle
    except Exception:
        return None


def run_shadow_parse(
    report: Mapping[str, Any], settings: PipelineSettings, context_id: str | None,
    *, run_id: str | None = None, task_token: str | None = None,
) -> dict[str, object]:
    handle = _handle(settings, context_id, run_id, task_token, PARSE_STAGE)
    if handle is None:
        return shadow_runtime_failure(settings, context_id, PARSE_STAGE)
    try:
        migration = inspection_report_to_canonical(report)
        comparison = compare_shadow_snapshots(
            snapshot_from_legacy_report(report), snapshot_from_canonical(migration.canonical_case), stage=PARSE_STAGE,
        )
        _record_comparison(handle, PARSE_STAGE, comparison, "after_legacy_parse")
    except Exception:
        _record_failure(handle, PARSE_STAGE, "SHADOW_PARSE_FAILED", "after_legacy_parse")
    return _summary(handle, settings, context_id, PARSE_STAGE)


def run_shadow_archive(
    context_id: str, report: Mapping[str, Any], manifest: Mapping[str, Any], context: Any,
    settings: PipelineSettings, *, legacy_plan: Any = None,
    canonical_source: Mapping[str, Any] | None = None,
    run_id: str | None = None, task_token: str | None = None,
) -> dict[str, object]:
    handle = _handle(settings, context_id, run_id, task_token, ARCHIVE_STAGE)
    if handle is None:
        return shadow_runtime_failure(settings, context_id, ARCHIVE_STAGE)
    context = _valid_context(handle, context_id, ARCHIVE_STAGE)
    if context is None:
        return _summary(handle, settings, context_id, ARCHIVE_STAGE)
    if not validated_manifest(manifest):
        _record_not_comparable(
            handle, ARCHIVE_STAGE, "SHADOW_ARCHIVE_MANIFEST_UNAVAILABLE", "after_legacy_archive",
        )
        return _summary(handle, settings, context_id, ARCHIVE_STAGE)
    try:
        migration = inspection_report_to_canonical(canonical_source or report)
        canonical_report = canonical_to_inspection_report(migration.canonical_case)
        legacy_plan = legacy_plan or build_attachment_plan(manifest, report)
        shadow_archive_plan = _build_shadow_archive_plan(migration.canonical_case, context)
        comparison = _compare_archive(
            report, canonical_report, migration.canonical_case, manifest, context, legacy_plan,
            shadow_archive_plan=shadow_archive_plan, stage=ARCHIVE_STAGE,
        )
        _record_comparison(handle, ARCHIVE_STAGE, comparison, "after_legacy_archive_preview")
    except Exception:
        _record_failure(handle, ARCHIVE_STAGE, "SHADOW_ARCHIVE_FAILED", "after_legacy_archive_preview")
    return _summary(handle, settings, context_id, ARCHIVE_STAGE)


def run_shadow_export(
    context_id: str, report: Mapping[str, Any], manifest: Mapping[str, Any], settings: PipelineSettings,
    *, legacy_plan: Any = None, canonical_source: Mapping[str, Any] | None = None,
    run_id: str | None = None, task_token: str | None = None, legacy_export_succeeded: bool = True,
) -> dict[str, object]:
    """仅在单个旧版 DOCX 成功后观测最终准备输入。"""
    handle = _handle(settings, context_id, run_id, task_token, EXPORT_STAGE)
    if handle is None:
        return shadow_runtime_failure(settings, context_id, EXPORT_STAGE)
    context = _valid_context(handle, context_id, EXPORT_STAGE)
    if context is None:
        return _summary(handle, settings, context_id, EXPORT_STAGE)
    if not legacy_export_succeeded:
        _record_failure(handle, EXPORT_STAGE, "LEGACY_DOCX_RENDER_FAILED", "after_legacy_docx_failure")
        return _summary(handle, settings, context_id, EXPORT_STAGE)
    try:
        migration = inspection_report_to_canonical(canonical_source or report)
        canonical_report = canonical_to_inspection_report(migration.canonical_case)
        legacy_plan = legacy_plan or build_attachment_plan(manifest, report)
        shadow_archive_plan = _build_shadow_archive_plan(migration.canonical_case, context)
        comparison = _compare_archive(
            report, canonical_report, migration.canonical_case, manifest, context, legacy_plan,
            shadow_archive_plan=shadow_archive_plan, stage=EXPORT_STAGE,
        )
        _record_comparison(handle, EXPORT_STAGE, comparison, "after_legacy_docx_success")
    except Exception:
        _record_failure(handle, EXPORT_STAGE, "SHADOW_EXPORT_FAILED", "after_legacy_docx_success")
    return _summary(handle, settings, context_id, EXPORT_STAGE)


def record_shadow_export_failure(
    settings: PipelineSettings, context_id: str, *, run_id: str | None = None,
    task_token: str | None = None, code: str = "LEGACY_DOCX_RENDER_FAILED",
) -> dict[str, object]:
    handle = _handle(settings, context_id, run_id, task_token, EXPORT_STAGE, issue_new=run_id is None)
    if handle is None:
        return shadow_runtime_failure(settings, context_id, EXPORT_STAGE, code)
    _record_failure(handle, EXPORT_STAGE, code, "after_legacy_docx_failure")
    return _summary(handle, settings, context_id, EXPORT_STAGE)


def record_shadow_failure(
    settings: PipelineSettings, context_id: str | None, stage: str,
    *, run_id: str | None = None, task_token: str | None = None,
    code: str = "SHADOW_RUNTIME_FAILED",
) -> dict[str, object]:
    handle = _handle(settings, context_id, run_id, task_token, stage, issue_new=run_id is None)
    if handle is None:
        return shadow_runtime_failure(settings, context_id, stage, code)
    _record_failure(handle, stage, code, "controller_boundary")
    return _summary(handle, settings, context_id, stage)


def _compare_archive(
    report: Mapping[str, Any], canonical_report: Mapping[str, Any], canonical_case: Any,
    manifest: Mapping[str, Any], context: Any, legacy_plan: Any, *, shadow_archive_plan: Any,
    stage: str,
):
    legacy = with_archive_facts(snapshot_from_legacy_report(report), manifest, context, legacy_plan, expected=False)
    shadow = with_archive_facts(
        snapshot_from_canonical(canonical_case), manifest, context, None,
        expected=True, expected_plan=shadow_archive_plan, expected_report=canonical_report,
    )
    return compare_shadow_snapshots(legacy, shadow, stage=stage)


def _handle(
    settings: PipelineSettings, context_id: str | None, run_id: str | None,
    task_token: str | None, stage: str, *, issue_new: bool = False,
):
    if run_id:
        return ShadowRunHandle(run_id, context_id, task_token)
    return SHADOW_RUNTIME_STORE.issue_stage(settings, context_id, stage, new_run=stage == PARSE_STAGE)


def _valid_context(handle: ShadowRunHandle, context_id: str, stage: str):
    try:
        return ARCHIVE_RUNTIME_STORE.get_context_snapshot(context_id)
    except ArchiveRuntimeError as error:
        _record_not_comparable(handle, stage, error.code, "archive_context_validation")
        return None


def _build_shadow_archive_plan(canonical_case: Any, context: Any):
    inventory = getattr(context, "inventory", None)
    files = getattr(inventory, "files", ())
    entries = tuple(
        ArchiveSourceEntry(item.relative_path, item.size_bytes, item.modified_time_ns)
        for item in files if isinstance(item.relative_path, str)
    )
    case_summary = getattr(canonical_case.case_info.introduction, "case_summary", "")
    first_disc = canonical_case.attachments.disc_number or None
    return plan_archive(case_summary, entries, first_disc_number=first_disc)


def _record_comparison(handle: ShadowRunHandle, stage: str, comparison: Any, observation_point: str) -> None:
    SHADOW_RUNTIME_STORE.record(
        handle.run_id,
        ShadowStageRecord(
            stage, comparison.status, comparison, comparison.diagnostic_codes,
            observation_point, handle.task_token,
        ),
        task_token=handle.task_token,
    )


def _record_failure(handle: ShadowRunHandle, stage: str, code: str, observation_point: str) -> None:
    SHADOW_RUNTIME_STORE.record(
        handle.run_id,
        ShadowStageRecord(stage, "failed", diagnostic_codes=(code,), observation_point=observation_point, task_token=handle.task_token),
        task_token=handle.task_token,
    )


def _record_not_comparable(handle: ShadowRunHandle, stage: str, code: str, observation_point: str) -> None:
    SHADOW_RUNTIME_STORE.record(
        handle.run_id,
        ShadowStageRecord(stage, "not_comparable", diagnostic_codes=(code,), observation_point=observation_point, task_token=handle.task_token),
        task_token=handle.task_token,
    )


def _summary(handle: ShadowRunHandle, settings: PipelineSettings, context_id: str | None, stage: str):
    return SHADOW_RUNTIME_STORE.public_summary(run_id=handle.run_id) or shadow_runtime_failure(settings, context_id, stage)


__all__ = [
    "ARCHIVE_STAGE", "EXPORT_STAGE", "PARSE_STAGE", "SHADOW_RUNTIME_STORE",
    "begin_shadow_stage", "public_pipeline_metadata", "record_shadow_export_failure",
    "record_shadow_failure",
    "run_shadow_archive", "run_shadow_export", "run_shadow_parse",
]
