"""Atomic CaseDraft template-reference updates without archive side effects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .case_workbench_repository import CaseDraftRepository
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import json_text
from .workbench_serialization import validate_opaque_id


class CaseTemplateReferenceRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.drafts = CaseDraftRepository(database)

    def update(
        self, case_id: str, template_ref: Mapping[str, Any], expected_revision: int,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        reference = _reference(template_ref)
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT revision FROM case_drafts WHERE case_id=?", (case_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("DRAFT_NOT_FOUND")
            actual = int(row["revision"])
            if actual != expected_revision:
                raise RevisionConflictError("case_draft", expected_revision, actual)
            updated = connection.execute(
                "UPDATE case_drafts SET template_ref_json=?,revision=revision+1,"
                "updated_at=? WHERE case_id=? AND revision=?",
                (json_text(reference), utc_now(), case_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("case_draft", expected_revision, actual)
        return self.drafts.get(case_id)


def _reference(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"template_id", "version"}:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_REFERENCE")
    return {
        "template_id": validate_opaque_id(value["template_id"]),
        "version": validate_opaque_id(value["version"]),
    }
