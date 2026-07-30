"""T018 immutable template registry and approval persistence tests."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.template_approval_repository import TemplateApprovalRepository  # noqa: E402
from app.repository.template_registry_repository import TemplateRegistryRepository  # noqa: E402
from app.repository.workbench_database import WorkbenchDatabase  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.template_profile_service import (  # noqa: E402
    CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    CURRENT_TEMPLATE_VALIDATION_RULE,
)

ROOT = Path(__file__).parents[1]
SOURCE_TEMPLATE = ROOT / "word_templates" / "template.docx"
REFERENCE = {"template_id": "template-SYNTHETIC-record", "version": "1.0.0"}


@pytest.fixture()
def registry(tmp_path: Path):
    assets = tmp_path / "controlled-template-assets"
    assets.mkdir()
    template = assets / "SYNTHETIC-template.docx"
    shutil.copy2(SOURCE_TEMPLATE, template)
    database = WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-TEMPLATE")
    versions = TemplateRegistryRepository(database, (assets,))
    approvals = TemplateApprovalRepository(database, versions)
    return database, versions, approvals, template


def version(reference=REFERENCE, *, asset_id="asset-SYNTHETIC-template"):
    return {
        "schema_version": 1,
        "template_ref": dict(reference),
        "display_name": "SYNTHETIC 已审核模板",
        "fingerprint": CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
        "validation_rules": [CURRENT_TEMPLATE_VALIDATION_RULE],
        "asset_id": asset_id,
        "registered_at": "2026-07-30T00:00:00+00:00",
    }


def approval(status="approved", *, record_id="approval-SYNTHETIC-001", hour=1):
    return {
        "approval_record_id": record_id,
        "status": status,
        "acceptance_summary": "SYNTHETIC fixture acceptance",
        "recorded_at": f"2026-07-30T{hour:02d}:00:00+00:00",
    }


def test_approved_version_persists_and_public_projection_is_path_free(registry):
    database, versions, approvals, template = registry
    versions.register(version(), template)
    approvals.record(REFERENCE, approval())

    restarted = TemplateRegistryRepository(database, (template.parent,))
    restarted_approvals = TemplateApprovalRepository(database, restarted)
    public = restarted_approvals.list_approved()

    assert len(public) == 1
    assert public[0]["template_ref"] == REFERENCE
    assert public[0]["fingerprint"] == CURRENT_TEMPLATE_PACKAGE_FINGERPRINT
    assert public[0]["approval_record"]["status"] == "approved"
    assert "internal_locator" not in public[0]
    assert str(template) not in repr(public)


def test_published_version_and_approval_records_are_immutable(registry):
    _, versions, approvals, template = registry
    versions.register(version(), template)
    assert versions.register(version(), template)["template_ref"] == REFERENCE
    changed = version()
    changed["display_name"] = "SYNTHETIC forbidden overwrite"
    with pytest.raises(WorkbenchPersistenceError) as error:
        versions.register(changed, template)
    assert error.value.code == "TEMPLATE_VERSION_IMMUTABLE"

    approvals.record(REFERENCE, approval())
    changed_approval = approval()
    changed_approval["acceptance_summary"] = "SYNTHETIC forbidden overwrite"
    with pytest.raises(WorkbenchPersistenceError) as error:
        approvals.record(REFERENCE, changed_approval)
    assert error.value.code == "TEMPLATE_APPROVAL_IMMUTABLE"


def test_latest_approval_status_governs_selection_without_deleting_version(registry):
    _, versions, approvals, template = registry
    versions.register(version(), template)
    approvals.record(REFERENCE, approval())
    approvals.record(
        REFERENCE,
        approval("revoked", record_id="approval-SYNTHETIC-revoked", hour=2),
    )

    assert approvals.list_approved() == []
    assert versions.get_internal(REFERENCE)["template_ref"] == REFERENCE
    with pytest.raises(WorkbenchPersistenceError) as error:
        approvals.require_approved(REFERENCE)
    assert error.value.code == "TEMPLATE_NOT_APPROVED"


def test_unknown_version_and_uncontrolled_asset_are_safely_rejected(registry, tmp_path):
    _, versions, approvals, _ = registry
    with pytest.raises(WorkbenchPersistenceError) as error:
        approvals.require_approved(REFERENCE)
    assert error.value.code == "TEMPLATE_UNKNOWN"

    outside = tmp_path / "outside.docx"
    shutil.copy2(SOURCE_TEMPLATE, outside)
    with pytest.raises(WorkbenchPersistenceError) as error:
        versions.register(version(), outside)
    assert error.value.code == "TEMPLATE_ASSET_OUTSIDE_CONTROLLED_ROOT"
