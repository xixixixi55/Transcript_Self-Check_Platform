"""Composition root for the persistent workbench services."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..config import OUTPUT_BASE, UPLOAD_BASE
from ..repository.workbench_database import WorkbenchDatabase, database_path_for_deployment
from .archive_authorization_service import ArchiveAuthorizationService
from .archive_attempt_service import ArchiveAttemptService
from .case_asset_service import CaseAssetService
from .case_draft_service import CaseDraftService
from .case_parse_dispatcher_service import CaseParseDispatcher
from .case_lifecycle_service import CaseLifecycleService
from .edit_lease_service import EditLeaseService
from .shared_defaults_service import SharedDefaultsService
from .source_record_service import SourceRecordService
from .task_record_service import TaskRecordService


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


def build_workbench_services(database: WorkbenchDatabase) -> WorkbenchServices:
    sources = SourceRecordService(
        database, ArchiveAuthorizationService(UPLOAD_BASE, OUTPUT_BASE),
    )
    leases = EditLeaseService(database)
    assets = CaseAssetService(database, leases)
    return WorkbenchServices(
        database=database,
        cases=CaseDraftService(database, source_service=sources),
        lifecycle=CaseLifecycleService(database, asset_service=assets),
        defaults=SharedDefaultsService(database),
        leases=leases,
        sources=sources,
        tasks=TaskRecordService(database),
        archive_attempts=ArchiveAttemptService(database, OUTPUT_BASE),
        assets=assets,
    )


_SERVICES: WorkbenchServices | None = None


def get_workbench_services() -> WorkbenchServices:
    global _SERVICES
    if _SERVICES is None:
        deployment_id = os.environ.get("BIJI_DEPLOYMENT_INSTANCE_ID", "local")
        data_root = os.environ.get("BIJI_WORKBENCH_DATA_ROOT")
        path = database_path_for_deployment(data_root, deployment_id)
        services = build_workbench_services(WorkbenchDatabase(path, deployment_id))
        services.tasks.recover_after_restart()
        if services.archive_attempts is not None:
            services.archive_attempts.recover_after_restart()
        services.leases.recover_after_restart()
        services.sources.recover_pending_after_startup(services.dispatcher)
        if services.assets is not None:
            services.assets.cleanup_orphans()
        _SERVICES = services
    return _SERVICES


def reset_workbench_services() -> None:
    """Test/support hook; production callers keep the deployment singleton."""
    global _SERVICES
    _SERVICES = None
