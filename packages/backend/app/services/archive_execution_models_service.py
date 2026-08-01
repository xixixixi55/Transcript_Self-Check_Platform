"""Public orchestration models and runtime-context construction."""

from __future__ import annotations

from dataclasses import dataclass

from ..repository.archive_authorization_repository import AuthorizedInputRoot
from .archive_planner_service import ArchiveDiagnostic, ArchivePlan
from .archive_runtime_service import ARCHIVE_RUNTIME_STORE


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
) -> str:
    case_name = report.get("introduction", {}).get("case_summary", "")
    return ARCHIVE_RUNTIME_STORE.create_context(
        authorized_input, str(case_name), output_root=output_root,
        cleanup_root=cleanup_root,
    ).context_id
