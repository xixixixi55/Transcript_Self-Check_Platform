"""Approved template discovery, validation, and case-reference updates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..repository.case_template_reference_repository import CaseTemplateReferenceRepository
from ..repository.template_approval_repository import TemplateApprovalRepository
from ..repository.template_registry_repository import TemplateRegistryRepository
from ..repository.workbench_database import WorkbenchDatabase
from .template_profile_service import (
    require_registered_template,
    validate_registered_template,
)


class TemplateRegistryService:
    def __init__(
        self,
        database: WorkbenchDatabase,
        registry: TemplateRegistryRepository,
        approvals: TemplateApprovalRepository,
    ) -> None:
        self.registry = registry
        self.approvals = approvals
        self.references = CaseTemplateReferenceRepository(database)

    def list_available(self) -> list[dict[str, Any]]:
        available = []
        for candidate in self.approvals.list_approved():
            result = self.validate(candidate["template_ref"])
            if result["valid"]:
                available.append(result["template"])
        return available

    def validate(self, template_ref: Mapping[str, Any]) -> dict[str, Any]:
        return validate_registered_template(self.registry, self.approvals, template_ref)

    def select_for_case(
        self, case_id: str, template_ref: Mapping[str, Any], expected_revision: int,
    ) -> dict[str, Any]:
        template = require_registered_template(
            self.registry, self.approvals, template_ref,
        )
        draft = self.references.update(
            case_id, template["template_ref"], expected_revision,
        )
        return {
            "draft": draft,
            "impact": {
                "word_artifact_validity": "invalidated_by_template_change",
                "archive_plan_changed": False,
                "archive_task_created": False,
                "manifest_changed": False,
                "disc_mapping_changed": False,
            },
        }
