"""持久工作台服务的组合根。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..config import ARCHIVE_OUTPUT_BASE, OUTPUT_BASE, UPLOAD_BASE
from ..repository.archive.archive_storage_settings_repository import ArchiveStorageSettingsRepository
from ..repository.workbench_database import WorkbenchDatabase, database_path_for_deployment
from ..repository.archive.archive_task_repository import ArchiveTaskRepository
from ..repository.local_directory_history_repository import LocalDirectoryHistoryRepository
from ..repository.local_inspection_environment_repository import LocalInspectionEnvironmentRepository
from ..repository.resource_snapshot_repository import ResourceSnapshotRepository
from ..repository.template_approval_repository import TemplateApprovalRepository
from ..repository.template_registry_repository import TemplateRegistryRepository
from ..repository.case.case_template_reference_repository import CaseTemplateReferenceRepository
from ..repository.shared_defaults_repository import SharedDefaultsRepository
from .archive.archive_authorization_service import ArchiveAuthorizationService
from .archive.archive_attempt_service import ArchiveAttemptService
from .archive.archive_progress_service import ArchiveProgressService
from .archive.archive_resource_admission_service import ArchiveAdmissionConfig, ArchiveResourceAdmissionService
from .archive.archive_runtime_coordinator_service import ArchiveRuntimeCoordinator
from .archive.archive_runtime_resource_service import (
    ArchiveRuntimeResourceProvider,
    build_archive_admission_config,
    positive_float_env,
)
from .archive.archive_scheduler_service import ArchiveSchedulerService
from .archive.archive_source_runtime_service import prepare_archive_source
from .archive.archive_storage_settings_service import ArchiveStorageSettingsService
from .archive.archive_task_api_service import ArchiveTaskApiService
from .archive.archive_worker_service import ArchiveWorkItem, ArchiveWorkerService
from .case.case_asset_service import CaseAssetService
from .case.case_artifact_deletion_service import CaseArtifactDeletionService
from .case.case_draft_service import CaseDraftService
from .case.case_parse_dispatcher_service import CaseParseDispatcher
from .case.case_lifecycle_service import CaseLifecycleService
from .edit_lease_service import EditLeaseService
from .local_directory_picker_service import LocalDirectoryPickerService
from .inspection_environment_service import InspectionEnvironmentService
from .shared_defaults_service import SharedDefaultsService
from .source_record_service import SourceRecordService
from .task_record_service import TaskRecordService
from .template_profile_service import (
    BUILTIN_TEMPLATE_ID,
    CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    CURRENT_TEMPLATE_VERSION,
    CURRENT_TEMPLATE_VALIDATION_RULE,
    RETIRED_BUILTIN_TEMPLATE_VERSIONS,
    validate_template_package_fingerprint,
)
from .template_registry_service import TemplateRegistryService
from ..repository.runtime_paths import get_runtime_paths


@dataclass
class WorkbenchServices:
    database: WorkbenchDatabase
    cases: CaseDraftService
    lifecycle: CaseLifecycleService
    defaults: SharedDefaultsService
    leases: EditLeaseService
    sources: SourceRecordService
    tasks: TaskRecordService
    archive_attempts: ArchiveAttemptService | None = None
    dispatcher: CaseParseDispatcher = field(default_factory=CaseParseDispatcher)
    assets: CaseAssetService | None = None
    archive_progress: ArchiveProgressService | None = None
    archive_scheduler: ArchiveSchedulerService | None = None
    archive_worker: ArchiveWorkerService | None = None
    archive_runtime: ArchiveRuntimeCoordinator | None = None
    archive_api: ArchiveTaskApiService | None = None
    template_registry: TemplateRegistryRepository | None = None
    template_approvals: TemplateApprovalRepository | None = None
    templates: TemplateRegistryService | None = None
    directory_picker: LocalDirectoryPickerService | None = None
    archive_storage_settings: ArchiveStorageSettingsService | None = None


def build_workbench_services(
    database: WorkbenchDatabase,
    archive_admission_config: ArchiveAdmissionConfig | None = None,
) -> WorkbenchServices:
    sources = SourceRecordService(
        database, ArchiveAuthorizationService(
            UPLOAD_BASE, OUTPUT_BASE, (ARCHIVE_OUTPUT_BASE,),
        ),
    )
    leases = EditLeaseService(database)
    assets = CaseAssetService(database, leases)
    archive_tasks = ArchiveTaskRepository(database)
    archive_progress = ArchiveProgressService(
        archive_tasks, ResourceSnapshotRepository(database),
    )
    attempts = ArchiveAttemptService(database, ARCHIVE_OUTPUT_BASE)
    runtime_paths = get_runtime_paths()
    storage_settings = ArchiveStorageSettingsService(
        ArchiveStorageSettingsRepository(),
        default_output_root=OUTPUT_BASE,
        active_output_root=ARCHIVE_OUTPUT_BASE,
        resource_root=runtime_paths.resource_root,
    )
    template_root = runtime_paths.templates_root
    template_registry = TemplateRegistryRepository(
        database, (template_root, database.database_path.parent / "template-assets"),
    )
    template_approvals = TemplateApprovalRepository(database, template_registry)
    current_template_ref, historical_template_refs = _register_builtin_templates(
        template_registry, template_approvals, template_root,
    )
    SharedDefaultsRepository(database).ensure_default_template(
        current_template_ref, replace_refs=historical_template_refs,
    )
    CaseTemplateReferenceRepository(database).replace_builtin_versions(
        BUILTIN_TEMPLATE_ID, RETIRED_BUILTIN_TEMPLATE_VERSIONS, current_template_ref,
    )
    template_registry.remove_builtin_versions(
        BUILTIN_TEMPLATE_ID, RETIRED_BUILTIN_TEMPLATE_VERSIONS,
    )
    admission_config = archive_admission_config or build_archive_admission_config()
    archive_scheduler = ArchiveSchedulerService(
        archive_tasks,
        ArchiveResourceAdmissionService(admission_config),
    )
    archive_worker = ArchiveWorkerService(archive_tasks, archive_progress)
    resource_provider = ArchiveRuntimeResourceProvider(ARCHIVE_OUTPUT_BASE)
    inspection_environment = InspectionEnvironmentService(
        LocalInspectionEnvironmentRepository(),
    )
    services = WorkbenchServices(
        database=database,
        cases=CaseDraftService(
            database,
            source_service=sources,
            environment_service=inspection_environment,
        ),
        lifecycle=CaseLifecycleService(
            database, asset_service=assets,
            artifact_deletion_service=CaseArtifactDeletionService(
                database,
                OUTPUT_BASE,
                archive_output_roots=(
                    ARCHIVE_OUTPUT_BASE,
                    OUTPUT_BASE,
                    runtime_paths.output_root,
                ),
            ),
        ),
        defaults=SharedDefaultsService(database),
        leases=leases,
        sources=sources,
        tasks=TaskRecordService(database),
        archive_attempts=attempts,
        assets=assets,
        archive_progress=archive_progress,
        archive_scheduler=archive_scheduler,
        archive_worker=archive_worker,
        template_registry=template_registry,
        template_approvals=template_approvals,
        templates=TemplateRegistryService(database, template_registry, template_approvals),
        directory_picker=LocalDirectoryPickerService(
            history=LocalDirectoryHistoryRepository(),
        ),
        archive_storage_settings=storage_settings,
    )
    services.archive_runtime = ArchiveRuntimeCoordinator(
        archive_scheduler,
        archive_worker,
        attempts,
        archive_progress,
        item_factory=lambda claim, context_id, cancellation_check: _archive_work_item(
            attempts, storage_settings, claim, context_id, cancellation_check,
        ),
        snapshot_provider=resource_provider.snapshot,
        poll_interval_seconds=positive_float_env(
            "BIJI_ARCHIVE_POLL_INTERVAL_SECONDS", 1.0,
        ),
        shutdown_timeout_seconds=positive_float_env(
            "BIJI_ARCHIVE_SHUTDOWN_TIMEOUT_SECONDS", 30.0,
        ),
    )
    services.archive_api = ArchiveTaskApiService(
        database, attempts, sources, archive_progress, services.archive_runtime,
        legacy_output_roots=(OUTPUT_BASE,),
    )
    return services


def _archive_work_item(
    attempts: ArchiveAttemptService,
    storage_settings: ArchiveStorageSettingsService,
    claim: object,
    context_id: str,
    cancellation_check: Callable[[], bool],
) -> ArchiveWorkItem:
    storage_settings.require_ready_for_new_archive()
    attempt_id = str(getattr(claim, "attempt_id"))
    report = attempts.workbench_report(attempt_id, context_id)
    formal_context_id = prepare_archive_source(
        context_id,
        report,
        output_root=ARCHIVE_OUTPUT_BASE,
        cancellation_check=cancellation_check,
    )
    return ArchiveWorkItem(
        formal_context_id,
        report,
        ARCHIVE_OUTPUT_BASE,
        attempts,
        workbench_context_id=context_id,
        configured_winrar_path=os.environ.get("BIJI_WINRAR_PATH"),
    )


def _register_builtin_templates(
    registry: TemplateRegistryRepository,
    approvals: TemplateApprovalRepository,
    template_root: Path,
) -> tuple[dict[str, str], tuple[dict[str, str], ...]]:
    current_asset = template_root / "template.docx"
    validate_template_package_fingerprint(
        str(current_asset), CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    )
    reference = {
        "template_id": BUILTIN_TEMPLATE_ID, "version": CURRENT_TEMPLATE_VERSION,
    }
    registry.relocate_builtin_asset(
        reference,
        CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
        "template-asset-current-v1-private-clean",
        current_asset,
    )
    _register_builtin_template(
        registry, approvals, reference,
        "电子数据检查笔录（current-template-v1）",
        CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
        "template-asset-current-v1-private-clean",
        "template-approval-current-v1-private-clean",
        current_asset,
        "current-template-v1 已清除隐藏隐私元数据，正文与版式保持不变。",
    )
    retired_references = tuple(
        {"template_id": BUILTIN_TEMPLATE_ID, "version": version}
        for version in sorted(RETIRED_BUILTIN_TEMPLATE_VERSIONS)
    )
    return reference, retired_references


def _register_builtin_template(
    registry: TemplateRegistryRepository,
    approvals: TemplateApprovalRepository,
    reference: dict[str, str],
    display_name: str,
    fingerprint: str,
    asset_id: str,
    approval_id: str,
    asset_path: Path,
    acceptance_summary: str,
) -> None:
    existing = registry.find_internal(reference)
    effective_display_name = (
        existing["display_name"] if existing is not None else display_name
    )
    registry.register({
        "schema_version": 1,
        "template_ref": reference,
        "display_name": effective_display_name,
        "fingerprint": fingerprint,
        "validation_rules": [CURRENT_TEMPLATE_VALIDATION_RULE],
        "asset_id": asset_id,
        "registered_at": "2026-07-30T00:00:00+00:00",
    }, asset_path)
    approvals.record(reference, {
        "approval_record_id": approval_id,
        "status": "approved",
        "acceptance_summary": acceptance_summary,
        "recorded_at": "2026-07-30T00:00:00+00:00",
    })


_SERVICES: WorkbenchServices | None = None


def get_workbench_services() -> WorkbenchServices:
    global _SERVICES
    if _SERVICES is None:
        deployment_id = os.environ.get("BIJI_DEPLOYMENT_INSTANCE_ID", "local")
        data_root = os.environ.get("BIJI_WORKBENCH_DATA_ROOT")
        path = database_path_for_deployment(data_root, deployment_id)
        services = build_workbench_services(WorkbenchDatabase(path, deployment_id))
        services.tasks.recover_after_restart(include_archive=False)
        if services.archive_worker is not None and services.archive_attempts is not None:
            services.archive_worker.recover_after_restart(services.archive_attempts)
        elif services.archive_attempts is not None:
            services.archive_attempts.recover_after_restart()
        services.leases.recover_after_restart()
        services.sources.recover_pending_after_startup(services.dispatcher)
        if services.assets is not None:
            services.assets.cleanup_orphans()
        _SERVICES = services
    return _SERVICES


def ensure_archive_task_api(services: WorkbenchServices) -> ArchiveTaskApiService | None:
    """首次使用时为测试或自定义组合根构建公开适配器。"""
    if services.archive_api is not None:
        return services.archive_api
    if services.archive_attempts is None:
        return None
    progress = services.archive_progress
    if progress is None:
        progress = ArchiveProgressService(
            ArchiveTaskRepository(services.database),
            ResourceSnapshotRepository(services.database),
        )
        services.archive_progress = progress
    services.archive_api = ArchiveTaskApiService(
        services.database, services.archive_attempts, services.sources, progress,
        services.archive_runtime,
    )
    return services.archive_api


def reset_workbench_services() -> None:
    """测试和支持钩子；生产调用方保留部署单例。"""
    global _SERVICES
    if _SERVICES is not None:
        if _SERVICES.archive_runtime is not None:
            _SERVICES.archive_runtime.stop()
        _SERVICES.dispatcher.shutdown(wait=False)
    _SERVICES = None
