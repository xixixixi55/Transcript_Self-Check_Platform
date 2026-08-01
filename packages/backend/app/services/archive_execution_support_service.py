"""Small shared guards for the synchronous archive execution pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..repository.filesystem_identity_repository import directory_fingerprint_matches
from .archive_manifest_access_service import ArchiveGateError
from .export_gate_service import ExportGateCode, ExportGateIssue


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
