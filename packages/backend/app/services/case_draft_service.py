"""Case submission, Legacy parse worker, draft initialization and retry."""

from __future__ import annotations

import copy
import secrets
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ..repository.case_workflow_repository import CaseWorkflowRepository
from ..repository.task_record_repository import TaskRecordRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError
from .report_parser_service import parse_report
from .disc_sequence_service import apply_disc_sequence_to_attachments
from .case_order_service import CaseOrderService
from .field_provenance_service import FieldProvenanceService
from .material_policy_service import enrich_report_material_types
from .shared_defaults_service import SharedDefaultsService
from .source_record_service import SourceRecordService

Parser = Callable[[Path, Path], Mapping[str, Any]]
Dispatch = Callable[[str, str], None]


class CaseDraftService:
    def __init__(
        self, database: WorkbenchDatabase, parser: Parser | None = None,
        source_service: SourceRecordService | None = None,
    ) -> None:
        self.database = database
        self.workflow = CaseWorkflowRepository(database)
        self.shells = CaseShellRepository(database)
        self.drafts = CaseDraftRepository(database)
        self.tasks = TaskRecordRepository(database)
        self.sources = source_service or SourceRecordService(database)
        self.defaults = SharedDefaultsService(database)
        self.parser = parser or _parse_source

    def submit(
        self, source: Mapping[str, Any], *, case_name: str = "", case_summary: str = "", case_number: str | None = None,
        identity: Mapping[str, Any] | None = None, dispatch: Dispatch | None = None,
    ) -> dict[str, str]:
        case_id = _opaque_id("case")
        task_id = _opaque_id("task")
        descriptor = dict(source)
        descriptor.update({"case_id": case_id, "task_id": task_id, "access_status": "pending"})
        try:
            self.workflow.create_submission(
                {"case_id": case_id, "case_name": case_name, "case_summary": case_summary, "case_number": case_number},
                {"task_id": task_id, "case_id": case_id}, descriptor, identity,
            )
        except Exception:
            self.sources.remove_unbound_source(descriptor)
            raise
        if dispatch is not None:
            try:
                dispatch(case_id, task_id)
            except Exception as error:
                self.mark_dispatch_failed(case_id, task_id)
                raise WorkbenchPersistenceError("TASK_DISPATCH_FAILED") from error
        return {"case_id": case_id, "task_id": task_id, "source_id": str(source["source_id"])}

    def run_parse_task(self, case_id: str, task_id: str, source_id: str | None = None) -> None:
        parsed: Mapping[str, Any] | None = None
        try:
            shell = self.shells.get(case_id)
            source_id = source_id or shell["source_id"]
            if source_id != shell["source_id"]:
                raise WorkbenchPersistenceError("SOURCE_CASE_MISMATCH")
            self.workflow.start_parse(case_id, task_id)
            self.sources.require_parse_ready(source_id)
            source_path = self.sources.internal_path(source_id)
            parsed = self.parser(source_path, self.database.database_path.parent / "parse-output")
            report = parsed.get("report")
            if not isinstance(report, Mapping):
                raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
            defaults = self.defaults.get()
            initialized, field_states = _initialize_draft(
                enrich_report_material_types(report), defaults,
            )
            default_template_ref = defaults.get("default_template_ref")
            self.workflow.complete_parse(
                case_id, task_id, initialized, field_states,
                template_ref=default_template_ref,
                case_metadata=_parse_case_metadata(parsed, initialized),
            )
        except Exception as error:
            try:
                if self.tasks.get(task_id)["status"] in {"cancelled", "cancelling"}:
                    return
            except WorkbenchPersistenceError:
                pass
            try:
                self.workflow.fail_parse(case_id, task_id, _safe_parse_error(error))
            except WorkbenchPersistenceError:
                pass
        finally:
            cleanup_root = parsed.get("_archive_source_cleanup_root") if isinstance(parsed, Mapping) else None
            if isinstance(cleanup_root, str):
                shutil.rmtree(cleanup_root, ignore_errors=True)

    def mark_dispatch_failed(self, case_id: str, task_id: str) -> None:
        self.workflow.fail_parse(case_id, task_id, "TASK_DISPATCH_FAILED")

    def retry(self, case_id: str, dispatch: Dispatch | None = None) -> dict[str, str]:
        shell = self.shells.get(case_id)
        task = self.tasks.get(shell["parse_task_id"])
        if task["kind"] != "parse" or task["status"] not in {"failed_retryable", "interrupted"}:
            raise WorkbenchPersistenceError("PARSE_RETRY_NOT_ALLOWED")
        self.sources.require_parse_ready(shell["source_id"], verify_existing=True)
        self.workflow.retry_parse(case_id, task["task_id"])
        if dispatch is not None:
            try:
                dispatch(case_id, task["task_id"])
            except Exception as error:
                self.mark_dispatch_failed(case_id, task["task_id"])
                raise WorkbenchPersistenceError("TASK_DISPATCH_FAILED") from error
        return {"case_id": case_id, "task_id": task["task_id"]}

    def shell(self, case_id: str) -> dict[str, Any]:
        return self.shells.get(case_id)


