"""Composition root for the persistent workbench services."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..repository.workbench_database import WorkbenchDatabase, database_path_for_deployment
from .case_draft_service import CaseDraftService
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


def build_workbench_services(database: WorkbenchDatabase) -> WorkbenchServices:
    return WorkbenchServices(
        database=database,
        cases=CaseDraftService(database),
        lifecycle=CaseLifecycleService(database),
        defaults=SharedDefaultsService(database),
        leases=EditLeaseService(database),
        sources=SourceRecordService(database),
        tasks=TaskRecordService(database),
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
        _SERVICES = services
    return _SERVICES


def reset_workbench_services() -> None:
    """Test/support hook; production callers keep the deployment singleton."""
    global _SERVICES
    _SERVICES = None
