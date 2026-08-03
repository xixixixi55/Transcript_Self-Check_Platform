"""Approved template discovery, validation, and case-reference updates."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..repository.case_template_reference_repository import CaseTemplateReferenceRepository
from ..repository.template_approval_repository import TemplateApprovalRepository
from ..repository.template_registry_repository import TemplateRegistryRepository
from ..repository.shared_defaults_repository import SharedDefaultsRepository
from ..repository.workbench_database import WorkbenchDatabase
from ..repository.workbench_database import utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError
from .docx_package_service import compute_ooxml_package_fingerprint
from .template_profile_service import (
    CURRENT_TEMPLATE_VALIDATION_RULE,
    validate_current_template_profile,
    require_registered_template,
    validate_registered_template,
)


class TemplateRegistryService:
    def __init__(
        self,
        database: WorkbenchDatabase,
        registry: TemplateRegistryRepository,
        approvals: TemplateApprovalRepository,
        defaults: SharedDefaultsRepository | None = None,
    ) -> None:
        self.registry = registry
        self.approvals = approvals
        self.references = CaseTemplateReferenceRepository(database)
        self.defaults = defaults or SharedDefaultsRepository(database)

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

    def list_management(self) -> dict[str, Any]:
        defaults = self.defaults.get()
        default_ref = defaults.get("default_template_ref")
        records: list[dict[str, Any]] = []
        for candidate in self.approvals.list_approved():
            result = self.validate(candidate["template_ref"])
            if not result["valid"]:
                continue
            reference = candidate["template_ref"]
            is_default = _same_ref(reference, default_ref)
            records.append({
                **result["template"],
                "is_default": is_default,
                "can_delete": not is_default and not self.references.is_referenced(reference),
            })
        return {
            "templates": records,
            "default_template_ref": default_ref,
            "defaults_revision": defaults["revision"],
        }

    def set_default(
        self, template_ref: Mapping[str, Any], expected_revision: int | None = None,
    ) -> dict[str, Any]:
        template = require_registered_template(self.registry, self.approvals, template_ref)
        defaults = self.defaults.get()
        revision = defaults["revision"] if expected_revision is None else expected_revision
        self.defaults.patch({"default_template_ref": template["template_ref"]}, revision)
        return self.list_management()

    def register_uploaded(
        self, template_ref: Mapping[str, Any], display_name: str, asset_path: str | Path,
    ) -> dict[str, Any]:
        path = Path(asset_path)
        try:
            fingerprint = compute_ooxml_package_fingerprint(path)
            from docx import Document
            validate_current_template_profile(
                str(path), Document(str(path)), fingerprint,
            )
        except Exception as error:
            raise WorkbenchPersistenceError("TEMPLATE_RULE_VALIDATION_FAILED") from error
        reference = {
            "template_id": template_ref.get("template_id"),
            "version": template_ref.get("version"),
        }
        self.registry.register({
            "schema_version": 1,
            "template_ref": reference,
            "display_name": display_name,
            "fingerprint": fingerprint,
            "validation_rules": [CURRENT_TEMPLATE_VALIDATION_RULE],
            "asset_id": f"template-asset-upload-{secrets.token_hex(16)}",
            "registered_at": utc_now(),
        }, path)
        self.approvals.record(reference, {
            "approval_record_id": f"template-approval-upload-{secrets.token_hex(16)}",
            "status": "approved",
            "acceptance_summary": "上传模板已通过 current-template-v1 结构校验。",
            "recorded_at": utc_now(),
        })
        result = self.validate(reference)
        if not result["valid"]:
            raise WorkbenchPersistenceError(str(result.get("error_code", "TEMPLATE_RULE_VALIDATION_FAILED")))
        return result["template"]

    def remove(self, template_ref: Mapping[str, Any]) -> dict[str, Any]:
        template = self.registry.get_internal(template_ref)
        self.approvals.require_approved(template["template_ref"])
        defaults = self.defaults.get()
        if _same_ref(template["template_ref"], defaults.get("default_template_ref")):
            raise WorkbenchPersistenceError("DEFAULT_TEMPLATE_CANNOT_DELETE")
        if self.references.is_referenced(template["template_ref"]):
            raise WorkbenchPersistenceError("TEMPLATE_IN_USE")
        self.approvals.record(template["template_ref"], {
            "approval_record_id": f"template-revocation-{secrets.token_hex(16)}",
            "status": "revoked",
            "acceptance_summary": "模板管理中已移除该版本。",
            "recorded_at": utc_now(),
        })
        return self.list_management()


def _same_ref(left: Any, right: Any) -> bool:
    return isinstance(left, Mapping) and isinstance(right, Mapping) and (
        left.get("template_id") == right.get("template_id")
        and left.get("version") == right.get("version")
    )