def _parse_source(path: Path, output: Path) -> Mapping[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    return parse_report(str(path), str(output), compress=False)


def _initialize_draft(report: Mapping[str, Any], defaults: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    value = copy.deepcopy(dict(report))
    now = utc_now()
    fields: dict[str, dict[str, Any]] = {}
    candidates = (
        ("document_number", ("document_number",), defaults.get("document_number")),
        ("introduction.inspection_place", ("introduction", "inspection_place"), defaults.get("inspection_place")),
        ("inspection.method", ("inspection", "method"), defaults.get("inspection_method")),
        ("inspection.hardware_device", ("inspection", "hardware_device"), defaults.get("hardware_device")),
    )
    for field_path, path, default in candidates:
        current = _read_path(value, path)
        selected, source = _select_value(current, default)
        if selected is not None and (source == "system_default" or current is None or not str(current).strip()):
            _write_path(value, path, selected)
        fields[field_path] = {
            "field_path": field_path, "source": source,
            "confirmation": "confirmed" if selected is not None else "pending",
            "revision": 0, "last_changed_at": now,
        }
    introduction = value.setdefault("introduction", {})
    parser_inspectors = introduction.get("inspectors")
    parser_snapshots = introduction.get("inspector_snapshots")
    serialized = defaults.get("inspector_order") or []
    if _has_items(parser_inspectors) or _has_items(parser_snapshots):
        inspector_source = "report"
        inspector_confirmation = "confirmed"
    elif isinstance(serialized, list) and serialized:
        introduction["inspectors"] = [_inspector_from_default(item) for item in serialized]
        inspector_source = "system_default"
        inspector_confirmation = "confirmed"
    else:
        inspector_source = "system_default"
        inspector_confirmation = "pending"
    fields["introduction.inspectors"] = {
        "field_path": "introduction.inspectors", "source": inspector_source,
        "confirmation": inspector_confirmation, "revision": 0, "last_changed_at": now,
    }
    attachments = value.setdefault("attachments", {})
    apply_disc_sequence_to_attachments(attachments)
    disc_current = attachments.get("disc_number")
    fields["attachments.disc_number"] = {
        "field_path": "attachments.disc_number", "source": "report" if isinstance(disc_current, str) and disc_current.strip() else "system_default",
        "confirmation": "confirmed" if isinstance(disc_current, str) and disc_current.strip() else "pending",
        "revision": 0, "last_changed_at": now,
    }
    ordered = CaseOrderService().initialize(value)
    return ordered, FieldProvenanceService().initialize(ordered, fields)


def _parse_case_metadata(parsed: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, str]:
    """Extract parser-only case metadata without adding fields to InspectionReport."""
    result: dict[str, str] = {}
    metadata = parsed.get("_case_metadata")
    if isinstance(metadata, Mapping):
        for key in ("case_name", "case_number", "case_summary"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                result[key] = value.strip()
    introduction = report.get("introduction")
    if "case_summary" not in result and isinstance(introduction, Mapping):
        value = introduction.get("case_summary")
        if isinstance(value, str) and value.strip():
            result["case_summary"] = value.strip()
    if "case_number" not in result:
        value = report.get("case_number")
        if isinstance(value, str) and value.strip():
            result["case_number"] = value.strip()
    return result


def _inspector_from_default(value: str) -> dict[str, str]:
    parts = value.split("|", 2)
    return {"name": parts[0], "unit": parts[1] if len(parts) > 1 else "", "badge_number": parts[2] if len(parts) > 2 else ""}


def _select_value(report_value: Any, default_value: Any) -> tuple[Any, str]:
    if report_value is not None and str(report_value).strip():
        return report_value, "report"
    if default_value is not None and str(default_value).strip():
        return default_value, "system_default"
    return None, "system_default"


def _has_items(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _read_path(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for item in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(item)
    return current


def _write_path(value: dict[str, Any], path: tuple[str, ...], item: Any) -> None:
    current = value
    for name in path[:-1]:
        child = current.get(name)
        if not isinstance(child, dict):
            child = {}
            current[name] = child
        current = child
    current[path[-1]] = item


def _safe_parse_error(error: Exception) -> str:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) and code and "PATH" not in code else "REPORT_PARSE_FAILED"


def _opaque_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(16)}"
